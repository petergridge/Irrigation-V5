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

    async def async_monitor(self, **kwargs):
        '''Monitor running zones to determine if pump is required.'''
        _LOGGER.debug("Pump Class Started monitoring zones %s", self._zones)
        step = 1
        pump = {ATTR_ENTITY_ID: self._pump}

        def zone_running():
            # for zone in self._zones:
            #     if self.hass.states.get(zone).state == "on":
            #         return True
            # return False
            return any(self.hass.states.get(zone).state == "on" for zone in self._zones)

        def pump_running():
            if self.hass.states.get(self._pump).state == "on":
                return True
            return False


        #Monitor the required zones
        while not self._stop:

            #check if any of the zones are running
            if zone_running():
                if self.hass.states.is_state(self._pump, "off"):
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
                    self.hass.states.is_state(self._pump, "on")
                    and not zone_running()
                ):
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_OFF, pump
                    )
                    #handle latency
                    for _ in range(CONST_LATENCY):
                        if self.check_switch_state() is True: #still on
                            await asyncio.sleep(1)
                        else:
                            break

            await asyncio.sleep(step)
        # reset for next call
        self._stop = False

    async def async_stop_monitoring(self, **kwargs):
        '''Flag turn off pump monitoring.'''
        self._stop = True
        if self.hass.states.is_state(self._pump, "on"):
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._pump}
            )

    async def latency_check(self, check = 'off'):
        '''Ensure switch has turned off and warn.'''
        if not (self.hass.states.is_state(self._pump, "on") or self.hass.states.is_state(self._pump, "off")):
            #switch is offline
            return True

        for i in range(CONST_LATENCY):  # noqa: B007
            if check == 'off':
                if self.check_switch_state() is False: #on
                    await asyncio.sleep(1)
                else:
                    return False
            if check == 'on':
                if self.check_switch_state() is True: #on
                    return True
                else:
                    await asyncio.sleep(1)

        _LOGGER.warning('Switch has latency exceding %s seconds, cannot confirm %s state is off', i+1, self._switch)
        return

    def check_switch_state(self):
        """Check the solenoid state if turned off stop this instance."""
        if self.hass.states.is_state(self._pump, "off"):
            return False
        if self.hass.states.is_state(self._pump, "on"):
            return True
        return None
