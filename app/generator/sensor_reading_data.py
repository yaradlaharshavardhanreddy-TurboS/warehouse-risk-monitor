"""Generate deterministic, realistic sensor readings for Phase 4.

Run:
    python -m app.generator.sensor_reading_data
    python -m app.generator.sensor_reading_data --count 5000
    python -m app.generator.sensor_reading_data --replace

The default creates exactly 1,000,000 readings (2,000 per sensor when
the database contains the expected 500 sensors).
"""

import argparse
import math
import random
import sqlite3
from datetime import datetime, timedelta

from app.database.database import DATABASE_PATH
from scripts.phase10_generation_config import get_generator_seed

SEED = get_generator_seed('sensor_readings')
DEFAULT_READING_COUNT = 1_000_000
READING_INTERVAL_MINUTES = 5
SIMULATION_START = datetime(2026, 10, 22, 0, 0, 0)
BATCH_SIZE = 10_000

# Approximate normal operating temperatures by zone type (Celsius).
TEMPERATURE_BASELINES = {
    "FREEZER": -18.0,
    "COLD": 4.0,
    "HOT": 28.0,
    "AMBIENT": 22.0,
    "LOADING": 20.0,
}
HUMIDITY_BASELINES = {
    "FREEZER": 55.0,
    "COLD": 60.0,
    "HOT": 45.0,
    "AMBIENT": 48.0,
    "LOADING": 58.0,
}


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _load_sensors(connection, expected_sensors=None):
    """Load each sensor with its currently assigned zone characteristics."""
    rows = connection.execute(
        """
        SELECT s.sensor_id, s.sensor_type, z.zone_id, z.zone_type,
               z.max_capacity
        FROM sensors AS s
        JOIN sensor_zone_assignments AS a
          ON a.sensor_id = s.sensor_id
         AND a.effective_to IS NULL
        JOIN zones AS z ON z.zone_id = a.zone_id
        WHERE s.lifecycle_state = 'ACTIVE'
        ORDER BY s.sensor_id
        """
    ).fetchall()

    if expected_sensors is not None and len(rows) != expected_sensors:
        raise RuntimeError(f"Expected {expected_sensors} active sensors with current zone assignments; found {len(rows)}.")
    if not rows:
        raise RuntimeError("No active sensors with current zone assignments were found.")

    sensor_ids = [row[0] for row in rows]
    if len(set(sensor_ids)) != len(sensor_ids):
        raise RuntimeError("A sensor has multiple current zone assignments.")

    return rows


def _make_reading(sensor, index, rng):
    sensor_id, sensor_type, _zone_id, zone_type, max_capacity = sensor
    timestamp = SIMULATION_START + timedelta(
        minutes=index * READING_INTERVAL_MINUTES
    )

    # Smooth daily cycle plus small random variation.
    day_angle = 2.0 * math.pi * (
        (timestamp.hour * 60 + timestamp.minute) / 1440.0
    )
    daily_wave = math.sin(day_angle - math.pi / 2.0)

    temperature = None
    humidity = None
    occupancy = None

    if sensor_type in ("TEMP", "MULTI"):
        baseline = TEMPERATURE_BASELINES.get(zone_type, 22.0)
        temperature = round(
            baseline + 0.7 * daily_wave + rng.gauss(0, 0.22), 2
        )

    if sensor_type in ("HUMIDITY", "MULTI"):
        baseline = HUMIDITY_BASELINES.get(zone_type, 50.0)
        humidity = round(
            _clamp(baseline + 2.0 * daily_wave + rng.gauss(0, 1.2), 0, 100),
            2,
        )

    if sensor_type in ("OCCUPANCY", "MULTI"):
        # Keep occupancy realistic and within the zone's declared capacity.
        capacity = max(1, int(max_capacity))
        typical_load = 0.16 + 0.08 * (1.0 + daily_wave)
        occupancy = int(
            _clamp(
                round(capacity * typical_load + rng.gauss(0, capacity * 0.025)),
                0,
                capacity,
            )
        )

    battery = round(
        _clamp(98.0 - (index * READING_INTERVAL_MINUTES / 1440.0) * 0.025
               + rng.uniform(-0.08, 0.08), 0, 100),
        2,
    )
    signal = round(_clamp(rng.gauss(-62.0, 7.0), -100, -25), 2)
    received_at = timestamp + timedelta(seconds=rng.randint(1, 45))

    reading_id = f"RDG-{sensor_id}-{index + 1:04d}"

    return (
        reading_id,
        sensor_id,
        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        temperature,
        humidity,
        occupancy,
        battery,
        signal,
        received_at.strftime("%Y-%m-%d %H:%M:%S"),
    )


def generate_sensor_readings(reading_count=DEFAULT_READING_COUNT, replace=False, expected_sensors=None):
    if reading_count < 1:
        raise ValueError("reading_count must be at least 1.")

    rng = random.Random(SEED)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        existing = connection.execute(
            "SELECT COUNT(*) FROM sensor_readings"
        ).fetchone()[0]

        if existing and not replace:
            raise RuntimeError(
                f"sensor_readings already contains {existing:,} rows. "
                "Use --replace only if you intentionally want to regenerate it."
            )

        sensors = _load_sensors(connection, expected_sensors=expected_sensors)

        if replace:
            connection.execute("DELETE FROM sensor_readings")

        base, remainder = divmod(reading_count, len(sensors))
        batch = []
        inserted = 0

        for sensor_index, sensor in enumerate(sensors):
            sensor_reading_count = base + (1 if sensor_index < remainder else 0)

            for reading_index in range(sensor_reading_count):
                batch.append(_make_reading(sensor, reading_index, rng))

                if len(batch) >= BATCH_SIZE:
                    connection.executemany(
                        """
                        INSERT INTO sensor_readings (
                            reading_id, sensor_id, recorded_at,
                            temperature_c, humidity_pct, occupancy_count,
                            battery_pct, signal_strength, received_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    inserted += len(batch)
                    batch.clear()

        if batch:
            connection.executemany(
                """
                INSERT INTO sensor_readings (
                    reading_id, sensor_id, recorded_at,
                    temperature_c, humidity_pct, occupancy_count,
                    battery_pct, signal_strength, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            inserted += len(batch)

        actual = connection.execute(
            "SELECT COUNT(*) FROM sensor_readings"
        ).fetchone()[0]
        if actual != reading_count:
            raise RuntimeError(
                f"Expected {reading_count:,} readings after insert; found {actual:,}."
            )

        connection.commit()

        print("Sensor reading generation successful!")
        print("Active sensors:", len(sensors))
        print("Readings inserted:", f"{inserted:,}")
        print("Total sensor_readings rows:", f"{actual:,}")
        print("Reading interval:", f"{READING_INTERVAL_MINUTES} minutes")
        print("Simulation start:", SIMULATION_START.isoformat(sep=" "))
        print("Random seed:", SEED)

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=DEFAULT_READING_COUNT,
        help="Total readings to generate (default: 1,000,000).",
    )
    parser.add_argument(
        "--replace", action="store_true",
        help="Delete existing sensor readings before generating new ones.",
    )
    args = parser.parse_args()
    generate_sensor_readings(args.count, args.replace)


if __name__ == "__main__":
    main()
