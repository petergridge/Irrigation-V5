"""Tests for the Irrigation Program number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.number import (
    InputNumberProgram,
    Repeat,
    Wait,
    Water,
    async_setup_entry,
)


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
                eco=True,
                watering_type="adjustable",
                water=None,
                wait=None,
                repeat=None,
                frequency=None,
                freq=True,
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


async def test_async_setup_entry_numbers(mock_hass, mock_config_entry):
    """Test number platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 1

    numbers = async_add_entities.call_args[0][0]

    # eco zone: water + wait + repeat = 3
    # zone_count=1 so no inter_zone_delay (condition: zone_count > 1)
    # rain_delay_on=False, repeat=False, start_type="selector" → no program-level numbers
    assert len(numbers) == 3

    for number in numbers:
        assert isinstance(number, NumberEntity)


async def test_number_entities_attributes():
    """Test number entity attributes are set correctly."""
    # Water entity (watering_type="fixed", water_max=30, step=1)
    water = Water("test_id", "Test Program", "zone1", "fixed", 30, 1)
    assert water.unique_id == "test_id_zone1_water"
    assert water._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert water._attr_translation_key == "water"
    assert water._attr_has_entity_name is True
    assert water.native_max_value == 30
    assert water.native_step == 1
    assert water.native_min_value == 1  # min_value is set to step

    # Wait entity (default min_sec="minutes" → max=10)
    wait = Wait("test_id", "Test Program", "zone1")
    assert wait.unique_id == "test_id_zone1_wait"
    assert wait._attr_translation_key == "wait"
    assert wait.native_min_value == 1
    assert wait.native_max_value == 10  # minutes mode

    # Wait entity (min_sec="seconds" → max=120)
    wait_sec = Wait("test_id", "Test Program", "zone1", min_sec="seconds")
    assert wait_sec.native_max_value == 120

    # Repeat entity
    repeat = Repeat("test_id", "Test Program", "zone1")
    assert repeat.unique_id == "test_id_zone1_repeat"
    assert repeat._attr_translation_key == "repeat"
    assert repeat.native_min_value == 1
    assert repeat.native_max_value == 10

    # InputNumberProgram — used for inter_zone_delay, rain_delay_days, repeats, offsets
    delay = InputNumberProgram("test_id", "Test Program", "inter_zone_delay", "sec", 120, 0, 1, "slider")
    assert delay.unique_id == "test_id_inter_zone_delay"
    assert delay._attr_translation_key == "inter_zone_delay"
    assert delay.native_min_value == 0
    assert delay.native_max_value == 120
