from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from itertools import zip_longest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL_DB = ROOT / "data" / "warehouse_monitor.db"
REPORT = ROOT / "docs" / "reproducibility_report.md"

SEED = 20261022
TABLES = [
    "warehouses",
    "storage_requirements",
    "zones",
    "inventory_lots",
    "lot_zone_assignments",
    "sensors",
    "sensor_zone_assignments",
    "sensor_readings",
    "door_events",
]

# The only approved exclusion. No other values are normalized or excluded.
EXCLUDED_COLUMNS = {
    "schema_metadata": {"applied_at"},
}

GENERATION_STEPS = [
    ("Initialize database", "initialize"),
    ("Generate warehouses", "app.generator.master_data"),
    ("Generate storage requirements", "app.generator.requirement_data"),
    ("Generate zones", "app.generator.zone_data"),
    ("Generate inventory lots", "app.generator.inventory_data"),
    ("Generate sensors and zone assignments", "app.generator.sensor_data"),
    ("Generate sensor readings", "app.generator.sensor_reading_data"),
    ("Generate door events", "app.generator.door_event_data"),
]


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def canonical_value(value):
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float):
        if value != value:
            return {"__float__": "nan"}
        if value == float("inf"):
            return {"__float__": "inf"}
        if value == float("-inf"):
            return {"__float__": "-inf"}
    return value


