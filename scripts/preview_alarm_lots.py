import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import statistics
import re

DB = Path("data/warehouse_monitor.db").resolve()
DATASET_END = datetime.fromisoformat("2026-10-29T00:05:10+00:00")
MAX_WINDOW = timedelta(hours=2)

TYPE_MAP = {
    "HIGH_TEMPERATURE": "TEMPERATURE",
    "LOW_TEMPERATURE": "TEMPERATURE",
    "HIGH_HUMIDITY": "HUMIDITY",
    "LOW_HUMIDITY": "HUMIDITY",
    "DOOR_OPEN": "DOOR_EXPOSURE",
    "HIGH_OCCUPANCY": "DWELL_TIME",
    "STORAGE_INCOMPATIBILITY": "STORAGE_INCOMPATIBILITY",
    "SENSOR_OUTAGE": "OTHER",
    "SENSOR_DRIFT": "OTHER",
}

def dt(value):
    if not value:
        return None
    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def stamp(value):
    return value.isoformat(timespec="microseconds")

def normalized(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())

def print_stats(conn, rows, title):
    total_lots = conn.execute(
        "SELECT COUNT(*) FROM inventory_lots"
    ).fetchone()[0]
    alarms = conn.execute(
        "SELECT alarm_id, alarm_type FROM alarms"
    ).fetchall()

    total_alarms = len(alarms)
    linked_alarm_ids = {r[0] for r in rows}
    unique_lots = len({r[1] for r in rows})
    zero = defaultdict(int)
    type_counts = defaultdict(int)
    type_links = defaultdict(int)

    for alarm_id, alarm_type in alarms:
        type_counts[alarm_type] += 1
        if alarm_id not in linked_alarm_ids:
            zero[alarm_type] += 1

    for row in rows:
        type_links[row[6]] += 1

    print(f"\n========== {title} ==========")
    print(f"Total links:                 {len(rows):,}")
    print(f"Unique affected lots:        {unique_lots:,} / {total_lots:,}")
    print(
        f"Affected lots percentage:   "
        f"{unique_lots * 100 / total_lots if total_lots else 0:.2f}%"
    )
    print(
        f"Average links per alarm:     "
        f"{len(rows) / total_alarms if total_alarms else 0:.2f}"
    )
    print(f"Alarms with zero links:      {sum(zero.values()):,}")

    print("\nZero-link alarms by type:")
    for alarm_type in sorted(type_counts):
        print(f"  {alarm_type:<28} {zero[alarm_type]:,}")

    print("\nAverage links per alarm by type:")
    for alarm_type in sorted(type_counts):
        average = type_links[alarm_type] / type_counts[alarm_type]
        print(
            f"  {alarm_type:<28} "
            f"{average:.2f} ({type_links[alarm_type]:,} links / "
            f"{type_counts[alarm_type]:,} alarms)"
        )

    non_door_zero = sum(
        count for alarm_type, count in zero.items()
        if alarm_type != "DOOR_OPEN"
    )
    print(f"\nNon-door alarms with zero links: {non_door_zero:,}")
    print("Non-door zero-link alarms by type:")
    for alarm_type in sorted(type_counts):
        if alarm_type != "DOOR_OPEN":
            print(f"  {alarm_type:<28} {zero[alarm_type]:,}")

