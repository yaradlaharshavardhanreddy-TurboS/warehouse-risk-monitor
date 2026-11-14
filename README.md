# Warehouse Risk Monitor

**YottaFlex.ai – Associate AI Forward Deployed Engineer | Round 2 Code Challenge**

## 1. Project Overview

Warehouse Risk Monitor is a synthetic-data-driven warehouse monitoring and risk management application built with Python and Flask.

The application models warehouse environments and monitors temperature, humidity, occupancy, sensor readings and door activity across warehouse zones. It identifies operational and storage risks, generates alarms, supports inspection workflows and maintains traceability between affected inventory and remediation records.

The project demonstrates an end-to-end workflow involving master data, dependent events, business rules, exception handling, persistent records, validation and measurable outputs.

## 2. Business Problem

Warehouse operators need visibility into environmental and operational conditions that can affect stored inventory.

The solution addresses:
- Temperature and humidity excursions.
- Abnormal occupancy and door activity.
- Sensor outages, missing readings and sensor drift.
- Inventory lots exposed to environmental risk.
- Storage requirement violations.
- Alarm investigation and inspection.
- Remediation and inventory-impact traceability.

## 3. Project Objectives

- Build a warehouse and zone hierarchy.
- Associate sensors with their respective zones.
- Define storage requirements for inventory.
- Generate realistic time-series sensor readings and door events.
- Detect risk conditions using documented business rules.
- Identify affected inventory using zone and time overlap.
- Preserve alarms, inspections and remediation history.
- Separate known anomaly labels from operational input data.
- Produce reproducible datasets and measurable validation results.

## 4. Key Features

### Warehouse monitoring
- Warehouse and zone hierarchy.
- Temperature and humidity monitoring.
- Occupancy and door-event monitoring.
- Sensor assignment and reading history.

### Risk and exception detection
- Environmental excursions.
- Door-open events.
- Sensor drift and outages.
- Missing-reading and reading-gap detection.
- Inventory stored in incompatible zones.
- Suspicious sensor-to-zone assignments.
- Alarms without complete inventory associations.

### Inventory traceability
- Inventory lots and storage requirements.
- Lot-to-zone associations.
- Storage duration and exposure analysis.
- Alarm-to-inventory relationships.
- Inspection and remediation traceability.

### Data engineering
- Deterministic synthetic data generation.
- Configurable starter and full-scale profiles.
- Fixed random seed.
- Primary-key and foreign-key validation.
- Ground-truth anomaly records.
- CSV, JSON and database-oriented outputs where supported.
- Reproducibility and integrity checks.

### Application workflows
The application provides monitoring, API and operational workflows for plant operators, maintenance/quality engineers, production planners and OT/IT administrators.

## 5. Technology Stack

- Python
- Flask
- SQLite
- SQL
- Pandas and other project dependencies
- Pytest
- HTML, CSS and JavaScript where applicable
- Git and GitHub

Refer to `requirements.txt` for the actual dependency list.

## 6. Architecture

The solution follows a data-generation, persistence, business-processing and presentation workflow.

```text
Synthetic Data Generation
          |
          v
Master Data
Warehouse -> Zone -> Sensor
          |
          v
Dependent Events
Sensor Readings / Door Events
          |
          v
Inventory and Storage Requirements
          |
          v
Risk Detection and Business Rules
          |
          v
Alarms and Affected Inventory
          |
          v
Inspections and Remediation
          |
          v
Database / APIs / Monitoring Interface
          |
          v
Validation, Reports and Ground Truth
```

The database is the persistence layer. Generated records use parent identifiers and documented relationships. Historical events and operational records are retained rather than silently overwritten.

## 7. Data Model

The principal entities are:

