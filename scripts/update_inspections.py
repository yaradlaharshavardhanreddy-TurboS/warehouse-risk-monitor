
from __future__ import annotations

import hashlib
import random
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.database import DATABASE_PATH


SEED = 20261022
RULE_VERSION = "inspection-rules-v2"
NAMESPACE = uuid.UUID("b0e18e8e-60a0-4b12-9ef5-1cb23c3d4e61")

TYPE_MAP = {
    "HIGH_TEMPERATURE": "QUALITY",
    "LOW_TEMPERATURE": "QUALITY",
    "STORAGE_INCOMPATIBILITY": "QUALITY",
    "HIGH_HUMIDITY": "MAINTENANCE",
    "LOW_HUMIDITY": "MAINTENANCE",
    "SENSOR_OUTAGE": "MAINTENANCE",
    "SENSOR_DRIFT": "MAINTENANCE",
    "DOOR_OPEN": "SAFETY",
    "HIGH_OCCUPANCY": "SAFETY",
}

STATUSES = ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
STATUS_WEIGHTS = [15, 20, 50, 15]


def stable_number(value):
    return int(hashlib.sha256(str(value).encode()).hexdigest(), 16)


def parse_time(value):
    if not value:
        raise ValueError("A required timestamp is missing")

    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)

    return result.astimezone(timezone.utc)


def format_time(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def deterministic_id(value):
    return str(uuid.uuid5(NAMESPACE, str(value)))


def dataset_end(conn):
    candidates = []

    sources = [
        ("sensor_readings", "recorded_at"),
        ("door_events", "event_timestamp"),
        ("alarms", "detected_at"),
    ]

    for table, column in sources:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()

        if not exists:
            continue

        columns = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table})")
        }

        if column not in columns:
            continue

        for (value,) in conn.execute(
            f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL"
        ):
            try:
                candidates.append(parse_time(value))
            except (ValueError, TypeError):
                continue

    if not candidates:
        raise RuntimeError("Could not determine the dataset end timestamp")

    return max(candidates)


def timestamp_between(alarm_time, end_time, fraction):
    duration = (end_time - alarm_time).total_seconds()

    if duration < 4:
        raise RuntimeError(
            "Alarm-to-dataset interval is too short to create valid "
            f"inspection timestamps: {alarm_time} to {end_time}"
        )

    seconds = max(1, min(int(duration * fraction), int(duration) - 1))

    return alarm_time + timedelta(seconds=seconds)


def eligible_alarms(alarms):
    selected = []

    for alarm in alarms:
        severity = alarm["severity"]

        if severity in ("HIGH", "CRITICAL"):
            selected.append(alarm)

        elif severity == "MEDIUM":
            rng = random.Random(
                f"{SEED}:inspection-eligibility:{alarm['alarm_id']}"
            )
            if rng.random() < 0.30:
                selected.append(alarm)

    return selected


def assign_statuses(inspection_ids):
    ordered = sorted(
        inspection_ids,
        key=lambda value: stable_number(
            f"{SEED}:inspection-status:{value}"
        ),
    )

    total = len(ordered)
    boundaries = [
        round(total * 0.15),
        round(total * 0.35),
        round(total * 0.85),
        total,
    ]

    assignments = {}
    start = 0

    for status, end in zip(STATUSES, boundaries):
        for inspection_id in ordered[start:end]:
            assignments[inspection_id] = status
        start = end

    return assignments


