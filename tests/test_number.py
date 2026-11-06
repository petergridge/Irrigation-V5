"""Tests for the Irrigation Program number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.number import async_setup_entry
import pytest

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry


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
                eco=True,  # Enable eco mode to get wait and repeat numbers
                watering_type="adjustable",
                water=None,
                wait=None,
                repeat=None,
                frequency=None,
                freq=True,  # Enable frequency
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

    # Verify async_add_entities was called
    assert async_add_entities.call_count == 1

    # Get the numbers that were added
    numbers = async_add_entities.call_args[0][0]

    # Should have: start_time, remaining_time, default_run_time, sunrise_offset, sunset_offset,
    # inter_zone_delay, rain_delay_days, repeats, water, wait, repeat, frequency
    # That's 12 numbers total
    assert len(numbers) == 12

    # Check that they are all NumberEntity instances
    for number in numbers:
        assert isinstance(number, NumberEntity)


async def test_number_entities_attributes():
    """Test number entity attributes are set correctly."""
    from custom_components.irrigationprogram.number import (
        Frequency,
        InterZoneDelay,
        RainDelayDays,
        Repeats,
        StartSunriseOffset,
        StartSunsetOffset,
        Water,
        Wait,
        ZoneRepeat,
    )

    # Test Water entity
    water = Water("test_id", "Test Program", "zone1")
    assert water.unique_id == "test_id_zone1_water"
    assert water._attr_attribution == "Irrigation Controller: Test Program, zone1"
    assert water._attr_translation_key == "water"
    assert water._attr_has_entity_name is True
    assert water.native_min_value == 0
    assert water.native_max_value == 30  # Default water_max
    assert water.native_step == 1

    # Test Wait entity (eco mode)
    wait = Wait("test_id", "Test Program", "zone1")
    assert wait.unique_id == "test_id_zone1_wait"
    assert wait._attr_translation_key == "wait"
    assert wait.native_min_value == 0
    assert wait.native_max_value == 120  # Default zone_delay_max

    # Test ZoneRepeat entity (eco mode)
    repeat = ZoneRepeat("test_id", "Test Program", "zone1")
    assert repeat.unique_id == "test_id_zone1_repeat"
    assert repeat._attr_translation_key == "repeat"
    assert repeat.native_min_value == 1
    assert repeat.native_max_value == 10

    # Test Frequency entity
    freq = Frequency("test_id", "Test Program", "zone1")
    assert freq.unique_id == "test_id_zone1_frequency"
    assert freq._attr_translation_key == "frequency"

    # Test InterZoneDelay entity
    delay = InterZoneDelay("test_id", "Test Program")
    assert delay.unique_id == "test_id_inter_zone_delay"
    assert delay._attr_translation_key == "inter_zone_delay"
    assert delay.native_min_value == 0
    assert delay.native_max_value == 120

    # Test RainDelayDays entity
    rain_delay = RainDelayDays("test_id", "Test Program")
    assert rain_delay.unique_id == "test_id_rain_delay_days"
    assert rain_delay._attr_translation_key == "rain_delay_days"
    assert rain_delay.native_min_value == 1
    assert rain_delay.native_max_value == 30

    # Test Repeats entity
    repeats = Repeats("test_id", "Test Program")
    assert repeats.unique_id == "test_id_repeats"
    assert repeats._attr_translation_key == "repeats"
    assert repeats.native_min_value == 1
    assert repeats.native_max_value == 10

    # Test sunrise/sunset offsets
    sunrise = StartSunriseOffset("test_id", "Test Program")
    assert sunrise.unique_id == "test_id_sunrise_offset"
    assert sunrise._attr_translation_key == "sunrise_offset"
    assert sunrise.native_min_value == -240
    assert sunrise.native_max_value == 240

    sunset = StartSunsetOffset("test_id", "Test Program")
    assert sunset.unique_id == "test_id_sunset_offset"
    assert sunset._attr_translation_key == "sunset_offset"
    assert sunset.native_min_value == -240
    assert sunset.native_max_value == 240
