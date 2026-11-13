
import argparse
import json
import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from app.database.database import DATABASE_PATH

from app.analytics.alarm_analytics import get_alarm_analytics
from app.analytics.warehouse_analytics import get_warehouse_analytics
from app.analytics.inventory_analytics import get_inventory_analytics
from app.analytics.inspection_analytics import get_inspection_analytics
from app.analytics.remediation_analytics import get_remediation_analytics
from app.analytics.trend_analytics import get_trend_analytics


REQUIRED_TABLES = [
    "warehouses",
    "zones",
    "sensor_readings",
    "door_events",
    "inventory_lots",
    "alarms",
    "alarm_lots",
    "inspections",
    "remediations"
]


def validate_database(conn):
    cur = conn.cursor()

    for table in REQUIRED_TABLES:
        exists = cur.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
            AND name = ?
        """, (table,)).fetchone()

        if not exists:
            raise RuntimeError(
                f"Required analytics table is missing: {table}"
            )


def generate_analytics():
    conn = sqlite3.connect(
        f"file:{DATABASE_PATH.as_posix()}?mode=ro",
        uri=True
    )

    conn.execute("PRAGMA query_only = ON")

    try:
        validate_database(conn)

        report = {
            "report_name": "Warehouse Risk Monitoring Analytics",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds"),

            "analytics": {
                "alarms": get_alarm_analytics(conn),
                "warehouses": get_warehouse_analytics(conn),
                "inventory": get_inventory_analytics(conn),
                "inspections": get_inspection_analytics(conn),
                "remediations": get_remediation_analytics(conn),
                "trends": get_trend_analytics(conn)
            }
        }

        return report

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate warehouse risk analytics."
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Optional path to save the JSON analytics report."
    )

    args = parser.parse_args()

    print("\n===== PHASE 6 ANALYTICS ENGINE =====")

    report = generate_analytics()

    output = json.dumps(
        report,
        indent=4,
        default=str
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        output_path.write_text(
            output,
            encoding="utf-8"
        )

        print("Report saved to:", output_path)

    print(output)

    print("\n===== ANALYTICS COMPLETED =====")


if __name__ == "__main__":
    main()
