"""Tests for the Irrigation Program select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.select import Frequency, async_setup_entry


class MockHomeAssistant:
    """Mock HomeAssistant for testing."""

    def __init__(self):
        self.data = {}


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
            freq_options=["1", "2", "3"],
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


async def test_async_setup_entry_selects(mock_hass, mock_config_entry):
    """Test select platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 1

    selects = async_add_entities.call_args[0][0]

    # p.freq=False → no program-level frequency
    # zone.freq=False but not p.freq → zone-level frequency added (zone.freq or not p.freq = True)
    assert len(selects) == 1
    assert isinstance(selects[0], SelectEntity)
    assert isinstance(selects[0], Frequency)


async def test_select_entities_attributes():
    """Test Frequency select entity attributes."""
    freq = Frequency("test_id", "Test Program", "zone1", ["1", "2", "7"])

    assert freq.unique_id == "test_id_zone1_frequency"
    assert freq._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert freq._attr_translation_key == "frequency"
    assert freq._attr_has_entity_name is True
    assert freq.options == ["1", "2", "7"]
    assert freq.current_option is None

    # Program-level frequency (no zone name)
    prog_freq = Frequency("test_id", "Test Program", None, ["1", "2"])
    assert prog_freq.unique_id == "test_id_frequency"
    assert prog_freq._attr_attribution == "Irrigation Controller: Test Program"


async def test_select_entity_functionality():
    """Test Frequency select functionality."""
    freq = Frequency("test_id", "Test Program", "zone1", ["1", "2", "7"])

    assert freq.current_option is None

    with patch.object(freq, "async_write_ha_state"):
        await freq.async_select_option("2")
    assert freq.current_option == "2"

    with patch.object(freq, "async_write_ha_state"):
        await freq.async_select_option("7")
    assert freq.current_option == "7"