| Entity | Purpose |
|---|---|
| Warehouse | Warehouse master information |
| Zone | Storage and monitoring area within a warehouse |
| Sensor | Monitoring device assigned to a zone |
| SensorReading | Timestamped sensor measurements |
| DoorEvent | Door activity and event history |
| InventoryLot | Stored inventory and lot information |
| StorageRequirement | Environmental requirements for stored products |
| Alarm | Detected risk and exception records |
| Inspection | Investigation and inspection records |
| Remediation | Corrective actions and their inventory impact |

Supporting association and traceability tables represent relationships where necessary.

### Relationship design

- Warehouse to Zone: one-to-many.
- Zone to Sensor: one-to-many over the applicable assignment period.
- Sensor to SensorReading: one-to-many.
- Warehouse/Zone to DoorEvent: one-to-many.
- InventoryLot to StorageRequirement: linked according to product and storage rules.
- Alarm to affected inventory: potentially many-to-many through traceability associations.
- Alarm to Inspection: linked through the implemented inspection workflow.
- Inspection to Remediation: linked through the implemented remediation workflow.

Effective dates, optional relationships and lifecycle states are documented in the schema and data dictionary. Consult the actual database schema for implementation-level details.

## 8. ID and Naming Conventions

The generator follows deterministic, readable identifiers based on the challenge conventions.

Examples:

| Entity | Example |
|---|---|
| Warehouse | `WH-001` |
| Zone | `ZONE-WH-001-001` |
| Temperature sensor | `SNS-ZONE-WH-001-001-TEMP-01` |
| Sensor reading | `RDG-<sensor-id>-<timestamp>` |
| Inventory lot | `LOT-2026-000001` |

Identifiers are intended to remain immutable and consistently referenced across generated records.

## 9. Synthetic Data Generation

The challenge's full-scale target is:

| Entity | Target volume |
|---|---:|
| Warehouses | 10 |
| Zones | 100 |
| Sensors | 500 |
| Sensor readings | 1,000,000 |
| Inventory lots | 10,000 |

The generator uses a fixed seed:

`20261022`

The same generation logic supports different scale profiles.

### Generation sequence

1. Generate warehouse master records.
2. Generate zones and their warehouse relationships.
3. Generate sensors and zone assignments.
4. Generate storage requirements and inventory lots.
5. Generate sensor readings and door events.
6. Introduce documented and labelled anomaly scenarios.
7. Calculate derived values from source records.
8. Generate alarms, inspections and traceability records.
9. Produce validation reports and ground-truth outputs.

### Required exception scenarios

- Inventory assigned to an incompatible storage zone.
- Sensor assigned to multiple zones without a valid rationale.
- Reading gaps incorrectly treated as normal.
- Alarm missing affected-inventory associations.

The anomaly label is maintained separately from operational input features.

## 10. Ground Truth and Evaluation

Ground truth represents known anomalies, expected outcomes and evaluation labels derived from documented generation rules.

It is kept separate from operational model inputs to avoid label leakage.

Validation and evaluation should cover:

- Primary-key uniqueness.
- Foreign-key integrity.
- Referential consistency.
- Allowed enumeration values.
- Timestamp ordering.
- Duplicate detection.
- Derived-value reconciliation.
- Lifecycle consistency.
- Inventory exposure and zone overlap.
- Alarm-to-inventory traceability.
- Sensor-gap and outage detection.
- Fixed-seed reproducibility.

The generated validation reports under `docs/` provide execution evidence. Reported metrics must be interpreted using their corresponding validation definitions.

## 11. Installation and Setup

### Prerequisites

- Python 3.10 or a compatible version required by the dependencies.
- Git.
- Windows, Linux or macOS.
- Git Bash is supported for the commands below.

### Clone the repository

```bash
git clone <PUBLIC_GITHUB_REPOSITORY_URL>
cd warehouse-risk-monitor
```

### Create a virtual environment

Windows Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 12. Running the Project

### Generate project data

Use the implemented generation commands from the repository root.

The full-scale generation configuration is:

```bash
python -m scripts.phase10_generation_config --profile full
```

Individual artifact-generation scripts, when needed:

