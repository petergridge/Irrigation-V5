# Irrigation Program Component Tests

This directory contains comprehensive tests for the Irrigation Program custom component for Home Assistant.

## Test Structure

The tests are organized by platform:

- `test_init.py` - Tests for the main component initialization and data structures
- `test_switch.py` - Tests for switch entities (program/zone control switches)
- `test_sensor.py` - Tests for sensor entities (status and timing sensors)
- `test_number.py` - Tests for number entities (watering times, delays, etc.)
- `test_select.py` - Tests for select entities (configuration options)
- `test_time.py` - Tests for time entities (start times)
- `test_text.py` - Tests for text entities (multitime schedules)
- `conftest.py` - Test configuration and fixtures
- `pytest.ini` - Pytest configuration

## Running Tests

### Prerequisites

Make sure you have the required test dependencies installed:

```bash
# From the Home Assistant core directory
uv pip install -r requirements_test_all.txt
```

### Run All Tests

```bash
# From the irrigationprogram/tests directory
pytest
```

### Run Specific Test Files

```bash
# Test only the switch platform
pytest test_switch.py

# Test only the sensor platform
pytest test_sensor.py

# Test initialization
pytest test_init.py
```

### Run Tests with Coverage

```bash
# Run tests with coverage report
pytest --cov=../ --cov-report=html
```

### Run Tests in Verbose Mode

```bash
# Run tests with detailed output
pytest -v
```

## Test Coverage

The tests cover:

1. **Component Setup**: Initialization of the irrigation program and zone data
2. **Platform Entities**: All entity types (switches, sensors, numbers, selects, times, texts)
3. **Entity Attributes**: Proper configuration of entity properties and translations
4. **Entity Functionality**: Basic operations like turning switches on/off, setting values
5. **Data Structures**: Validation of IrrigationData, IrrigationProgram, and IrrigationZoneData classes

## Mocking Strategy

The tests use extensive mocking to isolate the component logic:

- HomeAssistant instance is mocked
- ConfigEntry with runtime data is mocked
- Global state variables are mocked
- External dependencies are mocked

This allows testing the component logic without requiring a full Home Assistant environment.

## Adding New Tests

When adding new functionality to the component:

1. Identify which platform/entity type is affected
2. Add tests to the appropriate test file
3. Use the existing fixtures and mocking patterns
4. Test both positive and negative scenarios
5. Verify entity attributes are set correctly
6. Test entity functionality and state changes

## Test Fixtures

- `mock_hass`: Mock HomeAssistant instance
- `mock_config_entry`: Mock ConfigEntry with runtime data
- `mock_globals`: Automatically mocks global variables

## Notes

- Tests are designed to run independently without external dependencies
- All async operations are properly handled with pytest-asyncio
- Tests validate the component's integration with Home Assistant's entity framework