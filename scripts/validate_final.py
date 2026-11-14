
from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLEAN_DB = ROOT / "data" / "warehouse_monitor.db"
ANOMALY_DB = ROOT / "data" / "warehouse_monitor_anomalies.db"
GROUND_TRUTH = ROOT / "docs" / "phase10" / "ground_truth.csv"
SUMMARY = ROOT / "docs" / "validation_summary.md"

REQUIRED_ANOMALY_TYPES = {
    "LOT_WRONG_TYPE_ZONE",
    "SENSOR_OVERLAPPING_ZONE",
    "SENSOR_MISSING_READINGS",
    "ALARM_LOT_LINK_DELETED",
}

# Ground-truth entity_type values are checked against these mappings.
ENTITY_TABLES = {
    "LOT": ("inventory_lots", "lot_id"),
    "INVENTORY_LOT": ("inventory_lots", "lot_id"),
    "SENSOR": ("sensors", "sensor_id"),
    "ALARM": ("alarms", "alarm_id"),
}

ISSUE_ENTITY_TYPES = {
    "LOT_WRONG_TYPE_ZONE": {"LOT", "INVENTORY_LOT"},
    "SENSOR_OVERLAPPING_ZONE": {"SENSOR"},
    "SENSOR_MISSING_READINGS": {"SENSOR"},
    "ALARM_LOT_LINK_DELETED": {"ALARM"},
}

STATUS_COLUMNS = {
    "alarms": "lifecycle_state",
    "inspections": "inspection_status",
    "remediations": "remediation_status",
}

# Authoritative mapping from app/generator/inventory_data.py
# and scripts/validate_submission.py.
PRODUCT_ZONE_MAPPING = {
    "DAIRY": "COLD",
    "PRODUCE": "COLD",
    "PHARMA": "COLD",
    "FROZEN_FOOD": "FREEZER",
    "ELECTRONICS": "AMBIENT",
}


class ValidationError(Exception):
    pass


