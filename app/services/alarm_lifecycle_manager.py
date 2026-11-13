
import argparse
import re
import sqlite3
from datetime import datetime, timezone

from app.database.database import DATABASE_PATH


def get_allowed_states(conn):
    row = conn.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='alarms'
        """
    ).fetchone()

    if not row or not row[0]:
        raise RuntimeError("Could not read alarms table schema.")

    match = re.search(
        r"lifecycle_state\s+IN\s*\((.*?)\)",
        row[0],
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        raise RuntimeError(
            "Could not identify allowed alarm lifecycle states."
        )

    return re.findall(r"'([^']*)'", match.group(1))


def main():
    parser = argparse.ArgumentParser(
        description="Update the lifecycle state of one alarm."
    )
    parser.add_argument("--alarm-id", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        allowed = get_allowed_states(conn)
        requested_status = args.status.upper()

        if requested_status not in allowed:
            raise ValueError(
                f"Invalid status '{requested_status}'. "
                f"Allowed statuses: {', '.join(allowed)}"
            )

        row = cur.execute(
            """
            SELECT lifecycle_state
            FROM alarms
            WHERE alarm_id = ?
            """,
            (args.alarm_id,)
        ).fetchone()

        if not row:
            raise ValueError(
                f"Alarm not found: {args.alarm_id}"
            )

        current_status = row[0]

        print("===== ALARM LIFECYCLE MANAGER =====")
        print("Alarm ID:", args.alarm_id)
        print("Current status:", current_status)
        print("Requested status:", requested_status)
        print("Allowed statuses:", allowed)
        print("Mode:", "APPLY" if args.apply else "DRY RUN")

        if current_status == requested_status:
            print("Alarm already has the requested status.")
            return

        if not args.apply:
            print("Dry run complete. No changes made.")
            return

        timestamp = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )

        if requested_status in {"RESOLVED", "CLOSED"}:
            cur.execute(
                """
                UPDATE alarms
                SET lifecycle_state = ?, resolved_at = ?
                WHERE alarm_id = ?
                """,
                (requested_status, timestamp, args.alarm_id)
            )
        else:
            cur.execute(
                """
                UPDATE alarms
                SET lifecycle_state = ?, resolved_at = NULL
                WHERE alarm_id = ?
                """,
                (requested_status, args.alarm_id)
            )

        conn.commit()
        print("Alarm lifecycle updated successfully.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
