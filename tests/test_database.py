def table_names(conn):
    return {
        row[0] for row in conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()
    }


def test_schema_creates_expected_tables(test_db):
    expected = {
        "warehouses", "zones", "sensors", "sensor_zone_assignments",
        "sensor_readings", "door_events", "inventory_lots",
        "storage_requirements", "lot_zone_assignments", "alarms",
        "alarm_lots", "inspections", "remediations", "sensor_outages",
        "schema_metadata",
    }
    assert expected.issubset(table_names(test_db))


def test_database_integrity_is_ok(test_db):
    assert test_db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_foreign_keys_are_enabled(test_db):
    assert test_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_empty_schema_has_no_foreign_key_violations(test_db):
    assert test_db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_core_tables_have_primary_keys(test_db):
    for table in ("warehouses", "zones", "sensors", "inventory_lots", "alarms"):
        columns = test_db.execute(f'PRAGMA table_info("{table}")').fetchall()
        assert any(column["pk"] for column in columns), f"{table} has no primary key"
