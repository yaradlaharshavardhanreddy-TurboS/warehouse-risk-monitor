
-- ============================================================
-- WAREHOUSE ENVIRONMENTAL MONITORING & RISK ALERT SYSTEM
-- Database: SQLite
-- Schema version: 1.0
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1. WAREHOUSE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id TEXT PRIMARY KEY,
    warehouse_name TEXT NOT NULL,
    location TEXT NOT NULL,
    capacity_sq_m REAL NOT NULL CHECK (capacity_sq_m > 0),
    warehouse_type TEXT NOT NULL
        CHECK (warehouse_type IN ('COLD', 'HOT', 'AMBIENT', 'MIXED')),
    lifecycle_state TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ------------------------------------------------------------
-- 2. ZONE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    warehouse_id TEXT NOT NULL,
    zone_name TEXT NOT NULL,
    zone_type TEXT NOT NULL
        CHECK (zone_type IN ('COLD', 'HOT', 'AMBIENT', 'FREEZER', 'LOADING')),
    max_capacity INTEGER NOT NULL CHECK (max_capacity > 0),
    lifecycle_state TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE')),
    created_at TEXT NOT NULL,

    FOREIGN KEY (warehouse_id)
        REFERENCES warehouses(warehouse_id),

    UNIQUE (warehouse_id, zone_name)
);

-- ------------------------------------------------------------
-- 3. SENSOR
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id TEXT PRIMARY KEY,
    sensor_name TEXT NOT NULL,
    sensor_type TEXT NOT NULL
        CHECK (sensor_type IN ('TEMP', 'HUMIDITY', 'OCCUPANCY', 'MULTI')),
    manufacturer TEXT,
    installation_date TEXT NOT NULL,
    calibration_due_date TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (lifecycle_state IN ('ACTIVE', 'INACTIVE', 'FAULTY', 'RETIRED')),
    created_at TEXT NOT NULL
);

-- ------------------------------------------------------------
-- 4. SENSOR-ZONE ASSIGNMENT HISTORY
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sensor_zone_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    assignment_reason TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (sensor_id)
        REFERENCES sensors(sensor_id),

    FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id),

    CHECK (
        effective_to IS NULL OR effective_to > effective_from
    )
);

-- ------------------------------------------------------------
-- 5. SENSOR READING
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    temperature_c REAL,
    humidity_pct REAL,
    occupancy_count INTEGER,
    battery_pct REAL,
    signal_strength REAL,
    received_at TEXT NOT NULL,

    FOREIGN KEY (sensor_id)
        REFERENCES sensors(sensor_id),

    UNIQUE (sensor_id, recorded_at),

    CHECK (
        temperature_c IS NULL OR
        temperature_c BETWEEN -100 AND 150
    ),

    CHECK (
        humidity_pct IS NULL OR
        humidity_pct BETWEEN 0 AND 100
    ),

    CHECK (
        occupancy_count IS NULL OR occupancy_count >= 0
    ),

    CHECK (
        battery_pct IS NULL OR battery_pct BETWEEN 0 AND 100
    )
);

-- ------------------------------------------------------------
-- 6. SENSOR OUTAGE
-- Explicitly records periods with missing sensor data.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sensor_outages (
    outage_id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL,
    outage_start TEXT NOT NULL,
    outage_end TEXT,
    detected_at TEXT NOT NULL,
    outage_reason TEXT NOT NULL
        CHECK (outage_reason IN (
            'POWER_FAILURE',
            'NETWORK_FAILURE',
            'HARDWARE_FAILURE',
            'UNKNOWN'
        )),
    lifecycle_state TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (lifecycle_state IN ('OPEN', 'RESOLVED')),
    
    FOREIGN KEY (sensor_id)
        REFERENCES sensors(sensor_id),

    CHECK (
        outage_end IS NULL OR outage_end > outage_start
    )
);

-- ------------------------------------------------------------
-- 7. DOOR EVENT
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS door_events (
    door_event_id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    door_identifier TEXT NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'OPENED',
            'CLOSED',
            'HELD_OPEN',
            'FORCED_OPEN'
        )),
    event_timestamp TEXT NOT NULL,
    duration_seconds INTEGER,
    recorded_by TEXT NOT NULL DEFAULT 'SYSTEM',

    FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id),

    CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    )
);

