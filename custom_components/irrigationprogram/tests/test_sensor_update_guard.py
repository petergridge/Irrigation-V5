"""Regression tests: sensor async_update before program/zone registration.

During startup or a config-entry reload the sensor platform can poll before
the owning program/zone has registered itself in the PROGRAMS/ZONES globals.
Previously each async_update only assigned ``value`` inside ``if x:`` and
then unconditionally called ``set_value(value)``, raising NameError when the
lookup missed. These tests pin the guard: a missing object is a clean no-op,
and a registered object still propagates its property to set_value.

Self-contained: no live Home Assistant instance required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.irrigationprogram.sensor import (
    DefaultRunTime,
    RemainingTime,
    ZoneDefaultRunTime,
    ZoneRemainingTime,
    ZoneStatus,
)

ZONE_CASES = [
    (ZoneStatus, "status_sensor_value"),
    (ZoneRemainingTime, "remaining_time_value"),
    (ZoneDefaultRunTime, "default_run_time"),
]

PROGRAM_CASES = [
    (RemainingTime, "remaining_time_value"),
    (DefaultRunTime, "default_run_time_value"),
]


def _zone_sensor(cls):
    sensor = cls(MagicMock(), "prog", "zone1", "uid")
    sensor.set_value = AsyncMock()
    return sensor


def _program_sensor(cls):
    sensor = cls(MagicMock(), "prog", "uid")
    sensor.set_value = AsyncMock()
    return sensor


@pytest.mark.parametrize(("cls", "prop"), ZONE_CASES)
@pytest.mark.asyncio
async def test_zone_sensor_update_unregistered_zone_is_noop(cls, prop):
    """async_update must not raise nor write when the zone is unregistered."""
    sensor = _zone_sensor(cls)
    with patch.dict(
        "custom_components.irrigationprogram.sensor.ZONES", {}, clear=True
    ):
        await sensor.async_update()  # must not raise NameError
    sensor.set_value.assert_not_awaited()


@pytest.mark.parametrize(("cls", "prop"), ZONE_CASES)
@pytest.mark.asyncio
async def test_zone_sensor_update_registered_zone_propagates_value(cls, prop):
    """async_update passes the zone property straight through to set_value."""
    sensor = _zone_sensor(cls)
    zone = MagicMock()
    setattr(zone, prop, "expected-value")
    with patch.dict(
        "custom_components.irrigationprogram.sensor.ZONES",
        {"prog.zone1": zone},
        clear=True,
    ):
        await sensor.async_update()
    sensor.set_value.assert_awaited_once_with("expected-value")


@pytest.mark.parametrize(("cls", "prop"), PROGRAM_CASES)
@pytest.mark.asyncio
async def test_program_sensor_update_unregistered_program_is_noop(cls, prop):
    """async_update must not raise nor write when the program is unregistered."""
    sensor = _program_sensor(cls)
    with patch.dict(
        "custom_components.irrigationprogram.sensor.PROGRAMS", {}, clear=True
    ):
        await sensor.async_update()  # must not raise NameError
    sensor.set_value.assert_not_awaited()


@pytest.mark.parametrize(("cls", "prop"), PROGRAM_CASES)
@pytest.mark.asyncio
async def test_program_sensor_update_registered_program_propagates_value(cls, prop):
    """async_update passes the program property straight through to set_value."""
    sensor = _program_sensor(cls)
    program = MagicMock()
    setattr(program, prop, "expected-value")
    with patch.dict(
        "custom_components.irrigationprogram.sensor.PROGRAMS",
        {"prog": program},
        clear=True,
    ):
        await sensor.async_update()
    sensor.set_value.assert_awaited_once_with("expected-value")
