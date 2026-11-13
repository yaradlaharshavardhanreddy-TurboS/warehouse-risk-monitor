
import argparse
import hashlib
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from app.database.database import DATABASE_PATH


EXPECTED_READING_INTERVAL_MINUTES = 5
OCCUPANCY_GAP_MINUTES = 10


def make_id(prefix, *values):
    raw = "|".join(str(value) for value in values)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"{prefix}_{digest}"


def parse_time(value):
    return datetime.fromisoformat(value)


def load_assignments(cur):
    cur.execute("""
        SELECT sensor_id, zone_id, effective_from, effective_to
        FROM sensor_zone_assignments
        ORDER BY sensor_id, effective_from
    """)

    assignments = defaultdict(list)

    for sensor_id, zone_id, start, end in cur.fetchall():
        assignments[sensor_id].append((zone_id, start, end))

    return assignments


def find_zone(assignments, sensor_id, timestamp):
    for zone_id, start, end in assignments.get(sensor_id, []):
        if timestamp >= start and (end is None or timestamp < end):
            return zone_id

    return None


def insert_alarm(cur, alarm, apply):
    alarm_id = alarm[0]

    cur.execute(
        "SELECT 1 FROM alarms WHERE alarm_id = ?",
        (alarm_id,)
    )

    if cur.fetchone():
        return False

    if apply:
        cur.execute("""
            INSERT INTO alarms (
                alarm_id,
                warehouse_id,
                zone_id,
                sensor_id,
                alarm_type,
                severity,
                detected_at,
                description,
                lifecycle_state,
                resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, alarm)

    return True


def detect_door_risks(cur, apply, held_open_seconds):
    print("\n===== DOOR RISK DETECTION =====")

    cur.execute("""
        SELECT
            d.door_event_id,
            d.zone_id,
            d.event_type,
            d.event_timestamp,
            d.duration_seconds,
            z.warehouse_id
        FROM door_events d
        JOIN zones z ON z.zone_id = d.zone_id
        WHERE d.event_type IN ('FORCED_OPEN', 'HELD_OPEN')
        ORDER BY d.event_timestamp
    """)

    detected = 0

    for event_id, zone_id, event_type, timestamp, duration, warehouse_id in cur.fetchall():

        if event_type == "FORCED_OPEN":
            alarm_type = "DOOR_OPEN"
            severity = "CRITICAL"
            description = (
                f"Door forced open in zone {zone_id}"
            )

        elif duration is not None and duration >= held_open_seconds:
            alarm_type = "DOOR_OPEN"
            severity = "HIGH"
            description = (
                f"Door held open for {duration} seconds in zone {zone_id}"
            )

        else:
            continue

        alarm = (
            make_id("OP", event_id),
            warehouse_id,
            zone_id,
            None,
            alarm_type,
            severity,
            timestamp,
            description,
            "OPEN",
            None
        )

        if insert_alarm(cur, alarm, apply):
            detected += 1

    print("New door alarms:", detected)
    return detected


def detect_occupancy_risks(cur, apply):
    print("\n===== OCCUPANCY RISK DETECTION =====")

    cur.execute("""
        SELECT
            r.sensor_id,
            r.recorded_at,
            r.occupancy_count,
            a.zone_id,
            z.warehouse_id,
            z.max_capacity
        FROM sensor_readings r
        JOIN sensor_zone_assignments a
          ON a.sensor_id = r.sensor_id
         AND r.recorded_at >= a.effective_from
         AND (
             a.effective_to IS NULL
             OR r.recorded_at < a.effective_to
         )
        JOIN zones z ON z.zone_id = a.zone_id
        WHERE r.occupancy_count IS NOT NULL
          AND r.occupancy_count > z.max_capacity
        ORDER BY r.sensor_id, a.zone_id, r.recorded_at
    """)

    episodes = []
    current = None

    for row in cur:
        sensor_id, timestamp, occupancy, zone_id, warehouse_id, capacity = row

        if current is None:
            current = {
                "sensor_id": sensor_id,
                "zone_id": zone_id,
                "warehouse_id": warehouse_id,
                "start": timestamp,
                "end": timestamp,
                "maximum": occupancy,
                "capacity": capacity
            }
            continue

        same_group = (
            current["sensor_id"] == sensor_id
            and current["zone_id"] == zone_id
        )

        within_gap = (
            parse_time(timestamp) - parse_time(current["end"])
        ).total_seconds() <= OCCUPANCY_GAP_MINUTES * 60

        if same_group and within_gap:
            current["end"] = timestamp
            current["maximum"] = max(current["maximum"], occupancy)
        else:
            episodes.append(current)
            current = {
                "sensor_id": sensor_id,
                "zone_id": zone_id,
                "warehouse_id": warehouse_id,
                "start": timestamp,
                "end": timestamp,
                "maximum": occupancy,
                "capacity": capacity
            }

    if current is not None:
        episodes.append(current)

    detected = 0

    for episode in episodes:
        alarm = (
            make_id(
                "OP",
                "OCCUPANCY",
                episode["sensor_id"],
                episode["zone_id"],
                episode["start"]
            ),
            episode["warehouse_id"],
            episode["zone_id"],
            episode["sensor_id"],
            "OCCUPANCY_OVER_CAPACITY",
            "HIGH",
            episode["start"],
            (
                f"Maximum occupancy {episode['maximum']} exceeded "
                f"zone capacity {episode['capacity']}. "
                f"Episode ended at {episode['end']}."
            ),
            "OPEN",
            None
        )

        if insert_alarm(cur, alarm, apply):
            detected += 1

    print("Occupancy risk episodes:", detected)
    return detected


def detect_sensor_outages(cur, apply, outage_minutes, assignments):
    print("\n===== SENSOR OUTAGE DETECTION =====")

    cur.execute("""
        SELECT sensor_id, recorded_at
        FROM sensor_readings
        ORDER BY sensor_id, recorded_at
    """)

    detected = 0
    previous_sensor = None
    previous_timestamp = None

    for sensor_id, timestamp in cur:
        if sensor_id == previous_sensor and previous_timestamp is not None:

            gap = (
                parse_time(timestamp) -
                parse_time(previous_timestamp)
            )

            if gap.total_seconds() > outage_minutes * 60:
                outage_start = (
                    parse_time(previous_timestamp)
                    + timedelta(minutes=EXPECTED_READING_INTERVAL_MINUTES)
                ).isoformat(sep=" ")

                outage_end = timestamp
                zone_id = find_zone(
                    assignments,
                    sensor_id,
                    outage_start
                )

                warehouse_id = None

                if zone_id:
                    cur.execute("""
                        SELECT warehouse_id
                        FROM zones
                        WHERE zone_id = ?
                    """, (zone_id,))
                    result = cur.fetchone()
                    if result:
                        warehouse_id = result[0]

                outage_id = make_id(
                    "OUT",
                    sensor_id,
                    outage_start,
                    outage_end
                )

                cur.execute("""
                    SELECT 1
                    FROM sensor_outages
                    WHERE outage_id = ?
                """, (outage_id,))

                if not cur.fetchone():
                    alarm = (
                        make_id("OP", "OUTAGE", outage_id),
                        warehouse_id,
                        zone_id,
                        sensor_id,
                        "SENSOR_OUTAGE",
                        "HIGH",
                        outage_start,
                        (
                            f"Sensor {sensor_id} had a reading gap "
                            f"of {gap.total_seconds() / 60:.1f} minutes."
                        ),
                        "OPEN",
                        None
                    )

                    if insert_alarm(cur, alarm, apply):
                        detected += 1

                    if apply:
                        cur.execute("""
                            INSERT INTO sensor_outages (
                                outage_id,
                                sensor_id,
                                outage_start,
                                outage_end,
                                detected_at,
                                outage_reason,
                                lifecycle_state
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            outage_id,
                            sensor_id,
                            outage_start,
                            outage_end,
                            timestamp,
                            "MISSING_SENSOR_READINGS",
                            "RESOLVED"
                        ))

        previous_sensor = sensor_id
        previous_timestamp = timestamp

    print("New sensor outage alarms:", detected)
    return detected


