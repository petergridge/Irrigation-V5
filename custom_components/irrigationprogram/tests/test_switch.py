"""Tests for the Irrigation Program switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.switch import (
    EnableProgram,
    EnableRainDelay,
    EnableZone,
    IgnoreRainSensor,
    ProgramConfig,
    ProgramPause,
    ZoneConfig,
    async_setup_entry,
)
from custom_components.irrigationprogram.zone import Zone


class MockHomeAssistant:
    """Mock HomeAssistant for testing."""

    def __init__(self):
        self.data = {}
        self.config_entries = MagicMock()
        self.states = MagicMock()
        _config = MagicMock()
        _config.time_zone = "UTC"
        self.config = _config

    def async_available(self, entity_id):
        return True


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
            rain_delay_on=True,
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
                rain_sensor="sensor.rain1",
                adjustment=None,
                flow_rate=None,
            )
        ],
    )
    return entry


async def test_async_setup_entry_switches(mock_hass, mock_config_entry):
    """Test switch platform setup."""
    async_add_entities = AsyncMock()

    mock_entity = MagicMock()
    mock_entity.attributes = {"friendly_name": "Zone 1"}
    mock_hass.states.get.return_value = mock_entity

    with patch.object(mock_hass.config_entries, "async_forward_entry_setups", AsyncMock()):
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 2

    switches_call = async_add_entities.call_args_list[0]
    switches = switches_call[0][0]

    # EnableProgram, ProgramConfig, ProgramPause, EnableRainDelay,
    # IgnoreRainSensor (rain_sensor set), EnableZone, ZoneConfig, Zone
    assert len(switches) == 8
    assert isinstance(switches[0], EnableProgram)
    assert isinstance(switches[1], ProgramConfig)
    assert isinstance(switches[2], ProgramPause)
    assert isinstance(switches[3], EnableRainDelay)
    assert isinstance(switches[4], IgnoreRainSensor)
    assert isinstance(switches[5], EnableZone)
    assert isinstance(switches[6], ZoneConfig)
    assert isinstance(switches[7], Zone)


def test_enable_program_switch():
    switch = EnableProgram("test_id", "Test Program")

    assert switch.unique_id == "test_id_enable_program"
    assert switch._attr_attribution == "Irrigation Controller: Test Program"
    assert switch._attr_translation_key == "enable_program"
    assert switch._attr_has_entity_name is True
    assert switch.is_on is False


def test_program_config_switch():
    switch = ProgramConfig("test_id", "Test Program")

    assert switch.unique_id == "test_id_test_program_config"
    assert switch._attr_attribution == "Irrigation Controller: Test Program"
    assert switch._attr_translation_key == "config"
    assert switch._attr_has_entity_name is True
    assert switch.is_on is False


def test_program_pause_switch():
    switch = ProgramPause("test_id", "Test Program")

    assert switch.unique_id == "test_id_test_program_pause"
    assert switch._attr_attribution == "Irrigation Controller: Test Program"
    assert switch._attr_translation_key == "pause"
    assert switch._attr_has_entity_name is True
    assert switch.is_on is False


def test_enable_rain_delay_switch():
    switch = EnableRainDelay("test_id", "Test Program")

    assert switch.unique_id == "test_id_enable_rain_delay"
    assert switch._attr_attribution == "Irrigation Controller: Test Program"
    assert switch._attr_translation_key == "enable_rain_delay"
    assert switch._attr_has_entity_name is True
    assert switch.is_on is False


def test_enable_zone_switch():
    switch = EnableZone("test_id", "Test Program", "zone1")

    assert switch.unique_id == "test_id_zone1_enable_zone"
    assert switch._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert switch._attr_translation_key == "enable_zone"
    assert switch._attr_has_entity_name is True


def test_zone_config_switch():
    switch = ZoneConfig("test_id", "Test Program", "zone1")

    assert switch.unique_id == "test_id_zone1_config"
    assert switch._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert switch._attr_translation_key == "config"
    assert switch._attr_has_entity_name is True
    assert switch.is_on is False


async def test_switch_toggle():
    switch = ProgramConfig("test_id", "Test Program")

    assert switch.is_on is False

    with patch.object(switch, "async_schedule_update_ha_state"):
        await switch.async_turn_on()
        assert switch.is_on is True

        await switch.async_turn_off()
        assert switch.is_on is False

        await switch.async_toggle()
        assert switch.is_on is True

        await switch.async_toggle()
        assert switch.is_on is False


async def test_switch_restore_state():
    switch = ProgramConfig("test_id", "Test Program")

    last_state = MagicMock()
    last_state.state = "on"

    with (
        patch.object(switch, "async_get_last_state", return_value=last_state),
        patch.object(switch, "async_schedule_update_ha_state"),
    ):
        await switch.async_added_to_hass()
        assert switch.is_on is True
