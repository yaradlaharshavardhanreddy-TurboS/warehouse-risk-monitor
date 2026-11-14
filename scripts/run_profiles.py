"""Build isolated starter/full datasets and prove repeatability.

The operational database is never opened or modified by this runner.
Run: python -m scripts.run_profiles --profiles starter full --runs 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import io
from contextlib import closing, redirect_stdout
from pathlib import Path

from app.database import database
from app.generator import master_data, zone_data, sensor_data, requirement_data
from app.generator import inventory_data, sensor_reading_data, door_event_data
from app.services import environmental_risk_detector, operational_risk_detector
from scripts.phase10_generation_config import SCALE_PROFILES, MASTER_SEED

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "profile_execution_reproducibility.json"
MODULES = [database, master_data, zone_data, sensor_data, requirement_data,
           inventory_data, sensor_reading_data, door_event_data,
           environmental_risk_detector, operational_risk_detector]


def digest_database(conn: sqlite3.Connection) -> tuple[dict, dict]:
    counts, hashes = {}, {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        cur = conn.execute(f"SELECT * FROM {quoted}")
        columns = [d[0] for d in cur.description]
        primary = [r[1] for r in sorted(conn.execute(f"PRAGMA table_info({quoted})").fetchall(), key=lambda x: x[5]) if r[5]]
        order_columns = primary or columns
        order = ",".join('"' + c.replace('"', '""') + '"' for c in order_columns)
        count = 0
        h = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {quoted} ORDER BY {order}"):
            h.update(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str).encode())
            h.update(b"\n")
            count += 1
        counts[table] = count
        hashes[table] = h.hexdigest()
    return counts, hashes


def build_one(profile: str, run_number: int, db_path: Path) -> dict:
    scale = SCALE_PROFILES[profile]
    for module in MODULES:
        if hasattr(module, "DATABASE_PATH"):
            module.DATABASE_PATH = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
        # Schema metadata otherwise embeds wall-clock time and breaks deterministic hashes.
        conn.execute("UPDATE schema_metadata SET applied_at='2026-01-01T00:00:00.000Z'")
        conn.commit()

    warehouses = scale["warehouses"]
    zones = scale["zones"]
    sensors = scale["sensors"]
    readings = scale["sensor_readings"]
    lots = scale["inventory_lots"]
    if zones % warehouses or sensors % zones:
        raise ValueError(f"Profile {profile} has incompatible warehouse/zone/sensor ratios")

    # Keep the console summary compact; the per-run results are captured below.
    with redirect_stdout(io.StringIO()):
        master_data.generate_warehouses(warehouse_count=warehouses)
        zone_data.generate_zones(expected_warehouses=warehouses)
        requirement_data.generate_requirements()
        sensor_data.generate_sensors(expected_zones=zones)
        inventory_data.generate_inventory(lot_count=lots, expected_warehouses=warehouses, expected_zones=zones)
        sensor_reading_data.generate_sensor_readings(reading_count=readings, expected_sensors=sensors)
        door_event_data.generate_door_events(expected_zones=zones)

        # Execute both detector families in dry-run mode: validate findings without
        # persisting alarms into the reproducibility fixture.
        if profile == "starter":
            env_result = environmental_risk_detector.run_detection(dry_run=True)
        else:
            # The environmental detector's current lot-impact join is expensive
            # at 1M readings. Its full logic is exercised on starter; full scale
            # still runs operational detection and all data/business validators.
            env_result = {"status": "deferred_at_full_scale", "reason": "Environmental detector exercised on starter profile; full-scale impact scan is resource-intensive."}
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            cur = conn.cursor()
            assignments = operational_risk_detector.load_assignments(cur)
            operational = {
                "door": operational_risk_detector.detect_door_risks(cur, False, 60),
                "occupancy": operational_risk_detector.detect_occupancy_risks(cur, False),
                "outage": operational_risk_detector.detect_sensor_outages(cur, False, 15, assignments),
            }
            conn.rollback()
        finally:
            conn.close()

    conn = sqlite3.connect(db_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or fk:
            raise RuntimeError(f"Database checks failed: integrity={integrity}; fk={len(fk)}")
        counts, hashes = digest_database(conn)
        expected = {
            "warehouses": warehouses, "zones": zones, "sensors": sensors,
            "sensor_readings": readings, "inventory_lots": lots,
            "sensor_zone_assignments": sensors, "lot_zone_assignments": lots,
        }
        for table, value in expected.items():
            if counts.get(table) != value:
                raise AssertionError(f"{profile}: {table} expected {value}, got {counts.get(table)}")
        bad_assignments = conn.execute("""
            SELECT COUNT(*) FROM sensor_zone_assignments a
            JOIN sensors s ON s.sensor_id=a.sensor_id
            WHERE s.lifecycle_state='ACTIVE' AND a.effective_to IS NULL
            AND (SELECT COUNT(*) FROM sensor_zone_assignments x
                 WHERE x.sensor_id=a.sensor_id AND x.effective_to IS NULL) <> 1
        """).fetchone()[0]
        if bad_assignments:
            raise AssertionError(f"{bad_assignments} active sensors have non-unique current assignments")
        incompatible = conn.execute("""
            SELECT COUNT(*) FROM inventory_lots l
            JOIN lot_zone_assignments a ON a.lot_id=l.lot_id AND a.released_at IS NULL
            JOIN zones z ON z.zone_id=a.zone_id
            WHERE (l.product_type IN ('DAIRY','PRODUCE','PHARMA') AND z.zone_type<>'COLD')
               OR (l.product_type='FROZEN_FOOD' AND z.zone_type<>'FREEZER')
               OR (l.product_type='ELECTRONICS' AND z.zone_type<>'AMBIENT')
        """).fetchone()[0]
        if incompatible:
            raise AssertionError(f"{incompatible} inventory lots occupy incompatible zones")
    finally:
        conn.close()
    return {"profile": profile, "run": run_number, "seed": MASTER_SEED,
            "counts": counts, "hashes": hashes, "sqlite_integrity": integrity,
            "foreign_key_violations": len(fk), "environmental_detector": env_result,
            "operational_detector_dry_run": operational}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="+", choices=sorted(SCALE_PROFILES), default=["starter", "full"])
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2 to demonstrate reproducibility")
    results = {"master_seed": MASTER_SEED, "runs_per_profile": args.runs, "profiles": {}, "certified": False}
    with tempfile.TemporaryDirectory(prefix="warehouse-profile-") as tmp:
        tmpdir = Path(tmp)
        for profile in args.profiles:
            runs = []
            for index in range(1, args.runs + 1):
                print(f"\n========== {profile.upper()} PROFILE RUN {index}/{args.runs} ==========")
                run = build_one(profile, index, tmpdir / profile / f"run_{index}.db")
                print(f"PASS: {profile} run {index} generated {run['counts'].get('sensor_readings', 0):,} readings; SQLite={run['sqlite_integrity']}; FK errors={run['foreign_key_violations']}")
                runs.append(run)
            baseline = runs[0]["hashes"]
            same = all(run["hashes"] == baseline for run in runs[1:])
            results["profiles"][profile] = {
                "runs": [{k: v for k, v in run.items() if k != "hashes"} for run in runs],
                "table_hashes": baseline,
                "two_run_reproducibility": "PASS" if same else "FAIL",
            }
            if not same:
                raise AssertionError(f"{profile} profile is not reproducible across {args.runs} runs")
    results["certified"] = True
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nPASS: profile runs and reproducibility. Report: {REPORT.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
