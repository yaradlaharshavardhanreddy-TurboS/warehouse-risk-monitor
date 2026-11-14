import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB = Path("data/warehouse_monitor.db").resolve()
DATASET_END = datetime.fromisoformat(
    "2026-10-29T00:05:10+00:00"
)
WINDOW_HOURS = 6

def parse_dt(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def fmt(dt):
    return dt.isoformat(timespec="seconds")

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

def stats(conn, rows, title):
    total_lots = conn.execute(
        "SELECT COUNT(*) FROM inventory_lots"
    ).fetchone()[0]
    total_alarms = conn.execute(
        "SELECT COUNT(*) FROM alarms"
    ).fetchone()[0]

    unique_lots = len({r[1] for r in rows})
    links = len(rows)
    percentage = unique_lots * 100 / total_lots if total_lots else 0
    average = links / total_alarms if total_alarms else 0

    linked_alarm_ids = {r[0] for r in rows}
    alarm_types = conn.execute("""
        SELECT alarm_id, alarm_type FROM alarms
    """).fetchall()

    zero_by_type = {}
    for alarm_id, alarm_type in alarm_types:
        if alarm_id not in linked_alarm_ids:
            zero_by_type[alarm_type] = zero_by_type.get(alarm_type, 0) + 1

    print(f"\n========== {title} ==========")
    print(f"Total links:                 {links:,}")
    print(f"Unique affected lots:        {unique_lots:,} / {total_lots:,}")
    print(f"Affected lots percentage:   {percentage:.2f}%")
    print(f"Average links per alarm:     {average:.2f}")
    print(f"Alarms with zero links:      {sum(zero_by_type.values()):,}")
    print("Zero-link alarms by type:")
    for alarm_type in sorted(TYPE_MAP):
        print(f"  {alarm_type:<28} {zero_by_type.get(alarm_type, 0):,}")

def main():
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        print("Reading current alarm_lots...")
        old_rows = conn.execute("""
            SELECT alarm_id, lot_id, impact_type,
                   impact_start, impact_end, impact_details
            FROM alarm_lots
        """).fetchall()

        stats(conn, old_rows, "BEFORE REBUILD — CURRENT LINKS")

        alarms = conn.execute("""
            SELECT alarm_id, zone_id, alarm_type, detected_at
            FROM alarms
        """).fetchall()

        assignments = conn.execute("""
            SELECT lot_id, zone_id, assigned_at, released_at
            FROM lot_zone_assignments
        """).fetchall()

        assignments_by_zone = {}
        for lot_id, zone_id, assigned_at, released_at in assignments:
            assignments_by_zone.setdefault(zone_id, []).append(
                (lot_id, parse_dt(assigned_at), parse_dt(released_at))
            )

        candidate = set()

        for alarm_id, zone_id, alarm_type, detected_at in alarms:
            start = parse_dt(detected_at)

            if start is None or start >= DATASET_END:
                continue

            # No use of resolved_at. Six-hour fallback, capped at dataset end.
            end = min(start + timedelta(hours=WINDOW_HOURS), DATASET_END)

            if end <= start:
                continue

            impact_type = TYPE_MAP.get(alarm_type, "OTHER")

            for lot_id, lot_start, lot_end in assignments_by_zone.get(zone_id, []):
                if lot_start is None:
                    continue

                # Same zone is guaranteed by assignments_by_zone.
                # Half-open overlap: lot_start < alarm_end AND lot_end > alarm_start.
                if lot_start >= end:
                    continue
                if lot_end is not None and lot_end <= start:
                    continue

                overlap_start = max(start, lot_start)
                overlap_end = min(end, lot_end) if lot_end else end

                if overlap_start >= overlap_end:
                    continue

                details = (
                    f"Same-zone temporal overlap; zone_id={zone_id}; "
                    f"alarm_window={fmt(start)} to {fmt(end)}; "
                    f"lot_stay={fmt(lot_start)} to "
                    f"{fmt(lot_end) if lot_end else 'OPEN'}; "
                    f"window_rule=detected_at_plus_6_hours_capped_at_dataset_end"
                )

                candidate.add((
                    alarm_id,
                    lot_id,
                    impact_type,
                    fmt(overlap_start),
                    fmt(overlap_end),
                    details,
                ))

        candidate = sorted(candidate, key=lambda r: (r[0], r[1], r[3]))

        stats(conn, candidate, "PROPOSED LINKS — BEFORE ANY MODIFICATION")

        print("\nCandidate link count:", f"{len(candidate):,}")
        print("Existing link count: ", f"{len(old_rows):,}")

        if not candidate:
            print("\nNo candidate links generated. Database left unchanged.")
            return

        if len(candidate) > max(100, len(old_rows) * 3):
            print(
                "\nWARNING: Proposed link count is more than three times "
                "the existing count. Database left unchanged."
            )
            return

        approval = input(
            "\nReview the proposed statistics above. "
            "Type APPLY to back up and replace alarm_lots: "
        ).strip()

        if approval != "APPLY":
            print("Not approved. Database left unchanged.")
            return

        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"warehouse_monitor_pre_alarm_lots_{stamp}.db"

        # Backup is completed before any database modification.
        backup_conn = sqlite3.connect(backup)
        try:
            conn.backup(backup_conn)
        finally:
            backup_conn.close()

        print(f"\nBackup created: {backup.resolve()}")

        try:
            conn.execute("BEGIN IMMEDIATE")

            conn.execute("DELETE FROM alarm_lots")

            conn.executemany("""
                INSERT INTO alarm_lots (
                    alarm_id,
                    lot_id,
                    impact_type,
                    impact_start,
                    impact_end,
                    impact_details
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, candidate)

            fk_errors = conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if fk_errors:
                raise RuntimeError(
                    f"Foreign-key violations before commit: {fk_errors[:10]}"
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        final_rows = conn.execute("""
            SELECT alarm_id, lot_id, impact_type,
                   impact_start, impact_end, impact_details
            FROM alarm_lots
        """).fetchall()

        stats(conn, final_rows, "AFTER REBUILD — FINAL LINKS")

        print("\n========== DATABASE INTEGRITY ==========")
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        for row in integrity:
            print(row[0])

        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("\nForeign-key violations:", len(fk_errors))
        for row in fk_errors[:20]:
            print(row)

        if len(final_rows) != len(candidate):
            print("ERROR: Final row count differs from candidate count.")

        print("\nRebuild completed.")
        print("Alarms table was not modified.")
        print("Only alarm_lots rows were replaced.")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
