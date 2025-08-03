"""pump classs."""

import asyncio
import logging

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant

# from homeassistant.helpers.event import async_track_state_change_event
from .const import CONST_OFF_DELAY, CONST_ON, CONST_OPEN, CONST_SWITCH

_LOGGER = logging.getLogger(__name__)


class PumpClass:
    """Pump class."""

    def __init__(self, hass: HomeAssistant, pump, zones, program=None) -> None:  # noqa: D107
        self.hass = hass
        self._pump = pump
        self._zones = zones
        self._off_delay = CONST_OFF_DELAY
        self._program = program
        self._cancel = None

        # turn off the pump on start
        hass.async_create_task(self.async_stop())

        self._cancel = hass.bus.async_listen("irrigation_event", self.handle_event)

    async def handle_event(self, event):
        """Inspect irrigation events."""
        if event.data.get("action") == "turn_on_pump":
            delay = int(event.data.get("delay"))
            await asyncio.sleep(delay)
            await self.async_start()

        if event.data.get("action") == "turn_off_pump_all":
            await self.async_stop()

        if event.data.get("action") == "turn_off_pump":
            # Now need to determine if other zones are running that
            # need the pump to remain on.
            for zone in self._zones:
                if self.hass.states.get(zone.zone).state in (
                    CONST_ON,
                    CONST_OPEN,
                ) and zone.zone != event.data.get("device_id"):
                    break
            else:
                await self.async_stop()

    @property
    def zones(self) -> list:
        """Return list of zones."""
        return self._zones

    @property
    def pump(self) -> list:
        """Return pump."""
        return self._pump

    async def async_cancel(self):
        """Stop monitoring."""
        self._cancel()
        self._cancel = None

    async def async_stop(self):
        """Turn off pump."""
        state = self.hass.states.get(self._pump).state
        if state == "on":
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._pump}
            )
        if state == "open":
            await self.hass.services.async_call(
                "valve", SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self._pump}
            )

    async def async_start(self):
        """Turn on the pump."""
        state = self.hass.states.get(self._pump).state
        if state == "off":
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._pump}
            )
        if state == "closed":
            await self.hass.services.async_call(
                "valve", SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: self._pump}
            )
