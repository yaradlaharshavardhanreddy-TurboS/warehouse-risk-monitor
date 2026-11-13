from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
PHASE_DIR = ROOT / "docs" / "phase10"

EXPECTED_TABLE_COUNTS = {
    "warehouses": 10,
    "zones": 100,
    "sensors": 500,
    "sensor_readings": 1_000_000,
    "inventory_lots": 10_000,
    "sensor_zone_assignments": 500,
    "sensor_outages": 0,
}

EXPECTED_SENSOR_SCENARIOS = {
    "SENSOR_ASSIGNED_TO_MULTIPLE_ZONES",
    "SENSOR_READING_GAP",
    "SENSOR_OUTAGE",
    "OCCUPANCY_THRESHOLD_BREACH",
}


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print(f"PASS: {message}")


def read_csv(path):
    check(path.exists(), f"File exists: {path.relative_to(ROOT)}")

    with path.open(
        "r",
        newline="",
        encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def validate_database():
    print("\n========== DATABASE VALIDATION ==========")

    check(DB_PATH.exists(), "Source database exists")

    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )

    try:
        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        check(
            integrity == "ok",
            "SQLite integrity check"
        )

        foreign_key_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        check(
            len(foreign_key_errors) == 0,
            "No foreign-key violations"
        )

        tables = {
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
            """)
        }

        check(
            len(tables) == 15,
            f"Expected 15 tables; found {len(tables)}"
        )

        for table, expected_count in EXPECTED_TABLE_COUNTS.items():
            check(
                table in tables,
                f"Required table exists: {table}"
            )

            quoted = '"' + table.replace('"', '""') + '"'

            actual_count = conn.execute(
                f"SELECT COUNT(*) FROM {quoted}"
            ).fetchone()[0]

            check(
                actual_count == expected_count,
                f"{table}: expected {expected_count:,}, found {actual_count:,}"
            )

        return tables

    finally:
        conn.close()


def validate_data_dictionary(tables):
    print("\n========== DATA DICTIONARY VALIDATION ==========")

    dictionary_path = PHASE_DIR / "data_dictionary.json"
    check(
        dictionary_path.exists(),
        "Data dictionary JSON exists"
    )

    with dictionary_path.open(encoding="utf-8") as file:
        dictionary = json.load(file)

    # Support either a direct table mapping or a tables wrapper.
    documented_tables = dictionary.get(
        "tables",
        dictionary
    )

    if isinstance(documented_tables, list):
        documented_names = {
            item.get("table_name", item.get("name"))
            for item in documented_tables
        }
    else:
        documented_names = set(documented_tables.keys())

    check(
        tables.issubset(documented_names),
        "Every database table appears in the data dictionary"
    )

    for filename in (
        "data_dictionary.csv",
        "data_dictionary.md",
    ):
        check(
            (PHASE_DIR / filename).exists(),
            f"Data dictionary file exists: {filename}"
        )


def validate_sensor_scenarios():
    print("\n========== CONTROLLED SENSOR SCENARIOS ==========")

    scenario_path = PHASE_DIR / "controlled_sensor_scenarios.csv"
    truth_path = PHASE_DIR / "controlled_sensor_ground_truth.csv"
    manifest_path = PHASE_DIR / "controlled_sensor_manifest.json"

    scenarios = read_csv(scenario_path)
    truth = read_csv(truth_path)

    check(
        len(scenarios) == 4,
        f"Expected 4 controlled scenarios; found {len(scenarios)}"
    )

    check(
        len(truth) == 4,
        f"Expected 4 ground-truth records; found {len(truth)}"
    )

    scenario_types = {
        row.get("issue_type")
        for row in scenarios
    }

    check(
        EXPECTED_SENSOR_SCENARIOS.issubset(scenario_types),
        "All four expected sensor scenario types exist"
    )

    for row in scenarios:
        check(
            row.get("scenario_origin") == "CONTROLLED_SYNTHETIC",
            f"{row.get('scenario_id')} has synthetic origin"
        )

    truth_types = {
        row.get("issue_type")
        for row in truth
    }

    check(
        EXPECTED_SENSOR_SCENARIOS.issubset(truth_types),
        "Ground truth contains all four scenario types"
    )

    for row in truth:
        check(
            row.get("label_status") == "CONFIRMED_SYNTHETIC",
            f"{row.get('scenario_id')} has confirmed synthetic label"
        )

    check(
        manifest_path.exists(),
        "Controlled sensor manifest exists"
    )

    with manifest_path.open(encoding="utf-8") as file:
        json.load(file)

    print("PASS: Controlled sensor manifest is valid JSON")


def validate_ground_truth():
    print("\n========== ORIGINAL GROUND TRUTH ==========")

    path = PHASE_DIR / "ground_truth.csv"
    rows = read_csv(path)

    print(
        "PASS: Original ground-truth dataset may be empty "
        "when no qualifying anomalies exist"
    )

    check(
        all(row.get("issue_type") for row in rows),
        "Every original ground-truth row has an issue type"
    )

    print("Original ground-truth records:", len(rows))

    counts = Counter(
        row["issue_type"]
        for row in rows
    )

    for issue_type, count in sorted(counts.items()):
        print(f"{issue_type}: {count}")


def validate_remediation_report():
    print("\n========== REMEDIATION TRACEABILITY ==========")

    csv_path = PHASE_DIR / "remediation_traceability.csv"
    json_path = PHASE_DIR / "remediation_traceability_summary.json"

    rows = read_csv(csv_path)

    check(
        len(rows) > 0,
        "Remediation traceability report is not empty"
    )

    required_columns = {
        "alarm_id",
        "lot_id",
        "inspection_count",
        "remediation_count",
        "inventory_link_status",
        "remediation_status",
    }

    check(
        required_columns.issubset(rows[0].keys()),
        "Remediation report contains required columns"
    )

    check(
        json_path.exists(),
        "Remediation summary JSON exists"
    )

    with json_path.open(encoding="utf-8") as file:
        summary = json.load(file)

    check(
        summary.get("source_database_modified") is False,
        "Remediation report confirms source database was not modified"
    )


def validate_generation_configuration():
    print("\n========== GENERATION CONFIGURATION ==========")

    config_path = PHASE_DIR / "generation_config.json"
    manifest_path = PHASE_DIR / "generation_manifest.json"

    check(
        config_path.exists(),
        "Generation configuration exists"
    )

    check(
        manifest_path.exists(),
        "Generation manifest exists"
    )

    with config_path.open(encoding="utf-8") as file:
        config = json.load(file)

    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    check(
        config.get("master_seed") == 20261022,
        "Master seed is 20261022"
    )

    check(
        config.get("profile") in {"starter", "full"},
        "Generation profile is valid"
    )

    check(
        manifest.get("database_integrity") == "ok",
        "Generation manifest records valid database integrity"
    )

    check(
        manifest.get("foreign_key_violations") == 0,
        "Generation manifest records zero foreign-key violations"
    )


def validate_source_manifest():
    print("\n========== SOURCE MANIFEST ==========")

    path = PHASE_DIR / "source_manifest.json"

    check(
        path.exists(),
        "Source manifest exists"
    )

    with path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    check(
        isinstance(manifest, dict),
        "Source manifest is valid JSON object"
    )


def main():
    print("========== PHASE 10 COMPREHENSIVE VALIDATION ==========")

    tables = validate_database()
    validate_data_dictionary(tables)
    validate_sensor_scenarios()
    validate_ground_truth()
    validate_remediation_report()
    validate_generation_configuration()
    validate_source_manifest()

    print("\n========== PHASE 10 VALIDATION RESULT ==========")
    print("All Phase 10 validation checks passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nPHASE 10 VALIDATION FAILED")
        print(f"Reason: {exc}")
        sys.exit(1)