def main():
    parser = argparse.ArgumentParser(
        description="Warehouse operational risk detector"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Save detected alarms and outages to the database"
    )

    parser.add_argument(
        "--held-open-seconds",
        type=int,
        default=60
    )

    parser.add_argument(
        "--outage-minutes",
        type=int,
        default=15
    )

    args = parser.parse_args()

    if args.held_open_seconds < 1 or args.outage_minutes < 1:
        parser.error("Duration thresholds must be positive.")

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        print("\n===== OPERATIONAL RISK DETECTOR =====")
        print("Mode:", "APPLY" if args.apply else "DRY RUN")

        assignments = load_assignments(cur)

        door_count = detect_door_risks(
            cur,
            args.apply,
            args.held_open_seconds
        )

        occupancy_count = detect_occupancy_risks(
            cur,
            args.apply
        )

        outage_count = detect_sensor_outages(
            cur,
            args.apply,
            args.outage_minutes,
            assignments
        )

        print("\n===== DETECTION SUMMARY =====")
        print("Door alarms:", door_count)
        print("Occupancy alarms:", occupancy_count)
        print("Sensor outage alarms:", outage_count)
        print(
            "Total new alarms:",
            door_count + occupancy_count + outage_count
        )

        if args.apply:
            conn.commit()
            print("\nDatabase changes committed successfully.")
        else:
            conn.rollback()
            print("\nDRY RUN: No database records were changed.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
