"""Generate deterministic warehouse door activity for Phase 4.

Run:
    python -m app.generator.door_event_data
    python -m app.generator.door_event_data --replace
"""

import argparse
import random
import sqlite3
from datetime import datetime, timedelta

from app.database.database import DATABASE_PATH
from scripts.phase10_generation_config import get_generator_seed

SEED = get_generator_seed('door_events')
SIMULATION_START = datetime(2026, 10, 22, 0, 0, 0)
SIMULATION_DAYS = 7


def _load_zones(connection, expected_zones=None):
    rows = connection.execute(
        """
        SELECT zone_id, zone_type
        FROM zones
        WHERE lifecycle_state = 'ACTIVE'
        ORDER BY zone_id
        """
    ).fetchall()

    if expected_zones is not None and len(rows) != expected_zones:
        raise RuntimeError(f"Expected {expected_zones} active zones; found {len(rows)}.")
    if not rows:
        raise RuntimeError("No active zones found.")
    return rows


def generate_door_events(replace=False, expected_zones=None):
    rng = random.Random(SEED)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        existing = connection.execute(
            "SELECT COUNT(*) FROM door_events"
        ).fetchone()[0]

        if existing and not replace:
            raise RuntimeError(
                f"door_events already contains {existing:,} rows. "
                "Use --replace only if you intentionally want to regenerate it."
            )

        zones = _load_zones(connection, expected_zones=expected_zones)
        if replace:
            connection.execute("DELETE FROM door_events")

        simulation_end = SIMULATION_START + timedelta(days=SIMULATION_DAYS)
        event_records = []
        event_number = 0

        for zone_id, zone_type in zones:
            # Loading bays are busier; freezer/cold doors are opened less often.
            if zone_type == "LOADING":
                interval_range = (35, 120)
                duration_range = (30, 600)
            elif zone_type in ("FREEZER", "COLD"):
                interval_range = (100, 260)
                duration_range = (10, 150)
            else:
                interval_range = (60, 190)
                duration_range = (15, 240)

            current = SIMULATION_START + timedelta(
                minutes=rng.randint(0, 45)
            )
            door_identifier = f"DOOR-{zone_id}-01"

            while current < simulation_end:
                duration = rng.randint(*duration_range)

                # A small fraction of cycles are abnormal, while retaining
                # a coherent open-to-close sequence.
                roll = rng.random()
                if roll < 0.005:
                    opening_type = "FORCED_OPEN"
                else:
                    opening_type = "OPENED"

                event_number += 1
                event_records.append(
                    (
                        f"DR-{event_number:08d}",
                        zone_id,
                        door_identifier,
                        opening_type,
                        current.strftime("%Y-%m-%d %H:%M:%S"),
                        None,
                        "SENSOR",
                    )
                )

                if roll >= 0.005 and roll < 0.025 and duration >= 60:
                    held_at = current + timedelta(seconds=min(60, duration // 2))
                    event_number += 1
                    event_records.append(
                        (
                            f"DR-{event_number:08d}",
                            zone_id,
                            door_identifier,
                            "HELD_OPEN",
                            held_at.strftime("%Y-%m-%d %H:%M:%S"),
                            int((held_at - current).total_seconds()),
                            "SENSOR",
                        )
                    )

                closed_at = current + timedelta(seconds=duration)
                event_number += 1
                event_records.append(
                    (
                        f"DR-{event_number:08d}",
                        zone_id,
                        door_identifier,
                        "CLOSED",
                        closed_at.strftime("%Y-%m-%d %H:%M:%S"),
                        duration,
                        "SENSOR",
                    )
                )

                current += timedelta(
                    minutes=rng.randint(*interval_range)
                )

        connection.executemany(
            """
            INSERT INTO door_events (
                door_event_id, zone_id, door_identifier, event_type,
                event_timestamp, duration_seconds, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            event_records,
        )

        actual = connection.execute(
            "SELECT COUNT(*) FROM door_events"
        ).fetchone()[0]
        if actual != len(event_records):
            raise RuntimeError(
                f"Expected {len(event_records):,} door events; found {actual:,}."
            )

        connection.commit()

        print("Door event generation successful!")
        print("Active zones:", len(zones))
        print("Door identifiers:", len(zones))
        print("Door events inserted:", f"{len(event_records):,}")
        print("Simulation start:", SIMULATION_START.isoformat(sep=" "))
        print("Simulation days:", SIMULATION_DAYS)
        print("Event type distribution:")
        for event_type, count in connection.execute(
            """
            SELECT event_type, COUNT(*)
            FROM door_events
            GROUP BY event_type
            ORDER BY event_type
            """
        ):
            print(f"  {event_type}: {count:,}")
        print("Random seed:", SEED)

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace", action="store_true",
        help="Delete existing door events before generating new ones.",
    )
    args = parser.parse_args()
    generate_door_events(args.replace)


if __name__ == "__main__":
    main()
