"""Test configuration for Irrigation Program component."""

import pytest

# Pytest configuration
pytest_plugins = ["pytest_asyncio"]


# Test configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def mock_globals():
    """Mock global variables used by the component."""
    from unittest.mock import patch

    # Mock the globals module
    with (
        patch("custom_components.irrigationprogram.globals.ZONES", {}),
        patch("custom_components.irrigationprogram.globals.PROGRAMS", {}),
        patch("custom_components.irrigationprogram.globals.QUEUEDPROGRAMS", []),
        patch("custom_components.irrigationprogram.globals.RUNNINGPROGRAM", False),
    ):
        yield


@pytest.fixture
def mock_home_assistant():
    """Create a mock HomeAssistant instance for testing."""
    from unittest.mock import MagicMock

    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.states = MagicMock()
    hass.async_available = MagicMock(return_value=True)
    return hass


@pytest.fixture
def mock_config_entry(mock_home_assistant):
    """Create a mock ConfigEntry for testing."""
    from unittest.mock import MagicMock
    from homeassistant.config_entries import ConfigEntry

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.title = "Test Program"
    entry.data = {}
    entry.options = {
        "device_type": "Generic",
        "start_type": "selector",
        "rain_delay": False,
        "rain_behaviour": "stop",
        "interlock": "strict",
        "min_sec": "minutes",
        "latency": 5,
        "start_latency": 60,
        "pause_water_source": False,
        "zones": [
            {
                "zone": "switch.zone1",
                "eco": False,
                "watering_type": "fixed",
                "freq": False,
                "rain_sensor": None,
                "water_adjust": None,
            }
        ],
    }
    entry.runtime_data = None
    return entry
