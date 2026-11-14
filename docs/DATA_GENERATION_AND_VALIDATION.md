# Data Generation and Validation Guide

## Profile targets

| Entity | Starter | Full |
|---|---:|---:|
| Warehouses | 2 | 10 |
| Zones | 20 | 100 |
| Sensors | 100 | 500 |
| Sensor readings | 20,000 | 1,000,000 |
| Inventory lots | 500 | 10,000 |

The master seed and per-domain seeds are defined in `scripts/phase10_generation_config.py`. Domain generators use local `random.Random(seed)` instances where applicable; sensor master generation seeds its random sequence. Stable simulation timestamps are used so a fixed seed is not undermined by wall-clock creation times.

## Safe execution

Run from the repository root:

```bash
python -m scripts.run_profiles --profiles starter full --runs 2
```

The runner initializes fresh temporary databases from the checked-in schema, runs master data, requirements, sensors, inventory, readings and door events in dependency order, then executes both risk-detector families in dry-run mode. It checks expected profile counts, SQLite integrity, foreign keys, unique current sensor assignments and product/zone compatibility.

For each table, rows are serialized in deterministic sorted order and SHA-256 hashed. All requested runs for a profile must produce identical per-table hashes. The report is written to `reports/profile_execution_reproducibility.json`; temporary databases are deleted after the run. The operational `data/warehouse_monitor.db` is not changed.

The full profile is intentionally resource intensive: two full runs each generate one million sensor readings. Allow adequate disk space and execution time. The environmental detector is fully exercised in starter mode; on full profile the runner executes the operational detector but defers the environmental lot-impact scan because its current implementation is resource-intensive at one million readings. This is reported explicitly in the run JSON and is not represented as a full-scale environmental scan.

## Existing operational database audit

```bash
python -m scripts.validate_submission --profile full
python -m scripts.validate_phase10
python -m pytest -q
python -m compileall -q app scripts tests
```

`validate_submission` is read-only. It checks SQLite integrity, foreign keys, core entity volumes, current sensor assignment cardinality and overlap, active inventory compatibility, alarm-to-lot bridge references, alarm/inspection/remediation lifecycle timestamps, README sections and ground-truth evidence provenance.

## Ground truth

`python -m scripts.build_ground_truth` inspects the source database and writes anomaly candidates with an evidence field, label status and source-table provenance. Candidate labels must be interpreted using their status and evidence; a candidate is not automatically a confirmed production incident. Controlled scenarios under `docs/phase10/controlled_sensor_*` are deliberately synthetic fixtures and are documented as such.

## Business-rule checks

- Every active sensor should have exactly one current zone assignment.
- Assignment validity intervals for the same sensor must not overlap.
- A currently stored lot must occupy a compatible zone type according to `PRODUCT_ZONE_MAPPING` in `app/generator/inventory_data.py`.
- Every alarm-lot bridge row must reference an existing alarm and lot.
- Resolved/closed alarms require `resolved_at`; open/investigating states must not claim resolution.
- Completed inspections and remediations require their corresponding completion timestamps and valid start ordering.

## Reproducibility interpretation

A report certifies only the profiles and number of runs it actually contains. A successful starter-only report does not certify full-scale generation. A generator seed audit or a single generated database is not, by itself, proof of two-run reproducibility. Preserve the report and the exact command used as submission evidence.
