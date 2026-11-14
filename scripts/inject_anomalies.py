
#!/usr/bin/env python3
"""
Deterministic warehouse anomaly injector.

Clean source:
    data/warehouse_monitor.db

Anomaly output:
    data/warehouse_monitor_anomalies.db

Ground truth:
    docs/phase10/ground_truth.csv

Seed:
    20261022

Injects 15 cases per category:
    1. Lot moved to a wrong-type zone.
    2. Sensor assigned to a second overlapping zone.
    3. Sensor readings deleted, creating a gap of at least 30 minutes
       without a corresponding sensor_outages record.
    4. ALL alarm_lots links deleted for 15 selected alarms.

The clean source database is never modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


SEED = 20261022
CASES_PER_CATEGORY = 15
READING_GAP_MINUTES = 35

ROOT = Path(__file__).resolve().parents[1]

SOURCE_DB = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_DB = ROOT / "data" / "warehouse_monitor_anomalies.db"
GROUND_TRUTH = ROOT / "docs" / "phase10" / "ground_truth.csv"

CSV_FIELDS = [
    "ground_truth_id",
    "seed",
    "anomaly_type",
    "issue_type",
    "entity_type",
    "entity_id",
    "label_status",
    "case_number",
    "action",
    "table_name",
    "primary_key",
    "row_json_before",
    "row_json_after",
    "details",
]


def fail(message: str) -> None:
    raise RuntimeError(message)


def row_dict(row):
    if row is None:
        return None

    result = {}
    for key in row.keys():
        value = row[key]
        if isinstance(value, bytes):
            value = value.hex()
        result[key] = value

    return result


def json_dump(value):
    if value is None:
        return ""

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def parse_timestamp(value):
    if not value:
        return None

    try:
        result = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if result.tzinfo is not None:
            result = result.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        return result

    except (ValueError, TypeError):
        return None


def compatible_zone_type(min_temp, max_temp):
    """
    Infer an expected zone type from a lot's storage requirements.
    """

    if max_temp <= -18:
        return "FREEZER"

    if max_temp <= 8:
        return "COLD"

    if min_temp >= 15:
        return "HOT"

    return "AMBIENT"


def add_ground_truth(
    records,
    anomaly_type,
    case_number,
    action,
    table_name,
    primary_key,
    before,
    after,
    details,
    entity_type,
    entity_id,
):
    """
    Record one ground-truth row for every modified, inserted,
    or deleted database row.
    """

    ground_truth_id = f"GT-{len(records) + 1:06d}"

    records.append({
        "ground_truth_id": ground_truth_id,
        "seed": SEED,
        "anomaly_type": anomaly_type,
        "issue_type": anomaly_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "label_status": "CONFIRMED_INJECTED",
        "case_number": case_number,
        "action": action,
        "table_name": table_name,
        "primary_key": json_dump(primary_key),
        "row_json_before": json_dump(before),
        "row_json_after": json_dump(after),
        "details": details,
    })


def check_tables(conn):
    required = {
        "warehouses",
        "zones",
        "sensors",
        "sensor_zone_assignments",
        "sensor_readings",
        "sensor_outages",
        "storage_requirements",
        "inventory_lots",
        "lot_zone_assignments",
        "alarms",
        "alarm_lots",
    }

    existing = {
        row["name"]
        for row in conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """)
    }

    missing = sorted(required - existing)

    if missing:
        fail(
            "Missing required database tables: "
            + ", ".join(missing)
        )


