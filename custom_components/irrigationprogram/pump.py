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
        self._stop   = False
        self._off_delay = 2


    async def async_monitor(self, **kwargs):
        _LOGGER.debug('Pump Class Started monitoring zones %s', self._zones)
        step = 1
        PUMP = {ATTR_ENTITY_ID: self._pump}
        
        def zone_running():
            zone_running = False
            for zone in self._zones:
                try:
                    if self.hass.states.get(zone).state == 'on':
                        return True
                        self._running_zone = zone
                        break
                except:
                    _LOGGER.error('Zone not not found when getting state: %s', zone)
            return False 

        '''Monitor the required zones'''
        while not self._stop:
                
            ''' check if any of the zones are running'''
            if zone_running():
                try:
                    if self.hass.states.get(self._pump).state == 'off':
                        _LOGGER.debug('pump is off, turn on pump %s',  PUMP)
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_ON,
                                                            PUMP)
                except:
                    _LOGGER.error('pump not not found when getting state: %s', PUMP)
                
            await asyncio.sleep(step)
            '''check if the zone is running, delay incase another zone starts'''
            if not zone_running():
                await asyncio.sleep(self._off_delay)
                if self.hass.states.get(self._pump).state == 'on' and not zone_running():
                    _LOGGER.debug('pump is on,  turn off pump %s', PUMP)
                    await self.hass.services.async_call(CONST_SWITCH,
                                                        SERVICE_TURN_OFF,
                                                        PUMP)            
                 
    async def async_stop_monitoring(self, **kwargs):
        self._stop = True
