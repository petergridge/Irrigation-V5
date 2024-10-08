"""Irrigation zone class."""

import asyncio
from datetime import datetime, timedelta
import logging
import math
import re
from zoneinfo import ZoneInfo

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import (
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REPEAT,
    ATTR_RUN_FREQ,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_WATER_SOURCE,
    ATTR_ZONE,
    ATTR_ZONE_ORDER,
    CONST_ADJUSTED_OFF,
    CONST_CLOSED,
    CONST_CONTROLLER_DISABLED,
    CONST_DISABLED,
    CONST_ECO,
    CONST_LATENCY,
    CONST_NO_WATER_SOURCE,
    CONST_OFF,
    CONST_ON,
    CONST_OPEN,
    CONST_PENDING,
    CONST_PROGRAM_DISABLED,
    CONST_RAINING,
    CONST_SWITCH,
    CONST_UNAVAILABLE,
    CONST_ZERO_FLOW_DELAY,
    CONST_ZONE_DISABLED,
    DOMAIN,
    RAINBIRD,
    RAINBIRD_DURATION,
    RAINBIRD_TURN_ON,
    TIME_STR_FORMAT,
)

_LOGGER = logging.getLogger(__name__)

class IrrigationZone:
    '''Irrigation zone class.'''

    def __init__(  # noqa: D107
        self,
        hass:HomeAssistant,
        program,
        zone,
        hist_flow_rate,
        last_ran,
    ) -> None:
        self.hass = hass
        self._program = program
        self._run_freq = zone.get(ATTR_RUN_FREQ, program.run_freq)
        self._name = zone.get(ATTR_ZONE).split(".")[1]
        self._type = zone.get(ATTR_ZONE).split(".")[0]
        self._switch = zone.get(ATTR_ZONE)
        self._pump = zone.get(ATTR_PUMP)
        self._rain_sensor = zone.get(ATTR_RAIN_SENSOR)
        self._ignore_rain_sensor = zone.get(ATTR_IGNORE_RAIN_SENSOR)
        self._enable_zone = zone.get(ATTR_ENABLE_ZONE)
        self._flow_sensor = zone.get(ATTR_FLOW_SENSOR)
        self._hist_flow_rate = hist_flow_rate
        self._water = zone.get(ATTR_WATER)
        self._water_adjust = zone.get(ATTR_WATER_ADJUST)
        self._wait = zone.get(ATTR_WAIT)
        self._repeat = zone.get(ATTR_REPEAT)
        self._order = zone.get(ATTR_ZONE_ORDER,999) #the attribute set to reorder zones 0 is the first
        self._last_ran = last_ran
        self._remaining_time = 0
        self._water_adjust_prior = 0
        self._state = CONST_OFF
        self._next_run = CONST_OFF
        self._stop = True
        self._water_source = zone.get(ATTR_WATER_SOURCE)
        self._localtimezone = ZoneInfo(self.hass.config.time_zone)
        self._default_time = abs(program.inter_zone_delay)
        self._scheduled = False

    @property
    def name(self):
        """Return the name of the variable."""
        return self._name
    @property
    def order(self):
        """Return the name of the variable."""
        return self._order
    @property
    def switch(self):
        """Return the name of the variable."""
        return self._switch
    @property
    def type(self):
        """Return the name of the variable."""
        return self._type
    @property
    def pump(self):
        '''Pump entity attribute.'''
        return self._pump
    @property
    def run_freq(self):
        '''Run frequency enity attribute.'''
        return self._run_freq
    @property
    def run_freq_value(self):
        '''Run frequancy entity value.'''
        run_freq_value = None
        if self.run_freq is not None:
            if self.hass.states.get(self.run_freq) is None:
                _LOGGER.error(
                    "Run_freq: %s not found, check your configuration", self.run_freq
                )
            else:
                run_freq_value = self.hass.states.get(self.run_freq).state
        return run_freq_value
    @property
    def rain_sensor(self):
        '''Rain sensor entity attribute.'''
        return self._rain_sensor
    @property
    def rain_sensor_value(self):
        '''Rain sensor entity value.'''
        rain_sensor_value = False
        if self.rain_sensor is not None:
            if self.hass.states.get(self.rain_sensor) is None:
                _LOGGER.error(
                    "Rain sensor: %s not found, check your configuration",
                    self.rain_sensor,
                )
            else:
                rain_sensor_value = self.hass.states.is_state(
                    self.rain_sensor, CONST_ON
                )
        return rain_sensor_value
    @property
    def ignore_rain_sensor(self):
        '''Ignore rain sensor entity attribute.'''
        return self._ignore_rain_sensor
    @property
    def ignore_rain_sensor_value(self):
        '''Rain sensor value.'''
        ignore_rain_sensor_value = False
        if self.ignore_rain_sensor is not None:
            ignore_rain_sensor_value = self.hass.states.is_state(
                self.ignore_rain_sensor, CONST_ON
            )
        return ignore_rain_sensor_value
    @property
    def water_adjust(self):
        '''Water adjustment entity attribute.'''
        return self._water_adjust
    @property
    def water_adjust_value(self):
        '''Determine watering adjustment.'''
        water_adjust_value = 1
        if self.water_adjust is not None:
            water_adjust_value = float(self.hass.states.get(self.water_adjust).state)
            if self._default_time < abs(self._program.inter_zone_delay) and self._program.inter_zone_delay < 0:
                #calculate a new adjust value to use
                water_adjust_value = self.calc_adjustmet()
        return water_adjust_value
    @property
    def water_source(self):
        '''Water adjustment entity attribute.'''
        return self._water_source
    @property
    def water_source_value(self):
        '''Determine watering adjustment.'''
        water_source_value = True
        if self._water_source is not None:
            water_source_value = self.hass.states.is_state(self._water_source, CONST_ON)
        return water_source_value
    @property
    def flow_sensor(self):
        '''Flow sensor attribute.'''
        return self._flow_sensor
    @property
    def flow_sensor_value(self):
        '''Flow sensor attributes value.'''
        flow_value = None
        if self.flow_sensor is not None:
            flow_value = float(self.hass.states.get(self.flow_sensor).state)
        return flow_value
    @property
    def flow_rate(self):
        '''History flow attribute.'''
        if self.flow_sensor is not None:
            if self.flow_sensor_value > 0 :
                return self.flow_sensor_value
            #else use the historical value
        return self._hist_flow_rate
    @property
    def water(self):
        '''Water entity attribute.'''
        return self._water
    @property
    def water_value(self):
        '''Water attibute value.'''
        return float(self.hass.states.get(self.water).state)
    @property
    def wait(self):
        '''Wait entity attribute.'''
        return self._wait
    @property
    def wait_value(self):
        '''Wait entity value.'''
        v_wait_value = 0
        if self.wait is not None:
            v_wait_value = float(self.hass.states.get(self.wait).state)
        return v_wait_value
    @property
    def repeat(self):
        '''Repeat entity attribute.'''
        return self._repeat
    @property
    def repeat_value(self):
        '''Repeat entity value.'''
        v_repeat_value = 1
        if self.repeat is not None:
            v_repeat_value = int(float(self.hass.states.get(self.repeat).state))
            if v_repeat_value == 0:
                v_repeat_value = 1
        return v_repeat_value
    @property
    def state(self):
        '''State value.'''
        return self._state
    @property
    def enable_zone(self):
        '''Enable zone entity attribute.'''
        return self._enable_zone
    @property
    def enable_zone_value(self):
        '''Enable zone entity value.'''
        zone_value = True
        if self.enable_zone is not None:
            zone_value = self.hass.states.is_state(self.enable_zone, CONST_ON)
        return zone_value
    @property
    def remaining_time(self):
        """Remaining time or remaining volume."""
        return self._remaining_time

    def calc_adjustmet(self):
        """Calculate alternate adjustment where value < IZ delay."""
        wait = self.wait_value*60
        repeats = self.repeat_value

        if self.flow_sensor is None:
            #time based
            water = self.water_value*60
            adjust = (abs(self._program.inter_zone_delay) - (wait * (repeats -1)))/(water * repeats)
        else:
            #volume based/flow sensor
            water = self.water_value * 60 #volume
            flow = self.flow_rate # flow rate
            #remaining watering time + remaining waits
            adjust = (abs(self._program.inter_zone_delay) - (wait * (repeats -1)))/(water / flow)
        return adjust

    async def set_state_sensor(self, state):
        '''Set the state sensor.'''
        program = slugify(self._program.name)
        zone = slugify(self.name)
        device = f'sensor.{program}_{zone}_status'
        servicedata = {ATTR_ENTITY_ID: device, 'status': state}
        await self.hass.services.async_call(DOMAIN, 'set_zone_status', servicedata)

    async def get_state_sensor(self):
        '''Set the state sensor.'''
        program = slugify(self._program.name)
        zone = slugify(self.name)
        device = f'sensor.{program}_{zone}_status'
        return self.hass.states.get(device).state

    async def set_zone_next_run_sensor(self, state):
        '''Set the state sensor.'''
        if isinstance(state,datetime):
            program = slugify(self._program.name)
            zone = slugify(self.name)
            device = f'sensor.{program}_{zone}_next_run'
            servicedata = {ATTR_ENTITY_ID: device, 'status': state}
            await self.hass.services.async_call(DOMAIN, 'set_zone_next_run', servicedata)


    async def prepare_to_run(self,scheduled=False):
        """Initialise the remaining time when the program is started."""
        self._scheduled = scheduled
        self._remaining_time = await self.run_time(repeats=self.repeat_value,scheduled=scheduled)
        await self._program.set_zone_run_time_attr(self.name, self._remaining_time)
        self._state = CONST_PENDING
        await self.set_state_sensor(self._state)

    async def run_time(self, seconds_run=0, volume_delivered=0, repeats=1, scheduled=False):
        """Update the run time component."""

        wait = self.wait_value*60
        #make the water adjustment static once the program starts
        if self.state not in (CONST_ECO,CONST_ON):
            self._water_adjust_prior = self.water_adjust_value
            #_LOGGER.warning('state is off')
        if scheduled:
            if self.state in (CONST_ECO,CONST_ON):
                adjust = self._water_adjust_prior
                #_LOGGER.warning('state is on')
            else:
                adjust = self.water_adjust_value
        else:
            #if run manually do not adjust the time
            adjust = 1

        if self.flow_sensor is None:
            #time based
            water = self.water_value*60
            run_time = (water * adjust * repeats) + (wait * (repeats -1))
        else:
            #volume based/flow sensor
            water = self.water_value #volume
            flow = self.flow_rate # flow rate
            delivery_volume = water * adjust
            if volume_delivered > 0: # the cycle has started
                remaining_volume = (delivery_volume * (repeats-1)) +  delivery_volume - volume_delivered
            else:
                remaining_volume = delivery_volume * repeats

            watertime = remaining_volume / flow * 60
            #remaining watering time + remaining waits
            run_time = watertime + (wait * (repeats -1))

        #set the program attribute
        return math.ceil(run_time - seconds_run)

    @property
    def last_ran(self):
        '''Last ran datetime attribute.'''
        if self._last_ran is None:
            #default to today and start time
            self._last_ran = datetime.now(self._localtimezone) - timedelta(days=10)
        if isinstance(self._last_ran,str):
             self._last_ran = datetime.strptime(self._last_ran,"%Y-%m-%dT%H:%M:%S.%f%z")
        return self._last_ran

    @property
    def next_run_dt(self):
        """Present next run as a datetime."""
        if isinstance(self._next_run,datetime):
            return self._next_run
        return False

    async def next_run_validation(self):
        """Validate the object readyness."""
        if self.water_value == 0:
            return CONST_DISABLED
        if self._program.irrigation_on_value is False:
            return  CONST_PROGRAM_DISABLED
        if self._program.monitor_controller_value is False:
            return  CONST_CONTROLLER_DISABLED
        if await self.check_switch_state() is None:
            return CONST_UNAVAILABLE
        if self.water_source_value is False:
            return CONST_NO_WATER_SOURCE
        if self.enable_zone_value is False :
            return CONST_ZONE_DISABLED
        if self.rain_sensor_value is True and self.ignore_rain_sensor_value is False:
            return CONST_RAINING
        if self.water_adjust_value <= 0:
            return CONST_ADJUSTED_OFF
        return False

    async def next_run(self):
        '''Determine when a zone will next attempt to run.'''
        #something has changed recacl the run time
        if self._state == CONST_PENDING:
            await self.prepare_to_run(scheduled=self._scheduled)

        #is called when anything changes that will impact the
        #the next run date, frequency change, rain ...
        time = datetime.now(self._localtimezone).strftime(TIME_STR_FORMAT)

        if self._state in (CONST_ON, CONST_PENDING, CONST_ECO):
           return
        # determine next run time
        if "sensor." in self._program.start_time:
            try:
                #a datetime sensor like sun sensor.dawn
                string_times =datetime.strptime(self._program.start_time_value,"%Y-%m-%dT%H:%M:%S%z").replace(second=00, microsecond=00).astimezone(self._localtimezone).strftime("%H:%M:%S")
            except ValueError:
                #custom time only sensor - present better in the card
                string_times =datetime.strptime(self._program.start_time_value,"%H:%M:%S").replace(second=00).strftime("%H:%M:%S")
        else:
            string_times = self._program.start_time_value

        string_times = (
            string_times.replace(" ", "")
            .replace("\n", "")
            .replace("'", "")
            .replace('"', "")
            .strip("[]'")
            .split(",")
        )
        string_times.sort()
        starttime = string_times[0]
        for stime in string_times:
            if not re.search("^([0-2]?[0-9]:[0-5][0-9]:00)", stime):
                continue
            if stime > time:
                x = string_times.index(stime)
                starttime = string_times[x]
                break
        firststarttime = string_times[0]

        # starttime is not valid or missing
        if not starttime:
            #no start time set to 8am
            await self.hass.services.async_call(
                "input_text",
                "set_value",
                {ATTR_ENTITY_ID: self._program.start_time, "value": "08:00:00"},
            )
       #the next time to run in a multi start config
        try:
            if starttime:
                starthour = int(starttime.split(':')[0])
                startmin = int(starttime.split(':')[1])
            else:
                starthour = 8
                startmin = 0
            #first run time in a multi start config
            if firststarttime:
                firststarthour = int(firststarttime.split(':')[0])
                firststartmin = int(firststarttime.split(':')[1])
            else:
                firststarthour = 8
                firststarthour = 0
        except ValueError:
            self._state = CONST_DISABLED
            await self.set_state_sensor(self._next_run)
            return

        v_error = await self.next_run_validation()
        if v_error:
            #a validation error was returned
            self._state = v_error
            await self.set_state_sensor(self._state)
            return
        v_last_ran  = self.last_ran.replace(hour=starthour, minute=startmin, second=00, microsecond=00)

        try: # Frq is numeric
            if self.run_freq_value is None:
                #frq is not defined default to daily
                frq = 1
            else:
                frq = int(float(self.run_freq_value))

            today_start_time = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
            today_begin = datetime.now(self._localtimezone).replace(hour=00, minute=00, second=00, microsecond=00)
            last_ran_day_begin = v_last_ran.replace(hour=00, minute=00, second=00, microsecond=00)

            if (today_start_time - v_last_ran).total_seconds()/86400 >= frq:
                #it has been sometime since the zone ran
                v_next_run = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
                if today_start_time < datetime.now(self._localtimezone):
                    v_next_run += timedelta(days=1)
            elif today_start_time >= datetime.now(self._localtimezone) and last_ran_day_begin == today_begin:
                #time is in the future and it previously ran today, supports multiple start times
                v_next_run = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
            else:# (today_start_time - last_ran).total_seconds()/86400 < frq:
                #frequency has not been satisfied
                #set last ran datetime to the first runtime of the series and add the frequency
                v_next_run = v_last_ran.replace(hour=firststarthour, minute=firststartmin, second=00, microsecond=00) + timedelta(days=frq)
            self._next_run =  v_next_run
        except ValueError:
            #Frq is Alpha
            string_freq = self.run_freq_value
            # remove spaces, new line, quotes and brackets
            string_freq = string_freq.replace(" ","").replace("\n","").replace("'","").replace('"',"").strip("[]'").split(",")
            string_freq = [x.capitalize() for x in string_freq]
            valid_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            valid_freq = any(item in string_freq for item in valid_days)
            if valid_freq is True:
                #default to today and start time for day based running
                v_last_ran = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
                today = v_last_ran.isoweekday()
                v_next_run = v_last_ran + timedelta(days=100) #arbitary max
                for day in string_freq :
                    try:
                        if self.get_weekday(day) == today and v_last_ran > datetime.now(self._localtimezone):
                            v_next_run = v_last_ran
                        else:
                            v_next_run = min(self.get_next_dayofweek_datetime(v_last_ran, day), v_next_run)
                    except ValueError:
                        v_next_run = 'Error, invalid value in week day list'
                self._next_run =  v_next_run
            #zone is marked as off
            else:
                self._next_run =  CONST_DISABLED
                self._state = CONST_DISABLED
                await self.set_state_sensor(self._state)
                return

        #if we got this far there is a valid run time
        await self.set_zone_next_run_sensor(self._next_run)
        if self._state  not in (CONST_PENDING,CONST_ON,CONST_ECO,CONST_OFF):
            self._state = CONST_OFF
            await self.set_state_sensor(self._state)
        return

    def get_weekday(self,day):
        '''Determine weekday num.'''
        days  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        return days.index(day) + 1

    def get_next_dayofweek_datetime(self,date_time, dayofweek):
        '''Next date for the given day.'''
        start_time_w = date_time.isoweekday()
        target_w = self.get_weekday(dayofweek)
        if start_time_w < target_w:
            day_diff = target_w - start_time_w
        else:
            day_diff = 7 - (start_time_w - target_w)
        return date_time + timedelta(days=day_diff)

    async def should_run(self, scheduled=False):
        '''Determine if the zone should run.'''
        #determine the default time used when the runtime LT zone delay
        self._default_time = await self.run_time(repeats=self.repeat_value,scheduled=True)
        state = await self.get_state_sensor()
        _LOGGER.debug('SHould run: zone  %s, State %s, Scheduled %s',self.name, state, scheduled)

        #zone has been turned off or is offline
        if state in [CONST_DISABLED, CONST_PROGRAM_DISABLED,
                    CONST_UNAVAILABLE, CONST_CONTROLLER_DISABLED,
                    CONST_NO_WATER_SOURCE]:
            return False
        #zone should still run when manually started
        if scheduled is True:
            if state in [CONST_RAINING, CONST_ADJUSTED_OFF,CONST_ZONE_DISABLED]:
                return False
            #next run time is in the future
            _LOGGER.debug('SHould run: next %s now %s',self.next_run_dt,datetime.now(self._localtimezone))
            if self.next_run_dt > datetime.now(self._localtimezone):
                return False
        #should run
        return True
    # end should_run


    async def check_switch_state(self):
        """Check the solenoid state if turned off stop this instance."""
        #wait a few seconds if offline it may come back
        for _ in range(CONST_LATENCY):
            if self.hass.states.get(self.switch).state in [CONST_OFF,CONST_CLOSED]:
                return False
            if self.hass.states.get(self.switch).state in [CONST_ON,CONST_OPEN]:
                return True
            await asyncio.sleep(1)
        return None

    async def async_turn_on(self):
        """Turn on the zone."""
        if await self.check_switch_state() is False:
            if self._program.device_type == 'rainbird':
                # RAINBIRD controller requires a different service call
                await self.hass.services.async_call(
                    RAINBIRD, RAINBIRD_TURN_ON, {ATTR_ENTITY_ID: self.switch, RAINBIRD_DURATION: self.water_value}
                )
            elif self.switch.startswith('valve.'):
                #valve
                await self.hass.services.async_call(
                    'valve', SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: self.switch}
                )
            else:
                #switch
                await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self.switch}
                )

    async def async_turn_off(self):
        """Turn off the zone."""
        #is it a valve or a switch
        valve = self.switch.startswith('valve.')
        if valve:
            #postion entity defined get the value
            await self.hass.services.async_call(
                'valve', SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self.switch}
            )
        else:
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self.switch}
            )

    async def async_turn_on_cycle(self, scheduled=False):
        """Start the zone watering cycle."""
        self._stop = False
        self._state = CONST_ON
        self._scheduled = scheduled
        #initalise the reamining time for display
        #if run manually do not adjust the time
        if self.state not in (CONST_ECO,CONST_ON):
            #record the adjusted time prior to the zone starting
            self._water_adjust_prior = self.water_adjust_value
        if scheduled:
            if self.state in (CONST_ECO,CONST_ON):
                water_adjust_value = self._water_adjust_prior
            else:
                water_adjust_value = self.water_adjust_value
        else:
            water_adjust_value = 1
