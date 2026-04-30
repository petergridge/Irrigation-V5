"""Switch entity definition."""

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.const import MATCH_ALL
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util, slugify

from . import (
    IrrigationData,
    IrrigationProgram as ProgramData,
    IrrigationZoneData as ZoneData,
    async_queue_program as queue_program,
)
from .const import (
    ATTR_DEFAULT_RUN_TIME,
    ATTR_DELAY,
    ATTR_IRRIGATION_ON,
    ATTR_PAUSE,
    ATTR_REMAINING,
    ATTR_RUN_FREQ,
    ATTR_SHOW_CONFIG,
    ATTR_START,
    CONST_OFF,
    CONST_ON,
    CONST_PENDING,
    TIME_STR_FORMAT,
)
from .globals import PROGRAMS, QUEUEDPROGRAMS, REMAINING_ZONES, RUNNING_ZONES
from .pump import PumpClass

_LOGGER = logging.getLogger(__name__)


class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""

    _attr_has_entity_name = True
    _attr_attribution = "Irrigation Program"
    _unrecorded_attributes = frozenset({MATCH_ALL})
    _attr_translation_key = "program"
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, unique_id, device_id, runtime_data: IrrigationData
    ) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = unique_id
        self._hass = hass

        self._name = runtime_data.program.name
        self._program: ProgramData = runtime_data.program
        self._zones: list[ZoneData] = runtime_data.zone_data

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._scheduled = False
        self._state = False
        self._finished = True
        self._paused = False
        self._stop = False

        self._program_remaining = 0
        self._default_run_time = 0

        self._unsub_point_in_time = None
        self._unsub_start = None
        self._unsub_monitor = None
        self._unsub_pause = None
        self._unsub_pause_water = None

        self._pumps = []
        self._run_zones = []  # list of zones to run
        self._running_zone: ZoneData | None = (
            None  # list of currently running zones
        )
        self._extra_attrs = {}
        self._localtimezone = ZoneInfo(self._hass.config.time_zone)

        PROGRAMS.update({self._name: self})

    def generate_card(self):
        """Create card config yaml."""
        modified = None
        if self._program.modified:
            # dt_util.parse_datetime handles ISO strings and returns aware objects if tz info is present
            if type(self._program.modified) is datetime:
                modified: datetime | None = self._program.modified
            else:
                modified: datetime | None = dt_util.parse_datetime(
                    self._program.modified
                )

        # only generate the card if recently modified
        now = dt_util.now()
        if modified:
            modified_local = dt_util.as_local(modified)
            if now - modified_local > timedelta(seconds=30):
                return

        def add_entity(object, conditions, simple=False):
            if object:
                data = ""
                data += "- type: conditional" + chr(10)
                data += "  conditions:" + chr(10)
                for condition in conditions:
                    x = 1
                    for k, v in condition.items():
                        if x == 1:
                            data += "  - "
                            x = 2
                        else:
                            data += "    "
                        data += k + ": " + v + chr(10)
                data += "  row:" + chr(10)
                if simple:
                    data += "    type: " + "simple-entity" + chr(10)
                data += "    entity: " + object.entity_id + chr(10)

                return data
            return ""

        def add_entity_2(object, conditions, simple=False):
            if object:
                data = ""
                data += "- type: conditional" + chr(10)
                data += "  conditions:" + chr(10)
                for condition in conditions:
                    x = 1
                    for k, v in condition.items():
                        if x == 1:
                            data += "  - "
                            x = 2
                        else:
                            data += "    "
                        data += k + ": " + v + chr(10)
                data += "  row:" + chr(10)
                if simple:
                    data += "    type: " + "simple-entity" + chr(10)
                data += "    entity: " + object + chr(10)

                return data
            return ""

        card: str = "### Copy into manual card" + chr(10)
        card += "```" + chr(10)

        card += "state_color: true" + chr(10)
        card += "show_header_toggle: false" + chr(10)

        card += "type: entities" + chr(10)
        card += "entities:" + chr(10)
        card += "- type: conditional" + chr(10)
        card += "  conditions:" + chr(10)
        card += "  - entity: " + self.entity_id + chr(10)
        card += "    state: off" + chr(10)
        card += "  row:" + chr(10)
        card += "    type: buttons" + chr(10)
        card += "    entities: " + chr(10)
        card += "    - entity: " + self.entity_id + chr(10)
        card += "      show_name: true" + chr(10)
        card += "    - entity: " + self._program.config.entity_id + chr(10)
        card += "      show_name: true" + chr(10)
        card += "- type: conditional" + chr(10)
        card += "  conditions:" + chr(10)
        card += "  - entity: " + self.entity_id + chr(10)
        card += "    state: on" + chr(10)
        card += "  row:" + chr(10)
        card += "    type: buttons" + chr(10)
        card += "    entities: " + chr(10)
        card += "    - entity: " + self.entity_id + chr(10)
        card += "      show_name: true" + chr(10)
        card += "    - entity: " + self._program.config.entity_id + chr(10)
        card += "      show_name: true" + chr(10)
        card += "    - entity: " + self._program.pause.entity_id + chr(10)
        card += "      show_name: true" + chr(10)

        condition = [
            {"entity": self.entity_id, "state_not": "on"},
            {"entity": self._program.config.entity_id, "state_not": "on"},
            {"entity": self._program.enabled.entity_id, "state": "on"},
        ]
        card += add_entity(self._program.start_time, condition, True)
        card += add_entity(self._program.default_run_time, condition, True)
        condition = [
            {"entity": self.entity_id, "state_not": "on"},
            {"entity": self._program.config.entity_id, "state_not": "on"},
            {"entity": self._program.enabled.entity_id, "state_not": "on"},
        ]
        card += add_entity(self._program.enabled, condition, True)
        card += add_entity(self._program.default_run_time, condition, True)

        condition = [{"entity": self._program.config.entity_id, "state": "on"}]
        if self._program.sunrise_offset or self._program.sunset_offset:
            card += add_entity(self._program.start_time, condition, True)
            card += add_entity(self._program.default_run_time, condition, True)
        else:
            card += add_entity(self._program.start_time, condition)
            card += add_entity(self._program.default_run_time, condition)
        card += add_entity(self._program.sunrise_offset, condition)
        card += add_entity(self._program.sunset_offset, condition)

        condition = [{"entity": self.entity_id, "state": "on"}]
        card += add_entity(self._program.remaining_time, condition)

        condition = [{"entity": self._program.config.entity_id, "state": "on"}]
        card += add_entity(self._program.enabled, condition)
        card += add_entity(self._program.frequency, condition)
        card += add_entity(self._program.inter_zone_delay, condition)
        card += add_entity(self._program.repeats, condition)
        if self._program.rain_delay_on:
            card += add_entity(self._program.rain_delay, condition)
            card += add_entity(self._program.rain_delay_days, condition)

        # now process the zones
        for zone in self._zones:
            card += "- type: section" + chr(10)
            card += "  label: ''" + chr(10)
            card += "- type: conditional" + chr(10)
            card += "  conditions:" + chr(10)
            card += "  - entity: " + zone.switch.entity_id + chr(10)
            card += "    state: off" + chr(10)
            card += "  row:" + chr(10)
            card += "    type: buttons" + chr(10)
            card += "    entities: " + chr(10)
            card += "    - entity: " + zone.switch.entity_id + chr(10)
            card += "      show_name: true" + chr(10)
            card += "      show_icon: true" + chr(10)
            card += "      tap_action: " + chr(10)
            card += "        action: call-service" + chr(10)
            card += "        service: switch.toggle" + chr(10)
            card += "        service_data:" + chr(10)
            card += "          entity_id: " + zone.switch.entity_id + chr(10)
            card += "    - entity: " + zone.config.entity_id + chr(10)
            card += "      show_name: true" + chr(10)

            card += "- type: conditional" + chr(10)
            card += "  conditions:" + chr(10)
            card += "  - entity: " + zone.switch.entity_id + chr(10)
            card += "    state_not: off" + chr(10)
            card += "  row:" + chr(10)
            card += "    type: buttons" + chr(10)
            card += "    entities: " + chr(10)
            card += "    - entity: " + zone.switch.entity_id + chr(10)
            card += "      show_name: true" + chr(10)
            card += "      show_icon: true" + chr(10)
            card += "      tap_action: " + chr(10)
            card += "        action: call-service" + chr(10)
            card += "        service: switch.toggle" + chr(10)
            card += "        service_data:" + chr(10)
            card += "          entity_id: " + zone.switch.entity_id + chr(10)
            card += "    - entity: " + zone.config.entity_id + chr(10)
            card += "      show_name: true" + chr(10)
            card += "    - entity: " + zone.status.entity_id + chr(10)
            card += "      show_name: false" + chr(10)

            condition = [{"entity": zone.status.entity_id, "state": '["off"]'}]
            card += add_entity(zone.next_run, condition)

            condition = [
                {
                    "entity": zone.status.entity_id,
                    "state_not": '["off", "on", "pending", "eco"]',
                }
            ]
            card += add_entity(zone.status, condition)

            condition = [
                {"entity": zone.status.entity_id, "state": '["on","eco","pending"]'}
            ]
            card += add_entity(zone.remaining_time, condition)

            condition = [
                {
                    "entity": zone.status.entity_id,
                    "state_not": '["on", "eco", "pending"]',
                },
                {"entity": zone.config.entity_id, "state": "on"},
            ]
            card += add_entity(zone.last_ran, condition)

            condition = [{"entity": zone.config.entity_id, "state": "on"}]
            card += add_entity(zone.enabled, condition)
            card += add_entity(zone.frequency, condition)
            card += add_entity(zone.default_run_time, condition)
            card += add_entity(zone.water, condition)
            card += add_entity(zone.wait, condition)
            card += add_entity(zone.repeat, condition)
            card += add_entity_2(self._program.flow_sensor, condition)
            card += add_entity_2(zone.adjustment, condition)
            card += add_entity_2(zone.rain_sensor, condition)
            card += add_entity_2(self._program.water_source, condition)
            card += add_entity(zone.ignore_sensors, condition)

        card += "```" + chr(10)

        # create the persistent notification
        if self._program.card_yaml is True:
            async_dismiss(self.hass, "irrigation_card")
            async_create(
                self._hass,
                message=card,
                title="Irrigation Controller",
                notification_id="irrigation_card",
            )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel next update."""

        await self.async_turn_off()

        if self._unsub_point_in_time:
            self._unsub_point_in_time()
            self._unsub_point_in_time = None
        if self._unsub_start:
            self._unsub_start()
            self._unsub_start = None
        # stop monitoring
        if self._unsub_monitor:
            self._unsub_monitor()
            self._unsub_monitor = None
        if self._unsub_pause:
            self._unsub_pause()
            self._unsub_pause = None
        if self._unsub_pause_water:
            self._unsub_pause_water()
            self._unsub_pause_water = None

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
    def point_in_time_listener(self, time_date):
        """Get the latest time and check if irrigation should start."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self._hass, self.point_in_time_listener, self.get_next_interval()
        )

        time = datetime.now(self._localtimezone).strftime(TIME_STR_FORMAT)
        string_times = self.start_time_value
        if string_times:
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
                and self.irrigation_on_value == "on"
            ):
                self._running_zone = None
                self._scheduled = True
                self.hass.async_create_task(self.async_turn_on())
            self.async_write_ha_state()

    async def default_run_time_set(self):
        """Update the remaining time sensor."""
        await self.hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": self._program.default_run_time.entity_id},
            blocking=True,
        )

    async def remaining_time_set(self):
        """Update the remaining time sensor."""
        await self.hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": self._program.remaining_time.entity_id},
            blocking=True,
        )

    async def update_next_run(self, entity=None, old_status=None, new_status=None):
        """Update the next run callback."""

        d = timedelta(0)
        if self._program.sunrise_offset:
            # 1. Get the state string safely
            sun_state = self._hass.states.get("sensor.sun_next_rising")

            if sun_state and sun_state.state not in ("unknown", "unavailable"):
                # 2. Parse using dt_util (handles ISO strings better than strptime)
                sunrise = dt_util.parse_datetime(sun_state.state)

                # 3. Convert string offset to a number (float or int)
                try:
                    if self._program.sunrise_offset.state:
                        offset_minutes = float(self._program.sunrise_offset.state)
                        d = timedelta(minutes=offset_minutes)

                    # 4. Apply offset and convert to local time
                    if sunrise:
                        adjusted_sunrise = dt_util.as_local(sunrise + d)

                    # 5. Extract the time component without seconds/micros
                    target_time = adjusted_sunrise.replace(
                        second=0, microsecond=0
                    ).time()

                    self.hass.async_create_task(
                        self._program.start_time.async_set_value(target_time)
                    )
                except ValueError:
                    # Handle case where offset state isn't a valid number
                    pass

        if self._program.sunset_offset:
            # 1. Safely get the sun setting state
            sunset_state = self._hass.states.get("sensor.sun_next_setting")

            if sunset_state and sunset_state.state not in ("unknown", "unavailable"):
                # 2. Parse the ISO string to an aware datetime
                sunset = dt_util.parse_datetime(sunset_state.state)

                if sunset:
                    try:
                        # 3. Convert the string offset to a float/int
                        if self._program.sunset_offset.state:
                            offset_minutes = float(self._program.sunset_offset.state)
                            d = timedelta(minutes=offset_minutes)

                        # 4. Apply offset and convert to local time
                        adjusted_sunset = dt_util.as_local(sunset + d)

                        # 5. Extract time and update the value
                        target_time = adjusted_sunset.replace(
                            second=0, microsecond=0
                        ).time()

                        self.hass.async_create_task(
                            self._program.start_time.async_set_value(target_time)
                        )
                    except ValueError:
                        # Handle case where offset is not a valid number
                        pass

        if self._paused:
            # don't process changes to when attributes change
            return

        for zone in self._zones:
            kwargs = {}
            kwargs["action"] = "update_next_run"
            await zone.switch.async_toggle(**kwargs)

        # calculate the duration of the program
        if self._program.enabled.state == CONST_OFF:
            self._default_run_time = 0
            await self.default_run_time_set()
        else:
            zones = []
            for _ in range(self.repeats_value - 1, -1, -1):
                zones += await self.build_run_script(True)

            await self.calculate_program_remaining(
                [], zones, default_run_time=True
            )

        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Add listener."""
        self._unsub_point_in_time = async_track_point_in_utc_time(
            self._hass, self.point_in_time_listener, self.get_next_interval()
        )

        async def hass_started(event):
            """HA has started."""
            # build the zone to pump relationships
            pumps = {}
            if self._program.pump:
                for zone in self._zones:
                    # create pump - zone list
                    if self._program.pump not in pumps:
                        pumps[self._program.pump] = [zone]
                    else:
                        pumps[self._program.pump].append(zone)

            # Build Zone Attributes to support the custom card
            # self.hass.async_create_task(await self.define_program_attributes())
            await self.define_program_attributes()

            # create pump class to start/stop pumps
            for pump, zones in pumps.items():
                # pass pump_switch, list of zones, off_delay
                pumpobj = PumpClass(self._hass, pump, zones, self)
                self._pumps.append(pumpobj)

            # calculate the next run
            await self.update_next_run()
            # set up to monitor these entities
            await asyncio.sleep(0)
            await self.set_up_entity_monitoring()

        # setup the callback to kick in when HASS has started
        # listen for config_flow change and apply the updates
        self._unsub_start = async_at_started(self._hass, hass_started)

        await super().async_added_to_hass()

        # generate the entities card yaml to replicate the custom card
        await asyncio.sleep(1)
        if self._program.card_yaml:
            self.generate_card()

    async def set_up_entity_monitoring(self):
        """Set up to monitor these entities to change the next run data."""

        def monitor_append(object, name=None, table=None):
            if object not in table:
                try:
                    table.append(object)
                except AttributeError:
                    async_dismiss(self.hass, "irrigation_device_error1")
                    async_create(
                        self.hass,
                        message=f"Warning, configured monitor {name} item is no longer available or has been renamed",
                        title="Irrigation Controller",
                        notification_id="irrigation_device_error1",
                    )

        monitor = []

        monitor_append(self._program.start_time.entity_id, "start_time", monitor)
        if self._program.sunrise_offset:
            monitor_append(self._program.sunrise_offset.entity_id, "sunrise_offset", monitor)
            monitor_append("sensor.sun_next_rising", None, monitor)
        if self._program.sunset_offset:
            monitor_append(self._program.sunset_offset.entity_id, "sunset_offset", monitor)
            monitor_append("sensor.sun_next_setting", None, monitor)
        monitor_append(self._program.enabled.entity_id, "enabled", monitor)
        if self._program.rain_delay:
            monitor_append(self._program.rain_delay.entity_id, "rain_delay", monitor)
            monitor_append(self._program.rain_delay_days.entity_id, "rain_delay_days", monitor)
        if self._program.frequency:
            monitor_append(self._program.frequency.entity_id, "frequency", monitor)
        if self._program.inter_zone_delay:
            monitor_append(self._program.inter_zone_delay.entity_id, "inter_zone_delay", monitor)
        if self._program.repeats:
            monitor_append(self._program.repeats.entity_id, "repeats", monitor)
        if self._program.water_source:
            monitor_append(self._program.water_source, "water_source", monitor)

        for zone in self._zones:
            monitor_append(zone.switch.entity_id, "zone", monitor)
            monitor_append(zone.enabled.entity_id, "enabled", monitor)
            if zone.frequency:
                monitor_append(zone.frequency.entity_id, "frequency", monitor)
            if zone.rain_sensor:
                monitor_append(zone.rain_sensor, "rain_sensor", monitor)
            if zone.ignore_sensors:
                # possible problem
                monitor_append(zone.ignore_sensors.entity_id, "ignore_sensors", monitor)
            if zone.adjustment:
                monitor_append(zone.adjustment, "adjustment", monitor)
            if zone.water:
                monitor_append(zone.water.entity_id, "water", monitor)
            if zone.repeat:
                monitor_append(zone.repeat.entity_id, "repeat", monitor)
            if zone.wait:
                monitor_append(zone.wait.entity_id, "wait", monitor)

        self._unsub_monitor = async_track_state_change_event(
            self._hass, tuple(monitor), self.update_next_run
        )

        monitor2 = []

        if self._program.water_source and self._program.water_source_pause:
            monitor_append(self._program.water_source, "water_source", monitor2 )
        self._unsub_pause_water = async_track_state_change_event(
            self._hass, tuple(monitor2), self.pause_program_water_source
        )

        monitor3 = []
        monitor_append(self._program.pause.entity_id, "pause", monitor3 )
        self._unsub_pause = async_track_state_change_event(
            self._hass, tuple(monitor3), self.pause_program
        )

    async def define_program_attributes(self):
        """Build attributes in run order."""

        # Program attributes
        self._extra_attrs = {}
        self._extra_attrs[ATTR_START] = self._program.start_time.entity_id
        if self._program.start_type == "sunrise":
            self._extra_attrs["sunrise"] = self._program.sunrise_offset.entity_id
        elif self._program.start_type == "sunset":
            self._extra_attrs["sunset"] = self._program.sunset_offset.entity_id
        if self._program.frequency:
            self._extra_attrs[ATTR_RUN_FREQ] = self._program.frequency.entity_id
        self._extra_attrs[ATTR_IRRIGATION_ON] = self._program.enabled.entity_id
        if self._program.inter_zone_delay:
            self._extra_attrs[ATTR_DELAY] = self._program.inter_zone_delay.entity_id
        if self._program.repeats:
            self._extra_attrs["repeats"] = self._program.repeats.entity_id
        if self._program.rain_delay:
            self._extra_attrs["enable_rain_delay"] = self._program.rain_delay.entity_id
            self._extra_attrs["rain_delay_days"] = (
                self._program.rain_delay_days.entity_id
            )
        self._extra_attrs[ATTR_REMAINING] = self._program.remaining_time.entity_id
        self._extra_attrs[ATTR_DEFAULT_RUN_TIME] = (
            self._program.default_run_time.entity_id
        )
        self._extra_attrs[ATTR_SHOW_CONFIG] = self._program.config.entity_id
        self._extra_attrs[ATTR_PAUSE] = self._program.pause.entity_id

        # zone loop to initialise the attributes
        zones = []
        for zone in self._zones:
            try:
                zones.append(zone.switch.entity_id)
            except AttributeError:
                async_dismiss(self.hass, "irrigation_device_error2")
                async_create(
                    self.hass,
                    message=f"Warning, configured zone item {zone} is no longer available or has been renamed",
                    title="Irrigation Controller",
                    notification_id="irrigation_device_error2",
                )
        self._extra_attrs["zones"] = zones
        self.async_schedule_update_ha_state()

    async def entity_toggle_zone(self, zone) -> None:
        """Toggle a specific zone."""
        # called from the zone to ensure the program is notified
        # when the zone is stopped manually while it is running
        # built to handle a list but only one
        checkzone = None
        # index the switch to process
        for czone in self._zones:
            if czone.switch == zone.switch:
                checkzone = czone
                break

        if self._run_zones == []:
            # program is not already running
            self._running_zone = zone
            self._scheduled = False
            self._run_zones.append(zone)
            # self.hass.async_create_task(self.async_turn_on())
            await self.async_turn_on()
        elif self._run_zones.count(zone) == 0:
            # program is running add the zone to the list to run
            self._run_zones.append(zone)
            REMAINING_ZONES.append(zone)
            if checkzone:
                kwargs = {}
                kwargs["action"] = "prepare_to_run"
                kwargs["scheduled"] = self._scheduled
                await checkzone.switch.async_toggle(**kwargs)
        else:
            # zone is running/queued turn it off
            if checkzone:
                await checkzone.switch.async_turn_off()
            if self._run_zones.count(zone) > 0:
                self._run_zones.remove(zone)

            if len(self._run_zones) == 0:
                await self.async_turn_off()

        self.async_schedule_update_ha_state()

    @property
    def default_run_time_value(self):
        """Next run value for sensor."""
        return self._default_run_time

    @property
    def remaining_time_value(self):
        """Next run value for sensor."""
        return self._program_remaining

    @property
    def inter_zone_delay(self):
        """Return interzone delay value."""
        if self.degree_of_parallel > 1:
            return 0
        if self._program.inter_zone_delay and self._program.inter_zone_delay.state:
            return int(self._program.inter_zone_delay.state)
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
    def interlock(self):
        """Zone  entity value."""
        return self._program.interlock

    @property
    def pause_switch(self):
        """Zone  entity value."""
        return self._program.pause

    @property
    def repeats_value(self):
        """Get the value of program repeats."""
        value = 1
        if self._program.repeat is True:
            value = self._program.repeats.native_value
        return int(value)

    @property
    def start_time_value(self) -> int:
        """Start time entity value."""
        value = None
        if self._program.start_time is not None:
            value = self._program.start_time.state
        return value

    @property
    def degree_of_parallel(self):
        """Start time entity value."""
        return int(self._program.parallel)

    async def build_run_script(self, init=False):
        """Build the run script based on each zones data."""
        zones = []
        for zone in self._zones:
            if self._running_zone:
                # Zone has been manually run from service call
                if zone.switch != self._running_zone.switch:
                    continue
            # auto_run where program started based on start time
            if (
                zone.switch
                and await zone.switch.should_run_ex(self._scheduled) is False
            ):
                # calculate the next run
                continue

            if not init:
                kwargs = {}
                kwargs["action"] = "prepare_to_run"
                kwargs["scheduled"] = self._scheduled
                await zone.switch.async_toggle(**kwargs)
            zones.append(zone)
        return zones

    async def calculate_program_remaining(
        self, running_zones, remaining_zones, izd_remaining=0, default_run_time=False
    ):
        """Calculate the remaining time for the program."""

        class Stream:
            """Container for items that keeps a running sum for parrallel zones."""

            def __init__(self) -> None:
                self.items = []
                self.sum = 0

            def append(self, item):
                self.items.append(item)
                self.sum += item

        if default_run_time:
            remaining = [zone.switch.default_run_time for zone in remaining_zones]
        else:
            remaining = [zone.remaining_time.numeric_value for zone in running_zones]
            remaining += [zone.switch.default_run_time for zone in remaining_zones]

        streams = []
        # create the streams
        for _ in range(self.degree_of_parallel):
            stream: Stream = Stream()
            streams.append(stream)

        for time in remaining:
            # put the time in the stream with the lowest time
            minstream = None
            for stream in streams:
                if minstream is None:
                    minstream = stream
                if minstream.sum > stream.sum:
                    minstream = stream
            if minstream:
                minstream.append(time)

        remaining_time = 0
        for stream in streams:
            # return the max stream time
            remaining_time = max(remaining_time, stream.sum)

        if self.degree_of_parallel == 1:
            # add in the required zone transitions
            remaining_count = len(remaining_zones) + len(running_zones)
            remaining_time += self.inter_zone_delay * (remaining_count - 1)
            # If there is an active izd add it to the total
            if izd_remaining:
                remaining_time += izd_remaining

        if len(running_zones) == 0 and len(remaining_zones) == 0:
            remaining_time = 0

        if default_run_time is True:
            # remaining_time = remaining_time * self.repeats_value
            self._default_run_time = remaining_time
            await self.default_run_time_set()
        else:
            self._program_remaining = remaining_time
            await self.remaining_time_set()

        self.async_schedule_update_ha_state()

        return remaining_time

    async def pause_program_water_source(
        self,
        event: Event[EventStateChangedData],
    ):
        """Program paused status changes."""
        if (
            event.data["new_state"]
            and event.data["new_state"].state == CONST_ON
            and self.state == CONST_ON
        ):
            await self._program.pause.async_turn_off()

        if (
            event.data["new_state"]
            and event.data["new_state"].state == CONST_OFF
            and self.state == CONST_ON
        ):
            await self._program.pause.async_turn_on()

    async def pause_program(
        self,
        event: Event[EventStateChangedData],
    ):
        """Program paused status changes."""
        if self._program.pause.is_on:
            self._paused = True

        for zone in self._zones:
            kwargs = {}
            kwargs["action"] = "pause"
            await zone.switch.async_toggle(**kwargs)
        await asyncio.sleep(1)

        if not self._program.pause.is_on:
            self._paused = False

        if self._state is False:
            await self._program.pause.async_turn_off()

    async def zone_pending(self, zone) -> bool:
        """Determine if a another instance of the zone is pending."""
        if REMAINING_ZONES.count(zone) >= 1:
            return True
        return False

    async def run_monitor_zones(self):
        """Monitor zones to start based on inter zone delay."""

        if self._stop is True:
            # break out if program terminated
            self._program_remaining = 0
            await self.remaining_time_set()
            return RUNNING_ZONES

        if self._paused:
            await asyncio.sleep(1)
            return RUNNING_ZONES

        await self.calculate_program_remaining(
            RUNNING_ZONES, REMAINING_ZONES
        )
        await asyncio.sleep(1)

        if len(RUNNING_ZONES) < self.degree_of_parallel and len(REMAINING_ZONES) > 0:
            await self.zone_turn_on(REMAINING_ZONES[0], len(REMAINING_ZONES) == 1)
            RUNNING_ZONES.append(REMAINING_ZONES[0])
            del REMAINING_ZONES[0]
            return RUNNING_ZONES

        rzones = RUNNING_ZONES
        for running_zone in rzones:
            # add another zone as required
            if self._state is False:
                # break out if program terminated
                break

            if (
                self.inter_zone_delay <= 0
                and running_zone.remaining_time.numeric_value
                <= abs(self.inter_zone_delay)
                and len(RUNNING_ZONES) == self.degree_of_parallel
            ):
                # start the next zone if there is one
                if len(REMAINING_ZONES) > 0:
                    await self.zone_turn_on(REMAINING_ZONES[0], len(REMAINING_ZONES) == 1)
                    RUNNING_ZONES.append(REMAINING_ZONES[0])
                    del REMAINING_ZONES[0]

            if (
                self.inter_zone_delay > 0
                and running_zone.remaining_time.numeric_value <= 1
                and len(REMAINING_ZONES) > 0
            ):
                # there is a +'ve IZD and there is a zone to follow
                if len(REMAINING_ZONES) > 0:
                    # Delay before next zone
                    for izd in range(int(self.inter_zone_delay), 0, -1):
                        await asyncio.sleep(1)
                        await self.calculate_program_remaining(
                                RUNNING_ZONES, REMAINING_ZONES, izd
                            )
                        if self.state == CONST_OFF:
                            break
                # Interzone delay is complete
                if len(RUNNING_ZONES) < self.degree_of_parallel:
                    await self.zone_turn_on(REMAINING_ZONES[0], len(REMAINING_ZONES) == 1)
                    RUNNING_ZONES.append(REMAINING_ZONES[0])
                    del REMAINING_ZONES[0]

        return RUNNING_ZONES

    async def zone_turn_on(self, zone, last=False):
        """Turn on the irrigation zone."""
        await zone.switch.set_scheduled(self._scheduled)
        # run in the event loop to support independant executions
        self.hass.async_create_task(zone.switch.async_turn_on_from_program(last))
        await asyncio.sleep(0)

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        if self._program.enabled.state == CONST_OFF and self._scheduled is True:
            return
        self._stop = False
        if self._state is True:
            # program is already running
            return
        if self._finished is False:
            # program is not finalised from previous run
            return

        # Multiple iterations of the program
        self._run_zones = []
        for _ in range(self.repeats_value - 1, -1, -1):
            self._run_zones += await self.build_run_script()

        if len(self._run_zones) > 0:
            # raise event when the program starts
            event_data = {
                "action": "program_turned_on",
                "device_id": self.entity_id,
                "scheduled": self._scheduled,
                "program": self.name,
            }
            self._hass.bus.async_fire("irrigation_event", event_data)
        else:
            # No zones to run
            event_data = {
                "action": "program_no_zones_ready",
                "device_id": self.entity_id,
                "scheduled": self._scheduled,
                "program": self.name,
            }
            self._hass.bus.async_fire("irrigation_event", event_data)
            return

        self._state = True
        self._finished = False
        self.async_schedule_update_ha_state()

        # stop all running programs except the calling program
        if self._program.interlock:
            await queue_program(self._hass, self)
            if self._pumps:
                await asyncio.sleep(1)

        # calculate the remaining time for the program
        # Monitor and start the zone with lead/lag time
        for zone in self._run_zones:
            if zone.status.state in (CONST_PENDING, CONST_ON):
                REMAINING_ZONES.append(zone)

        RUNNING_ZONES.clear()
        await self.run_monitor_zones()

        while self._program_remaining > 0:
            await self.run_monitor_zones()

        event_data = {
            "action": "program_turned_off",
            "device_id": self.entity_id,
            "program": self.name,
        }
        self._hass.bus.async_fire("irrigation_event", event_data)
        await self.async_turn_off()

    async def async_turn_off(self, **kwargs):
        """Stop the switch/program."""

        self._stop = True
        if self._pumps:
            event_data = {
                "action": "turn_off_pump_all",
                "program": self.entity_id,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)
            await asyncio.sleep(3)

        await self._program.pause.async_turn_off()
        self._scheduled = False
        self._running_zone = None
        self._run_zones = []
        self._program_remaining = 0
        for zone in self._zones:
            if zone.switch.state == CONST_ON:
                await zone.switch.async_turn_off()
                await asyncio.sleep(0)
        self._state = False
        self._finished = True
        self.async_schedule_update_ha_state()

        # check the queue remove this program
        for n, x in enumerate(QUEUEDPROGRAMS):
            if x.name == self._name:
                QUEUEDPROGRAMS.pop(n)
        # unpause the next program in the queue
        if len(QUEUEDPROGRAMS) > 0:
            await QUEUEDPROGRAMS[0].pause_switch.async_turn_off()
        REMAINING_ZONES.clear()
