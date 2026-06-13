"""Tests for the Irrigation Program text platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.text import RunTimes, async_setup_entry


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
            start_type="multistart",
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


async def test_async_setup_entry_texts(mock_hass, mock_config_entry):
    """Test text platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    assert async_add_entities.call_count == 1

    texts = async_add_entities.call_args[0][0]

    # start_type="multistart" → RunTimes entity created
    assert len(texts) == 1
    assert isinstance(texts[0], TextEntity)
    assert isinstance(texts[0], RunTimes)


async def test_text_entity_attributes():
    """Test RunTimes text entity attributes."""
    runtimes = RunTimes("test_id", "Test Program")

    assert runtimes.unique_id == "test_id_start_times"
    assert runtimes._attr_attribution == "Irrigation Controller: Test Program"
    assert runtimes.translation_key == "start_times"
    assert runtimes.has_entity_name is True
    assert runtimes.native_value is None


async def test_text_entity_functionality():
    """Test RunTimes text entity functionality."""
    runtimes = RunTimes("test_id", "Test Program")

    assert runtimes.native_value is None

    test_text = "06:00:00,12:00:00,18:00:00"
    with patch.object(runtimes, "async_write_ha_state"):
        await runtimes.async_set_value(test_text)
    assert runtimes.native_value == test_text

    test_text2 = "08:00:00,14:00:00,20:00:00"
    with patch.object(runtimes, "async_write_ha_state"):
        await runtimes.async_set_value(test_text2)
    assert runtimes.native_value == test_text2
