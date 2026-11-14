
"""Generate warehouse zone master data."""

import sqlite3
from datetime import datetime

from app.database.database import DATABASE_PATH

ZONES_PER_WAREHOUSE = 10

ZONE_TYPES = [
    "COLD",
    "HOT",
    "AMBIENT",
    "FREEZER",
    "LOADING",
]


def generate_zones(expected_warehouses=None):
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        warehouse_count = cursor.execute(
            "SELECT COUNT(*) FROM warehouses"
        ).fetchone()[0]

        if expected_warehouses is not None and warehouse_count != expected_warehouses:
            raise RuntimeError(f"Expected {expected_warehouses} warehouses, found {warehouse_count}.")

        existing = cursor.execute(
            "SELECT COUNT(*) FROM zones"
        ).fetchone()[0]

        if existing:
            raise RuntimeError(
                "Zones already exist. Generator stopped "
                "to prevent duplicate records."
            )

        warehouses = cursor.execute(
            "SELECT warehouse_id FROM warehouses ORDER BY warehouse_id"
        ).fetchall()

        now = "2026-01-01 00:00:00"

        zone_records = []

        for warehouse_index, (warehouse_id,) in enumerate(warehouses, 1):
            for zone_number in range(1, ZONES_PER_WAREHOUSE + 1):

                zone_id = (
                    f"ZN-{warehouse_index:03d}-{zone_number:02d}"
                )

                zone_type = ZONE_TYPES[
                    (zone_number - 1) % len(ZONE_TYPES)
                ]

                zone_name = f"Zone {zone_number:02d}"
                max_capacity = 500 + (zone_number * 100)

                zone_records.append(
                    (
                        zone_id,
                        warehouse_id,
                        zone_name,
                        zone_type,
                        max_capacity,
                        "ACTIVE",
                        now,
                    )
                )

        cursor.executemany(
            """
            INSERT INTO zones (
                zone_id,
                warehouse_id,
                zone_name,
                zone_type,
                max_capacity,
                lifecycle_state,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            zone_records,
        )

        connection.commit()

        print("Zone generation successful!")
        print("Total warehouses:", warehouse_count)
        print("Zones per warehouse:", ZONES_PER_WAREHOUSE)
        print("Total zones:", len(zone_records))

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_zones()
