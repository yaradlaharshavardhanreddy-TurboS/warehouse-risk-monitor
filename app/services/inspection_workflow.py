"""Safely complete a scheduled inspection using recorded findings."""

import argparse
import sqlite3
from datetime import datetime, timezone

from app.database.database import DATABASE_PATH


def main():
    parser = argparse.ArgumentParser(
        description="Complete a scheduled warehouse inspection."
    )
    parser.add_argument("--inspection-id", required=True)
    parser.add_argument("--findings", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the inspection completion. Default is dry-run.",
    )
    args = parser.parse_args()

    findings = args.findings.strip()
    if not findings:
        parser.error("--findings cannot be empty.")

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        inspection = conn.execute(
            """
            SELECT
                i.inspection_id,
                i.alarm_id,
                i.inspector_name,
                i.inspection_type,
                i.inspection_status,
                i.scheduled_at,
                a.alarm_type
            FROM inspections i
            JOIN alarms a ON a.alarm_id = i.alarm_id
            WHERE i.inspection_id = ?
            """,
            (args.inspection_id,),
        ).fetchone()

        if inspection is None:
            raise ValueError("Inspection not found.")

        if inspection["inspection_status"].upper() != "SCHEDULED":
            raise ValueError(
                "Only SCHEDULED inspections can be completed. "
                f"Current status: {inspection['inspection_status']}"
            )

        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

        print("========== INSPECTION COMPLETION ==========")
        print("Inspection:", inspection["inspection_id"])
        print("Alarm:", inspection["alarm_id"])
        print("Alarm type:", inspection["alarm_type"])
        print("Inspector:", inspection["inspector_name"])
        print("Inspection type:", inspection["inspection_type"])
        print("Findings:", findings)
        print("Completed at:", timestamp)
        print("Mode:", "APPLY" if args.apply else "DRY RUN")

        if not args.apply:
            print("Dry run complete. No database changes made.")
            return

        cursor = conn.execute(
            """
            UPDATE inspections
            SET inspection_status = 'COMPLETED',
                findings = ?,
                completed_at = ?
            WHERE inspection_id = ?
              AND UPPER(inspection_status) = 'SCHEDULED'
            """,
            (findings, timestamp, args.inspection_id),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Inspection was not updated; its status may have changed."
            )

        conn.commit()
        print("PASS: Inspection marked COMPLETED.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
