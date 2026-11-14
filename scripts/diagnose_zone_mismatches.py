import sqlite3
from pathlib import Path
from collections import defaultdict

DB = Path("data/warehouse_monitor.db").resolve()

def main():
    if not DB.is_file():
        raise SystemExit(f"Database not found: {DB}")

    conn = sqlite3.connect(
        f"file:{DB.as_posix()}?mode=ro",
        uri=True
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA query_only = ON")

        print("=" * 76)
        print("READ-ONLY SENSOR AND LOT ZONE MISMATCH BREAKDOWN")
        print("Database:", DB)
        print("No database writes or backup creation.")
        print("=" * 76)

        # ---------------------------------------------------------
        # 1. Sensor mismatches grouped by alarm type
        # ---------------------------------------------------------
        sensor_rows = conn.execute("""
            SELECT
                a.alarm_id,
                a.alarm_type,
                a.sensor_id
            FROM alarms a
            WHERE NOT EXISTS (
                SELECT 1
                FROM sensor_zone_assignments sza
                WHERE sza.sensor_id = a.sensor_id
                  AND sza.zone_id = a.zone_id
                  AND julianday(sza.effective_from)
                      <= julianday(a.detected_at)
                  AND (
                      sza.effective_to IS NULL
                      OR julianday(sza.effective_to)
                         > julianday(a.detected_at)
                  )
            )
            ORDER BY a.alarm_type, a.alarm_id
        """).fetchall()

        sensor_by_type = defaultdict(list)
        for row in sensor_rows:
            sensor_by_type[row["alarm_type"]].append(row)

        null_sensor_count = sum(
            1 for row in sensor_rows if row["sensor_id"] is None
        )

        print("\n========== 1. SENSOR MISMATCHES ==========")
        print(f"Total sensor mismatches: {len(sensor_rows):,}")
        print(f"Alarms with sensor_id IS NULL: {null_sensor_count:,}")
        print(f"Alarms with non-NULL sensor_id: {len(sensor_rows) - null_sensor_count:,}")

        print("\nGrouped by alarm type:")
        print(f"{'ALARM TYPE':<30} {'MISMATCHES':>12} {'NULL SENSOR':>13}")
        print("-" * 60)

        for alarm_type in sorted(sensor_by_type):
            rows = sensor_by_type[alarm_type]
            nulls = sum(1 for r in rows if r["sensor_id"] is None)
            print(f"{alarm_type:<30} {len(rows):>12,} {nulls:>13,}")

        # ---------------------------------------------------------
        # 2. Lot mismatch classification
        # ---------------------------------------------------------
        mismatch_rows = conn.execute("""
            SELECT
                al.alarm_id,
                al.lot_id,
                al.impact_start,
                al.impact_end,
                a.alarm_type,
                a.zone_id,
                a.detected_at
            FROM alarm_lots al
            JOIN alarms a ON a.alarm_id = al.alarm_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM lot_zone_assignments lza
                WHERE lza.lot_id = al.lot_id
                  AND lza.zone_id = a.zone_id
                  AND julianday(lza.assigned_at)
                      <= julianday(a.detected_at)
                  AND (
                      lza.released_at IS NULL
                      OR julianday(lza.released_at)
                         > julianday(a.detected_at)
                  )
            )
            ORDER BY a.alarm_type, al.alarm_id, al.lot_id
        """).fetchall()

        categories = {
            "A_VALID_LATER_OVERLAP": defaultdict(list),
            "B_RELEASED_BEFORE_DETECTION": defaultdict(list),
            "C_NEVER_ASSIGNED_TO_ZONE": defaultdict(list),
            "OTHER_OUTSIDE_WINDOW": defaultdict(list),
        }

        for row in mismatch_rows:
            assignments = conn.execute("""
                SELECT assigned_at, released_at
                FROM lot_zone_assignments
                WHERE lot_id = ?
                  AND zone_id = ?
                ORDER BY assigned_at
            """, (row["lot_id"], row["zone_id"])).fetchall()

            detected = row["detected_at"]
            window_end = row["impact_end"]

            # A: A matching-zone assignment began after detection,
            #    but strictly before the recorded alarm-lot window end.
            later_overlap = False
            if window_end is not None:
                later_overlap = any(
                    conn.execute("""
                        SELECT
                            julianday(?) > julianday(?)
                            AND julianday(?) < julianday(?)
                    """, (
                        assignment["assigned_at"],
                        detected,
                        assignment["assigned_at"],
                        window_end
                    )).fetchone()[0]
                    for assignment in assignments
                )

            # B: At least one matching-zone stay ended at or before
            #    alarm detection.
            released_before = any(
                assignment["released_at"] is not None
                and conn.execute(
                    "SELECT julianday(?) <= julianday(?)",
                    (assignment["released_at"], detected)
                ).fetchone()[0]
                for assignment in assignments
            )

            if later_overlap:
                category = "A_VALID_LATER_OVERLAP"
            elif released_before:
                category = "B_RELEASED_BEFORE_DETECTION"
            elif not assignments:
                category = "C_NEVER_ASSIGNED_TO_ZONE"
            else:
                category = "OTHER_OUTSIDE_WINDOW"

            categories[category][row["alarm_type"]].append(
                (row["alarm_id"], row["lot_id"])
            )

        print("\n========== 2. ALARM_LOTS MISMATCH CLASSIFICATION ==========")
        print(f"Total mismatched alarm_lots rows: {len(mismatch_rows):,}")
        print("Window end used: alarm_lots.impact_end")
        print("Boundary rule: assignment start must be strictly before impact_end.")

        descriptions = {
            "A_VALID_LATER_OVERLAP":
                "A — Assigned after detected_at, before impact_end",
            "B_RELEASED_BEFORE_DETECTION":
                "B — Released at or before detected_at",
            "C_NEVER_ASSIGNED_TO_ZONE":
                "C — Never assigned to the alarm's zone",
            "OTHER_OUTSIDE_WINDOW":
                "OTHER — Assigned to zone, but none of A/B/C applies",
        }

        grand_total = 0

        for category, description in descriptions.items():
            grouped = categories[category]
            total = sum(len(items) for items in grouped.values())
            grand_total += total

            print(f"\n---------- {description} ----------")
            print(f"Total rows: {total:,}")

            if not grouped:
                print("No rows.")
                continue

            for alarm_type in sorted(grouped):
                pairs = grouped[alarm_type]
                print(f"\n{alarm_type}: {len(pairs):,} rows")
                print("Examples (alarm_id, lot_id):")
                for alarm_id, lot_id in pairs[:3]:
                    print(f"  {alarm_id} | {lot_id}")

        print("\n========== RECONCILIATION ==========")
        print(f"Sensor mismatches: {len(sensor_rows):,}")
        print(f"Lot mismatch rows: {len(mismatch_rows):,}")
        print(f"Classified lot rows: {grand_total:,}")
        print(
            "Classification totals match:",
            "YES" if grand_total == len(mismatch_rows) else "NO"
        )

        print("\n========== READ-ONLY CONFIRMATION ==========")
        print("No database writes performed.")
        print("No backup created.")
        print("No rows or tables changed.")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
