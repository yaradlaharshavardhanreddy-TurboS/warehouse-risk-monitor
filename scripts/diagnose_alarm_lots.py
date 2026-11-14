import sqlite3
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone, timedelta

DB = Path("data/warehouse_monitor.db").resolve()
DATASET_END = datetime.fromisoformat("2026-10-29T00:05:10+00:00")
MAX_WINDOW = timedelta(hours=2)

TEMP_TYPES = {"HIGH_TEMPERATURE", "LOW_TEMPERATURE"}
HUMIDITY_TYPES = {"HIGH_HUMIDITY", "LOW_HUMIDITY"}
MEASURE_TYPES = TEMP_TYPES | HUMIDITY_TYPES


def dt(value):
    if value is None:
        return None
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def fmt(value):
    return value.isoformat(timespec="seconds") if value else "N/A"


def breach(alarm_type, value, req):
    if value is None:
        return False
    value = float(value)

    if alarm_type == "HIGH_TEMPERATURE":
        limit = req["max_temperature_c"]
        return limit is not None and value > float(limit)

    if alarm_type == "LOW_TEMPERATURE":
        limit = req["min_temperature_c"]
        return limit is not None and value < float(limit)

    if alarm_type == "HIGH_HUMIDITY":
        limit = req["max_humidity_pct"]
        return limit is not None and value > float(limit)

    if alarm_type == "LOW_HUMIDITY":
        limit = req["min_humidity_pct"]
        return limit is not None and value < float(limit)

    return False


