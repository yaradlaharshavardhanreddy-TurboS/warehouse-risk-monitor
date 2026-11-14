# Warehouse Risk Monitoring System
# Data Dictionary

Generated from the actual SQLite schema using a read-only connection. Required includes declared NOT NULL columns and primary-key columns. “Allowed values” lists only values enforced by SQLite CHECK constraints. Observed values are shown separately and are not presented as constraints. Units are documented only where established; otherwise they are marked not specified / not applicable.

Tables documented: 19

## alarm_history

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| history_id | INTEGER | Yes | - | - | identifier (integer) | Yes (primary key) | Generated INTEGER PRIMARY KEY AUTOINCREMENT; unique row identifier. | - |
| alarm_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required; foreign key to alarms.alarm_id. | alarms.alarm_id |
| from_state | TEXT | No | OPEN, ACKNOWLEDGED, RESOLVED, CLOSED | - | Not specified / not applicable | No | Optional; when present must be one of the four CHECK-enforced alarm states. | - |
| to_state | TEXT | Yes | OPEN, ACKNOWLEDGED, RESOLVED, CLOSED | - | Not specified / not applicable | No | Required; CHECK-enforced alarm lifecycle state. | - |
| changed_at | TEXT | Yes | - | - | timestamp (TEXT) | No | Required timestamp text; SQLite does not enforce a timestamp format. | - |
| reason | TEXT | Yes | - | - | Not specified / not applicable | No | Required explanatory text. | - |
| severity | TEXT | Yes | - | CRITICAL, HIGH, LOW, MEDIUM | Not specified / not applicable | No | Required text; no column-level CHECK constraint in this table. | - |
| age_minutes | REAL | Yes | - | - | minutes | No | Required REAL value; no CHECK constraint in this table. | - |
| rule_version | TEXT | Yes | - | - | Not specified / not applicable | No | Required rule/version identifier text. | - |

### Indexes and uniqueness

- `idx_alarm_history_alarm`: alarm_id, history_id; unique=False

### Table validation constraints

- `CHECK (to_state IN (
                'OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'CLOSED'
            )`
- `CHECK (from_state IS NULL OR from_state IN (
                'OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'CLOSED'
            )`

### Foreign keys

