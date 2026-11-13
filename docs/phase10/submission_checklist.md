# Warehouse Risk Monitoring — Submission Checklist

## Project documentation

- [ ] Main README reviewed and updated
- [ ] Data dictionary reviewed
- [ ] Entity relationships and constraints reviewed
- [ ] Generator commands and seed documented
- [ ] Source manifest reviewed

## Data quality

- [ ] Primary-key uniqueness verified
- [ ] Foreign-key integrity verified
- [ ] Enum and lifecycle values verified
- [ ] Date and time relationships verified
- [ ] Ground-truth labels reviewed
- [ ] Controlled scenarios reviewed

## Application

- [ ] Flask API endpoints tested
- [ ] Dashboard pages tested
- [ ] Analytics outputs reviewed
- [ ] Alarm-to-inventory traceability reviewed
- [ ] Inspection and remediation workflow reviewed

## Reproducibility

- [ ] Central generation configuration integrated into generators
- [ ] Starter profile tested
- [ ] Full profile tested
- [ ] Two same-seed generation runs compared
- [ ] Checksums and row counts compared

## Final verification

- [ ] Phase 10 validator passes
- [ ] Pytest passes
- [ ] JavaScript syntax checks pass
- [ ] Git working tree reviewed
- [ ] Changes committed
- [ ] Changes pushed to GitHub

## Current database baseline

- SQLite integrity: `ok`
- Foreign-key violations: `0`
- Database tables: `15`

Items above are a checklist, not assertions that the work is already complete.

- `docs/phase10/data_dictionary.json`: present
- `docs/phase10/data_dictionary.csv`: present
- `docs/phase10/data_dictionary.md`: present
- `docs/phase10/ground_truth.csv`: present
- `docs/phase10/anomaly_catalog.md`: present
- `docs/phase10/source_manifest.json`: present
- `docs/phase10/controlled_sensor_scenarios.csv`: present
- `docs/phase10/controlled_sensor_ground_truth.csv`: present
- `docs/phase10/controlled_sensor_manifest.json`: present
- `docs/phase10/remediation_traceability.csv`: present
- `docs/phase10/remediation_traceability_summary.json`: present
- `docs/phase10/generation_config.json`: present
- `docs/phase10/generation_manifest.json`: present