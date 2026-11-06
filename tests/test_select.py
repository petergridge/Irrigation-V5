"""Tests for the Irrigation Program select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.select import async_setup_entry


class MockHomeAssistant:
    """Mock HomeAssistant for testing."""

    def __init__(self):
        self.data = {}


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    return MockHomeAssistant()


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry with runtime data."""
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


async def test_async_setup_entry_selects(mock_hass, mock_config_entry):
    """Test select platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    # Verify async_add_entities was called
    assert async_add_entities.call_count == 1

    # Get the selects that were added
    selects = async_add_entities.call_args[0][0]

    # Should have: start_type, rain_behaviour, interlock, min_sec, watering_type
    # That's 5 selects total
    assert len(selects) == 5

    # Check that they are all SelectEntity instances
    for select in selects:
        assert isinstance(select, SelectEntity)


async def test_select_entities_attributes():
    """Test select entity attributes are set correctly."""
    from custom_components.irrigationprogram.select import (
        Interlock,
        MinSec,
        RainBehaviour,
        StartType,
        WateringType,
    )

    # Test StartType entity
    start_type = StartType("test_id", "Test Program")
    assert start_type.unique_id == "test_id_start_type"
    assert start_type._attr_attribution == "Irrigation Controller: Test Program"
    assert start_type._attr_translation_key == "start_type"
    assert start_type._attr_has_entity_name is True
    assert start_type.options == ["selector", "time", "sunrise", "sunset"]

    # Test RainBehaviour entity
    rain_behav = RainBehaviour("test_id", "Test Program")
    assert rain_behav.unique_id == "test_id_rain_behaviour"
    assert rain_behav._attr_translation_key == "rain_behaviour"
    assert rain_behav.options == ["stop", "continue", "delay"]

    # Test Interlock entity
    interlock = Interlock("test_id", "Test Program")
    assert interlock.unique_id == "test_id_interlock"
    assert interlock._attr_translation_key == "interlock"
    assert interlock.options == ["strict", "flexible", "none"]

    # Test MinSec entity
    min_sec = MinSec("test_id", "Test Program")
    assert min_sec.unique_id == "test_id_min_sec"
    assert min_sec._attr_translation_key == "min_sec"
    assert min_sec.options == ["minutes", "seconds"]

    # Test WateringType entity
    watering_type = WateringType("test_id", "Test Program", "zone1")
    assert watering_type.unique_id == "test_id_zone1_watering_type"
    assert (
        watering_type._attr_attribution == "Irrigation Controller: Test Program, zone1"
    )
    assert watering_type._attr_translation_key == "watering_type"
    assert watering_type._attr_has_entity_name is True
    assert watering_type.options == ["fixed", "adjustable", "sensor"]


async def test_select_entity_functionality():
    """Test select entity selection functionality."""
    from custom_components.irrigationprogram.select import StartType

    select = StartType("test_id", "Test Program")

    # Initially should be None or default
    assert select.current_option is None

    # Test selecting an option
    await select.async_select_option("time")
    assert select.current_option == "time"

    # Test selecting another option
    await select.async_select_option("sunrise")
    assert select.current_option == "sunrise"
