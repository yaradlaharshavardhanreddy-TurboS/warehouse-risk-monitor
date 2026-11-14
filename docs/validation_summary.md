# Final Project Validation Summary

- Generated: 2026-11-14T17:14:19.265037+05:30
- Database access: read-only
- Database modifications: none
- Clean database: `data\warehouse_monitor.db`
- Anomaly database: `data\warehouse_monitor_anomalies.db`
- Ground truth: `docs\phase10\ground_truth.csv`

## Validation results

| Check | Result | Details |
|---|---|---|
| Ground-truth CSV is non-empty and structurally valid | **PASS** | 1604 data rows; required columns and values present |
| All four anomaly types have at least 10 cases | **PASS** | ALARM_LOT_LINK_DELETED: 15 distinct entities (PASS; minimum 10); LOT_WRONG_TYPE_ZONE: 15 distinct entities (PASS; minimum 10); SENSOR_MISSING_READINGS: 15 distinct entities (PASS; minimum 10); SENSOR_OVERLAPPING_ZONE: 15 distinct entities (PASS; minimum 10) |
| Clean database opened read-only | **PASS** | C:\Users\akshi\warehouse-risk-monitor\data\warehouse_monitor.db |
| Anomaly database opened read-only | **PASS** | C:\Users\akshi\warehouse-risk-monitor\data\warehouse_monitor_anomalies.db |
| alarms has more than one status | **PASS** | 4 distinct statuses: ['ACKNOWLEDGED', 'CLOSED', 'OPEN', 'RESOLVED']; required: more than one |
| inspections has more than one status | **PASS** | 4 distinct statuses: ['CANCELLED', 'COMPLETED', 'IN_PROGRESS', 'SCHEDULED']; required: more than one |
| remediations has more than one status | **PASS** | 5 distinct statuses: ['CANCELLED', 'COMPLETED', 'FAILED', 'IN_PROGRESS', 'PLANNED']; required: more than one |
| Every ground-truth entity exists in anomaly database | **PASS** | All 1604 ground-truth entity references exist in the anomaly database. |
| Clean database has zero incompatible lot assignments | **PASS** | Incompatible active lot assignments: 0; required: 0 |
| Clean database has zero overlapping sensor assignments | **PASS** | Overlapping sensor assignment pairs: 0; required: 0 |
| Clean database: integrity_check and foreign_key_check | **PASS** | integrity_check: PASS; foreign_key_check: PASS |
| Anomaly database: integrity_check and foreign_key_check | **PASS** | integrity_check: PASS; foreign_key_check: PASS |

## Overall result

**PASS**

- Checks passed: 12
- Checks failed: 0

## Safety statement

- Both SQLite databases were opened using read-only connections.
- SQLite connections used `PRAGMA query_only = ON`.
- No database modification statements were executed.
- The only file written by this script is this validation summary.
