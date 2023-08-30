''' Switch entity definition'''

import asyncio
import logging
import voluptuous as vol
from datetime import timedelta
from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
    ATTR_ENTITY_ID
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
)
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time, async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util
from .const import (
    DOMAIN,
    ATTR_DELAY,
    ATTR_DEVICE_TYPE,
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_IRRIGATION_ON,
    ATTR_LAST_RAN,
    ATTR_NEXT_RUN,
    ATTR_MONITOR_CONTROLLER,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REMAINING,
    ATTR_REPEAT,
    ATTR_RUN_FREQ,
    ATTR_SHOW_CONFIG,
    ATTR_START,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_ZONE,
    ATTR_ZONE_GROUP,
    ATTR_ZONES,
    CONST_SWITCH,
    ATTR_GROUPS,
    ATTR_HISTORICAL_FLOW,
    ATTR_INTERLOCK,
    CONST_LATENCY,
    ATTR_SCHEDULED,
    )
from .irrigationzone import IrrigationZone
from .pump import PumpClass
TIME_STR_FORMAT = "%H:%M:00"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow"""
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
        self._groups = config.get(ATTR_GROUPS)
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
        self.unsub = None
        self.unsub_start = None
        self._unsub_monitor_start = None
        self._unsub_monitor_program_enabled = None
        self._unsub_monitor_program_frequency = None
        self._unsub_monitor_zone_enabled = []
        self._unsub_monitor_zone_frequency = []
        self._unsub_monitor_zone_switch = []

    async def async_will_remove_from_hass(self) -> None:
        """Cancel next update."""
        if self.unsub:
            self.unsub()
            self.unsub = None
        if self.unsub_start:
            self.unsub_start()
            self.unsub_start = None
        if self._unsub_monitor_start:
            self._unsub_monitor_start()
            self._unsub_monitor_start = None
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
        for unsub in self._unsub_monitor_zone_switch:
            unsub()

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
        """Helper to format attribute names"""
        return slugify("{}_{}".format(part_a, part_b))

    @callback
    async def point_in_time_listener(self, time_date):
        """Get the latest time and check if irrigation should start"""
        # await self.async_update()
        self.unsub = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )
        time = dt_util.as_local(dt_util.utcnow()).strftime(TIME_STR_FORMAT)
        if (self._state is False and
            time == self.start_time_value() and
            self.irrigation_on_value() is True and
            self.monitor_controller_value() is True):
                self._run_zone = []
                self.scheduled = True
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())

        self.async_write_ha_state()


    async def async_added_to_hass(self):
        self.unsub = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )

        @callback
        async def hass_started(event):

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

                #use a set() to maintain uniqueness as this gets processed twice when HA is started
                #but must be reprocessed when a config flow is processed
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
            for zone in self._irrigationzones:
                if zone.enable_zone() :
                    self._unsub_monitor_zone_enabled.append(async_track_state_change(self.hass, zone.enable_zone(), update_next_run))
                if zone.run_freq():
                    self._unsub_monitor_zone_frequency.append(async_track_state_change(self.hass, zone.run_freq(), update_next_run))

            # build attributes in run order
            groups = await self.build_run_script(True)
            # zone loop to initialise the attributes
            zonecount = 0
            pumps = {}
            for group in groups.values():
                z_group = []
                if len(group) > 1:
                    #build the group attr
                    for zone in group:
                        z_group.append(zone.switch())
                #process each zone in the group
                for zone in group:
                    zonecount += 1
                    if zone.pump() is not None:
                        #create pump - zone list
                        if zone.pump() not in pumps:
                            pumps[zone.pump()] = [zone.switch()]
                        else:
                            pumps[zone.pump()].append(zone.switch())
                    # Build Zone Attributes to support the custom card
                    z_name =  zone.name()
                    attr = self.format_attr("zone" + str(zonecount), CONF_NAME)
                    self._extra_attrs[attr] = zone.name()
                    if z_group:
                        attr = self.format_attr(z_name, ATTR_ZONE_GROUP)
                        self._extra_attrs[attr] = z_group
                    # set the last ran time
                    attr = self.format_attr(z_name, ATTR_LAST_RAN)
                    self._extra_attrs[attr] = zone.last_ran()
                    attr = self.format_attr(z_name, ATTR_NEXT_RUN)
                    hour = int(self.hass.states.get(self._start_time).state.split(':')[0])
                    minute = int(self.hass.states.get(self._start_time).state.split(':')[1])
                    self._extra_attrs[attr] = zone.next_run(hour, minute,self.irrigation_on_value())

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
                    if zone.zone_group() is not None:
                        self._extra_attrs[self.format_attr(z_name,ATTR_ZONE_GROUP)] = zone.zone_group()
                    if zone.ignore_rain_sensor() is not None:
                        self._extra_attrs[self.format_attr(z_name,ATTR_IGNORE_RAIN_SENSOR)] = zone.ignore_rain_sensor()
                    if zone.enable_zone() is not None:
                        self._extra_attrs[self.format_attr(z_name,ATTR_ENABLE_ZONE)] = zone.enable_zone()
                    self._extra_attrs[self.format_attr(z_name,ATTR_SHOW_CONFIG)] = f'binary_sensor.{slugify(self._name)}_{slugify(z_name)}_config'

            self._extra_attrs["zone_count"] = zonecount
            # create pump class to start/stop pumps
            for pump, zones in pumps.items():
                #pass pump_switch, list of zones, off_delay
                self._pumps.append(PumpClass(self.hass, pump, zones))

            #turn off the underlying switches as a precaution
            for pump in pumps.keys():
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

            #set the next run attribute
            await update_next_run(None, None, None)

        #setup the callback to kick in when HASS has started
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, hass_started
        )
        #listen for config_flow change and apply the updates
        self.unsub_start = async_at_start(self.hass,hass_started)

        @callback
        async def update_next_run(entity, old_status, new_status):
            #process all the zones for next run
            hour = int(self.hass.states.get(self._start_time).state.split(':')[0])
            minute = int(self.hass.states.get(self._start_time).state.split(':')[1])
            for zone in self._irrigationzones:
                attr = self.format_attr(zone.name(), ATTR_NEXT_RUN)
                next_run = zone.next_run(hour, minute,self.irrigation_on_value())
                self._extra_attrs[attr] = next_run
                if next_run == 'off':
                    await self.set_sensor_status('disabled', self._name, zone.name())
                else:
                    await self.set_sensor_status('off', self._name, zone.name())
            self.async_schedule_update_ha_state()

        #monitor the entities that impact the next run time
        self._unsub_monitor_start = async_track_state_change(self.hass, self._start_time, update_next_run)
        if self._irrigation_on:
            self._unsub_monitor_program_enabled = async_track_state_change(self.hass, self._irrigation_on, update_next_run)
        if self._run_freq:
            self._unsub_monitor_program_frequency = async_track_state_change(self.hass, self._run_freq, update_next_run)

        @callback
        async def hass_shutdown(event):
            '''make sure everything is shut down'''
            for zone in self._irrigationzones:
                await zone.async_turn_off()
            await asyncio.sleep(1)

        #setup the callback tolisten for the shut down
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, hass_shutdown
        )

        await super().async_added_to_hass()

    async def entity_run_zone(self, zone) -> None:
        '''Run a specific zone'''
        for stopzone in self._irrigationzones:
            await stopzone.async_turn_off()

        await asyncio.sleep(1)
        self._run_zone = zone
        self.scheduled = False
        loop = asyncio.get_event_loop()
        loop.create_task(self.async_turn_on())
        await asyncio.sleep(1)

    async def entity_toggle_zone(self, zone) -> None:
        '''Run a specific zone'''
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
        '''execute a simulation tests'''
        _LOGGER.warning("Irrigation Program: %s:",self._name)
        runscript = await self.build_run_script(True)
        if len(runscript) == 0:
            _LOGGER.warning("No zones to run based on current configuration")
        for group in runscript.values():
            if len(runscript) > 0:
                text = "Grouped zones to run: "
            else:
                text = "Zone to run: "
            for zone in group:
                text += zone.name() + " "
            _LOGGER.warning(text)
        #list all zone details
        for testzone in self._irrigationzones:
            await testzone.async_test_zone(scheduled)

    async def entity_reset_runtime(self) -> None:
        '''reset last runtime to support testing'''
        for zone in self._irrigationzones:
            zone.set_last_ran(None)
            #update the attributes
            zonelastran = self.format_attr(
                    zone.name(),
                    ATTR_LAST_RAN,
                )
            self._extra_attrs.pop(zonelastran)
            self.async_schedule_update_ha_state()

    def inter_zone_delay(self):
        """ return interzone delay value"""
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
        '''zone group entity value'''
        value = True
        if self._irrigation_on is not None:
            if self.hass.states.get(self._irrigation_on).state == 'off':
                value = False
        return value

    def monitor_controller_value(self):
        '''zone group entity value'''
        value = True
        if self._monitor_controller is not None:
            if self.hass.states.get(self._monitor_controller).state == 'off':
                value = False
        return value

    def start_time_value(self):
        '''zone group entity value'''
        value = None
        if self._start_time is not None:
            value = self.hass.states.get(self._start_time).state
        return value

    def format_run_time(self, runtime):
        """Format the runtime for attributes"""
        hourmin = divmod(runtime, 3600)
        minsec = divmod(hourmin[1], 60)
        return "%d:%02d:%02d" % (hourmin[0], minsec[0], minsec[1])

    async def set_sensor_status(self, state, program, zone):
        '''set the runtime on the relevant sensor'''
        device = f'sensor.{slugify(program)}_{slugify(zone)}_status'
        servicedata = {ATTR_ENTITY_ID: device, 'status': state}
        await self.hass.services.async_call(DOMAIN, "set_zone_status", servicedata)

    async def build_run_script(self, allzones=False):
        """Build the run script based on each zones data"""
        # allzones ignores checks, used when setting up program
        def check_group_config(pzone):
        # has the zone been configured in a group
            if self._groups is not None:
                for count, group in enumerate(self._groups):
                    if pzone in group[ATTR_ZONES]:
                        return count

        #build run list for this execution
        groups = {}
        for zonecount, zone in enumerate(self._irrigationzones):
            zonenextrun = self.format_attr(
                    zone.name(),
                    ATTR_NEXT_RUN,
                )

            hour = int(self.hass.states.get(self._start_time).state.split(':')[0])
            minute = int(self.hass.states.get(self._start_time).state.split(':')[1])
            self._extra_attrs[zonenextrun] = zone.next_run(hour, minute,self.irrigation_on_value())

            if not allzones:

                if self._run_zone:
                # Zone has been manually run from service call
                    if zone.switch() not in self._run_zone:
                        continue
                #auto_run where program started based on start time
                if zone.should_run(self.scheduled) is False :
                    continue

                # set the runtime attributes for zones that will run
                zoneremaining = self.format_attr(zone.name(), ATTR_REMAINING)
                runtime = self.format_run_time(
                    zone.run_time(repeats=zone.repeat_value(),scheduled=self.scheduled)
                )
                self._extra_attrs[zoneremaining] = runtime
                await self.set_sensor_status('pending', self._name, zone.name())

            #build zone groupings that will run concurrently
            groupkey = zonecount
            if self._run_zone:
                zgroup = self._run_zone
            else:
                zgroup = check_group_config(zone.switch())
            if zgroup is not None:
                groupkey = "G" + str(zgroup)
            if groupkey in groups:
                groups[groupkey].append(zone)
            else:
                groups[groupkey] = [zone]

        self.async_schedule_update_ha_state()
        return groups

    async def async_calculate_program_remaining(self,groups):
            """calculate the remaining time for the program"""
            self._program_remaining = 0
            for thisgroup in groups.values():
                group_runtime = 0
                attr_runtime = 0
                for thiszone in thisgroup:
                    attr_value = self._extra_attrs["{}{}".format(thiszone.name(),"_remaining")]
                    group_runtime = sum(x * int(t) for x, t in zip([3600, 60, 1], attr_value.split(":")))
                    if attr_runtime > group_runtime:
                        group_runtime = attr_runtime
                self._program_remaining += group_runtime
            self._extra_attrs[ATTR_REMAINING] = self.format_run_time(self._program_remaining)

    async def async_finalise_group_run(self, group, last_ran):
        """clean up group once it has run"""
        #clean up after the run
        for zone in group:
            #Update the zones last ran time
            zonelastran = self.format_attr(
                    zone.name(),
                    ATTR_LAST_RAN,
                )
            if not self._run_zone and self._state is True and last_ran is not None:
                #not manual run or aborted
                self._extra_attrs[zonelastran] = last_ran
                zone.set_last_ran(last_ran)
            #next run time
            zonenextrun = self.format_attr(
                    zone.name(),
                    ATTR_NEXT_RUN,
                )
            hour = int(self.hass.states.get(self._start_time).state.split(':')[0])
            minute = int(self.hass.states.get(self._start_time).state.split(':')[1])
            self._extra_attrs[zonenextrun] = zone.next_run(hour, minute,self.irrigation_on_value())
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
        ''' Turn on the switch'''

        if self._state is True:
            #program is still running
            return
        self._state = True
        #stop all running programs except the calling program
        if self._interlock:
            #how to determine if two programs have the same start time?
            data = {'ignore':self.name}
            await self.hass.services.async_call(DOMAIN, "stop_programs", data)
        # start pump monitoring
        loop = asyncio.get_event_loop()
        for thispump in self._pumps:
            loop.create_task(thispump.async_monitor())
        # use this to set the last ran attribute of the zones
        p_last_ran = dt_util.now()

        groups = await self.build_run_script(False)
        if len(groups)>0:
              #raise event when the program starts
              event_data = {
                             "action": "program_turned_on",
                             "device_id": self._device_id,
                             "scheduled": self.scheduled,
                             "program": self._name
              }
              self.hass.bus.async_fire("irrigation_event", event_data)

        #loop through zone_groups
        for count, group in enumerate(groups.values()):
            if self._state is False:
                #program terminated clean up
                await self.async_finalise_group_run(group,p_last_ran)
                continue
            #if this is the second group and interzone delay is defined
            if count > 0:
                #check if there is a next zone
                if count < len(groups.values()):
                    if self.inter_zone_delay() is not None:
                        await asyncio.sleep(self.inter_zone_delay())
            #start all zones in a group
            if self._state is True:
                loop = asyncio.get_event_loop()
                for gzone in group:
                    #run in parrallel
                    loop.create_task(gzone.async_turn_on(self.scheduled))
                    await asyncio.sleep(1)
                    # latency issue loop a few times to see if the switch turns on
                    # otherwise give a warning and skip this switch
                    for _ in range(CONST_LATENCY):
                        if gzone.check_switch_state() is False:
                            await asyncio.sleep(1)
                        else:
                            break
                    else:
                        _LOGGER.warning('Significant latency has been detected, unexpected behaviour may occur, %s',gzone.switch())
                        continue

                    event_data = {
                        "action": "zone_turned_on",
                        "device_id": self._device_id,
                        "scheduled": self.scheduled,
                        "zone": gzone.name(),
                        "pump": gzone.pump(),
                        "runtime": gzone.run_time(gzone.repeat_value()),
                        "water": gzone.water_value(),
                        "wait": gzone.wait_value(),
                        "repeat": gzone.repeat_value(),
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)
            #wait for the zones to complete
            zones_running = True
            while zones_running and self._state is True:
                zones_running = False
                for gzone in group:
                    if self._state is False:
                        break
                    #check each zone in the group
                    attr = self.format_attr(
                            gzone.name(),
                            ATTR_REMAINING,
                        )
                    remaining_time = self.format_run_time(
                        await gzone.remaining_time()
                    )
                    self._extra_attrs[attr] = remaining_time
                    #continue until all zones in the groups finished
                    if await gzone.state() in ["on","eco"]:
                        zones_running = True

                #calculate the remaining time for the program
                await self.async_calculate_program_remaining(groups)
                self.async_schedule_update_ha_state()
                await asyncio.sleep(1)
                if not zones_running:
                    break

            #clean up after the run
            await self.async_finalise_group_run(group,p_last_ran)

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
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        '''stop the switch/program'''
        if self._state is True:
            self._state = False
            self.scheduled = False
            self._run_zone = []
            for zone in self._irrigationzones:
                await zone.async_turn_off()