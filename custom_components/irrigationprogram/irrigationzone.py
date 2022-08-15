import logging
import asyncio
import voluptuous as vol
from datetime import timedelta
from time import sleep
import math
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_RUN_FREQ,
    ATTR_RAIN_SENSOR,
    CONST_SWITCH,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_ZONE,
    ATTR_PUMP,
    ATTR_FLOW_SENSOR,
    ATTR_WATER,
    ATTR_WAIT,
    ATTR_REPEAT,
    ATTR_ENABLE_ZONE,
    ATTR_WATER_ADJUST,
    ATTR_ZONE_GROUP,
)

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ATTR_ICON,
    CONF_NAME,
)

_LOGGER = logging.getLogger(__name__)

class irrigationzone:

    def __init__(
        self,
        hass,
        name,
        switch,
        run_freq,
        rain_sensor,
        ignore_rain_sensor,
        enable_zone,
        flow_sensor,
        hist_flow_rate,
        water,
        water_adjust,
        wait,
        repeat,
        last_ran,
        zone_group,
    ):
        self.hass                = hass
        self._name               = name
        self._switch             = switch
        self._run_freq           = run_freq
        self._rain_sensor        = rain_sensor
        self._ignore_rain_sensor = ignore_rain_sensor
        self._enable_zone        = enable_zone
        self._flow_sensor        = flow_sensor
        self._hist_flow_rate     = hist_flow_rate
        self._water              = water
        self._water_adjust       = water_adjust
        self._wait               = wait
        self._repeat             = repeat
        self._zone_group         = zone_group

        if last_ran is None:
            ''' default to 10 days ago for new zones '''
            self._last_ran = dt_util.now() - timedelta(days=10)
        else:
            self._last_ran        = last_ran
        
        self._run_time           = 0
        self._default_run_time   = 0
        self._remaining_time     = 0
        self._state              = 'off'
        self._stop               = False

    def name(self):
        '''Return the name of the variable.'''
        return self._name
        
    def switch(self):
        '''Return the name of the variable.'''
        return self._switch

    def pump(self):
        return self._pump

    def run_freq(self):
        return self._run_freq
    def run_freq_value(self):
        self._run_freq_value = None
        if self._run_freq is not None:
            if  self.hass.states.get(self._run_freq) == None:
                _LOGGER.warning('run_freq: %s not found, check your configuration',self._run_freq)
            else:
                self._run_freq_value = self.hass.states.get(self._run_freq).state

        return self._run_freq_value

    def rain_sensor(self):
        return self._rain_sensor
    def rain_sensor_value(self):
        self._rain_sensor_value = False
        if self._rain_sensor is not None:
            if  self.hass.states.get(self._rain_sensor) == None:
                _LOGGER.warning('rain sensor: %s not found, check your configuration',self._rain_sensor)
            else:
                self._rain_sensor_value = self.hass.states.is_state(self._rain_sensor,'on')
        return self._rain_sensor_value

    def ignore_rain_sensor(self):
        return self._ignore_rain_sensor
    def ignore_rain_sensor_value(self):
        self._ignore_rain_sensor_value = False
        if  self._ignore_rain_sensor is not None:
            self._ignore_rain_sensor_value = self.hass.states.is_state(self._ignore_rain_sensor,'on')
        return self._ignore_rain_sensor_value

    def water_adjust(self):
        return self._water_adjust
    def water_adjust_value(self):
        self._water_adjust_value = 1
        try:
            if self._water_adjust is not None:
                self._water_adjust_value = float(self.hass.states.get(self._water_adjust).state)
        except:
            _LOGGER.error('watering adjustment factor is not numeric %s', self._water_adjust)
        return self._water_adjust_value

    def flow_sensor(self):
        return self._flow_sensor
    def flow_sensor_value(self):
        self._flow_sensor_value = None
        if self._flow_sensor is not None:
            self._flow_sensor_value = int(float(self.hass.states.get(self._flow_sensor).state))
        return self._flow_sensor_value
    def hist_flow_rate(self):
        return self._hist_flow_rate

    def water(self):
        return self._water
    def water_value(self):
        self._water_value = int(float(self.hass.states.get(self._water).state))
        return self._water_value

    def wait(self):
        return self._wait
    def wait_value(self):
        self._wait_value = 0
        try:
            if self._wait is not None:
                self._wait_value = int(float(self.hass.states.get(self._wait).state))
        except:
            _LOGGER.error('wait is not numeric %s', self._wait)
        return self._wait_value

    def repeat(self):
        return self._repeat
    def repeat_value(self):
        self._repeat_value = 1
        try:
            if self._repeat is not None :
                self._repeat_value = int(float(self.hass.states.get(self._repeat).state))
                if self._repeat_value == 0:
                    self._repeat_value = 1
        except:
            _LOGGER.error('repeat is not numeric %s', self._repeat)
        return self._repeat_value

    def state(self):
        return self._state

    def zone_group(self):
        return self._zone_group
    def zone_group_value(self):
        self._zone_group_value = None
        if self._zone_group is not None :
           self._zone_group_value = self.hass.states.get(self._zone_group).state
        return self._zone_group_value

    def enable_zone(self):
        return self._enable_zone
    def enable_zone_value(self):
        self._enable_zone_value = self.hass.states.is_state(self._enable_zone,'on')
        return self._enable_zone_value

    def remaining_time(self):
        ''' remaining time or remaining volume '''
        return self._remaining_time

    def run_time(self):
        ''' update the run time component '''
        if self._flow_sensor is None:
            z_water = math.ceil(int(float(self.water_value()) * float(self.water_adjust_value())))
            self._run_time = (((z_water + self.wait_value()) * self.repeat_value()) - self.wait_value()) * 60
        else:
            z_water = math.ceil(int(float(self.water_value()) * float(self.water_adjust_value())))
            z_watertime = z_water/float(self.hist_flow_rate())
            self._run_time = (((z_watertime + self.wait_value()) * self.repeat_value()) - self.wait_value()) * 60
        ''' zone has been disabled '''
        if self.enable_zone_value() == False:
            self._run_time = 0
        return self._run_time

    def last_ran(self):
        return self._last_ran

    def is_raining(self):
        ''' assess the rain_sensor including ignore rain_sensor'''
        if self.ignore_rain_sensor_value():
            return False
        else:
            return self.rain_sensor_value()

    def should_run(self):

        ''' adjust by 10 minutes to allow for any variances '''
        calc_freq = float(((dt_util.as_timestamp(dt_util.now()) - dt_util.as_timestamp(self._last_ran)) + 600) / 86400)

        Numeric_Freq = None
        String_Freq = None
        response = True
        try:
            Numeric_Freq = float(int(self.run_freq_value()))
        except:
            String_Freq = self.run_freq_value()
            ''' check if this day matches frequency '''
        if Numeric_Freq is not None:
            if Numeric_Freq <= calc_freq:
                response = True
            else:
                response =  False
        if String_Freq is not None:
            if dt_util.now().strftime('%a') not in String_Freq:
                response =  False
            else:
                response =  True

        return response
    ''' end should_run '''

    async def async_turn_on(self, **kwargs):
        ''' Watering time or volume to water

            water wait repeat cycle using either volume of time
            remaining is volume or time
        '''
        self._stop = False
        z_water = self.water_value()
        z_wait = self.wait_value()
        z_repeat = self.repeat_value()
        self._remaining_time = self.run_time()
        ''' run the watering cycle, water/wait/repeat '''
        SOLENOID = {ATTR_ENTITY_ID: self._switch}
        for i in range(z_repeat, 0, -1):

            self._state = 'on'
            if self.hass.states.is_state(self._switch,'off') and not self._stop:
                await self.hass.services.async_call(CONST_SWITCH,
                                                    SERVICE_TURN_ON,
                                                    SOLENOID)

            if self._flow_sensor is not None:
                ''' estimate the remaining volume and time'''
                water = z_water
                while water > 0 and not self._stop:
                    water -= self.flow_sensor_value()/60
                    remaining_cycle = water/self.flow_sensor_value()*60
                    if remaining_cycle < 0: remaining_cycle = 0
                    full_cycle = z_water/self.flow_sensor_value()*60
                    self._remaining_time = remaining_cycle + (full_cycle*(i-1)) + (z_wait*60*(i-1))
                    if self.flow_sensor_value() > self.hist_flow_rate():
                        self._hist_flow_rate = self.flow_sensor_value()
                    if not self._stop: await asyncio.sleep(1)
            else:
                ''' calculate remaining time '''
                water = z_water * 60
                for w in range(0,water, 1):
                    self._remaining_time -= 1
                    if self._stop:
                        break
                    await asyncio.sleep(1)

            if z_wait > 0 and i > 1 and not self._stop:
                ''' Eco mode is enabled '''
                self._state = 'eco'
                if self.hass.states.is_state(self._switch,'on'):
                    await self.hass.services.async_call(CONST_SWITCH,
                                                        SERVICE_TURN_OFF,
                                                        SOLENOID)
                wait = z_wait * 60
                for w in range(0,wait, 1):
                    self._remaining_time -= 1
                    if self._stop:
                        break
                    await asyncio.sleep(1)

            ''' turn the switch entity off '''
            if i <= 1 or self._stop:
                ''' last/only cycle '''
                self._remaining_time = 0

                if self.hass.states.is_state(self._switch,'on'):
                    await self.hass.services.async_call(CONST_SWITCH,
                                                        SERVICE_TURN_OFF,
                                                        SOLENOID)
                if self._stop:
                    break

        ''' End of repeat loop '''
        self._state = 'off'


    async def async_turn_off(self, **kwargs):
        self._stop = True

    def set_last_ran(self, last_ran):
        if last_ran is None:
            ''' default to 10 days ago for new zones '''
            self._last_ran = dt_util.now() - timedelta(days=10)
        else:
            self._last_ran = last_ran

    def validate(self, **kwargs):
        valid = True
        if  self._switch is not None and self.hass.states.async_available(self._switch):
            _LOGGER.error('%s not found',self._switch)
            valid = False
        if  self._run_freq is not None and self.hass.states.async_available(self._run_freq):
            _LOGGER.error('%s not found',self._run_freq)
            valid = False
        if  self._rain_sensor is not None and self.hass.states.async_available(self._rain_sensor):
            _LOGGER.error('%s not found',self._rain_sensor)
            valid = False

        return valid