- `alarm_id` references `alarms.alarm_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## alarm_lots

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| alarm_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (part of composite primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. Foreign key references alarms.alarm_id. | alarms.alarm_id |
| lot_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (part of composite primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 2; unique. Foreign key references inventory_lots.lot_id. | inventory_lots.lot_id |
| impact_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| impact_start | TEXT | Yes | - | - | Not specified / not applicable | Yes (part of composite primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 3; unique. | - |
| impact_end | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| impact_details | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |

### Indexes and uniqueness

- `idx_alarm_lots_lot`: lot_id; unique=False
- `sqlite_autoindex_alarm_lots_1`: alarm_id, lot_id, impact_start; unique=True

### Table validation constraints

- `CHECK (impact_type IN (
            'TEMPERATURE',
            'HUMIDITY',
            'DWELL_TIME',
            'DOOR_EXPOSURE',
            'STORAGE_INCOMPATIBILITY',
            'OTHER'
        )`
- `CHECK (
        impact_end IS NULL OR impact_end >= impact_start
    )`

### Foreign keys

- `lot_id` references `inventory_lots.lot_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `alarm_id` references `alarms.alarm_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## alarms

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| alarm_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| warehouse_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references warehouses.warehouse_id. | warehouses.warehouse_id |
| zone_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references zones.zone_id. | zones.zone_id |
| sensor_id | TEXT | No | - | - | Not specified / not applicable | No | Foreign key references sensors.sensor_id. | sensors.sensor_id |
| alarm_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| severity | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| detected_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| description | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| lifecycle_state | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| resolved_at | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |

### Indexes and uniqueness

- `idx_alarms_status`: lifecycle_state, severity; unique=False
- `idx_alarms_zone_time`: zone_id, detected_at; unique=False
- `sqlite_autoindex_alarms_1`: alarm_id; unique=True

### Table validation constraints

- `CHECK (alarm_type IN (
            'HIGH_TEMPERATURE',
            'LOW_TEMPERATURE',
            'HIGH_HUMIDITY',
            'LOW_HUMIDITY',
            'HIGH_OCCUPANCY',
            'DOOR_OPEN',
            'SENSOR_OUTAGE',
            'SENSOR_DRIFT',
            'STORAGE_INCOMPATIBILITY'
        )`
- `CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')`
- `CHECK (lifecycle_state IN (
            'OPEN',
            'ACKNOWLEDGED',
            'INVESTIGATING',
            'RESOLVED',
            'CLOSED'
        )`
- `CHECK (
        resolved_at IS NULL OR resolved_at >= detected_at
    )`

### Foreign keys

- `sensor_id` references `sensors.sensor_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `zone_id` references `zones.zone_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `warehouse_id` references `warehouses.warehouse_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## door_events

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| door_event_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| zone_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references zones.zone_id. | zones.zone_id |
| door_identifier | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| event_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| event_timestamp | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| duration_seconds | INTEGER | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| recorded_by | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `idx_door_events_zone_time`: zone_id, event_timestamp; unique=False
- `sqlite_autoindex_door_events_1`: door_event_id; unique=True

### Table validation constraints

- `CHECK (event_type IN (
            'OPENED',
            'CLOSED',
            'HELD_OPEN',
            'FORCED_OPEN'
        )`
- `CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    )`

### Foreign keys

- `zone_id` references `zones.zone_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## inspection_history

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| inspection_history_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required TEXT PRIMARY KEY; unique identifier. | - |
| inspection_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required; foreign key to inspections.inspection_id. | inspections.inspection_id |
| from_status | TEXT | No | - | IN_PROGRESS, SCHEDULED | Not specified / not applicable | No | Optional status text; no SQLite CHECK constraint. | - |
| to_status | TEXT | Yes | - | CANCELLED, COMPLETED, IN_PROGRESS, SCHEDULED | Not specified / not applicable | No | Required status text; no SQLite CHECK constraint. | - |
| changed_at | TEXT | Yes | - | - | timestamp (TEXT) | No | Required timestamp text; SQLite does not enforce a timestamp format. | - |
| reason | TEXT | Yes | - | - | Not specified / not applicable | No | Required explanatory text. | - |
| rule_version | TEXT | Yes | - | - | Not specified / not applicable | No | Required rule/version identifier text. | - |

### Indexes and uniqueness

- `idx_inspection_history_inspection`: inspection_id, changed_at; unique=False
- `sqlite_autoindex_inspection_history_1`: inspection_history_id; unique=True

### Table validation constraints

No CHECK constraints detected.

### Foreign keys

- `inspection_id` references `inspections.inspection_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## inspections

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| inspection_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| alarm_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references alarms.alarm_id. | alarms.alarm_id |
| inspector_name | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| inspection_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| inspection_status | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| findings | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| scheduled_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| completed_at | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |

### Indexes and uniqueness

- `idx_inspections_alarm`: alarm_id; unique=False
- `sqlite_autoindex_inspections_1`: inspection_id; unique=True

### Table validation constraints

- `CHECK (inspection_type IN (
            'QUALITY',
            'MAINTENANCE',
            'INVENTORY',
            'SAFETY'
        )`
- `CHECK (inspection_status IN (
            'SCHEDULED',
            'IN_PROGRESS',
            'COMPLETED',
            'CANCELLED'
        )`
- `CHECK (
        completed_at IS NULL OR completed_at >= scheduled_at
    )`

### Foreign keys

- `alarm_id` references `alarms.alarm_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## inventory_lots

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| lot_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| product_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| product_name | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| quantity | INTEGER | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| unit_of_measure | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| requirement_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references storage_requirements.requirement_id. | storage_requirements.requirement_id |
| received_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| expiry_date | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| lifecycle_state | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `sqlite_autoindex_inventory_lots_1`: lot_id; unique=True

### Table validation constraints

- `CHECK (quantity > 0)`
- `CHECK (lifecycle_state IN (
            'RECEIVED',
            'STORED',
            'UNDER_INSPECTION',
            'QUARANTINED',
            'RELEASED',
            'DISPATCHED',
            'EXPIRED'
        )`
- `CHECK (
        expiry_date IS NULL OR expiry_date >= received_at
    )`

### Foreign keys

- `requirement_id` references `storage_requirements.requirement_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## lot_zone_assignments

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| assignment_id | INTEGER | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| lot_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references inventory_lots.lot_id. | inventory_lots.lot_id |
| zone_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references zones.zone_id. | zones.zone_id |
| assigned_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| released_at | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| assignment_reason | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `idx_lot_assignments_lot`: lot_id, assigned_at; unique=False
- `idx_lot_assignments_zone_time`: zone_id, assigned_at, released_at; unique=False

### Table validation constraints

- `CHECK (
        released_at IS NULL OR released_at > assigned_at
    )`

### Foreign keys

- `zone_id` references `zones.zone_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `lot_id` references `inventory_lots.lot_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## remediation_history

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| history_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required TEXT PRIMARY KEY; unique identifier. | - |
| remediation_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required; foreign key to remediations.remediation_id. | remediations.remediation_id |
| from_status | TEXT | No | - | IN_PROGRESS, PLANNED | Not specified / not applicable | No | Optional status text; no SQLite CHECK constraint. | - |
| to_status | TEXT | Yes | - | CANCELLED, COMPLETED, FAILED, IN_PROGRESS, PLANNED | Not specified / not applicable | No | Required status text; no SQLite CHECK constraint. | - |
| changed_at | TEXT | Yes | - | - | timestamp (TEXT) | No | Required timestamp text; SQLite does not enforce a timestamp format. | - |
| reason | TEXT | Yes | - | - | Not specified / not applicable | No | Required explanatory text. | - |
| rule_version | TEXT | Yes | - | - | Not specified / not applicable | No | Required rule/version identifier text. | - |

### Indexes and uniqueness

- `idx_remediation_history_remediation`: remediation_id; unique=False
- `sqlite_autoindex_remediation_history_1`: history_id; unique=True

### Table validation constraints

No CHECK constraints detected.

### Foreign keys

- `remediation_id` references `remediations.remediation_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## remediation_lots

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| remediation_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (part of composite primary key) | Required; first component of composite primary key and foreign key to remediations.remediation_id. | remediations.remediation_id |
| lot_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (part of composite primary key) | Required; second component of composite primary key and foreign key to inventory_lots.lot_id. | inventory_lots.lot_id |
| linked_at | TEXT | Yes | - | - | timestamp (TEXT) | No | Required timestamp text; SQLite does not enforce a timestamp format. | - |

### Indexes and uniqueness

- `idx_remediation_lots_lot`: lot_id; unique=False
- `sqlite_autoindex_remediation_lots_1`: remediation_id, lot_id; unique=True

### Table validation constraints

No CHECK constraints detected.

### Foreign keys

- `lot_id` references `inventory_lots.lot_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `remediation_id` references `remediations.remediation_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## remediations

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| remediation_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| inspection_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references inspections.inspection_id. | inspections.inspection_id |
| lot_id | TEXT | No | - | - | Not specified / not applicable | No | Foreign key references inventory_lots.lot_id. | inventory_lots.lot_id |
| remediation_type | TEXT | Yes | ADJUST_TEMPERATURE, ADJUST_HUMIDITY, REPAIR_SENSOR, CLOSE_DOOR, REPAIR_DOOR, RELOCATE_INVENTORY, QUARANTINE_INVENTORY, RECALIBRATE_SENSOR, OTHER | - | Not specified / not applicable | No | Required; value must match one of the nine values in the SQLite CHECK constraint. | - |
| action_description | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| remediation_status | TEXT | Yes | PLANNED, IN_PROGRESS, COMPLETED, FAILED, CANCELLED | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). CHECK constraint restricts the value to the listed values. | - |
| assigned_to | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| started_at | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| completed_at | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| inventory_impact | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| alarm_id | TEXT | No | - | - | Not specified / not applicable | No | Foreign key references alarms.alarm_id. | alarms.alarm_id |
| created_at | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |

### Indexes and uniqueness

- `idx_remediations_inspection`: inspection_id; unique=False
- `sqlite_autoindex_remediations_1`: remediation_id; unique=True

### Table validation constraints

- `CHECK (remediation_type IN (
            'ADJUST_TEMPERATURE',
            'ADJUST_HUMIDITY',
            'REPAIR_SENSOR',
            'CLOSE_DOOR', 'REPAIR_DOOR',
            'RELOCATE_INVENTORY',
            'QUARANTINE_INVENTORY',
            'RECALIBRATE_SENSOR',
            'OTHER'
        )`
- `CHECK (remediation_status IN (
            'PLANNED',
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED',
            'CANCELLED'
        )`
- `CHECK (
        completed_at IS NULL OR started_at IS NOT NULL
    )`
- `CHECK (
        completed_at IS NULL OR completed_at >= started_at
    )`

### Foreign keys

- `lot_id` references `inventory_lots.lot_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `inspection_id` references `inspections.inspection_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `alarm_id` references `alarms.alarm_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## schema_metadata

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| version | INTEGER | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| description | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| applied_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

No indexes reported.

### Table validation constraints

No CHECK constraints detected.

## sensor_outages

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| outage_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| sensor_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references sensors.sensor_id. | sensors.sensor_id |
| outage_start | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| outage_end | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| detected_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| outage_reason | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| lifecycle_state | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `idx_sensor_outages_sensor_time`: sensor_id, outage_start; unique=False
- `sqlite_autoindex_sensor_outages_1`: outage_id; unique=True

### Table validation constraints

- `CHECK (outage_reason IN (
            'POWER_FAILURE',
            'NETWORK_FAILURE',
            'HARDWARE_FAILURE',
            'UNKNOWN'
        )`
- `CHECK (lifecycle_state IN ('OPEN', 'RESOLVED')`
- `CHECK (
        outage_end IS NULL OR outage_end > outage_start
    )`

### Foreign keys

- `sensor_id` references `sensors.sensor_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## sensor_readings

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| reading_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| sensor_id | TEXT | Yes | - | - | Not specified / not applicable | Part of unique key | Required (NOT NULL or PRIMARY KEY). Foreign key references sensors.sensor_id. | sensors.sensor_id |
| recorded_at | TEXT | Yes | - | - | Not specified / not applicable | Part of unique key | Required (NOT NULL or PRIMARY KEY). | - |
| temperature_c | REAL | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| humidity_pct | REAL | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| occupancy_count | INTEGER | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| battery_pct | REAL | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| signal_strength | REAL | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| received_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `idx_readings_sensor_time`: sensor_id, recorded_at; unique=False
- `sqlite_autoindex_sensor_readings_2`: sensor_id, recorded_at; unique=True
- `sqlite_autoindex_sensor_readings_1`: reading_id; unique=True

### Table validation constraints

- `CHECK (
        temperature_c IS NULL OR
        temperature_c BETWEEN -100 AND 150
    )`
- `CHECK (
        humidity_pct IS NULL OR
        humidity_pct BETWEEN 0 AND 100
    )`
- `CHECK (
        occupancy_count IS NULL OR occupancy_count >= 0
    )`
- `CHECK (
        battery_pct IS NULL OR battery_pct BETWEEN 0 AND 100
    )`

### Foreign keys

- `sensor_id` references `sensors.sensor_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## sensor_zone_assignments

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| assignment_id | INTEGER | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| sensor_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references sensors.sensor_id. | sensors.sensor_id |
| zone_id | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). Foreign key references zones.zone_id. | zones.zone_id |
| effective_from | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| effective_to | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| assignment_reason | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `idx_sensor_assignments_zone`: zone_id, effective_from; unique=False
- `idx_sensor_assignments_sensor`: sensor_id, effective_from; unique=False

### Table validation constraints

- `CHECK (
        effective_to IS NULL OR effective_to > effective_from
    )`

### Foreign keys

- `zone_id` references `zones.zone_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).
- `sensor_id` references `sensors.sensor_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

## sensors

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| sensor_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| sensor_name | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| sensor_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| manufacturer | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| installation_date | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| calibration_due_date | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| lifecycle_state | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `sqlite_autoindex_sensors_1`: sensor_id; unique=True

### Table validation constraints

- `CHECK (sensor_type IN ('TEMP', 'HUMIDITY', 'OCCUPANCY', 'MULTI')`
- `CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'FAULTY', 'RETIRED')`

## storage_requirements

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| requirement_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| product_type | TEXT | Yes | - | - | Not specified / not applicable | Part of unique key | Required (NOT NULL or PRIMARY KEY). | - |
| min_temperature_c | REAL | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| max_temperature_c | REAL | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| min_humidity_pct | REAL | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| max_humidity_pct | REAL | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| max_dwell_hours | REAL | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| effective_from | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| effective_to | TEXT | No | - | - | Not specified / not applicable | No | No additional column-level validation identified in the SQLite schema. | - |
| requirement_version | INTEGER | Yes | - | - | Not specified / not applicable | Part of unique key | Required (NOT NULL or PRIMARY KEY). | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `sqlite_autoindex_storage_requirements_2`: product_type, requirement_version; unique=True
- `sqlite_autoindex_storage_requirements_1`: requirement_id; unique=True

### Table validation constraints

- `CHECK (min_temperature_c <= max_temperature_c)`
- `CHECK (min_humidity_pct <= max_humidity_pct)`
- `CHECK (min_humidity_pct >= 0 AND max_humidity_pct <= 100)`
- `CHECK (max_dwell_hours > 0)`
- `CHECK (
        effective_to IS NULL OR effective_to > effective_from
    )`

## warehouses

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| warehouse_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| warehouse_name | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| location | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| capacity_sq_m | REAL | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| warehouse_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| lifecycle_state | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| updated_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `sqlite_autoindex_warehouses_1`: warehouse_id; unique=True

### Table validation constraints

- `CHECK (capacity_sq_m > 0)`
- `CHECK (warehouse_type IN ('COLD', 'HOT', 'AMBIENT', 'MIXED')`
- `CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')`

## zones

| Column | Type | Required | Allowed values (CHECK) | Observed values (not constraints) | Units | Unique | Validation rule | Foreign key |
|---|---|---|---|---|---|---|---|---|
| zone_id | TEXT | Yes | - | - | Not specified / not applicable | Yes (primary key) | Required (NOT NULL or PRIMARY KEY). Primary key position 1; unique. | - |
| warehouse_id | TEXT | Yes | - | - | Not specified / not applicable | Part of unique key | Required (NOT NULL or PRIMARY KEY). Foreign key references warehouses.warehouse_id. | warehouses.warehouse_id |
| zone_name | TEXT | Yes | - | - | Not specified / not applicable | Part of unique key | Required (NOT NULL or PRIMARY KEY). | - |
| zone_type | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| max_capacity | INTEGER | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| lifecycle_state | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |
| created_at | TEXT | Yes | - | - | Not specified / not applicable | No | Required (NOT NULL or PRIMARY KEY). | - |

### Indexes and uniqueness

- `idx_zones_warehouse`: warehouse_id; unique=False
- `sqlite_autoindex_zones_2`: warehouse_id, zone_name; unique=True
- `sqlite_autoindex_zones_1`: zone_id; unique=True

### Table validation constraints

- `CHECK (zone_type IN ('COLD', 'HOT', 'AMBIENT', 'FREEZER', 'LOADING')`
- `CHECK (max_capacity > 0)`
- `CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')`

### Foreign keys

- `warehouse_id` references `warehouses.warehouse_id` (ON UPDATE NO ACTION; ON DELETE NO ACTION).

