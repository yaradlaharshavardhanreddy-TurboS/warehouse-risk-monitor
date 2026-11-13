from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_DIR = ROOT / "docs" / "phase10"

CSV_PATH = OUTPUT_DIR / "remediation_traceability.csv"
JSON_PATH = OUTPUT_DIR / "remediation_traceability_summary.json"


def quote_identifier(value: str) -> str:
    """Safely quote a SQLite identifier."""
    return '"' + value.replace('"', '""') + '"'


def load_table(conn, table_name):
    query = f"SELECT * FROM {quote_identifier(table_name)}"
    cursor = conn.execute(query)
    columns = [item[0] for item in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def first_value(record, candidates):
    for column in candidates:
        if column in record and record[column] is not None:
            return record[column]
    return None


def matching_records(records, column, value):
    if value is None:
        return []

    return [
        record for record in records
        if record.get(column) == value
    ]


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row

    try:
        table_names = {
            row["name"]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
            """)
        }

        required_tables = {
            "alarms",
            "alarm_lots",
            "inventory_lots",
            "inspections",
            "remediations",
        }

        missing = required_tables - table_names
        if missing:
            raise RuntimeError(
                f"Required tables missing: {sorted(missing)}"
            )

        alarms = load_table(conn, "alarms")
        alarm_lots = load_table(conn, "alarm_lots")
        inventory_lots = load_table(conn, "inventory_lots")
        inspections = load_table(conn, "inspections")
        remediations = load_table(conn, "remediations")

        lots_by_id = {
            lot.get("lot_id"): lot
            for lot in inventory_lots
            if lot.get("lot_id") is not None
        }

        rows = []

        for alarm in alarms:
            alarm_id = alarm.get("alarm_id")

            linked_lot_rows = matching_records(
                alarm_lots,
                "alarm_id",
                alarm_id
            )

            linked_lot_ids = sorted({
                link.get("lot_id")
                for link in linked_lot_rows
                if link.get("lot_id") is not None
            })

            alarm_inspections = matching_records(
                inspections,
                "alarm_id",
                alarm_id
            )

            alarm_remediations = matching_records(
                remediations,
                "alarm_id",
                alarm_id
            )

            # Also include remediation records linked through inspections.
            inspection_ids = {
                item.get("inspection_id")
                for item in alarm_inspections
                if item.get("inspection_id") is not None
            }

            for remediation in remediations:
                inspection_id = remediation.get("inspection_id")
                if inspection_id in inspection_ids:
                    if remediation not in alarm_remediations:
                        alarm_remediations.append(remediation)

            # Keep one report row per alarm-lot relationship.
            # Alarms without a linked lot still receive one row.
            report_lot_ids = linked_lot_ids or [None]

            for lot_id in report_lot_ids:
                lot = lots_by_id.get(lot_id, {})

                rows.append({
                    "alarm_id": alarm_id,
                    "warehouse_id": alarm.get("warehouse_id"),
                    "zone_id": alarm.get("zone_id"),
                    "sensor_id": alarm.get("sensor_id"),
                    "alarm_type": alarm.get("alarm_type"),
                    "severity": alarm.get("severity"),
                    "detected_at": alarm.get("detected_at"),
                    "alarm_status": first_value(
                        alarm,
                        ["status", "lifecycle_status"]
                    ),
                    "lot_id": lot_id,
                    "lot_status": first_value(
                        lot,
                        ["status", "lifecycle_status"]
                    ),
                    "product_id": lot.get("product_id"),
                    "inspection_count": len(alarm_inspections),
                    "inspection_ids": ";".join(
                        str(item.get("inspection_id"))
                        for item in alarm_inspections
                        if item.get("inspection_id") is not None
                    ),
                    "remediation_count": len(alarm_remediations),
                    "remediation_ids": ";".join(
                        str(item.get("remediation_id"))
                        for item in alarm_remediations
                        if item.get("remediation_id") is not None
                    ),
                    "inventory_link_status": (
                        "LINKED_TO_INVENTORY"
                        if lot_id is not None
                        else "NO_INVENTORY_LINK"
                    ),
                    "remediation_status": (
                        "REMEDIATION_RECORDED"
                        if alarm_remediations
                        else "NO_REMEDIATION_RECORDED"
                    ),
                })

        fieldnames = [
            "alarm_id",
            "warehouse_id",
            "zone_id",
            "sensor_id",
            "alarm_type",
            "severity",
            "detected_at",
            "alarm_status",
            "lot_id",
            "lot_status",
            "product_id",
            "inspection_count",
            "inspection_ids",
            "remediation_count",
            "remediation_ids",
            "inventory_link_status",
            "remediation_status",
        ]

        with CSV_PATH.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )
            writer.writeheader()
            writer.writerows(rows)

        inventory_link_counts = Counter(
            row["inventory_link_status"]
            for row in rows
        )

        remediation_status_counts = Counter(
            row["remediation_status"]
            for row in rows
        )

        summary = {
            "generated_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "source_database": str(
                DB_PATH.relative_to(ROOT)
            ),
            "source_database_modified": False,
            "total_alarms": len(alarms),
            "total_alarm_lot_links": len(alarm_lots),
            "total_inventory_lots": len(inventory_lots),
            "total_inspections": len(inspections),
            "total_remediations": len(remediations),
            "traceability_rows": len(rows),
            "alarms_with_inventory_links": len({
                row["alarm_id"]
                for row in rows
                if row["lot_id"] is not None
            }),
            "alarms_without_inventory_links": len({
                row["alarm_id"]
                for row in rows
                if row["lot_id"] is None
            }),
            "inventory_link_status": dict(
                inventory_link_counts
            ),
            "remediation_status": dict(
                remediation_status_counts
            ),
            "limitations": [
                "Inventory links reflect existing alarm_lots records.",
                "This report does not infer missing alarm-to-lot links.",
                "Remediation links are matched using alarm_id and inspection_id.",
                "No source database records are inserted or updated."
            ],
        }

        with JSON_PATH.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                summary,
                file,
                indent=4
            )

        print("========== PHASE 10.5 TRACEABILITY REPORT ==========")
        print("Alarms:", len(alarms))
        print("Alarm-lot links:", len(alarm_lots))
        print("Inventory lots:", len(inventory_lots))
        print("Inspections:", len(inspections))
        print("Remediations:", len(remediations))
        print("Traceability rows:", len(rows))

        print("\nInventory link status:")
        for name, count in inventory_link_counts.items():
            print(f"{name}: {count}")

        print("\nRemediation status:")
        for name, count in remediation_status_counts.items():
            print(f"{name}: {count}")

        print("\nGenerated:")
        print(CSV_PATH)
        print(JSON_PATH)

        print("\nSource database modified: NO")
        print("PHASE 10.5 REPORT GENERATION COMPLETED.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()