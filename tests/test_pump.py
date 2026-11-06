"""Tests for PumpClass valve/switch actuation.

Covers the fix for driving a valve-domain pump (open/close services) and
tolerating a lagging/``unknown`` state: the pump is commanded unless it is
already confirmed to be in the target state.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)

from custom_components.irrigationprogram.pump import PumpClass


def _make_pump(entity_id):
    """Build a PumpClass with a mock hass, neutralising constructor side effects."""
    hass = MagicMock()
    # The constructor schedules async_stop() via async_create_task; close the
    # coroutine without running it so it neither warns nor pollutes call counts.
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
    hass.bus.async_listen = MagicMock()
    hass.services.async_call = AsyncMock()
    pump = PumpClass(hass, entity_id, [], None)
    hass.services.async_call.reset_mock()
    return hass, pump


def _set_state(hass, value):
    """Point hass.states.get at a State with .state == value (or None)."""
    if value is None:
        hass.states.get.return_value = None
    else:
        state = MagicMock()
        state.state = value
        hass.states.get.return_value = state


# --- valve-domain pump: async_start opens ---------------------------------

@pytest.mark.asyncio
async def test_valve_pump_opens_when_closed():
    """A closed valve pump is opened on start (regression: object-vs-string bug)."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, "closed")
    await pump.async_start()
    hass.services.async_call.assert_awaited_once_with(
        "valve", SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: "valve.pump1"}
    )


@pytest.mark.asyncio
async def test_valve_pump_opens_when_unknown():
    """A valve reporting 'unknown' is still opened (lagging-state tolerance)."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, "unknown")
    await pump.async_start()
    hass.services.async_call.assert_awaited_once_with(
        "valve", SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: "valve.pump1"}
    )


@pytest.mark.asyncio
async def test_valve_pump_not_reopened_when_open():
    """An already-open valve is not commanded again on start."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, "open")
    await pump.async_start()
    hass.services.async_call.assert_not_awaited()


# --- valve-domain pump: async_stop closes ---------------------------------

@pytest.mark.asyncio
async def test_valve_pump_closes_when_open():
    """An open valve pump is closed on stop."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, "open")
    await pump.async_stop()
    hass.services.async_call.assert_awaited_once_with(
        "valve", SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: "valve.pump1"}
    )


@pytest.mark.asyncio
async def test_valve_pump_closes_when_unknown():
    """A valve reporting 'unknown' is still closed on stop."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, "unknown")
    await pump.async_stop()
    hass.services.async_call.assert_awaited_once_with(
        "valve", SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: "valve.pump1"}
    )


@pytest.mark.asyncio
async def test_valve_pump_not_reclosed_when_closed():
    """An already-closed valve is not commanded again on stop."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, "closed")
    await pump.async_stop()
    hass.services.async_call.assert_not_awaited()


# --- switch-domain pump: unchanged happy path + unknown tolerance ----------

@pytest.mark.asyncio
async def test_switch_pump_turns_on_when_off():
    """A switch pump that is off is turned on."""
    hass, pump = _make_pump("switch.pump1")
    _set_state(hass, "off")
    await pump.async_start()
    hass.services.async_call.assert_awaited_once_with(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.pump1"}
    )


@pytest.mark.asyncio
async def test_switch_pump_turns_on_when_unknown():
    """A switch reporting 'unknown' is turned on (lagging-state tolerance)."""
    hass, pump = _make_pump("switch.pump1")
    _set_state(hass, "unknown")
    await pump.async_start()
    hass.services.async_call.assert_awaited_once_with(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.pump1"}
    )


@pytest.mark.asyncio
async def test_switch_pump_not_reissued_when_on():
    """An already-on switch is not commanded again on start."""
    hass, pump = _make_pump("switch.pump1")
    _set_state(hass, "on")
    await pump.async_start()
    hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_switch_pump_turns_off_when_on():
    """A switch pump that is on is turned off on stop."""
    hass, pump = _make_pump("switch.pump1")
    _set_state(hass, "on")
    await pump.async_stop()
    hass.services.async_call.assert_awaited_once_with(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.pump1"}
    )


@pytest.mark.asyncio
async def test_switch_pump_not_turned_off_when_off():
    """An already-off switch is not commanded again on stop."""
    hass, pump = _make_pump("switch.pump1")
    _set_state(hass, "off")
    await pump.async_stop()
    hass.services.async_call.assert_not_awaited()


# --- missing entity (state is None) → no action (file idiom) ---------------

@pytest.mark.asyncio
async def test_no_action_when_state_missing():
    """A pump whose entity has no state is left alone (None-guard)."""
    hass, pump = _make_pump("valve.pump1")
    _set_state(hass, None)
    await pump.async_start()
    await pump.async_stop()
    hass.services.async_call.assert_not_awaited()
