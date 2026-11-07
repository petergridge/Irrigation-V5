"""Tests for delayed solenoid confirmation."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.irrigationprogram.zone import Zone


@pytest.fixture
def zone():
    program = SimpleNamespace(
        latency=0, pump=None, pump_delay=0, controller_type="generic", min_sec="seconds",
        continue_on_unexpected_state=False,
    )
    data = SimpleNamespace(
        zone="switch.valve", type="switch", eco=False, watering_type="time",
        water=SimpleNamespace(value=1), wait=None, repeat=None,
    )
    zone = Zone("id", "Garden", "valve", "Valve", data, program)
    zone.hass = MagicMock()
    zone.hass.services.async_call = AsyncMock()
    zone.hass.async_create_task.side_effect = asyncio.create_task
    zone.entity_id = "switch.zone"
    zone._attr_name = "Valve"
    zone.hass.states.get.return_value = SimpleNamespace(state="off")
    return zone


@pytest.mark.asyncio
@pytest.mark.parametrize(("expected", "state"), [(True, "on"), (True, "open"), (False, "off"), (False, "closed")])
async def test_late_confirmation(zone, expected, state):
    with (
        patch("custom_components.irrigationprogram.zone.async_create") as notify,
        patch("custom_components.irrigationprogram.zone.async_dismiss") as dismiss,
    ):
        if expected:
            await zone.check_is_on()
        else:
            zone.hass.states.get.return_value.state = "on"
            await zone.check_is_off()
        assert "cannot confirm" in notify.call_args.kwargs["message"]
        zone.hass.states.get.return_value.state = state
        await zone._latency_task
    assert "now confirmed" in notify.call_args.kwargs["message"]
    dismiss.assert_called_with(zone.hass, "irrigation_latency")
    assert zone.hass.bus.async_fire.call_args.args[1]["action"] == "latency_cleared"


@pytest.mark.asyncio
async def test_close_after_unconfirmed_open(zone):
    await zone.async_solenoid_turn_on()
    assert zone._solenoid_commanded_open
    assert not zone._solenoid_open_confirmed
    zone.hass.services.async_call.reset_mock()
    await zone.async_solenoid_turn_off()
    zone.hass.services.async_call.assert_awaited_once_with(
        "switch", "turn_off", {"entity_id": "switch.valve"}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("expected", [True, False])
@pytest.mark.parametrize(("latency", "timeout"), [(0, 30), (10, 40)])
async def test_settle_timeout(zone, expected, latency, timeout):
    zone._latency = latency
    zone.hass.states.get.return_value.state = "off" if expected else "on"
    now = datetime.now()
    clock = MagicMock()
    clock.now.side_effect = [now, now, now + timedelta(seconds=timeout + 1)]
    with (
        patch("custom_components.irrigationprogram.zone.datetime", clock),
        patch("custom_components.irrigationprogram.zone.asyncio.sleep", AsyncMock()),
        patch("custom_components.irrigationprogram.zone.async_create") as notify,
        patch("custom_components.irrigationprogram.zone.async_dismiss"),
    ):
        await zone.recheck_latency(expected)
    assert f"after {timeout} seconds, check the valve" in notify.call_args.kwargs["message"]
    zone.hass.services.async_call.assert_awaited_once()
    assert not any(
        call.args[1].get("action") == "latency_cleared"
        for call in zone.hass.bus.async_fire.call_args_list
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["aborted", "paused"])
async def test_settle_stops(zone, status):
    zone._aborted = status == "aborted"
    zone._status = "paused" if status == "paused" else "off"
    with patch("custom_components.irrigationprogram.zone.async_create") as notify:
        await zone.recheck_latency(True)
    notify.assert_not_called()
    zone.hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["async_solenoid_turn_on", "async_solenoid_turn_off", "async_will_remove_from_hass"])
async def test_new_command_cancels_settle(zone, command):
    task = asyncio.create_task(asyncio.Event().wait())
    zone._latency_task = task
    await getattr(zone, command)()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert zone._latency_task is None


@pytest.mark.asyncio
async def test_missing_state_keeps_checking(zone):
    zone.hass.states.get.return_value = None

    async def closed(_seconds):
        zone.hass.states.get.return_value = SimpleNamespace(state="closed")

    with (
        patch("custom_components.irrigationprogram.zone.asyncio.sleep", closed),
        patch("custom_components.irrigationprogram.zone.async_create") as notify,
        patch("custom_components.irrigationprogram.zone.async_dismiss"),
    ):
        await zone.recheck_latency(False)
    assert "now confirmed off" in notify.call_args.kwargs["message"]
    zone.hass.services.async_call.assert_awaited_once()
    assert not zone._solenoid_commanded_open
    assert not zone._solenoid_open_confirmed
