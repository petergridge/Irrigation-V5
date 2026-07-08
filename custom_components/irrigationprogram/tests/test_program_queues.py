"""Regression tests for per-program zone queues and queue handling.

Previously the running/remaining zone queues were module-level globals
shared by every program instance, so two programs running concurrently
(interlock disabled) corrupted each other's queues.  These tests are
self-contained: they exercise the queue logic with mocks and do not
require a running Home Assistant instance.

Run from the repo root:
    PYTHONPATH=. python -m pytest \
        custom_components/irrigationprogram/tests/test_program_queues.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.irrigationprogram import globals as irr_globals
from custom_components.irrigationprogram.program import IrrigationProgram


async def _async_noop(*args, **kwargs):
    return None


def _bare_program():
    """An IrrigationProgram without running the HA-dependent __init__."""
    p = IrrigationProgram.__new__(IrrigationProgram)
    p._name = "program_a"
    p._program = MagicMock()
    p._program.pause.async_turn_off = AsyncMock()
    p._zones = []
    p._pumps = []
    p._run_zones = []
    p._remaining_zones = []
    p._running_zones = []
    p._running_zone = None
    p._scheduled = False
    p._state = True
    p._finished = False
    p._paused = False
    p._stop = False
    p._program_remaining = 0
    p.async_schedule_update_ha_state = MagicMock()
    return p


def _queued_entry(name):
    """A minimal stand-in for a queued program."""
    entry = MagicMock()
    entry.name = name
    entry.pause_switch.async_turn_off = AsyncMock()
    return entry


# --------------------------------------------------------------------------
# The shared module-level queues are gone
# --------------------------------------------------------------------------
def test_shared_zone_queues_removed_from_globals():
    """The module-level zone lists that leaked across programs are gone.

    Their continued absence is what guarantees two concurrent programs can
    no longer corrupt each other's queues.
    """
    assert not hasattr(irr_globals, "REMAINING_ZONES")
    assert not hasattr(irr_globals, "RUNNING_ZONES")


def test_program_queues_are_per_instance():
    """Each program owns independent queues."""
    a = _bare_program()
    b = _bare_program()
    a._remaining_zones.append("zone_a")
    a._running_zones.append("zone_b")
    assert b._remaining_zones == []  # B's queues are untouched
    assert b._running_zones == []


def test_queue_properties_expose_instance_lists():
    """Zones remove themselves via the program's queue properties."""
    p = _bare_program()
    assert p.remaining_zones is p._remaining_zones
    assert p.running_zones is p._running_zones


# --------------------------------------------------------------------------
# Program queue is rebuilt, not popped while enumerating
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_turn_off_removes_all_queue_entries_for_program():
    """pop() inside enumerate() skipped the entry after each removal.

    With two consecutive queue entries for the same program, the old code
    removed only the first one; the leftover entry could later be unpaused
    as if it were a distinct queued program.
    """
    p = _bare_program()
    queue = [_queued_entry("program_a"), _queued_entry("program_a")]
    next_program = _queued_entry("program_b")
    queue.append(next_program)

    with patch(
        "custom_components.irrigationprogram.program.QUEUEDPROGRAMS", queue
    ):
        await p.async_turn_off()

    assert [entry.name for entry in queue] == ["program_b"]
    # the next queued program is unpaused exactly once
    next_program.pause_switch.async_turn_off.assert_awaited_once()


# --------------------------------------------------------------------------
# run_monitor_zones: snapshot iteration + guard after the inter-zone delay
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_monitor_survives_queue_drain_during_inter_zone_delay():
    """Queues emptied mid-delay must not crash the monitor loop.

    A zone can be turned off manually while the inter-zone delay is
    counting down.  The old code indexed REMAINING_ZONES[0] after the
    delay without re-checking the queue and raised IndexError; it also
    iterated the live running list while zones mutated it.
    """
    p = _bare_program()
    p._program.parallel = 1  # degree_of_parallel == 1
    p._program.inter_zone_delay.state = 1  # +'ve IZD -> delay branch

    running_zone = MagicMock()
    running_zone.remaining_time.numeric_value = 0  # about to finish
    queued_zone = MagicMock()
    queued_zone.remaining_time.numeric_value = 60
    p._running_zones = [running_zone]
    p._remaining_zones = [queued_zone]

    calls = {"count": 0}

    async def drain_queues(*args, **kwargs):
        # first call is the pre-loop recalculation; on the call made from
        # inside the inter-zone delay, simulate the running zone finishing
        # and the queued zone being cancelled manually
        calls["count"] += 1
        if calls["count"] > 1:
            p._running_zones.clear()
            p._remaining_zones.clear()

    p.calculate_program_remaining = drain_queues
    p.zone_turn_on = AsyncMock()

    result = await p.run_monitor_zones()  # must not raise IndexError

    assert result == []
    # nothing left to start once the queue was drained
    p.zone_turn_on.assert_not_awaited()
