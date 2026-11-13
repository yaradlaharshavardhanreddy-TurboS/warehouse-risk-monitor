# Phase 10 — Anomaly Catalog

These labels are generated from evidence in the source database.
They are stored separately from operational input data.

All automatically generated records initially use
`REVIEW_REQUIRED`. Review them against business rules before treating
them as confirmed ground truth.

| Issue type | Detection rule | Review required |
|---|---|---|
| `SENSOR_ASSIGNED_TO_MULTIPLE_ZONES` | A sensor has more than one distinct zone in sensor-zone assignments. | Confirm effective dates and approved multi-zone use. |
| `SENSOR_READING_GAP` | Consecutive readings for a sensor are separated by more than the calculated threshold. | Confirm expected sampling cadence and outage context. |
| `ALARM_WITHOUT_INVENTORY_LOT_LINK` | An alarm has no matching row in the alarm-lot bridge table. | Confirm whether the alarm should affect inventory. |

## Reading-gap threshold

The script calculates the median positive interval between readings
across sensors. The detection threshold is the greater of:

- 10 minutes
- Three times the calculated median interval

## Important

This catalog does not modify source tables, create alarms, or assign
remediation outcomes. It only writes a separate review dataset.
