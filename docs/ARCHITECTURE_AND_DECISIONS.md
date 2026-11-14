# Architecture and Engineering Decisions

## Layered workflow

```text
Profile configuration + fixed seeds
               |
               v
Master data: warehouses -> zones -> sensors + assignments
               |
               v
Dependent synthetic events: readings + door events
               |
               v
Storage requirements + inventory lots + lot-zone assignments
               |
               v
Environmental detector + operational detector
               |
               v
Alarms -> alarm/lot impact links -> inspections -> remediations
               |
               v
Flask routes / dashboard / analytics / health checks
               |
               v
Ground truth + validators + reproducibility reports
```

## Components

- `app/database/schema.sql` defines the relational contract, foreign keys, uniqueness constraints, checks and indexes.
- `app/generator/` creates deterministic warehouse, zone, sensor, reading, inventory and door-event data. Generator functions accept profile counts where profile scaling is required.
- `app/services/environmental_risk_detector.py` evaluates sensor measurements against effective storage requirements and calculates affected inventory from zone/time overlap.
- `app/services/operational_risk_detector.py` evaluates door activity, occupancy and sensor reading gaps/outages.
- `app/services/alarm_lifecycle_manager.py`, `inspection_manager.py` and `remediation_manager.py` manage operational state transitions and traceability.
- `app/routes/`, `app/templates/` and `app/static/` provide the Flask user interface and API surface.
- `scripts/` contains data dictionary, ground-truth, validation and profile-execution tooling.

## Key data relationships

- A warehouse owns zones.
- Sensors are associated with zones through effective-dated `sensor_zone_assignments`; historical assignments are retained.
- Sensor readings reference sensors and are ordered by event time.
- Inventory lots reference storage requirements and are placed through effective-dated `lot_zone_assignments`.
- Alarms reference warehouse, zone and optionally sensor; `alarm_lots` is the many-to-many impact bridge.
- Inspections reference alarms; remediations reference inspections and optionally inventory lots.

## Engineering decisions

| Decision | Rationale / consequence |
|---|---|
| SQLite | Portable local persistence with integrity checks; not a distributed production database. |
| Fixed random seeds | Makes random sequences repeatable; timestamps and IDs must also be stable for byte-level comparison. |
| Stable IDs | Supports joins and deterministic output comparison. |
| Effective-dated assignments | Preserves sensor/lot movement history and enables time-aware impact analysis. |
| Separate ground truth | Reduces label leakage into operational input features. |
| Detector dry-run mode | Allows analysis without persisting alarms during isolated validation. |
| Temporary profile databases | Prevents starter/full test execution from damaging the operational project database. |

## Assumptions and limitations

- Product-to-zone compatibility is a challenge business rule documented by the inventory generator mapping.
- Environmental impact requires matching zone and time overlap; an alarm without an impact link is not automatically proof that inventory was affected.
- A synthetic negative fixture is labelled as synthetic and is never silently inserted into the operational database.
- The rules are explainable examples, not validated industrial thresholds. No live OT/PLC integration, safety certification or production deployment guarantee is claimed.
