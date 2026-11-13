
import argparse
import re
import sqlite3
import uuid
from datetime import datetime, timezone

from app.database.database import DATABASE_PATH


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def allowed_values(conn, table, column):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()

    if not row or not row[0]:
        return []

    pattern = rf"{column}\s+IN\s*\((.*?)\)"
    match = re.search(pattern, row[0], re.IGNORECASE | re.DOTALL)

    if not match:
        return []

    return re.findall(r"'([^']*)'", match.group(1))


def choose_value(values, preferred, fallback=None):
    for value in preferred:
        if value in values:
            return value

    if values:
        return values[0]

    return fallback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        alarm_columns = {
            row[1] for row in cur.execute("PRAGMA table_info(alarms)")
        }
        inspection_columns = {
            row[1] for row in cur.execute("PRAGMA table_info(inspections)")
        }

        required_alarm_columns = {"alarm_id"}
        required_inspection_columns = {
            "inspection_id", "alarm_id", "inspector_name",
            "inspection_type", "inspection_status", "scheduled_at"
        }

        if not required_alarm_columns.issubset(alarm_columns):
            raise RuntimeError("Required columns missing from alarms table.")

        if not required_inspection_columns.issubset(inspection_columns):
            raise RuntimeError(
                "Required columns missing from inspections table."
            )

        status_values = allowed_values(
            conn, "inspections", "inspection_status"
        )
        type_values = allowed_values(
            conn, "inspections", "inspection_type"
        )

        inspection_status = choose_value(
            status_values,
            ["SCHEDULED", "PENDING", "PLANNED", "OPEN"],
            "SCHEDULED"
        )
        inspection_type = choose_value(
    type_values,
    ["QUALITY", "MAINTENANCE", "INVENTORY", "SAFETY"],
    "QUALITY"
        )

        existing = {
            row[0]
            for row in cur.execute(
                "SELECT alarm_id FROM inspections"
            )
        }

        alarms = [
            row[0]
            for row in cur.execute("SELECT alarm_id FROM alarms")
            if row[0] not in existing
        ]

        if args.limit > 0:
            alarms = alarms[:args.limit]

        print("===== INSPECTION MANAGER =====")
        print("Existing inspections:", len(existing))
        print("New inspections planned:", len(alarms))
        print("Inspection status:", inspection_status)
        print("Inspection type:", inspection_type)
        print("Mode:", "APPLY" if args.apply else "DRY RUN")

        if not args.apply:
            print("Dry run complete. No records inserted.")
            return

        timestamp = now()

        for alarm_id in alarms:
            inspection_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"warehouse-risk-inspection:{alarm_id}"
                )
            )

            cur.execute(
                """
                INSERT INTO inspections (
                    inspection_id,
                    alarm_id,
                    inspector_name,
                    inspection_type,
                    inspection_status,
                    scheduled_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    inspection_id,
                    alarm_id,
                    "UNASSIGNED",
                    inspection_type,
                    inspection_status,
                    timestamp
                )
            )

        conn.commit()
        print("Inspections inserted:", len(alarms))

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
