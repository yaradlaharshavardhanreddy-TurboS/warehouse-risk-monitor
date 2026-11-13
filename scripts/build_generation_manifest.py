from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_PATH = ROOT / "docs" / "phase10" / "generation_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )

    try:
        tables = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        table_counts = {}

        for (table_name,) in tables:
            # Table names originate from sqlite_master.
            quoted_name = '"' + table_name.replace('"', '""') + '"'

            count = conn.execute(
                f"SELECT COUNT(*) FROM {quoted_name}"
            ).fetchone()[0]

            table_counts[table_name] = count

        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_key_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if integrity != "ok":
            raise RuntimeError(
                f"Database integrity failure: {integrity}"
            )

        if foreign_key_errors:
            raise RuntimeError(
                f"Foreign-key violations: {len(foreign_key_errors)}"
            )

    finally:
        conn.close()

    manifest = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "database": "data/warehouse_monitor.db",
        "database_sha256": sha256_file(DB_PATH),
        "database_size_bytes": DB_PATH.stat().st_size,
        "master_seed": 20261022,
        "table_counts": table_counts,
        "total_tables": len(table_counts),
        "database_integrity": integrity,
        "foreign_key_violations": len(foreign_key_errors),
        "source_database_modified": False,
        "note": (
            "This is a baseline manifest. It does not claim "
            "that the existing generators have been unified "
            "or that two full regenerations have been compared."
        ),
    }

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(manifest, file, indent=4)

    print("========== GENERATION BASELINE MANIFEST ==========")
    print("Tables:", len(table_counts))

    for table, count in table_counts.items():
        print(f"{table}: {count:,}")

    print("\nDatabase SHA-256:")
    print(manifest["database_sha256"])

    print("\nManifest:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()