def quote_identifier(identifier: str) -> str:
    """Safely quote a SQLite identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def connect_read_only(path: Path) -> sqlite3.Connection:
    """Open an existing SQLite database without write access."""
    if not path.is_file():
        raise ValidationError(f"Database file does not exist: {path}")

    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        raise ValidationError(f"Required table is missing: {table}")

    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        )
    }


def require_columns(
    conn: sqlite3.Connection,
    table: str,
    required: set[str],
) -> None:
    actual = get_columns(conn, table)
    missing = required - actual

    if missing:
        raise ValidationError(
            f"{table} is missing required columns: {sorted(missing)}"
        )


def check_database_integrity(
    conn: sqlite3.Connection,
) -> tuple[bool, str]:
    integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
    integrity_messages = [row[0] for row in integrity_rows]

    integrity_ok = integrity_messages == ["ok"]

    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    fk_ok = len(fk_rows) == 0

    details = [
        f"integrity_check: {'PASS' if integrity_ok else 'FAIL'}",
        f"foreign_key_check: {'PASS' if fk_ok else 'FAIL'}",
    ]

    if not integrity_ok:
        details.append(
            "Integrity errors: " + "; ".join(integrity_messages[:10])
        )

    if not fk_ok:
        details.append(f"Foreign-key violations: {len(fk_rows)}")
        for row in fk_rows[:10]:
            details.append(f"  {tuple(row)}")

    return integrity_ok and fk_ok, "; ".join(details)


def check_status_diversity(
    conn: sqlite3.Connection,
    table: str,
    status_column: str,
) -> tuple[bool, str]:
    require_columns(conn, table, {status_column})

    sql = f"""
        SELECT COUNT(DISTINCT {quote_identifier(status_column)})
        FROM {quote_identifier(table)}
        WHERE {quote_identifier(status_column)} IS NOT NULL
    """

    distinct_count = conn.execute(sql).fetchone()[0]

    values = conn.execute(
        f"""
        SELECT DISTINCT {quote_identifier(status_column)}
        FROM {quote_identifier(table)}
        WHERE {quote_identifier(status_column)} IS NOT NULL
        ORDER BY {quote_identifier(status_column)}
        """
    ).fetchall()

    statuses = [row[0] for row in values]
    passed = distinct_count > 1

    return passed, (
        f"{distinct_count} distinct statuses: {statuses}; "
        "required: more than one"
    )


def load_ground_truth() -> tuple[list[dict[str, str]], list[str]]:
    if not GROUND_TRUTH.is_file():
        raise ValidationError(f"Ground-truth CSV not found: {GROUND_TRUTH}")

    with GROUND_TRUTH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        required = {
            "ground_truth_id",
            "issue_type",
            "entity_type",
            "entity_id",
        }

        headers = set(reader.fieldnames or [])
        missing = required - headers

        if missing:
            raise ValidationError(
                f"Ground-truth CSV is missing columns: {sorted(missing)}"
            )

        rows = list(reader)

    errors = []

    if not rows:
        errors.append("Ground-truth CSV has no data rows.")

    for index, row in enumerate(rows, start=2):
        for column in required:
            if not (row.get(column) or "").strip():
                errors.append(
                    f"CSV line {index}: empty required field {column}"
                )

    return rows, errors


def validate_ground_truth_cases(
    rows: list[dict[str, str]],
) -> tuple[bool, str, dict[str, set[str]]]:
    cases = defaultdict(set)

    for row in rows:
        issue_type = row["issue_type"].strip()
        entity_id = row["entity_id"].strip()

        if issue_type in REQUIRED_ANOMALY_TYPES and entity_id:
            cases[issue_type].add(entity_id)

    details = []
    passed = True

    for issue_type in sorted(REQUIRED_ANOMALY_TYPES):
        count = len(cases[issue_type])
        type_pass = count >= 10

        if not type_pass:
            passed = False

        details.append(
            f"{issue_type}: {count} distinct entities "
            f"({'PASS' if type_pass else 'FAIL'}; minimum 10)"
        )

    unexpected = sorted(
        {
            row["issue_type"].strip()
            for row in rows
            if row["issue_type"].strip() not in REQUIRED_ANOMALY_TYPES
        }
    )

    if unexpected:
        details.append(f"Additional issue types present: {unexpected}")

    return passed, "; ".join(details), cases


def validate_ground_truth_entities(
    conn: sqlite3.Connection,
    rows: list[dict[str, str]],
) -> tuple[bool, str]:
    errors = []
    checked = 0
    existence_cache = {}

    for row in rows:
        issue_type = row["issue_type"].strip()
        entity_type = row["entity_type"].strip().upper()
        entity_id = row["entity_id"].strip()

        if issue_type not in REQUIRED_ANOMALY_TYPES:
            errors.append(
                f"Unknown issue type {issue_type!r} "
                f"for entity {entity_id!r}"
            )
            continue

        allowed_types = ISSUE_ENTITY_TYPES[issue_type]

        if entity_type not in allowed_types:
            errors.append(
                f"{issue_type}: unexpected entity_type "
                f"{entity_type!r} for {entity_id!r}"
            )
            continue

        mapping = ENTITY_TABLES.get(entity_type)

        if mapping is None:
            errors.append(
                f"No table mapping for entity_type {entity_type!r}"
            )
            continue

        table, primary_key = mapping

        try:
            require_columns(conn, table, {primary_key})
        except ValidationError as exc:
            errors.append(str(exc))
            continue

        cache_key = (table, primary_key, entity_id)

        if cache_key not in existence_cache:
            existence_cache[cache_key] = conn.execute(
                f"""
                SELECT 1
                FROM {quote_identifier(table)}
                WHERE {quote_identifier(primary_key)} = ?
                LIMIT 1
                """,
                (entity_id,),
            ).fetchone() is not None

        checked += 1

        if not existence_cache[cache_key]:
            errors.append(
                f"{issue_type}: {entity_type} {entity_id!r} "
                f"not found in {table}.{primary_key}"
            )

    if errors:
        return False, (
            f"Checked {checked} ground-truth entity references; "
            f"{len(errors)} problem(s): "
            + " | ".join(errors[:20])
        )

    return True, (
        f"All {checked} ground-truth entity references exist "
        "in the anomaly database."
    )


def check_incompatible_lot_assignments(
    conn: sqlite3.Connection,
) -> tuple[bool, str]:
    require_columns(
        conn,
        "inventory_lots",
        {"lot_id", "product_type"},
    )
    require_columns(
        conn,
        "lot_zone_assignments",
        {"lot_id", "zone_id", "released_at"},
    )
    require_columns(
        conn,
        "zones",
        {"zone_id", "zone_type"},
    )

    # Only current assignments are checked. Historical assignments
    # with a released_at timestamp are not current storage placements.
    #
    # The product-to-zone mapping is the same mapping used by the
    # project's inventory generator and submission validator.
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM lot_zone_assignments AS lza
        JOIN inventory_lots AS l
          ON l.lot_id = lza.lot_id
        JOIN zones AS z
          ON z.zone_id = lza.zone_id
        WHERE lza.released_at IS NULL
          AND (
              CASE UPPER(TRIM(l.product_type))
                  WHEN 'DAIRY' THEN 'COLD'
                  WHEN 'PRODUCE' THEN 'COLD'
                  WHEN 'PHARMA' THEN 'COLD'
                  WHEN 'FROZEN_FOOD' THEN 'FREEZER'
                  WHEN 'ELECTRONICS' THEN 'AMBIENT'
                  ELSE NULL
              END IS NULL
              OR UPPER(TRIM(z.zone_type)) !=
              CASE UPPER(TRIM(l.product_type))
                  WHEN 'DAIRY' THEN 'COLD'
                  WHEN 'PRODUCE' THEN 'COLD'
                  WHEN 'PHARMA' THEN 'COLD'
                  WHEN 'FROZEN_FOOD' THEN 'FREEZER'
                  WHEN 'ELECTRONICS' THEN 'AMBIENT'
                  ELSE NULL
              END
          )
        """
    ).fetchone()[0]

    return count == 0, (
        f"Incompatible active lot assignments: {count}; required: 0"
    )


