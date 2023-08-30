'''pump classs'''
import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON

from .const import CONST_SWITCH

CONST_OFF_DELAY = 2

_LOGGER = logging.getLogger(__name__)

class PumpClass:
    ''' pump class'''
    def __init__(self, hass: HomeAssistant, pump, zones) -> None:
        self.hass = hass
        self._pump = pump
        self._zones = zones
        self._stop = False
        self._off_delay = CONST_OFF_DELAY

    async def async_monitor(self, **kwargs):
        '''monitor running zones to determine if pump is required'''
        _LOGGER.debug("Pump Class Started monitoring zones %s", self._zones)
        step = 1
        pump = {ATTR_ENTITY_ID: self._pump}

        def zone_running():
            for zone in self._zones:
                if self.hass.states.get(zone).state == "on":
                    return True
            return False

        #Monitor the required zones
        while not self._stop:

            #check if any of the zones are running
            if zone_running():
                if self.hass.states.get(self._pump).state == 'off':
                    _LOGGER.debug('pump is off, turn on pump %s', pump)
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_ON, pump
                    )

            await asyncio.sleep(step)
            #check if the zone is running, delay incase another zone starts
            if not zone_running():
                await asyncio.sleep(self._off_delay)
                if (
                    self.hass.states.get(self._pump).state == "on"
                    and not zone_running()
                ):
                    _LOGGER.debug("pump is on,  turn off pump %s", pump)
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_OFF, pump
                    )
        # reset for next call
        self._stop = False

    async def async_stop_monitoring(self, **kwargs):
        '''flag turn off pump monitoring'''
        self._stop = True
