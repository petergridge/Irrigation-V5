"""Switch entity definition."""

import asyncio
from datetime import UTC, datetime, timedelta
import logging
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
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_started
from homeassistant.util import slugify

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
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REMAINING,
    ATTR_REPEAT,
    ATTR_RESET,
    ATTR_RUN_FREQ,
    ATTR_SCHEDULED,
    ATTR_START,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_WATER_SOURCE,
    ATTR_ZONE,
    ATTR_ZONES,
    CONST_ECO,
    CONST_ON,
    CONST_PENDING,
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
        async_add_entities(
            [
                IrrigationProgram(
                    hass, unique_id, config_entry.options, name, config_entry
                )
            ]
        )
    else:
        async_add_entities(
            [IrrigationProgram(hass, unique_id, config_entry.data, name, config_entry)]
        )

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
        {vol.Optional(ATTR_RESET, default=10): cv.positive_int},
        "entity_reset_runtime",
    )

    platform.async_register_entity_service(
        "run_simulation",
        {vol.Optional(ATTR_SCHEDULED, default=True): cv.boolean},
        "async_simulate_program",
    )

class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""

    _attr_has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, unique_id, config, device_id, config_entry
    ) -> None:
        """Initialize a Irrigation program."""
        self.hass = hass
        self._name = config.get(CONF_NAME, device_id)
        self._start_time = config.get(ATTR_START)
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
        self._irrigationzones = [] #list of all zones
        self._pumps = []
        self._run_zones = [] #list of zones to run
        self._running_zone = [] #list of currently running zones
        self._extra_attrs = {}
        self._program_remaining = 0
        self._unsub_point_in_time = None
        self._unsub_start = None
        self._unsub_monitor = None
        self._localtimezone = ZoneInfo(self.hass.config.time_zone)

    async def async_will_remove_from_hass(self) -> None:
        """Cancel next update."""
        if self._unsub_point_in_time:
            self._unsub_point_in_time()
            self._unsub_point_in_time = None
        if self._unsub_start:
            self._unsub_start()
            self._unsub_start = None
        #stop monitoring
        self._unsub_monitor()
        self._unsub_monitor = None

        await self.async_turn_off()

    def get_next_interval(self):
        """Next time an update should occur."""
        now = datetime.now(UTC)
        timestamp = datetime.timestamp(datetime.now())
        interval = 60
        delta = interval - (timestamp % interval)
        return now + timedelta(seconds=delta)

    def format_attr(self, part_a, part_b):
        """Format attribute names."""
        return slugify(f"{part_a}_{part_b}")

    @callback
    async def point_in_time_listener(self, time_date):
        """Get the latest time and check if irrigation should start."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )
        #HH:MM:SS string from datetime
        time = datetime.now(self._localtimezone).strftime(TIME_STR_FORMAT)
        string_times = self.start_time_value
        string_times = (
            string_times.replace(" ", "")
            .replace("\n", "")
            .replace("'", "")
            .replace('"', "")
            .strip("[]'")
            .split(",")
        )

        if (
            self._state is False
            and time in string_times
            and self.irrigation_on_value is True
            and self.monitor_controller_value is True
           ):
            self._running_zone = []
            self.scheduled = True
            loop = asyncio.get_event_loop()
            background_tasks = set()
            task = loop.create_task(self.async_turn_on())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
            _LOGGER.debug('Scheduled run executed')
        self.async_write_ha_state()

    @callback
    async def update_next_run(
        self, entity=None, old_status=None, new_status=None
    ):
        """Update the next run callback."""
        for zone in self._irrigationzones:
            await zone.next_run()
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Add listener."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval()
        )

        @callback
        async def hass_started(event):
            """HA has started."""
            last_state = await self.async_get_last_state()
            # create the zone class
            zonedict = {}
            pumps = {}
            for zone in self._zones:
                # initialise historical flow
                z_name = zone.get(ATTR_ZONE).split(".")[1]
                z_hist_flow = None
                if zone.get(ATTR_FLOW_SENSOR) is not None:
                    attr = self.format_attr(z_name, ATTR_HISTORICAL_FLOW)
                    z_hist_flow = last_state.attributes.get(attr, 1)
                # set the last ran time
                attr = self.format_attr(z_name, ATTR_LAST_RAN)
                if last_state:
                    self._last_run = last_state.attributes.get(attr, None)
                # add the zone class
                # use a set() to maintain uniqueness as this gets processed twice, when HA is started
                # and is reprocessed when a config flow is processed
                zonedict[z_name] = IrrigationZone(
                    self.hass,   #hass class object
                    self,        #program class object
                    zone,        #Zone config
                    z_hist_flow, #flow rate from the last run
                    self._last_run,
                )
            self._irrigationzones = zonedict.values()

            # set up to monitor these entities
            await self.set_up_entity_monitoring()

            # build attributes in run order
            zones = await self.build_run_script(config=True)

            for zone in zones:
                if zone.pump is not None:
                    # create pump - zone list
                    if zone.pump not in pumps:
                        pumps[zone.pump] = [zone.switch]
                    else:
                        pumps[zone.pump].append(zone.switch)

            # Build Zone Attributes to support the custom card
            await self.define_program_attributes()

            # create pump class to start/stop pumps
            for pump, zones in pumps.items():
                # pass pump_switch, list of zones, off_delay
                _LOGGER.debug("hass_started - pump class added %s", pump)
                self._pumps.append(PumpClass(self.hass, pump, zones))

            # turn off the underlying switches as a precaution
            for pump in pumps.keys():  # noqa: SIM118
                if self.hass.states.is_state(pump, "on"):
                    await self.hass.services.async_call(
                        CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: pump}
                    )

            for zone in self._irrigationzones:
                if self.hass.states.is_state(zone.switch, "on"):
                    await zone.async_turn_off()
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

            # calculate the next run
            await self.update_next_run()
            self.async_schedule_update_ha_state()

        # setup the callback to kick in when HASS has started
        # listen for config_flow change and apply the updates
        self._unsub_start = async_at_started(self.hass, hass_started)

        @callback
        async def hass_shutdown(event):
            """Make sure everything is shut down."""
            for zone in self._irrigationzones:
                await zone.async_turn_zone_off()
            self.async_schedule_update_ha_state()
            await asyncio.sleep(1)

        # setup the callback to listen for the shut down
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hass_shutdown)

        await super().async_added_to_hass()

    async def set_up_entity_monitoring(self):
        """Set up to monitor these entities to change the next run data."""
        monitor = [self._start_time]
        if self._monitor_controller:
            monitor.append(self._monitor_controller)
        if self._irrigation_on:
            monitor.append(self._irrigation_on)
        if self._run_freq:
            monitor.append(self._run_freq)
        for zone in self._irrigationzones:
            monitor.append(zone.switch)
            if zone.enable_zone:
                monitor.append(zone.enable_zone)
            if zone.run_freq:
                monitor.append(zone.run_freq)
            if zone.rain_sensor:
                monitor.append(zone.rain_sensor)
            if zone.water_source:
                monitor.append(zone.water_source)
            if zone.ignore_rain_sensor:
                monitor.append(zone.ignore_rain_sensor)
            if zone.water_adjust:
                monitor.append(zone.water_adjust)
            if zone.water:
                monitor.append(zone.water)

        self._unsub_monitor = async_track_state_change_event(
            self.hass, tuple(monitor), self.update_next_run
        )

    async def define_program_attributes(self):
        """Build attributes in run order."""
        #Program attributes
        self._extra_attrs = {}
        if self._start_time is not None:
            self._extra_attrs[ATTR_START] = self._start_time
        if self._run_freq is not None:
            self._extra_attrs[ATTR_RUN_FREQ] = self._run_freq
        if self._monitor_controller is not None:
            self._extra_attrs[ATTR_MONITOR_CONTROLLER] = self._monitor_controller
        if self._irrigation_on is not None:
            self._extra_attrs[ATTR_IRRIGATION_ON] = self._irrigation_on
        if self._inter_zone_delay is not None:
            self._extra_attrs[ATTR_DELAY] = self._inter_zone_delay
        self._extra_attrs[ATTR_REMAINING] = "%d:%02d:%02d" % (0, 0, 0)
        #zone attributes
        zones = await self.build_run_script(config=True)
        # zone loop to initialise the attributes
        for zonecount, zone in enumerate(zones,1):
            # Build Zone Attributes to support the custom card
            z_name = zone.name
            attr = self.format_attr("zone " + str(zonecount), CONF_NAME)
            self._extra_attrs[attr] = zone.name
            # set the switch type: switch or valve
            attr = self.format_attr(z_name, 'type')
            self._extra_attrs[attr] = zone.type
            # set the last ran time
            attr = self.format_attr(z_name, ATTR_LAST_RAN)
            self._extra_attrs[attr] = zone.last_ran
            # set the historical flow
            attr = self.format_attr(z_name, ATTR_HISTORICAL_FLOW)
            if zone.flow_rate:
                attr = self.format_attr(z_name, ATTR_HISTORICAL_FLOW)
                self._extra_attrs[attr] = zone.flow_rate
            # zone remaining time
            attr = self.format_attr(z_name, ATTR_REMAINING)
            self._extra_attrs[attr] = "%d:%02d:%02d" % (0, 0, 0)
            if zone.switch is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_ZONE)] = (
                    zone.switch
                )
            if zone.water is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_WATER)] = (
                    zone.water
                )
            if zone.wait is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_WAIT)] = zone.wait
            if zone.repeat is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_REPEAT)] = (
                    zone.repeat
                )
            if zone.pump is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_PUMP)] = zone.pump
            if zone.flow_sensor is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_FLOW_SENSOR)] = (
                    zone.flow_sensor
                )
            if zone.water_adjust is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_WATER_ADJUST)] = (
                    zone.water_adjust
                )
            if zone.water_source is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_WATER_SOURCE)] = (
                    zone.water_source
                )
            if zone.run_freq is not None and self._run_freq != zone.run_freq:
                self._extra_attrs[self.format_attr(z_name, ATTR_RUN_FREQ)] = (
                    zone.run_freq
                )
            if zone.rain_sensor is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_RAIN_SENSOR)] = (
                    zone.rain_sensor
                )
            if zone.ignore_rain_sensor is not None:
                self._extra_attrs[
                    self.format_attr(z_name, ATTR_IGNORE_RAIN_SENSOR)
                ] = zone.ignore_rain_sensor
            if zone.enable_zone is not None:
                self._extra_attrs[self.format_attr(z_name, ATTR_ENABLE_ZONE)] = (
                    zone.enable_zone
                )
        self._extra_attrs["zone_count"] = len(zones)


    async def entity_run_zone(self, zone) -> None:
        """Run a specific zone."""
        for stopzone in self._irrigationzones:
            await stopzone.async_turn_zone_off()
        self.async_schedule_update_ha_state()
        self._running_zone = zone
        self.scheduled = False
        background_tasks = set()
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.async_turn_on())
        task.add_done_callback(background_tasks.discard)
        background_tasks.add(task)

    async def entity_toggle_zone(self, zone) -> None:
        """Toggle a specific zone."""
        #built to handle a list but only one
        checkzone = None
        togglezone = zone[0]

        for czone in self._irrigationzones:
            if czone.switch == togglezone:
                checkzone = czone
                break
        if self._run_zones == []:
            self._running_zone = zone
            self.scheduled = False
            background_tasks = set()
            loop = asyncio.get_event_loop()
            task = loop.create_task(self.async_turn_on())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
        elif self._run_zones.count(checkzone) == 0:
            #add the zone to the list to run
                self._run_zones.append(checkzone)
                await checkzone.prepare_to_run(scheduled=False)
        else:
            # zone is running/queued turn it off
            await checkzone.async_turn_zone_off()
            if self._run_zones.count(checkzone) > 0:
                self._run_zones.remove(checkzone)

        self.async_schedule_update_ha_state()

    async def async_simulate_program(self, scheduled) -> None:
        """Execute a simulation tests."""
        _LOGGER.warning("Irrigation Program: %s:", self._name)
        runscript = await self.build_run_script(config=True)
        if len(runscript) == 0:
            _LOGGER.warning("No zones to run based on current configuration")
        for zone in runscript.values():
            text = "Zone to run: " + zone.name
            _LOGGER.warning(text)
        # list all zone details
        for testzone in self._irrigationzones:
            await testzone.async_test_zone(scheduled)

    async def entity_reset_runtime(self, reset=10) -> None:
        """Reset last runtime to support testing."""
        for zone in self._irrigationzones:
            last_ran = datetime.now(self._localtimezone) - timedelta(days=reset)
            await zone.set_last_ran(last_ran)
            # update the attributes
            attr = self.format_attr(
                zone.name,
                ATTR_LAST_RAN,
            )
            self._extra_attrs[attr] = last_ran
        self.async_schedule_update_ha_state()
        await self.update_next_run()

    @property
    def inter_zone_delay(self):
        """Return interzone delay value."""
        if isinstance(self._inter_zone_delay, str):
            # supports config version 1
            return int(float(self.hass.states.get(self._inter_zone_delay).state))
        return 0

    @property
    def device_type(self):
        """Return the name of the variable."""
        return self._device_type

    @property
    def name(self):
        """Return the name of the variable."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def set_extra_state_attributes(self,attr):
        """Return the state attributes."""
        self._extra_attrs = attr

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_attrs

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def irrigation_on_value(self):
        """Zone  entity value."""
        value = True
        if self._irrigation_on is not None:
            if self.hass.states.get(self._irrigation_on).state == "off":
                value = False
        return value

    @property
    def monitor_controller_value(self):
        """Zone  entity value."""
        value = True
        if self._monitor_controller is not None:
            if self.hass.states.get(self._monitor_controller).state == "off":
                value = False
        return value
    @property
    def run_freq(self):
        """Run Frequncy."""
        return self._run_freq
    @property
    def run_freq_value(self):
        """Run Frequncy."""
        value = None
        if self._run_freq is not None:
            value = self.hass.states.get(self._run_freq).state
        return value
    @property
    def start_time(self):
        """Start time entity."""
        return self._start_time
    @property
    def start_time_value(self):
        """Start time entity value."""
        value = None
        if self._start_time is not None:
            value = self.hass.states.get(self._start_time).state
        return value

    def format_run_time(self, runtime):
        """Format the runtime for attributes."""
        hourmin = divmod(runtime, 3600)
        minsec = divmod(hourmin[1], 60)
        return "%d:%02d:%02d" % (hourmin[0], minsec[0], minsec[1])

    async def set_zone_run_time_attr(self,zone_name,runtime):
        """Set the runtime attributes for zones that will run."""
        zoneremaining = self.format_attr(zone_name, ATTR_REMAINING)
        fruntime = self.format_run_time(
            runtime
        )
        self._extra_attrs[zoneremaining] = fruntime
        self.async_schedule_update_ha_state()

    async def set_sensor_status(self, state, program, zone):
        """Set the runtime on the relevant sensor."""
        device = f"sensor.{slugify(program)}_{slugify(zone)}_status"
        servicedata = {ATTR_ENTITY_ID: device, "status": state}
        await self.hass.services.async_call(DOMAIN, "set_zone_status", servicedata)

    async def build_run_script(self, config=False):
        """Build the run script based on each zones data."""
        zones = []
        for zone in self._irrigationzones:
            if not config:
                # config only used when setting up program or running simmulation
                if self._running_zone:
                    # Zone has been manually run from service call
                    if zone.switch not in self._running_zone:
                        continue
                # auto_run where program started based on start time
                if await zone.should_run(self.scheduled) is False:
                    # calculate the next run
                    continue

                await zone.prepare_to_run(scheduled=self.scheduled)
            zones.append(zone)
        return zones

    async def calculate_program_remaining(self, zones):
        """Calculate the remaining time for the program."""
        self._program_remaining = 0
        for program_postion, zone in enumerate(zones,1):
            if zone.state in  (CONST_ON, CONST_PENDING, CONST_ECO):
                self._program_remaining += zone.remaining_time
                if program_postion < len(zones):
                    self._program_remaining += self.inter_zone_delay
        #update the attribute
        self._extra_attrs[ATTR_REMAINING] = self.format_run_time(
            self._program_remaining
        )
        self.async_schedule_update_ha_state()
        return self._program_remaining

    async def async_finalise_run(self, zone, last_ran):
        """Clean up once it has run."""
        # clean up after the run
        zonelastran = self.format_attr(
            zone.name,
            ATTR_LAST_RAN,
        )

        if not self._running_zone and self._state is True and last_ran is not None:
            # not manual run or aborted
            self._extra_attrs[zonelastran] = last_ran
            await zone.set_last_ran(last_ran)
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_finalise_run - finalise run - last_ran %s", last_ran)

        # update the historical flow rate, better information for next run
        if zone.flow_sensor:
            # record the flow rate from this run
            attr = self.format_attr(
                zone.name,
                ATTR_HISTORICAL_FLOW,
            )
            self._extra_attrs[attr] = zone.flow_rate

    async def run_monitor_zones(self, running_zones, zones):
        """Monitor zones to start based on inter zone delay."""
        if running_zones == []:
            # #start first zone
            for zone in zones:
                running_zones.append(zone)
                await self.zone_turn_on(zone)
                break
        await self.calculate_program_remaining(zones)

        #monitor the running zones
        rzones = running_zones
        for running_zone in rzones:
            if self.inter_zone_delay <= 0 and running_zone.remaining_time <= abs(self.inter_zone_delay):
                #zone has turned off remove from the running zones
                running_zones.remove(running_zone)
                if self._run_zones.count(running_zone) > 0:
                    self._run_zones.remove(running_zone)
                #start the next zone if there is one
                for zone in zones:
                    if zone.state in (CONST_PENDING):
                        #start the next zone
                        await self.zone_turn_on(zone)
                        running_zones.append(zone)
                        break

            if self.inter_zone_delay > 0 and running_zone.remaining_time == 0:
                #there is a + IZD and there is a zone to follow
                for zone in zones:
                    if zone.state in (CONST_PENDING):
                        #start the next zone
                        await asyncio.sleep(self.inter_zone_delay)
                        await self.zone_turn_on(zone)
                        running_zones.append(zone)
                        break

            if running_zone.remaining_time == 0:
                if running_zones.count(running_zone) > 0:
                    running_zones.remove(running_zone)
                if self._run_zones.count(running_zone) > 0:
                    self._run_zones.remove(running_zone)

        self.async_schedule_update_ha_state()
        await asyncio.sleep(1)
        return running_zones

    async def zone_turn_on(self,zone):
        """Turn on the irrigation zone."""
        #in an independant task so the main prog continues to run
        background_tasks = set()
        loop = asyncio.get_event_loop()
        task = loop.create_task(zone.async_turn_on_cycle(self.scheduled))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

        event_data = {
            "action": "zone_turned_on",
            "device_id": self._device_id,
            "scheduled": self.scheduled,
            "zone": zone.name,
            "pump": zone.pump,
            "runtime": await zone.run_time(),
            "water": zone.water_value,
            "wait": zone.wait_value,
            "repeat": zone.repeat_value,
            }
        self.hass.bus.async_fire("irrigation_event", event_data)
        return True

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        # use time at start to set the last ran attribute of the zones
        # all zones will have the last ran of the program start
        p_last_ran = datetime.now(self._localtimezone)
        self._run_zones = await self.build_run_script(config=False)
        #take a copy to finalise with
        scheduled_zones = self._run_zones.copy()

        if self._state is True:
            # program is still running
            for zone in self._run_zones:
                await self.async_finalise_run(zone, p_last_ran)
            return
        # stop all running programs except the calling program
        if self._interlock:
            # how to determine if two programs have the same start time?
            data = {"ignore": self.name}
            await self.hass.services.async_call(DOMAIN, "stop_programs", data)

        if len(self._run_zones) > 0:
            # raise event when the program starts
            event_data = {
                "action": "program_turned_on",
                "device_id": self._device_id,
                "scheduled": self.scheduled,
                "program": self._name,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)
        else:
            # No zones to run
            _LOGGER.debug("async_turn_on - No zones to run")
            return
        self._state = True

        # start pump monitoring
        loop = asyncio.get_event_loop()
        background_tasks = set()
        for thispump in self._pumps:
            task = loop.create_task(thispump.async_monitor())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        # now start the program
        # calculate the remaining time for the program
        await self.calculate_program_remaining(self._run_zones)
        self.async_schedule_update_ha_state()
        await asyncio.sleep(1)
        # Monitor and start the zone with lead/lag time
        running_zones = []
        running_zones = await self.run_monitor_zones(running_zones, self._run_zones)
        while self._program_remaining > 0:
            running_zones = await self.run_monitor_zones(running_zones, self._run_zones)
            self.async_schedule_update_ha_state()
        # clean up after the run
        for zone in scheduled_zones:
            await self.async_finalise_run(zone, p_last_ran)
        self.async_schedule_update_ha_state()

        # run is complete stop pump monitoring
        background_tasks = set()
        for pump in self._pumps:
            task = loop.create_task(pump.async_stop_monitoring())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        event_data = {
            "action": "program_turned_off",
            "device_id": self._device_id,
            "completed": self._state,  # False = terminated
            "program": self._name,
        }
        self.hass.bus.async_fire("irrigation_event", event_data)
        self._state = False
        self.scheduled = False
        self._running_zone = []
        self._run_zones = []
        self.async_schedule_update_ha_state()
        # program finished

    async def async_turn_off(self, **kwargs):
        """Stop the switch/program."""
        if self._state is True:
            self._state = False
            self.scheduled = False
            self._running_zone = []
            self._run_zones = []
            for zone in self._irrigationzones:
                await zone.async_turn_zone_off()
        self.async_schedule_update_ha_state()