def main():
    if not DB.is_file():
        raise SystemExit(f"Database not found: {DB}")

    conn = sqlite3.connect(
        f"file:{DB.as_posix()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row

    try:
        print("=" * 76)
        print("READ-ONLY ALARM / LOT DIAGNOSTIC")
        print("Database:", DB)
        print("Dataset end:", fmt(DATASET_END))
        print("No database writes or backup creation.")
        print("=" * 76)

        # ------------------------------------------------------------
        # 1. Storage requirements and lot counts
        # ------------------------------------------------------------
        requirements = conn.execute("""
            SELECT
                r.requirement_id,
                r.product_type,
                r.min_temperature_c,
                r.max_temperature_c,
                r.min_humidity_pct,
                r.max_humidity_pct,
                r.effective_from,
                r.effective_to,
                COUNT(DISTINCT l.lot_id) AS lot_count
            FROM storage_requirements r
            LEFT JOIN inventory_lots l
                ON l.requirement_id = r.requirement_id
            GROUP BY
                r.requirement_id,
                r.product_type,
                r.min_temperature_c,
                r.max_temperature_c,
                r.min_humidity_pct,
                r.max_humidity_pct,
                r.effective_from,
                r.effective_to
            ORDER BY r.product_type, r.requirement_id
        """).fetchall()

        print("\n========== 1. STORAGE REQUIREMENTS ==========")
        print(f"Requirement rows: {len(requirements)}")
        print(
            f"{'REQUIREMENT ID':<24} {'PRODUCT TYPE':<25} "
            f"{'TEMP MIN':>9} {'TEMP MAX':>9} "
            f"{'HUM MIN':>9} {'HUM MAX':>9} {'LOTS':>7}"
        )
        print("-" * 105)

        for r in requirements:
            print(
                f"{r['requirement_id']:<24} "
                f"{str(r['product_type']):<25.25} "
                f"{str(r['min_temperature_c']):>9} "
                f"{str(r['max_temperature_c']):>9} "
                f"{str(r['min_humidity_pct']):>9} "
                f"{str(r['max_humidity_pct']):>9} "
                f"{r['lot_count']:>7,}"
            )
            print(
                f"  effective_from={r['effective_from']} "
                f"effective_to={r['effective_to']}"
            )

        # ------------------------------------------------------------
        # Load assignments and requirements for zone-based analysis
        # ------------------------------------------------------------
        req_by_id = {
            r["requirement_id"]: dict(r)
            for r in conn.execute("SELECT * FROM storage_requirements")
        }

        lot_req = {
            r["lot_id"]: r["requirement_id"]
            for r in conn.execute("""
                SELECT lot_id, requirement_id
                FROM inventory_lots
            """)
        }

        assignment_rows = conn.execute("""
            SELECT lot_id, zone_id, assigned_at, released_at
            FROM lot_zone_assignments
            ORDER BY zone_id, assigned_at
        """).fetchall()

        assignments_by_zone = defaultdict(list)
        assignments_by_lot = defaultdict(list)

        for row in assignment_rows:
            item = {
                "lot_id": row["lot_id"],
                "zone_id": row["zone_id"],
                "start": dt(row["assigned_at"]),
                "end": dt(row["released_at"]),
            }
            assignments_by_zone[item["zone_id"]].append(item)
            assignments_by_lot[item["lot_id"]].append(item)

        zones = conn.execute("""
            SELECT zone_id, zone_name, zone_type
            FROM zones
            ORDER BY zone_id
        """).fetchall()

        # ------------------------------------------------------------
        # 2. Per-zone distinct requirements and average lot stay
        # ------------------------------------------------------------
        print("\n========== 2. ZONE REQUIREMENTS AND LOT STAYS ==========")
        print(
            f"{'ZONE ID':<22} {'ZONE NAME':<24} "
            f"{'REQ TYPES':>10} {'ASSIGNMENTS':>12} "
            f"{'AVG STAY DAYS':>15}"
        )
        print("-" * 90)

        for zone in zones:
            zone_id = zone["zone_id"]
            zone_assignments = assignments_by_zone.get(zone_id, [])

            distinct_requirements = {
                lot_req.get(a["lot_id"])
                for a in zone_assignments
                if lot_req.get(a["lot_id"]) is not None
            }

            durations = []
            for a in zone_assignments:
                if a["start"] is None:
                    continue

                stay_end = min(a["end"] or DATASET_END, DATASET_END)
                if stay_end > a["start"]:
                    durations.append(
                        (stay_end - a["start"]).total_seconds() / 86400
                    )

            avg_stay = statistics.mean(durations) if durations else 0.0

            print(
                f"{zone_id:<22} "
                f"{str(zone['zone_name']):<24.24} "
                f"{len(distinct_requirements):>10,} "
                f"{len(zone_assignments):>12,} "
                f"{avg_stay:>15.2f}"
            )

        # ------------------------------------------------------------
        # Load alarms and existing alarm_lots counts
        # ------------------------------------------------------------
        alarms = conn.execute("""
            SELECT alarm_id, zone_id, sensor_id, alarm_type, detected_at
            FROM alarms
            ORDER BY detected_at
        """).fetchall()

        links_by_alarm = defaultdict(int)
        for row in conn.execute("""
            SELECT alarm_id, COUNT(DISTINCT lot_id) AS n
            FROM alarm_lots
            GROUP BY alarm_id
        """):
            links_by_alarm[row["alarm_id"]] = row["n"]

        # ------------------------------------------------------------
        # 3. Alarm type: zone occupancy at detected_at and current links
        # ------------------------------------------------------------
        type_counts = defaultdict(int)
        type_lot_counts = defaultdict(list)
        type_link_counts = defaultdict(list)

        alarm_lots_at_detection = {}

        for alarm in alarms:
            alarm_id = alarm["alarm_id"]
            zone_id = alarm["zone_id"]
            alarm_type = alarm["alarm_type"]
            detected = dt(alarm["detected_at"])

            present_lots = set()
            if detected is not None:
                for a in assignments_by_zone.get(zone_id, []):
                    if a["start"] is None or a["start"] > detected:
                        continue
                    if a["end"] is not None and a["end"] <= detected:
                        continue
                    present_lots.add(a["lot_id"])

            alarm_lots_at_detection[alarm_id] = present_lots
            type_counts[alarm_type] += 1
            type_lot_counts[alarm_type].append(len(present_lots))
            type_link_counts[alarm_type].append(
                links_by_alarm.get(alarm_id, 0)
            )

        print("\n========== 3. ALARM TYPE SUMMARY ==========")
        print(
            f"{'ALARM TYPE':<28} {'ALARMS':>9} "
            f"{'AVG LOTS IN ZONE':>18} {'AVG EXISTING LINKS':>20}"
        )
        print("-" * 80)

        for alarm_type in sorted(type_counts):
            print(
                f"{alarm_type:<28} "
                f"{type_counts[alarm_type]:>9,} "
                f"{statistics.mean(type_lot_counts[alarm_type]):>18.2f} "
                f"{statistics.mean(type_link_counts[alarm_type]):>20.2f}"
            )

        # ------------------------------------------------------------
        # 4. Requirement-relative consecutive reading windows
        # ------------------------------------------------------------
        print("\n========== 4. REQUIREMENT-RELATIVE READING WINDOWS ==========")
        print(
            "Definition: detected_at reading must exist and breach at least "
            "one applicable lot requirement. Continue while each next "
            "reading breaches at least one such requirement. Stop at the "
            "first reading that breaches none. Maximum duration: 120 minutes."
        )
        print(
            "This is NOT a confirmed alarm-clear duration; alarm thresholds "
            "are absent from the alarms schema."
        )

        readings_cache = {}
        window_durations = defaultdict(list)
        window_missing = defaultdict(int)
        window_first_not_breaching = defaultdict(int)
        window_no_current_lots = defaultdict(int)

        for alarm in alarms:
            alarm_type = alarm["alarm_type"]
            if alarm_type not in MEASURE_TYPES:
                continue

            alarm_id = alarm["alarm_id"]
            sensor_id = alarm["sensor_id"]
            zone_id = alarm["zone_id"]
            start = dt(alarm["detected_at"])

            if not sensor_id or not start or start >= DATASET_END:
                window_missing[alarm_type] += 1
                continue

            # Requirements of lots actually present in this zone at detection.
            applicable = set()
            for lot_id in alarm_lots_at_detection.get(alarm_id, set()):
                requirement_id = lot_req.get(lot_id)
                req = req_by_id.get(requirement_id)
                if not req:
                    continue

                effective_from = dt(req["effective_from"])
                effective_to = dt(req["effective_to"])
                if effective_from and start < effective_from:
                    continue
                if effective_to and start >= effective_to:
                    continue

                applicable.add(requirement_id)

            if not applicable:
                window_no_current_lots[alarm_type] += 1
                continue

            if sensor_id not in readings_cache:
                readings_cache[sensor_id] = [
                    dict(r) for r in conn.execute("""
                        SELECT recorded_at, temperature_c, humidity_pct
                        FROM sensor_readings
                        WHERE sensor_id = ?
                        ORDER BY recorded_at
                    """, (sensor_id,))
                ]

            cap = min(start + MAX_WINDOW, DATASET_END)
            measurement = (
                "temperature_c"
                if alarm_type in TEMP_TYPES
                else "humidity_pct"
            )

            readings = []
            for reading in readings_cache[sensor_id]:
                reading_time = dt(reading["recorded_at"])
                if reading_time is not None and start <= reading_time <= cap:
                    readings.append((reading_time, reading))

            if not readings or readings[0][0] != start:
                window_missing[alarm_type] += 1
                continue

            def any_requirement_breached(reading):
                value = reading[measurement]
                return any(
                    breach(alarm_type, value, req_by_id[req_id])
                    for req_id in applicable
                )

            if not any_requirement_breached(readings[0][1]):
                window_first_not_breaching[alarm_type] += 1
                continue

            last_breach = start
            for reading_time, reading in readings[1:]:
                if not any_requirement_breached(reading):
                    break
                last_breach = reading_time

            duration = (last_breach - start).total_seconds() / 60
            window_durations[alarm_type].append(duration)

        for label, alarm_types in (
            ("TEMPERATURE", TEMP_TYPES),
            ("HUMIDITY", HUMIDITY_TYPES),
        ):
            values = [
                duration
                for alarm_type in alarm_types
                for duration in window_durations[alarm_type]
            ]
            total_alarm_count = sum(type_counts[t] for t in alarm_types)
            measured_count = len(values)

            print(f"\n{label}:")
            print(f"  Alarms:                     {total_alarm_count:,}")
            print(f"  Windows measured:           {measured_count:,}")
            print(
                f"  Average window length:      "
                f"{statistics.mean(values):.2f} minutes"
                if values else
                "  Average window length:      N/A"
            )
            print(
                f"  Median window length:       "
                f"{statistics.median(values):.2f} minutes"
                if values else
                "  Median window length:       N/A"
            )
            print(
                f"  Missing exact first reading: "
                f"{sum(window_missing[t] for t in alarm_types):,}"
            )
            print(
                f"  First reading not breaching: "
                f"{sum(window_first_not_breaching[t] for t in alarm_types):,}"
            )
            print(
                f"  No applicable current lots:  "
                f"{sum(window_no_current_lots[t] for t in alarm_types):,}"
            )

            for alarm_type in sorted(alarm_types):
                vals = window_durations[alarm_type]
                print(
                    f"    {alarm_type:<24} "
                    f"n={len(vals):>5,}; "
                    f"avg={statistics.mean(vals):>8.2f} min"
                    if vals else
                    f"    {alarm_type:<24} n=0; avg=N/A"
                )

        # ------------------------------------------------------------
        # 5. Alarm counts per zone
        # ------------------------------------------------------------
        alarm_counts_by_zone = defaultdict(int)
        for alarm in alarms:
            alarm_counts_by_zone[alarm["zone_id"]] += 1

        zone_counts = [
            (zone["zone_id"], zone["zone_name"],
             alarm_counts_by_zone[zone["zone_id"]])
            for zone in zones
        ]

        counts = [item[2] for item in zone_counts]

        print("\n========== 5. ALARM COUNTS PER ZONE ==========")
        if counts:
            print(f"Zones counted: {len(counts):,}")
            print(f"Minimum alarms per zone: {min(counts):,}")
            print(f"Median alarms per zone:  {statistics.median(counts):,.1f}")
            print(f"Maximum alarms per zone: {max(counts):,}")

            print("\nTop 10 zones by alarm count:")
            print(f"{'ZONE ID':<22} {'ZONE NAME':<28} {'ALARMS':>10}")
            print("-" * 64)
            for zone_id, zone_name, count in sorted(
                zone_counts, key=lambda x: (-x[2], x[0])
            )[:10]:
                print(
                    f"{zone_id:<22} {str(zone_name):<28.28} {count:>10,}"
                )
        else:
            print("No zones found.")

        print("\n========== READ-ONLY CONFIRMATION ==========")
        print("No database writes performed.")
        print("No backup created.")
        print("No tables or rows changed.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
