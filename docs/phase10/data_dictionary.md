# Warehouse Risk Monitoring System
# Data Dictionary

This document is generated from the actual SQLite database schema.

Tables documented: 15

## alarm_lots

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| alarm_id | TEXT | Yes | 1 | alarms.alarm_id |
| lot_id | TEXT | Yes | 2 | inventory_lots.lot_id |
| impact_type | TEXT | Yes | - | - |
| impact_start | TEXT | Yes | 3 | - |
| impact_end | TEXT | No | - | - |
| impact_details | TEXT | No | - | - |

### Indexes

- `idx_alarm_lots_lot`: lot_id; unique=False
- `sqlite_autoindex_alarm_lots_1`: alarm_id, lot_id, impact_start; unique=True

### Validation constraints

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

## alarms

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| alarm_id | TEXT | No | 1 | - |
| warehouse_id | TEXT | Yes | - | warehouses.warehouse_id |
| zone_id | TEXT | Yes | - | zones.zone_id |
| sensor_id | TEXT | No | - | sensors.sensor_id |
| alarm_type | TEXT | Yes | - | - |
| severity | TEXT | Yes | - | - |
| detected_at | TEXT | Yes | - | - |
| description | TEXT | Yes | - | - |
| lifecycle_state | TEXT | Yes | - | - |
| resolved_at | TEXT | No | - | - |

### Indexes

- `idx_alarms_status`: lifecycle_state, severity; unique=False
- `idx_alarms_zone_time`: zone_id, detected_at; unique=False
- `sqlite_autoindex_alarms_1`: alarm_id; unique=True

### Validation constraints

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

## door_events

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| door_event_id | TEXT | No | 1 | - |
| zone_id | TEXT | Yes | - | zones.zone_id |
| door_identifier | TEXT | Yes | - | - |
| event_type | TEXT | Yes | - | - |
| event_timestamp | TEXT | Yes | - | - |
| duration_seconds | INTEGER | No | - | - |
| recorded_by | TEXT | Yes | - | - |

### Indexes

- `idx_door_events_zone_time`: zone_id, event_timestamp; unique=False
- `sqlite_autoindex_door_events_1`: door_event_id; unique=True

### Validation constraints

- `CHECK (event_type IN (
            'OPENED',
            'CLOSED',
            'HELD_OPEN',
            'FORCED_OPEN'
        )`
- `CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    )`

## inspections

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| inspection_id | TEXT | No | 1 | - |
| alarm_id | TEXT | Yes | - | alarms.alarm_id |
| inspector_name | TEXT | Yes | - | - |
| inspection_type | TEXT | Yes | - | - |
| inspection_status | TEXT | Yes | - | - |
| findings | TEXT | No | - | - |
| scheduled_at | TEXT | Yes | - | - |
| completed_at | TEXT | No | - | - |

### Indexes

- `idx_inspections_alarm`: alarm_id; unique=False
- `sqlite_autoindex_inspections_1`: inspection_id; unique=True

### Validation constraints

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

## inventory_lots

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| lot_id | TEXT | No | 1 | - |
| product_type | TEXT | Yes | - | - |
| product_name | TEXT | Yes | - | - |
| quantity | INTEGER | Yes | - | - |
| unit_of_measure | TEXT | Yes | - | - |
| requirement_id | TEXT | Yes | - | storage_requirements.requirement_id |
| received_at | TEXT | Yes | - | - |
| expiry_date | TEXT | No | - | - |
| lifecycle_state | TEXT | Yes | - | - |
| created_at | TEXT | Yes | - | - |

### Indexes

- `sqlite_autoindex_inventory_lots_1`: lot_id; unique=True

### Validation constraints

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

## lot_zone_assignments

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| assignment_id | INTEGER | No | 1 | - |
| lot_id | TEXT | Yes | - | inventory_lots.lot_id |
| zone_id | TEXT | Yes | - | zones.zone_id |
| assigned_at | TEXT | Yes | - | - |
| released_at | TEXT | No | - | - |
| assignment_reason | TEXT | No | - | - |
| created_at | TEXT | Yes | - | - |

### Indexes

- `idx_lot_assignments_lot`: lot_id, assigned_at; unique=False
- `idx_lot_assignments_zone_time`: zone_id, assigned_at, released_at; unique=False

### Validation constraints

- `CHECK (
        released_at IS NULL OR released_at > assigned_at
    )`

## remediations

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| remediation_id | TEXT | No | 1 | - |
| inspection_id | TEXT | Yes | - | inspections.inspection_id |
| lot_id | TEXT | No | - | inventory_lots.lot_id |
| remediation_type | TEXT | Yes | - | - |
| action_description | TEXT | Yes | - | - |
| remediation_status | TEXT | Yes | - | - |
| assigned_to | TEXT | Yes | - | - |
| started_at | TEXT | No | - | - |
| completed_at | TEXT | No | - | - |
| inventory_impact | TEXT | No | - | - |

### Indexes

- `idx_remediations_inspection`: inspection_id; unique=False
- `sqlite_autoindex_remediations_1`: remediation_id; unique=True

### Validation constraints

