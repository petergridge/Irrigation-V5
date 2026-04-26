"""pump classs."""

import asyncio
import logging

from homeassistant.components.persistent_notification import async_create
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class MonitorClass:
    """Monitor class to track load time of a device and log if it exceeds start latency."""

    def __init__(self, hass: HomeAssistant, device,start_latency) -> None:  # noqa: D107
        self.hass = hass
        self._device = device
        self._start_latency = start_latency

        hass.async_create_task(self.async_monitor())

    async def async_monitor(self):
        """Monitor the load time of the device and log if it exceeds start latency."""
        msg = None
        loadtime = 0

        for loadtime in range(300):
            #loadtime += 1
            if not self.hass.states.async_available(self._device): #name is no longer avaiable object is now loaded
                break
            await asyncio.sleep(1)
            if loadtime > self._start_latency:
                msg = f"{self._device} load time is ESTIMATED at {loadtime} seconds this exceeds start latency of {self._start_latency}"
        else:
            msg = f"{self._device} load time exceeds 300 seconds"

        if msg:
            _LOGGER.error(msg)
            async_create(
                self.hass,
                message=msg,
                title="Irrigation Controller",
            )

