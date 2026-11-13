
"""Generate warehouse master data."""

import sqlite3
from datetime import datetime
from app.database.database import DATABASE_PATH

WAREHOUSES = [
    ("WH-001", "Central Cold Storage", "Hyderabad", 8000, "COLD"),
    ("WH-002", "North Distribution Center", "Hyderabad", 6500, "MIXED"),
    ("WH-003", "South Storage Facility", "Bengaluru", 7000, "AMBIENT"),
    ("WH-004", "Frozen Goods Warehouse", "Chennai", 5000, "COLD"),
    ("WH-005", "Industrial Storage Hub", "Pune", 9000, "HOT"),
    ("WH-006", "Pharmaceutical Storage", "Mumbai", 4500, "COLD"),
    ("WH-007", "Eastern Distribution Center", "Kolkata", 6000, "MIXED"),
    ("WH-008", "Western Logistics Hub", "Ahmedabad", 7500, "AMBIENT"),
    ("WH-009", "Southern Cold Chain Center", "Kochi", 5500, "COLD"),
    ("WH-010", "National Distribution Center", "Delhi", 10000, "MIXED"),
]


def generate_warehouses():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        existing = cursor.execute(
            "SELECT COUNT(*) FROM warehouses"
        ).fetchone()[0]

        if existing:
            raise RuntimeError(
                "Warehouse records already exist. "
                "Generator stopped to prevent duplicates."
            )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.executemany(
            """
            INSERT INTO warehouses (
                warehouse_id,
                warehouse_name,
                location,
                capacity_sq_m,
                warehouse_type,
                lifecycle_state,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """,
            [
                (*warehouse, now, now)
                for warehouse in WAREHOUSES
            ],
        )

        connection.commit()

        print("Warehouse generation successful!")
        print("Total warehouses:", len(WAREHOUSES))

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_warehouses()
