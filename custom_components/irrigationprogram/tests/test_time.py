"""Tests for the Irrigation Program time platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.time import async_setup_entry, starttime


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
            start_type="time",
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


async def test_async_setup_entry_times(mock_hass, mock_config_entry):
    """Test time platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 1

    times = async_add_entities.call_args[0][0]

    assert len(times) == 1
    assert isinstance(times[0], TimeEntity)


async def test_time_entity_attributes():
    """Test starttime entity attributes."""
    start_time = starttime("test_id", "Test Program")

    assert start_time.unique_id == "test_id_start_time"
    assert start_time._attr_attribution == "Irrigation Controller: Test Program"
    assert start_time._attr_translation_key == "start_time"
    assert start_time._attr_has_entity_name is True
    assert start_time.native_value is None


async def test_time_entity_functionality():
    """Test starttime entity functionality."""
    from datetime import time

    start_time = starttime("test_id", "Test Program")

    assert start_time.native_value is None

    test_time = time(6, 30)
    with patch.object(start_time, "async_write_ha_state"):
        await start_time.async_set_value(test_time)
    assert start_time.native_value == test_time

    test_time2 = time(18, 45)
    with patch.object(start_time, "async_write_ha_state"):
        await start_time.async_set_value(test_time2)
    assert start_time.native_value == test_time2