def inject_wrong_zone_lots(conn, rng, records):
    anomaly_type = "LOT_WRONG_TYPE_ZONE"

    rows = conn.execute("""
        SELECT
            la.assignment_id,
            la.lot_id,
            la.zone_id AS original_zone_id,
            la.assigned_at,
            la.released_at,
            il.product_type,
            sr.min_temperature_c,
            sr.max_temperature_c,
            z.warehouse_id,
            z.zone_type AS original_zone_type
        FROM lot_zone_assignments la
        JOIN inventory_lots il
            ON il.lot_id = la.lot_id
        JOIN storage_requirements sr
            ON sr.requirement_id = il.requirement_id
        JOIN zones z
            ON z.zone_id = la.zone_id
        WHERE la.released_at IS NULL
        ORDER BY la.lot_id, la.assignment_id DESC
    """).fetchall()

    candidates = []
    seen_lots = set()

    for row in rows:
        lot_id = row["lot_id"]

        if lot_id in seen_lots:
            continue

        seen_lots.add(lot_id)

        expected_type = compatible_zone_type(
            row["min_temperature_c"],
            row["max_temperature_c"],
        )

        # Only use a currently compatible original assignment.
        if row["original_zone_type"] != expected_type:
            continue

        wrong_zones = conn.execute("""
            SELECT zone_id, zone_type
            FROM zones
            WHERE warehouse_id = ?
              AND lifecycle_state = 'ACTIVE'
              AND zone_type != ?
              AND zone_id != ?
            ORDER BY zone_id
        """, (
            row["warehouse_id"],
            expected_type,
            row["original_zone_id"],
        )).fetchall()

        if wrong_zones:
            candidates.append((row, wrong_zones, expected_type))

    if len(candidates) < CASES_PER_CATEGORY:
        fail(
            f"{anomaly_type}: only {len(candidates)} eligible lots "
            f"found; {CASES_PER_CATEGORY} required."
        )

    selected = rng.sample(candidates, CASES_PER_CATEGORY)

    for number, (candidate, wrong_zones, expected_type) in enumerate(
        selected,
        1,
    ):
        target = rng.choice(wrong_zones)

        before_row = conn.execute("""
            SELECT *
            FROM lot_zone_assignments
            WHERE assignment_id = ?
        """, (candidate["assignment_id"],)).fetchone()

        before = row_dict(before_row)

        # IMPORTANT:
        # Only zone_id is changed.
        # The original assignment_reason is preserved.
        conn.execute("""
            UPDATE lot_zone_assignments
            SET zone_id = ?
            WHERE assignment_id = ?
        """, (
            target["zone_id"],
            candidate["assignment_id"],
        ))

        after_row = conn.execute("""
            SELECT *
            FROM lot_zone_assignments
            WHERE assignment_id = ?
        """, (candidate["assignment_id"],)).fetchone()

        after = row_dict(after_row)

        add_ground_truth(
            records=records,
            anomaly_type=anomaly_type,
            case_number=number,
            action="UPDATE",
            table_name="lot_zone_assignments",
            primary_key={
                "assignment_id": candidate["assignment_id"]
            },
            before=before,
            after=after,
            details=(
                f"Lot {candidate['lot_id']}: expected zone type "
                f"{expected_type}; original zone "
                f"{candidate['original_zone_id']}; injected zone "
                f"{target['zone_id']} ({target['zone_type']}). "
                f"Original assignment_reason preserved."
            ),
            entity_type="INVENTORY_LOT",
            entity_id=candidate["lot_id"],
        )

    print(
        f"PASS {anomaly_type}: "
        f"{len(selected)} lots moved to wrong-type zones"
    )


