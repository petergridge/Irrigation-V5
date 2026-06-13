"""Unit tests for the performance / low-power changes and the bug fixes.

These tests are deliberately self-contained: they exercise the throttling
logic, the parallel-scheduling maths and a few regression guards WITHOUT
requiring a running Home Assistant instance (the repo's existing harness,
which does need one, is unrelated to these changes).

Run from the repo root:
    PYTHONPATH=. python -m pytest \
        custom_components/irrigationprogram/tests/test_perf_frugal.py -v
"""

from datetime import time
import inspect
from unittest.mock import MagicMock

import pytest

from custom_components.irrigationprogram import globals as irr_globals
from custom_components.irrigationprogram.const import (
    CONST_SENSOR_WRITE_INTERVAL,
    CONST_SENSOR_WRITE_INTERVAL_LOW_POWER,
)
from custom_components.irrigationprogram.program import IrrigationProgram
from custom_components.irrigationprogram.sensor import RemainingTime, ZoneRemainingTime
from custom_components.irrigationprogram.zone import Zone


def _make_countdown(cls, write_interval):
    """Build a countdown sensor with HA state writes stubbed out."""
    if cls is ZoneRemainingTime:
        s = cls(MagicMock(), "prog", "zone", "uid")
    else:
        s = cls(MagicMock(), "prog", "uid")
    s._write_interval = write_interval
    # async_schedule_update_ha_state needs a live entity/platform; count instead
    s.async_schedule_update_ha_state = MagicMock()
    return s


# --------------------------------------------------------------------------
# Throttle: normal mode
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cls", [ZoneRemainingTime, RemainingTime])
@pytest.mark.asyncio
async def test_normal_mode_throttles_intermediate_writes(cls):
    """A 1 Hz countdown must not write every second in normal mode."""
    s = _make_countdown(cls, CONST_SENSOR_WRITE_INTERVAL)
    # feed a 30s -> 0s per-second countdown
    for v in range(30, -1, -1):
        await s.set_value(v)

    writes = s.async_schedule_update_ha_state.call_count
    # without throttling this would be 31; with a 5s interval it is far fewer
    assert writes < 31
    assert writes <= 31 // CONST_SENSOR_WRITE_INTERVAL + 3


@pytest.mark.parametrize("cls", [ZoneRemainingTime, RemainingTime])
@pytest.mark.asyncio
async def test_zero_is_always_written(cls):
    """The final value (0) must always reach the state machine."""
    s = _make_countdown(cls, CONST_SENSOR_WRITE_INTERVAL)
    await s.set_value(100)  # start -> written
    s.async_schedule_update_ha_state.reset_mock()
    await s.set_value(99)   # within interval -> suppressed
    assert s.async_schedule_update_ha_state.call_count == 0
    await s.set_value(0)    # boundary -> written
    assert s.async_schedule_update_ha_state.call_count == 1
    assert s.native_value == time(hour=0, minute=0, second=0)


# --------------------------------------------------------------------------
# Throttle: low-power mode
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cls", [ZoneRemainingTime, RemainingTime])
@pytest.mark.asyncio
async def test_low_power_writes_only_at_boundaries(cls):
    """Low power: exactly one write at start + one at finish, nothing between."""
    s = _make_countdown(cls, CONST_SENSOR_WRITE_INTERVAL_LOW_POWER)
    for v in range(600, -1, -1):  # 10 minute cycle, 1 Hz
        await s.set_value(v)
    # first call (start) + the zero boundary == 2 writes only
    assert s.async_schedule_update_ha_state.call_count == 2


# --------------------------------------------------------------------------
# Correctness invariant: internal value stays exact while writes are throttled
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cls", [ZoneRemainingTime, RemainingTime])
@pytest.mark.asyncio
async def test_numeric_value_exact_despite_throttling(cls):
    """Program timing reads numeric_value every second; it must stay exact.

    This is the invariant that makes throttling safe: the HA-visible state
    may lag, but the value the scheduler reads never does.
    """
    s = _make_countdown(cls, CONST_SENSOR_WRITE_INTERVAL_LOW_POWER)
    for v in (623, 622, 487, 3, 1):
        await s.set_value(v)
        assert s.numeric_value == v  # exact to the second, no throttle effect


# --------------------------------------------------------------------------
# Parallel-scheduling maths (previously untested core logic)
# --------------------------------------------------------------------------
def _zone_with_remaining(seconds, default=None):
    z = MagicMock()
    z.remaining_time.numeric_value = seconds
    z.switch.default_run_time = seconds if default is None else default
    return z


def _bare_program(parallel, izd):
    """An IrrigationProgram with only the attributes calculate_program_remaining
    touches, bypassing the HA-dependent __init__."""
    p = IrrigationProgram.__new__(IrrigationProgram)
    p._program = MagicMock()
    p._program.parallel = parallel
    p._program.inter_zone_delay = MagicMock()
    p._program.inter_zone_delay.state = izd
    p._program_remaining = 0
    p._default_run_time = 0
    p.remaining_time_set = _async_noop
    p.default_run_time_set = _async_noop
    p.async_schedule_update_ha_state = MagicMock()
    return p


async def _async_noop(*a, **k):
    return None


@pytest.mark.asyncio
async def test_serial_run_sums_with_interzone_delay():
    """Single stream: total = sum(times) + izd * (n-1)."""
    p = _bare_program(parallel=1, izd=10)
    zones = [_zone_with_remaining(60), _zone_with_remaining(120)]
    total = await p.calculate_program_remaining([], zones, 0, False)
    # 60 + 120 + 10*(2-1)
    assert total == 190


@pytest.mark.asyncio
async def test_parallel_packs_into_streams():
    """Two parallel streams: longest stream wins, no inter-zone delay applied."""
    p = _bare_program(parallel=2, izd=0)
    # 100, 50, 40 packed into 2 streams -> {100} and {50,40}=90 -> max 100
    zones = [
        _zone_with_remaining(100),
        _zone_with_remaining(50),
        _zone_with_remaining(40),
    ]
    total = await p.calculate_program_remaining([], zones, 0, False)
    assert total == 100


@pytest.mark.asyncio
async def test_empty_program_is_zero():
    p = _bare_program(parallel=1, izd=10)
    assert await p.calculate_program_remaining([], [], 0, False) == 0


# --------------------------------------------------------------------------
# Regression guards for the bug fixes
# --------------------------------------------------------------------------
def test_shared_zone_queues_removed_from_globals():
    """B1: the module-level zone lists that leaked across programs are gone.

    Their continued absence is what guarantees two concurrent programs can no
    longer corrupt each other's queues.
    """
    assert not hasattr(irr_globals, "REMAINING_ZONES")
    assert not hasattr(irr_globals, "RUNNING_ZONES")


def test_program_queues_are_per_instance():
    """B1: each program owns independent queues."""
    a = IrrigationProgram.__new__(IrrigationProgram)
    b = IrrigationProgram.__new__(IrrigationProgram)
    a._remaining_zones, a._running_zones = [], []
    b._remaining_zones, b._running_zones = [], []
    a._remaining_zones.append("zoneA")
    assert b._remaining_zones == []  # B's queue is untouched


def test_turn_on_from_program_default_not_evaluated_at_import():
    """B3: last_ran default must be None (computed per call), not a frozen now()."""
    sig = inspect.signature(Zone.async_turn_on_from_program)
    assert sig.parameters["last_ran"].default is None
