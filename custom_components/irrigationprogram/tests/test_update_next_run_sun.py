"""Regression tests for sun-based start time handling in update_next_run.

When the sun sensor state cannot be parsed, dt_util.parse_datetime returns
None; update_next_run must skip the start-time update instead of raising
NameError on the unbound adjusted_sunrise local.

These tests are self-contained: they build a bare IrrigationProgram with
mocked collaborators and do not need a running Home Assistant instance.

Run from the repo root:
    PYTHONPATH=. python -m pytest \
        custom_components/irrigationprogram/tests/test_update_next_run_sun.py -v
"""

from datetime import time
from unittest.mock import MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.irrigationprogram.program import IrrigationProgram


def _make_program(sun_rising_state):
    """Build a minimal IrrigationProgram without running __init__."""
    prog = object.__new__(IrrigationProgram)

    program = MagicMock()
    program.sunrise_offset.state = "10"
    program.sunset_offset = None
    prog._program = program

    hass = MagicMock()
    sun_state = MagicMock()
    sun_state.state = sun_rising_state
    hass.states.get.return_value = sun_state
    prog._hass = hass
    prog.hass = hass

    # Stop update_next_run before the zone/run-time recalculation:
    # only the sun handling at the top is under test here.
    prog._paused = True
    prog._zones = []
    return prog


@pytest.mark.asyncio
async def test_unparseable_sunrise_does_not_raise():
    """An unparseable sun sensor state must not crash update_next_run."""
    prog = _make_program("not-a-datetime")

    # Before the fix this raised NameError: 'adjusted_sunrise' referenced
    # before assignment.
    await prog.update_next_run()

    prog.hass.async_create_task.assert_not_called()
    prog._program.start_time.async_set_value.assert_not_called()


@pytest.mark.asyncio
async def test_valid_sunrise_schedules_start_time_update():
    """A valid sun sensor state schedules the start-time update with the
    offset-adjusted local time (seconds/microseconds stripped)."""
    dt_util.set_default_time_zone(dt_util.UTC)

    # 05:30 UTC + 10 minute offset -> 05:40 local, seconds truncated.
    prog = _make_program("2026-06-21T05:30:00+00:00")

    await prog.update_next_run()

    assert prog.hass.async_create_task.call_count == 1
    prog._program.start_time.async_set_value.assert_called_once_with(
        time(5, 40)
    )