def canonical_json(value) -> bytes:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def table_names(connection):
    return {
        row[0]
        for row in connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
        """)
    }


def table_columns(connection, table):
    rows = connection.execute(
        f"PRAGMA table_info({quote_identifier(table)})"
    ).fetchall()
    return [row[1] for row in rows]


def ordered_rows(connection, table, columns):
    quoted_table = quote_identifier(table)
    quoted_columns = ", ".join(quote_identifier(c) for c in columns)

    if columns:
        order_clause = " ORDER BY " + ", ".join(
            quote_identifier(c) for c in columns
        )
    else:
        order_clause = ""

    return connection.execute(
        f"SELECT {quoted_columns} FROM {quoted_table}{order_clause}"
    )


def database_integrity(connection):
    result = connection.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        raise RuntimeError(f"SQLite quick_check failed: {result}")

    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if foreign_key_errors:
        raise RuntimeError(
            f"Foreign-key violations found: {len(foreign_key_errors)}; "
            f"first rows: {foreign_key_errors[:10]}"
        )


def table_signature(connection, table):
    columns = table_columns(connection, table)
    excluded = EXCLUDED_COLUMNS.get(table, set())
    included_columns = [c for c in columns if c not in excluded]

    digest = hashlib.sha256()
    row_count = 0

    if included_columns:
        cursor = ordered_rows(connection, table, included_columns)
        for row in cursor:
            digest.update(canonical_json(tuple(row)))
            digest.update(b"\n")
            row_count += 1
    else:
        row_count = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)}"
        ).fetchone()[0]

    return {
        "row_count": row_count,
        "sha256": digest.hexdigest(),
        "columns": columns,
        "included_columns": included_columns,
    }


def schema_description(connection, table):
    return [
        tuple(row)
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        ).fetchall()
    ]


def differing_columns(connection_a, connection_b, table):
    columns_a = table_columns(connection_a, table)
    columns_b = table_columns(connection_b, table)

    differences = []

    if columns_a != columns_b:
        differences.append(
            f"<schema: columns A={columns_a!r}; B={columns_b!r}>"
        )

    common = [column for column in columns_a if column in columns_b]
    common = [
        column for column in common
        if column not in EXCLUDED_COLUMNS.get(table, set())
    ]

    if not common:
        return differences or ["<no comparable columns>"]

    # Compare sorted rows cell by cell. This identifies the columns
    # responsible for differing row content without loading a whole table
    # into memory.
    cursor_a = ordered_rows(connection_a, table, common)
    cursor_b = ordered_rows(connection_b, table, common)

    missing = object()
    for row_a, row_b in zip_longest(cursor_a, cursor_b, fillvalue=missing):
        if row_a is missing or row_b is missing:
            differences.append("<missing or additional row>")
            break

        for index, column in enumerate(common):
            if canonical_json(row_a[index]) != canonical_json(row_b[index]):
                if column not in differences:
                    differences.append(column)

    if not differences:
        differences.append(
            "<row ordering/association differs despite matching column names>"
        )

    return differences


def connect_read_only(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Database does not exist: {path}")

    uri = "file:" + path.resolve().as_posix() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=60)
    connection.execute("PRAGMA query_only = ON")
    return connection


def copy_project_workspace(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)

    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".venv",
        "venv",
        "backups",
        "backup_*",
        "*.db",
        "*.db-wal",
        "*.db-shm",
    )

    for directory in ("app", "scripts"):
        source = ROOT / directory
        if not source.is_dir():
            raise FileNotFoundError(f"Required project directory missing: {source}")

        shutil.copytree(
            source,
            destination / directory,
            ignore=ignore,
        )

    config_source = ROOT / "config.py"
    if not config_source.is_file():
        raise FileNotFoundError(
            "Expected project-root config.py was not found. "
            "No workspace was generated."
        )

    shutil.copy2(config_source, destination / "config.py")
    (destination / "data").mkdir(parents=True, exist_ok=True)


def subprocess_environment(workspace: Path):
    environment = os.environ.copy()

    # Prevent deployment configuration or an inherited path override
    # from redirecting the temporary run.
    environment.pop("VERCEL", None)
    environment["WAREHOUSE_DATABASE_PATH"] = str(
        (workspace / "data" / "warehouse_monitor.db").resolve()
    )
    environment["PYTHONPATH"] = str(workspace)
    environment["PYTHONHASHSEED"] = "0"

    return environment


def run_command(workspace, environment, command, description):
    started = time.perf_counter()

    result = subprocess.run(
        command,
        cwd=workspace,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    elapsed = time.perf_counter() - started
    print(f"[TIME] {description}: {elapsed:.2f} seconds")

    if result.stdout:
        print(result.stdout.rstrip())

    if result.returncode != 0:
        raise RuntimeError(
            f"{description} failed with exit code {result.returncode}"
        )

    return elapsed


def generate_one_run(label: str, workspace: Path):
    print(f"\n========== {label}: STAGE A ==========")

    started = time.perf_counter()
    copy_project_workspace(workspace)
    copy_elapsed = time.perf_counter() - started
    print(f"[TIME] Create isolated project copy ({label}): "
          f"{copy_elapsed:.2f} seconds")

    environment = subprocess_environment(workspace)
    python = sys.executable
    total_step_times = []

    for description, module in GENERATION_STEPS:
        if module == "initialize":
            command = [
                python,
                "-c",
                "from app.database.database import initialize_database; "
                "initialize_database()",
            ]
        else:
            command = [python, "-m", module]

        elapsed = run_command(
            workspace,
            environment,
            command,
            f"{label} - {description}",
        )
        total_step_times.append((description, elapsed))

    database_path = workspace / "data" / "warehouse_monitor.db"

    if not database_path.is_file():
        raise RuntimeError(
            f"{label}: expected generated database is missing: {database_path}"
        )

    with sqlite3.connect(database_path) as connection:
        database_integrity(connection)

        actual_tables = table_names(connection)
        missing_tables = sorted(set(TABLES) - actual_tables)

        if missing_tables:
            raise RuntimeError(
                f"{label}: required base tables are missing: {missing_tables}"
            )

        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {quote_identifier(table)}"
            ).fetchone()[0]
            for table in TABLES
        }

    print(f"\n{label} base table row counts:")
    for table, count in counts.items():
        print(f"  {table}: {count:,}")

    print(f"[TIME] {label} total Stage A generation: "
          f"{sum(value for _, value in total_step_times) + copy_elapsed:.2f} seconds")

    return database_path


def compare_databases(path_a: Path, path_b: Path, label: str):
    connection_a = connect_read_only(path_a)
    connection_b = connect_read_only(path_b)

    results = {}

    try:
        database_integrity(connection_a)
        database_integrity(connection_b)

        tables_a = table_names(connection_a)
        tables_b = table_names(connection_b)

        for table in TABLES:
            started = time.perf_counter()

            if table not in tables_a or table not in tables_b:
                results[table] = {
                    "passed": False,
                    "reason": "Table missing from one or both databases",
                    "columns": ["<missing table>"],
                }
                print(f"[TIME] {label} / {table}: "
                      f"{time.perf_counter() - started:.2f} seconds")
                continue

            signature_a = table_signature(connection_a, table)
            signature_b = table_signature(connection_b, table)

            schema_a = schema_description(connection_a, table)
            schema_b = schema_description(connection_b, table)

            same_schema = schema_a == schema_b
            same_count = (
                signature_a["row_count"] == signature_b["row_count"]
            )
            same_hash = signature_a["sha256"] == signature_b["sha256"]

            passed = same_schema and same_count and same_hash

            columns = []
            if not passed:
                columns = differing_columns(
                    connection_a, connection_b, table
                )
                if not same_schema and "<schema>" not in columns:
                    columns.insert(0, "<schema>")

            results[table] = {
                "passed": passed,
                "count_a": signature_a["row_count"],
                "count_b": signature_b["row_count"],
                "hash_a": signature_a["sha256"],
                "hash_b": signature_b["sha256"],
                "columns": columns,
            }

            status = "PASS" if passed else "FAIL"
            print(
                f"[{status}] {label}: {table} "
                f"(A={signature_a['row_count']:,}, "
                f"B={signature_b['row_count']:,})"
            )
            if columns:
                print(f"       Differing columns: {', '.join(columns)}")

            print(f"[TIME] {label} / {table}: "
                  f"{time.perf_counter() - started:.2f} seconds")

    finally:
        connection_a.close()
        connection_b.close()

    return results


def render_comparison(lines, heading, results):
    lines.append(f"\n## {heading}\n")
    lines.append("| Table | Result | Rows A | Rows B | Differing columns |")
    lines.append("|---|---:|---:|---:|---|")

    for table in TABLES:
        result = results[table]
        status = "PASS" if result["passed"] else "FAIL"
        rows_a = result.get("count_a", "—")
        rows_b = result.get("count_b", "—")
        columns = ", ".join(result.get("columns", [])) or "—"
        lines.append(
            f"| `{table}` | **{status}** | {rows_a} | {rows_b} | "
            f"{columns} |"
        )

    for table in TABLES:
        result = results[table]
        if not result["passed"] and "hash_a" in result:
            lines.append(f"\n### `{table}` details\n")
            lines.append(f"- Run A SHA256: `{result['hash_a']}`")
            lines.append(f"- Run B SHA256: `{result['hash_b']}`")
            lines.append(
                f"- Differing columns: "
                f"{', '.join(result.get('columns', []))}"
            )
            if result.get("reason"):
                lines.append(f"- Reason: {result['reason']}")


def write_report(lines):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport saved: {REPORT}")


def main():
    started = time.perf_counter()
    lines = [
        "# Stage A — Reproducibility Report",
        "",
        f"- Seed: `{SEED}`",
        "- Profile: `full`",
        "- Scope: base data only",
        "- Real database access: read-only",
        "- Temporary run databases: isolated copies",
        "",
        "## Excluded columns",
        "",
        "Only the following column is excluded from row hashing:",
        "",
        "- `schema_metadata.applied_at` — generated by SQLite using "
        "the current time during schema initialization.",
        "",
        "No other columns or values are excluded, normalized, or repaired.",
        "",
        "## Generation timings",
        "",
        "The checker prints the elapsed time for each generation step "
        "for both runs.",
        "",
    ]

    failure = None

    try:
        if not REAL_DB.is_file():
            raise FileNotFoundError(
                f"Real comparison database not found: {REAL_DB}"
            )

        with tempfile.TemporaryDirectory(
            prefix="warehouse_reproducibility_"
        ) as temporary_root:
            temporary_root = Path(temporary_root)
            workspace_a = temporary_root / "run_a"
            workspace_b = temporary_root / "run_b"

            db_a = generate_one_run("RUN A", workspace_a)
            db_b = generate_one_run("RUN B", workspace_b)

            print("\n========== RUN A vs RUN B ==========")
            run_comparison = compare_databases(
                db_a,
                db_b,
                "Run A vs Run B",
            )
            render_comparison(
                lines,
                "Run A vs Run B",
                run_comparison,
            )

            print("\n========== RUN A vs REAL DATABASE (READ-ONLY) ==========")
            real_comparison = compare_databases(
                db_a,
                REAL_DB,
                "Run A vs real database",
            )
            render_comparison(
                lines,
                "Run A vs Real Database (Read-Only)",
                real_comparison,
            )

            all_results = list(run_comparison.values()) + list(
                real_comparison.values()
            )
            overall_pass = all(result["passed"] for result in all_results)

            lines.extend([
                "",
                "## Overall result",
                "",
                f"**{'PASS' if overall_pass else 'FAIL'}**",
                "",
                "- Run A and Run B must match for every listed table.",
                "- Run A must match the real database for every listed table.",
                "- Any differing table or column is reported above.",
                "- The real database was opened read-only.",
                "- No repair or normalization was performed.",
            ])

            print(
                "\nOVERALL:",
                "PASS" if overall_pass else "FAIL",
            )

    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        print(f"\nSTAGE A FAILED: {failure}")
        lines.extend([
            "",
            "## Overall result",
            "",
            "**FAIL**",
            "",
            f"Pipeline stopped: `{failure}`",
            "",
            "No repair or normalization was attempted.",
        ])

    elapsed = time.perf_counter() - started
    lines.extend([
        "",
        "## Total elapsed time",
        "",
        f"{elapsed:.2f} seconds",
    ])

    write_report(lines)

    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
