"""Tests for the Irrigation Program component."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.irrigationprogram import (
    IrrigationData,
    IrrigationProgram,
    IrrigationZoneData,
    async_setup_entry,
)
from custom_components.irrigationprogram.const import (
    ATTR_DEVICE_TYPE,
    ATTR_FLOW_SENSOR,
    ATTR_INTERLOCK,
    ATTR_LATENCY,
    ATTR_MIN_SEC,
    ATTR_PAUSE_WATER_SOURCE,
    ATTR_PUMP,
    ATTR_RAIN_BEHAVIOUR,
    ATTR_RAIN_DELAY,
    ATTR_RAIN_SENSOR,
    ATTR_START_LATENCY,
    ATTR_START_TYPE,
    ATTR_WATER_ADJUST,
    ATTR_WATER_SOURCE,
    ATTR_ZONES,
    ATTR_ZONE,
    DOMAIN,
)


class MockHomeAssistant:
    """Mock HomeAssistant for testing."""

    def __init__(self):
        self.data = {}
        self.config_entries = MagicMock()
        self.states = MagicMock()

    def async_available(self, entity_id):
        """Mock async_available."""
        return True


class MockDataUpdateCoordinator(DataUpdateCoordinator):
    """Mock DataUpdateCoordinator for testing."""

    def __init__(self, hass, weather_data=None):
        super().__init__(hass, logger=MagicMock(), name="test", update_interval=None)
        self.data = weather_data or MagicMock()


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    return MockHomeAssistant()


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.title = "Test Program"
    entry.data = {}
    entry.options = {
        ATTR_DEVICE_TYPE: "Generic",
        ATTR_START_TYPE: "selector",
        ATTR_RAIN_DELAY: False,
        ATTR_RAIN_BEHAVIOUR: "stop",
        ATTR_INTERLOCK: "strict",
        ATTR_MIN_SEC: "minutes",
        ATTR_LATENCY: 5,
        ATTR_START_LATENCY: 60,
        ATTR_PAUSE_WATER_SOURCE: False,
        ATTR_ZONES: [
            {
                ATTR_ZONE: "switch.zone1",
                "eco": False,
                "watering_type": "fixed",
                "freq": False,
                ATTR_RAIN_SENSOR: None,
                ATTR_WATER_ADJUST: None,
            }
        ],
    }
    entry.runtime_data = None
    return entry


async def test_async_setup_entry_basic(mock_hass, mock_config_entry):
    """Test basic async_setup_entry functionality."""
    # Mock the required dependencies
    with (
        patch("custom_components.irrigationprogram.asyncio.sleep"),
        patch.object(mock_hass.states, "async_available", return_value=True),
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
        patch(
            "homeassistant.config_entries.async_forward_entry_setups"
        ) as mock_forward,
    ):
        # Call async_setup_entry
        result = await async_setup_entry(mock_hass, mock_config_entry, AsyncMock())

        # Verify the result
        assert result is True

        # Verify that platform setups were called
        assert mock_forward.call_count == 2

        # Verify runtime_data was set
        assert mock_config_entry.runtime_data is not None
        assert isinstance(mock_config_entry.runtime_data, IrrigationData)

        # Verify program data
        program = mock_config_entry.runtime_data.program
        assert isinstance(program, IrrigationProgram)
        assert program.name == "Test Program"
        assert program.controller_type == "Generic"
        assert program.rain_behaviour == "stop"

        # Verify zone data
        zones = mock_config_entry.runtime_data.zone_data
        assert len(zones) == 1
        assert isinstance(zones[0], IrrigationZoneData)
        assert zones[0].zone == "switch.zone1"


async def test_irrigation_program_initialization(mock_config_entry):
    """Test IrrigationProgram dataclass initialization."""
    config = {
        ATTR_DEVICE_TYPE: "Generic",
        ATTR_START_TYPE: "time",
        ATTR_RAIN_DELAY: True,
        ATTR_RAIN_BEHAVIOUR: "continue",
        ATTR_INTERLOCK: "flexible",
        ATTR_MIN_SEC: "seconds",
        ATTR_LATENCY: 10,
        ATTR_START_LATENCY: 120,
        ATTR_PAUSE_WATER_SOURCE: True,
        ATTR_PUMP: "switch.pump1",
        ATTR_FLOW_SENSOR: "sensor.flow1",
        ATTR_WATER_SOURCE: "sensor.water1",
    }

    program = IrrigationProgram(
        name="Test Program",
        switch=None,
        modified="",
        pause=None,
        rain_delay_on=config.get(ATTR_RAIN_DELAY, False),
        pump=config.get(ATTR_PUMP),
        flow_sensor=config.get(ATTR_FLOW_SENSOR),
        water_source=config.get(ATTR_WATER_SOURCE),
        rain_delay=None,
        rain_delay_days=None,
        unique_id="test_unique_id",
        config=None,
        start_time=None,
        remaining_time=None,
        default_run_time=None,
        multitime=None,
        sunrise_offset=None,
        sunset_offset=None,
        start_type=config.get(ATTR_START_TYPE, "selector"),
        frequency=None,
        freq_options=[],
        freq=False,
        repeat=False,
        repeats=None,
        rain_behaviour=config.get(ATTR_RAIN_BEHAVIOUR, "stop"),
        enabled=None,
        controller_type=config.get(ATTR_DEVICE_TYPE, "Generic"),
        inter_zone_delay=None,
        interlock=config.get(ATTR_INTERLOCK, "strict"),
        zone_count=1,
        min_sec=config.get(ATTR_MIN_SEC, "minutes"),
        water_max=30,
        water_step=1,
        zone_delay_max=120,
        parallel=1,
        pump_delay=1,
        card_yaml=False,
        latency=config.get(ATTR_LATENCY, 5),
        start_latency=config.get(ATTR_START_LATENCY, 60),
        water_source_pause=config.get(ATTR_PAUSE_WATER_SOURCE, False),
    )

    assert program.name == "Test Program"
    assert program.controller_type == "Generic"
    assert program.start_type == "time"
    assert program.rain_behaviour == "continue"
    assert program.interlock == "flexible"
    assert program.min_sec == "seconds"
    assert program.latency == 10
    assert program.start_latency == 120
    assert program.water_source_pause is True
    assert program.pump == "switch.pump1"
    assert program.flow_sensor == "sensor.flow1"
    assert program.water_source == "sensor.water1"


async def test_irrigation_zone_data_initialization():
    """Test IrrigationZoneData dataclass initialization."""
    zone_data = IrrigationZoneData(
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
        rain_sensor="sensor.rain1",
        adjustment="sensor.adjust1",
        flow_rate=None,
    )

    assert zone_data.zone == "switch.zone1"
    assert zone_data.type == "switch"
    assert zone_data.name == "zone1"
    assert zone_data.eco is True
    assert zone_data.watering_type == "adjustable"
    assert zone_data.freq is True
    assert zone_data.rain_sensor == "sensor.rain1"
    assert zone_data.adjustment == "sensor.adjust1"


async def test_irrigation_data_structure(mock_config_entry):
    """Test IrrigationData structure."""
    program = IrrigationProgram(
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
    )

    zone_data = [
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
    ]

    irrigation_data = IrrigationData(program, zone_data)

    assert irrigation_data.program.name == "Test Program"
    assert len(irrigation_data.zone_data) == 1
    assert irrigation_data.zone_data[0].zone == "switch.zone1"


def test_exclude_function(mock_hass):
    """Test the exclude function for config flow."""
    from custom_components.irrigationprogram import exclude

    # Mock config entries
    mock_entry1 = MagicMock()
    mock_entry1.state.name = "ConfigEntryState.LOADED"
    mock_entry1.runtime_data = MagicMock()
    mock_entry1.runtime_data.program = MagicMock()
    mock_entry1.runtime_data.program.switch = MagicMock()
    mock_entry1.runtime_data.program.switch.entity_id = "switch.program1"
    mock_entry1.runtime_data.program.enabled = MagicMock()
    mock_entry1.runtime_data.program.enabled.entity_id = "switch.program1_enabled"
    mock_entry1.runtime_data.program.config = MagicMock()
    mock_entry1.runtime_data.program.config.entity_id = "switch.program1_config"
    mock_entry1.runtime_data.program.start_time = MagicMock()
    mock_entry1.runtime_data.program.start_time.entity_id = "time.program1_start"
    mock_entry1.runtime_data.program.remaining_time = MagicMock()
    mock_entry1.runtime_data.program.remaining_time.entity_id = (
        "sensor.program1_remaining"
    )
    mock_entry1.runtime_data.program.default_run_time = MagicMock()
    mock_entry1.runtime_data.program.default_run_time.entity_id = (
        "sensor.program1_default"
    )
    mock_entry1.runtime_data.zone_data = []

    with patch.object(
        mock_hass.config_entries, "async_entries", return_value=[mock_entry1]
    ):
        excluded = exclude(mock_hass)

        expected = [
            "switch.program1",
            "switch.program1_enabled",
            "switch.program1_config",
            "time.program1_start",
            "sensor.program1_remaining",
            "sensor.program1_default",
        ]

        assert excluded == expected
