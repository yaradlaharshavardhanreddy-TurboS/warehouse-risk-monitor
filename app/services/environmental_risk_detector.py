"""
Phase 5: Environmental Risk Detection Engine.

Detects temperature and humidity violations against product-specific
storage requirements and links alarms to inventory lots exposed in
the affected zone.

Default execution is DRY RUN. Use --apply to save alarms.
"""

import argparse
import hashlib
import sqlite3
from collections import Counter
from datetime import datetime, timedelta

from app.database.database import DATABASE_PATH


INFINITY = "9999-12-31 23:59:59"

METRICS = {
    "TEMPERATURE": {
        "column": "temperature_c",
        "high_alarm": "HIGH_TEMPERATURE",
        "low_alarm": "LOW_TEMPERATURE",
        "impact_type": "TEMPERATURE",
    },
    "HUMIDITY": {
        "column": "humidity_pct",
        "high_alarm": "HIGH_HUMIDITY",
        "low_alarm": "LOW_HUMIDITY",
        "impact_type": "HUMIDITY",
    },
}


def merge_intervals(intervals):
    """Merge overlapping or adjacent time intervals."""
    if not intervals:
        return []

    intervals = sorted(intervals)
    merged = [list(intervals[0])]

    for start, end in intervals[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def interval_contains(intervals, timestamp):
    """Return True when timestamp falls inside an interval."""
    low = 0
    high = len(intervals) - 1

    while low <= high:
        mid = (low + high) // 2
        start, end = intervals[mid]

        if timestamp < start:
            high = mid - 1
        elif timestamp >= end:
            low = mid + 1
        else:
            return True

    return False


def get_severity(metric, deviation):
    """Calculate severity based on the amount of threshold violation."""
    if metric == "TEMPERATURE":
        if deviation >= 5:
            return "CRITICAL"
        if deviation >= 3:
            return "HIGH"
        if deviation >= 1:
            return "MEDIUM"
        return "LOW"

    if deviation >= 20:
        return "CRITICAL"
    if deviation >= 10:
        return "HIGH"
    if deviation >= 5:
        return "MEDIUM"
    return "LOW"


def make_alarm_id(sensor_id, alarm_type, requirement_id, start):
    """Create a deterministic alarm ID to prevent duplicate alarms."""
    raw = f"{sensor_id}|{alarm_type}|{requirement_id}|{start}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f"ALM-ENV-{digest.upper()}"


def load_zone_requirements(conn):
    """
    Load product requirements and inventory assignments.

    Each zone is mapped to the requirements of the lots stored there.
    Assignment and requirement effective dates are both respected.
    """
    requirements = {}

    rows = conn.execute("""
        SELECT
            lza.zone_id,
            lza.lot_id,
            lza.assigned_at,
            lza.released_at,
            sr.requirement_id,
            sr.product_type,
            sr.min_temperature_c,
            sr.max_temperature_c,
            sr.min_humidity_pct,
            sr.max_humidity_pct,
            sr.effective_from,
            sr.effective_to
        FROM lot_zone_assignments lza
        JOIN inventory_lots il
            ON il.lot_id = lza.lot_id
        JOIN storage_requirements sr
            ON sr.requirement_id = il.requirement_id
        JOIN zones z
            ON z.zone_id = lza.zone_id
        WHERE z.lifecycle_state = 'ACTIVE'
          AND il.lifecycle_state IN (
              'RECEIVED',
              'STORED',
              'UNDER_INSPECTION',
              'QUARANTINED'
          )
        ORDER BY lza.zone_id, sr.requirement_id
    """).fetchall()

    for row in rows:
        zone_id = row["zone_id"]
        requirement_id = row["requirement_id"]

        start = max(row["assigned_at"], row["effective_from"])
        end = min(
            row["released_at"] or INFINITY,
            row["effective_to"] or INFINITY,
        )

        if start >= end:
            continue

        key = (zone_id, requirement_id)

        if key not in requirements:
            requirements[key] = {
                "zone_id": zone_id,
                "requirement_id": requirement_id,
                "product_type": row["product_type"],
                "min_temperature_c": row["min_temperature_c"],
                "max_temperature_c": row["max_temperature_c"],
                "min_humidity_pct": row["min_humidity_pct"],
                "max_humidity_pct": row["max_humidity_pct"],
                "intervals": [],
                "lots": [],
            }

        requirements[key]["intervals"].append((start, end))
        requirements[key]["lots"].append({
            "lot_id": row["lot_id"],
            "start": start,
            "end": end,
        })

    by_zone = {}

    for requirement in requirements.values():
        requirement["intervals"] = merge_intervals(
            requirement["intervals"]
        )
        by_zone.setdefault(requirement["zone_id"], []).append(requirement)

    return by_zone


def find_affected_lots(requirement, episode_start, episode_end):
    """Find lots exposed during an environmental risk episode."""
    affected = []

    for lot in requirement["lots"]:
        start = max(episode_start, lot["start"])
        end = min(episode_end, lot["end"])

        if start <= end:
            affected.append({
                "lot_id": lot["lot_id"],
                "impact_start": start,
                "impact_end": end,
            })

    return affected


def run_detection(dry_run=True, min_readings=2, gap_minutes=10):
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        by_zone = load_zone_requirements(conn)

        # Requirement IDs are unique in storage_requirements. Keeping this
        # lookup allows episode keys to use a hashable string, not a dict.
        requirements_by_id = {
            requirement["requirement_id"]: requirement
            for zone_requirements in by_zone.values()
            for requirement in zone_requirements
        }

        print("\n===== ENVIRONMENTAL RISK DETECTION =====")
        print("Mode:", "DRY RUN" if dry_run else "APPLY")
        print("Minimum consecutive readings:", min_readings)
        print("Maximum gap between readings:", gap_minutes, "minutes")
        print("Zones with stored inventory requirements:", len(by_zone))

        reading_query = """
            SELECT
                r.sensor_id,
                r.recorded_at,
                r.temperature_c,
                r.humidity_pct,
                z.zone_id,
                z.warehouse_id
            FROM sensor_readings r
            JOIN sensor_zone_assignments sza
                ON sza.sensor_id = r.sensor_id
               AND sza.effective_from <= r.recorded_at
               AND (
                    sza.effective_to IS NULL
                    OR sza.effective_to > r.recorded_at
               )
            JOIN zones z
                ON z.zone_id = sza.zone_id
            WHERE z.lifecycle_state = 'ACTIVE'
            ORDER BY r.sensor_id, r.recorded_at
        """

        states = {}
        episode_counts = Counter()
        severity_counts = Counter()

        totals = {
            "episodes": 0,
            "short_episodes": 0,
            "affected_lot_links": 0,
            "inserted_alarms": 0,
            "inserted_lot_links": 0,
        }

        gap = timedelta(minutes=gap_minutes)

        def save_episode(key, state):
            (
                sensor_id,
                zone_id,
                warehouse_id,
                requirement_id,
                metric,
                alarm_type,
            ) = key

            requirement = requirements_by_id[requirement_id]

            if state["count"] < min_readings:
                totals["short_episodes"] += 1
                return

            totals["episodes"] += 1
            episode_counts[alarm_type] += 1

            severity = get_severity(metric, state["max_deviation"])
            severity_counts[severity] += 1

            affected_lots = find_affected_lots(
                requirement,
                state["start"],
                state["end"],
            )
            totals["affected_lot_links"] += len(affected_lots)

            alarm_id = make_alarm_id(
                sensor_id,
                alarm_type,
                requirement_id,
                state["start"],
            )

            direction = (
                "above maximum"
                if alarm_type.startswith("HIGH_")
                else "below minimum"
            )

            minimum = (
                requirement["min_temperature_c"]
                if metric == "TEMPERATURE"
                else requirement["min_humidity_pct"]
            )
            maximum = (
                requirement["max_temperature_c"]
                if metric == "TEMPERATURE"
                else requirement["max_humidity_pct"]
            )

            description = (
                f"{requirement['product_type']} environmental violation: "
                f"{metric.lower()} was {direction} its storage limit. "
                f"Observed value: {state['worst_value']:.2f}. "
                f"Allowed range: {minimum:.2f} to {maximum:.2f}. "
                f"Consecutive readings: {state['count']}. "
                f"Episode: {state['start']} to {state['end']}. "
                f"Affected inventory lots: {len(affected_lots)}."
            )

            print(
                f"\n[{severity}] {alarm_type} | "
                f"Sensor: {sensor_id} | Zone: {zone_id} | "
                f"Lots: {len(affected_lots)}"
            )

            if dry_run:
                return

            conn.execute("""
                INSERT OR IGNORE INTO alarms (
                    alarm_id,
                    warehouse_id,
                    zone_id,
                    sensor_id,
                    alarm_type,
                    severity,
                    detected_at,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alarm_id,
                warehouse_id,
                zone_id,
                sensor_id,
                alarm_type,
                severity,
                state["start"],
                description,
            ))

            totals["inserted_alarms"] += max(
                conn.execute("SELECT changes()").fetchone()[0], 0
            )

            for lot in affected_lots:
                conn.execute("""
                    INSERT OR IGNORE INTO alarm_lots (
                        alarm_id,
                        lot_id,
                        impact_type,
                        impact_start,
                        impact_end,
                        impact_details
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    alarm_id,
                    lot["lot_id"],
                    METRICS[metric]["impact_type"],
                    lot["impact_start"],
                    lot["impact_end"],
                    (
                        f"{metric} violation for "
                        f"{requirement['product_type']}; "
                        f"observed value {state['worst_value']:.2f}"
                    ),
                ))

                totals["inserted_lot_links"] += max(
                    conn.execute("SELECT changes()").fetchone()[0], 0
                )

        def flush_state(key):
            state = states.pop(key, None)
            if state is not None:
                save_episode(key, state)

        cursor = conn.execute(reading_query)

        for row in cursor:
            sensor_id = row["sensor_id"]
            zone_id = row["zone_id"]
            warehouse_id = row["warehouse_id"]
            timestamp = row["recorded_at"]

            zone_requirements = by_zone.get(zone_id, [])

            for metric, config in METRICS.items():
                value = row[config["column"]]

                # A sensor may not measure every metric.
                if value is None:
                    continue

                for requirement in zone_requirements:
                    requirement_id = requirement["requirement_id"]

                    # Base key ends an episode when inventory is no longer
                    # assigned to this requirement in the zone.
                    base_key = (
                        sensor_id,
                        zone_id,
                        warehouse_id,
                        requirement_id,
                        metric,
                        None,
                    )

                    if not interval_contains(
                        requirement["intervals"], timestamp
                    ):
                        flush_state(base_key)
                        continue

                    if metric == "TEMPERATURE":
                        minimum = requirement["min_temperature_c"]
                        maximum = requirement["max_temperature_c"]
                    else:
                        minimum = requirement["min_humidity_pct"]
                        maximum = requirement["max_humidity_pct"]

                    if value > maximum:
                        alarm_type = config["high_alarm"]
                        deviation = value - maximum
                    elif value < minimum:
                        alarm_type = config["low_alarm"]
                        deviation = minimum - value
                    else:
                        flush_state(base_key)
                        continue

                    # Use the requirement ID (a string) in state keys.
                    key = (
                        sensor_id,
                        zone_id,
                        warehouse_id,
                        requirement_id,
                        metric,
                        alarm_type,
                    )

                    opposite_type = (
                        config["low_alarm"]
                        if alarm_type == config["high_alarm"]
                        else config["high_alarm"]
                    )

                    opposite_key = (
                        sensor_id,
                        zone_id,
                        warehouse_id,
                        requirement_id,
                        metric,
                        opposite_type,
                    )
                    flush_state(opposite_key)

                    state = states.get(key)

                    if state is not None:
                        previous_time = datetime.fromisoformat(state["end"])
                        current_time = datetime.fromisoformat(timestamp)

                        if current_time - previous_time > gap:
                            flush_state(key)
                            state = None

                    if state is None:
                        state = {
                            "start": timestamp,
                            "end": timestamp,
                            "count": 0,
                            "max_deviation": 0.0,
                            "worst_value": value,
                        }
                        states[key] = state

                    state["count"] += 1
                    state["end"] = timestamp

                    if deviation > state["max_deviation"]:
                        state["max_deviation"] = deviation
                        state["worst_value"] = value

        # Flush all episodes still open at the end of the dataset.
        for key in list(states):
            flush_state(key)

        if not dry_run:
            conn.commit()

        print("\n===== DETECTION SUMMARY =====")
        print("Qualifying risk episodes:", totals["episodes"])
        print(
            "Episodes below minimum reading count:",
            totals["short_episodes"],
        )
        print("Affected inventory links found:", totals["affected_lot_links"])

        print("\nAlarm counts by type:")
        for alarm_type, count in sorted(episode_counts.items()):
            print(f"  {alarm_type}: {count}")

        print("\nAlarm counts by severity:")
        for severity, count in sorted(severity_counts.items()):
            print(f"  {severity}: {count}")

        if not dry_run:
            print("\nNew alarms inserted:", totals["inserted_alarms"])
            print("New alarm-lot links inserted:", totals["inserted_lot_links"])
        else:
            print("\nDRY RUN: No database records were changed.")

        return totals

    except Exception:
        if not dry_run:
            conn.rollback()
        raise

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Detect environmental warehouse risks."
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Save detected alarms to the database.",
    )
    parser.add_argument(
        "--min-readings",
        type=int,
        default=2,
        help="Minimum consecutive violating readings per episode.",
    )
    parser.add_argument(
        "--gap-minutes",
        type=int,
        default=10,
        help="Maximum time gap between consecutive violating readings.",
    )

    args = parser.parse_args()

    if args.min_readings < 1:
        parser.error("--min-readings must be at least 1")
    if args.gap_minutes < 1:
        parser.error("--gap-minutes must be at least 1")

    run_detection(
        dry_run=not args.apply,
        min_readings=args.min_readings,
        gap_minutes=args.gap_minutes,
    )


if __name__ == "__main__":
    main()
