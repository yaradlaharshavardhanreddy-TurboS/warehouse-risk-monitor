from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MASTER_SEED = 20261022

# Keep generator seeds explicit so each data domain is reproducible.
GENERATOR_SEEDS = {
    "warehouses": MASTER_SEED,
    "zones": MASTER_SEED,
    "sensors": MASTER_SEED,
    "sensor_readings": MASTER_SEED,
    "inventory_lots": MASTER_SEED,
    "door_events": 20261023,
    "alarms": MASTER_SEED,
    "inspections": MASTER_SEED,
}

SCALE_PROFILES = {
    "starter": {
        "warehouses": 2,
        "zones": 20,
        "sensors": 100,
        "sensor_readings": 20000,
        "inventory_lots": 500,
    },
    "full": {
        "warehouses": 10,
        "zones": 100,
        "sensors": 500,
        "sensor_readings": 1000000,
        "inventory_lots": 10000,
    },
}


def get_scale_profile(name: str) -> dict:
    if name not in SCALE_PROFILES:
        raise ValueError(
            f"Unknown scale profile '{name}'. "
            f"Choose from: {', '.join(SCALE_PROFILES)}"
        )

    return SCALE_PROFILES[name].copy()


def get_generator_seed(generator_name: str) -> int:
    if generator_name not in GENERATOR_SEEDS:
        raise ValueError(
            f"Unknown generator: {generator_name}"
        )

    return GENERATOR_SEEDS[generator_name]


def create_rng(generator_name: str) -> random.Random:
    return random.Random(
        get_generator_seed(generator_name)
    )


def warehouse_id(number: int) -> str:
    return f"WH-{number:03d}"


def zone_id(warehouse_number: int, zone_number: int) -> str:
    return (
        f"ZN-{warehouse_number:03d}-{zone_number:02d}"
    )


def sensor_id(sensor_number: int) -> str:
    return f"SEN-{sensor_number:04d}"


def lot_id(lot_number: int) -> str:
    return f"LOT-2026-{lot_number:06d}"


def reading_id(sensor_identifier: str, timestamp: str) -> str:
    normalized = (
        timestamp.replace("-", "")
        .replace(":", "")
        .replace(" ", "T")
    )

    return f"RDG-{sensor_identifier}-{normalized}"


def build_configuration(profile_name: str) -> dict:
    return {
        "project": "Warehouse Risk Monitoring System",
        "master_seed": MASTER_SEED,
        "profile": profile_name,
        "scale": get_scale_profile(profile_name),
        "generator_seeds": GENERATOR_SEEDS,
        "id_formats": {
            "warehouse": "WH-{number:03d}",
            "zone": "ZN-{warehouse_number:03d}-{zone_number:02d}",
            "sensor": "SEN-{number:04d}",
            "inventory_lot": "LOT-2026-{number:06d}",
            "sensor_reading": "RDG-{sensor_id}-{normalized_timestamp}",
        },
        "reproducibility": {
            "fixed_seed": True,
            "stable_id_formats": True,
            "same_seed_same_random_sequence": True,
            "generator_integration_required": True,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Warehouse data generation configuration"
    )

    parser.add_argument(
        "--profile",
        choices=sorted(SCALE_PROFILES),
        default="full",
    )

    parser.add_argument(
        "--output",
        default="docs/phase10/generation_config.json",
    )

    args = parser.parse_args()

    config = build_configuration(args.profile)

    output_path = ROOT / args.output
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(config, file, indent=4)

    print("========== GENERATION CONFIGURATION ==========")
    print("Profile:", args.profile)
    print("Master seed:", MASTER_SEED)

    for entity, count in config["scale"].items():
        print(f"{entity}: {count:,}")

    print("\nGenerator seeds:")
    for name, seed in GENERATOR_SEEDS.items():
        print(f"{name}: {seed}")

    print("\nConfiguration written to:")
    print(output_path)


if __name__ == "__main__":
    main()