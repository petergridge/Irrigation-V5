'''Switch entity definition.'''

import asyncio
from datetime import datetime, timedelta
import logging
import re
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_start
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_DELAY,
    ATTR_DEVICE_TYPE,
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_HISTORICAL_FLOW,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_INTERLOCK,
    ATTR_IRRIGATION_ON,
    ATTR_LAST_RAN,
    ATTR_MONITOR_CONTROLLER,
    ATTR_NEXT_RUN,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REMAINING,
    ATTR_REPEAT,
    ATTR_RUN_FREQ,
    ATTR_SCHEDULED,
    ATTR_SHOW_CONFIG,
    ATTR_START,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_ZONE,
    ATTR_ZONES,
    CONST_LATENCY,
    CONST_SWITCH,
    DOMAIN,
    TIME_STR_FORMAT,
)
from .irrigationzone import IrrigationZone
from .pump import PumpClass

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow."""
    name = config_entry.title
    unique_id = config_entry.entry_id
    if config_entry.options != {}:
        async_add_entities([IrrigationProgram(hass, unique_id, config_entry.options, name,config_entry)])
    else:
        async_add_entities([IrrigationProgram(hass, unique_id, config_entry.data, name, config_entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "run_zone",
        {
            vol.Required(ATTR_ZONE): cv.ensure_list,
        },
        "entity_run_zone",
    )
    platform.async_register_entity_service(
        "toggle_zone",
        {
            vol.Required(ATTR_ZONE): cv.ensure_list,
        },
        "entity_toggle_zone",
    )

    platform.async_register_entity_service(
        "reset_runtime",
        {

        },
        "entity_reset_runtime",
    )

    platform.async_register_entity_service(
        "run_simulation",
        {
            vol.Optional(ATTR_SCHEDULED, default=True): cv.boolean
        },
        "async_simulate_program",
    )

class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""

    _attr_has_entity_name = True
    def __init__(
        self, hass:HomeAssistant, unique_id, config, device_id, config_entry
    ) -> None:
        """Initialize a Irrigation program."""
        self.config_entry = config_entry
        self.hass = hass
        self._config = config
        self._name = config.get(CONF_NAME, device_id)
        self._start_time = config.get(ATTR_START)
        self._show_config = config.get(ATTR_SHOW_CONFIG)
        self._run_freq = config.get(ATTR_RUN_FREQ)
        self._irrigation_on = config.get(ATTR_IRRIGATION_ON)
        self._monitor_controller = config.get(ATTR_MONITOR_CONTROLLER)
        self._inter_zone_delay = config.get(ATTR_DELAY)
        self._zones = config.get(ATTR_ZONES)
        self._interlock = config.get(ATTR_INTERLOCK)
        self.scheduled = False
        self._device_type = config.get(ATTR_DEVICE_TYPE)
        self._device_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._attr_unique_id = unique_id
        self._state = False
        self._last_run = None
        self._irrigationzones = []
        self._pumps = []
        self._run_zone = []
        self._extra_attrs = {}
        self._program_remaining = 0
        self._unsub_point_in_time = None
        self._unsub_start = None
        self._unsub_monitor_program_enabled = None
        self._unsub_monitor_program_frequency = None
        self._unsub_monitor_start_time = None
        self._unsub_monitor_zone_enabled = []
        self._unsub_monitor_zone_frequency = []
        self._unsub_monitor_zone_rain = []
        self._unsub_monitor_zone_ignore_rain = []
        self._unsub_monitor_zone_adjust = []

    async def async_will_remove_from_hass(self) -> None:
        """Cancel next update."""
        if self._unsub_point_in_time:
            self._unsub_point_in_time()
            self._unsub_point_in_time = None
        if self._unsub_start:
            self._unsub_start()
            self._unsub_start = None
        if self._unsub_monitor_program_enabled:
            self._unsub_monitor_program_enabled()
            self._unsub_monitor_program_enabled = None
        if self._unsub_monitor_program_frequency:
            self._unsub_monitor_program_frequency()
            self._unsub_monitor_program_frequency = None
        for unsub in self._unsub_monitor_zone_enabled:
            unsub()
        self._unsub_monitor_zone_enabled = []
        for unsub in self._unsub_monitor_zone_frequency:
            unsub()
        self._unsub_monitor_zone_frequency = []
        for unsub in self._unsub_monitor_zone_rain:
            unsub()
        self._unsub_monitor_zone_rain = []
        for unsub in self._unsub_monitor_zone_ignore_rain:
            unsub()
        self._unsub_monitor_zone_ignore_rain = []
        for unsub in self._unsub_monitor_zone_adjust:
            unsub()
        self._unsub_monitor_zone_adjust = []

        if self._unsub_monitor_start_time:
            self._unsub_monitor_start_time()
            self._unsub_monitor_start_time = None

        await self.async_turn_off()

    def get_next_interval(self):
        """Next time an update should occur."""
        now = dt_util.utcnow()
        timestamp = dt_util.as_timestamp(now)
        interval = 60
        delta = interval - (timestamp % interval)
        next_interval = now + timedelta(seconds=delta)
        return next_interval

    def format_attr(self, part_a, part_b):
        """Format attribute names."""
        return slugify(f"{part_a}_{part_b}")

    @callback
    async def point_in_time_listener(self, time_date):
        """Get the latest time and check if irrigation should start."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )
        time = dt_util.as_local(dt_util.utcnow()).strftime(TIME_STR_FORMAT)
        string_times = self.start_time_value()
        string_times = string_times.replace(" ","").replace("\n","").replace("'","").replace('"',"").strip("[]'").split(",")
        if (self._state is False and
            time in string_times and
            self.irrigation_on_value() is True and
            self.monitor_controller_value() is True):
                self._run_zone = []
                self.scheduled = True
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())

        self.async_write_ha_state()

    @callback
    async def update_next_run(self, entity=None, old_status=None, new_status=None, single_zone=None):
        """Update the next run callback."""
        _LOGGER.debug('_____________________')
        #determine next run time
        time = dt_util.as_local(dt_util.utcnow()).strftime(TIME_STR_FORMAT)
        string_times = self.start_time_value()
        string_times = string_times.replace(" ","").replace("\n","").replace("'","").replace('"',"").strip("[]'").split(",")
        string_times.sort()
        next_start_time = string_times[0]
        _LOGGER.debug('next start time: %s', next_start_time)
        for stime in string_times:
            _LOGGER.debug('stime: %s', stime)
            if not re.search("^([0-2]?[0-9]:[0-5][0-9]:00)", stime):
                continue
            if stime > time:
                _LOGGER.debug('stime %s > time %s',stime,time)
                x = string_times.index(stime)
                next_start_time = string_times[x]
                break
        #starttime is not valid or missing
        if not next_start_time:
            await self.hass.services.async_call(
                'input_text', 'set_value', {ATTR_ENTITY_ID: self._start_time, 'value':'08:00:00'}
                    )
        if single_zone:
            await self.set_zone_next_run(single_zone, string_times[0], next_start_time)
        else:
            for zone in self._irrigationzones:
                await self.set_zone_next_run(zone, string_times[0], next_start_time)

        self.async_schedule_update_ha_state()

    async def set_zone_next_run(self,zone, first_start_time, start_time):
        """Set next start time."""
        attr = self.format_attr(zone.name(), ATTR_NEXT_RUN)
        next_run = zone.next_run(first_start_time, start_time,self.irrigation_on_value())
        _LOGGER.debug('post next_run %s',next_run)
        self._extra_attrs[attr] = next_run
        if next_run in  ['off','unavailable','program disabled']: #'raining','adjusted off',
            await self.set_sensor_status('disabled', self._name, zone.name())

    async def async_added_to_hass(self):  # noqa: C901
        """Add listener."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )

        @callback
        async def hass_started(event):  # noqa: C901
            last_state = await self.async_get_last_state()
            self._extra_attrs = {}
            if self._start_time is not None:
                self._extra_attrs[ATTR_START] = self._start_time
            if self._run_freq is not None:
                self._extra_attrs[ATTR_RUN_FREQ] = self._run_freq
            if self._monitor_controller is not None:
                self._extra_attrs[ATTR_MONITOR_CONTROLLER] = self._monitor_controller
            if self._irrigation_on is not None:
                self._extra_attrs[ATTR_IRRIGATION_ON] = self._irrigation_on
            self._extra_attrs[ATTR_SHOW_CONFIG] = f'binary_sensor.{slugify(self._name)}_config'
            if self._inter_zone_delay is not None:
                self._extra_attrs[ATTR_DELAY] = self._inter_zone_delay

            #create the zone class
            zonedict = {}
            pumps = {}
            for zone in self._zones:
                #initialise historical flow
                z_name = zone.get(ATTR_ZONE).split(".")[1]
                z_hist_flow = None
                if zone.get(ATTR_FLOW_SENSOR) is not None:
                    attr = self.format_attr(z_name, ATTR_HISTORICAL_FLOW)
                    z_hist_flow = last_state.attributes.get(attr,1)
                # set the last ran time
                attr = self.format_attr(z_name, ATTR_LAST_RAN)
                if last_state:
                    self._last_run = last_state.attributes.get(attr,None)
                #add the zone class
                #use a set() to maintain uniqueness as this gets processed twice, when HA is started
                #and is reprocessed when a config flow is processed
                zonedict[z_name] = IrrigationZone(
                        self.hass,
                        self._name,
                        zone,
                        self._device_type,
                        zone.get(ATTR_RUN_FREQ, self._run_freq),
                        z_hist_flow,
                        self._last_run,
                    )
            self._irrigationzones = zonedict.values()
            #set up to monitor these entities
            self._unsub_monitor_start_time = async_track_state_change(self.hass, self._start_time, self.update_next_run)
            if self._irrigation_on:
                self._unsub_monitor_program_enabled = async_track_state_change(self.hass, self._irrigation_on, self.update_next_run)
            if self._run_freq:
                self._unsub_monitor_program_frequency = async_track_state_change(self.hass, self._run_freq, self.update_next_run)
            for zone in self._irrigationzones:
                if zone.enable_zone() :
                    self._unsub_monitor_zone_enabled.append(async_track_state_change(self.hass, zone.enable_zone(), self.update_next_run))
                if zone.run_freq():
                    self._unsub_monitor_zone_frequency.append(async_track_state_change(self.hass, zone.run_freq(), self.update_next_run))
                if zone.rain_sensor():
                    self._unsub_monitor_zone_rain.append(async_track_state_change(self.hass, zone.rain_sensor(), self.update_next_run))
                if zone.ignore_rain_sensor():
                    self._unsub_monitor_zone_ignore_rain.append(async_track_state_change(self.hass, zone.ignore_rain_sensor(), self.update_next_run))
                if zone.water_adjust():
                    self._unsub_monitor_zone_adjust.append(async_track_state_change(self.hass, zone.water_adjust(), self.update_next_run))

            # build attributes in run order
            zones = await self.build_run_script(True)
            # zone loop to initialise the attributes
            zonecount = 0

            for zone in zones:
                zonecount += 1
                if zone.pump() is not None:
                    #create pump - zone list
                    if zone.pump() not in pumps:
                        pumps[zone.pump()] = [zone.switch()]
                        _LOGGER.debug("creating pump %s", zone.pump())
                    else:
                        pumps[zone.pump()].append(zone.switch())
                        _LOGGER.debug("Appending zone to pump %s", zone.pump())
                # Build Zone Attributes to support the custom card
                z_name =  zone.name()
                attr = self.format_attr("zone" + str(zonecount), CONF_NAME)
                self._extra_attrs[attr] = zone.name()
                # set the last ran time
                attr = self.format_attr(z_name, ATTR_LAST_RAN)
                self._extra_attrs[attr] = zone.last_ran()

                # setup zone attributes to populate the Custom card
                attr = self.format_attr(z_name, ATTR_REMAINING)
                self._extra_attrs[attr] = "%d:%02d:%02d" % (0, 0, 0)
                self._extra_attrs[self.format_attr(z_name,'status')] = f'sensor.{slugify(self._name)}_{slugify(z_name)}_status'
                if zone.switch() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_ZONE)] = zone.switch()
                if zone.water() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_WATER)] = zone.water()
                if zone.wait() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_WAIT)] = zone.wait()
                if zone.repeat() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_REPEAT)] = zone.repeat()
                if zone.pump() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_PUMP)] = zone.pump()
                if zone.flow_sensor() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_FLOW_SENSOR)] = zone.flow_sensor()
                if zone.water_adjust() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_WATER_ADJUST)] = zone.water_adjust()
                if zone.run_freq() is not None  and self._run_freq != zone.run_freq():
                    self._extra_attrs[self.format_attr(z_name,ATTR_RUN_FREQ)] = zone.run_freq()
                if zone.rain_sensor() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_RAIN_SENSOR)] = zone.rain_sensor()
                if zone.ignore_rain_sensor() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_IGNORE_RAIN_SENSOR)] = zone.ignore_rain_sensor()
                if zone.enable_zone() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_ENABLE_ZONE)] = zone.enable_zone()
                self._extra_attrs[self.format_attr(z_name,ATTR_SHOW_CONFIG)] = f'binary_sensor.{slugify(self._name)}_{slugify(z_name)}_config'

            self._extra_attrs["zone_count"] = zonecount
            # create pump class to start/stop pumps
            for pump, zones in pumps.items():
                #pass pump_switch, list of zones, off_delay
                _LOGGER.debug("pump class added %s", pump)
                self._pumps.append(PumpClass(self.hass, pump, zones))

            #turn off the underlying switches as a precaution
            for pump in pumps.keys():  # noqa: SIM118
                if self.hass.states.is_state(pump, "on"):
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: pump}
                        )

            for zone in self._irrigationzones:
                if self.hass.states.is_state(zone.switch(), "on"):
                    await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: zone.switch()}
                    )
            # Validate the referenced objects now that HASS has started
            if self._monitor_controller is not None:
                if self.hass.states.async_available(self._monitor_controller):
                    _LOGGER.error(
                        "%s not found, check your configuration",
                        self._monitor_controller,
                    )
            if self._run_freq is not None:
                if self.hass.states.async_available(self._run_freq):
                    _LOGGER.error(
                        "%s not found, check your configuration", self._run_freq
                    )
            await asyncio.sleep(1)
            for zone in self._irrigationzones:
                # run validation over the zones
                zone.validate()

           #calculate the next run
            await self.update_next_run()

            self.async_schedule_update_ha_state()

        #setup the callback to kick in when HASS has started
        #listen for config_flow change and apply the updates
        self._unsub_start = async_at_start(self.hass,hass_started)

        @callback
        async def hass_shutdown(event):
            '''Make sure everything is shut down.'''
            for zone in self._irrigationzones:
                await zone.async_turn_off()
            await asyncio.sleep(1)

        #setup the callback tolisten for the shut down
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, hass_shutdown
        )

        await super().async_added_to_hass()

    async def entity_run_zone(self, zone) -> None:
        '''Run a specific zone.'''
        for stopzone in self._irrigationzones:
            await stopzone.async_turn_off()

        await asyncio.sleep(1)
        self._run_zone = zone
        self.scheduled = False
        loop = asyncio.get_event_loop()
        loop.create_task(self.async_turn_on())
        await asyncio.sleep(1)

    async def entity_toggle_zone(self, zone) -> None:
        '''Run a specific zone.'''
        #check if the zone is running
        toggle_off = False
        for checkzone in zone:
            if self.hass.states.get(checkzone).state == 'on':
                toggle_off = True
        # turn off all zones in preperation for running
        for stopzone in self._irrigationzones:
            await stopzone.async_turn_off()
        #a zone in the list was running so exit
        if toggle_off:
            return
        # no zones in the list running so start them
        await asyncio.sleep(1)
        self._run_zone = zone
        self.scheduled = False
        loop = asyncio.get_event_loop()
        loop.create_task(self.async_turn_on())
        await asyncio.sleep(1)

    async def async_simulate_program(self, scheduled) -> None:
        '''Execute a simulation tests.'''
        _LOGGER.warning("Irrigation Program: %s:",self._name)
        runscript = await self.build_run_script(True)
        if len(runscript) == 0:
            _LOGGER.warning("No zones to run based on current configuration")
        for zone in runscript.values():
            text = "Zone to run: " + zone.name()
            _LOGGER.warning(text)
        #list all zone details
        for testzone in self._irrigationzones:
            await testzone.async_test_zone(scheduled)

    async def entity_reset_runtime(self) -> None:
        '''Reset last runtime to support testing.'''

        for zone in self._irrigationzones:
            localtimezone = ZoneInfo(self.hass.config.time_zone)
            last_ran = datetime.now().astimezone(tz=localtimezone) - timedelta(days=10)
            zone.set_last_ran(last_ran)
            #update the attributes
            attr = self.format_attr(
                    zone.name(),
                    ATTR_LAST_RAN,
                )
            self._extra_attrs[attr] = last_ran
            self.async_schedule_update_ha_state()
        await self.update_next_run()

    def inter_zone_delay(self):
        """Return interzone delay value."""
        if isinstance(self._inter_zone_delay,str):
            #supports config version 1
            return  int(
                float(
                    self.hass.states.get(
                        self._inter_zone_delay
                    ).state
                )
            )

    @property
    def name(self):
        """Return the name of the variable."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_attrs

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    def irrigation_on_value(self):
        '''Zone  entity value.'''
        value = True
        if self._irrigation_on is not None:
            if self.hass.states.get(self._irrigation_on).state == 'off':
                value = False
        return value

    def monitor_controller_value(self):
        '''Zone  entity value.'''
        value = True
        if self._monitor_controller is not None:
            if self.hass.states.get(self._monitor_controller).state == 'off':
                value = False
        return value

    def start_time_value(self):
        '''Zone  entity value.'''
        value = None
        if self._start_time is not None:
            value = self.hass.states.get(self._start_time).state
        return value

    def format_run_time(self, runtime):
        """Format the runtime for attributes."""
        hourmin = divmod(runtime, 3600)
        minsec = divmod(hourmin[1], 60)
        return "%d:%02d:%02d" % (hourmin[0], minsec[0], minsec[1])

    async def set_sensor_status(self, state, program, zone):
        '''Set the runtime on the relevant sensor.'''
        device = f'sensor.{slugify(program)}_{slugify(zone)}_status'
        servicedata = {ATTR_ENTITY_ID: device, 'status': state}
        await self.hass.services.async_call(DOMAIN, "set_zone_status", servicedata)

    async def build_run_script(self, allzones=False):
        """Build the run script based on each zones data."""

        zones = []
        for zone in self._irrigationzones:

            if not allzones:
                # allzones ignores checks, only used when setting up program

                if self._run_zone:
                # Zone has been manually run from service call
                    if zone.switch() not in self._run_zone:
                        continue
                #auto_run where program started based on start time
                if zone.should_run(self.scheduled) is False :
                    _LOGGER.debug('should run false %s', zone.name())
                            #calculate the next run
                    await self.update_next_run(single_zone=zone)
                    continue

                # set the runtime attributes for zones that will run
                zoneremaining = self.format_attr(zone.name(), ATTR_REMAINING)
                runtime = self.format_run_time(
                    zone.run_time(repeats=zone.repeat_value(),scheduled=self.scheduled)
                )
                self._extra_attrs[zoneremaining] = runtime
                await self.set_sensor_status('pending', self._name, zone.name())
            zones.append(zone)

        return zones

    async def async_calculate_program_remaining(self,zones):
            """Calculate the remaining time for the program."""
            self._program_remaining = 0
            for thiszone in zones:
                attr_value = self._extra_attrs["{}{}".format(thiszone.name(),"_remaining")]
                attr_runtime = sum(x * int(t) for x, t in zip([3600, 60, 1], attr_value.split(":")))
                self._program_remaining += attr_runtime
            self._extra_attrs[ATTR_REMAINING] = self.format_run_time(self._program_remaining)

    async def async_finalise_run(self, zone, last_ran):
        """Clean up once it has run."""
        #clean up after the run
        zonelastran = self.format_attr(
                zone.name(),
                ATTR_LAST_RAN,
            )
        if not self._run_zone and self._state is True and last_ran is not None:
            #not manual run or aborted
            self._extra_attrs[zonelastran] = last_ran
            zone.set_last_ran(last_ran)
            _LOGGER.debug('finalise run - last_ran %s', last_ran)

        #calculate the next run
        await self.update_next_run(single_zone=zone)

        # update the historical flow rate
        if zone.flow_sensor():
            #record the flow rate from this run
            attr = self.format_attr(
                    zone.name(),
                    ATTR_HISTORICAL_FLOW,
                )
            self._extra_attrs[attr] = zone.flow_rate()

        #reset the time remaining to 0
        attr = self.format_attr(
                zone.name(),
                ATTR_REMAINING,
            )
        self._extra_attrs[attr] = "%d:%02d:%02d" % (0, 0, 0)
        await self.set_sensor_status('off', self._name, zone.name())

        self._extra_attrs[ATTR_REMAINING] = "%d:%02d:%02d" % (0, 0, 0)

    async def async_turn_on(self, **kwargs):
        '''Turn on the switch.'''

        if self._state is True:
            #program is still running
            return
        #stop all running programs except the calling program
        if self._interlock:
            #how to determine if two programs have the same start time?
            data = {'ignore':self.name}
            await self.hass.services.async_call(DOMAIN, "stop_programs", data)
        # start pump monitoring
        loop = asyncio.get_event_loop()
        for thispump in self._pumps:
            loop.create_task(thispump.async_monitor())
        #use time at start to set the last ran attribute of the zones
        #all zones will have the last ran of the program start
        p_last_ran = dt_util.now()

        zones = await self.build_run_script(False)
        if len(zones)>0:
              #raise event when the program starts
              event_data = {
                             "action": "program_turned_on",
                             "device_id": self._device_id,
                             "scheduled": self.scheduled,
                             "program": self._name
              }
              self.hass.bus.async_fire("irrigation_event", event_data)
        else:
            #No zones to run
            _LOGGER.debug('No zones to run')
            return
        self._state = True

        for count, zone in enumerate(zones):
            if self._state is False:
                #program terminated clean up
                await self.async_finalise_run(zone,p_last_ran)
                continue
            #if this is the second zone and interzone delay is defined
            if count > 0:
                #check if there is a next zone
                if count < len(zones):
                    if self.inter_zone_delay() is not None:
                        await asyncio.sleep(self.inter_zone_delay())
            #start zone
            if self._state is True:
                loop = asyncio.get_event_loop()
                loop.create_task(zone.async_turn_on(self.scheduled))
                await asyncio.sleep(1)
                #switch has gone off-line
                if zone.check_switch_state() is None:
                    _LOGGER.warning("Switch %s has become unavailable",zone.name())
                    event_data = {
                        "action": "zone_became_unavailable",
                        "device_id": self._device_id,
                        "scheduled": self.scheduled,
                        "zone": zone.name(),
                        "pump": zone.pump(),
                        "runtime": zone.run_time(zone.repeat_value()),
                        "water": zone.water_value(),
                        "wait": zone.wait_value(),
                        "repeat": zone.repeat_value(),
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)
                    continue

                # latency issue loop a few times to see if the switch turns on
                # otherwise give a warning and skip this switch
                for _ in range(CONST_LATENCY):
                    if zone.check_switch_state() is False:
                        await asyncio.sleep(1)
                    else:
                        break
                else:
                    _LOGGER.warning('Significant latency has been detected, unexpected behaviour may occur, %s',zone.switch())
                    continue

                event_data = {
                    "action": "zone_turned_on",
                    "device_id": self._device_id,
                    "scheduled": self.scheduled,
                    "zone": zone.name(),
                    "pump": zone.pump(),
                    "runtime": zone.run_time(zone.repeat_value()),
                    "water": zone.water_value(),
                    "wait": zone.wait_value(),
                    "repeat": zone.repeat_value(),
                }
                self.hass.bus.async_fire("irrigation_event", event_data)

            #wait for the zones to complete
            zone_running = True
            while zone_running and self._state is True:
                zone_running = False
                if self._state is False:
                    break
                #check zone
                attr = self.format_attr(
                        zone.name(),
                        ATTR_REMAINING,
                    )
                remaining_time = self.format_run_time(
                    await zone.remaining_time()
                )
                self._extra_attrs[attr] = remaining_time
                #continue until zone finished
                if await zone.state() in ["on","eco"]:
                    zone_running = True

                #calculate the remaining time for the program
                await self.async_calculate_program_remaining(zones)
                self.async_schedule_update_ha_state()
                await asyncio.sleep(1)
                if not zone_running:
                    break

            #clean up after the run
            await self.async_finalise_run(zone,p_last_ran)
            #calculate the next run
#            await self.update_next_run()

            #zone finished
            self.async_schedule_update_ha_state()

        #run is complete stop pump monitoring
        for pump in self._pumps:
            loop.create_task(pump.async_stop_monitoring())

        event_data = {
            "action": "program_turned_off",
            "device_id": self._device_id,
            "completed": self._state, #False = terminated
            "program": self._name
        }
        self.hass.bus.async_fire("irrigation_event", event_data)
        self._state = False
        self.scheduled = False
        self._run_zone = []
        #program finished
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        '''Stop the switch/program.'''
        if self._state is True:
            self._state = False
            self.scheduled = False
            self._run_zone = []
            for zone in self._irrigationzones:
                await zone.async_turn_off()