#        await self.next_run()

        # run the watering cycle, water/wait/repeat
        zeroflowcount = 0
        for i in range(self.repeat_value, 0, -1):
            seconds_run = 0
            #run time adjusted to 0 skip this zone
            if self.remaining_time <= 0:
                continue
            self._state = CONST_ON
            await self.set_state_sensor(self._state)
            if await self.check_switch_state() is False and self._stop is False:
                await self.async_turn_on()
                if await self.latency_check(True):
                    self._stop = True

            #track the watering
            if self.flow_sensor is not None:
                volume_remaining = self.water_value * water_adjust_value
                volume_delivered = 0
                while volume_remaining > 0:
                    volume_delivered += self.flow_sensor_value / 60
                    volume_required = self.water_value * water_adjust_value
                    volume_remaining = volume_required - volume_delivered
                    self._remaining_time = await self.run_time(volume_delivered=volume_delivered, repeats=i, scheduled=scheduled)
                    await self._program.set_zone_run_time_attr(self.name,self.remaining_time)
                    await asyncio.sleep(1)
                    if await self.check_switch_state() is False:
                        self._stop = True
                        break
                    #flow sensor has failed or no water is being provided
                    if self.flow_sensor_value == 0 or self.water_source_value is False:
                        zeroflowcount += 1
                        self._stop = True
                        if zeroflowcount > CONST_ZERO_FLOW_DELAY:
                            _LOGGER.warning("No flow detected for %s seconds, turning off solenoid to allow program to complete",CONST_ZERO_FLOW_DELAY)
                            break
                    else:
                        zeroflowcount = 0
            else:
                watertime = math.ceil(self.water_value*60 * water_adjust_value)
                while watertime > 0:
                    seconds_run += 1
                    watertime = math.ceil(self.water_value*60 * water_adjust_value) - seconds_run
                    self._remaining_time = await self.run_time(seconds_run, repeats=i, scheduled=scheduled)
                    await self._program.set_zone_run_time_attr(self.name,self.remaining_time)
                    await asyncio.sleep(1)
                    if await self.check_switch_state() is False:
                        self._stop = True
                        break
                    #no water is being provided
                    if self.water_source_value is False:
                        zeroflowcount += 1
                        self._stop = True
                        if zeroflowcount > CONST_ZERO_FLOW_DELAY:
                            _LOGGER.warning("No water source detected for %s seconds, turning off solenoid to allow program to complete",CONST_ZERO_FLOW_DELAY)
                            break
                    else:
                        zeroflowcount = 0

            if self._stop:
                break
            #Eco mode, wait cycle
            if self.wait_value > 0 and i > 1:
                await self.async_eco_off()
                waittime = self.wait_value * 60
                wait_seconds = 0
                while waittime > 0:
                    seconds_run += 1
                    wait_seconds += 1
                    waittime = self.wait_value * 60 - wait_seconds
                    self._remaining_time = await self.run_time(seconds_run, repeats=i, scheduled=scheduled)
                    await self._program.set_zone_run_time_attr(self.name,self.remaining_time)
                    if self._stop:
                        break
                    await asyncio.sleep(1)

            if self._stop:
                break

        # End of repeat loop
        self._scheduled = False

        await self.async_turn_zone_off()

    async def async_eco_off(self):
        '''Signal the zone to stop.'''
        await self.async_turn_off()
        latency = await self.latency_check(False)
        #raise an event
        event_data = {
            "action": "zone_turned_off",
            "device_id": self.switch,
            "zone": self.name,
            "state":CONST_ECO,
            "latency": latency
        }
        self.hass.bus.async_fire("irrigation_event", event_data)
        self._state = CONST_ECO
        await self.set_state_sensor(self._state)

    async def async_turn_zone_off(self):
        '''Signal the zone to stop.'''

        self._state = CONST_OFF
        self._stop = True
        self._scheduled = False
        self._remaining_time = 0
        await self._program.set_zone_run_time_attr(self.name,self.remaining_time)
        await self.set_state_sensor(self._state)
        await self.next_run()
        if  self.hass.states.is_state(self.switch, CONST_OFF):
            #switch is already off
            return
        await self.async_turn_off()

        latency = await self.latency_check(False)
        #raise an event
        event_data = {
            "action": "zone_turned_off",
            "device_id": self.switch,
            "zone": self.name,
            "state":CONST_OFF,
            "latency": latency
        }
        self.hass.bus.async_fire("irrigation_event", event_data)


    async def latency_check(self,state):
        '''Ensure switch has turned off and warn.'''
        #state: true = on false = off
        if not (self.hass.states.is_state(self.switch, CONST_ON) or self.hass.states.is_state(self.switch, CONST_OFF)
             or self.hass.states.is_state(self.switch, CONST_OPEN) or self.hass.states.is_state(self.switch, CONST_CLOSED)):

            return False
        for _ in range(CONST_LATENCY):
            if await self.check_switch_state() is not state: #on
                await asyncio.sleep(1)
            else:
                return False
        _LOGGER.warning('Switch has latency exceding %s seconds, cannot confirm %s state, unexpected behaviour may occur', CONST_LATENCY+1, self.switch)
        return True

    async def set_last_ran(self, p_last_ran):
        '''Update the last ran attribute.'''
        self._last_ran = p_last_ran
        await self.next_run()

    def validate(self):
        '''Validate inputs.'''
        valid = True
        if self.switch is not None and self.hass.states.async_available(self.switch):
            _LOGGER.error("%s not found switch", self.switch)
            valid = False
        if self.pump is not None and self.hass.states.async_available(self.pump):
            _LOGGER.error("%s not found pump", self.pump)
            valid = False
        if self.run_freq is not None and self.hass.states.async_available(
            self.run_freq):
            _LOGGER.error("%s not found run frequency" , self.run_freq)
            valid = False
        if self.rain_sensor is not None and self.hass.states.async_available(
            self.rain_sensor):
            _LOGGER.error("%s not found rain sensor", self.rain_sensor)
            valid = False
        if self.flow_sensor is not None and self.hass.states.async_available(
            self.flow_sensor):
            _LOGGER.error("%s not found flow sensor", self.flow_sensor)
            valid = False
        if self.water_adjust is not None and self.hass.states.async_available(
            self.water_adjust):
            _LOGGER.error("%s not found adjustment", self.water_adjust)
            valid = False
        return valid

    async def async_test_zone(self, scheduled):
        '''Show simulation results.'''
        _LOGGER.warning("----------------------------")
        _LOGGER.warning("Zone:                     %s", self.name)
        _LOGGER.warning("Should run:               %s", await self.should_run(scheduled=scheduled))
        _LOGGER.warning("Last Run time:            %s", self._last_ran)
        _LOGGER.warning("Run time:                 %s", await self.run_time(repeats=self.repeat_value))
        _LOGGER.warning("Water Value:              %s", self.water_value)
        _LOGGER.warning("Wait Value:               %s", self.wait_value)
        _LOGGER.warning("Repeat Value:             %s", self.repeat_value)
        _LOGGER.warning("Rain sensor value:        %s", self.rain_sensor_value)
        _LOGGER.warning("Ignore rain sensor Value: %s", self.ignore_rain_sensor_value)
        _LOGGER.warning("Run frequency Value:      %s", self.run_freq_value)
        _LOGGER.warning("Flow Sensor Value:        %s", self.flow_sensor_value)
        _LOGGER.warning("Adjuster Value:           %s", self.water_adjust_value)
