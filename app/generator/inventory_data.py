
"""Generate inventory lots and their zone assignments."""

import random
import sqlite3
from datetime import datetime, timedelta

from app.database.database import DATABASE_PATH

SEED = 20261022
LOT_COUNT = 10_000

BASE_DATE = datetime(2026, 1, 1)

PRODUCT_ZONE_MAPPING = {
    "DAIRY": "COLD",
    "PRODUCE": "COLD",
    "FROZEN_FOOD": "FREEZER",
    "PHARMA": "COLD",
    "ELECTRONICS": "AMBIENT",
}


def format_timestamp(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def generate_inventory():
    rng = random.Random(SEED)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        # Check prerequisite master data.
        warehouse_count = cursor.execute(
            "SELECT COUNT(*) FROM warehouses"
        ).fetchone()[0]

        zone_count = cursor.execute(
            "SELECT COUNT(*) FROM zones"
        ).fetchone()[0]

        requirement_count = cursor.execute(
            "SELECT COUNT(*) FROM storage_requirements"
        ).fetchone()[0]

        if warehouse_count != 10:
            raise RuntimeError(
                f"Expected 10 warehouses, found {warehouse_count}."
            )

        if zone_count != 100:
            raise RuntimeError(
                f"Expected 100 zones, found {zone_count}."
            )

        if requirement_count != 5:
            raise RuntimeError(
                f"Expected 5 requirements, found {requirement_count}."
            )

        existing_lots = cursor.execute(
            "SELECT COUNT(*) FROM inventory_lots"
        ).fetchone()[0]

        if existing_lots:
            raise RuntimeError(
                "Inventory lots already exist. "
                "Stopping to prevent duplicate records."
            )

        # Read storage requirement IDs.
        requirements = {
            product_type: requirement_id
            for requirement_id, product_type
            in cursor.execute(
                """
                SELECT requirement_id, product_type
                FROM storage_requirements
                """
            ).fetchall()
        }

        if set(requirements) != set(PRODUCT_ZONE_MAPPING):
            raise RuntimeError(
                "Storage requirement product types do not match "
                "the inventory generator configuration."
            )

        # Read compatible zones.
        zones_by_type = {}

        for zone_type in set(PRODUCT_ZONE_MAPPING.values()):
            zones_by_type[zone_type] = cursor.execute(
                """
                SELECT zone_id
                FROM zones
                WHERE zone_type = ?
                ORDER BY zone_id
                """,
                (zone_type,),
            ).fetchall()

            if not zones_by_type[zone_type]:
                raise RuntimeError(
                    f"No zones found for type {zone_type}."
                )

        product_types = list(PRODUCT_ZONE_MAPPING.keys())

        lot_records = []
        assignment_records = []

        for number in range(1, LOT_COUNT + 1):
            lot_id = f"LOT-{number:06d}"

            product_type = rng.choice(product_types)

            requirement_id = requirements[product_type]

            compatible_zone_type = PRODUCT_ZONE_MAPPING[product_type]

            zone_id = rng.choice(
                zones_by_type[compatible_zone_type]
            )[0]

            received_at = BASE_DATE + timedelta(
                days=rng.randint(0, 300),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            expiry_date = received_at + timedelta(
                days=rng.randint(30, 730)
            )

            quantity = rng.randint(10, 1000)

            product_name = (
                f"{product_type.replace('_', ' ').title()} "
                f"Batch {number:06d}"
            )

            lot_records.append(
                (
                    lot_id,
                    product_type,
                    product_name,
                    quantity,
                    "UNITS",
                    requirement_id,
                    format_timestamp(received_at),
                    format_timestamp(expiry_date),
                    "STORED",
                    format_timestamp(received_at),
                )
            )

            assignment_records.append(
                (
                    lot_id,
                    zone_id,
                    format_timestamp(received_at),
                    None,
                    "Initial compatible storage placement",
                    format_timestamp(received_at),
                )
            )

        # Insert inventory lots.
        cursor.executemany(
            """
            INSERT INTO inventory_lots (
                lot_id,
                product_type,
                product_name,
                quantity,
                unit_of_measure,
                requirement_id,
                received_at,
                expiry_date,
                lifecycle_state,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            lot_records,
        )

        # Insert lot-zone assignments.
        cursor.executemany(
            """
            INSERT INTO lot_zone_assignments (
                lot_id,
                zone_id,
                assigned_at,
                released_at,
                assignment_reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            assignment_records,
        )

        connection.commit()

        print("Inventory generation successful!")
        print("Inventory lots:", len(lot_records))
        print("Lot-zone assignments:", len(assignment_records))

        print("\nLots by product type:")

        results = cursor.execute(
            """
            SELECT product_type, COUNT(*)
            FROM inventory_lots
            GROUP BY product_type
            ORDER BY product_type
            """
        ).fetchall()

        for product_type, count in results:
            print(f"{product_type}: {count:,}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_inventory()
