
#!/usr/bin/env python3
"""Deterministic, seed-based alarm lifecycle simulation."""

import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "warehouse_monitor.db"

SEED = 20261022
RULE_VERSION = "seeded_lifecycle_v2"

TARGET_PERCENTAGES = {
    "OPEN": 0.15,
    "ACKNOWLEDGED": 0.15,
    "RESOLVED": 0.25,
    "CLOSED": 0.45,
}

ACK_FRACTION = {
    "CRITICAL": 0.05,
    "HIGH": 0.12,
    "MEDIUM": 0.25,
    "LOW": 0.40,
}

SEVERITY_BONUS = {
    "CRITICAL": 0.30,
    "HIGH": 0.20,
    "MEDIUM": 0.10,
    "LOW": 0.00,
}

STATE_ORDER = ["OPEN", "ACKNOWLEDGED", "RESOLVED", "CLOSED"]


def parse_time(value):
    if not value:
        raise ValueError("Required timestamp is empty")

    result = datetime.fromisoformat(
        str(value).strip().replace("Z", "+00:00")
    )

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)

    return result.astimezone(timezone.utc)


def fmt_time(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def connect(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def check_integrity(conn, label):
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]

    if result != "ok":
        raise RuntimeError(f"{label} integrity failed: {result}")

    errors = conn.execute("PRAGMA foreign_key_check").fetchall()

    if errors:
        raise RuntimeError(f"{label} foreign-key errors: {errors[:10]}")


def get_alarm_count(conn):
    return conn.execute("SELECT COUNT(*) FROM alarms").fetchone()[0]


def find_pre_lifecycle_backup(current_count):
    candidates = sorted(
        DB.parent.glob(DB.name + ".backup_*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        try:
            conn = connect(path)

            tables = {
                row[0]
                for row in conn.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """)
            }

            if "alarms" not in tables or "alarm_history" in tables:
                conn.close()
                continue

            count = get_alarm_count(conn)

            states = conn.execute("""
                SELECT lifecycle_state, COUNT(*)
                FROM alarms
                GROUP BY lifecycle_state
            """).fetchall()

            check_integrity(conn, str(path))
            conn.close()

            if count == current_count and states == [("OPEN", current_count)]:
                print(f"Original database backup: {path}")
                return path

        except Exception as exc:
            print(f"Skipping {path.name}: {exc}")

    raise RuntimeError(
        "No verified pre-lifecycle backup with all alarms OPEN was found. "
        "No database changes were made."
    )


def create_backup(label):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = DB.with_name(f"{DB.name}.{label}_{stamp}")

    source = connect(DB)
    destination = sqlite3.connect(str(backup_path))

    try:
        source.backup(destination)

        result = destination.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if result != "ok":
            raise RuntimeError("Safety backup integrity check failed")
    finally:
        destination.close()
        source.close()

    print(f"Verified safety backup: {backup_path}")
    return backup_path


def restore_database(source_path):
    source = connect(source_path)
    destination = connect(DB)

    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def dataset_end(conn):
    fields = [
        ("sensor_readings", "recorded_at"),
        ("door_events", "event_timestamp"),
        ("alarms", "detected_at"),
    ]

    values = []

    for table, column in fields:
        result = conn.execute(
            f"SELECT MAX({column}) FROM {table}"
        ).fetchone()[0]

        if result:
            values.append(parse_time(result))

    if not values:
        raise RuntimeError("Cannot determine dataset end timestamp")

    return max(values)


def target_counts(total):
    counts = {
        "OPEN": round(total * 0.15),
        "ACKNOWLEDGED": round(total * 0.15),
        "RESOLVED": round(total * 0.25),
    }

    counts["CLOSED"] = total - sum(counts.values())
    return counts


def assign_final_states(alarms):
    ranked = []

    for alarm in alarms:
        alarm_id, severity, detected_at = alarm
        severity = (severity or "LOW").upper()

        if severity not in SEVERITY_BONUS:
            raise ValueError(
                f"Unknown severity {severity} for alarm {alarm_id}"
            )

        rng = random.Random(f"{SEED}:{alarm_id}")
        score = rng.random() - SEVERITY_BONUS[severity]

        ranked.append((score, str(alarm_id), alarm))

    ranked.sort(key=lambda item: (item[0], item[1]))

    counts = target_counts(len(alarms))
    assignments = {}
    position = 0

    for state in ("CLOSED", "RESOLVED", "ACKNOWLEDGED", "OPEN"):
        group = ranked[position:position + counts[state]]

        for _, _, alarm in group:
            assignments[alarm[0]] = state

        position += counts[state]

    if len(assignments) != len(alarms):
        raise RuntimeError("Some alarms were not assigned a final state")

    return assignments, counts


def create_history_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alarm_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alarm_id TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            severity TEXT NOT NULL,
            age_minutes REAL NOT NULL,
            rule_version TEXT NOT NULL,
            FOREIGN KEY (alarm_id) REFERENCES alarms(alarm_id),
            CHECK (to_state IN (
                'OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'CLOSED'
            )),
            CHECK (from_state IS NULL OR from_state IN (
                'OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'CLOSED'
            ))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_alarm_history_alarm
        ON alarm_history(alarm_id, history_id)
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_alarm_history_update
        BEFORE UPDATE ON alarm_history
        BEGIN
            SELECT RAISE(ABORT, 'alarm_history is append-only');
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_alarm_history_delete
        BEFORE DELETE ON alarm_history
        BEGIN
            SELECT RAISE(ABORT, 'alarm_history is append-only');
        END
    """)


def transition_time(detected, end, fraction):
    return detected + (end - detected) * fraction


def build_transitions(alarms, assignments, end):
    transitions = []

    for alarm_id, severity, detected_at in alarms:
        severity = (severity or "LOW").upper()
        detected = parse_time(detected_at)
        final_state = assignments[alarm_id]

        if detected > end:
            raise RuntimeError(
                f"Alarm {alarm_id} is later than dataset end"
            )

        if final_state == "OPEN":
            continue

        ack_time = transition_time(
            detected, end, ACK_FRACTION[severity]
        )

        transitions.append((
            ack_time, str(alarm_id), "OPEN",
            "ACKNOWLEDGED", severity, detected
        ))

        if final_state == "ACKNOWLEDGED":
            continue

        resolve_time = transition_time(detected, end, 0.65)

        if resolve_time <= ack_time:
            raise RuntimeError("Invalid acknowledgement/resolution order")

        transitions.append((
            resolve_time, str(alarm_id), "ACKNOWLEDGED",
            "RESOLVED", severity, detected
        ))

        if final_state == "CLOSED":
            close_time = transition_time(detected, end, 0.90)

            if close_time <= resolve_time:
                raise RuntimeError("Invalid resolution/closure order")

            transitions.append((
                close_time, str(alarm_id), "RESOLVED",
                "CLOSED", severity, detected
            ))

    transitions.sort(
        key=lambda item: (
            item[0],
            item[1],
            STATE_ORDER.index(item[3]),
        )
    )

    previous = None

    for item in transitions:
        if item[0] > end:
            raise RuntimeError("Transition exceeds dataset end")

        if previous is not None and item[0] < previous:
            raise RuntimeError("Global transition ordering failed")

        previous = item[0]

    return transitions


def apply_lifecycle(conn):
    alarms = conn.execute("""
        SELECT alarm_id, severity, detected_at
        FROM alarms
        ORDER BY alarm_id
    """).fetchall()

    if not alarms:
        raise RuntimeError("No alarms found")

    end = dataset_end(conn)
    assignments, counts = assign_final_states(alarms)
    transitions = build_transitions(alarms, assignments, end)

    create_history_table(conn)

    # Compatibility correction: build the lookup once, outside the loop.
    final_state_by_text = {
        str(alarm_id): state
        for alarm_id, state in assignments.items()
    }

    for (
        changed_at,
        alarm_id,
        from_state,
        to_state,
        severity,
        detected,
    ) in transitions:

        age_minutes = (
            changed_at - detected
        ).total_seconds() / 60.0

        reason = (
            f"SEEDED_RULE: seed={SEED}; "
            f"severity={severity}; "
            f"final_state={final_state_by_text[alarm_id]}"
        )

        conn.execute("""
            INSERT INTO alarm_history (
                alarm_id,
                from_state,
                to_state,
                changed_at,
                reason,
                severity,
                age_minutes,
                rule_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alarm_id,
            from_state,
            to_state,
            fmt_time(changed_at),
            reason,
            severity,
            round(age_minutes, 2),
            RULE_VERSION,
        ))

    for alarm_id, final_state in assignments.items():
        resolved_at = None

        if final_state in ("RESOLVED", "CLOSED"):
            detected = parse_time(
                next(row[2] for row in alarms if row[0] == alarm_id)
            )
            resolved_at = fmt_time(
                transition_time(detected, end, 0.65)
            )

        conn.execute("""
            UPDATE alarms
            SET lifecycle_state = ?,
                resolved_at = ?
            WHERE alarm_id = ?
        """, (
            final_state,
            resolved_at,
            alarm_id,
        ))

    return end, counts, len(transitions)


def validate(conn, end, expected_counts):
    check_integrity(conn, "Final database")

    actual = dict(conn.execute("""
        SELECT lifecycle_state, COUNT(*)
        FROM alarms
        GROUP BY lifecycle_state
    """).fetchall())

    for state in STATE_ORDER:
        actual.setdefault(state, 0)

    if actual != expected_counts:
        raise RuntimeError(f"Distribution mismatch: {actual}")

    end_text = fmt_time(end)

    later = conn.execute("""
        SELECT COUNT(*)
        FROM alarm_history
        WHERE changed_at > ?
    """, (end_text,)).fetchone()[0]

    if later:
        raise RuntimeError("History contains transitions after dataset end")

    invalid = conn.execute("""
        SELECT COUNT(*)
        FROM alarm_history
        WHERE NOT (
            (from_state = 'OPEN' AND to_state = 'ACKNOWLEDGED')
            OR
            (from_state = 'ACKNOWLEDGED' AND to_state = 'RESOLVED')
            OR
            (from_state = 'RESOLVED' AND to_state = 'CLOSED')
        )
    """).fetchone()[0]

    if invalid:
        raise RuntimeError("Invalid transition records found")

    history = conn.execute("""
        SELECT alarm_id, changed_at
        FROM alarm_history
        ORDER BY alarm_id, history_id
    """).fetchall()

    last_time = {}

    for alarm_id, changed_at in history:
        parsed = parse_time(changed_at)

        if alarm_id in last_time and parsed <= last_time[alarm_id]:
            raise RuntimeError(
                f"Non-increasing transition times for alarm {alarm_id}"
            )

        last_time[alarm_id] = parsed

    mismatch = conn.execute("""
        SELECT COUNT(*)
        FROM alarms a
        WHERE a.lifecycle_state != (
            SELECT h.to_state
            FROM alarm_history h
            WHERE h.alarm_id = a.alarm_id
            ORDER BY h.history_id DESC
            LIMIT 1
        )
    """).fetchone()[0]

    if mismatch:
        raise RuntimeError(
            f"{mismatch} alarm states disagree with their history"
        )

    triggers = {
        row[0]
        for row in conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
        """)
    }

    required = {
        "prevent_alarm_history_update",
        "prevent_alarm_history_delete",
    }

    if not required.issubset(triggers):
        raise RuntimeError("Append-only triggers are missing")


def main():
    if not DB.exists():
        raise RuntimeError(f"Database not found: {DB}")

    current = connect(DB)
    current_count = get_alarm_count(current)
    check_integrity(current, "Current database")
    current.close()

    print("========== SEEDED ALARM LIFECYCLE ==========")
    print(f"Database: {DB}")
    print(f"Seed: {SEED}")
    print(f"Alarms: {current_count}")

    original_backup = find_pre_lifecycle_backup(current_count)

    # Preserve the current database before restoring original alarm data.
    safety_backup = create_backup("before_lifecycle_rebuild")

    print("Restoring original database contents...")
    restore_database(original_backup)

    conn = connect(DB)

    try:
        conn.execute("BEGIN IMMEDIATE")

        end, counts, transition_count = apply_lifecycle(conn)
        validate(conn, end, counts)

        conn.commit()

        print("\n========== FINAL STATE DISTRIBUTION ==========")

        for state in STATE_ORDER:
            count = counts[state]
            percentage = count / current_count * 100
            print(f"{state}: {count} ({percentage:.2f}%)")

        print("\n========== TRANSITIONS ==========")
        print(f"History transition rows: {transition_count}")
        print(f"Dataset end: {fmt_time(end)}")

        latest = conn.execute("""
            SELECT MAX(changed_at) FROM alarm_history
        """).fetchone()[0]

        print(f"Latest transition: {latest}")

        print("\n========== VALIDATION ==========")
        print("SQLite integrity: PASS")
        print("Foreign keys: PASS")
        print("Seeded distribution: PASS")
        print("Chronological transitions: PASS")
        print("Dataset time boundary: PASS")
        print("Only actual transitions recorded: PASS")
        print("Append-only triggers: PASS")
        print("Current state matches history: PASS")
        print(f"Safety backup: {safety_backup}")
        print("\nRESULT: SUCCESS")

    except Exception:
        conn.rollback()
        print(
            "\nMigration failed. Transaction rolled back.",
            file=sys.stderr,
        )
        print(f"Safety backup: {safety_backup}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
