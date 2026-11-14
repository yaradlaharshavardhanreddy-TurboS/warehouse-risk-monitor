
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL_DB = ROOT / "data" / "warehouse_monitor.db"

BASE_TABLES = (
    "warehouses",
    "storage_requirements",
    "zones",
    "inventory_lots",
    "lot_zone_assignments",
    "sensors",
    "sensor_zone_assignments",
    "sensor_readings",
    "door_events",
)

ALIGN_COLUMNS = {
    "warehouses": ("created_at", "updated_at"),
    "zones": ("created_at",),
    "sensors": (
        "installation_date",
        "calibration_due_date",
        "created_at",
    ),
    "sensor_zone_assignments": (
        "effective_from",
        "created_at",
    ),
}

EXPECTED_CHANGES = 2620

GENERATOR_MODULES = (
    "app.generator.master_data",
    "app.generator.requirement_data",
    "app.generator.zone_data",
    "app.generator.inventory_data",
    "app.generator.sensor_data",
    "app.generator.sensor_reading_data",
    "app.generator.door_event_data",
)

READING_TIME_CANDIDATES = (
    "reading_timestamp",
    "recorded_at",
    "reading_time",
    "timestamp",
    "reading_date",
)


def q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=120)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(
        f"PRAGMA table_info({q(table)})"
    ).fetchall()

    if not rows:
        raise RuntimeError(f"Missing table: {table}")

    return [row["name"] for row in rows]


def primary_key_columns(
    conn: sqlite3.Connection,
    table: str,
) -> list[str]:
    rows = conn.execute(
        f"PRAGMA table_info({q(table)})"
    ).fetchall()

    keys = sorted(
        (row["pk"], row["name"])
        for row in rows
        if row["pk"]
    )

    if not keys:
        raise RuntimeError(f"No primary key declared for {table}")

    return [name for _, name in keys]


def create_backup() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = REAL_DB.with_name(
        f"{REAL_DB.name}.before_align_base_dates_{stamp}"
    )

    source = connect_readonly(REAL_DB)
    destination = sqlite3.connect(backup)

    try:
        source.backup(destination)
        destination.commit()

        result = destination.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if result != "ok":
            raise RuntimeError(
                f"Backup integrity check failed: {result}"
            )
    finally:
        destination.close()
        source.close()

    return backup


def build_fresh_database(temp_root: Path) -> Path:
    """
    Build an isolated project copy and run the base generators.

    The real project and real database are not used as generator targets.
    """
    fresh_project = temp_root / "fresh_project"
    fresh_project.mkdir()

    for directory in ("app", "scripts"):
        source = ROOT / directory

        if not source.is_dir():
            raise RuntimeError(f"Required directory missing: {source}")

        shutil.copytree(
            source,
            fresh_project / directory,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
            ),
        )

    for filename in ("config.py",):
        source = ROOT / filename
        if source.is_file():
            shutil.copy2(source, fresh_project / filename)

    fresh_data = fresh_project / "data"
    fresh_data.mkdir(exist_ok=True)

    fresh_db = fresh_data / "warehouse_monitor.db"

    env = os.environ.copy()
    env["WAREHOUSE_DATABASE_PATH"] = str(fresh_db.resolve())
    env["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (
                str(fresh_project.resolve()),
                env.get("PYTHONPATH", ""),
            ),
        )
    )

    def run_step(description: str, arguments: list[str]) -> None:
        print(f"  {description}", flush=True)
        subprocess.run(
            [sys.executable, *arguments],
            cwd=fresh_project,
            env=env,
            check=True,
        )

    run_step(
        "Initialize fresh database",
        [
            "-c",
            (
                "from app.database.database import initialize_database; "
                "initialize_database()"
            ),
        ],
    )

    for module in GENERATOR_MODULES:
        run_step(
            f"Run {module}",
            ["-m", module],
        )

    if not fresh_db.is_file():
        raise RuntimeError(
            f"Fresh database was not created: {fresh_db}"
        )

    check = sqlite3.connect(fresh_db)
    try:
        integrity = check.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"Fresh database integrity check failed: {integrity}"
            )
    finally:
        check.close()

    return fresh_db


def validate_schema(
    real: sqlite3.Connection,
    fresh: sqlite3.Connection,
) -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {}

    for table in BASE_TABLES:
        real_columns = table_columns(real, table)
        fresh_columns = table_columns(fresh, table)

        if real_columns != fresh_columns:
            raise RuntimeError(
                f"Schema mismatch in {table}: "
                f"real={real_columns}; fresh={fresh_columns}"
            )

        real_pk = primary_key_columns(real, table)
        fresh_pk = primary_key_columns(fresh, table)

        if real_pk != fresh_pk:
            raise RuntimeError(
                f"Primary-key mismatch in {table}"
            )

        keys[table] = real_pk

    for table, columns in ALIGN_COLUMNS.items():
        available = set(table_columns(real, table))

        for column in columns:
            if column not in available:
                raise RuntimeError(
                    f"Required column missing: {table}.{column}"
                )

    return keys


