''' Switch entity definition'''

import asyncio
from datetime import timedelta
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
    ATTR_ENTITY_ID,
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
        async_add_entities([IrrigationProgram(hass, unique_id, config_entry.options, name)])
    else:
        async_add_entities([IrrigationProgram(hass, unique_id, config_entry.data, name)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "run_zone",
        {
            vol.Required(ATTR_ZONE): cv.string,
        },
        "entity_run_zone",
    )

    platform.async_register_entity_service(
        "reset_runtime",
        {

        },
        "entity_reset_runtime",
    )

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the irrigation switches from yaml required until YAML deprecated"""

class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""
    _attr_has_entity_name = True
    def __init__(
        self, hass, unique_id, config, device_id
    ):

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

        self._device_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._attr_unique_id = unique_id
        self._state = False
        self._last_run = None
        self._template = None
        self._irrigationzones = []
        self._pumps = []
        self._run_zone = None
        self._attrs = {}
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

    def format_attr(self, a, b):
        """Helper to format attribute names"""
        return slugify("{}_{}".format(a, b))

    async def async_added_to_hass(self):
        state = await self.async_get_last_state()
        self._last_run = None
        self._attrs = {}
        if self._start_time is not None:
            self._attrs[ATTR_START] = self._start_time
        if self._run_freq is not None:
            self._attrs[ATTR_RUN_FREQ] = self._run_freq
        if self._monitor_controller is not None:
            self._attrs[ATTR_MONITOR_CONTROLLER] = self._monitor_controller
        if self._irrigation_on is not None:
            self._attrs[ATTR_IRRIGATION_ON] = self._irrigation_on
        if self._show_config is not None:
            self._attrs[ATTR_SHOW_CONFIG] = self._show_config
        if self._inter_zone_delay is not None:
            self._attrs[ATTR_DELAY] = self._inter_zone_delay
        # zone loop to set the attributes
        zonecount = 0
        pumps = {}
        for zone in self._zones:
            zonecount += 1
            if zone.get(ATTR_PUMP) is not None:
                #create pump - zone list
                if zone.get(ATTR_PUMP) not in pumps:
                    pumps[zone.get(ATTR_PUMP)] = [zone.get(ATTR_ZONE)]
                else:
                    pumps[zone.get(ATTR_PUMP)].append(zone.get(ATTR_ZONE))
            # Build Zone Attributes to support the custom card
            z_name = zone.get(ATTR_ZONE).split(".")[1]
            attr = self.format_attr("zone" + str(zonecount), CONF_NAME)
            self._attrs[attr] = z_name
            # set the last ran time
            attr = self.format_attr(z_name, ATTR_LAST_RAN)
            z_last_ran = None
            if state is not None:
                z_last_ran = state.attributes.get(attr,dt_util.now() - timedelta(days=10))
            self._attrs[attr] = z_last_ran
            attr = self.format_attr(z_name, ATTR_REMAINING)
            self._attrs[attr] = "%d:%02d:%02d" % (0, 0, 0)
            z_hist_flow = None
            if zone.get(ATTR_FLOW_SENSOR) is not None:
                attr = self.format_attr(z_name, "historical_flow")
                if state is not None:
                    z_hist_flow = state.attributes.get(attr)
                if z_hist_flow is None:
                    z_hist_flow = 1
            # setup attributes to populate the Custom card
            if zone.get(ATTR_ZONE) is not None:
                self._attrs[self.format_attr(z_name,ATTR_ZONE)] = zone.get(ATTR_ZONE)
            if zone.get(ATTR_WATER) is not None:
                self._attrs[self.format_attr(z_name,ATTR_WATER)] = zone.get(ATTR_WATER)
            if zone.get(ATTR_WAIT) is not None:
                self._attrs[self.format_attr(z_name,ATTR_WAIT)] = zone.get(ATTR_WAIT)
            if zone.get(ATTR_REPEAT) is not None:
                self._attrs[self.format_attr(z_name,ATTR_REPEAT)] = zone.get(ATTR_REPEAT)
            if zone.get(ATTR_PUMP) is not None:
                self._attrs[self.format_attr(z_name,ATTR_PUMP)] = zone.get(ATTR_PUMP)
            if zone.get(ATTR_FLOW_SENSOR) is not None:
                self._attrs[self.format_attr(z_name,ATTR_FLOW_SENSOR)] = zone.get(ATTR_FLOW_SENSOR)
            if zone.get(ATTR_WATER_ADJUST) is not None:
                self._attrs[self.format_attr(z_name,ATTR_WATER_ADJUST)] = zone.get(ATTR_WATER_ADJUST)
            if zone.get(ATTR_RUN_FREQ) is not None:
                self._attrs[self.format_attr(z_name,ATTR_RUN_FREQ)] = zone.get(ATTR_RUN_FREQ)
            if zone.get(ATTR_RAIN_SENSOR) is not None:
                self._attrs[self.format_attr(z_name,ATTR_RAIN_SENSOR)] = zone.get(ATTR_RAIN_SENSOR)
            if zone.get(ATTR_ZONE_GROUP) is not None:
                self._attrs[self.format_attr(z_name,ATTR_ZONE_GROUP)] = zone.get(ATTR_ZONE_GROUP)
            if zone.get(ATTR_IGNORE_RAIN_SENSOR) is not None:
                self._attrs[self.format_attr(z_name,ATTR_IGNORE_RAIN_SENSOR)] = zone.get(ATTR_IGNORE_RAIN_SENSOR)
            if zone.get(ATTR_ENABLE_ZONE) is not None:
                self._attrs[self.format_attr(z_name,ATTR_ENABLE_ZONE)] = zone.get(ATTR_ENABLE_ZONE)
            #add the zone class
            self._irrigationzones.append(
                IrrigationZone(
                    self.hass,
                    zone,
                    zone.get(ATTR_RUN_FREQ, self._run_freq),
                    z_hist_flow,
                    z_last_ran,
                )
            )
        self._attrs["zone_count"] = zonecount

        # create pump class to start/stop pumps
        for pump, zones in pumps.items():
            self._pumps.append(PumpClass(self.hass, pump, zones))

        @callback
        async def template_check(entity, old_state, new_state):
            self.async_schedule_update_ha_state(True)
        #Upcheck the date template
        self._unsub_track_change = async_track_state_change(self.hass, "sensor.time", template_check)

        @callback
        async def hass_startup(event):
            '''Triggered when HASS has fully started only required on a hard restart'''
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

    async def entity_run_zone(self, zone: str) -> None:
        '''Run a specific zone is to run'''
        for stopzone in self._irrigationzones:
            await stopzone.async_turn_off()
        await asyncio.sleep(1)
        self._run_zone = zone
        loop = asyncio.get_event_loop()
        loop.create_task(self.async_turn_on())

    async def entity_reset_runtime(self) -> None:
        '''Run a specific zone is to run'''
        for zone in self._irrigationzones:
            zone.set_last_ran(None)

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
        return self._attrs

    @property
    def should_poll(self):
        """If entity should be polled."""
        #replaced with self.async_schedule_update_ha_state()
        return False

    async def async_update(self):
        '''monitor to turn on the irrigation based on the input parameters'''
        if self._state is False:
            if self._template.async_render():
                self._run_zone = None
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        ''' Turn on the switch'''

        self._state = True
        #stop all running programs except the calling program
        data = {'ignore':self.name}
        await self.hass.services.async_call(DOMAIN, "stop_programs", data)

        def format_run_time(runtime):
            hourmin = divmod(runtime, 3600)
            minsec = divmod(hourmin[1], 60)
            return "%d:%02d:%02d" % (hourmin[0], minsec[0], minsec[1])

        def delay_required(groups, runninggroup):
            delay_required = False
            findnext = False
            for group in groups:
                if group == runninggroup:
                    findnext = True
                    continue
                if findnext is True:
                    delay_required = True
                    break
            return delay_required

        # start pump monitoring
        loop = asyncio.get_event_loop()
        for thispump in self._pumps:
            loop.create_task(thispump.async_monitor())

        # use this to set the last ran attribute of the zones
        p_last_ran = dt_util.now()

        groups = {}
        for zonecount, zone in enumerate(self._irrigationzones):
            # determine if the zone has been manually run
            if self._run_zone:
                if zone.switch() != self._run_zone:
                    continue
            #should the zone run? rain, frequency ...
            if zone.enable_zone_value() is False:
                continue
            if not self._run_zone:
                if zone.is_raining():
                    continue
                if zone.should_run() is False:
                    continue
            #build zone groupings that will run concurrently
            groupkey = zonecount
            if zone.zone_group_value() is not None:
                zone_group = zone.zone_group_value()
                if zone_group:
                    groupkey = "G" + zone_group
            if groupkey in groups:
                groups[groupkey].append(zone)
            else:
                groups[groupkey] = [zone]

            zoneremaining = self.format_attr(zone.name(), ATTR_REMAINING)
            self._attrs[zoneremaining] = format_run_time(
                zone.run_time()
            )

        self.async_schedule_update_ha_state()

        #loop through zone_groups
        first_group = True
        for group in groups.values():
            #if this is the second set trigger interzone delay if defined
            if self._state is True:
                if not first_group and self._inter_zone_delay is not None:
                    izd = int(
                        float(
                            self.hass.states.get(
                                self._inter_zone_delay
                            ).state
                        )
                    )
                    #check if there is a next zone
                    if delay_required(groups, group):
                        if izd > 0:
                            await asyncio.sleep(izd)
            first_group = False
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
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)
                await asyncio.sleep(1)

            #wait for the zones to complete
            zns_running = True
            while zns_running and self._state is True:
                zns_running = False
                for gzone in group:
                    attr = self.format_attr(
                            gzone.name(),
                            ATTR_REMAINING,
                        )
                    self._attrs[attr] = format_run_time(
                        gzone.remaining_time()
                    )
                    #continue running until all zones have completed
                    if gzone.state() == "on":
                        zns_running = True

                #calculate the remaining time for the program
                self._program_remaining = 0
                for tgroup in groups.values():
                    group_runtime = 0
                    attr_runtime = 0
                    for tzone in tgroup:
                        attr_value = self._attrs["{}{}".format(tzone.name(),"_remaining")]
                        group_runtime = sum(x * int(t) for x, t in zip([3600, 60, 1], attr_value.split(":")))
                        if attr_runtime > group_runtime:
                            group_runtime = attr_runtime
                    self._program_remaining += group_runtime
                self._attrs["remaining"] = format_run_time(self._program_remaining)
                self.async_schedule_update_ha_state()
                await asyncio.sleep(1)

            #clean up after the run
            for gzone in group:
                #Update the zones last ran time
                zonelastran = self.format_attr(
                        gzone.name(),
                        ATTR_LAST_RAN,
                    )
                if not self._run_zone and self._state is True:
                    self._attrs[zonelastran] = p_last_ran
                    gzone.set_last_ran(p_last_ran)
                # update the historical flow rate
                if gzone.flow_sensor():
                    attr = self.format_attr(
                            gzone.name(),
                            "historical_flow",
                        )
                    self._attrs[attr] = gzone.hist_flow_rate()
                #reset the time remaining to 0
                attr = self.format_attr(
                        gzone.name(),
                        ATTR_REMAINING,
                    )
                self._attrs[attr] = "%d:%02d:%02d" % (0, 0, 0)
            self._attrs["remaining_runtime"] = "%d:%02d:%02d" % (0, 0, 0)

        #stop pump monitoring
        for pump in self._pumps:
            loop.create_task(pump.async_stop_monitoring())

        self._state = False
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        '''stop the switch'''

        for zone in self._irrigationzones:
            await zone.async_turn_off()
        self._state = False