-- ------------------------------------------------------------
-- 8. STORAGE REQUIREMENT
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS storage_requirements (
    requirement_id TEXT PRIMARY KEY,
    product_type TEXT NOT NULL,
    min_temperature_c REAL NOT NULL,
    max_temperature_c REAL NOT NULL,
    min_humidity_pct REAL NOT NULL,
    max_humidity_pct REAL NOT NULL,
    max_dwell_hours REAL NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    requirement_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,

    CHECK (min_temperature_c <= max_temperature_c),
    CHECK (min_humidity_pct <= max_humidity_pct),
    CHECK (min_humidity_pct >= 0 AND max_humidity_pct <= 100),
    CHECK (max_dwell_hours > 0),
    CHECK (
        effective_to IS NULL OR effective_to > effective_from
    ),
    UNIQUE (product_type, requirement_version)
);

-- ------------------------------------------------------------
-- 9. INVENTORY LOT
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS inventory_lots (
    lot_id TEXT PRIMARY KEY,
    product_type TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_of_measure TEXT NOT NULL,
    requirement_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    expiry_date TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'RECEIVED'
        CHECK (lifecycle_state IN (
            'RECEIVED',
            'STORED',
            'UNDER_INSPECTION',
            'QUARANTINED',
            'RELEASED',
            'DISPATCHED',
            'EXPIRED'
        )),
    created_at TEXT NOT NULL,

    FOREIGN KEY (requirement_id)
        REFERENCES storage_requirements(requirement_id),

    CHECK (
        expiry_date IS NULL OR expiry_date >= received_at
    )
);

-- ------------------------------------------------------------
-- 10. LOT-ZONE ASSIGNMENT HISTORY
-- Tracks inventory movement and dwell time.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lot_zone_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    released_at TEXT,
    assignment_reason TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (lot_id)
        REFERENCES inventory_lots(lot_id),

    FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id),

    CHECK (
        released_at IS NULL OR released_at > assigned_at
    )
);

-- ------------------------------------------------------------
-- 11. ALARM
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alarms (
    alarm_id TEXT PRIMARY KEY,
    warehouse_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    sensor_id TEXT,
    alarm_type TEXT NOT NULL
        CHECK (alarm_type IN (
            'HIGH_TEMPERATURE',
            'LOW_TEMPERATURE',
            'HIGH_HUMIDITY',
            'LOW_HUMIDITY',
            'HIGH_OCCUPANCY',
            'DOOR_OPEN',
            'SENSOR_OUTAGE',
            'SENSOR_DRIFT',
            'STORAGE_INCOMPATIBILITY'
        )),
    severity TEXT NOT NULL
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    detected_at TEXT NOT NULL,
    description TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (lifecycle_state IN (
            'OPEN',
            'ACKNOWLEDGED',
            'INVESTIGATING',
            'RESOLVED',
            'CLOSED'
        )),
    resolved_at TEXT,

    FOREIGN KEY (warehouse_id)
        REFERENCES warehouses(warehouse_id),

    FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id),

    FOREIGN KEY (sensor_id)
        REFERENCES sensors(sensor_id),

    CHECK (
        resolved_at IS NULL OR resolved_at >= detected_at
    )
);

-- ------------------------------------------------------------
-- 12. ALARM-LOT BRIDGE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alarm_lots (
    alarm_id TEXT NOT NULL,
    lot_id TEXT NOT NULL,
    impact_type TEXT NOT NULL
        CHECK (impact_type IN (
            'TEMPERATURE',
            'HUMIDITY',
            'DWELL_TIME',
            'DOOR_EXPOSURE',
            'STORAGE_INCOMPATIBILITY',
            'OTHER'
        )),
    impact_start TEXT NOT NULL,
    impact_end TEXT,
    impact_details TEXT,

    PRIMARY KEY (alarm_id, lot_id, impact_start),

    FOREIGN KEY (alarm_id)
        REFERENCES alarms(alarm_id),

    FOREIGN KEY (lot_id)
        REFERENCES inventory_lots(lot_id),

    CHECK (
        impact_end IS NULL OR impact_end >= impact_start
    )
);

