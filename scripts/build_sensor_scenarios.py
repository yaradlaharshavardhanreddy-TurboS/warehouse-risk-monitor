import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_DIR = ROOT / "docs" / "phase10"

SCENARIO_FILE = OUTPUT_DIR / "controlled_sensor_scenarios.csv"
GROUND_TRUTH_FILE = OUTPUT_DIR / "controlled_sensor_ground_truth.csv"
MANIFEST_FILE = OUTPUT_DIR / "controlled_sensor_manifest.json"


def stable_id(prefix, value):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        f"file:{DB_PATH.as_posix()}?mode=ro",
        uri=True,
    )
    conn.row_factory = sqlite3.Row

    try:
        sensors = conn.execute("""
            SELECT sensor_id
            FROM sensors
            ORDER BY sensor_id
        """).fetchall()

        zones = conn.execute("""
            SELECT zone_id
            FROM zones
            ORDER BY zone_id
        """).fetchall()

        date_range = conn.execute("""
            SELECT MIN(recorded_at), MAX(recorded_at)
            FROM sensor_readings
        """).fetchone()

        occupancy_sensor = conn.execute("""
            SELECT sensor_id
            FROM sensor_readings
            WHERE occupancy_count IS NOT NULL
            GROUP BY sensor_id
            ORDER BY sensor_id
            LIMIT 1
        """).fetchone()

        if len(sensors) < 4 or len(zones) < 2:
            raise RuntimeError(
                "At least four sensors and two zones are required."
            )

        if not date_range[0] or not occupancy_sensor:
            raise RuntimeError(
                "Reading date range or occupancy sensor is unavailable."
            )

        base_time = datetime.fromisoformat(date_range[0]) + timedelta(hours=12)

        # Select four distinct sensors deterministically.
        selected_sensors = [row["sensor_id"] for row in sensors[:4]]

        # Use a sensor with actual occupancy readings for the occupancy fixture.
        occupancy_sensor_id = occupancy_sensor["sensor_id"]

        if occupancy_sensor_id not in selected_sensors:
            selected_sensors[3] = occupancy_sensor_id

        # Find the existing active zone assignment for the first sensor.
        first_sensor = selected_sensors[0]

        current_assignment = conn.execute("""
            SELECT zone_id, effective_from
            FROM sensor_zone_assignments
            WHERE sensor_id = ?
              AND effective_to IS NULL
            ORDER BY effective_from DESC
            LIMIT 1
        """, (first_sensor,)).fetchone()

        if not current_assignment:
            raise RuntimeError(
                f"No active zone assignment found for {first_sensor}"
            )

        original_zone = current_assignment["zone_id"]

        alternative_zone = next(
            row["zone_id"]
            for row in zones
            if row["zone_id"] != original_zone
        )

        # Use an actual sensor zone for the other fixtures where possible.
        def get_sensor_zone(sensor_id):
            row = conn.execute("""
                SELECT zone_id
                FROM sensor_zone_assignments
                WHERE sensor_id = ?
                  AND effective_to IS NULL
                ORDER BY effective_from DESC
                LIMIT 1
            """, (sensor_id,)).fetchone()

            return row["zone_id"] if row else zones[0]["zone_id"]

        reading_sensor = selected_sensors[1]
        outage_sensor = selected_sensors[2]

        reading_zone = get_sensor_zone(reading_sensor)
        outage_zone = get_sensor_zone(outage_sensor)
        occupancy_zone = get_sensor_zone(occupancy_sensor_id)

        t0 = base_time
        t1 = base_time + timedelta(minutes=20)
        t2 = base_time + timedelta(minutes=30)

        scenarios = [
            {
                "scenario_id": "SYN-SENSOR-001",
                "issue_type": "SENSOR_ASSIGNED_TO_MULTIPLE_ZONES",
                "entity_type": "SENSOR",
                "sensor_id": first_sensor,
                "zone_id": original_zone,
                "related_zone_id": alternative_zone,
                "event_start": t0.isoformat(sep=" "),
                "event_end": t2.isoformat(sep=" "),
                "previous_reading_at": "",
                "next_reading_at": "",
                "gap_seconds": "",
                "occupancy_count": "",
                "occupancy_limit": "",
                "scenario_origin": "CONTROLLED_SYNTHETIC",
                "evidence": (
                    f"Existing assignment to {original_zone} overlaps "
                    f"a synthetic assignment to {alternative_zone} "
                    f"from {t0} to {t2}."
                ),
            },
            {
                "scenario_id": "SYN-SENSOR-002",
                "issue_type": "SENSOR_READING_GAP",
                "entity_type": "SENSOR",
                "sensor_id": reading_sensor,
                "zone_id": reading_zone,
                "related_zone_id": "",
                "event_start": t0.isoformat(sep=" "),
                "event_end": t1.isoformat(sep=" "),
                "previous_reading_at": t0.isoformat(sep=" "),
                "next_reading_at": t1.isoformat(sep=" "),
                "gap_seconds": 1200,
                "occupancy_count": "",
                "occupancy_limit": "",
                "scenario_origin": "CONTROLLED_SYNTHETIC",
                "evidence": (
                    "Synthetic consecutive reading interval is 1200 seconds, "
                    "exceeding the 900-second threshold."
                ),
            },
            {
                "scenario_id": "SYN-SENSOR-003",
                "issue_type": "SENSOR_OUTAGE",
                "entity_type": "SENSOR",
                "sensor_id": outage_sensor,
                "zone_id": outage_zone,
                "related_zone_id": "",
                "event_start": t0.isoformat(sep=" "),
                "event_end": t2.isoformat(sep=" "),
                "previous_reading_at": "",
                "next_reading_at": "",
                "gap_seconds": 1800,
                "occupancy_count": "",
                "occupancy_limit": "",
                "scenario_origin": "CONTROLLED_SYNTHETIC",
                "evidence": (
                    "Synthetic sensor outage lasting 1800 seconds. "
                    "No outage row was inserted into the source database."
                ),
            },
            {
                "scenario_id": "SYN-SENSOR-004",
                "issue_type": "OCCUPANCY_THRESHOLD_BREACH",
                "entity_type": "SENSOR",
                "sensor_id": occupancy_sensor_id,
                "zone_id": occupancy_zone,
                "related_zone_id": "",
                "event_start": t0.isoformat(sep=" "),
                "event_end": "",
                "previous_reading_at": "",
                "next_reading_at": "",
                "gap_seconds": "",
                "occupancy_count": 65,
                "occupancy_limit": 50,
                "scenario_origin": "CONTROLLED_SYNTHETIC",
                "evidence": (
                    "Synthetic occupancy count of 65 exceeds the "
                    "fixture-specific configured limit of 50."
                ),
            },
        ]

    finally:
        conn.close()

    scenario_fields = list(scenarios[0].keys())
    write_csv(SCENARIO_FILE, scenarios, scenario_fields)

    ground_truth = []

    for scenario in scenarios:
        ground_truth.append({
            "ground_truth_id": stable_id(
                "GT", scenario["scenario_id"]
            ),
            "issue_type": scenario["issue_type"],
            "entity_type": scenario["entity_type"],
            "entity_id": scenario["sensor_id"],
            "detected_at": scenario["event_start"],
            "zone_id": scenario["zone_id"],
            "related_zone_id": scenario["related_zone_id"],
            "scenario_id": scenario["scenario_id"],
            "scenario_origin": "CONTROLLED_SYNTHETIC",
            "label_status": "CONFIRMED_SYNTHETIC",
            "evidence": scenario["evidence"],
        })

    ground_truth_fields = list(ground_truth[0].keys())
    write_csv(
        GROUND_TRUTH_FILE,
        ground_truth,
        ground_truth_fields,
    )

    manifest = {
        "phase": "10.4",
        "project": "Warehouse Risk Monitoring System",
        "scenario_count": len(scenarios),
        "scenario_origin": "CONTROLLED_SYNTHETIC",
        "source_database": str(DB_PATH.relative_to(ROOT)),
        "source_database_modified": False,
        "scenarios": [
            {
                "scenario_id": row["scenario_id"],
                "issue_type": row["issue_type"],
                "sensor_id": row["sensor_id"],
                "zone_id": row["zone_id"],
            }
            for row in scenarios
        ],
        "files": [
            str(SCENARIO_FILE.relative_to(ROOT)),
            str(GROUND_TRUTH_FILE.relative_to(ROOT)),
        ],
    }

    with MANIFEST_FILE.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4)

    print("========== CONTROLLED SENSOR SCENARIOS ==========")

    for row in scenarios:
        print(
            row["scenario_id"],
            "|",
            row["issue_type"],
            "| Sensor:",
            row["sensor_id"],
            "| Zone:",
            row["zone_id"],
        )

    print("\nScenario records:", len(scenarios))
    print("Ground-truth records:", len(ground_truth))
    print("Source database modified: NO")

    print("\nGenerated files:")
    print(SCENARIO_FILE)
    print(GROUND_TRUTH_FILE)
    print(MANIFEST_FILE)

    print("\nPHASE 10.4 SCENARIO GENERATION PASSED.")


if __name__ == "__main__":
    main()
