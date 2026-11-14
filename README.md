# Warehouse Risk Monitor

**YottaFlex.ai – Associate AI Forward Deployed Engineer | Round 2 Code Challenge**

## Project Overview

Warehouse Risk Monitor is a Python/Flask application backed by SQLite. It models warehouses, storage zones, sensors, time-series measurements, door activity and inventory lots. Rule-based services detect environmental and operational exceptions, associate alarms with potentially affected inventory, and support inspection and remediation workflows.

The repository includes an existing full-scale synthetic operational database and isolated profile-generation tooling. The operational database is not overwritten by the profile runner.

## Features

- Warehouse, zone, sensor and time-effective sensor-zone assignment records.
- Deterministic synthetic temperature, humidity, occupancy and door-event generation.
- Product-specific storage requirements and lot-zone assignments.
- Environmental excursion detection and door, occupancy and sensor-outage detection.
- Alarm lifecycle, inspection and remediation workflows.
- Alarm-to-inventory impact links and evidence-based anomaly ground truth.
- Flask dashboard, operational pages, analytics and health endpoints.
- SQLite integrity, foreign-key, business-rule and reproducibility validation.

## Technology

- Python 3.10+ (the source uses modern typing syntax)
- Flask 3.1.2
- SQLite (Python standard library)
- SQLAlchemy 2.0.44 and python-dotenv 1.2.1 as declared dependencies
- pytest 8.4.2
- HTML, CSS and browser JavaScript

Pandas is not a required dependency. See `requirements.txt` for the pinned runtime/test packages.

## Repository Layout

```text
app/
  analytics/       Analytics and reporting queries
  database/        SQLite schema and connection helpers
  generator/       Synthetic master, event, sensor and inventory generators
  routes/          Flask routes and API endpoints
  services/        Risk detection and alarm/inspection/remediation workflows
  static/          CSS and JavaScript assets
  templates/       Flask/Jinja templates
scripts/
  phase10_generation_config.py
  run_profiles.py
  validate_submission.py
  validate_phase10.py
  build_ground_truth.py
  build_data_dictionary.py
  build_remediation_traceability.py
data/
  warehouse_monitor.db   Existing operational challenge database
  generated/             Optional generated outputs (ignored by Git)
docs/
  ARCHITECTURE_AND_DECISIONS.md
  DATA_GENERATION_AND_VALIDATION.md
  AI_USAGE_AND_PROMPT_HISTORY.md
  phase10/               Data dictionary, scenarios, ground truth and audits
exports/                 Database seed exports
reports/                 Local execution reports (ignored by Git)
tests/                   Pytest suite
```

## Installation

Run from the repository root in Git Bash, macOS Terminal or Linux:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Git Bash on Windows
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with `.venv\\Scripts\\Activate.ps1`.

## Usage

Start the web application:

```bash
python -m app.run
```

Run the existing test suite and static syntax check:

```bash
python -m pytest -q
python -m compileall -q app scripts tests
```

Run the read-only comprehensive audit against the checked-in operational database:

```bash
python -m scripts.validate_submission --profile full
```

Execute both isolated data-generation profiles twice and compare all table hashes:

```bash
python -m scripts.run_profiles --profiles starter full --runs 2
```

The profile runner creates temporary SQLite databases, runs the generators and detector dry-runs, validates profile row counts and database integrity, and compares deterministic table hashes. It does not modify `data/warehouse_monitor.db`. The environmental detector dry-run is exercised on starter; operational detection runs on both profiles. Full profile generation is computationally intensive because it creates one million sensor readings per run.

The distributable source package intentionally excludes the 380 MB operational database. Restore a local copy from the compressed seed export with:

```bash
python -m scripts.restore_database
```

The restore command refuses to overwrite an existing database unless `--overwrite` is explicitly supplied. The compressed seed restore was verified locally: 15 tables, 1,000,000 readings, SQLite integrity `ok`, and zero foreign-key violations.

Other useful commands:

```bash
python -m scripts.build_ground_truth
python -m scripts.build_data_dictionary
python -m scripts.build_remediation_traceability
python -m scripts.validate_phase10
```

## Data Profiles

| Entity | Starter | Full |
|---|---:|---:|
| Warehouses | 2 | 10 |
| Zones | 20 | 100 |
| Sensors | 100 | 500 |
| Sensor readings | 20,000 | 1,000,000 |
| Inventory lots | 500 | 10,000 |

Both profiles use the seed configuration in `scripts/phase10_generation_config.py`. The profile runner requires two or more runs for reproducibility certification and writes `reports/profile_execution_reproducibility.json`.

## Ground Truth and Validation

Ground truth is stored separately from operational feature tables. Each record should identify the anomaly type, entity, evidence, label status and source tables. Controlled synthetic scenarios are explicitly marked as fixtures and must not be represented as source-database facts. Validation checks relational integrity, assignment periods, product/zone compatibility, lifecycle timestamps and artifact completeness.

## Important Safety and Data Notes

- `data/warehouse_monitor.db` is the existing project database. Back it up before any manual regeneration or destructive `--replace` operation.
- The profile runner uses temporary databases and is the preferred way to exercise starter/full generation without touching the operational database.
- Synthetic data and rule-based detections are challenge/demo artifacts, not validated production monitoring or safety controls.
- Reproducibility is certified only when the two-run report exists and reports matching hashes for each requested profile.

## Documentation

- [Architecture and engineering decisions](docs/ARCHITECTURE_AND_DECISIONS.md)
- [Data generation and validation](docs/DATA_GENERATION_AND_VALIDATION.md)
- [AI usage and prompt-history disclosure](docs/AI_USAGE_AND_PROMPT_HISTORY.md)
- [Phase 10 submission checklist](docs/phase10/submission_checklist.md)