- `CHECK (remediation_type IN (
            'ADJUST_TEMPERATURE',
            'ADJUST_HUMIDITY',
            'REPAIR_SENSOR',
            'CLOSE_DOOR',
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

## schema_metadata

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| version | INTEGER | No | 1 | - |
| description | TEXT | Yes | - | - |
| applied_at | TEXT | Yes | - | - |

### Indexes

No explicit indexes.

### Validation constraints

No CHECK constraints detected.

## sensor_outages

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| outage_id | TEXT | No | 1 | - |
| sensor_id | TEXT | Yes | - | sensors.sensor_id |
| outage_start | TEXT | Yes | - | - |
| outage_end | TEXT | No | - | - |
| detected_at | TEXT | Yes | - | - |
| outage_reason | TEXT | Yes | - | - |
| lifecycle_state | TEXT | Yes | - | - |

### Indexes

- `idx_sensor_outages_sensor_time`: sensor_id, outage_start; unique=False
- `sqlite_autoindex_sensor_outages_1`: outage_id; unique=True

### Validation constraints

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

## sensor_readings

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| reading_id | TEXT | No | 1 | - |
| sensor_id | TEXT | Yes | - | sensors.sensor_id |
| recorded_at | TEXT | Yes | - | - |
| temperature_c | REAL | No | - | - |
| humidity_pct | REAL | No | - | - |
| occupancy_count | INTEGER | No | - | - |
| battery_pct | REAL | No | - | - |
| signal_strength | REAL | No | - | - |
| received_at | TEXT | Yes | - | - |

### Indexes

- `idx_readings_sensor_time`: sensor_id, recorded_at; unique=False
- `sqlite_autoindex_sensor_readings_2`: sensor_id, recorded_at; unique=True
- `sqlite_autoindex_sensor_readings_1`: reading_id; unique=True

### Validation constraints

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

## sensor_zone_assignments

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| assignment_id | INTEGER | No | 1 | - |
| sensor_id | TEXT | Yes | - | sensors.sensor_id |
| zone_id | TEXT | Yes | - | zones.zone_id |
| effective_from | TEXT | Yes | - | - |
| effective_to | TEXT | No | - | - |
| assignment_reason | TEXT | No | - | - |
| created_at | TEXT | Yes | - | - |

### Indexes

- `idx_sensor_assignments_zone`: zone_id, effective_from; unique=False
- `idx_sensor_assignments_sensor`: sensor_id, effective_from; unique=False

### Validation constraints

- `CHECK (
        effective_to IS NULL OR effective_to > effective_from
    )`

## sensors

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| sensor_id | TEXT | No | 1 | - |
| sensor_name | TEXT | Yes | - | - |
| sensor_type | TEXT | Yes | - | - |
| manufacturer | TEXT | No | - | - |
| installation_date | TEXT | Yes | - | - |
| calibration_due_date | TEXT | No | - | - |
| lifecycle_state | TEXT | Yes | - | - |
| created_at | TEXT | Yes | - | - |

### Indexes

- `sqlite_autoindex_sensors_1`: sensor_id; unique=True

### Validation constraints

- `CHECK (sensor_type IN ('TEMP', 'HUMIDITY', 'OCCUPANCY', 'MULTI')`
- `CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'FAULTY', 'RETIRED')`

## storage_requirements

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| requirement_id | TEXT | No | 1 | - |
| product_type | TEXT | Yes | - | - |
| min_temperature_c | REAL | Yes | - | - |
| max_temperature_c | REAL | Yes | - | - |
| min_humidity_pct | REAL | Yes | - | - |
| max_humidity_pct | REAL | Yes | - | - |
| max_dwell_hours | REAL | Yes | - | - |
| effective_from | TEXT | Yes | - | - |
| effective_to | TEXT | No | - | - |
| requirement_version | INTEGER | Yes | - | - |
| created_at | TEXT | Yes | - | - |

### Indexes

- `sqlite_autoindex_storage_requirements_2`: product_type, requirement_version; unique=True
- `sqlite_autoindex_storage_requirements_1`: requirement_id; unique=True

### Validation constraints

- `CHECK (min_temperature_c <= max_temperature_c)`
- `CHECK (min_humidity_pct <= max_humidity_pct)`
- `CHECK (min_humidity_pct >= 0 AND max_humidity_pct <= 100)`
- `CHECK (max_dwell_hours > 0)`
- `CHECK (
        effective_to IS NULL OR effective_to > effective_from
    )`

## warehouses

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| warehouse_id | TEXT | No | 1 | - |
| warehouse_name | TEXT | Yes | - | - |
| location | TEXT | Yes | - | - |
| capacity_sq_m | REAL | Yes | - | - |
| warehouse_type | TEXT | Yes | - | - |
| lifecycle_state | TEXT | Yes | - | - |
| created_at | TEXT | Yes | - | - |
| updated_at | TEXT | Yes | - | - |

### Indexes

- `sqlite_autoindex_warehouses_1`: warehouse_id; unique=True

### Validation constraints

- `CHECK (capacity_sq_m > 0)`
- `CHECK (warehouse_type IN ('COLD', 'HOT', 'AMBIENT', 'MIXED')`
- `CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')`

## zones

| Column | Type | Required | Primary Key | Foreign Key |
|---|---|---|---|---|
| zone_id | TEXT | No | 1 | - |
| warehouse_id | TEXT | Yes | - | warehouses.warehouse_id |
| zone_name | TEXT | Yes | - | - |
| zone_type | TEXT | Yes | - | - |
| max_capacity | INTEGER | Yes | - | - |
| lifecycle_state | TEXT | Yes | - | - |
| created_at | TEXT | Yes | - | - |

### Indexes

- `idx_zones_warehouse`: warehouse_id; unique=False
- `sqlite_autoindex_zones_2`: warehouse_id, zone_name; unique=True
- `sqlite_autoindex_zones_1`: zone_id; unique=True

### Validation constraints

- `CHECK (zone_type IN ('COLD', 'HOT', 'AMBIENT', 'FREEZER', 'LOADING')`
- `CHECK (max_capacity > 0)`
- `CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')`

