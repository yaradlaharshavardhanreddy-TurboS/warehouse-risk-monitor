
"""Generate sensors and their zone assignments."""

import random
import sqlite3
from datetime import datetime, timedelta

from app.database.database import DATABASE_PATH

SEED = 20261022

SENSOR_TYPES = [
    "TEMP",
    "TEMP",
    "HUMIDITY",
    "OCCUPANCY",
    "MULTI",
]

MANUFACTURERS = [
    "Honeywell",
    "Siemens",
    "Bosch",
    "Sensirion",
    "Generic",
]


def generate_sensors():
    random.seed(SEED)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        zone_count = cursor.execute(
            "SELECT COUNT(*) FROM zones"
        ).fetchone()[0]

        if zone_count != 100:
            raise RuntimeError(
                f"Expected 100 zones, found {zone_count}."
            )

        existing = cursor.execute(
            "SELECT COUNT(*) FROM sensors"
        ).fetchone()[0]

        if existing:
            raise RuntimeError(
                "Sensors already exist. Stopping to prevent duplicates."
            )

        zones = cursor.execute(
            "SELECT zone_id FROM zones ORDER BY zone_id"
        ).fetchall()

        now = datetime.now()
        sensor_records = []
        assignment_records = []

        sensor_number = 0

        for (zone_id,) in zones:
            for sensor_type in SENSOR_TYPES:
                sensor_number += 1

                sensor_id = f"SEN-{sensor_number:04d}"

                installation_date = now - timedelta(
                    days=random.randint(30, 365)
                )

                calibration_due = installation_date + timedelta(
                    days=180
                )

                sensor_records.append(
                    (
                        sensor_id,
                        f"{sensor_type} Sensor {sensor_number:04d}",
                        sensor_type,
                        random.choice(MANUFACTURERS),
                        installation_date.strftime("%Y-%m-%d %H:%M:%S"),
                        calibration_due.strftime("%Y-%m-%d %H:%M:%S"),
                        "ACTIVE",
                        installation_date.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )

                assignment_records.append(
                    (
                        sensor_id,
                        zone_id,
                        installation_date.strftime("%Y-%m-%d %H:%M:%S"),
                        None,
                        "Initial sensor installation",
                        installation_date.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )

        cursor.executemany(
            """
            INSERT INTO sensors (
                sensor_id,
                sensor_name,
                sensor_type,
                manufacturer,
                installation_date,
                calibration_due_date,
                lifecycle_state,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sensor_records,
        )

        cursor.executemany(
            """
            INSERT INTO sensor_zone_assignments (
                sensor_id,
                zone_id,
                effective_from,
                effective_to,
                assignment_reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            assignment_records,
        )

        connection.commit()

        print("Sensor generation successful!")
        print("Total zones:", len(zones))
        print("Sensors per zone:", len(SENSOR_TYPES))
        print("Total sensors:", len(sensor_records))
        print("Sensor-zone assignments:", len(assignment_records))

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_sensors()
