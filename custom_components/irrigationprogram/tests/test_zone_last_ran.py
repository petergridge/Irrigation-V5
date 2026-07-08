"""Regression test for the last_ran default of Zone.async_turn_on_from_program.

The parameter default must not be a call to ``dt_util.now()``: Python
evaluates default arguments once, at import time, so a literal timestamp
default would freeze for every call that omits the argument. The default is
``None`` and the current local time is computed inside the function body,
per call.

Self-contained: no running Home Assistant instance is required. The test
drives the real coroutine against a minimal stand-in object, with ``repeat``
set to 0 so the watering loop is skipped and execution reaches the block
that stores ``last_ran``.

Run from the repo root:
    PYTHONPATH=. python -m pytest \
        custom_components/irrigationprogram/tests/test_zone_last_ran.py -v
"""

from datetime import datetime

import pytest
from homeassistant.util import dt as dt_util

from custom_components.irrigationprogram.zone import Zone


class _MinimalZone:
    """Just enough surface for the reachable path of the coroutine."""

    ignore_sensors = True
    repeat = 0

    async def status_sensor_set(self, *args, **kwargs):
        return None

    async def sensor_last_ran_set(self, *args, **kwargs):
        return None

    async def remaining_time_set(self, *args, **kwargs):
        return None

    async def async_turn_off_zone_natural(self, *args, **kwargs):
        return None

    def async_schedule_update_ha_state(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_omitted_last_ran_uses_fresh_now():
    """Omitting last_ran stores the current local time, not a frozen value."""
    zone = _MinimalZone()

    before = dt_util.as_local(dt_util.now())
    await Zone.async_turn_on_from_program(zone)
    after = dt_util.as_local(dt_util.now())

    assert isinstance(zone._last_ran, datetime)
    # A time computed inside the call falls within the bracket; an
    # import-time-frozen default would predate `before`.
    assert before <= zone._last_ran <= after


@pytest.mark.asyncio
async def test_explicit_last_ran_is_preserved():
    """An explicit last_ran is stored unchanged (guard only fires on None)."""
    zone = _MinimalZone()
    supplied = dt_util.as_local(dt_util.now()).replace(year=2000)

    await Zone.async_turn_on_from_program(zone, last_ran=supplied)

    assert zone._last_ran == supplied
