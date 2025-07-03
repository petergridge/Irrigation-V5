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

from .const import CONST_OFF_DELAY, CONST_SWITCH

_LOGGER = logging.getLogger(__name__)


class PumpClass:
    """Pump class."""

    def __init__(self, hass: HomeAssistant, pump, zones, vent=False) -> None:  # noqa: D107
        self.hass = hass
        self._pump = pump
        self._zones = zones
        self._vent = vent
        self._stop = False
        self._off_delay = CONST_OFF_DELAY

    @property
    def zones(self) -> list:
        """Return list of zones."""
        return self._zones

    @property
    def pump(self) -> list:
        """Return pump."""
        return self._pump

    @property
    def pump_running(self) -> list:
        """Return pump state."""
        return self.hass.states.get(self._pump).state in ("on", "open")

    async def async_monitor(self):
        """Monitor running zones to determine if pump is required."""

        def zone_running():
            return any(
                self.hass.states.get(zone).state in ("on", "open")
                for zone in self._zones
            )

        def pump_running():
            return self.hass.states.get(self._pump).state in ("on", "open")

        # Monitor the required zones
        while not self._stop:
            # check if any of the zones are running
            if zone_running():
                state = self.hass.states.get(self._pump).state
                if state == "off":
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._pump}
                    )
                if state == "closed":
                    await self.hass.services.async_call(
                        "valve", SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: self._pump}
                    )

            # check if the zone is running,
            if not zone_running() and pump_running():
                # delay incase another zone starts
                await asyncio.sleep(self._off_delay)
                # turn off the pump
                if not zone_running():
                    state = self.hass.states.get(self._pump).state
                    if state == "on":
                        await self.hass.services.async_call(
                            CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._pump}
                        )
                    if state == "open":
                        await self.hass.services.async_call(
                            "valve", SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self._pump}
                        )

            await asyncio.sleep(1)
        # reset for next call
        self._stop = False

    async def async_stop_monitoring(self):
        """Flag turn off pump monitoring."""
        self._stop = True
        state = self.hass.states.get(self._pump).state
        if state == "on":
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._pump}
            )
        if state == "open":
            await self.hass.services.async_call(
                "valve", SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self._pump}
            )
        if self._vent:
            await asyncio.sleep(1)
            await self.async_vent_pressure()

    async def async_vent_pressure(self):
        """Open a valve for a few seconds to relive pressure when the pump stops monitoring."""
        if not self.pump_running:
            state = self.hass.states.get(self._zones[0]).state
            if state == "off":
                await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._zones[0]}
                )
            if state == "closed":
                await self.hass.services.async_call(
                    "valve", SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: self._zones[0]}
                )
            await asyncio.sleep(3)
            state = self.hass.states.get(self._zones[0]).state
            if state == "on":
                await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._zones[0]}
                )
            if state == "open":
                await self.hass.services.async_call(
                    "valve", SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self._zones[0]}
                )