def inject_overlapping_sensor_zones(conn, rng, records):
    anomaly_type = "SENSOR_OVERLAPPING_ZONE"

    rows = conn.execute("""
        SELECT
            a.assignment_id,
            a.sensor_id,
            a.zone_id,
            a.effective_from,
            a.effective_to,
            a.created_at,
            z.warehouse_id
        FROM sensor_zone_assignments a
        JOIN zones z
            ON z.zone_id = a.zone_id
        WHERE a.effective_to IS NULL
        ORDER BY a.sensor_id, a.assignment_id DESC
    """).fetchall()

    candidates = []
    seen_sensors = set()

    for row in rows:
        sensor_id = row["sensor_id"]

        if sensor_id in seen_sensors:
            continue

        seen_sensors.add(sensor_id)

        alternatives = conn.execute("""
            SELECT zone_id, zone_type
            FROM zones
            WHERE warehouse_id = ?
              AND lifecycle_state = 'ACTIVE'
              AND zone_id != ?
            ORDER BY zone_id
        """, (
            row["warehouse_id"],
            row["zone_id"],
        )).fetchall()

        if alternatives:
            candidates.append((row, alternatives))

    if len(candidates) < CASES_PER_CATEGORY:
        fail(
            f"{anomaly_type}: only {len(candidates)} eligible sensors "
            f"found; {CASES_PER_CATEGORY} required."
        )

    selected = rng.sample(candidates, CASES_PER_CATEGORY)

    for number, (original, alternatives) in enumerate(selected, 1):
        target = rng.choice(alternatives)

        # Start the second assignment at the original assignment's
        # start time, guaranteeing a temporal overlap.
        effective_from = original["effective_from"]
        created_at = original["created_at"] or effective_from

        cursor = conn.execute("""
            INSERT INTO sensor_zone_assignments (
                sensor_id,
                zone_id,
                effective_from,
                effective_to,
                assignment_reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            original["sensor_id"],
            target["zone_id"],
            effective_from,
            original["effective_to"],
            None,
            created_at,
        ))

        inserted_id = cursor.lastrowid

        inserted = conn.execute("""
            SELECT *
            FROM sensor_zone_assignments
            WHERE assignment_id = ?
        """, (inserted_id,)).fetchone()

        add_ground_truth(
            records=records,
            anomaly_type=anomaly_type,
            case_number=number,
            action="INSERT",
            table_name="sensor_zone_assignments",
            primary_key={"assignment_id": inserted_id},
            before=None,
            after=row_dict(inserted),
            details=(
                f"Sensor {original['sensor_id']} already assigned "
                f"to zone {original['zone_id']} from "
                f"{effective_from}; a second overlapping assignment "
                f"was inserted for zone {target['zone_id']} "
                f"({target['zone_type']}). "
                f"assignment_reason is NULL."
            ),
            entity_type="SENSOR",
            entity_id=original["sensor_id"],
        )

    print(
        f"PASS {anomaly_type}: "
        f"{len(selected)} sensors given overlapping assignments"
    )


def outages_for_sensor(conn, sensor_id):
    rows = conn.execute("""
        SELECT outage_start, outage_end
        FROM sensor_outages
        WHERE sensor_id = ?
    """, (sensor_id,)).fetchall()

    result = []

    for row in rows:
        start = parse_timestamp(row["outage_start"])
        end = (
            parse_timestamp(row["outage_end"])
            if row["outage_end"]
            else None
        )

        result.append((start, end))

    return result


def interval_has_outage(outages, start, end):
    for outage_start, outage_end in outages:
        if outage_start is None:
            continue

        effective_end = outage_end or datetime.max

        if outage_start < end and effective_end > start:
            return True

    return False


def reading_gap_candidate(conn, sensor_id):
    rows = conn.execute("""
        SELECT *
        FROM sensor_readings
        WHERE sensor_id = ?
        ORDER BY recorded_at, reading_id
    """, (sensor_id,)).fetchall()

    if len(rows) < 3:
        return None

    outages = outages_for_sensor(conn, sensor_id)

    for index in range(1, len(rows) - 1):
        previous = parse_timestamp(
            rows[index - 1]["recorded_at"]
        )

        start = parse_timestamp(
            rows[index]["recorded_at"]
        )

        if previous is None or start is None:
            continue

        required_end = start + timedelta(
            minutes=READING_GAP_MINUTES
        )

        if interval_has_outage(outages, start, required_end):
            continue

        deleted = []
        next_retained = None

        for row in rows[index:]:
            recorded = parse_timestamp(row["recorded_at"])

            if recorded is None:
                continue

            if recorded < required_end:
                deleted.append(row)
            else:
                next_retained = recorded
                break

        if not deleted or next_retained is None:
            continue

        actual_gap = next_retained - previous

        if actual_gap >= timedelta(minutes=30):
            return deleted, previous, next_retained

    return None


def inject_missing_readings(conn, rng, records):
    anomaly_type = "SENSOR_MISSING_READINGS"

    sensor_ids = [
        row["sensor_id"]
        for row in conn.execute("""
            SELECT DISTINCT sensor_id
            FROM sensor_readings
            ORDER BY sensor_id
        """)
    ]

    rng.shuffle(sensor_ids)

    selected = []

    for sensor_id in sensor_ids:
        candidate = reading_gap_candidate(conn, sensor_id)

        if candidate is None:
            continue

        selected.append((sensor_id, candidate))

        if len(selected) == CASES_PER_CATEGORY:
            break

    if len(selected) < CASES_PER_CATEGORY:
        fail(
            f"{anomaly_type}: found only {len(selected)} eligible "
            f"sensors with a reading gap of at least 30 minutes "
            f"and no overlapping outage row; "
            f"{CASES_PER_CATEGORY} required."
        )

    for number, (sensor_id, candidate) in enumerate(selected, 1):
        deleted_rows, previous, next_retained = candidate

        for row in deleted_rows:
            before = row_dict(row)

            conn.execute("""
                DELETE FROM sensor_readings
                WHERE reading_id = ?
            """, (row["reading_id"],))

            add_ground_truth(
                records=records,
                anomaly_type=anomaly_type,
                case_number=number,
                action="DELETE",
                table_name="sensor_readings",
                primary_key={"reading_id": row["reading_id"]},
                before=before,
                after=None,
                details=(
                    f"Sensor {sensor_id}; deleted reading at "
                    f"{row['recorded_at']}; retained readings "
                    f"bracket the resulting gap from "
                    f"{previous.isoformat()} to "
                    f"{next_retained.isoformat()}. "
                    f"No overlapping sensor_outages row exists."
                ),
                entity_type="SENSOR",
                entity_id=sensor_id,
            )

        print(
            f"  Case {number:02d}: sensor {sensor_id}; "
            f"{len(deleted_rows)} readings deleted"
        )

    print(
        f"PASS {anomaly_type}: "
        f"{len(selected)} sensors have missing-reading gaps"
    )


def inject_missing_alarm_links(conn, rng, records):
    anomaly_type = "ALARM_LOT_LINK_DELETED"

    rows = conn.execute("""
        SELECT *
        FROM alarm_lots
        ORDER BY alarm_id, lot_id, impact_start
    """).fetchall()

    by_alarm = defaultdict(list)

    for row in rows:
        by_alarm[row["alarm_id"]].append(row)

    eligible_alarm_ids = sorted(by_alarm)

    if len(eligible_alarm_ids) < CASES_PER_CATEGORY:
        fail(
            f"{anomaly_type}: only {len(eligible_alarm_ids)} alarms "
            f"with alarm_lots rows found; "
            f"{CASES_PER_CATEGORY} required."
        )

    selected_alarm_ids = rng.sample(
        eligible_alarm_ids,
        CASES_PER_CATEGORY,
    )

    total_deleted = 0

    for number, alarm_id in enumerate(selected_alarm_ids, 1):
        # Delete ALL alarm_lots rows for this selected alarm.
        alarm_rows = by_alarm[alarm_id]

        for row in alarm_rows:
            before = row_dict(row)

            conn.execute("""
                DELETE FROM alarm_lots
                WHERE alarm_id = ?
                  AND lot_id = ?
                  AND impact_start = ?
            """, (
                row["alarm_id"],
                row["lot_id"],
                row["impact_start"],
            ))

            add_ground_truth(
                records=records,
                anomaly_type=anomaly_type,
                case_number=number,
                action="DELETE",
                table_name="alarm_lots",
                primary_key={
                    "alarm_id": row["alarm_id"],
                    "lot_id": row["lot_id"],
                    "impact_start": row["impact_start"],
                },
                before=before,
                after=None,
                details=(
                    f"Deleted alarm-lot link for alarm {alarm_id}; "
                    f"lot {row['lot_id']}. ALL alarm_lots links "
                    f"for this selected alarm are intentionally removed."
                ),
                entity_type="ALARM",
                entity_id=alarm_id,
            )

            total_deleted += 1

        # Verify no bridge rows remain for this selected alarm.
        remaining = conn.execute("""
            SELECT COUNT(*)
            FROM alarm_lots
            WHERE alarm_id = ?
        """, (alarm_id,)).fetchone()[0]

        if remaining != 0:
            fail(
                f"Alarm {alarm_id} still has {remaining} alarm_lots "
                f"rows after injection."
            )

        print(
            f"  Case {number:02d}: alarm {alarm_id}; "
            f"{len(alarm_rows)} links deleted"
        )

    print(
        f"PASS {anomaly_type}: "
        f"{len(selected_alarm_ids)} alarms; "
        f"{total_deleted} total links deleted"
    )


def write_csv(records, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_FIELDS,
        )

        writer.writeheader()
        writer.writerows(records)


def validate_output(conn, records):
    expected_cases = {
        "LOT_WRONG_TYPE_ZONE": CASES_PER_CATEGORY,
        "SENSOR_OVERLAPPING_ZONE": CASES_PER_CATEGORY,
        "SENSOR_MISSING_READINGS": CASES_PER_CATEGORY,
        "ALARM_LOT_LINK_DELETED": CASES_PER_CATEGORY,
    }

    actual_cases = defaultdict(set)

    for record in records:
        actual_cases[record["anomaly_type"]].add(
            int(record["case_number"])
        )

    for anomaly_type, expected in expected_cases.items():
        actual = len(actual_cases[anomaly_type])

        if actual != expected:
            fail(
                f"Validation failed for {anomaly_type}: "
                f"expected {expected} cases, got {actual}."
            )

    # All ground-truth records must have the requested label.
    for record in records:
        if record["issue_type"] != record["anomaly_type"]:
            fail("issue_type does not match anomaly_type.")

        if record["label_status"] != "CONFIRMED_INJECTED":
            fail("Unexpected ground-truth label_status.")

        if not record["entity_id"]:
            fail("Ground-truth entity_id is missing.")

    # IDs must be unique.
    ids = [record["ground_truth_id"] for record in records]

    if len(ids) != len(set(ids)):
        fail("Duplicate ground_truth_id values detected.")

    integrity = conn.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    if integrity != "ok":
        fail(f"SQLite integrity_check failed: {integrity}")

    fk_errors = conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if fk_errors:
        fail(
            "Foreign-key validation failed: "
            + repr(fk_errors[:10])
        )

    # Verify the 15 overlapping assignment cases really have
    # two simultaneously active assignments.
    overlap_records = [
        r for r in records
        if r["anomaly_type"] == "SENSOR_OVERLAPPING_ZONE"
    ]

    for record in overlap_records:
        pk = json.loads(record["primary_key"])
        assignment_id = pk["assignment_id"]

        inserted = conn.execute("""
            SELECT sensor_id, effective_from, effective_to,
                   assignment_reason
            FROM sensor_zone_assignments
            WHERE assignment_id = ?
        """, (assignment_id,)).fetchone()

        if inserted is None:
            fail("Inserted overlapping assignment is missing.")

        if inserted["assignment_reason"] is not None:
            fail("Overlapping assignment_reason is not NULL.")

        overlapping = conn.execute("""
            SELECT COUNT(*)
            FROM sensor_zone_assignments a
            JOIN sensor_zone_assignments b
              ON a.sensor_id = b.sensor_id
             AND a.assignment_id != b.assignment_id
            WHERE a.assignment_id = ?
              AND (
                b.effective_to IS NULL
                OR b.effective_to > a.effective_from
              )
              AND (
                a.effective_to IS NULL
                OR b.effective_from < a.effective_to
              )
        """, (assignment_id,)).fetchone()[0]

        if overlapping < 1:
            fail(
                f"Assignment {assignment_id} has no verified "
                f"overlapping assignment."
            )

    # Verify all selected alarm IDs have no remaining bridge rows.
    selected_alarm_ids = {
        record["entity_id"]
        for record in records
        if record["anomaly_type"] == "ALARM_LOT_LINK_DELETED"
    }

    if len(selected_alarm_ids) != CASES_PER_CATEGORY:
        fail("Expected exactly 15 distinct selected alarm IDs.")

    for alarm_id in selected_alarm_ids:
        remaining = conn.execute("""
            SELECT COUNT(*)
            FROM alarm_lots
            WHERE alarm_id = ?
        """, (alarm_id,)).fetchone()[0]

        if remaining:
            fail(
                f"Alarm {alarm_id} still has {remaining} bridge rows."
            )

    # Verify all 15 lot cases retain their original assignment reason.
    lot_records = [
        r for r in records
        if r["anomaly_type"] == "LOT_WRONG_TYPE_ZONE"
    ]

    for record in lot_records:
        before = json.loads(record["row_json_before"])
        after = json.loads(record["row_json_after"])

        if before.get("assignment_reason") != after.get(
            "assignment_reason"
        ):
            fail(
                "Original lot assignment_reason was not preserved."
            )

    print("\n========== VALIDATION ==========")
    print("SQLite integrity: PASS")
    print("Foreign keys: PASS")
    print("Wrong-zone lot reasons preserved: PASS")
    print("Overlapping assignments verified: PASS")
    print("Overlapping assignment reasons NULL: PASS")
    print("All links removed for selected alarms: PASS")
    print("Distinct selected alarms:", len(selected_alarm_ids))
    print("Anomaly categories: 4")
    print("Cases per category: 15")
    print("Total cases: 60")
    print("Ground-truth records:", len(records))


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a separate warehouse database with "
            "four deterministic injected anomaly types."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Replace existing anomaly database and ground-truth CSV."
        ),
    )

    args = parser.parse_args()

    if not SOURCE_DB.exists():
        fail(f"Clean source database not found: {SOURCE_DB}")

    if OUTPUT_DB.exists() and not args.force:
        fail(
            f"Output already exists: {OUTPUT_DB}\n"
            "Use --force to replace it."
        )

    if GROUND_TRUTH.exists() and not args.force:
        fail(
            f"Ground-truth file already exists: {GROUND_TRUTH}\n"
            "Use --force to replace it."
        )

    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    records = []

    db_fd, db_temp_name = tempfile.mkstemp(
        prefix="warehouse_anomalies_",
        suffix=".db",
        dir=str(OUTPUT_DB.parent),
    )
    os.close(db_fd)

    csv_fd, csv_temp_name = tempfile.mkstemp(
        prefix="ground_truth_",
        suffix=".csv",
        dir=str(GROUND_TRUTH.parent),
    )
    os.close(csv_fd)

    db_temp = Path(db_temp_name)
    csv_temp = Path(csv_temp_name)

    try:
        # Create an independent, transactionally consistent SQLite copy.
        source = sqlite3.connect(str(SOURCE_DB))
        destination = sqlite3.connect(str(db_temp))

        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        conn = sqlite3.connect(str(db_temp))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            check_tables(conn)

            print("========== INJECTING ANOMALIES ==========")
            print("Seed:", SEED)
            print("Clean source:", SOURCE_DB)
            print("Temporary working copy:", db_temp)

            # All modifications are committed together.
            with conn:
                inject_wrong_zone_lots(conn, rng, records)
                inject_overlapping_sensor_zones(conn, rng, records)
                inject_missing_readings(conn, rng, records)
                inject_missing_alarm_links(conn, rng, records)

            validate_output(conn, records)

        finally:
            conn.close()

        # Create the CSV temporary file before publishing either artifact.
        write_csv(records, csv_temp)

        # Publish the completed files.
        if args.force:
            OUTPUT_DB.unlink(missing_ok=True)
            GROUND_TRUTH.unlink(missing_ok=True)

        shutil.move(str(db_temp), str(OUTPUT_DB))
        shutil.move(str(csv_temp), str(GROUND_TRUTH))

        print("\n========== COMPLETE ==========")
        print("Clean database preserved:", SOURCE_DB)
        print("Anomaly database:", OUTPUT_DB)
        print("Ground truth CSV:", GROUND_TRUTH)
        print("Seed:", SEED)
        print("Anomaly cases:", CASES_PER_CATEGORY * 4)
        print("Ground-truth records:", len(records))
        print("Status: SUCCESS")

    except Exception:
        db_temp.unlink(missing_ok=True)
        csv_temp.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
