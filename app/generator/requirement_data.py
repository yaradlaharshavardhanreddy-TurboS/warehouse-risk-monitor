
"""Generate product storage requirements."""

import sqlite3

from app.database.database import DATABASE_PATH

REQUIREMENTS = [
    (
        "REQ-DAIRY",
        "DAIRY",
        2,
        8,
        30,
        70,
        48,
    ),
    (
        "REQ-PRODUCE",
        "PRODUCE",
        4,
        12,
        50,
        90,
        72,
    ),
    (
        "REQ-FROZEN",
        "FROZEN_FOOD",
        -25,
        -18,
        20,
        60,
        120,
    ),
    (
        "REQ-PHARMA",
        "PHARMA",
        2,
        8,
        30,
        60,
        24,
    ),
    (
        "REQ-ELECTRONICS",
        "ELECTRONICS",
        15,
        30,
        20,
        60,
        168,
    ),
]

EFFECTIVE_FROM = "2025-01-01 00:00:00"
CREATED_AT = "2026-01-01 00:00:00"


def generate_requirements():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        existing = cursor.execute(
            "SELECT COUNT(*) FROM storage_requirements"
        ).fetchone()[0]

        if existing:
            raise RuntimeError(
                "Storage requirements already exist. "
                "Generator stopped to prevent duplicates."
            )

        cursor.executemany(
            """
            INSERT INTO storage_requirements (
                requirement_id,
                product_type,
                min_temperature_c,
                max_temperature_c,
                min_humidity_pct,
                max_humidity_pct,
                max_dwell_hours,
                effective_from,
                effective_to,
                requirement_version,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)
            """,
            [
                (
                    requirement_id,
                    product_type,
                    min_temp,
                    max_temp,
                    min_humidity,
                    max_humidity,
                    max_dwell,
                    EFFECTIVE_FROM,
                    CREATED_AT,
                )
                for (
                    requirement_id,
                    product_type,
                    min_temp,
                    max_temp,
                    min_humidity,
                    max_humidity,
                    max_dwell,
                ) in REQUIREMENTS
            ],
        )

        connection.commit()

        print("Storage requirement generation successful!")
        print("Total requirements:", len(REQUIREMENTS))

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    generate_requirements()
