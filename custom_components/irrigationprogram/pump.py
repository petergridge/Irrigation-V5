import logging
import asyncio
from .const import (
    CONST_SWITCH,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
_LOGGER = logging.getLogger(__name__)

class pumpclass:

    def __init__(self, hass, pump, zones):
        self.hass    = hass
        self._pump   = pump
        self._zones  = zones

    async def async_monitor(self, **kwargs):

        # loop test if the zones are running
        # if none are running turn off the pump
        x = True
        step = 2
        count = 0
        PUMP = {ATTR_ENTITY_ID: self._pump}
        ''' endless loop, not sure if this is good practive'''
        while x == True:
            zone_running = False
            ''' check if any of the zones are running'''

            for zone in self._zones:
                if self.hass.states.get(zone).state == 'on':
                    _LOGGER.debug('zone %s is on, pump %s',zone, PUMP)
                    zone_running = True
                    count = 0
                    ''' turn the pump on if requied '''
                    if self.hass.states.get(self._pump).state == 'off':
                        _LOGGER.debug('pump id off, turn on pump %s', PUMP)
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_ON,
                                                            PUMP)
                        break

            await asyncio.sleep(step)
            if not zone_running:
                count += 1
                if count > 2:
                    count = 0
                    if self.hass.states.get(self._pump).state == 'on':
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_OFF,
                                                            PUMP)
