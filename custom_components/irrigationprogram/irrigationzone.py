'''Irrigation zone class.'''
import asyncio

from datetime import datetime, timedelta
import logging
import math
from zoneinfo import ZoneInfo

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_CLOSE_VALVE, SERVICE_OPEN_VALVE
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import (
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REPEAT,
    ATTR_SHOW_CONFIG,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_WATER_SOURCE,
    ATTR_ZONE,
    CONST_LATENCY,
    CONST_SWITCH,
    CONST_ZERO_FLOW_DELAY,
    DOMAIN,
    RAINBIRD,
    RAINBIRD_DURATION,
    RAINBIRD_TURN_ON,
)

_LOGGER = logging.getLogger(__name__)

class IrrigationZone:
    '''Irrigation zone class.'''

    def __init__(  # noqa: D107
        self,
        hass:HomeAssistant,
        program_name,
        zone,
        device_type,
        run_freq,
        hist_flow_rate,
        last_ran,
    ) -> None:
        self.hass = hass
        self._program_name = program_name
        self._name = zone.get(ATTR_ZONE).split(".")[1]
        self._type = zone.get(ATTR_ZONE).split(".")[0]
        self._switch = zone.get(ATTR_ZONE)
        self._pump = zone.get(ATTR_PUMP)
        self._run_freq = run_freq
        self._rain_sensor = zone.get(ATTR_RAIN_SENSOR)
        self._ignore_rain_sensor = zone.get(ATTR_IGNORE_RAIN_SENSOR)
        self._enable_zone = zone.get(ATTR_ENABLE_ZONE)
        self._show_config = zone.get(ATTR_SHOW_CONFIG)
        self._flow_sensor = zone.get(ATTR_FLOW_SENSOR)
        self._hist_flow_rate = hist_flow_rate
        self._water = zone.get(ATTR_WATER)
        self._water_adjust = zone.get(ATTR_WATER_ADJUST)
        self._wait = zone.get(ATTR_WAIT)
        self._repeat = zone.get(ATTR_REPEAT)
        self._last_ran = last_ran
        self._remaining_time = 0
        self._state = "off"
        self._next_run = "off"
        self._stop = False
        self._water_source = zone.get(ATTR_WATER_SOURCE)
        self._device_type = device_type
        self._localtimezone = ZoneInfo(self.hass.config.time_zone)

    def name(self):
        """Return the name of the variable."""
        return self._name

    def switch(self):
        """Return the name of the variable."""
        return self._switch

    def type(self):
        """Return the name of the variable."""
        return self._type

    def pump(self):
        '''Pump entity attribute.'''
        return self._pump

    def run_freq(self):
        '''Run frequency enity attribute.'''
        return self._run_freq

    def run_freq_value(self):
        '''Run frequancy entity value.'''
        run_freq_value = None
        if self._run_freq is not None:
            if self.hass.states.get(self._run_freq) is None:
                _LOGGER.error(
                    "Run_freq: %s not found, check your configuration", self._run_freq
                )
            else:
                run_freq_value = self.hass.states.get(self._run_freq).state
        return run_freq_value

    def rain_sensor(self):
        '''Rain sensor entity attribute.'''
        return self._rain_sensor

    def rain_sensor_value(self):
        '''Rain sensor entity value.'''
        rain_sensor_value = False
        if self._rain_sensor is not None:
            if self.hass.states.get(self._rain_sensor) is None:
                _LOGGER.error(
                    "Rain sensor: %s not found, check your configuration",
                    self._rain_sensor,
                )
            else:
                rain_sensor_value = self.hass.states.is_state(
                    self._rain_sensor, "on"
                )
        return rain_sensor_value

    def ignore_rain_sensor(self):
        '''Ignore rain sensor entity attribute.'''
        return self._ignore_rain_sensor

    def ignore_rain_sensor_value(self):
        '''Rain sensor value.'''
        ignore_rain_sensor_value = False
        if self._ignore_rain_sensor is not None:
            ignore_rain_sensor_value = self.hass.states.is_state(
                self._ignore_rain_sensor, "on"
            )
        return ignore_rain_sensor_value

    def water_adjust(self):
        '''Water adjustment entity attribute.'''
        return self._water_adjust

    def water_adjust_value(self):
        '''Determine watering adjustment.'''
        water_adjust_value = 1
        if self._water_adjust is not None:
            water_adjust_value = float(self.hass.states.get(self._water_adjust).state)
        return water_adjust_value

    def water_source(self):
        '''Water adjustment entity attribute.'''
        return self._water_source

    def water_source_value(self):
        '''Determine watering adjustment.'''
        water_source_value = True
        if self._water_source is not None:
            water_source_value = self.hass.states.is_state(self._water_source, "on")
        return water_source_value

    def flow_sensor(self):
        '''Flow sensor attribute.'''
        return self._flow_sensor

    def flow_sensor_value(self):
        '''Flow sensor attributes value.'''
        flow_value = None
        if self._flow_sensor is not None:
            flow_value = float(self.hass.states.get(self._flow_sensor).state)
        return flow_value

    def flow_rate(self):
        '''History flow attribute.'''
        if self.flow_sensor_value() > 0:
            return self.flow_sensor_value()
        #else use the historical value
        return self._hist_flow_rate

    def water(self):
        '''Water entity attribute.'''
        return self._water

    def water_value(self):
        '''Water attibute value.'''
        return float(self.hass.states.get(self._water).state)

    def wait(self):
        '''Wait entity attribute.'''
        return self._wait

    def wait_value(self):
        '''Wait entity value.'''
        wait_value = 0
        if self._wait is not None:
            wait_value = float(self.hass.states.get(self._wait).state)
        return wait_value

    def repeat(self):
        '''Repeat entity attribute.'''
        return self._repeat

    def repeat_value(self):
        '''Repeat entity value.'''
        repeat_value = 1
        if self._repeat is not None:
            repeat_value = int(float(self.hass.states.get(self._repeat).state))
            if repeat_value == 0:
                repeat_value = 1
        return repeat_value

    async def state(self):
        '''State value.'''
        return self._state

    async def set_state_sensor(self, state, program, zone):
        '''Set the state sensor.'''

        new_status = 'off'
        program = slugify(program)
        zone = slugify(zone)
        if state in ('on','eco'):
            new_status = state
        elif self._remaining_time != 0:
            new_status = 'pending'
        device = f'sensor.{program}_{zone}_status'
        servicedata = {ATTR_ENTITY_ID: device, 'status': new_status}
        await self.hass.services.async_call(DOMAIN, 'set_zone_status', servicedata)

    def enable_zone(self):
        '''Enable zone entity attribute.'''
        return self._enable_zone

    def enable_zone_value(self):
        '''Enable zone entity value.'''
        zone_value = True
        if self._enable_zone is not None:
            zone_value = self.hass.states.is_state(self._enable_zone, "on")
        return zone_value

    def show_config(self):
        '''Enable zone entity attribute.'''
        return self._show_config

    def show_config_value(self):
        '''Enable zone entity value.'''
        show_config_value = True
        if self._show_config is not None:
            show_config_value = self.hass.states.is_state(self._show_config, "on")
        return show_config_value

    async def remaining_time(self):
        """Remaining time or remaining volume."""
        return self._remaining_time

    def run_time(self, seconds_run=0, volume_delivered=0, repeats=1, scheduled=False, water_adjustment=1):
        """Update the run time component."""

        wait = self.wait_value()*60
        #if run manually do not adjust the time
        if scheduled:
            adjust = water_adjustment
        else:
            adjust = 1

        if self._flow_sensor is None:
            #time based
            water = self.water_value()*60
            run_time = (water * adjust * repeats) + (wait * (repeats -1))
        else:
            #volume based/flow sensor
            water = self.water_value() #volume
            flow = self.flow_rate() # flow rate
            delivery_volume = water * adjust
            if volume_delivered > 0: # the cycle has started
                remaining_volume = (delivery_volume * (repeats-1)) +  delivery_volume - volume_delivered
            else:
                remaining_volume = delivery_volume * repeats

            watertime = remaining_volume / flow * 60
            #remaining watering time + remaining waits
            run_time = watertime + (wait * (repeats -1))

        run_time = run_time - seconds_run

        return math.ceil(run_time)

    def last_ran(self):
        '''Last ran datetime attribute.'''

        if self._last_ran is None:
            #default to today and start time
            last_ran = datetime.now(self._localtimezone)
            last_ran = last_ran - timedelta(days=10)
            self._last_ran = last_ran
        return self._last_ran

    def next_run(self,firststarttime, starttime, program_enabled = True, monitor_controller = True):
        '''Determine when a zone will next attempt to run.'''

        #the next time to run in a multi start config
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

        if self.enable_zone_value() is False:
            self._next_run = "disabled"
            return self._next_run
        if self.water_value() == 0:
            self._next_run = "disabled"
            return self._next_run
        if program_enabled is False:
            self._next_run =  "program disabled"
            _LOGGER.debug('program disabled')
            return self._next_run
        if monitor_controller is False:
            self._next_run =  "controller disabled"
            _LOGGER.debug('controller disabled')
            return self._next_run

        if self.check_switch_state() is None:
            self._next_run = "unavailable"
            return self._next_run
        if self.rain_sensor_value() is True and self.ignore_rain_sensor_value() is False:
            self._next_run = "raining"
            return self._next_run
        if self.water_adjust_value() <= 0:
            self._next_run = "adjusted off"
            return self._next_run
        if self.water_source_value() is False:
            self._next_run = "No water source"
            return self._next_run

        if isinstance(self.last_ran(),str):
            _LOGGER.debug('irrigationzone.nextrun str %s',self.last_ran() )
            #2024-08-21T02:05:00.010448
            last_ran = datetime.strptime(self.last_ran(),"%Y-%m-%dT%H:%M:%S.%f%z").replace(hour=starthour, minute=startmin, second=00, microsecond=00)
        if isinstance(self.last_ran(),datetime):
            _LOGGER.debug('irrigationzone.nextrun datetime %s',self.last_ran() )
            last_ran = self.last_ran().replace(hour=starthour, minute=startmin, second=00, microsecond=00)

        try: # Frq is numeric
            if self.run_freq_value() is None:
                #frq is not defined default to daily
                frq = 1
            else:
                frq = int(float(self.run_freq_value()))
            today_start_time = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
            today_begin = datetime.now(self._localtimezone).replace(hour=00, minute=00, second=00, microsecond=00)
            last_ran_day_begin = last_ran.replace(hour=00, minute=00, second=00, microsecond=00)
            if today_start_time > datetime.now(self._localtimezone) and last_ran_day_begin == today_begin:
                #time is in the future and it previously ran today, supports multiple start times
                next_run = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
            elif (today_start_time - last_ran).total_seconds()/86400 < frq:
                #frequency has not been satisfied
                #set last ran datetime to the first runtime of the series and add the frequency
                next_run = last_ran.replace(hour=firststarthour, minute=firststartmin, second=00, microsecond=00) + timedelta(days=frq)
            else:
                #it has been sometime since the zone ran
                next_run = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
                if today_start_time < datetime.now(self._localtimezone):
                    next_run += timedelta(days=1)
                else:
                    pass

            self._next_run =  next_run
            return self._next_run  # noqa: TRY300

        except ValueError:
            #Frq is Alpha
            string_freq = self.run_freq_value()
            # remove spaces, new line, quotes and brackets
            string_freq = string_freq.replace(" ","").replace("\n","").replace("'","").replace('"',"").strip("[]'").split(",")
            string_freq = [x.capitalize() for x in string_freq]
            valid_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            valid_freq = any(item in string_freq for item in valid_days)
            if valid_freq is True:
                #default to today and start time for day based running
                last_ran = datetime.now(self._localtimezone).replace(hour=starthour, minute=startmin, second=00, microsecond=00)
                today = last_ran.isoweekday()
                next_run = last_ran + timedelta(days=100) #arbitary max
                for day in string_freq :
                    try:
                        if self.get_weekday(day) == today and last_ran > datetime.now(self._localtimezone):
                            next_run = last_ran
                        else:
                            next_run = min(self.get_next_dayofweek_datetime(last_ran, day), next_run)
                    except ValueError:
                        next_run = 'Error, invalid value in week day list'
                self._next_run =  next_run
                return self._next_run
            #zone is marked as off
            self._next_run =  "off"
            return self._next_run

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

    def is_raining(self):
        """Assess the rain_sensor including ignore rain_sensor."""
        if self.ignore_rain_sensor_value():
            return False
        return self.rain_sensor_value()

    def should_run(self, scheduled=False):
        '''Determine if the zone should run.'''
        #zone has been turned off or is offline
        if self._next_run in  ["disabled","program disabled", "unavailable","controller disabled"]:
            _LOGGER.debug('zone - should - run false, disabled')
            return False
        if self._next_run in  ["No water source"]:
            _LOGGER.debug('zone - should - run false, no water source')
            return False

        if scheduled is True:
            if self._next_run in  ["raining"]:
                _LOGGER.debug('zone - should - run false, raining')
                return False
            if self._next_run in  ["adjusted off"]:
                _LOGGER.debug('zone - should - run false, adjusted off')
                return False

            # #not time to run yet
            # try:
            #     if self._next_run >  datetime.now(self._localtimezone):
            #         return False
            # except ValueError:
            #     _LOGGER.error('exception processing start time: %s', self._next_run)
            #     return False

        return True
    # end should_run

    def check_switch_state(self):
        """Check the solenoid state if turned off stop this instance."""
        if self.hass.states.is_state(self._switch, "off"):
            return False
        if self.hass.states.is_state(self._switch, "on"):
            return True
        if self.hass.states.is_state(self._switch, "open"):
            return True
        if self.hass.states.is_state(self._switch, "closed"):
            return False
        return None

    async def async_turn_on(self):

        if self.check_switch_state() is False and self._stop is False:
            if self._device_type == 'rainbird':
                # RAINBIRD controller requires a different service call
                await self.hass.services.async_call(
                    RAINBIRD, RAINBIRD_TURN_ON, {ATTR_ENTITY_ID: self._switch, RAINBIRD_DURATION: self.water_value()}
                )
            else:
                #is it a valve or a switch
                valve = self._switch.startswith('valve.')
                if valve:
                    await self.hass.services.async_call(
                        'valve', SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: self._switch}
                    )
                else:
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._switch}
                    )

    async def async_turn_off(self):
        #is it a valve or a switch
        valve = self._switch.startswith('valve.')
        if valve:
            #postion entity defined get the value
            await self.hass.services.async_call(
                'valve', SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self._switch}
            )
        else:
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._switch}
            )

    async def async_turn_on_cycle(self, scheduled=False):
        """Start the watering cycle."""
        self._stop = False
        self._state = "on"
        #initalise the reamining time for display
        if scheduled is True:
            water_adjust_value = self.water_adjust_value()
        else:
            water_adjust_value = 1

        self._remaining_time = self.run_time(repeats=self.repeat_value(), scheduled=scheduled, water_adjustment=water_adjust_value)
        # run the watering cycle, water/wait/repeat
        zeroflowcount = 0
        for i in range(self.repeat_value(), 0, -1):
            seconds_run = 0
            #run time adjusted to 0 skip this zone
            if self._remaining_time <= 0:
                continue
            self._state = "on"
            await self.set_state_sensor(self._state, self._program_name, self._name)
            await asyncio.sleep(1)
            if self.check_switch_state() is False and self._stop is False:
                await self.async_turn_on()
                for _ in range(CONST_LATENCY):
                    if self.check_switch_state() is False:
                        await asyncio.sleep(1)
                    else:
                        break
                else:
                    _LOGGER.warning ("Significant latency has been detected, zone switch may not be updating state correctly, unexpected behaviour may occur, %s", self._switch)
                    continue

            #track the watering

            if self._flow_sensor is not None:
                volume_remaining = self.water_value() * water_adjust_value
                volume_delivered = 0
                while volume_remaining > 0:
                    volume_delivered += self.flow_sensor_value() / 60
                    volume_required = self.water_value() * water_adjust_value
                    volume_remaining = volume_required - volume_delivered
                    self._remaining_time = self.run_time(volume_delivered=volume_delivered, repeats=i, scheduled=scheduled, water_adjustment=water_adjust_value)
                    await asyncio.sleep(1)
                    if self.check_switch_state() is False:
                        self._stop = True
                        break
                    #flow sensor has failed or no water is being provided
                    if self.flow_sensor_value() == 0 or self.water_source_value() is False:
                        zeroflowcount += 1
                        self._stop = True
                        if zeroflowcount > CONST_ZERO_FLOW_DELAY:
                            _LOGGER.warning("No flow detected for %s seconds, turning off solenoid to allow program to complete",CONST_ZERO_FLOW_DELAY)
                            break
                    else:
                        zeroflowcount = 0
            else:
                watertime = math.ceil(self.water_value()*60 * water_adjust_value)
                while watertime > 0:
                    seconds_run += 1
                    watertime = math.ceil(self.water_value()*60 * water_adjust_value) - seconds_run
                    self._remaining_time = self.run_time(seconds_run, repeats=i, scheduled=scheduled, water_adjustment=water_adjust_value)
                    await asyncio.sleep(1)
                    if self.check_switch_state() is False:
                        self._stop = True
                        break
                    #no water is being provided
                    if self.water_source_value() is False:
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
            if self.wait_value() > 0 and i > 1:
                await self.async_eco_off()
                waittime = self.wait_value() * 60
                wait_seconds = 0
                while waittime > 0:
                    seconds_run += 1
                    wait_seconds += 1
                    waittime = self.wait_value() * 60 - wait_seconds
                    self._remaining_time = self.run_time(seconds_run, repeats=i, scheduled=scheduled, water_adjustment=water_adjust_value)
                    if self._stop:
                        break
                    await asyncio.sleep(1)

            if self._stop:
                break
        # End of repeat loop
        await self.async_turn_zone_off()

    async def async_eco_off(self, **kwargs):
        '''Signal the zone to stop.'''
        await self.async_turn_off()
        latency = await self.latency_check()
        #raise an event
        event_data = {
            "action": "zone_turned_off",
            "device_id": self._switch,
            "zone": self._name,
            "state":"eco",
            "latency": latency
        }
        self.hass.bus.async_fire("irrigation_event", event_data)
        self._state = "eco"
        await self.set_state_sensor(self._state, self._program_name, self._name)


    async def async_turn_zone_off(self, **kwargs):
        '''Signal the zone to stop.'''
        self._state = "off"
        self._stop = True
        self._remaining_time = 0
        if  self.hass.states.is_state(self._switch, "off"):
            #switch is already off
            return
        await self.async_turn_off()
        #raise an event
        latency = await self.latency_check()
        event_data = {
            "action": "zone_turned_off",
            "device_id": self._switch,
            "zone": self._name,
            "state":"off",
            "latency": latency
        }
        self.hass.bus.async_fire("irrigation_event", event_data)

    async def latency_check(self):
        '''Ensure switch has turned off and warn.'''
        if not (self.hass.states.is_state(self._switch, "on") or self.hass.states.is_state(self._switch, "off")):
            #switch is offline
            return True

        for i in range(CONST_LATENCY):  # noqa: B007
            if self.check_switch_state() is True: #on
                await asyncio.sleep(1)
            else:
                return False
        _LOGGER.warning('Switch has latency exceding %s seconds, cannot confirm %s state is off', i+1, self._switch)
        return True

    def set_last_ran(self, last_ran):
        '''Update the last ran attribute.'''
        self._last_ran = last_ran

    def validate(self, **kwargs):
        '''Validate inputs.'''
        valid = True
        if self._switch is not None and self.hass.states.async_available(self._switch):
            _LOGGER.error("%s not found switch", self._switch)
            valid = False
        if self._pump is not None and self.hass.states.async_available(self._pump):
            _LOGGER.error("%s not found pump", self._pump)
            valid = False
        if self._run_freq is not None and self.hass.states.async_available(
            self._run_freq):
            _LOGGER.error("%s not found run frequency" , self._run_freq)
            valid = False
        if self._rain_sensor is not None and self.hass.states.async_available(
            self._rain_sensor):
            _LOGGER.error("%s not found rain sensor", self._rain_sensor)
            valid = False
        if self._flow_sensor is not None and self.hass.states.async_available(
            self._flow_sensor):
            _LOGGER.error("%s not found flow sensor", self._flow_sensor)
            valid = False
        if self._water_adjust is not None and self.hass.states.async_available(
            self._water_adjust):
            _LOGGER.error("%s not found adjustment", self._water_adjust)
            valid = False
        return valid

    async def async_test_zone(self, scheduled):
        '''Show simulation results.'''
        _LOGGER.warning("----------------------------")
        _LOGGER.warning("Zone:                     %s", self._name)
        _LOGGER.warning("Should run:               %s", self.should_run(scheduled=scheduled))
        _LOGGER.warning("Last Run time:            %s", self._last_ran)
        _LOGGER.warning("Run time:                 %s", self.run_time(repeats=self.repeat_value()))
        _LOGGER.warning("Water Value:              %s", self.water_value())
        _LOGGER.warning("Wait Value:               %s", self.wait_value())
        _LOGGER.warning("Repeat Value:             %s", self.repeat_value())
        _LOGGER.warning("Rain sensor value:        %s", self.rain_sensor_value())
        _LOGGER.warning("Ignore rain sensor Value: %s", self.ignore_rain_sensor_value())
        _LOGGER.warning("Run frequency Value:      %s", self.run_freq_value())
        _LOGGER.warning("Flow Sensor Value:        %s", self.flow_sensor_value())
        _LOGGER.warning("Adjuster Value:           %s", self.water_adjust_value())
