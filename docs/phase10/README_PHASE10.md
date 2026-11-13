# Phase 10 — Data Quality and Submission Documentation

## Overview

Phase 10 adds data-quality documentation, controlled synthetic anomaly scenarios, inventory traceability reporting, generation configuration, and automated validation for the Warehouse Risk Monitoring System.

## Database baseline

- Database: `data/warehouse_monitor.db`
- Tables: 15
- SQLite integrity: `ok`
- Foreign-key violations: 0

### Table row counts

| Table | Records |
|---|---:|
| `alarm_lots` | 628,552 |
| `alarms` | 6,472 |
| `door_events` | 16,398 |
| `inspections` | 6,472 |
| `inventory_lots` | 10,000 |
| `lot_zone_assignments` | 10,000 |
| `remediations` | 10 |
| `schema_metadata` | 1 |
| `sensor_outages` | 0 |
| `sensor_readings` | 1,000,000 |
| `sensor_zone_assignments` | 500 |
| `sensors` | 500 |
| `storage_requirements` | 5 |
| `warehouses` | 10 |
| `zones` | 100 |

## Ground truth

- Original ground-truth records: 0

| Issue type | Records |
|---|---:|

## Controlled synthetic scenarios

The controlled sensor scenario dataset includes:

- Sensor assigned to multiple zones
- Sensor reading gap
- Sensor outage
- Occupancy threshold breach

These records are labelled as controlled synthetic scenarios and are kept separate from the source database.

## Generated reports

- `data_dictionary.md` — schema documentation
- `ground_truth.csv` — labelled source-data anomaly records
- `anomaly_catalog.md` — anomaly definitions
- `controlled_sensor_scenarios.csv` — controlled test scenarios
- `controlled_sensor_ground_truth.csv` — controlled scenario labels
- `remediation_traceability.csv` — alarm, inventory, inspection, and remediation traceability
- `generation_config.json` — generation seed and scale profiles
- `generation_manifest.json` — source database baseline

## Commands

Run from the repository root with the project virtual environment active:

```bash
python scripts/build_data_dictionary.py
python scripts/build_ground_truth.py
python scripts/build_sensor_scenarios.py
python scripts/build_remediation_traceability.py
python scripts/phase10_generation_config.py --profile full
python scripts/build_generation_manifest.py
python scripts/build_phase10_submission_report.py
python scripts/validate_phase10.py
pytest -q
```

## Reproducibility notes

The configuration defines a master seed and per-generator seeds. The existing source generators must consume the centralized configuration before full end-to-end regeneration can be claimed as deterministic. The generation manifest records a baseline; it is not proof of two identical regeneration runs.

## Safety and data integrity

The Phase 10 report-generation scripts use read-only database connections. Controlled synthetic scenarios are stored in separate CSV files rather than inserted into the source database.

## Generated documentation

This file is a Phase 10 addendum. It does not replace the main repository README.