```bash
python -m scripts.build_data_dictionary
python -m scripts.build_ground_truth
python -m scripts.build_sensor_scenarios
python -m scripts.build_remediation_traceability
```

Run generation in the documented order and consult the individual script help or source for supported arguments.

### Run the Flask application

```bash
python -m flask --app app run
```

If the application uses a different Flask entry point, use the entry point documented in its configuration.

### Run automated tests

```bash
pytest -q
```

### Run comprehensive validation

```bash
python -m scripts.validate_phase10
```

Validation reports and generated documentation are maintained in the project documentation directories.

## 13. Testing Strategy

The test suite is designed to cover:

- Database integrity.
- Entity relationships.
- Data generation.
- Business-rule execution.
- Risk and alarm handling.
- Exception scenarios.
- Inventory traceability.
- API and application behavior.
- Data validation and reconciliation.

Run the complete suite with `pytest -q`.

Do not interpret a successful test run as proof of every challenge acceptance criterion; use the final acceptance audit and its individual evidence.

## 14. Repository Structure

Important directories include:

```text
warehouse-risk-monitor/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── scripts/
├── tests/
├── data/
├── docs/
│   ├── phase10/
│   ├── AI_USAGE_AND_PROMPT_HISTORY.md
│   ├── ARCHITECTURE_AND_DECISIONS.md
│   └── DATA_GENERATION_AND_VALIDATION.md
└── ...
```

The exact repository may contain additional modules and supporting files. Consult the source tree for the complete implementation.

## 15. Assumptions and Engineering Decisions

- Synthetic data is used to provide controlled, reproducible scenarios.
- A fixed seed supports repeatable generation.
- Valid baseline data is generated before labelled exceptions are introduced.
- Derived outcomes are calculated from source records and documented rules.
- Ground truth is maintained separately from operational input features.
- Historical operational records are retained for traceability.
- Missing relationships and incomplete records are treated as explicit exceptions where applicable.
- SQLite provides a lightweight relational persistence layer suitable for the challenge demonstration.

## 16. Limitations and Future Improvements

This is a synthetic-data challenge implementation, not a certified production OT monitoring system.

Potential future improvements include:

- Live industrial sensor integrations.
- Streaming ingestion and event processing.
- Role-based access control and production-grade authentication.
- Distributed database deployment.
- Configurable alert policies.
- Advanced anomaly detection.
- Production monitoring, observability and alert delivery.
- Performance benchmarking at larger scales.

These improvements should not be interpreted as currently implemented features unless supported by repository code.

## 17. Lawful Data Provenance

The project uses synthetic data for its generated operational records.

No confidential warehouse, employee or customer dataset is required for the synthetic generation workflow.

If external reference data is introduced, its source URL, version, retrieval date, license, attribution, transformations and discarded fields must be documented in the source manifest.

## 18. AI-Assisted Development Disclosure

LLM tools were used as development assistance during the challenge.

The developer remains responsible for reviewing generated code, integrating changes, running commands, evaluating validation results, and verifying the final application.

The accompanying `docs/AI_USAGE_AND_PROMPT_HISTORY.md` describes the AI-assisted development workflow and representative prompt categories. It distinguishes AI assistance from developer review and execution.

## 19. Submission Checklist

- [ ] Public GitHub repository.
- [ ] Complete README and installation instructions.
- [ ] Working application and executable generation workflow.
- [ ] Requirements and configuration documented.
- [ ] Data dictionary and schema documentation.
- [ ] Synthetic generation and fixed-seed details.
- [ ] Ground-truth separation.
- [ ] Validation and reproducibility evidence.
- [ ] Automated tests passing.
- [ ] AI disclosure and prompt history.
- [ ] Assumptions, decisions, trade-offs and limitations.
- [ ] Final acceptance audit completed.

## 20. License and Usage

This repository was prepared as a candidate project for the YottaFlex.ai recruitment challenge. Any redistribution or reuse should respect the licenses of included dependencies and any separately sourced material.
