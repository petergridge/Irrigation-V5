"""Tests for the Irrigation Program text platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
)
from custom_components.irrigationprogram.text import async_setup_entry


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


async def test_async_setup_entry_texts(mock_hass, mock_config_entry):
    """Test text platform setup."""
    async_add_entities = AsyncMock()

    await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

    # Verify async_add_entities was called
    assert async_add_entities.call_count == 1

    # Get the texts that were added
    texts = async_add_entities.call_args[0][0]

    # Should have: multitime (when start_type is "selector")
    assert len(texts) == 1

    # Check that it's a TextEntity instance
    assert isinstance(texts[0], TextEntity)


async def test_text_entity_attributes():
    """Test text entity attributes are set correctly."""
    from custom_components.irrigationprogram.text import Multitime

    # Test Multitime entity
    multitime = Multitime("test_id", "Test Program")
    assert multitime.unique_id == "test_id_multitime"
    assert multitime._attr_attribution == "Irrigation Controller: Test Program"
    assert multitime._attr_translation_key == "multitime"
    assert multitime._attr_has_entity_name is True
    assert multitime.native_min_length == 0
    assert multitime.native_max_length == 255


async def test_text_entity_functionality():
    """Test text entity functionality."""
    from custom_components.irrigationprogram.text import Multitime

    multitime = Multitime("test_id", "Test Program")

    # Initially should be None or empty
    assert multitime.native_value is None or multitime.native_value == ""

    # Test setting text
    test_text = "6:00,12:00,18:00"
    await multitime.async_set_value(test_text)
    assert multitime.native_value == test_text

    # Test setting another text
    test_text2 = "8:00,14:00,20:00"
    await multitime.async_set_value(test_text2)
    assert multitime.native_value == test_text2