def compare_table(
    real: sqlite3.Connection,
    fresh: sqlite3.Connection,
    table: str,
    pk_columns: list[str],
) -> tuple[int, int]:
    columns = table_columns(real, table)
    selected = ", ".join(q(column) for column in columns)
    ordering = ", ".join(q(column) for column in pk_columns)

    sql = (
        f"SELECT {selected} FROM {q(table)} "
        f"ORDER BY {ordering}"
    )

    real_cursor = real.execute(sql)
    fresh_cursor = fresh.execute(sql)

    sentinel = object()
    different_cells = 0
    different_rows = 0

    from itertools import zip_longest

    for real_row, fresh_row in zip_longest(
        real_cursor,
        fresh_cursor,
        fillvalue=sentinel,
    ):
        if real_row is sentinel or fresh_row is sentinel:
            different_rows += 1
            different_cells += len(columns)
            continue

        row_differences = sum(
            real_row[column] != fresh_row[column]
            for column in columns
        )

        if row_differences:
            different_rows += 1
            different_cells += row_differences

    return different_cells, different_rows


def compare_all_tables(
    real: sqlite3.Connection,
    fresh: sqlite3.Connection,
    keys: dict[str, list[str]],
) -> int:
    total = 0

    print("\nNine-table comparison:", flush=True)

    for table in BASE_TABLES:
        cells, rows = compare_table(
            real,
            fresh,
            table,
            keys[table],
        )

        total += cells

        print(
            f"  {table}: {cells} differing cells, "
            f"{rows} differing rows",
            flush=True,
        )

    print(f"  Total differing cells: {total}", flush=True)
    return total


def find_reading_timestamp_column(
    conn: sqlite3.Connection,
) -> str:
    available = set(table_columns(conn, "sensor_readings"))

    for candidate in READING_TIME_CANDIDATES:
        if candidate in available:
            return candidate

    raise RuntimeError(
        "Could not identify the sensor_readings timestamp column. "
        f"Available columns: {sorted(available)}"
    )


def check_assignment_ordering(
    conn: sqlite3.Connection,
) -> list[sqlite3.Row]:
    reading_column = find_reading_timestamp_column(conn)

    return conn.execute(
        f"""
        SELECT
            a.assignment_id,
            a.sensor_id,
            a.effective_from,
            r.first_timestamp
        FROM sensor_zone_assignments AS a
        JOIN (
            SELECT
                sensor_id,
                MIN(julianday({q(reading_column)})) AS first_jd,
                MIN({q(reading_column)}) AS first_timestamp
            FROM sensor_readings
            GROUP BY sensor_id
        ) AS r
          ON r.sensor_id = a.sensor_id
        WHERE julianday(a.effective_from) > r.first_jd
        ORDER BY a.assignment_id
        """
    ).fetchall()


def update_timestamp_cells(
    real: sqlite3.Connection,
    fresh: sqlite3.Connection,
    keys: dict[str, list[str]],
) -> tuple[int, dict[str, int]]:
    total_updated = 0
    counts: dict[str, int] = {}

    for table, columns in ALIGN_COLUMNS.items():
        pk = keys[table]
        selected_columns = pk + list(columns)
        selected = ", ".join(q(column) for column in selected_columns)

        fresh_rows = fresh.execute(
            f"SELECT {selected} FROM {q(table)}"
        ).fetchall()

        real_rows = real.execute(
            f"SELECT {selected} FROM {q(table)}"
        ).fetchall()

        def row_key(row):
            return tuple(row[column] for column in pk)

        fresh_by_key = {row_key(row): row for row in fresh_rows}
        real_by_key = {row_key(row): row for row in real_rows}

        if len(fresh_by_key) != len(fresh_rows):
            raise RuntimeError(
                f"Duplicate primary keys in fresh {table}"
            )

        if len(real_by_key) != len(real_rows):
            raise RuntimeError(
                f"Duplicate primary keys in real {table}"
            )

        if fresh_by_key.keys() != real_by_key.keys():
            raise RuntimeError(
                f"Primary-key sets differ in {table}"
            )

        where_clause = " AND ".join(
            f"{q(column)} = ?" for column in pk
        )

        for column in columns:
            update_sql = (
                f"UPDATE {q(table)} "
                f"SET {q(column)} = ? "
                f"WHERE {where_clause}"
            )

            changed = 0

            for key, real_row in real_by_key.items():
                new_value = fresh_by_key[key][column]

                if real_row[column] == new_value:
                    continue

                cursor = real.execute(
                    update_sql,
                    (new_value, *key),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        f"Unexpected row count updating "
                        f"{table}.{column}, key={key}: "
                        f"{cursor.rowcount}"
                    )

                changed += 1

            counts[f"{table}.{column}"] = changed
            total_updated += changed

    return total_updated, counts


