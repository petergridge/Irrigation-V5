"""Switch entity definition."""

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_started
from homeassistant.util import slugify

from . import (
    IrrigationData,
    IrrigationProgram as ProgramData,
    IrrigationZoneData as ZoneData,
    async_stop_programs,
)
from .const import (
    ATTR_DELAY,
    ATTR_IRRIGATION_ON,
    ATTR_PAUSE,
    ATTR_REMAINING,
    ATTR_RUN_FREQ,
    ATTR_SHOW_CONFIG,
    ATTR_START,
    CONST_ECO,
    CONST_ON,
    CONST_PENDING,
    TIME_STR_FORMAT,
)
from .pump import PumpClass

_LOGGER = logging.getLogger(__name__)


class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""

    _attr_has_entity_name = True
    _attr_attribution = "Irrigation Program"
    _unrecorded_attributes = frozenset({MATCH_ALL})
    _attr_translation_key = 'program'
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, unique_id, device_id, runtime_data:IrrigationData
    ) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = unique_id
        self._hass = hass

        self._name = runtime_data.program.name
        self._program:ProgramData = runtime_data.program
        self._zones:list[ZoneData] = runtime_data.zone_data

        self._device_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._scheduled = False
        self._state = False
        self._aborted = False
        self._last_run = None
        self._program_remaining = 0

        self._unsub_point_in_time = None
        self._unsub_start = None
        self._unsub_monitor = None
        self._unsub_pause = None

        self._pumps = []
        self._run_zones = [] #list of zones to run
        self._running_zone = [] #list of currently running zones
        self._extra_attrs = {}

        self._localtimezone = ZoneInfo(self._hass.config.time_zone)

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
        self._unsub_pause()
        self._unsub_pause = None

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

    def create_task_loop(self,task):
        '''Initiate an async call.'''
        loop = asyncio.get_event_loop()
        background_tasks = set()
        task = loop.create_task(task)
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    @callback
    def point_in_time_listener(self, time_date):
        """Get the latest time and check if irrigation should start."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self._hass, self.point_in_time_listener, self.get_next_interval()
        )

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
            and self.irrigation_on_value == 'on'
           ):
            self._running_zone = []
            self._scheduled = True
            self.create_task_loop(self.async_turn_on())
        self.async_write_ha_state()

    @callback
    def update_next_run(
        self, entity=None, old_status=None, new_status=None
    ):
        """Update the next run callback."""

        if self._program.sunrise_offset:
            sunrise = datetime.strptime(self._hass.states.get('sensor.sun_next_rising').state,'%Y-%m-%dT%H:%M:%S%z')
            d=timedelta(minutes=self._program.sunrise_offset.state)
            sunrise += d
            self.create_task_loop(
                self._program.start_time.async_set_value(sunrise.astimezone(self._localtimezone).replace(second=00, microsecond=00).time())
            )
        if self._program.sunset_offset:
            sunset = datetime.strptime(self._hass.states.get('sensor.sun_next_setting').state,'%Y-%m-%dT%H:%M:%S%z')
            d=timedelta(minutes=self._program.sunset_offset.state)
            sunset += d
            self.create_task_loop(
                self._program.start_time.async_set_value(sunset.astimezone(self._localtimezone).replace(second=00, microsecond=00).time())
            )

        if self._program.pause.is_on:
            #don't process changes to when attributes change
            return

        for zone in self._zones:
            self.create_task_loop(
                zone.switch.calc_next_run()
            )
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Add listener."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self._hass, self.point_in_time_listener, self.get_next_interval()
        )

        @callback
        def hass_started(event):
            """HA has started."""
            #build the zone to pump relationships
            pumps = {}
            for zone in self._zones:
                if zone.pump is not None:
                    # create pump - zone list
                    if zone.pump not in pumps:
                        pumps[zone.pump] = [zone.zone]
                    else:
                        pumps[zone.pump].append(zone.zone)
            # Build Zone Attributes to support the custom card
            self.create_task_loop(
                self.define_program_attributes()
            )
            # set up to monitor these entities
            self.set_up_entity_monitoring()

            # create pump class to start/stop pumps
            for pump, zones in pumps.items():
                # pass pump_switch, list of zones, off_delay
                self._pumps.append(PumpClass(self._hass, pump, zones))

            # calculate the next run
            self.update_next_run()

        # setup the callback to kick in when HASS has started
        # listen for config_flow change and apply the updates
        self._unsub_start = async_at_started(self._hass, hass_started)

        @callback
        def hass_shutdown(event):
            """Make sure everything is shut down."""
            for zone in self._zones:
                self.create_task_loop(
                    zone.async_turn_zone_off()
                )
        # setup the callback to listen for the shut down
        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hass_shutdown)

        await super().async_added_to_hass()

    @callback
    def set_up_entity_monitoring(self):
        """Set up to monitor these entities to change the next run data."""
        monitor = []
        monitor.append(self._program.start_time.entity_id)
        if self._program.sunrise_offset:
            monitor.append(self._program.sunrise_offset.entity_id)
        if self._program.sunset_offset:
            monitor.append(self._program.sunset_offset.entity_id)
        monitor.append(self._program.enabled.entity_id)
        monitor.append(self._program.pause.entity_id)
        if self._program.frequency:
            monitor.append(self._program.frequency.entity_id)
        for zone in self._zones:
            monitor.append(zone.switch.entity_id)
            monitor.append(zone.enabled.entity_id)
            if zone.frequency:
                monitor.append(zone.frequency.entity_id)
            if zone.rain_sensor:
                monitor.append(zone.rain_sensor)
            if zone.ignore_sensors:
                monitor.append(zone.ignore_sensors.entity_id)
            if zone.adjustment:
                monitor.append(zone.adjustment)
            if zone.water_source:
                monitor.append(zone.water_source)

        self._unsub_monitor = async_track_state_change_event(
            self._hass, tuple(monitor), self.update_next_run
        )
        monitor = []
        monitor.append(self._program.pause.entity_id)
        self._unsub_pause = async_track_state_change_event(
            self._hass, tuple(monitor), self.pause_program
        )


    async def define_program_attributes(self):
        """Build attributes in run order."""

        #Program attributes
        self._extra_attrs = {}
        self._extra_attrs[ATTR_START] = self._program.start_time.entity_id
        if self._program.start_type == 'sunrise':
            self._extra_attrs['sunrise'] = self._program.sunrise_offset.entity_id
        elif self._program.start_type == 'sunset':
            self._extra_attrs['sunset'] = self._program.sunset_offset.entity_id
        if self._program.frequency:
            self._extra_attrs[ATTR_RUN_FREQ] = self._program.frequency.entity_id
        self._extra_attrs[ATTR_IRRIGATION_ON] = self._program.enabled.entity_id
        if self._program.inter_zone_delay:
            self._extra_attrs[ATTR_DELAY] = self._program.inter_zone_delay.entity_id
        self._extra_attrs[ATTR_REMAINING] = self._program.remaining_time.entity_id
        self._extra_attrs[ATTR_SHOW_CONFIG] = self._program.config.entity_id
        self._extra_attrs[ATTR_PAUSE] = self._program.pause.entity_id

        # zone loop to initialise the attributes
        zones = self._zones
        zones = []
        for zone in self._zones:
            zones.append(zone.switch.entity_id)
        self._extra_attrs["zones"] = zones
        self.async_schedule_update_ha_state()

    async def entity_toggle_zone(self, zone) -> None:
        """Toggle a specific zone."""
        #built to handle a list but only one

        checkzone = None
        #index the switch to process
        for czone in self._zones:
            if czone.switch == zone.switch:
                checkzone = czone
                break
        if self._run_zones == []:
             #program is not already running
            self._running_zone = zone
            self._scheduled = False
            background_tasks = set()
            self._run_zones.append(checkzone)
            loop = asyncio.get_event_loop()
            task = loop.create_task(self.async_turn_on())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
        elif self._run_zones.count(checkzone) == 0:
            #program is running add the zone to the list to run
            self._run_zones.append(checkzone)
            await checkzone.switch.prepare_to_run(self._scheduled)
        else:
            #zone is running/queued turn it off
            await checkzone.switch.async_turn_off()
            if self._run_zones.count(checkzone) > 0:
                self._run_zones.remove(checkzone)
            if len(self._run_zones) == 0:
                await self.async_turn_off()

        self.async_schedule_update_ha_state()


    @property
    def inter_zone_delay(self):
        """Return interzone delay value."""
        if self.degree_of_parallel > 1:
            return 0
        if self._program.inter_zone_delay:
            return self._program.inter_zone_delay.state
        return 0

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
    def irrigation_on_value(self):
        """Zone  entity value."""
        return self._program.enabled.state

    @property
    def start_time_value(self):
        """Start time entity value."""
        value = None
        if self._program.start_time is not None:
            value = self._program.start_time.state
        return value

    @property
    def degree_of_parallel(self):
        """Start time entity value."""
        return int(self._program.parallel)

    async def build_run_script(self):
        """Build the run script based on each zones data."""
        zones = []
        for zone in self._zones:
            if self._running_zone:
                # Zone has been manually run from service call
                if zone.switch != self._running_zone.switch:
                    continue
            # auto_run where program started based on start time
            if await zone.switch.should_run(self._scheduled) is False:
                # calculate the next run
                continue

            await zone.switch.prepare_to_run(self._scheduled)
            zones.append(zone)
        return zones

    async def calculate_program_remaining(self, zones,izd_remaining=0):
        """Calculate the remaining time for the program."""

        class Stream(object):
            """Container for items that keeps a running sum."""

            def __init__(self):
                self.items = []
                self.sum = 0

            def append(self, item):
                self.items.append(item)
                self.sum += item

        if self.degree_of_parallel > 1:

            remaining = [int(zone.remaining_time.state) for zone in zones ]

            streams = []
            #create the streams
            for _ in range(self.degree_of_parallel):
                stream = Stream()
                streams.append(stream)

            for time in remaining:
            #put the time in the stream with the lowest time
                minstream = None
                for stream in streams:
                    if minstream is None:
                        minstream = stream
                    if minstream.sum > stream.sum:
                        minstream = stream
                minstream.append(time)

            remaining_time = 0
            for stream in streams:
            #return the max stream time
                remaining_time = max(remaining_time, stream.sum)

            self._program_remaining = remaining_time
            await self._program.remaining_time.set_value(self._program_remaining)
        else:
            self._program_remaining = 0
            for program_postion, zone in enumerate(zones,1):
                if zone.switch.status.state in  (CONST_ON, CONST_PENDING, CONST_ECO):
                    self._program_remaining +=  int(zone.remaining_time.state)
                    if program_postion < len(zones):
                        self._program_remaining += self.inter_zone_delay
            self._program_remaining += izd_remaining
            await self._program.remaining_time.set_value(self._program_remaining)
        return self._program_remaining

    async def async_finalise_run(self, zone, last_ran):
        """Clean up once it has run."""
        # clean up after the run
        if zone.switch.aborted is False:
            # completed zone
            await zone.last_ran.set_state(last_ran)

    async def pause_program(self, entity=None, old_status=None, new_status=None):
        """Program paused status changes."""
        if self._state is False:
            await self._program.pause.async_turn_off()
        for zone in self._zones:
            await zone.switch.pause()

    async def run_monitor_zones(self, running_zones, all_zones, last_ran):
        """Monitor zones to start based on inter zone delay."""
        if self._program.pause.is_on:
            await asyncio.sleep(1)
            return running_zones

        if running_zones == []:
            #start first zones
            for zone in all_zones:
                running_zones.append(zone.switch)
                await self.zone_turn_on(zone.switch)
                if len(running_zones) == self.degree_of_parallel:
                    break

        if len(running_zones) < self.degree_of_parallel:
            #add another zone as required
            pend = (x for x in all_zones if x.status.state == CONST_PENDING)
            for zone in pend:
                #start the next zone
                await self.zone_turn_on(zone.switch)
                running_zones.append(zone.switch)
                break

        rzones = running_zones

        for running_zone in rzones:
            if self.inter_zone_delay <= 0 and running_zone.remaining_time.state <= abs(self.inter_zone_delay):
                #zone has turned off remove from the running zones
                running_zones.remove(running_zone)

                #start the next zone if there is one
                pend = (x for x in all_zones if x.status.state == CONST_PENDING)
                for zone in pend:
                    #start the next zone
                    await self.zone_turn_on(zone.switch)
                    running_zones.append(zone.switch)
                    break

            if running_zone.remaining_time.state == 0 and running_zones.count(running_zone) > 0:
                running_zones.remove(running_zone)
                # if running_zone.aborted is False:
                #     await running_zone.last_ran.set_state(last_ran)

            if self.inter_zone_delay > 0 and running_zone.remaining_time.state == 0:
                #there is a + IZD and there is a zone to follow
                pend = (x for x in all_zones if x.status.state == CONST_PENDING)
                if len(list(pend)) > 0:
                    #start the delay before next
                    izd = int(self.inter_zone_delay)
                    for _ in range(int(self.inter_zone_delay)):
                        await asyncio.sleep(1)
                        izd -= 1
                        await self.calculate_program_remaining(all_zones,izd)
                for zone in (x for x in all_zones if x.status.state == CONST_PENDING):
                    #get the next pending zone and run it
                    await self.zone_turn_on(zone.switch)
                    running_zones.append(zone.switch)
                    break

        await self.calculate_program_remaining(all_zones)
        await asyncio.sleep(1)
        return running_zones

    async def zone_turn_on(self,zone):
        """Turn on the irrigation zone."""
        background_tasks = set()

        loop = asyncio.get_event_loop()
        task = loop.create_task(zone.set_scheduled(self._scheduled))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

        loop = asyncio.get_event_loop()
        task = loop.create_task(zone.async_turn_on())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

        return True

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        if self._state is True:
            # program is already running
            return

        self._run_zones = await self.build_run_script()
        #take a copy to finalise with
        scheduled_zones = self._run_zones.copy()

        if len(self._run_zones) > 0:
            # raise event when the program starts
            event_data = {
                "action": "program_turned_on",
                "device_id": self._device_id,
                "scheduled": self._scheduled,
                "program": self.name,
            }
            self._hass.bus.async_fire("irrigation_event", event_data)
        else:
            # No zones to run
            return
        self._state = True
        self.async_schedule_update_ha_state()
        # stop all running programs except the calling program
        if self._program.interlock:
            await async_stop_programs(self._hass, self.name)

        # start pump monitoring
        loop = asyncio.get_event_loop()
        background_tasks = set()
        for thispump in self._pumps:
            task = loop.create_task(thispump.async_monitor())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        # now start the program
        # all zones will have the last ran of the program start
        p_last_ran = datetime.now(self._localtimezone)
        # calculate the remaining time for the program
        # Monitor and start the zone with lead/lag time
        running_zones = []
        running_zones = await self.run_monitor_zones(running_zones, self._run_zones,p_last_ran)

        while self._program_remaining > 0:
            running_zones = await self.run_monitor_zones(running_zones, self._run_zones,p_last_ran)
        # clean up after the run
        for zone in scheduled_zones:
            await self.async_finalise_run(zone, p_last_ran)


        # run is complete stop pump monitoring
        background_tasks = set()
        for pump in self._pumps:
            task = loop.create_task(pump.async_stop_monitoring())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        event_data = {
            "action": "program_turned_off",
            "device_id": self._device_id,
            "program": self.name,
        }
        self._hass.bus.async_fire("irrigation_event", event_data)
        #reset indicators
        self._state = False
        self._scheduled = False
        self._running_zone = []
        self._run_zones = []
        self.async_schedule_update_ha_state()
        # program finished

    async def async_turn_off(self, **kwargs):
        """Stop the switch/program."""
        await self._program.pause.async_turn_off()
        if self._state is True:
            self._state = False
            self._scheduled = False
            self._running_zone = []
            self._run_zones = []
            for zone in self._zones:
                if zone.switch.remaining_time.state > 0:
                    self._aborted = True
                await zone.switch.async_turn_off()
        self.async_schedule_update_ha_state()
