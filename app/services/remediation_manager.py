
import argparse
import sqlite3
import uuid
from datetime import datetime, timezone

from app.database.database import DATABASE_PATH


REMEDIATION_MAP = {
    "HIGH_TEMPERATURE": "ADJUST_TEMPERATURE",
    "LOW_TEMPERATURE": "ADJUST_TEMPERATURE",
    "HIGH_HUMIDITY": "ADJUST_HUMIDITY",
    "LOW_HUMIDITY": "ADJUST_HUMIDITY",
    "DOOR_OPEN": "CLOSE_DOOR",
    "SENSOR_OUTAGE": "REPAIR_SENSOR",
    "SENSOR_DRIFT": "RECALIBRATE_SENSOR",
    "HIGH_OCCUPANCY": "RELOCATE_INVENTORY",
    "STORAGE_INCOMPATIBILITY": "QUARANTINE_INVENTORY",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        alarm_lot_columns = {
            row[1] for row in cur.execute("PRAGMA table_info(alarm_lots)")
        }

        if not {"alarm_id", "lot_id"}.issubset(alarm_lot_columns):
            raise RuntimeError(
                "alarm_lots must contain alarm_id and lot_id columns."
            )

        existing = {
            (row[0], row[1] or "")
            for row in cur.execute(
                "SELECT inspection_id, lot_id FROM remediations"
            )
        }

        completed_statuses = {"COMPLETED", "COMPLETE", "CLOSED"}

        inspections = cur.execute(
            """
            SELECT
                i.inspection_id,
                i.alarm_id,
                a.alarm_type
            FROM inspections i
            JOIN alarms a ON a.alarm_id = i.alarm_id
            WHERE UPPER(i.inspection_status) IN (
                'COMPLETED', 'COMPLETE', 'CLOSED'
            )
            ORDER BY i.inspection_id
            """
        ).fetchall()

        plans = []

        for inspection_id, alarm_id, alarm_type in inspections:
            remediation_type = REMEDIATION_MAP.get(alarm_type)

            if not remediation_type:
                continue

            lots = cur.execute(
                """
                SELECT lot_id
                FROM alarm_lots
                WHERE alarm_id = ?
                AND lot_id IS NOT NULL
                ORDER BY lot_id
                """,
                (alarm_id,)
            ).fetchall()

            for (lot_id,) in lots:
                if (inspection_id, lot_id) in existing:
                    continue

                remediation_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"warehouse-remediation:{inspection_id}:{lot_id}:{remediation_type}"
                    )
                )

                plans.append((
                    remediation_id,
                    inspection_id,
                    lot_id,
                    remediation_type,
                    f"Review and address {alarm_type} affecting inventory lot {lot_id}.",
                    "PLANNED",
                    "UNASSIGNED"
                ))

                if args.limit > 0 and len(plans) >= args.limit:
                    break

            if args.limit > 0 and len(plans) >= args.limit:
                break

        print("===== REMEDIATION MANAGER =====")
        print("Completed inspections examined:", len(inspections))
        print("New remediation records planned:", len(plans))
        print("Record limit:", args.limit)
        print("Mode:", "APPLY" if args.apply else "DRY RUN")

        if not args.apply:
            print("Dry run complete. No records inserted.")
            return

        for plan in plans:
            cur.execute(
                """
                INSERT INTO remediations (
                    remediation_id,
                    inspection_id,
                    lot_id,
                    remediation_type,
                    action_description,
                    remediation_status,
                    assigned_to
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                plan
            )

        conn.commit()
        print("Remediation records inserted:", len(plans))

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