-- ------------------------------------------------------------
-- 13. INSPECTION
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS inspections (
    inspection_id TEXT PRIMARY KEY,
    alarm_id TEXT NOT NULL,
    inspector_name TEXT NOT NULL,
    inspection_type TEXT NOT NULL
        CHECK (inspection_type IN (
            'QUALITY',
            'MAINTENANCE',
            'INVENTORY',
            'SAFETY'
        )),
    inspection_status TEXT NOT NULL DEFAULT 'SCHEDULED'
        CHECK (inspection_status IN (
            'SCHEDULED',
            'IN_PROGRESS',
            'COMPLETED',
            'CANCELLED'
        )),
    findings TEXT,
    scheduled_at TEXT NOT NULL,
    completed_at TEXT,
    
    FOREIGN KEY (alarm_id)
        REFERENCES alarms(alarm_id),

    CHECK (
        completed_at IS NULL OR completed_at >= scheduled_at
    )
);

-- ------------------------------------------------------------
-- 14. REMEDIATION
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS remediations (
    remediation_id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    lot_id TEXT,
    remediation_type TEXT NOT NULL
        CHECK (remediation_type IN (
            'ADJUST_TEMPERATURE',
            'ADJUST_HUMIDITY',
            'REPAIR_SENSOR',
            'CLOSE_DOOR',
            'RELOCATE_INVENTORY',
            'QUARANTINE_INVENTORY',
            'RECALIBRATE_SENSOR',
            'OTHER'
        )),
    action_description TEXT NOT NULL,
    remediation_status TEXT NOT NULL DEFAULT 'PLANNED'
        CHECK (remediation_status IN (
            'PLANNED',
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED',
            'CANCELLED'
        )),
    assigned_to TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    inventory_impact TEXT,

    FOREIGN KEY (inspection_id)
        REFERENCES inspections(inspection_id),

    FOREIGN KEY (lot_id)
        REFERENCES inventory_lots(lot_id),

    CHECK (
        completed_at IS NULL OR started_at IS NOT NULL
    ),
    CHECK (
        completed_at IS NULL OR completed_at >= started_at
    )
);

-- ------------------------------------------------------------
-- INDEXES FOR QUERY PERFORMANCE
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_zones_warehouse
    ON zones(warehouse_id);

CREATE INDEX IF NOT EXISTS idx_sensor_assignments_sensor
    ON sensor_zone_assignments(sensor_id, effective_from);

CREATE INDEX IF NOT EXISTS idx_sensor_assignments_zone
    ON sensor_zone_assignments(zone_id, effective_from);

CREATE INDEX IF NOT EXISTS idx_readings_sensor_time
    ON sensor_readings(sensor_id, recorded_at);

CREATE INDEX IF NOT EXISTS idx_door_events_zone_time
    ON door_events(zone_id, event_timestamp);

CREATE INDEX IF NOT EXISTS idx_lot_assignments_zone_time
    ON lot_zone_assignments(zone_id, assigned_at, released_at);

CREATE INDEX IF NOT EXISTS idx_lot_assignments_lot
    ON lot_zone_assignments(lot_id, assigned_at);

CREATE INDEX IF NOT EXISTS idx_alarms_zone_time
    ON alarms(zone_id, detected_at);

CREATE INDEX IF NOT EXISTS idx_alarms_status
    ON alarms(lifecycle_state, severity);

CREATE INDEX IF NOT EXISTS idx_alarm_lots_lot
    ON alarm_lots(lot_id);

CREATE INDEX IF NOT EXISTS idx_inspections_alarm
    ON inspections(alarm_id);

CREATE INDEX IF NOT EXISTS idx_remediations_inspection
    ON remediations(inspection_id);

CREATE INDEX IF NOT EXISTS idx_sensor_outages_sensor_time
    ON sensor_outages(sensor_id, outage_start);

-- ------------------------------------------------------------
-- SCHEMA VERSION
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schema_metadata (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_metadata
    (version, description, applied_at)
VALUES
    (1, 'Initial warehouse monitoring database schema',
     strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
