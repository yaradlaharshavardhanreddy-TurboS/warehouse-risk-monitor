from app.analytics.alarm_analytics import get_alarm_analytics
from app.analytics.warehouse_analytics import get_warehouse_analytics
from app.analytics.inventory_analytics import get_inventory_analytics
from app.analytics.inspection_analytics import get_inspection_analytics
from app.analytics.remediation_analytics import get_remediation_analytics
from app.analytics.trend_analytics import get_trend_analytics


def test_alarm_analytics_handles_empty_database(test_db):
    result = get_alarm_analytics(test_db)
    assert result["total_alarms"] == 0
    assert result["by_type"] == []
    assert result["by_severity"] == []


def test_warehouse_analytics_handles_empty_database(test_db):
    result = get_warehouse_analytics(test_db)
    assert result["total_warehouses"] == 0
    assert result["warehouse_comparison"] == []


def test_inventory_analytics_handles_empty_database(test_db):
    result = get_inventory_analytics(test_db)
    assert result["total_inventory_lots"] == 0
    assert result["alarm_lot_links"] == 0
    assert result["unique_affected_lots"] == 0
    assert result["lots_affected_by_multiple_alarms"] == 0


def test_inspection_analytics_handles_empty_database(test_db):
    result = get_inspection_analytics(test_db)
    assert result["total_inspections"] == 0
    assert result["completion_percentage"] == 0.0


def test_remediation_analytics_handles_empty_database(test_db):
    result = get_remediation_analytics(test_db)
    assert result["total_remediations"] == 0
    assert result["completion_percentage"] == 0.0


def test_trend_analytics_handles_empty_database(test_db):
    result = get_trend_analytics(test_db)
    assert result["daily_alarm_trends"] == []
    assert result["daily_sensor_trends"] == []
    assert result["daily_door_event_trends"] == []
