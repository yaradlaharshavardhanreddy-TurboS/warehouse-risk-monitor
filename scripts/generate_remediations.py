
from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path("data/warehouse_monitor.db").resolve()
SEED = 20261022
DATASET_END = datetime.fromisoformat("2026-10-29T00:05:10+00:00")
RULE = "seeded-remediation-generation-v3"

ACTIVE_ALARM_STATES = {"OPEN", "ACKNOWLEDGED", "INVESTIGATING"}
TERMINAL_ALARM_STATES = {"RESOLVED", "CLOSED"}

ACTIVE_FINAL_STATUSES = {"PLANNED", "IN_PROGRESS", "CANCELLED"}
TERMINAL_FINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}

ACTIVE_WEIGHTS = {
    "PLANNED": 40,
    "IN_PROGRESS": 35,
    "CANCELLED": 25,
}

TERMINAL_WEIGHTS = {
    "COMPLETED": 55,
    "FAILED": 25,
    "CANCELLED": 20,
}

TYPE_MAP = {
    "HIGH_TEMPERATURE": [
        ("ADJUST_TEMPERATURE",
         "Adjust storage temperature and verify sensor readings."),
        ("REPAIR_SENSOR",
         "Inspect and repair temperature monitoring equipment."),
    ],
    "LOW_TEMPERATURE": [
        ("ADJUST_TEMPERATURE",
         "Adjust storage temperature and verify safe operating range."),
        ("REPAIR_SENSOR",
         "Inspect and repair temperature monitoring equipment."),
    ],
    "HIGH_HUMIDITY": [
        ("ADJUST_HUMIDITY",
         "Adjust humidity controls and verify environmental conditions."),
    ],
    "LOW_HUMIDITY": [
        ("ADJUST_HUMIDITY",
         "Adjust humidity controls and verify environmental conditions."),
    ],
    "DOOR_OPEN": [
        ("REPAIR_DOOR",
         "Inspect and repair the affected access door; verify closure."),
    ],
    "SENSOR_OUTAGE": [
        ("REPAIR_SENSOR",
         "Inspect and repair the affected sensor."),
    ],
    "SENSOR_DRIFT": [
        ("RECALIBRATE_SENSOR",
         "Recalibrate and validate the affected sensor."),
    ],
    "STORAGE_INCOMPATIBILITY": [
        ("RELOCATE_INVENTORY",
         "Move incompatible stock to suitable storage."),
        ("QUARANTINE_INVENTORY",
         "Quarantine incompatible stock pending review."),
    ],
    "HIGH_OCCUPANCY": [
        ("OTHER",
         "Review occupancy and restore safe zone capacity."),
    ],
}


def parse_time(value):
    if not value:
        return None

    value = str(value).strip().replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def stable_id(prefix, value):
    digest = hashlib.sha1(
        str(value).encode("utf-8")
    ).hexdigest()[:24]
    return f"{prefix}-{digest}"


def stable_number(value):
    return int(
        hashlib.sha1(
            f"{SEED}:{value}".encode("utf-8")
        ).hexdigest()[:8],
        16,
    )


def columns(conn, table):
    return {
        row["name"]
        for row in conn.execute(
            f'PRAGMA table_info("{table}")'
        )
    }


def choose_weighted(weights, key):
    number = stable_number(key) % sum(weights.values())

    for status, weight in weights.items():
        if number < weight:
            return status
        number -= weight

    raise RuntimeError("Could not select a remediation status")


def make_times(detected, alarm_id, steps):
    """Create deterministic, increasing times inside the alarm window."""
    span = (DATASET_END - detected).total_seconds()

    if span <= steps + 1:
        raise RuntimeError(
            f"Insufficient time window for remediation of {alarm_id}"
        )

    fractions = {
        1: [0.50],
        2: [0.30, 0.75],
        3: [0.15, 0.48, 0.82],
    }

    if steps not in fractions:
        raise RuntimeError(f"Unsupported number of history steps: {steps}")

    result = [
        detected + timedelta(seconds=span * fraction)
        for fraction in fractions[steps]
    ]

    if any(t <= detected or t >= DATASET_END for t in result):
        raise RuntimeError(
            f"Invalid remediation timestamp for alarm {alarm_id}"
        )

    if any(a >= b for a, b in zip(result, result[1:])):
        raise RuntimeError(
            f"Non-increasing timestamps for alarm {alarm_id}"
        )

    return result


