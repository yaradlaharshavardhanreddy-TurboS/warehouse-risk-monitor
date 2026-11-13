import csv
import json
import random
import sqlite3
from pathlib import Path

import pytest

from scripts.phase10_generation_config import (
    MASTER_SEED,
    GENERATOR_SEEDS,
    SCALE_PROFILES,
    get_scale_profile,
    get_generator_seed,
    create_rng,
    warehouse_id,
    zone_id,
    sensor_id,
    lot_id,
    reading_id,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
PHASE_DIR = ROOT / "docs" / "phase10"


def test_master_seed_is_fixed():
    assert MASTER_SEED == 20261022


def test_generator_seeds_are_defined():
    required = {
        "warehouses",
        "zones",
        "sensors",
        "sensor_readings",
        "inventory_lots",
        "door_events",
        "alarms",
        "inspections",
    }

    assert required.issubset(GENERATOR_SEEDS)


def test_generator_random_sequences_are_deterministic():
    first = create_rng("sensor_readings")
    second = create_rng("sensor_readings")

    assert [
        first.randint(1, 100000)
        for _ in range(10)
    ] == [
        second.randint(1, 100000)
        for _ in range(10)
    ]


def test_scale_profiles():
    assert get_scale_profile("starter") == SCALE_PROFILES["starter"]
    assert get_scale_profile("full") == SCALE_PROFILES["full"]


def test_invalid_scale_profile():
    with pytest.raises(ValueError):
        get_scale_profile("invalid")


def test_generator_seed_lookup():
    assert get_generator_seed("door_events") == 20261023

    with pytest.raises(ValueError):
        get_generator_seed("unknown")


def test_deterministic_id_formats():
    assert warehouse_id(1) == "WH-001"
    assert zone_id(1, 1) == "ZN-001-01"
    assert sensor_id(1) == "SEN-0001"
    assert lot_id(1) == "LOT-2026-000001"


def test_reading_id_format():
    result = reading_id(
        "SEN-0001",
        "2026-10-22 12:00:00"
    )

    assert result == "RDG-SEN-0001-20261022T120000"


def test_database_exists():
    assert DB_PATH.exists()


def test_database_integrity():
    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )

    try:
        result = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        assert result == "ok"

    finally:
        conn.close()


def test_database_foreign_keys():
    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )

    try:
        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert violations == []

    finally:
        conn.close()


def test_expected_source_table_counts():
    expected = {
        "warehouses": 10,
        "zones": 100,
        "sensors": 500,
        "sensor_readings": 1_000_000,
        "inventory_lots": 10_000,
    }

    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )

    try:
        for table, count in expected.items():
            actual = conn.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

            assert actual == count

    finally:
        conn.close()


def test_controlled_scenario_files_exist():
    assert (
        PHASE_DIR / "controlled_sensor_scenarios.csv"
    ).exists()

    assert (
        PHASE_DIR / "controlled_sensor_ground_truth.csv"
    ).exists()

    assert (
        PHASE_DIR / "controlled_sensor_manifest.json"
    ).exists()


def test_controlled_scenario_types():
    path = PHASE_DIR / "controlled_sensor_scenarios.csv"

    with path.open(
        newline="",
        encoding="utf-8"
    ) as file:
        rows = list(csv.DictReader(file))

    expected = {
        "SENSOR_ASSIGNED_TO_MULTIPLE_ZONES",
        "SENSOR_READING_GAP",
        "SENSOR_OUTAGE",
        "OCCUPANCY_THRESHOLD_BREACH",
    }

    actual = {
        row["issue_type"]
        for row in rows
    }

    assert expected.issubset(actual)


def test_controlled_ground_truth_labels():
    path = PHASE_DIR / "controlled_sensor_ground_truth.csv"

    with path.open(
        newline="",
        encoding="utf-8"
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 4

    for row in rows:
        assert row["label_status"] == "CONFIRMED_SYNTHETIC"


def test_generation_config_is_valid_json():
    path = PHASE_DIR / "generation_config.json"

    with path.open(encoding="utf-8") as file:
        config = json.load(file)

    assert config["master_seed"] == MASTER_SEED
    assert config["profile"] in {"starter", "full"}


def test_generation_manifest_is_valid_json():
    path = PHASE_DIR / "generation_manifest.json"

    with path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    assert manifest["database_integrity"] == "ok"
    assert manifest["foreign_key_violations"] == 0