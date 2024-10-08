'''pump classs.'''
import asyncio
import logging

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from .const import CONST_LATENCY, CONST_OFF_DELAY, CONST_SWITCH

_LOGGER = logging.getLogger(__name__)

class PumpClass:
    '''Pump class.'''

    def __init__(self, hass: HomeAssistant, pump, zones) -> None:  # noqa: D107
        self.hass = hass
        self._pump = pump
        self._zones = zones
        self._stop = False
        self._off_delay = CONST_OFF_DELAY

    async def async_monitor(self):
        '''Monitor running zones to determine if pump is required.'''
        _LOGGER.debug("Pump Class Started monitoring zones %s", self._zones)
        step = 1
        pump = {ATTR_ENTITY_ID: self._pump}

        def zone_running():
            return any(self.hass.states.get(zone).state in ("on","open") for zone in self._zones)

        def pump_running():
            if self.hass.states.get(self._pump).state == "on":
                return True
            return False

        #Monitor the required zones
        while not self._stop:
            #check if any of the zones are running
            if zone_running():
                if self.hass.states.get(self._pump).state in ("off","closed"):
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_ON, pump
                    )
                    #handle latency
                    for _ in range(CONST_LATENCY):
                        if self.check_switch_state() is False: #still off
                            await asyncio.sleep(1)
                        else:
                            break

            #check if the zone is running, delay incase another zone starts
            if not zone_running() and pump_running():
                await asyncio.sleep(self._off_delay)
                if (
                    self.hass.states.get(self._pump).state in ("on","open")
                    and not zone_running()
                ):
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_OFF, pump
                    )
                    _LOGGER.debug('Pump Class zone monitor has turned off pump')

                    #handle latency
                    for _ in range(CONST_LATENCY):
                        if self.check_switch_state() is True: #still on
                            await asyncio.sleep(1)
                        else:
                            break

            await asyncio.sleep(step)
        # reset for next call
        self._stop = False

    async def async_stop_monitoring(self):
        '''Flag turn off pump monitoring.'''
        _LOGGER.debug('Pump Class zone monitoring has stopped')
        self._stop = True
        if self.hass.states.get(self._pump).state in ("on","open"):
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._pump}
            )

    def check_switch_state(self):
        """Check the solenoid state if turned off stop this instance."""
        if self.hass.states.get(self._pump).state in ("off","closed"):
            return False
        if self.hass.states.get(self._pump).state in ("on","open"):
            return True
        return None