def main():
    if not DB.is_file():
        raise SystemExit(f"Database not found: {DB}")

    conn = sqlite3.connect(
        f"file:{DB.as_posix()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row

    try:
        print("READ-ONLY PREVIEW — DATABASE WILL NOT BE MODIFIED")
        print("Database:", DB)

        # Inspect alarms columns before generating candidates.
        alarm_columns = {
            row["name"] for row in
            conn.execute("PRAGMA table_info(alarms)")
        }
        print("\n========== ALARM THRESHOLD / OBSERVED COLUMN CHECK ==========")
        print("Alarm columns:", ", ".join(sorted(alarm_columns)))

        threshold_names = {
            "threshold", "thresholdvalue", "temperaturethreshold",
            "humiditythreshold", "thresholdtemperaturec",
            "thresholdhumiditypct"
        }
        observed_names = {
            "observedvalue", "measuredvalue", "observedtemperaturec",
            "observedhumiditypct", "temperaturevalue", "humidityvalue"
        }

        threshold_col = next(
            (c for c in alarm_columns if normalized(c) in threshold_names),
            None
        )
        observed_col = next(
            (c for c in alarm_columns if normalized(c) in observed_names),
            None
        )

        print("Threshold column:", threshold_col or "NOT FOUND")
        print("Observed-value column:", observed_col or "NOT FOUND")

        use_alarm_values = bool(threshold_col and observed_col)
        if use_alarm_values:
            print("Alarm-level threshold confirmation: ENABLED")
        else:
            print(
                "Alarm-level threshold confirmation: NOT AVAILABLE; "
                "lot-specific requirement breach remains mandatory."
            )

        old_rows = conn.execute("""
            SELECT al.alarm_id, al.lot_id, al.impact_type,
                   al.impact_start, al.impact_end,
                   al.impact_details, a.alarm_type
            FROM alarm_lots al
            JOIN alarms a ON a.alarm_id = al.alarm_id
        """).fetchall()

        old_rows = [tuple(r) for r in old_rows]
        print_stats(conn, old_rows, "BEFORE — EXISTING ALARM_LOTS")

        # Read alarms. resolved_at is deliberately never selected or used.
        alarm_select = """
            SELECT alarm_id, zone_id, sensor_id, alarm_type, detected_at
        """
        if use_alarm_values:
            alarm_select += f', "{observed_col}", "{threshold_col}"'
        alarm_select += " FROM alarms"

        alarms = conn.execute(alarm_select).fetchall()

        requirements = {
            r["requirement_id"]: dict(r)
            for r in conn.execute("SELECT * FROM storage_requirements")
        }

        lots = conn.execute("""
            SELECT lot_id, requirement_id
            FROM inventory_lots
        """).fetchall()

        assignments = conn.execute("""
            SELECT lot_id, zone_id, assigned_at, released_at
            FROM lot_zone_assignments
        """).fetchall()

        assignments_by_zone = defaultdict(list)
        for row in assignments:
            assignments_by_zone[row["zone_id"]].append({
                "lot_id": row["lot_id"],
                "start": dt(row["assigned_at"]),
                "end": dt(row["released_at"]),
            })

        lot_requirements = {}
        for lot in lots:
            req = requirements.get(lot["requirement_id"])
            if req:
                lot_requirements[lot["lot_id"]] = req

        readings_cache = {}
        candidate_rows = set()
        window_lengths = []
        missing_first_reading = defaultdict(int)
        first_reading_found = defaultdict(int)
        threshold_rejected = defaultdict(int)

        def alarm_threshold_confirms(alarm_type, observed, threshold):
            if observed is None or threshold is None:
                return True
            try:
                observed = float(observed)
                threshold = float(threshold)
            except (TypeError, ValueError):
                return True

            if alarm_type in ("HIGH_TEMPERATURE", "HIGH_HUMIDITY"):
                return observed > threshold
            if alarm_type in ("LOW_TEMPERATURE", "LOW_HUMIDITY"):
                return observed < threshold
            return True

        def lot_breaches(alarm_type, value, req):
            if value is None:
                return False
            value = float(value)

            if alarm_type == "HIGH_TEMPERATURE":
                return value > req["max_temperature_c"]
            if alarm_type == "LOW_TEMPERATURE":
                return value < req["min_temperature_c"]
            if alarm_type == "HIGH_HUMIDITY":
                return value > req["max_humidity_pct"]
            if alarm_type == "LOW_HUMIDITY":
                return value < req["min_humidity_pct"]
            return False

        for alarm in alarms:
            alarm_id = alarm["alarm_id"]
            zone_id = alarm["zone_id"]
            sensor_id = alarm["sensor_id"]
            alarm_type = alarm["alarm_type"]
            start = dt(alarm["detected_at"])

            if start is None or start >= DATASET_END:
                continue

            if alarm_type == "DOOR_OPEN":
                # Door exposure is restricted to cold/frozen requirements.
                end = min(start + MAX_WINDOW, DATASET_END)
                for assignment in assignments_by_zone.get(zone_id, []):
                    req = lot_requirements.get(assignment["lot_id"])
                    if not req:
                        continue

                    product_type = str(req["product_type"]).lower()
                    cold_or_frozen = any(
                        word in product_type
                        for word in ("cold", "frozen", "freezer", "refrigerat")
                    )
                    if not cold_or_frozen:
                        continue

                    if assignment["start"] >= end:
                        continue
                    if assignment["end"] is not None and assignment["end"] <= start:
                        continue

                    overlap_start = max(start, assignment["start"])
                    overlap_end = min(
                        end,
                        assignment["end"] or end
                    )
                    if overlap_start >= overlap_end:
                        continue

                    candidate_rows.add((
                        alarm_id,
                        assignment["lot_id"],
                        "DOOR_EXPOSURE",
                        stamp(overlap_start),
                        stamp(overlap_end),
                        "DOOR_OPEN; cold/frozen requirement; same-zone stay overlap",
                        alarm_type,
                        (end - start).total_seconds() / 60
                    ))
                    window_lengths.append((end - start).total_seconds() / 60)
                continue

            if alarm_type not in (
                "HIGH_TEMPERATURE", "LOW_TEMPERATURE",
                "HIGH_HUMIDITY", "LOW_HUMIDITY"
            ):
                continue

            if not sensor_id:
                missing_first_reading[alarm_type] += 1
                continue

            cap = min(start + MAX_WINDOW, DATASET_END)

            if sensor_id not in readings_cache:
                readings_cache[sensor_id] = [
                    dict(r) for r in conn.execute("""
                        SELECT recorded_at, temperature_c, humidity_pct
                        FROM sensor_readings
                        WHERE sensor_id = ?
                        ORDER BY recorded_at
                    """, (sensor_id,))
                ]

            readings = []
            for reading in readings_cache[sensor_id]:
                reading_time = dt(reading["recorded_at"])
                if reading_time is not None and start <= reading_time <= cap:
                    readings.append((reading_time, reading))

            # The first reading MUST be exactly at detected_at.
            if not readings or readings[0][0] != start:
                missing_first_reading[alarm_type] += 1
                continue

            first_reading_found[alarm_type] += 1

            alarm_observed = alarm["observed_value"] if use_alarm_values else None
            alarm_threshold = alarm["threshold_value"] if use_alarm_values else None

            if use_alarm_values and not alarm_threshold_confirms(
                alarm_type, alarm_observed, alarm_threshold
            ):
                threshold_rejected[alarm_type] += 1
                continue

            measurement_key = (
                "temperature_c"
                if alarm_type.endswith("TEMPERATURE")
                else "humidity_pct"
            )

            for assignment in assignments_by_zone.get(zone_id, []):
                req = lot_requirements.get(assignment["lot_id"])
                if not req:
                    continue

                # Only requirements effective at the alarm start are eligible.
                effective_from = dt(req["effective_from"])
                effective_to = dt(req["effective_to"])
                if effective_from and start < effective_from:
                    continue
                if effective_to and start >= effective_to:
                    continue

                # Lot must overlap the alarm window.
                if assignment["start"] >= cap:
                    continue
                if assignment["end"] is not None and assignment["end"] <= start:
                    continue

                first_value = readings[0][1][measurement_key]

                # Mandatory first-reading breach against this lot's own limits.
                if not lot_breaches(alarm_type, first_value, req):
                    continue

                last_breach_time = start
                peak_or_lowest = float(first_value)

                # Continue only through consecutive readings that breach
                # this particular lot's requirement.
                for reading_time, reading in readings[1:]:
                    value = reading[measurement_key]
                    if not lot_breaches(alarm_type, value, req):
                        break

                    last_breach_time = reading_time
                    value = float(value)
                    if alarm_type.startswith("HIGH_"):
                        peak_or_lowest = max(peak_or_lowest, value)
                    else:
                        peak_or_lowest = min(peak_or_lowest, value)

                # Make the last reading part of a non-empty half-open interval.
                end = min(
                    last_breach_time + timedelta(microseconds=1),
                    DATASET_END
                )

                if end <= start:
                    continue

                overlap_start = max(start, assignment["start"])
                overlap_end = min(end, assignment["end"] or end)

                if overlap_start >= overlap_end:
                    continue

                impact_type = TYPE_MAP[alarm_type]
                details = (
                    f"Same-zone overlap; first reading at detected_at breached "
                    f"lot requirement; consecutive readings checked; "
                    f"window_peak_or_lowest={peak_or_lowest}; "
                    f"window_end={stamp(end)}"
                )

                candidate_rows.add((
                    alarm_id,
                    assignment["lot_id"],
                    impact_type,
                    stamp(overlap_start),
                    stamp(overlap_end),
                    details,
                    alarm_type,
                    (last_breach_time - start).total_seconds() / 60
                ))

        candidates = sorted(
            candidate_rows,
            key=lambda r: (r[0], r[1], r[3])
        )

        # The final tuple field is internal reporting data, not a DB column.
        print("\n========== READING WINDOW DIAGNOSTICS ==========")
        for alarm_type in sorted(TYPE_MAP):
            if alarm_type == "DOOR_OPEN":
                continue
            print(
                f"{alarm_type:<28} "
                f"first reading found={first_reading_found[alarm_type]:,}; "
                f"missing={missing_first_reading[alarm_type]:,}; "
                f"alarm-threshold rejected={threshold_rejected[alarm_type]:,}"
            )

        print("\n========== PROPOSED WINDOW LENGTH ==========")
        if window_lengths:
            print(f"Average window length: {statistics.mean(window_lengths):.2f} minutes")
            print(f"Windows measured:      {len(window_lengths):,}")
        else:
            print("Average window length: N/A (no candidate windows)")

        db_rows = [row[:7] for row in candidates]
        print_stats(conn, db_rows, "PROPOSED — PREVIEW ONLY")

        print("\n========== FINAL PREVIEW ==========")
        print(f"Existing links: {len(old_rows):,}")
        print(f"Proposed links: {len(db_rows):,}")
        print(f"Difference:     {len(db_rows) - len(old_rows):+,}")
        print("\nNo database writes were performed.")
        print("No backup was created.")
        print("No rows were deleted or inserted.")
        print("This script has no APPLY operation.")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