def check_overlapping_sensor_assignments(
    conn: sqlite3.Connection,
) -> tuple[bool, str]:
    require_columns(
        conn,
        "sensor_zone_assignments",
        {
            "assignment_id",
            "sensor_id",
            "effective_from",
            "effective_to",
        },
    )

    # Two assignments for the same sensor overlap when each begins
    # before the other ends. A NULL effective_to is an open-ended interval.
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM sensor_zone_assignments AS a
        JOIN sensor_zone_assignments AS b
          ON a.sensor_id = b.sensor_id
         AND a.assignment_id < b.assignment_id
         AND a.effective_from <
             COALESCE(b.effective_to, '9999-12-31 23:59:59')
         AND b.effective_from <
             COALESCE(a.effective_to, '9999-12-31 23:59:59')
        """
    ).fetchone()[0]

    return count == 0, (
        f"Overlapping sensor assignment pairs: {count}; required: 0"
    )


def main() -> int:
    results = []
    clean_conn = None
    anomaly_conn = None

    def record(name: str, passed: bool, details: str) -> None:
        results.append({
            "name": name,
            "passed": passed,
            "details": details,
        })

    clean_open = False
    anomaly_open = False

    try:
        # ---------------------------------------------------------
        # Ground-truth file checks
        # ---------------------------------------------------------
        try:
            ground_truth_rows, csv_errors = load_ground_truth()

            csv_pass = bool(ground_truth_rows) and not csv_errors

            record(
                "Ground-truth CSV is non-empty and structurally valid",
                csv_pass,
                (
                    f"{len(ground_truth_rows)} data rows; "
                    + (
                        "; ".join(csv_errors[:10])
                        if csv_errors
                        else "required columns and values present"
                    )
                ),
            )

            cases_pass, cases_details, _ = validate_ground_truth_cases(
                ground_truth_rows
            )

            record(
                "All four anomaly types have at least 10 cases",
                cases_pass,
                cases_details,
            )

        except Exception as exc:
            ground_truth_rows = []
            record(
                "Ground-truth CSV is non-empty and structurally valid",
                False,
                str(exc),
            )
            record(
                "All four anomaly types have at least 10 cases",
                False,
                "Could not evaluate because ground-truth loading failed.",
            )

        # ---------------------------------------------------------
        # Open both databases read-only
        # ---------------------------------------------------------
        try:
            clean_conn = connect_read_only(CLEAN_DB)
            clean_open = True
            record(
                "Clean database opened read-only",
                True,
                str(CLEAN_DB),
            )
        except Exception as exc:
            record("Clean database opened read-only", False, str(exc))

        try:
            anomaly_conn = connect_read_only(ANOMALY_DB)
            anomaly_open = True
            record(
                "Anomaly database opened read-only",
                True,
                str(ANOMALY_DB),
            )
        except Exception as exc:
            record("Anomaly database opened read-only", False, str(exc))

        # ---------------------------------------------------------
        # Lifecycle status diversity
        # ---------------------------------------------------------
        if clean_open:
            for table, status_column in STATUS_COLUMNS.items():
                try:
                    passed, details = check_status_diversity(
                        clean_conn,
                        table,
                        status_column,
                    )
                    record(
                        f"{table} has more than one status",
                        passed,
                        details,
                    )
                except Exception as exc:
                    record(
                        f"{table} has more than one status",
                        False,
                        str(exc),
                    )
        else:
            for table in STATUS_COLUMNS:
                record(
                    f"{table} has more than one status",
                    False,
                    "Clean database could not be opened.",
                )

        # ---------------------------------------------------------
        # Ground-truth entity existence in anomaly database
        # ---------------------------------------------------------
        if anomaly_open and ground_truth_rows:
            try:
                passed, details = validate_ground_truth_entities(
                    anomaly_conn,
                    ground_truth_rows,
                )
                record(
                    "Every ground-truth entity exists in anomaly database",
                    passed,
                    details,
                )
            except Exception as exc:
                record(
                    "Every ground-truth entity exists in anomaly database",
                    False,
                    str(exc),
                )
        else:
            record(
                "Every ground-truth entity exists in anomaly database",
                False,
                "Anomaly database or ground-truth rows unavailable.",
            )

        # ---------------------------------------------------------
        # Clean database anomaly-free checks
        # ---------------------------------------------------------
        if clean_open:
            try:
                passed, details = check_incompatible_lot_assignments(
                    clean_conn
                )
                record(
                    "Clean database has zero incompatible lot assignments",
                    passed,
                    details,
                )
            except Exception as exc:
                record(
                    "Clean database has zero incompatible lot assignments",
                    False,
                    str(exc),
                )

            try:
                passed, details = check_overlapping_sensor_assignments(
                    clean_conn
                )
                record(
                    "Clean database has zero overlapping sensor assignments",
                    passed,
                    details,
                )
            except Exception as exc:
                record(
                    "Clean database has zero overlapping sensor assignments",
                    False,
                    str(exc),
                )
        else:
            record(
                "Clean database has zero incompatible lot assignments",
                False,
                "Clean database could not be opened.",
            )
            record(
                "Clean database has zero overlapping sensor assignments",
                False,
                "Clean database could not be opened.",
            )

        # ---------------------------------------------------------
        # Database integrity and foreign-key checks
        # ---------------------------------------------------------
        for label, conn, opened in (
            ("Clean database", clean_conn, clean_open),
            ("Anomaly database", anomaly_conn, anomaly_open),
        ):
            if opened:
                try:
                    passed, details = check_database_integrity(conn)
                    record(
                        f"{label}: integrity_check and foreign_key_check",
                        passed,
                        details,
                    )
                except Exception as exc:
                    record(
                        f"{label}: integrity_check and foreign_key_check",
                        False,
                        str(exc),
                    )
            else:
                record(
                    f"{label}: integrity_check and foreign_key_check",
                    False,
                    "Database could not be opened.",
                )

    finally:
        if clean_conn is not None:
            clean_conn.close()

        if anomaly_conn is not None:
            anomaly_conn.close()

    # -------------------------------------------------------------
    # Write Markdown summary. No database writes are performed.
    # -------------------------------------------------------------
    overall_pass = all(item["passed"] for item in results)

    lines = [
        "# Final Project Validation Summary",
        "",
        f"- Generated: {datetime.now().astimezone().isoformat()}",
        "- Database access: read-only",
        "- Database modifications: none",
        f"- Clean database: `{CLEAN_DB.relative_to(ROOT)}`",
        f"- Anomaly database: `{ANOMALY_DB.relative_to(ROOT)}`",
        f"- Ground truth: `{GROUND_TRUTH.relative_to(ROOT)}`",
        "",
        "## Validation results",
        "",
        "| Check | Result | Details |",
        "|---|---|---|",
    ]

    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        details = item["details"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {item['name']} | **{status}** | {details} |"
        )

    lines.extend([
        "",
        "## Overall result",
        "",
        f"**{'PASS' if overall_pass else 'FAIL'}**",
        "",
        f"- Checks passed: {sum(x['passed'] for x in results)}",
        f"- Checks failed: {sum(not x['passed'] for x in results)}",
        "",
        "## Safety statement",
        "",
        "- Both SQLite databases were opened using read-only connections.",
        "- SQLite connections used `PRAGMA query_only = ON`.",
        "- No database modification statements were executed.",
        "- The only file written by this script is this validation summary.",
        "",
    ])

    try:
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"ERROR: Could not write validation summary: {exc}")
        return 2

    print("========== FINAL VALIDATION ==========")

    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{status}: {item['name']}")
        print(f"  {item['details']}")

    print()
    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    print(f"Summary: {SUMMARY}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
