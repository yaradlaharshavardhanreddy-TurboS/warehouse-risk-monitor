
import csv
import hashlib
import json
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_DIR = ROOT / "docs" / "phase10"

OUTPUT_CSV = OUTPUT_DIR / "ground_truth.csv"
OUTPUT_CATALOG = OUTPUT_DIR / "anomaly_catalog.md"
OUTPUT_MANIFEST = OUTPUT_DIR / "source_manifest.json"

# Reading gaps shorter than this are not flagged.
MIN_GAP_SECONDS = 10 * 60

OUTPUT_FIELDS = [
    "ground_truth_id",
    "issue_type",
    "entity_type",
    "entity_id",
    "related_entity_ids",
    "evidence",
    "label_status",
    "source_tables",
]


def table_columns(connection, table_name):
    return {
        row["name"]
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        )
    }


def first_column(columns, candidates):
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def parse_timestamp(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        # Support Unix timestamps in seconds or milliseconds.
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None

    value = str(value).strip()
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def json_text(value):
    return json.dumps(value, sort_keys=True, default=str)


def add_candidate(
    candidates,
    issue_type,
    entity_type,
    entity_id,
    related_ids,
    evidence,
    source_tables,
):
    candidates.append({
        "issue_type": issue_type,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "related_entity_ids": json_text(related_ids),
        "evidence": json_text(evidence),
        "label_status": "REVIEW_REQUIRED",
        "source_tables": json_text(source_tables),
    })


def detect_multi_zone_sensors(connection, candidates):
    table = "sensor_zone_assignments"
    existing = {
        row["name"]
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        )
    } if table in get_tables(connection) else set()

    sensor_col = first_column(existing, ["sensor_id"])
    zone_col = first_column(existing, ["zone_id"])

    if not sensor_col or not zone_col:
        print("SKIP: Multi-zone sensor check (required columns unavailable)")
        return

    rows = connection.execute(
        f'SELECT "{sensor_col}", "{zone_col}" FROM "{table}"'
    ).fetchall()

    zones_by_sensor = defaultdict(set)
    for row in rows:
        if row[0] is not None and row[1] is not None:
            zones_by_sensor[str(row[0])].add(str(row[1]))

    count = 0
    for sensor_id, zone_ids in sorted(zones_by_sensor.items()):
        if len(zone_ids) > 1:
            add_candidate(
                candidates,
                "SENSOR_ASSIGNED_TO_MULTIPLE_ZONES",
                "sensor",
                sensor_id,
                {"zone_ids": sorted(zone_ids)},
                {
                    "distinct_zone_count": len(zone_ids),
                    "note": (
                        "Multiple zone assignments detected. Confirm "
                        "whether assignments overlap in effective time "
                        "or have an approved operational reason."
                    ),
                },
                [table],
            )
            count += 1

    print(f"Multi-zone sensor candidates: {count}")


def detect_alarm_without_lot_links(connection, candidates):
    tables = get_tables(connection)
    if "alarms" not in tables or "alarm_lots" not in tables:
        print("SKIP: Alarm-to-lot check (required tables unavailable)")
        return

    alarm_columns = table_columns(connection, "alarms")
    link_columns = table_columns(connection, "alarm_lots")

    alarm_id_col = first_column(alarm_columns, ["alarm_id", "id"])
    alarm_type_col = first_column(alarm_columns, ["alarm_type", "type"])
    link_alarm_col = first_column(link_columns, ["alarm_id"])

    if not alarm_id_col or not alarm_type_col or not link_alarm_col:
        print("SKIP: Alarm-to-lot check (required columns unavailable)")
        return

    linked_ids = {
        str(row[0])
        for row in connection.execute(
            f'SELECT DISTINCT "{link_alarm_col}" '
            f'FROM alarm_lots WHERE "{link_alarm_col}" IS NOT NULL'
        )
    }

    rows = connection.execute(
        f'SELECT "{alarm_id_col}", "{alarm_type_col}" '
        f'FROM alarms ORDER BY "{alarm_id_col}"'
    ).fetchall()

    count = 0
    expected_exceptions = 0

    for row in rows:
        alarm_id = str(row[0])
        alarm_type = str(row[1]).upper()

        # Door alarms are operational events. They do not necessarily
        # represent an inventory impact and must not be labelled as
        # missing inventory relationships by default.
        if alarm_type == "DOOR_OPEN":
            if alarm_id not in linked_ids:
                expected_exceptions += 1
            continue

        if alarm_id not in linked_ids:
            add_candidate(
                candidates,
                "ALARM_WITHOUT_INVENTORY_LOT_LINK",
                "alarm",
                alarm_id,
                {"lot_ids": []},
                {
                    "note": (
                        "Non-door alarm has no alarm_lots relationship. "
                        "Review whether inventory impact was expected."
                    )
                },
                ["alarms", "alarm_lots"],
            )
            count += 1

    print(f"Unlinked non-door alarm candidates: {count}")
    print(f"Unlinked DOOR_OPEN expected exceptions: {expected_exceptions}")


