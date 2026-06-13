"""Tests for the Irrigation Program sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.const import (
    CONST_ADJUSTED_OFF,
    CONST_CLOSED,
    CONST_CONTROLLER_DISABLED,
    CONST_DISABLED,
    CONST_ECO,
    CONST_NO_WATER_SOURCE,
    CONST_OFF,
    CONST_ON,
    CONST_OPEN,
    CONST_PENDING,
    CONST_PROGRAM_DISABLED,
    CONST_RAINING,
    CONST_UNAVAILABLE,
    CONST_ZONE_DISABLED,
)
from custom_components.irrigationprogram.sensor import (
    DefaultRunTime,
    RemainingTime,
    ZoneDefaultRunTime,
    ZoneLastRan,
    ZoneNextRun,
    ZoneRemainingTime,
    ZoneStatus,
    async_setup_entry,
)


class MockHomeAssistant:
    """Mock HomeAssistant for testing."""

    def __init__(self):
        self.data = {}
        _config = MagicMock()
        _config.time_zone = "UTC"
        self.config = _config


@pytest.fixture
def mock_hass():
    return MockHomeAssistant()


@pytest.fixture
def mock_config_entry():
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.runtime_data = IrrigationData(
        program=IrrigationProgram(
            name="Test Program",
            switch=None,
            modified="",
            pause=None,
            rain_delay_on=False,
            pump=None,
            flow_sensor=None,
            water_source=None,
            rain_delay=None,
            rain_delay_days=None,
            unique_id="test_id",
            config=None,
            start_time=None,
            remaining_time=None,
            default_run_time=None,
            multitime=None,
            sunrise_offset=None,
            sunset_offset=None,
            start_type="selector",
            frequency=None,
            freq_options=[],
            freq=False,
            repeat=False,
            repeats=None,
            rain_behaviour="stop",
            enabled=None,
            controller_type="Generic",
            inter_zone_delay=None,
            interlock="strict",
            zone_count=1,
            min_sec="minutes",
            water_max=30,
            water_step=1,
            zone_delay_max=120,
            parallel=1,
            pump_delay=1,
            card_yaml=False,
        ),
        zone_data=[
            IrrigationZoneData(
                zone="switch.zone1",
                switch=None,
                type="switch",
                name="zone1",
                config=None,
                eco=False,
                watering_type="fixed",
                water=None,
                wait=None,
                repeat=None,
                frequency=None,
                freq=False,
                ignore_sensors=None,
                enabled=None,
                status=None,
                next_run=None,
                last_ran=None,
                remaining_time=None,
                default_run_time=None,
                rain_sensor=None,
                adjustment=None,
                flow_rate=None,
            )
        ],
    )
    return entry


async def test_async_setup_entry_sensors(mock_hass, mock_config_entry):
    """Test sensor platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 1

    sensors = async_add_entities.call_args[0][0]

    # RemainingTime, DefaultRunTime, ZoneStatus, ZoneNextRun, ZoneLastRan, ZoneRemainingTime, ZoneDefaultRunTime
    assert len(sensors) == 7
    assert isinstance(sensors[0], RemainingTime)
    assert isinstance(sensors[1], DefaultRunTime)
    assert isinstance(sensors[2], ZoneStatus)
    assert isinstance(sensors[3], ZoneNextRun)
    assert isinstance(sensors[4], ZoneLastRan)
    assert isinstance(sensors[5], ZoneRemainingTime)
    assert isinstance(sensors[6], ZoneDefaultRunTime)


def test_remaining_time_sensor():
    mock_hass = MockHomeAssistant()
    sensor = RemainingTime(mock_hass, "Test Program", "test_id")

    assert sensor.unique_id == "test_id_remaining_time"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program"
    assert sensor._attr_translation_key == "remaining_time"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.DATE


def test_default_run_time_sensor():
    mock_hass = MockHomeAssistant()
    sensor = DefaultRunTime(mock_hass, "Test Program", "test_id")

    assert sensor.unique_id == "test_id_default_run_time"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program"
    assert sensor._attr_translation_key == "default_run_time"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.DATE


def test_zone_status_sensor():
    mock_hass = MockHomeAssistant()
    sensor = ZoneStatus(mock_hass, "Test Program", "zone1", "test_id")

    assert sensor.unique_id == "test_id_zone1_status"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert sensor._attr_translation_key == "zone_status"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.ENUM

    expected_options = [
        CONST_ADJUSTED_OFF,
        CONST_CLOSED,
        CONST_CONTROLLER_DISABLED,
        CONST_DISABLED,
        CONST_ECO,
        CONST_NO_WATER_SOURCE,
        CONST_OFF,
        CONST_ON,
        CONST_OPEN,
        CONST_PENDING,
        CONST_PROGRAM_DISABLED,
        CONST_RAINING,
        CONST_UNAVAILABLE,
        CONST_ZONE_DISABLED,
        "paused",
    ]
    assert sensor.options == expected_options


def test_zone_next_run_sensor():
    mock_hass = MockHomeAssistant()
    sensor = ZoneNextRun(mock_hass, "Test Program", "zone1", "test_id")

    assert sensor.unique_id == "test_id_zone1_next_run"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert sensor._attr_translation_key == "zone_next_run"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.TIMESTAMP


def test_zone_last_ran_sensor():
    mock_hass = MockHomeAssistant()
    sensor = ZoneLastRan(mock_hass, "Test Program", "zone1", "test_id")

    assert sensor.unique_id == "test_id_zone1_last_ran"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert sensor._attr_translation_key == "zone_last_ran"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.TIMESTAMP


def test_zone_remaining_time_sensor():
    mock_hass = MockHomeAssistant()
    sensor = ZoneRemainingTime(mock_hass, "Test Program", "zone1", "test_id")

    assert sensor.unique_id == "test_id_zone1_remaining_time"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert sensor._attr_translation_key == "remaining_time"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.DATE


def test_zone_default_run_time_sensor():
    mock_hass = MockHomeAssistant()
    sensor = ZoneDefaultRunTime(mock_hass, "Test Program", "zone1", "test_id")

    assert sensor.unique_id == "test_id_zone1_default_run_time"
    assert sensor._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert sensor._attr_translation_key == "default_run_time"
    assert sensor._attr_has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.DATE


async def test_zone_status_sensor_update():
    import custom_components.irrigationprogram.sensor as sensor_mod

    mock_hass = MockHomeAssistant()
    zone_sensor = ZoneStatus(mock_hass, "Test Program", "zone1", "test_id")

    mock_zone = MagicMock()
    mock_zone.status_sensor_value = "on"

    with patch.dict(sensor_mod.ZONES, {"Test Program.zone1": mock_zone}):
        with patch.object(zone_sensor, "async_schedule_update_ha_state"):
            await zone_sensor.async_update()
        assert zone_sensor.native_value == "on"

        mock_zone.status_sensor_value = "off"
        with patch.object(zone_sensor, "async_schedule_update_ha_state"):
            await zone_sensor.async_update()
        assert zone_sensor.native_value == "off"