def migrate_remediation_type_constraint(conn):
    """Add REPAIR_DOOR while preserving existing remediation records."""
    row = conn.execute("""
        SELECT sql
          FROM sqlite_master
         WHERE type='table' AND name='remediations'
    """).fetchone()

    if not row or not row["sql"]:
        raise RuntimeError("Could not read remediations table definition")

    create_sql = row["sql"]

    if "'REPAIR_DOOR'" in create_sql:
        print("REPAIR_DOOR constraint already supported.")
        return

    if "'CLOSE_DOOR'" not in create_sql:
        raise RuntimeError(
            "Could not locate the expected remediation_type CHECK "
            "constraint. No automatic table rebuild was attempted."
        )

    updated_sql = create_sql.replace(
        "'CLOSE_DOOR',",
        "'CLOSE_DOOR', 'REPAIR_DOOR',",
        1,
    )

    if updated_sql == create_sql:
        raise RuntimeError("Could not update remediation type constraint")

    dependent_objects = conn.execute("""
        SELECT type, name, sql
          FROM sqlite_master
         WHERE tbl_name='remediations'
           AND type IN ('index', 'trigger')
           AND sql IS NOT NULL
         ORDER BY type, name
    """).fetchall()

    old_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(remediations)"
        )
    ]

    if not old_columns:
        raise RuntimeError("Could not inspect remediations columns")

    new_sql = re.sub(
        r"(?i)^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:[\"`\[]?remediations[\"`\]]?)",
        "CREATE TABLE remediations__new",
        updated_sql,
        count=1,
    )

    if "CREATE TABLE remediations__new" not in new_sql:
        raise RuntimeError("Could not construct replacement table definition")

    conn.execute(new_sql)

    column_list = ", ".join(
        f'"{name}"' for name in old_columns
    )

    conn.execute(
        f"""
        INSERT INTO remediations__new ({column_list})
        SELECT {column_list}
          FROM remediations
        """
    )

    old_count = conn.execute(
        "SELECT COUNT(*) FROM remediations"
    ).fetchone()[0]

    new_count = conn.execute(
        "SELECT COUNT(*) FROM remediations__new"
    ).fetchone()[0]

    if old_count != new_count:
        raise RuntimeError(
            f"Remediation preservation failed: {old_count} != {new_count}"
        )

    conn.execute("DROP TABLE remediations")
    conn.execute(
        "ALTER TABLE remediations__new RENAME TO remediations"
    )

    for obj in dependent_objects:
        conn.execute(obj["sql"])

    print(f"Preserved existing remediation rows: {old_count}")
    print("Added REPAIR_DOOR to remediation_type constraint.")


def ensure_column(conn, table, name, definition):
    if name not in columns(conn, table):
        conn.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}'
        )


