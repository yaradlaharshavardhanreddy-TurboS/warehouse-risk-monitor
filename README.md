# Warehouse Risk Monitor

YottaFlex.ai — Associate AI Forward Deployed Engineer | Round 2 Code Challenge

## Project Overview

Warehouse Risk Monitor is a synthetic warehouse environmental monitoring and operational risk system built with Python, Flask, and SQLite.

The project models warehouse facilities, storage zones, sensors, environmental readings, door events, inventory lots, alarms, inspections, and remediation activities.

It demonstrates how warehouse monitoring data can be organized, analyzed, and connected to operational decisions. The system identifies environmental excursions, evaluates potentially affected inventory, preserves alarm and action histories, and supports follow-up inspections and remediation.

The system supports four operational actors:

- Plant operator: monitors warehouse conditions, alarms, and operational events.
- Maintenance or quality engineer: investigates environmental exceptions, sensor issues, and product-storage risks.
- Production planner: reviews potentially affected inventory and its operational impact.
- OT/IT administrator: oversees sensor assignments, data integrity, application availability, and system configuration.

## Live Demo

Application: [Warehouse Risk Monitor — Live Demo](https://warehouse-risk-monitor-gp11.vercel.app)

Link: https://warehouse-risk-monitor-gp11.vercel.app

The hosted deployment provides a read-only viewer of the warehouse monitoring data and dashboard.

## Features

- Warehouse and storage-zone management.
- Sensor records and effective-dated sensor-to-zone assignments.
- Synthetic temperature, humidity, occupancy, and sensor-reading data.
- Door-event monitoring.
- Product-specific storage requirements.
- Inventory-lot records and time-based lot-to-zone assignments.
- Environmental and operational risk detection.
- Alarm severity and lifecycle tracking.
- Alarm-to-inventory impact traceability.
- Inspection scheduling and status tracking.
- Remediation planning, execution, and outcome tracking.
- Alarm, inspection, and remediation lifecycle histories.
- Flask dashboard, operational pages, analytics, and health endpoints.
- Ground-truth anomaly evidence stored separately from operational data.
- Database integrity, foreign-key, business-rule, validation, and reproducibility checks.

## Submission Contents

| Deliverable | Repository link | Purpose |
|---|---|---|
| Flask application | [`app/`](app/) | Routes, dashboard, analytics, services, templates, and static assets |
| Database schema | [`app/database/schema.sql`](app/database/schema.sql) | SQLite schema, constraints, and indexes |
| Database connection | [`app/database/database.py`](app/database/database.py) | Database access and loading |
| Synthetic data generators | [`app/generator/`](app/generator/) | Warehouse, zone, sensor, reading, inventory, requirement, and door-event generation |
| Clean operational database | `data/warehouse_monitor.db` | Baseline database, supplied separately |
| Anomaly injection script | [`scripts/inject_anomalies.py`](scripts/inject_anomalies.py) | Creates injected anomaly scenarios and ground truth |
| CSV export script | [`scripts/export_data.py`](scripts/export_data.py) | Exports database tables to CSV |
| Ground truth | [`docs/phase10/ground_truth.csv`](docs/phase10/ground_truth.csv) | Injected anomaly records and detector-derived evidence |
| Data dictionary — Markdown | [`docs/phase10/data_dictionary.md`](docs/phase10/data_dictionary.md) | Human-readable database schema |
| Data dictionary — JSON | [`docs/phase10/data_dictionary.json`](docs/phase10/data_dictionary.json) | Structured schema documentation |
| Data dictionary — CSV | [`docs/phase10/data_dictionary.csv`](docs/phase10/data_dictionary.csv) | Tabular schema documentation |
| Source manifest | [`docs/phase10/source_manifest.json`](docs/phase10/source_manifest.json) | Source database and generation evidence |
| Generation configuration | [`docs/phase10/generation_config.json`](docs/phase10/generation_config.json) | Seed and generation-profile configuration |
| Generation manifest | [`docs/phase10/generation_manifest.json`](docs/phase10/generation_manifest.json) | Generated database baseline information |
| Validation summary | [`docs/validation_summary.md`](docs/validation_summary.md) | Final validation evidence |
| Comprehensive validation | [`docs/phase10/comprehensive_validation.json`](docs/phase10/comprehensive_validation.json) | Detailed validation results |
| Final submission report | [`docs/phase10/final_submission_report.json`](docs/phase10/final_submission_report.json) | Submission validation evidence |
| Reproducibility report | [`docs/reproducibility_report.md`](docs/reproducibility_report.md) | Two-run and delivered-database comparison |
| Reproducibility audit | [`docs/phase10/phase11_reproducibility_audit.json`](docs/phase10/phase11_reproducibility_audit.json) | Reproducibility audit evidence |
| Remediation traceability | [`docs/phase10/remediation_traceability.csv`](docs/phase10/remediation_traceability.csv) | Alarm, inventory, inspection, and remediation relationships |
| Controlled sensor scenarios | [`docs/phase10/controlled_sensor_scenarios.csv`](docs/phase10/controlled_sensor_scenarios.csv) | Controlled sensor test scenarios |
| Controlled sensor ground truth | [`docs/phase10/controlled_sensor_ground_truth.csv`](docs/phase10/controlled_sensor_ground_truth.csv) | Expected labels for controlled sensor scenarios |
| Controlled business fixtures | [`docs/phase10/controlled_business_edge_cases.csv`](docs/phase10/controlled_business_edge_cases.csv) | Controlled business-rule test fixtures |
| Controlled business fixture labels | [`docs/phase10/controlled_business_edge_case_ground_truth.csv`](docs/phase10/controlled_business_edge_case_ground_truth.csv) | Expected labels for controlled business fixtures |
| AI usage disclosure | [`docs/AI_USAGE_AND_PROMPT_HISTORY.md`](docs/AI_USAGE_AND_PROMPT_HISTORY.md) | Disclosure of AI-assisted development |
| Architecture documentation | [`docs/ARCHITECTURE_AND_DECISIONS.md`](docs/ARCHITECTURE_AND_DECISIONS.md) | Architecture, relationships, and engineering decisions |
| Data generation and validation guide | [`docs/DATA_GENERATION_AND_VALIDATION.md`](docs/DATA_GENERATION_AND_VALIDATION.md) | Generation profiles and validation approach |
| Automated tests | [`tests/`](tests/) | Automated test suite |
| Python dependencies | [`requirements.txt`](requirements.txt) | Required Python packages |

## Architecture

### Application structure

```text
warehouse-risk-monitor/
│
├── app/
│   ├── analytics/
│   ├── database/
│   │   ├── database.py
│   │   └── schema.sql
│   ├── generator/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── validators/
│   ├── static/
│   └── templates/
│
├── scripts/
│   ├── inject_anomalies.py
│   ├── export_data.py
│   ├── reproducibility_check.py
│   ├── validate_final.py
│   ├── validate_phase10.py
│   ├── validate_submission.py
│   └── ...
│
├── data/
│   ├── warehouse_monitor.db
│   ├── warehouse_monitor_anomalies.db
│   └── exports/
│
├── docs/
│   ├── AI_USAGE_AND_PROMPT_HISTORY.md
│   ├── ARCHITECTURE_AND_DECISIONS.md
│   ├── DATA_GENERATION_AND_VALIDATION.md
│   ├── reproducibility_report.md
│   ├── validation_summary.md
│   └── phase10/
│
├── reports/
├── tests/
├── config.py
├── requirements.txt
└── README.md
```

### Database entities and relationships

The SQLite database contains 19 tables.

| Table | Primary key | Foreign-key relationships | Purpose |
|---|---|---|---|
| `warehouses` | `warehouse_id` | — | Warehouse master records |
| `zones` | `zone_id` | `warehouse_id` → `warehouses` | Storage zones within warehouses |
| `sensors` | `sensor_id` | — | Sensor master records |
| `sensor_zone_assignments` | `assignment_id` | `sensor_id` → `sensors`; `zone_id` → `zones` | Effective-dated sensor-to-zone assignments |
| `sensor_readings` | `reading_id` | `sensor_id` → `sensors` | Sensor measurement history |
| `sensor_outages` | `outage_id` | `sensor_id` → `sensors` | Sensor outage records |
| `door_events` | `door_event_id` | `zone_id` → `zones` | Door activity associated with zones |
| `storage_requirements` | `requirement_id` | — | Product storage requirements |
| `inventory_lots` | `lot_id` | `requirement_id` → `storage_requirements` | Inventory lot records |
| `lot_zone_assignments` | `assignment_id` | `lot_id` → `inventory_lots`; `zone_id` → `zones` | Effective-dated lot-to-zone assignments |
| `alarms` | `alarm_id` | `warehouse_id` → `warehouses`; `zone_id` → `zones`; optional `sensor_id` → `sensors` | Alarm records |
| `alarm_lots` | Composite key | `alarm_id` → `alarms`; `lot_id` → `inventory_lots` | Alarm-to-affected-lot relationship |
| `alarm_history` | `history_id` | `alarm_id` → `alarms` | Alarm lifecycle history |
| `inspections` | `inspection_id` | `alarm_id` → `alarms` | Inspection records associated with alarms |
| `inspection_history` | `inspection_history_id` | `inspection_id` → `inspections` | Inspection lifecycle history |
| `remediations` | `remediation_id` | `inspection_id` → `inspections`; `alarm_id` → `alarms` | Remediation actions |
| `remediation_history` | `history_id` | `remediation_id` → `remediations` | Remediation lifecycle history |
| `remediation_lots` | Composite key | `remediation_id` → `remediations`; `lot_id` → `inventory_lots` | Remediation-to-lot relationship |
| `schema_metadata` | `version` | — | Database schema version metadata |

For complete column definitions, constraints, indexes, and foreign-key details, see the [Data Dictionary](docs/phase10/data_dictionary.md).

### Business rules and workflow

1. Environmental monitoring: sensor readings are evaluated against applicable storage requirements to identify environmental excursions.
2. Operational monitoring: door events, occupancy conditions, and sensor-data gaps or outages are evaluated for operational risks.
3. Inventory compatibility: inventory lots are associated with storage requirements and zone assignments. Product-storage compatibility is evaluated against the applicable zone type.
4. Time-aware impact: affected inventory is determined using zone assignments and the overlap between the event or alarm period and the lot's occupancy period.
5. Alarm traceability: alarms are connected to potentially affected inventory through `alarm_lots`.
6. Lifecycle tracking: alarm, inspection, and remediation status changes are recorded in their corresponding history tables.
7. Inspection workflow: inspections reference alarms and record their type, status, schedule, and findings.
8. Remediation workflow: remediation actions reference alarms and inspections and are linked to affected inventory lots through `remediation_lots`.

For additional design details, see [Architecture and Decisions](docs/ARCHITECTURE_AND_DECISIONS.md).

## Installation

Run the following commands from the repository root.

### Create and activate a virtual environment

Git Bash on Windows:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

Linux or macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Provide the database

Place the supplied clean database at:

```text
data/warehouse_monitor.db
```

The large database is supplied separately from the source-and-documentation ZIP.

## Usage

Run the following commands from the repository root with the project virtual environment activated.

### Start the Flask application

```bash
python -m app.run
```

Open the local application:

```text
http://127.0.0.1:5000
```

### Run automated tests

```bash
python -m pytest -q
```

### Generate a separate anomaly database and ground truth

```bash
python scripts/inject_anomalies.py --force
```

The injector uses seed 20261022 and creates:

- `data/warehouse_monitor_anomalies.db`
- `docs/phase10/ground_truth.csv`

The clean source database is preserved.

### Export database tables to CSV

```bash
python scripts/export_data.py
```

### Run final validation

```bash
python scripts/validate_final.py
```

### Run Phase 10 validation

```bash
python scripts/validate_phase10.py
```

### Run submission validation

```bash
python scripts/validate_submission.py --profile full
```

### Run reproducibility verification

```bash
python scripts/reproducibility_check.py
```

### Generate the data dictionary

```bash
python scripts/build_data_dictionary.py
```

### Generate remediation traceability

```bash
python scripts/build_remediation_traceability.py
```

For more details, see the [Data Generation and Validation Guide](docs/DATA_GENERATION_AND_VALIDATION.md).

## Ground Truth and Edge Cases

Ground truth is stored separately from the operational database:

[Open Ground Truth CSV](docs/phase10/ground_truth.csv)

It records injected anomaly evidence and detector-derived candidates. The application and detection services do not read this file; it is reserved for validation and evaluation.

The file contains 1,604 data rows covering four injected anomaly types. There are 60 injected cases, with 15 cases per type.

| Anomaly type | Ground-truth rows | Injected cases | Description |
|---|---:|---:|---|
| `LOT_WRONG_TYPE_ZONE` | 15 | 15 | Inventory lots are assigned to zones whose type is incompatible with their storage requirements |
| `SENSOR_OVERLAPPING_ZONE` | 15 | 15 | Sensor assignments are modified to create overlapping zone assignments |
| `SENSOR_MISSING_READINGS` | 105 | 15 | Reading records are removed to create missing-reading gaps |
| `ALARM_LOT_LINK_DELETED` | 1,469 | 15 | All alarm-to-lot links are deleted for selected alarms |

The ground-truth records identify the affected entity, anomaly type, action, affected table, primary-key information, and before/after evidence. Injected records are labelled `CONFIRMED_INJECTED`; detector-derived candidates use `REVIEW_REQUIRED`.

Controlled sensor and business-rule fixtures:

- [Controlled sensor scenarios](docs/phase10/controlled_sensor_scenarios.csv)
- [Controlled sensor ground truth](docs/phase10/controlled_sensor_ground_truth.csv)
- [Controlled business edge cases](docs/phase10/controlled_business_edge_cases.csv)
- [Controlled business edge-case ground truth](docs/phase10/controlled_business_edge_case_ground_truth.csv)

## Data Volumes and Statistics

The delivered clean database contains 19 tables.

| Entity or record type | Records |
|---|---:|
| Warehouses | 10 |
| Zones | 100 |
| Sensors | 500 |
| Sensor readings | 1,000,000 |
| Inventory lots | 10,000 |
| Door events | 16,398 |
| Alarms | 6,472 |
| Alarm history | 12,943 |
| Alarm-to-lot links | 628,550 |
| Inspections | 427 |
| Inspection history | 1,128 |
| Remediations | 256 |
| Remediation history | 648 |
| Remediation-to-lot links | 11,458 |

### Alarm lifecycle distribution

| Lifecycle state | Share |
|---|---:|
| `OPEN` | 15% |
| `ACKNOWLEDGED` | 15% |
| `RESOLVED` | 25% |
| `CLOSED` | 45% |

### Inspection distribution

Inspection statuses:

- `CANCELLED`
- `COMPLETED`
- `IN_PROGRESS`
- `SCHEDULED`

Inspection types:

- `QUALITY`
- `MAINTENANCE`
- `SAFETY`

### Remediation distribution

| Remediation status | Records |
|---|---:|
| `COMPLETED` | 126 |
| `CANCELLED` | 49 |
| `FAILED` | 36 |
| `PLANNED` | 26 |
| `IN_PROGRESS` | 19 |
| Total | 256 |

## Validation Results

| Validation | Result |
|---|---|
| Final validation (`validate_final.py`) | 11/11 PASS |
| Phase 10 validation (`validate_phase10.py`) | All checks PASS |
| Automated test suite | PASS |
| Clean database integrity and foreign-key checks | PASS |
| Anomaly database integrity and foreign-key checks | PASS |
| Ground-truth structure and injected anomaly coverage | PASS |
| Ground-truth entity references | PASS |

Supporting evidence:

- [Validation Summary](docs/validation_summary.md)
- [Comprehensive Validation Results](docs/phase10/comprehensive_validation.json)
- [Final Submission Report](docs/phase10/final_submission_report.json)
- [Final Project Audit](docs/phase10/final_project_audit.md)
- [Final Project Audit Data](docs/phase10/final_project_audit.json)
- [Submission Readiness Audit](docs/phase10/phase15_submission_readiness.json)
- [Submission Checklist](docs/phase10/submission_checklist.md)

## Reproducibility

The master generation seed is:

```text
20261022
```

The reproducibility check compares the generated contents of nine base tables:

1. `warehouses`
2. `storage_requirements`
3. `zones`
4. `inventory_lots`
5. `lot_zone_assignments`
6. `sensors`
7. `sensor_zone_assignments`
8. `sensor_readings`
9. `door_events`

The recorded verification establishes that:

- Two fresh generation runs match each other across the nine base tables.
- A fresh generation run matches the delivered database across those same nine base tables.
- The delivered database is opened read-only during the comparison.
- No repair, normalization, or database modification is performed as part of the comparison.

Alarm, lifecycle, inspection, and remediation records are seeded, but are not included in this nine-table hash proof.

Reproducibility evidence:

- [Reproducibility Report](docs/reproducibility_report.md)
- [Reproducibility Audit](docs/phase10/phase11_reproducibility_audit.json)
- [Reproducibility Check Script](scripts/reproducibility_check.py)
- [Generation Configuration](docs/phase10/generation_config.json)
- [Generation Manifest](docs/phase10/generation_manifest.json)
- [Source Manifest](docs/phase10/source_manifest.json)

## Data Provenance and Lawful Use

The warehouse, zone, sensor, measurement, door-event, inventory, alarm, inspection, and remediation records are synthetic challenge data.

The dataset was created for software development, demonstration, testing, and evaluation. It does not contain intentionally sourced real customer, employee, patient, or warehouse operational records.

## Responsible AI Use

AI-assisted tools were used during development for:

- Challenge decomposition and implementation planning.
- Architecture and database relationship discussions.
- Code drafting and review.
- Debugging suggestions.
- Test and validator design.
- Documentation and submission-readiness support.

The developer remains responsible for the project and its submitted results. Human review included running the test suite, checking database and business-rule validation, reviewing reproducibility evidence, and examining submission artifacts.

For the detailed disclosure, see [`docs/AI_USAGE_AND_PROMPT_HISTORY.md`](docs/AI_USAGE_AND_PROMPT_HISTORY.md).

## Known Limitations

- Separate clean and anomaly databases: `data/warehouse_monitor.db` is the clean baseline. `data/warehouse_monitor_anomalies.db` is created separately by `scripts/inject_anomalies.py` and is recreated when the injector runs with `--force`.
- Database packaging: the large clean database is supplied separately from the source-and-documentation ZIP.
- Identifier format differences: zone IDs use forms such as `ZN-001-01` and sensor IDs use forms such as `SEN-0001`, rather than the specified `ZONE-WH-001-001` and `SNS-...` patterns.
- Zone and lot distribution: 40 of 100 zones hold no inventory lots.
- Alarm distribution: alarms are concentrated in zone positions 01 and 06.
- Lot dwell time: lot stays are long compared with the 7-day sensor-reading window, so a large share of lots (about 60%) is linked to alarms.
- Door alarms: door alarms have no sensor and no affected lots, and door remediations are about 55% of all remediations.
- Sensor outages: the clean database's `sensor_outages` table is intentionally empty. The injected missing-reading cases deliberately add no outage record.
- Historical cleanup: two zero-duration `alarm_lots` links were removed in a one-time manual cleanup.
- Timestamp alignment: base-table timestamps were aligned once with the seeded generator after an earlier version used the wall clock.
- Reproducibility scope: the hash proof covers the nine base tables only.
- Synthetic rules: thresholds, product-zone compatibility, alarm generation, and lifecycle behavior are demonstration rules.
- No live OT integration: the project does not connect to industrial controllers, PLCs, or physical sensors.
- No safety certification: the application must not be used as the sole basis for inventory release, quarantine, or facility safety decisions.

## Author and Usage Note

Author: Harsha Vardhan Reddy Yaradla
Contact: yaradlaharshavardhanreddy@gmail.com
Challenge: YottaFlex.ai — Associate AI Forward Deployed Engineer, Round 2 Code Challenge

### Usage note

- This repository contains a fully synthetic dataset, its generator, validation scripts and a viewer dashboard. It contains no real warehouse, customer, employee or patient data.
- The project is for demonstration, testing and evaluation. It is not a certified safety or monitoring system.
- The clean database (`data/warehouse_monitor.db`) is supplied separately because of its size. The anomaly database is recreated with `python scripts/inject_anomalies.py --force`.
- [`docs/phase10/ground_truth.csv`](docs/phase10/ground_truth.csv) is for evaluation only. The application and the detectors never read it.
- Fixed seed for all generation: `20261022`.
