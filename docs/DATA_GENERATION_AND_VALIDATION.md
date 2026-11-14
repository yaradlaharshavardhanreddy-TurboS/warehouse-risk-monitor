# Data Generation and Validation Guide

## Generation Profile

- Master seed: `20261022`
- Starter and full profiles use the same generation configuration.
- Full-scale challenge targets:
  - 10 warehouses
  - 100 zones
  - 500 sensors
  - 1,000,000 readings
  - 10,000 inventory lots

## Generation Order

1. Warehouse
2. Zone
3. Sensor
4. Storage requirements
5. Inventory lots
6. Sensor readings
7. Door events
8. Labelled exceptions
9. Alarms
10. Inspections
11. Remediation and traceability

## Required Validation

- Primary-key uniqueness.
- Foreign-key integrity.
- Allowed values and enums.
- Effective-date and event-date ordering.
- Duplicate detection.
- Arithmetic and derived-value reconciliation.
- Lifecycle consistency.
- Sensor assignment integrity.
- Reading-gap and outage identification.
- Inventory compatibility.
- Alarm-to-inventory traceability.
- Ground-truth separation.
- Fixed-seed reproducibility.

## Reproducibility

Run the same supported generation profile twice using the same seed. Compare:

- Entity row counts.
- Generated artifact checksums.
- Database integrity.
- Ground-truth outputs.

A reproducibility claim should be made only when the generated outputs have actually been compared.

## Evidence

Store generated validation summaries and reproducibility reports in the relevant `docs/phase*` directory. Preserve the source data and report the exact generation profile used.
