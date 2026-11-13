from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
PHASE_DIR = ROOT / "docs" / "phase10"

REPORT_PATH = PHASE_DIR / "final_submission_report.json"
README_PATH = PHASE_DIR / "README_PHASE10.md"
CHECKLIST_PATH = PHASE_DIR / "submission_checklist.md"


EXPECTED_FILES = [
    "data_dictionary.json",
    "data_dictionary.csv",
    "data_dictionary.md",
    "ground_truth.csv",
    "anomaly_catalog.md",
    "source_manifest.json",
    "controlled_sensor_scenarios.csv",
    "controlled_sensor_ground_truth.csv",
    "controlled_sensor_manifest.json",
    "remediation_traceability.csv",
    "remediation_traceability_summary.json",
    "generation_config.json",
    "generation_manifest.json",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(path: Path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def inspect_database():
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    conn = sqlite3.connect(
        f"file:{DB_PATH.resolve()}?mode=ro",
        uri=True
    )

    try:
        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        table_rows = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        counts = {}

        for (table_name,) in table_rows:
            quoted = '"' + table_name.replace('"', '""') + '"'
            counts[table_name] = conn.execute(
                f"SELECT COUNT(*) FROM {quoted}"
            ).fetchone()[0]

        return {
            "integrity": integrity,
            "foreign_key_violations": len(fk_errors),
            "table_count": len(counts),
            "table_counts": counts,
        }

    finally:
        conn.close()


def inspect_files():
    results = []

    for filename in EXPECTED_FILES:
        path = PHASE_DIR / filename

        results.append({
            "file": f"docs/phase10/{filename}",
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "sha256": sha256_file(path) if path.is_file() else None,
        })

    return results


def inspect_ground_truth():
    path = PHASE_DIR / "ground_truth.csv"

    if not path.exists():
        return {
            "exists": False,
            "record_count": 0,
            "issue_types": {},
        }

    with path.open(
        newline="",
        encoding="utf-8"
    ) as file:
        rows = list(csv.DictReader(file))

    issue_types = {}

    for row in rows:
        issue_type = row.get("issue_type", "UNKNOWN")
        issue_types[issue_type] = (
            issue_types.get(issue_type, 0) + 1
        )

    return {
        "exists": True,
        "record_count": len(rows),
        "issue_types": issue_types,
    }


def build_readme_addendum(database, files, ground_truth):
    lines = [
        "# Phase 10 — Data Quality and Submission Documentation",
        "",
        "## Overview",
        "",
        "Phase 10 adds data-quality documentation, controlled synthetic "
        "anomaly scenarios, inventory traceability reporting, generation "
        "configuration, and automated validation for the Warehouse Risk "
        "Monitoring System.",
        "",
        "## Database baseline",
        "",
        f"- Database: `data/warehouse_monitor.db`",
        f"- Tables: {database['table_count']}",
        f"- SQLite integrity: `{database['integrity']}`",
        f"- Foreign-key violations: {database['foreign_key_violations']}",
        "",
        "### Table row counts",
        "",
        "| Table | Records |",
        "|---|---:|",
    ]

    for table, count in sorted(database["table_counts"].items()):
        lines.append(f"| `{table}` | {count:,} |")

    lines.extend([
        "",
        "## Ground truth",
        "",
        f"- Original ground-truth records: {ground_truth['record_count']}",
        "",
        "| Issue type | Records |",
        "|---|---:|",
    ])

    for issue_type, count in sorted(
        ground_truth["issue_types"].items()
    ):
        lines.append(f"| `{issue_type}` | {count} |")

    lines.extend([
        "",
        "## Controlled synthetic scenarios",
        "",
        "The controlled sensor scenario dataset includes:",
        "",
        "- Sensor assigned to multiple zones",
        "- Sensor reading gap",
        "- Sensor outage",
        "- Occupancy threshold breach",
        "",
        "These records are labelled as controlled synthetic scenarios "
        "and are kept separate from the source database.",
        "",
        "## Generated reports",
        "",
        "- `data_dictionary.md` — schema documentation",
        "- `ground_truth.csv` — labelled source-data anomaly records",
        "- `anomaly_catalog.md` — anomaly definitions",
        "- `controlled_sensor_scenarios.csv` — controlled test scenarios",
        "- `controlled_sensor_ground_truth.csv` — controlled scenario labels",
        "- `remediation_traceability.csv` — alarm, inventory, inspection, "
        "and remediation traceability",
        "- `generation_config.json` — generation seed and scale profiles",
        "- `generation_manifest.json` — source database baseline",
        "",
        "## Commands",
        "",
        "Run from the repository root with the project virtual environment active:",
        "",
        "```bash",
        "python scripts/build_data_dictionary.py",
        "python scripts/build_ground_truth.py",
        "python scripts/build_sensor_scenarios.py",
        "python scripts/build_remediation_traceability.py",
        "python scripts/phase10_generation_config.py --profile full",
        "python scripts/build_generation_manifest.py",
        "python scripts/build_phase10_submission_report.py",
        "python scripts/validate_phase10.py",
        "pytest -q",
        "```",
        "",
        "## Reproducibility notes",
        "",
        "The configuration defines a master seed and per-generator seeds. "
        "The existing source generators must consume the centralized "
        "configuration before full end-to-end regeneration can be claimed "
        "as deterministic. The generation manifest records a baseline; "
        "it is not proof of two identical regeneration runs.",
        "",
        "## Safety and data integrity",
        "",
        "The Phase 10 report-generation scripts use read-only database "
        "connections. Controlled synthetic scenarios are stored in "
        "separate CSV files rather than inserted into the source database.",
        "",
        "## Generated documentation",
        "",
        "This file is a Phase 10 addendum. It does not replace the main "
        "repository README.",
        "",
    ])

    return "\n".join(lines)


def build_checklist(files, database):
    lines = [
        "# Warehouse Risk Monitoring — Submission Checklist",
        "",
        "## Project documentation",
        "",
        "- [ ] Main README reviewed and updated",
        "- [ ] Data dictionary reviewed",
        "- [ ] Entity relationships and constraints reviewed",
        "- [ ] Generator commands and seed documented",
        "- [ ] Source manifest reviewed",
        "",
        "## Data quality",
        "",
        "- [ ] Primary-key uniqueness verified",
        "- [ ] Foreign-key integrity verified",
        "- [ ] Enum and lifecycle values verified",
        "- [ ] Date and time relationships verified",
        "- [ ] Ground-truth labels reviewed",
        "- [ ] Controlled scenarios reviewed",
        "",
        "## Application",
        "",
        "- [ ] Flask API endpoints tested",
        "- [ ] Dashboard pages tested",
        "- [ ] Analytics outputs reviewed",
        "- [ ] Alarm-to-inventory traceability reviewed",
        "- [ ] Inspection and remediation workflow reviewed",
        "",
        "## Reproducibility",
        "",
        "- [ ] Central generation configuration integrated into generators",
        "- [ ] Starter profile tested",
        "- [ ] Full profile tested",
        "- [ ] Two same-seed generation runs compared",
        "- [ ] Checksums and row counts compared",
        "",
        "## Final verification",
        "",
        "- [ ] Phase 10 validator passes",
        "- [ ] Pytest passes",
        "- [ ] JavaScript syntax checks pass",
        "- [ ] Git working tree reviewed",
        "- [ ] Changes committed",
        "- [ ] Changes pushed to GitHub",
        "",
        "## Current database baseline",
        "",
        f"- SQLite integrity: `{database['integrity']}`",
        f"- Foreign-key violations: `{database['foreign_key_violations']}`",
        f"- Database tables: `{database['table_count']}`",
        "",
        "Items above are a checklist, not assertions that the work is already complete.",
        "",
    ]

    for item in files:
        status = "present" if item["exists"] else "missing"
        lines.append(f"- `{item['file']}`: {status}")

    return "\n".join(lines)


def main():
    PHASE_DIR.mkdir(parents=True, exist_ok=True)

    database = inspect_database()
    files = inspect_files()
    ground_truth = inspect_ground_truth()

    report = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "project": "Warehouse Risk Monitoring System",
        "phase": "10",
        "database": database,
        "ground_truth": ground_truth,
        "phase10_files": files,
        "source_database_modified": False,
        "submission_status": "PENDING_FINAL_VALIDATION",
        "notes": [
            "This report inventories available artifacts.",
            "It does not claim that all final tests have passed.",
            "Reproducibility must be demonstrated by comparing two runs.",
            "The main README is not overwritten.",
        ],
    }

    with REPORT_PATH.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=4)

    README_PATH.write_text(
        build_readme_addendum(
            database,
            files,
            ground_truth
        ),
        encoding="utf-8"
    )

    CHECKLIST_PATH.write_text(
        build_checklist(files, database),
        encoding="utf-8"
    )

    print("========== PHASE 10 SUBMISSION DOCUMENTATION ==========")
    print("Database tables:", database["table_count"])
    print("Ground-truth records:", ground_truth["record_count"])
    print(
        "Present Phase 10 files:",
        sum(item["exists"] for item in files),
        "/",
        len(files)
    )

    print("\nGenerated:")
    print(REPORT_PATH)
    print(README_PATH)
    print(CHECKLIST_PATH)

    print("\nSource database modified: NO")
    print("Submission status: PENDING FINAL VALIDATION")


if __name__ == "__main__":
    main()