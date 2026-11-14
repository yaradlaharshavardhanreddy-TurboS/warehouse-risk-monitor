# Warehouse Risk Monitor - Final Project Audit

- Generated: 2026-11-14T05:43:11.210136+00:00
- Overall result: **NOT READY - FAILURES FOUND**

## Summary

- PASS: 42
- FAIL: 1
- REVIEW: 4
- NOT VERIFIABLE: 1

## Detailed checks

- **PASS** — Required project structure: Missing: none
- **PASS** — Python compilation: exit_code=0
- **PASS** — Complete pytest suite: exit_code=0
- **PASS** — JavaScript syntax: dashboard.js: exit_code=0
- **PASS** — JavaScript syntax: data_page.js: exit_code=0
- **PASS** — JavaScript syntax: charts.js: exit_code=0
- **PASS** — SQLite integrity: ok
- **PASS** — SQLite foreign-key integrity: violations=0
- **PASS** — Required application tables: Missing: none
- **PASS** — Alarm-to-affected-lot traceability: alarms=6472, linked_alarms=6331, links=628552
- **PASS** — Inventory data population: inventory_lots=10000
- **PASS** — inspections population: rows=6472
- **PASS** — remediations population: rows=10
- **FAIL** — Sensor outage data: tables=['sensor_outages'], rows=0
- **PASS** — Deployment archive matches local database: SHA-256 comparison
- **REVIEW** — Generator seed consistency review: detected seeds=no simple numeric assignments; inspect derived seeds and RNG usage
- **PASS** — Sensor-to-zone assignment: Source keyword evidence: zone_id, sensor_id
- **PASS** — Sensor outage implementation: Source keyword evidence: outage
- **PASS** — Incompatible inventory assignment: Source keyword evidence: compatibility, product_type
- **PASS** — Alarm-to-lot traceability implementation: Source keyword evidence: alarm_lots, inventory_lots
- **PASS** — Inspection lifecycle implementation: Source keyword evidence: inspection, completed, scheduled
- **PASS** — Remediation lifecycle implementation: Source keyword evidence: remediation, planned, completed
- **REVIEW** — Ground-truth or anomaly labeling: Source keyword evidence: not detected
- **PASS** — Sensor drift implementation: Source keyword evidence: drift, calibration
- **PASS** — Occupancy implementation: Source keyword evidence: occupancy, capacity
- **PASS** — Profile tooling: run_profiles.py: present
- **PASS** — Profile tooling: phase10_generation_config.py: present
- **REVIEW** — Multiple generation profiles declared: detected profile labels=[]
- **PASS** — Validation implementation: app\services\phase5_validation.py
- **REVIEW** — Dedicated reproducibility/profile tests: No clearly named dedicated test files found
- **PASS** — README: Project overview: matching terms=overview, warehouse
- **PASS** — README: Installation and setup: matching terms=install
- **PASS** — README: Execution instructions: matching terms=run, execution
- **PASS** — README: Data generation profiles: matching terms=profile
- **PASS** — README: Deterministic generation: matching terms=seed, reproduc
- **PASS** — README: Validation and testing: matching terms=validation, test
- **PASS** — README: Architecture or project structure: matching terms=architecture
- **PASS** — README: Limitations or synthetic-data disclosure: matching terms=synthetic
- **PASS** — Data dictionary: matching documentation file found
- **PASS** — Ground-truth documentation: matching documentation file found
- **PASS** — Reproducibility documentation: matching documentation file found
- **PASS** — Challenge coverage report: matching documentation file found
- **PASS** — Existing Phase 15 readiness report: Valid JSON
- **PASS** — All eight Vercel-mode APIs: all HTTP 200
- **PASS** — Git branch: main
- **PASS** — Git working tree: clean
- **PASS** — Git upstream tracking: origin/main; ahead/behind=0	0
- **NOT VERIFIABLE** — Live Vercel deployment verification: No VERCEL_URL supplied; local Vercel-mode tests are not a live deployment test.

## Database row counts

- `alarm_lots`: 628,552
- `alarms`: 6,472
- `door_events`: 16,398
- `inspections`: 6,472
- `inventory_lots`: 10,000
- `lot_zone_assignments`: 10,000
- `remediations`: 10
- `schema_metadata`: 1
- `sensor_outages`: 0
- `sensor_readings`: 1,000,000
- `sensor_zone_assignments`: 500
- `sensors`: 500
- `storage_requirements`: 5
- `warehouses`: 10
- `zones`: 100