def create_history_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inspection_history (
            inspection_history_id TEXT PRIMARY KEY,
            inspection_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            FOREIGN KEY (inspection_id)
                REFERENCES inspections(inspection_id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_inspection_history_inspection
        ON inspection_history(inspection_id, changed_at)
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_inspection_history_update
        BEFORE UPDATE ON inspection_history
        BEGIN
            SELECT RAISE(ABORT, 'inspection_history is append-only');
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_inspection_history_delete
        BEFORE DELETE ON inspection_history
        BEGIN
            SELECT RAISE(ABORT, 'inspection_history is append-only');
        END
    """)


def append_history(conn, inspection_id, current_status, target_status,
                   alarm_time, end_time):
    existing = conn.execute("""
        SELECT to_status
        FROM inspection_history
        WHERE inspection_id = ?
        ORDER BY changed_at DESC, inspection_history_id DESC
        LIMIT 1
    """, (inspection_id,)).fetchone()

    if existing:
        if existing[0] != target_status:
            raise RuntimeError(
                f"Existing history for {inspection_id} ends at "
                f"{existing[0]}, but inspection status is {target_status}. "
                "Refusing to rewrite history."
            )
        return

    schedule_time = timestamp_between(alarm_time, end_time, 0.05)

    transitions = [
        (None, "SCHEDULED", schedule_time, "Inspection scheduled"),
    ]

    if target_status == "IN_PROGRESS":
        transitions.append((
            "SCHEDULED",
            "IN_PROGRESS",
            timestamp_between(alarm_time, end_time, 0.35),
            "Inspection started",
        ))

    elif target_status == "COMPLETED":
        transitions.extend([
            (
                "SCHEDULED",
                "IN_PROGRESS",
                timestamp_between(alarm_time, end_time, 0.35),
                "Inspection started",
            ),
            (
                "IN_PROGRESS",
                "COMPLETED",
                timestamp_between(alarm_time, end_time, 0.80),
                "Inspection completed",
            ),
        ])

    elif target_status == "CANCELLED":
        transitions.append((
            "SCHEDULED",
            "CANCELLED",
            timestamp_between(alarm_time, end_time, 0.55),
            "Inspection cancelled",
        ))

    for from_status, to_status, changed_at, reason in transitions:
        history_id = deterministic_id(
            f"history:{inspection_id}:{to_status}"
        )

        conn.execute("""
            INSERT INTO inspection_history (
                inspection_history_id,
                inspection_id,
                from_status,
                to_status,
                changed_at,
                reason,
                rule_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            history_id,
            inspection_id,
            from_status,
            to_status,
            format_time(changed_at),
            reason,
            RULE_VERSION,
        ))


def validate(conn, end_time):
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")

    foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()

    if foreign_key_errors:
        raise RuntimeError(
            f"Foreign-key validation failed: {foreign_key_errors[:10]}"
        )

    missing_history = conn.execute("""
        SELECT COUNT(*)
        FROM inspections i
        LEFT JOIN inspection_history h
            ON h.inspection_id = i.inspection_id
        WHERE h.inspection_id IS NULL
    """).fetchone()[0]

    if missing_history:
        raise RuntimeError(
            f"{missing_history} inspections have no history"
        )

    mismatches = conn.execute("""
        SELECT i.inspection_id, i.inspection_status, h.to_status
        FROM inspections i
        JOIN (
            SELECT inspection_id, MAX(changed_at) AS latest
            FROM inspection_history
            GROUP BY inspection_id
        ) latest
          ON latest.inspection_id = i.inspection_id
        JOIN inspection_history h
          ON h.inspection_id = latest.inspection_id
         AND h.changed_at = latest.latest
        WHERE i.inspection_status != h.to_status
    """).fetchall()

    if mismatches:
        raise RuntimeError(
            f"Inspection/history status mismatch: {mismatches[:5]}"
        )

    bad_times = conn.execute("""
        SELECT i.inspection_id, i.scheduled_at, a.detected_at
        FROM inspections i
        JOIN alarms a ON a.alarm_id = i.alarm_id
        WHERE i.scheduled_at IS NULL
    """).fetchall()

    if bad_times:
        raise RuntimeError(f"Missing scheduled timestamps: {bad_times[:5]}")

    rows = conn.execute("""
        SELECT i.inspection_id, i.scheduled_at, i.completed_at,
               a.detected_at
        FROM inspections i
        JOIN alarms a ON a.alarm_id = i.alarm_id
    """).fetchall()

    for inspection_id, scheduled, completed, detected in rows:
        scheduled_dt = parse_time(scheduled)
        alarm_dt = parse_time(detected)

        if not alarm_dt < scheduled_dt < end_time:
            raise RuntimeError(
                f"Invalid schedule chronology for {inspection_id}"
            )

        if completed:
            completed_dt = parse_time(completed)
            if not scheduled_dt < completed_dt < end_time:
                raise RuntimeError(
                    f"Invalid completion chronology for {inspection_id}"
                )

    for table in ("alarms", "inspections", "remediations"):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        print(f"{table}: {count}")

    print(
        "Remediation records preserved:",
        conn.execute("SELECT COUNT(*) FROM remediations").fetchone()[0],
    )

    print(
        "Inspection history entries:",
        conn.execute("SELECT COUNT(*) FROM inspection_history").fetchone()[0],
    )

    print("SQLite integrity: OK")
    print("Foreign keys: OK")


def main():
    db_path = Path(DATABASE_PATH).resolve()

    if db_path.name != "warehouse_monitor.db":
        raise RuntimeError(
            f"Unexpected database target: {db_path}"
        )

    if not db_path.exists():
        raise RuntimeError(f"Database does not exist: {db_path}")

    backup_path = db_path.with_name(
        db_path.name + ".inspection_backup_" +
        datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )

    shutil.copy2(db_path, backup_path)

    print("Target database:", db_path)
    print("Verified backup:", backup_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN IMMEDIATE")

        required = {"alarms", "inspections", "remediations"}
        existing = {
            row[0] for row in conn.execute("""
                SELECT name FROM sqlite_master WHERE type='table'
            """)
        }

        if not required.issubset(existing):
            raise RuntimeError(
                f"Missing required tables: {required - existing}"
            )

        end_time = dataset_end(conn)

        alarms = conn.execute("""
            SELECT alarm_id, alarm_type, severity, detected_at
            FROM alarms
            ORDER BY alarm_id
        """).fetchall()

        alarm_rows = [
            dict(zip(
                ["alarm_id", "alarm_type", "severity", "detected_at"],
                row
            ))
            for row in alarms
        ]

        eligible = eligible_alarms(alarm_rows)
        eligible_by_id = {
            alarm["alarm_id"]: alarm for alarm in eligible
        }

        existing_inspections = conn.execute("""
            SELECT inspection_id, alarm_id, inspection_type,
                   inspection_status
            FROM inspections
        """).fetchall()

        by_alarm = {
            row[1]: row[0] for row in existing_inspections
        }

        # Create missing inspections for eligible alarms.
        for alarm in eligible:
            if alarm["alarm_id"] in by_alarm:
                continue

            inspection_id = deterministic_id(
                f"inspection:{alarm['alarm_id']}"
            )

            conn.execute("""
                INSERT INTO inspections (
                    inspection_id,
                    alarm_id,
                    inspector_name,
                    inspection_type,
                    inspection_status,
                    findings,
                    scheduled_at,
                    completed_at
                )
                VALUES (?, ?, 'UNASSIGNED', ?, 'SCHEDULED',
                        'Inspection created by seeded inspection rules.',
                        ?, NULL)
            """, (
                inspection_id,
                alarm["alarm_id"],
                TYPE_MAP.get(alarm["alarm_type"], "QUALITY"),
                format_time(timestamp_between(
                    parse_time(alarm["detected_at"]), end_time, 0.05
                )),
            ))

            by_alarm[alarm["alarm_id"]] = inspection_id

        # Re-read after creating missing inspections.
        inspections = conn.execute("""
            SELECT inspection_id, alarm_id, inspection_type,
                   inspection_status
            FROM inspections
        """).fetchall()

        remediation_links = {
            row[0] for row in conn.execute("""
                SELECT DISTINCT inspection_id
                FROM remediations
                WHERE inspection_id IS NOT NULL
            """)
        }

        history_links = set()

        history_exists = conn.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='inspection_history'
        """).fetchone()

        if history_exists:
            history_links = {
                row[0] for row in conn.execute("""
                    SELECT DISTINCT inspection_id
                    FROM inspection_history
                """)
            }

        # Remove ineligible inspections only when no records depend on them.
        for inspection_id, alarm_id, _, _ in inspections:
            if alarm_id in eligible_by_id:
                continue

            if inspection_id in remediation_links:
                print(
                    "Preserving remediation-dependent LOW/ineligible "
                    f"inspection: {inspection_id}"
                )
                continue

            if inspection_id in history_links:
                print(
                    "Preserving inspection with existing history:",
                    inspection_id,
                )
                continue

            conn.execute(
                "DELETE FROM inspections WHERE inspection_id = ?",
                (inspection_id,),
            )

        create_history_table(conn)

        # Assign the seeded status distribution to eligible inspections.
        eligible_inspection_ids = [
            by_alarm[alarm["alarm_id"]] for alarm in eligible
        ]

        assignments = assign_statuses(eligible_inspection_ids)

        # Include remediation-dependent exceptions, preserving their
        # existing valid status rather than treating LOW alarms as eligible.
        remaining = conn.execute("""
            SELECT inspection_id, alarm_id, inspection_status
            FROM inspections
        """).fetchall()

        alarm_lookup = {a["alarm_id"]: a for a in alarm_rows}

        for inspection_id, alarm_id, current_status in remaining:
            alarm = alarm_lookup[alarm_id]

            is_eligible = alarm_id in eligible_by_id

            target_status = (
                assignments[inspection_id]
                if is_eligible
                else current_status
            )

            if target_status not in STATUSES:
                target_status = "COMPLETED" if not is_eligible else "SCHEDULED"

            alarm_time = parse_time(alarm["detected_at"])
            scheduled = timestamp_between(alarm_time, end_time, 0.05)

            completed = None
            if target_status == "COMPLETED":
                completed = timestamp_between(alarm_time, end_time, 0.80)

            inspection_type = TYPE_MAP.get(
                alarm["alarm_type"], "QUALITY"
            )

            conn.execute("""
                UPDATE inspections
                SET inspection_type = ?,
                    inspection_status = ?,
                    scheduled_at = ?,
                    completed_at = ?
                WHERE inspection_id = ?
            """, (
                inspection_type,
                target_status,
                format_time(scheduled),
                format_time(completed) if completed else None,
                inspection_id,
            ))

            append_history(
                conn,
                inspection_id,
                current_status,
                target_status,
                alarm_time,
                end_time,
            )

        validate(conn, end_time)

        conn.commit()

        print("\nINSPECTION UPDATE SUCCESSFUL")
        print("Eligible alarms:", len(eligible))
        print("Seed:", SEED)
        print("Dataset end:", format_time(end_time))
        print("Backup:", backup_path)

        print("\nFinal inspection status distribution:")
        for status, count in conn.execute("""
            SELECT inspection_status, COUNT(*)
            FROM inspections
            GROUP BY inspection_status
            ORDER BY inspection_status
        """):
            print(f"{status}: {count}")

        print("\nInspection type distribution:")
        for inspection_type, count in conn.execute("""
            SELECT inspection_type, COUNT(*)
            FROM inspections
            GROUP BY inspection_type
            ORDER BY inspection_type
        """):
            print(f"{inspection_type}: {count}")

    except Exception:
        conn.rollback()
        print("\nERROR: Inspection update failed.")
        print("Transaction rolled back.")
        print("Backup preserved:", backup_path)
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