def detect_reading_gaps(connection, candidates):
    tables = get_tables(connection)
    if "sensor_readings" not in tables:
        print("SKIP: Reading-gap check (sensor_readings table unavailable)")
        return

    columns = table_columns(connection, "sensor_readings")
    sensor_col = first_column(columns, ["sensor_id"])
    timestamp_col = first_column(
        columns,
        ["recorded_at", "reading_timestamp", "timestamp", "reading_time"],
    )

    if not sensor_col or not timestamp_col:
        print("SKIP: Reading-gap check (required columns unavailable)")
        return

    rows = connection.execute(
        f'SELECT "{sensor_col}", "{timestamp_col}" '
        f'FROM sensor_readings '
        f'WHERE "{sensor_col}" IS NOT NULL '
        f'AND "{timestamp_col}" IS NOT NULL '
        f'ORDER BY "{sensor_col}", "{timestamp_col}"'
    ).fetchall()

    readings_by_sensor = defaultdict(list)
    for row in rows:
        parsed = parse_timestamp(row[1])
        if parsed:
            readings_by_sensor[str(row[0])].append(parsed)

    intervals = []
    sensor_intervals = {}

    for sensor_id, timestamps in readings_by_sensor.items():
        timestamps.sort()
        gaps = [
            (timestamps[index] - timestamps[index - 1]).total_seconds()
            for index in range(1, len(timestamps))
        ]
        gaps = [gap for gap in gaps if gap > 0]
        if gaps:
            sensor_intervals[sensor_id] = gaps
            intervals.extend(gaps)

    if not intervals:
        print("SKIP: Reading-gap check (no usable timestamp intervals)")
        return

    typical_interval = statistics.median(intervals)
    threshold = max(MIN_GAP_SECONDS, typical_interval * 3)

    count = 0
    for sensor_id, timestamps in readings_by_sensor.items():
        timestamps.sort()

        for index in range(1, len(timestamps)):
            gap_seconds = (
                timestamps[index] - timestamps[index - 1]
            ).total_seconds()

            if gap_seconds > threshold:
                add_candidate(
                    candidates,
                    "SENSOR_READING_GAP",
                    "sensor",
                    sensor_id,
                    {},
                    {
                        "gap_start": timestamps[index - 1].isoformat(),
                        "gap_end": timestamps[index].isoformat(),
                        "gap_seconds": round(gap_seconds, 2),
                        "threshold_seconds": round(threshold, 2),
                        "database_median_interval_seconds": round(
                            typical_interval, 2
                        ),
                    },
                    ["sensor_readings"],
                )
                count += 1

    print(f"Sensor reading-gap candidates: {count}")
    print(f"Calculated reading-gap threshold: {threshold:.2f} seconds")


def get_tables(connection):
    return {
        row[0]
        for row in connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
        """)
    }


def write_catalog():
    content = """# Phase 10 — Anomaly Catalog

These labels are generated from evidence in the source database.
They are stored separately from operational input data.

All automatically generated records initially use
`REVIEW_REQUIRED`. Review them against business rules before treating
them as confirmed ground truth.

| Issue type | Detection rule | Review required |
|---|---|---|
| `SENSOR_ASSIGNED_TO_MULTIPLE_ZONES` | A sensor has more than one distinct zone in sensor-zone assignments. | Confirm effective dates and approved multi-zone use. |
| `SENSOR_READING_GAP` | Consecutive readings for a sensor are separated by more than the calculated threshold. | Confirm expected sampling cadence and outage context. |
| `ALARM_WITHOUT_INVENTORY_LOT_LINK` | An alarm has no matching row in the alarm-lot bridge table. | Confirm whether the alarm should affect inventory. |

## Reading-gap threshold

The script calculates the median positive interval between readings
across sensors. The detection threshold is the greater of:

- 10 minutes
- Three times the calculated median interval

## Important

This catalog does not modify source tables, create alarms, or assign
remediation outcomes. It only writes a separate review dataset.
"""
    OUTPUT_CATALOG.write_text(content, encoding="utf-8")


def main():
    print("========== PHASE 10.3: GROUND TRUTH GENERATION ==========")

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        detect_multi_zone_sensors(connection, candidates)
        detect_reading_gaps(connection, candidates)
        detect_alarm_without_lot_links(connection, candidates)

        # Stable ordering makes IDs reproducible across identical runs.
        candidates.sort(
            key=lambda item: (
                item["issue_type"],
                item["entity_type"],
                item["entity_id"],
                item["evidence"],
            )
        )

        counters = defaultdict(int)
        output_rows = []

        for candidate in candidates:
            issue_type = candidate["issue_type"]
            counters[issue_type] += 1

            candidate["ground_truth_id"] = (
                f"GT-{issue_type}-{counters[issue_type]:06d}"
            )

            output_rows.append({
                "ground_truth_id": candidate["ground_truth_id"],
                **candidate,
            })

        with OUTPUT_CSV.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(output_rows)

        write_catalog()

        table_counts = {}
        for table in sorted(get_tables(connection)):
            table_counts[table] = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

    finally:
        connection.close()

    csv_hash = hashlib.sha256(OUTPUT_CSV.read_bytes()).hexdigest()

    manifest = {
        "phase": "10.3",
        "database": "data/warehouse_monitor.db",
        "ground_truth_file": "docs/phase10/ground_truth.csv",
        "anomaly_catalog": "docs/phase10/anomaly_catalog.md",
        "label_policy": (
            "Automatically detected candidates require manual review."
        ),
        "ground_truth_rows": len(output_rows),
        "issue_counts": dict(sorted(counters.items())),
        "source_table_counts": table_counts,
        "ground_truth_sha256": csv_hash,
    }

    OUTPUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("\n========== GENERATION SUMMARY ==========")
    print("Ground-truth rows:", len(output_rows))
    for issue_type, count in sorted(counters.items()):
        print(f"{issue_type}: {count}")

    print("\nCreated:")
    print(OUTPUT_CSV.relative_to(ROOT))
    print(OUTPUT_CATALOG.relative_to(ROOT))
    print(OUTPUT_MANIFEST.relative_to(ROOT))
    print("\nSource database was not modified.")


if __name__ == "__main__":
    main()