def main() -> None:
    print("========== ALIGN BASE DATABASE DATES ==========")
    print(f"Project: {ROOT}")
    print(f"Database: {REAL_DB}")

    if not REAL_DB.is_file():
        raise RuntimeError(f"Database not found: {REAL_DB}")

    # The backup is created before the fresh build or any database writes.
    print("\n[1] Creating timestamped backup", flush=True)
    backup = create_backup()
    print(f"PASS: {backup}", flush=True)

    # Build the fresh database in an isolated temporary project.
    print("\n[2] Building fresh base database", flush=True)

    with tempfile.TemporaryDirectory(
        prefix="warehouse_align_base_dates_"
    ) as temporary_directory:
        fresh_path = build_fresh_database(
            Path(temporary_directory)
        )

        print(f"PASS: {fresh_path}", flush=True)

        fresh = connect_readonly(fresh_path)

        try:
            real_readonly = connect_readonly(REAL_DB)

            try:
                keys = validate_schema(real_readonly, fresh)

                print("\n[3] Checking current differences")
                before = compare_all_tables(
                    real_readonly,
                    fresh,
                    keys,
                )
            finally:
                real_readonly.close()

            print(
                f"\nDifferences before alignment: {before}",
                flush=True,
            )

            # Open the real database for the single update transaction.
            writable = sqlite3.connect(
                REAL_DB,
                timeout=120,
            )
            writable.row_factory = sqlite3.Row

            try:
                writable.execute("PRAGMA foreign_keys = ON")
                writable.execute("BEGIN IMMEDIATE")

                print("\n[4] Updating specified timestamp columns")

                updated, column_counts = update_timestamp_cells(
                    writable,
                    fresh,
                    keys,
                )

                for column, count in column_counts.items():
                    print(f"  {column}: {count}")

                print(f"  Total updated: {updated}")

                if updated not in (0, EXPECTED_CHANGES):
                    raise RuntimeError(
                        f"Unexpected number of changed cells: {updated}. "
                        f"Expected 0 or {EXPECTED_CHANGES}."
                    )

                # Required temporal validation before commit.
                print("\n[5] Checking assignment ordering")

                ordering_errors = check_assignment_ordering(writable)

                if ordering_errors:
                    print(
                        f"FAIL: {len(ordering_errors)} ordering violations"
                    )

                    for row in ordering_errors[:20]:
                        print(dict(row))

                    raise RuntimeError(
                        "An assignment begins after its sensor's "
                        "first reading. Transaction will roll back."
                    )

                print("PASS: No assignment ordering violations.")

                # Foreign-key validation before commit.
                print("\n[6] Checking foreign keys")

                fk_errors = writable.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()

                if fk_errors:
                    for row in fk_errors[:20]:
                        print(tuple(row))

                    raise RuntimeError(
                        "Foreign-key violations found. "
                        "Transaction will roll back."
                    )

                print("PASS: No foreign-key violations.")

                # All nine tables must match before the transaction commits.
                print("\n[7] Comparing all nine base tables")

                differences = compare_all_tables(
                    writable,
                    fresh,
                    keys,
                )

                if differences != 0:
                    raise RuntimeError(
                        f"{differences} differences remain. "
                        "Transaction will roll back."
                    )

                print("PASS: All nine tables match.")

                writable.commit()
                print("PASS: Transaction committed.", flush=True)

            except Exception:
                if writable.in_transaction:
                    writable.rollback()
                    print(
                        "ROLLBACK: Transaction changes were not committed.",
                        flush=True,
                    )
                raise

            finally:
                writable.close()

            # Post-commit checks.
            print("\n[8] Post-commit database checks")

            verify = connect_readonly(REAL_DB)

            try:
                integrity_rows = verify.execute(
                    "PRAGMA integrity_check"
                ).fetchall()

                print("integrity_check:")
                for row in integrity_rows:
                    print(f"  {row[0]}")

                if (
                    len(integrity_rows) != 1
                    or integrity_rows[0][0] != "ok"
                ):
                    raise RuntimeError(
                        "Post-commit integrity_check failed."
                    )

                fk_errors = verify.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()

                print("foreign_key_check:")

                if fk_errors:
                    for row in fk_errors:
                        print(f"  {tuple(row)}")

                    raise RuntimeError(
                        "Post-commit foreign-key check failed."
                    )

                print("  No violations.")

                print("\n[9] Final comparison")

                final_differences = compare_all_tables(
                    verify,
                    fresh,
                    keys,
                )

                if final_differences != 0:
                    raise RuntimeError(
                        f"Final comparison found "
                        f"{final_differences} differences."
                    )

            finally:
                verify.close()

        finally:
            fresh.close()

    print("\n========== ALIGNMENT COMPLETE ==========")
    print(f"Cells updated in this run: {updated}")
    print("integrity_check: ok")
    print("foreign_key_check: no violations")
    print("Nine base tables: 0 differing cells")
    print(f"Backup preserved: {backup}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
