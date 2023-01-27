''' Switch entity definition'''

import asyncio
#from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_SWITCHES,
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    ATTR_DELAY,
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_IRRIGATION_ON,
    ATTR_LAST_RAN,
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
    )

from .irrigationzone import IrrigationZone
from .pump import PumpClass

SWITCH_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_RUN_FREQ): cv.entity_domain("input_select"),
            vol.Optional(ATTR_MONITOR_CONTROLLER): cv.entity_domain(
                ["binary_sensor", "input_boolean"]
            ),
            vol.Required(ATTR_START): cv.entity_domain("input_datetime"),
            vol.Optional(ATTR_IRRIGATION_ON): cv.entity_domain("input_boolean"),
            vol.Optional(ATTR_SHOW_CONFIG): cv.entity_domain("input_boolean"),
            vol.Optional(ATTR_DELAY): cv.entity_domain("input_number"),
            vol.Optional('icon'): cv.icon,
            vol.Optional('name'): cv.string,
            vol.Required(ATTR_ZONES): [
                {
                    vol.Required(ATTR_ZONE): cv.entity_domain(CONST_SWITCH),
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(ATTR_PUMP): cv.entity_domain(CONST_SWITCH),
                    vol.Optional(ATTR_FLOW_SENSOR): cv.entity_domain(
                        ["input_number", "sensor"]
                    ),
                    vol.Optional(ATTR_WATER_ADJUST): cv.entity_domain(
                        ["input_number", "sensor"]
                    ),
                    vol.Optional(ATTR_RUN_FREQ): cv.entity_domain("input_select"),
                    vol.Optional(ATTR_RAIN_SENSOR): cv.entity_domain("binary_sensor"),
                    vol.Optional(ATTR_ZONE_GROUP): cv.entity_domain("input_text"),
                    vol.Required(ATTR_WATER): cv.entity_domain("input_number"),
                    vol.Optional(ATTR_WAIT): cv.entity_domain("input_number"),
                    vol.Optional(ATTR_REPEAT): cv.entity_domain("input_number"),
                    vol.Optional(ATTR_IGNORE_RAIN_SENSOR): cv.entity_domain("input_boolean"),
                    vol.Optional(ATTR_ENABLE_ZONE): cv.entity_domain("input_boolean"),
                    vol.Optional('icon'): cv.icon,
                }
            ],
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

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
        "reset_runtime",
        {

        },
        "entity_reset_runtime",
    )

    platform.async_register_entity_service(
        "run_simulation",
        {

        },
        "async_simulate_program",
    )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the irrigation switches from yaml required until YAML deprecated"""

class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""
    _attr_has_entity_name = True
    def __init__(
        self, hass, unique_id, config, device_id, config_entry
    ):
        #--------------------------
        #
        self.config_entry = config_entry

        """Initialize a Irrigation program."""
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

        self._device_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._attr_unique_id = unique_id
        self._state = False
        self._last_run = None
        self._template = None
        self._irrigationzones = []
        self._pumps = []
        self._run_zone = []
        self._extra_attrs = {}
        self._unsub_track_change = None
        self._program_remaining = 0

        # Validate and Build a template from the attributes provided
        template = "states('sensor.time')" + " + ':00' == states('" + self._start_time + "') "
        if self._irrigation_on is not None:
            template = template + " and is_state('" + self._irrigation_on + "', 'on') "
        if self._monitor_controller is not None:
            template = (
                template + " and is_state('" + self._monitor_controller + "', 'on') "
            )
        template = "{{ " + template + " }}"
        template = cv.template(template)
        template.hass = hass
        self._template = template

        @callback
        def _update_state(self, result):
            super()._update_state(result)

    async def async_will_remove_from_hass(self):
        #tidy up when reloading config
        self._unsub_track_change()
        await self.async_turn_off()

    def format_attr(self, part_a, part_b):
        """Helper to format attribute names"""
        return slugify("{}_{}".format(part_a, part_b))

    async def async_added_to_hass(self):
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
        if self._show_config is not None:
            self._extra_attrs[ATTR_SHOW_CONFIG] = self._show_config
        if self._inter_zone_delay is not None:
            self._extra_attrs[ATTR_DELAY] = self._inter_zone_delay

        #create the zone class
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
            self._irrigationzones.append(
                IrrigationZone(
                    self.hass,
                    zone,
                    zone.get(ATTR_RUN_FREQ, self._run_freq),
                    z_hist_flow,
                    self._last_run,
                )
            )

        # build attributes in run order
        groups = self.build_run_script(True)

        # zone loop to initialise the attributes
        zonecount = 0
        pumps = {}

        for group in groups.values():
            z_group = []
            if len(group) > 1:
                #build the group attr
                for zone in group:
                    z_group.append(zone.switch())
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
                #initialise remaining time
                attr = self.format_attr(z_name, ATTR_REMAINING)
                self._extra_attrs[attr] = "%d:%02d:%02d" % (0, 0, 0)
                # setup zone attributes to populate the Custom card
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
                if zone.run_freq() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_RUN_FREQ)] = zone.run_freq()
                if zone.rain_sensor() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_RAIN_SENSOR)] = zone.rain_sensor()
                if zone.zone_group() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_ZONE_GROUP)] = zone.zone_group()
                if zone.ignore_rain_sensor() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_IGNORE_RAIN_SENSOR)] = zone.ignore_rain_sensor()
                if zone.enable_zone() is not None:
                    self._extra_attrs[self.format_attr(z_name,ATTR_ENABLE_ZONE)] = zone.enable_zone()

        self._extra_attrs["zone_count"] = zonecount
        # create pump class to start/stop pumps
        for pump, zones in pumps.items():
            #pass pump_switch, list of zones, off_delay
            self._pumps.append(PumpClass(self.hass, pump, zones, 2))

        @callback
        async def template_check(entity, old_state, new_state):
            self.async_schedule_update_ha_state(True)
        #subscribe the template checking
        self._unsub_track_change = async_track_state_change(self.hass, "sensor.time", template_check)

        @callback
        async def hass_startup(event):
            '''Triggered when HASS has fully started only required on a hard restart'''


#-------------Upgrade config flow schema--------------------------
            #typically this is undertaken in the __init__ but I needed to
            #process the groups after HA has started and entities are available.
            new={}
            new.update(self._config)
            if self.config_entry.version == 1:
                #creat group dictionary as per VERSION 2
                zone_groups = {}
                for zone in new[ATTR_ZONES]:
                    if zone.get(ATTR_ZONE_GROUP):
                        zone_group_value = self.hass.states.get(zone.get(ATTR_ZONE_GROUP)).state
                        #now check if the group existing in the dictionary
                        if zone_groups.get(zone_group_value):
                            #append the zone switch to the switches
                            zone_groups[zone_group_value].append(zone.get('zone'))
                        else:
                            zone_groups[zone_group_value] = [zone.get('zone')]

                groups = []
                for group in zone_groups.values():
                    #create the groups entry on the config
                    zones = {}
                    zones["zones"] = group
                    name = ""
                    for switch in group:
                        name += self.hass.states.get(switch).attributes.get('friendly_name') + chr(10)
                    zones["name"] = name.strip().replace(chr(10),', ')
                    groups.append(zones)
                new.update({"groups" : groups})

                new.update({'interlock': True})

                for zonecount, zone in enumerate(new[ATTR_ZONES]):
                    if ATTR_ZONE_GROUP in zone:
                        #delete old grouping method
                        new[ATTR_ZONES][zonecount].pop(ATTR_ZONE_GROUP)

                #clean up from previous alpha
                if new.get('inter_zone_delay'):
                    new.pop('inter_zone_delay')

                self.config_entry.version = 2
                self.hass.config_entries.async_update_entry(self.config_entry, data=new)
                _LOGGER.info('Irrigation program upgraded to schema version %s',self.config_entry.version)

#---------------------------------------

            #turn off the underlying switches as a precaution
            for zone in self._irrigationzones:
                if self.hass.states.is_state(zone.switch(), "on"):
                    await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: zone.switch()}
                    )
            # Validate the referenced objects now that HASS has started
            # incase an object has been removed
            if self.hass.states.async_available("sensor.time"):
                _LOGGER.error(
                    "Sensor.time not defined check your configuration"
                )
            if self._monitor_controller is not None:
                if self.hass.states.async_available(self._monitor_controller):
                    _LOGGER.warning(
                        "%s not found, check your configuration",
                        self._monitor_controller,
                    )
            if self._run_freq is not None:
                if self.hass.states.async_available(self._run_freq):
                    _LOGGER.warning(
                        "%s not found, check your configuration", self._run_freq
                    )
            # run validation over the zones
            for zone in self._irrigationzones:
                zone.validate()

        #setup the callback
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, hass_startup
        )

        @callback
        async def hass_shutdown(event):
            #make sure everything is shut down
            for zone in self._irrigationzones:
                await zone.async_turn_off()
            await asyncio.sleep(1)
        #setup the callback
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
        loop = asyncio.get_event_loop()
        loop.create_task(self.async_turn_on())
        await asyncio.sleep(1)

    async def async_simulate_program(self) -> None:
        '''execute a simulation tests'''
        _LOGGER.error("")
        _LOGGER.error("Irrigation Program: %s:",self._name)
        if len(self.build_run_script(False).values()) == 0:
            _LOGGER.error("No zones to run based on current configuration")
        for group in self.build_run_script(False).values():
            if len(self.build_run_script(False).values()) > 0:
                text = "Grouped zones to run: "
            else:
                text = "Zone to run: "
            for zone in group:
                text += zone.name() + " "
            _LOGGER.error(text)
        #list all zone details
        for testzone in self._irrigationzones:
            await testzone.async_test_zone()
        #clean up after the simulation
        for group in self.build_run_script(False).values():
            await self.async_finalise_group_run(group, None)

    async def entity_reset_runtime(self) -> None:
        '''reset last runtime to support testing'''
        for zone in self._irrigationzones:
            zone.set_last_ran(None)

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
        #replaced with self.async_schedule_update_ha_state()
        return False

    async def async_update(self):
        '''monitor to turn on the irrigation based on the input parameters'''
        # fired by self.async_schedule_update_ha_state()
        if self._state is False:
            if self._template.async_render():
                self._run_zone = []
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())
        self.async_write_ha_state()

    def format_run_time(self, runtime):
        """Format the runtime for attributes"""
        hourmin = divmod(runtime, 3600)
        minsec = divmod(hourmin[1], 60)
        return "%d:%02d:%02d" % (hourmin[0], minsec[0], minsec[1])

    def build_run_script(self, allzones):
        """Build the run script based on each zones data"""

        def check_group_config(pzone):
        # has the zone been configured in a group
            if self._groups is not None:
                for count, group in enumerate(self._groups):
                    if pzone in group[ATTR_ZONES]:
                        return count

        #build run list for this execution
        groups = {}
        for zonecount, zone in enumerate(self._irrigationzones):
            if not allzones:
                if self._run_zone:
                # Zone has been manually run from service call
                    if zone.switch() not in self._run_zone:
                        continue
                else:
                    if not zone.should_run():
                        continue

                # set the runtime attributes for zones that will run
                zoneremaining = self.format_attr(zone.name(), ATTR_REMAINING)
                self._extra_attrs[zoneremaining] = self.format_run_time(
                    zone.run_time(repeats=zone.repeat_value())
                )

            #build zone groupings that will run concurrently
            #--- new config flow version 2 group functionality
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
            #---- end new zone group
        # Config Version 1 will run in parallel until depricated
            if not groups:
                #No config version 2 groups build on version 1 rules
                groupkey = zonecount
                if zone.zone_group_value() is not None:
                    zone_group = zone.zone_group_value()
                    if zone_group:
                        groupkey = "G" + zone_group
                if groupkey in groups:
                    groups[groupkey].append(zone)
                else:
                    groups[groupkey] = [zone]
        #--- end to be depricated

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

        groups = self.build_run_script(False)

        #loop through zone_groups
        for count, group in enumerate(groups.values()):
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
                    loop.create_task(gzone.async_turn_on())
                    event_data = {
                        "device_id": self._device_id,
                        "action": "zone_turned_on",
                        "zone": gzone.name(),
                        "pump": gzone.pump(),
                        "runtime": gzone.run_time(gzone.repeat_value()),
                        "water": gzone.water_value(),
                        "wait": gzone.wait_value(),
                        "repeat": gzone.repeat_value(),
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)
                await asyncio.sleep(1)

            #wait for the zones to complete
            zones_running = True
            while zones_running and self._state is True:
                zones_running = False
                for gzone in group:
                    #check each zone in the group
                    attr = self.format_attr(
                            gzone.name(),
                            ATTR_REMAINING,
                        )
                    self._extra_attrs[attr] = self.format_run_time(
                        gzone.remaining_time()
                    )
                    #continue until all zones in the groups finished
                    if gzone.state() in ["on","eco"]:
                        zones_running = True

                if not zones_running:
                    break

                #calculate the remaining time for the program
                await self.async_calculate_program_remaining(groups)

                self.async_schedule_update_ha_state()
                await asyncio.sleep(1)

            #clean up after the run
            await self.async_finalise_group_run(group,p_last_ran)
            self.async_schedule_update_ha_state()

        #run is complete stop pump monitoring
        for pump in self._pumps:
            loop.create_task(pump.async_stop_monitoring())

        self._state = False
        self._run_zone = []

        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        '''stop the switch/program'''
        if self._state is True:
            for zone in self._irrigationzones:
                await zone.async_turn_off()
            self._state = False
            self._run_zone = []
