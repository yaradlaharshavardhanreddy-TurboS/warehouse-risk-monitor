import importlib
import pytest

@pytest.mark.parametrize("module", [
    "app.generator.master_data",
    "app.generator.zone_data",
    "app.generator.sensor_data",
    "app.generator.inventory_data",
    "app.generator.requirement_data",
    "app.generator.sensor_reading_data",
    "app.generator.door_event_data",
])
def test_generator_modules_import(module):
    imported = importlib.import_module(module)
    assert imported is not None