def create_history_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remediation_lots (
            remediation_id TEXT NOT NULL,
            lot_id TEXT NOT NULL,
            linked_at TEXT NOT NULL,
            PRIMARY KEY (remediation_id, lot_id),
            FOREIGN KEY (remediation_id)
                REFERENCES remediations(remediation_id),
            FOREIGN KEY (lot_id)
                REFERENCES inventory_lots(lot_id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_remediation_lots_lot
        ON remediation_lots(lot_id)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS remediation_history (
            history_id TEXT PRIMARY KEY,
            remediation_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            FOREIGN KEY (remediation_id)
                REFERENCES remediations(remediation_id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_remediation_history_remediation
        ON remediation_history(remediation_id)
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_remediation_history_no_update
        BEFORE UPDATE ON remediation_history
        BEGIN
            SELECT RAISE(ABORT, 'remediation_history is append-only');
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_remediation_history_no_delete
        BEFORE DELETE ON remediation_history
        BEGIN
            SELECT RAISE(ABORT, 'remediation_history is append-only');
        END
    """)


def append_history(
    conn,
    remediation_id,
    from_status,
    to_status,
    changed_at,
    reason,
):
    history_id = stable_id(
        "RMH",
        f"{remediation_id}:{from_status}:{to_status}:{iso(changed_at)}",
    )

    existing = conn.execute(
        "SELECT 1 FROM remediation_history WHERE history_id=?",
        (history_id,),
    ).fetchone()

    if existing:
        return False

    conn.execute("""
        INSERT INTO remediation_history (
            history_id,
            remediation_id,
            from_status,
            to_status,
            changed_at,
            reason,
            rule_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        history_id,
        remediation_id,
        from_status,
        to_status,
        iso(changed_at),
        reason,
        RULE,
    ))

    return True


def create_inspection_for_door_alarm(conn, alarm):
    """
    Create a deterministic SAFETY inspection for a DOOR_OPEN alarm
    that has no inspection.

    The remediations.inspection_id foreign-key requirement is preserved.
    Unknown mandatory inspection columns cause a clear failure.
    """
    alarm_id = alarm["alarm_id"]
    inspection_id = stable_id("INSP", f"DOOR_OPEN:{alarm_id}")

    existing = conn.execute("""
        SELECT inspection_id
          FROM inspections
         WHERE inspection_id=?
    """, (inspection_id,)).fetchone()

    if existing:
        return inspection_id

    info = conn.execute(
        "PRAGMA table_info(inspections)"
    ).fetchall()

    available = {row["name"] for row in info}

    required_values = {
        "inspection_id": inspection_id,
        "alarm_id": alarm_id,
        "inspector_name": "WAREHOUSE_OPERATIONS",
        "inspection_type": "SAFETY",
        "scheduled_at": alarm["detected_at"],
    }

    missing_columns = set(required_values) - available

    if missing_columns:
        raise RuntimeError(
            "Cannot create a DOOR_OPEN safety inspection. "
            f"Required inspection columns are missing: "
            f"{sorted(missing_columns)}"
        )

    unsupported_required = [
        row["name"]
        for row in info
        if row["notnull"]
        and row["dflt_value"] is None
        and row["pk"] == 0
        and row["name"] not in required_values
    ]

    if unsupported_required:
        raise RuntimeError(
            "Cannot safely create a DOOR_OPEN safety inspection. "
            "The inspections table has additional mandatory columns "
            f"that this script does not populate: {unsupported_required}"
        )

    names = list(required_values)
    placeholders = ", ".join("?" for _ in names)
    quoted_names = ", ".join(f'"{name}"' for name in names)

    conn.execute(
        f"""
        INSERT INTO inspections ({quoted_names})
        VALUES ({placeholders})
        """,
        tuple(required_values[name] for name in names),
    )

    return inspection_id


def ensure_inspections_for_door_alarms(conn, alarms):
    """Ensure every eligible door alarm has an inspection reference."""
    mapping = {}

    for alarm in alarms:
        alarm_id = alarm["alarm_id"]
        alarm_type = str(alarm["alarm_type"] or "").upper()
        lifecycle = str(alarm["lifecycle_state"] or "").upper()

        if alarm_type != "DOOR_OPEN":
            continue

        if lifecycle not in ACTIVE_ALARM_STATES | TERMINAL_ALARM_STATES:
            continue

        row = conn.execute("""
            SELECT MIN(inspection_id) AS inspection_id
              FROM inspections
             WHERE alarm_id=?
        """, (alarm_id,)).fetchone()

        inspection_id = row["inspection_id"]

        if not inspection_id:
            inspection_id = create_inspection_for_door_alarm(
                conn,
                alarm,
            )

        mapping[alarm_id] = inspection_id

    return mapping


def build_lots_by_alarm(conn):
    result = {}

    for row in conn.execute("""
        SELECT alarm_id, lot_id
          FROM alarm_lots
         ORDER BY alarm_id, lot_id
    """):
        result.setdefault(row["alarm_id"], []).append(row["lot_id"])

    return result


def build_inspections_by_alarm(conn):
    result = {}

    for row in conn.execute("""
        SELECT alarm_id, MIN(inspection_id) AS inspection_id
          FROM inspections
         WHERE alarm_id IS NOT NULL
         GROUP BY alarm_id
    """):
        result[row["alarm_id"]] = row["inspection_id"]

    return result


def status_path(status, started_at):
    status = str(status or "").upper()

    if status == "PLANNED":
        return ["PLANNED"]

    if status == "IN_PROGRESS":
        return ["PLANNED", "IN_PROGRESS"]

    if status in ("COMPLETED", "FAILED"):
        return ["PLANNED", "IN_PROGRESS", status]

    if status == "CANCELLED":
        if started_at:
            return ["PLANNED", "IN_PROGRESS", "CANCELLED"]
        return ["PLANNED", "CANCELLED"]

    raise RuntimeError(f"Unsupported remediation status: {status}")


def derive_history_times(rem, path, detected):
    """
    Use actual created/started/completed times where available.
    Derive deterministic times for missing transitions.
    """
    created = parse_time(rem["created_at"])

    if created is None:
        created = detected + (
            DATASET_END - detected
        ) * 0.20

    if not detected < created < DATASET_END:
        raise RuntimeError(
            f"Invalid created_at for remediation {rem['remediation_id']}"
        )

    values = [created]

    if len(path) == 1:
        return values

    started = parse_time(rem["started_at"])

    if "IN_PROGRESS" in path:
        if started is None:
            started = created + (
                DATASET_END - created
            ) * 0.35

        if not created < started < DATASET_END:
            raise RuntimeError(
                f"Invalid started_at for remediation {rem['remediation_id']}"
            )

        values.append(started)

    if path[-1] in ("COMPLETED", "FAILED", "CANCELLED"):
        completed = parse_time(rem["completed_at"])

        if completed is None:
            lower = values[-1]
            completed = lower + (
                DATASET_END - lower
            ) * 0.50

        if not values[-1] < completed < DATASET_END:
            raise RuntimeError(
                f"Invalid completed_at for remediation {rem['remediation_id']}"
            )

        values.append(completed)

    if len(values) != len(path):
        raise RuntimeError(
            f"Could not construct timestamps for {rem['remediation_id']}"
        )

    return values


def ensure_full_history_path(conn, rem, detected):
    """
    Ensure the history table contains the complete ordered status path.

    Existing rows are never updated or deleted. Existing history must be
    a valid prefix of the required path; otherwise the transaction fails.
    """
    remediation_id = rem["remediation_id"]
    final_status = str(rem["remediation_status"]).upper()
    path = status_path(final_status, rem["started_at"])

    times = derive_history_times(rem, path, detected)

    existing = conn.execute("""
        SELECT from_status, to_status, changed_at
          FROM remediation_history
         WHERE remediation_id=?
         ORDER BY changed_at, history_id
    """, (remediation_id,)).fetchall()

    if len(existing) > len(path):
        raise RuntimeError(
            f"Existing history has extra transitions for {remediation_id}; "
            "append-only history cannot be rewritten."
        )

    previous = None

    for index, row in enumerate(existing):
        expected_status = path[index]
        actual_status = str(row["to_status"]).upper()

        actual_from = (
            str(row["from_status"]).upper()
            if row["from_status"] is not None
            else None
        )

        expected_from = previous

        if actual_status != expected_status or actual_from != expected_from:
            raise RuntimeError(
                f"Existing history is not a valid prefix for {remediation_id}. "
                "The transaction will roll back rather than rewrite "
                "append-only history."
            )

        changed_at = parse_time(row["changed_at"])

        if changed_at is None:
            raise RuntimeError(
                f"Invalid history timestamp for {remediation_id}"
            )

        if index and changed_at <= parse_time(existing[index - 1]["changed_at"]):
            raise RuntimeError(
                f"History timestamps are not strictly increasing for "
                f"{remediation_id}"
            )

        previous = expected_status

    if len(existing) == len(path):
        return 0

    if existing:
        last_time = parse_time(existing[-1]["changed_at"])
        remaining_steps = len(path) - len(existing)
        available = (DATASET_END - last_time).total_seconds()

        if available <= remaining_steps:
            raise RuntimeError(
                f"No safe time remains to complete history for {remediation_id}"
            )

        # Retain existing history timestamps and append the missing steps
        # at deterministic, increasing points before DATASET_END.
        missing_times = [
            last_time + timedelta(
                seconds=available * (i + 1) / (remaining_steps + 1)
            )
            for i in range(remaining_steps)
        ]
        start_index = len(existing)
    else:
        missing_times = times
        start_index = 0

    previous = path[start_index - 1] if start_index else None
    added = 0

    for offset, timestamp in enumerate(missing_times):
        status = path[start_index + offset]

        if append_history(
            conn,
            remediation_id,
            previous,
            status,
            timestamp,
            "Complete remediation lifecycle path",
        ):
            added += 1

        previous = status

    return added


def reconcile_remediation_status(conn, rem, lifecycle):
    """Align a remediation's final status and timestamps with its alarm."""
    lifecycle = str(lifecycle or "").upper()
    old_status = str(rem["remediation_status"] or "").upper()

    if lifecycle in ACTIVE_ALARM_STATES:
        allowed = ACTIVE_FINAL_STATUSES

        if old_status in allowed:
            return False

        new_status = (
            "IN_PROGRESS" if rem["started_at"] else "PLANNED"
        )

    elif lifecycle in TERMINAL_ALARM_STATES:
        allowed = TERMINAL_FINAL_STATUSES

        if old_status in allowed:
            return False

        # Preserve evidence that work started. Otherwise cancel before start.
        new_status = (
            "COMPLETED" if rem["started_at"] else "CANCELLED"
        )

    else:
        return False

    started_at = rem["started_at"]
    completed_at = rem["completed_at"]

    if new_status == "PLANNED":
        started_at = None
        completed_at = None

    elif new_status == "IN_PROGRESS":
        if not started_at:
            detected = parse_time(rem["detected_at"])
            created = parse_time(rem["created_at"]) or detected

            if not detected or not created:
                raise RuntimeError(
                    f"Cannot establish start time for {rem['remediation_id']}"
                )

            started_at = iso(
                created + (DATASET_END - created) * 0.50
            )

        completed_at = None

    elif new_status == "COMPLETED":
        detected = parse_time(rem["detected_at"])
        created = parse_time(rem["created_at"]) or detected

        if not detected or not created:
            raise RuntimeError(
                f"Cannot establish completion time for {rem['remediation_id']}"
            )

        if not started_at:
            started_at = iso(
                created + (DATASET_END - created) * 0.35
            )

        start_dt = parse_time(started_at)
        completed_at = iso(
            start_dt + (DATASET_END - start_dt) * 0.50
        )

    elif new_status == "CANCELLED":
        if not started_at:
            completed_at = None

    conn.execute("""
        UPDATE remediations
           SET remediation_status=?,
               started_at=?,
               completed_at=?
         WHERE remediation_id=?
    """, (
        new_status,
        started_at,
        completed_at,
        rem["remediation_id"],
    ))

    return True


def create_remediation(conn, alarm, inspection_id, lots):
    alarm_id = alarm["alarm_id"]
    alarm_type = str(alarm["alarm_type"] or "").upper()
    lifecycle = str(alarm["lifecycle_state"] or "").upper()
    severity = str(alarm["severity"] or "").upper()
    detected = parse_time(alarm["detected_at"])

    if not detected or not detected < DATASET_END:
        raise RuntimeError(
            f"Invalid detection time for alarm {alarm_id}"
        )

    options = TYPE_MAP.get(
        alarm_type,
        [("OTHER", "Inspect the affected warehouse condition.")],
    )

    rem_type, description = options[
        stable_number(f"{alarm_id}:type") % len(options)
    ]

    rem_id = stable_id("REM", f"{SEED}:{alarm_id}")

    existing = conn.execute("""
        SELECT remediation_id
          FROM remediations
         WHERE alarm_id=?
         ORDER BY remediation_id
         LIMIT 1
    """, (alarm_id,)).fetchone()

    if existing:
        rem_id = existing["remediation_id"]

        if alarm_type == "DOOR_OPEN":
            conn.execute("""
                UPDATE remediations
                   SET remediation_type='REPAIR_DOOR'
                 WHERE remediation_id=?
            """, (rem_id,))

        return rem_id, False

    if lifecycle in ACTIVE_ALARM_STATES:
        final_status = choose_weighted(
            ACTIVE_WEIGHTS,
            f"{alarm_id}:active-status",
        )
    else:
        final_status = choose_weighted(
            TERMINAL_WEIGHTS,
            f"{alarm_id}:terminal-status",
        )

    path = status_path(
        final_status,
        started_at=(final_status in ("COMPLETED", "FAILED")),
    )

    transition_times = make_times(
        detected,
        alarm_id,
        len(path),
    )

    created = transition_times[0]
    started_at = None
    completed_at = None

    if final_status == "IN_PROGRESS":
        started_at = iso(transition_times[-1])

    elif final_status in ("COMPLETED", "FAILED"):
        started_at = iso(transition_times[1])
        completed_at = iso(transition_times[-1])

    # CANCELLED is deliberately a pre-start cancellation.
    # It has no started_at and no completed_at.
    conn.execute("""
        INSERT INTO remediations (
            remediation_id,
            inspection_id,
            remediation_type,
            action_description,
            remediation_status,
            assigned_to,
            started_at,
            completed_at,
            alarm_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rem_id,
        inspection_id,
        rem_type,
        description,
        final_status,
        "WAREHOUSE_OPERATIONS",
        started_at,
        completed_at,
        alarm_id,
        iso(created),
    ))

    for lot_id in lots:
        conn.execute("""
            INSERT OR IGNORE INTO remediation_lots (
                remediation_id,
                lot_id,
                linked_at
            )
            VALUES (?, ?, ?)
        """, (
            rem_id,
            lot_id,
            iso(created),
        ))

    for index, status in enumerate(path):
        previous = path[index - 1] if index else None

        append_history(
            conn,
            rem_id,
            previous,
            status,
            transition_times[index],
            "Seeded remediation lifecycle",
        )

    return rem_id, True


def audit_history_paths(conn):
    """Validate every remediation has a complete, ordered history path."""
    errors = []

    remediations = conn.execute("""
        SELECT remediation_id, remediation_status, started_at
          FROM remediations
    """).fetchall()

    for rem in remediations:
        rows = conn.execute("""
            SELECT from_status, to_status, changed_at
              FROM remediation_history
             WHERE remediation_id=?
             ORDER BY changed_at, history_id
        """, (rem["remediation_id"],)).fetchall()

        expected = status_path(
            rem["remediation_status"],
            rem["started_at"],
        )

        actual = [
            str(row["to_status"]).upper()
            for row in rows
        ]

        if actual != expected:
            errors.append(rem["remediation_id"])
            continue

        previous = None
        previous_time = None

        for row in rows:
            from_status = (
                str(row["from_status"]).upper()
                if row["from_status"] is not None
                else None
            )

            changed_at = parse_time(row["changed_at"])

            if from_status != previous:
                errors.append(rem["remediation_id"])
                break

            if changed_at is None:
                errors.append(rem["remediation_id"])
                break

            if previous_time and changed_at <= previous_time:
                errors.append(rem["remediation_id"])
                break

            previous = str(row["to_status"]).upper()
            previous_time = changed_at

    return len(set(errors))


def main():
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")

    # The backup is created before opening the database for modification.
    backup = DB.with_name(
        f"{DB.stem}.before_remediations_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{DB.suffix}"
    )

    shutil.copy2(DB, backup)

    print(f"Database: {DB}")
    print(f"Backup:   {backup}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    inserted = 0
    linked_lots = 0
    history_added = 0
    corrected_existing = 0
    created_door_inspections = 0
    skipped_no_lots = 0
    skipped_no_inspection = 0
    skipped_time = 0

    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")

        required_tables = {
            "alarms",
            "alarm_lots",
            "inventory_lots",
            "inspections",
            "remediations",
        }

        existing_tables = {
            row[0]
            for row in conn.execute("""
                SELECT name
                  FROM sqlite_master
                 WHERE type='table'
            """)
        }

        missing_tables = required_tables - existing_tables

        if missing_tables:
            raise RuntimeError(
                f"Missing required tables: {sorted(missing_tables)}"
            )

        required_columns = {
            "alarms": {
                "alarm_id",
                "alarm_type",
                "severity",
                "detected_at",
                "lifecycle_state",
            },
            "alarm_lots": {"alarm_id", "lot_id"},
            "inspections": {"inspection_id", "alarm_id"},
            "remediations": {
                "remediation_id",
                "inspection_id",
                "remediation_type",
                "action_description",
                "remediation_status",
                "assigned_to",
                "started_at",
                "completed_at",
            },
        }

        for table, required in required_columns.items():
            missing = required - columns(conn, table)

            if missing:
                raise RuntimeError(
                    f"{table} missing required columns: {sorted(missing)}"
                )

        migrate_remediation_type_constraint(conn)

        ensure_column(
            conn,
            "remediations",
            "alarm_id",
            "TEXT REFERENCES alarms(alarm_id)",
        )
        ensure_column(
            conn,
            "remediations",
            "created_at",
            "TEXT",
        )

        create_history_tables(conn)

        # Restore alarm references for older remediations.
        conn.execute("""
            UPDATE remediations
               SET alarm_id = (
                   SELECT i.alarm_id
                     FROM inspections i
                    WHERE i.inspection_id=remediations.inspection_id
               )
             WHERE alarm_id IS NULL
               AND EXISTS (
                   SELECT 1
                     FROM inspections i
                    WHERE i.inspection_id=remediations.inspection_id
               )
        """)

        alarms = conn.execute("""
            SELECT alarm_id,
                   alarm_type,
                   severity,
                   detected_at,
                   lifecycle_state
              FROM alarms
             WHERE UPPER(severity) IN ('HIGH', 'CRITICAL', 'MEDIUM')
                OR UPPER(alarm_type)='DOOR_OPEN'
             ORDER BY alarm_id
        """).fetchall()

        # Door alarms receive an inspection if none exists.
        inspections_before = conn.execute(
            "SELECT COUNT(*) FROM inspections"
        ).fetchone()[0]

        door_inspections = ensure_inspections_for_door_alarms(
            conn,
            alarms,
        )

        inspections_after = conn.execute(
            "SELECT COUNT(*) FROM inspections"
        ).fetchone()[0]

        created_door_inspections = inspections_after - inspections_before

        lots_by_alarm = build_lots_by_alarm(conn)
        inspections_by_alarm = build_inspections_by_alarm(conn)
        inspections_by_alarm.update(door_inspections)

        selected = []

        for alarm in alarms:
            alarm_id = alarm["alarm_id"]
            alarm_type = str(alarm["alarm_type"] or "").upper()
            severity = str(alarm["severity"] or "").upper()
            lifecycle = str(alarm["lifecycle_state"] or "").upper()
            detected = parse_time(alarm["detected_at"])

            if lifecycle not in ACTIVE_ALARM_STATES | TERMINAL_ALARM_STATES:
                continue

            if detected is None or detected >= DATASET_END:
                if alarm_type == "DOOR_OPEN":
                    raise RuntimeError(
                        f"DOOR_OPEN alarm {alarm_id} has an invalid "
                        "detection time; it cannot be safely remediated."
                    )
                skipped_time += 1
                continue

            if alarm_type != "DOOR_OPEN":
                if not lots_by_alarm.get(alarm_id):
                    skipped_no_lots += 1
                    continue

                if alarm_id not in inspections_by_alarm:
                    skipped_no_inspection += 1
                    continue

                threshold = (
                    0.90 if severity in ("HIGH", "CRITICAL") else 0.35
                )

                sample_value = stable_number(alarm_id) / 0xFFFFFFFF

                if sample_value > threshold:
                    continue

            # DOOR_OPEN is always selected, regardless of severity or lots.
            selected.append(alarm)

        # Create or reuse one remediation for each selected alarm.
        for alarm in selected:
            alarm_id = alarm["alarm_id"]
            inspection_id = inspections_by_alarm.get(alarm_id)

            if not inspection_id:
                raise RuntimeError(
                    f"No inspection available for alarm {alarm_id}; "
                    "remediation.inspection_id cannot be NULL."
                )

            before_count = conn.execute(
                "SELECT COUNT(*) FROM remediation_history"
            ).fetchone()[0]

            rem_id, was_inserted = create_remediation(
                conn,
                alarm,
                inspection_id,
                lots_by_alarm.get(alarm_id, []),
            )

            inserted += int(was_inserted)

            after_count = conn.execute(
                "SELECT COUNT(*) FROM remediation_history"
            ).fetchone()[0]

            history_added += after_count - before_count

        # Add missing lot links for all existing remediations.
        existing_remediations = conn.execute("""
            SELECT remediation_id, alarm_id
              FROM remediations
             WHERE alarm_id IS NOT NULL
        """).fetchall()

        for rem in existing_remediations:
            for lot_id in lots_by_alarm.get(rem["alarm_id"], []):
                cur = conn.execute("""
                    INSERT OR IGNORE INTO remediation_lots (
                        remediation_id,
                        lot_id,
                        linked_at
                    )
                    VALUES (?, ?, ?)
                """, (
                    rem["remediation_id"],
                    lot_id,
                    iso(DATASET_END - timedelta(seconds=1)),
                ))

                linked_lots += cur.rowcount

        # Reconcile existing remediation states with their alarm lifecycle.
        existing_rows = conn.execute("""
            SELECT r.remediation_id,
                   r.remediation_status,
                   r.started_at,
                   r.completed_at,
                   r.created_at,
                   r.alarm_id,
                   a.detected_at,
                   a.lifecycle_state
              FROM remediations r
              JOIN alarms a ON a.alarm_id=r.alarm_id
        """).fetchall()

        for rem in existing_rows:
            if reconcile_remediation_status(
                conn,
                rem,
                rem["lifecycle_state"],
            ):
                corrected_existing += 1

        # Ensure created_at exists and all remediation histories are complete.
        all_remediations = conn.execute("""
            SELECT r.remediation_id,
                   r.remediation_status,
                   r.started_at,
                   r.completed_at,
                   r.created_at,
                   r.alarm_id,
                   a.detected_at
              FROM remediations r
              LEFT JOIN alarms a ON a.alarm_id=r.alarm_id
             ORDER BY r.remediation_id
        """).fetchall()

        for rem in all_remediations:
            detected = (
                parse_time(rem["detected_at"])
                if rem["detected_at"]
                else None
            )

            if detected is None:
                created = parse_time(rem["created_at"])

                if created is None:
                    raise RuntimeError(
                        f"Remediation {rem['remediation_id']} has no "
                        "alarm detection time or valid created_at."
                    )

                detected = created - timedelta(seconds=1)

            created = parse_time(rem["created_at"])

            if created is None:
                created = detected + (
                    DATASET_END - detected
                ) * 0.20

                conn.execute("""
                    UPDATE remediations
                       SET created_at=?
                     WHERE remediation_id=?
                """, (
                    iso(created),
                    rem["remediation_id"],
                ))

                rem = dict(rem)
                rem["created_at"] = iso(created)

            before = conn.execute("""
                SELECT COUNT(*)
                  FROM remediation_history
                 WHERE remediation_id=?
            """, (rem["remediation_id"],)).fetchone()[0]

            added = ensure_full_history_path(
                conn,
                rem,
                detected,
            )

            history_added += added

        # ---------- Final audit: all checks run before COMMIT ----------

        lifecycle_mismatches = conn.execute("""
            SELECT COUNT(*)
              FROM remediations r
              JOIN alarms a ON a.alarm_id=r.alarm_id
             WHERE (
                 UPPER(a.lifecycle_state)
                     IN ('OPEN', 'ACKNOWLEDGED', 'INVESTIGATING')
                 AND UPPER(r.remediation_status)
                     NOT IN ('PLANNED', 'IN_PROGRESS', 'CANCELLED')
             )
             OR (
                 UPPER(a.lifecycle_state) IN ('RESOLVED', 'CLOSED')
                 AND UPPER(r.remediation_status)
                     NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
             )
        """).fetchone()[0]

        missing_non_door_lots = conn.execute("""
            SELECT COUNT(*)
              FROM remediations r
              JOIN alarms a ON a.alarm_id=r.alarm_id
             WHERE UPPER(a.alarm_type) != 'DOOR_OPEN'
               AND NOT EXISTS (
                   SELECT 1
                     FROM remediation_lots rl
                    WHERE rl.remediation_id=r.remediation_id
               )
        """).fetchone()[0]

        broken_links = conn.execute("""
            SELECT COUNT(*)
              FROM remediation_lots rl
              LEFT JOIN remediations r
                ON r.remediation_id=rl.remediation_id
              LEFT JOIN inventory_lots l
                ON l.lot_id=rl.lot_id
             WHERE r.remediation_id IS NULL
                OR l.lot_id IS NULL
        """).fetchone()[0]

        door_without_remediation = conn.execute("""
            SELECT COUNT(*)
              FROM alarms a
             WHERE UPPER(a.alarm_type)='DOOR_OPEN'
               AND UPPER(a.lifecycle_state) IN (
                   'OPEN', 'ACKNOWLEDGED', 'INVESTIGATING',
                   'RESOLVED', 'CLOSED'
               )
               AND NOT EXISTS (
                   SELECT 1
                     FROM remediations r
                    WHERE r.alarm_id=a.alarm_id
               )
        """).fetchone()[0]

        wrong_door_type = conn.execute("""
            SELECT COUNT(*)
              FROM remediations r
              JOIN alarms a ON a.alarm_id=r.alarm_id
             WHERE UPPER(a.alarm_type)='DOOR_OPEN'
               AND UPPER(r.remediation_type)!='REPAIR_DOOR'
        """).fetchone()[0]

        invalid_times = conn.execute("""
            SELECT COUNT(*)
              FROM remediations r
              JOIN alarms a ON a.alarm_id=r.alarm_id
             WHERE r.created_at IS NULL
                OR r.created_at <= a.detected_at
                OR r.created_at >= ?
                OR (
                    r.started_at IS NOT NULL
                    AND (
                        r.started_at <= a.detected_at
                        OR r.started_at >= ?
                    )
                )
                OR (
                    r.completed_at IS NOT NULL
                    AND (
                        r.completed_at <= a.detected_at
                        OR r.completed_at >= ?
                    )
                )
        """, (
            iso(DATASET_END),
            iso(DATASET_END),
            iso(DATASET_END),
        )).fetchone()[0]

        cancelled_prestart_with_start = conn.execute("""
            SELECT COUNT(*)
              FROM remediations
             WHERE UPPER(remediation_status)='CANCELLED'
               AND started_at IS NULL
               AND completed_at IS NOT NULL
        """).fetchone()[0]

        history_path_errors = audit_history_paths(conn)

        latest_status_mismatches = conn.execute("""
            SELECT COUNT(*)
              FROM remediations r
             WHERE EXISTS (
                 SELECT 1
                   FROM remediation_history h
                  WHERE h.remediation_id=r.remediation_id
             )
               AND UPPER(r.remediation_status) != UPPER((
                   SELECT h.to_status
                     FROM remediation_history h
                    WHERE h.remediation_id=r.remediation_id
                    ORDER BY h.changed_at DESC, h.history_id DESC
                    LIMIT 1
               ))
        """).fetchone()[0]

        history_triggers = {
            row["name"]
            for row in conn.execute("""
                SELECT name
                  FROM sqlite_master
                 WHERE type='trigger'
            """)
        }

        append_only = (
            "trg_remediation_history_no_update" in history_triggers
            and "trg_remediation_history_no_delete" in history_triggers
        )

        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) FROM remediations"
        ).fetchone()[0]

        with_alarm = conn.execute("""
            SELECT COUNT(*)
              FROM remediations
             WHERE alarm_id IS NOT NULL
        """).fetchone()[0]

        bridge_count = conn.execute(
            "SELECT COUNT(*) FROM remediation_lots"
        ).fetchone()[0]

        history_count = conn.execute(
            "SELECT COUNT(*) FROM remediation_history"
        ).fetchone()[0]

        door_without_lots = conn.execute("""
            SELECT COUNT(*)
              FROM remediations r
              JOIN alarms a ON a.alarm_id=r.alarm_id
             WHERE UPPER(a.alarm_type)='DOOR_OPEN'
               AND NOT EXISTS (
                   SELECT 1
                     FROM remediation_lots rl
                    WHERE rl.remediation_id=r.remediation_id
               )
        """).fetchone()[0]

        print("\n========== REMEDIATION GENERATION ==========")
        print(f"New remediations created:          {inserted}")
        print(f"Existing statuses reconciled:      {corrected_existing}")
        print(f"New door safety inspections:       {created_door_inspections}")
        print(f"New remediation-lot links:         {linked_lots}")
        print(f"History rows added:                 {history_added}")
        print(f"Skipped: no affected lots:         {skipped_no_lots}")
        print(f"Skipped: no matching inspection:   {skipped_no_inspection}")
        print(f"Skipped: invalid time window:      {skipped_time}")

        print("\n========== FINAL AUDIT ==========")
        print(f"Total remediations:                 {total}")
        print(f"Remediations linked to alarms:      {with_alarm}")
        print(f"Remediation-lot bridge rows:        {bridge_count}")
        print(f"Remediation history rows:           {history_count}")
        print(f"Alarm/remediation state mismatches: {lifecycle_mismatches}")
        print(f"Non-door remediations missing lots: {missing_non_door_lots}")
        print(f"Door remediations without lots:     {door_without_lots}")
        print(f"Door alarms without remediation:    {door_without_remediation}")
        print(f"Door remediations with wrong type:  {wrong_door_type}")
        print(f"Broken remediation-lot links:       {broken_links}")
        print(f"Invalid remediation timestamps:    {invalid_times}")
        print(f"Pre-start cancellation violations:  {cancelled_prestart_with_start}")
        print(f"History path errors:                {history_path_errors}")
        print(f"Latest history/status mismatches:   {latest_status_mismatches}")
        print(f"Append-only history triggers:       {append_only}")
        print(f"SQLite integrity:                   {integrity}")
        print(f"Foreign-key violations:             {len(fk_errors)}")

        failures = {
            "lifecycle mismatches": lifecycle_mismatches,
            "non-door remediations missing lots": missing_non_door_lots,
            "door alarms without remediation": door_without_remediation,
            "door remediation type errors": wrong_door_type,
            "broken remediation-lot links": broken_links,
            "invalid remediation timestamps": invalid_times,
            "pre-start cancellation violations": cancelled_prestart_with_start,
            "history path errors": history_path_errors,
            "latest history/status mismatches": latest_status_mismatches,
            "append-only history triggers": 0 if append_only else 1,
            "SQLite integrity": 0 if integrity == "ok" else 1,
            "foreign-key violations": len(fk_errors),
        }

        failed = {
            name: count
            for name, count in failures.items()
            if count != 0
        }

        if failed:
            raise RuntimeError(
                f"Final remediation audit failed: {failed}"
            )

        # Commit only after every audit has passed.
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

        print("\nSUCCESS: remediation generation and all audits passed.")
        print(f"Backup preserved at: {backup}")

    except Exception:
        conn.rollback()
        print(
            "\nERROR: transaction rolled back. "
            "The pre-run database backup is preserved."
        )
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
