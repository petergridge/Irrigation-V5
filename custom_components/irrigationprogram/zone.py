import asyncio
from datetime import timedelta
import logging
import math

from homeassistant.components.number import NumberEntity
from homeassistant.components.persistent_notification import async_create
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    MATCH_ALL,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util, slugify

from . import IrrigationProgram, IrrigationZoneData
from .const import (
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_HISTORICAL_FLOW,
    ATTR_IGNORE_SENSOR,
    ATTR_LAST_RAN,
    ATTR_NEXT_RUN,
    ATTR_RAIN_SENSOR,
    ATTR_REMAINING,
    ATTR_REPEAT,
    ATTR_RUN_FREQ,
    ATTR_SHOW_CONFIG,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_WATER_SOURCE,
    BHYVE,
    BHYVE_DURATION,
    BHYVE_TURN_ON,
    CONST_ABORTED,
    CONST_ADJUSTED_OFF,
    CONST_CLOSED,
    CONST_DISABLED,
    CONST_ECO,
    CONST_LATENCY,
    CONST_NO_WATER_SOURCE,
    CONST_OFF,
    CONST_ON,
    CONST_OPEN,
    CONST_PAUSED,
    CONST_PENDING,
    CONST_PROGRAM_DISABLED,
    CONST_RAINING,
    CONST_RAINING_STOP,
    CONST_SWITCH,
    CONST_UNAVAILABLE,
    CONST_VALVE,
    CONST_ZERO_FLOW_DELAY,
    CONST_ZONE_DISABLED,
    RAINBIRD,
    RAINBIRD_DURATION,
    RAINBIRD_TURN_ON,
    TIME_STR_FORMAT,
)

VALID_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_LOGGER = logging.getLogger(__name__)


class Zone(SwitchEntity, RestoreEntity):
    """Represents the zone."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        unique_id,
        pname,
        zname,
        zfriendly_name,
        zonedata: IrrigationZoneData,
        programdata: IrrigationProgram,
    ) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_{zname}_zone")
        self._attr_attribution = f"Irrigation Controller: {pname} {zname}"
        self._extra_attrs = {}
        self.translation_placeholders = {"zone_name": f"{zfriendly_name}"}
        self._programdata = programdata
        self._zonedata = zonedata

        self._remaining_time = 0
        self._state = CONST_OFF  # switch state
        self._status = CONST_OFF  # zone run status
        self._last_status = None
        self._stop = False
        self._aborted = True
        self._scheduled = False
        self._hist_flow_rate = 1
        self._water_adjust_prior = 1

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        self._hist_flow_rate = 1
        if last_state:
            self._hist_flow_rate = last_state.attributes.get(ATTR_HISTORICAL_FLOW, 1)
        # Build attributes
        self._extra_attrs = {}
        self._extra_attrs[ATTR_SHOW_CONFIG] = self._zonedata.config.entity_id
        self._extra_attrs[ATTR_REMAINING] = self._zonedata.remaining_time.entity_id
        self._extra_attrs[ATTR_WATER] = self._zonedata.water.entity_id
        if self._zonedata.eco:
            self._extra_attrs[ATTR_WAIT] = self._zonedata.wait.entity_id
            self._extra_attrs[ATTR_REPEAT] = self._zonedata.repeat.entity_id
        self._extra_attrs[ATTR_NEXT_RUN] = self._zonedata.next_run.entity_id
        self._extra_attrs[ATTR_LAST_RAN] = self._zonedata.last_ran.entity_id
        self._extra_attrs["status"] = self._zonedata.status.entity_id
        self._extra_attrs[ATTR_ENABLE_ZONE] = self._zonedata.enabled.entity_id
        if self._zonedata.frequency is not None:
            self._extra_attrs[ATTR_RUN_FREQ] = self._zonedata.frequency.entity_id
        if self._zonedata.flow_sensor is not None:
            self._extra_attrs[ATTR_FLOW_SENSOR] = self._zonedata.flow_sensor
            self._extra_attrs[ATTR_HISTORICAL_FLOW] = self._hist_flow_rate
        if self._zonedata.adjustment is not None:
            self._extra_attrs[ATTR_WATER_ADJUST] = self._zonedata.adjustment
        if self._zonedata.water_source is not None:
            self._extra_attrs[ATTR_WATER_SOURCE] = self._zonedata.water_source
        if self._zonedata.rain_sensor is not None:
            self._extra_attrs[ATTR_RAIN_SENSOR] = self._zonedata.rain_sensor
        if self._zonedata.ignore_sensors is not None:
            self._extra_attrs[ATTR_IGNORE_SENSOR] = (
                self._zonedata.ignore_sensors.entity_id
            )
        self.async_schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if self._state == CONST_ON:
            return True
        return False

    @property
    def controller_type(self) -> str:
        """Controller type Rainbird Generic."""
        return self._programdata.controller_type

    @property
    def solenoid(self) -> str:
        """Zone solenoid Entity str."""
        return self._zonedata.zone

    @property
    def pump(self) -> str:
        """Pump solenoid Entity str."""
        return self._zonedata.pump

    @property
    def entity_type(self) -> str:
        """Switch or Valve."""
        return self._zonedata.type

    @property
    def measurement(self) -> str:
        """Switch or Valve."""
        return self._programdata.min_sec

    @property
    def water(self) -> NumberEntity:
        """Water entity number."""

        # allow seconds alongside minutes
        #self.measurement = "seconds"
        if self.measurement == "seconds":
            return int(self._zonedata.water.value)
        if self.measurement == "minutes":
            return int(self._zonedata.water.value) * 60

        return int(self._zonedata.water.value)

    @property
    def wait(self) -> NumberEntity:
        """Wait entity number."""
        if self._zonedata.wait:
            return int(self._zonedata.wait.value) * 60
        return 0

    @property
    def repeat(self) -> NumberEntity:
        """Repeat entity number."""
        if self._zonedata.repeat:
            return int(self._zonedata.repeat.value)
        return 1

    @property
    def frequency(self) -> SensorEntity:
        """Frequency entity select."""
        if self._zonedata.frequency:
            return self._zonedata.frequency.state
        return self._programdata.frequency.state

    @property
    def ignore_sensors(self) -> SwitchEntity:
        """Ignore rain sensor entity."""
        if self._zonedata.ignore_sensors:
            return self._zonedata.ignore_sensors.is_on
        return True

    @property
    def enabled(self) -> SwitchEntity:
        """Zone enabled entity bool."""
        return self._zonedata.enabled

    @property
    def status(self) -> SensorEntity:
        """Zone status sensor entity."""
        return self._zonedata.status

    @property
    def last_ran(self) -> SensorEntity:
        """Last ran entity time."""
        return self._zonedata.last_ran

    @property
    def remaining_time(self) -> SensorEntity:
        """Remaining time entity number."""
        return self._zonedata.remaining_time

    @property
    def rain_sensor(self) -> bool:
        """Raining value Bool."""
        if self._zonedata.rain_sensor:
            return self.hass.states.get(self._zonedata.rain_sensor).state
        return None

    @property
    def rain_behaviour(self) -> bool:
        """Raining value Bool."""
        return self._programdata.rain_behaviour

    @property
    def flow_sensor(self) -> float:
        """Flow rate value."""
        if self._zonedata.flow_sensor:
            flow = float(self.hass.states.get(self._zonedata.flow_sensor).state)
            if self._state == CONST_ON:
                return flow
            return self._hist_flow_rate
        return None

    @property
    def adjustment(self) -> float:
        """Adjustment value."""
        if self._zonedata.adjustment:
            return float(self.hass.states.get(self._zonedata.adjustment).state)
        return 1

    @property
    def water_source(self) -> bool:
        """Water Source value Bool."""
        if self._zonedata.water_source:
            return self.hass.states.get(self._zonedata.water_source).state
        return None

    @property
    def next_run(self) -> SensorEntity:
        """Next run entity time."""
        return self._zonedata.next_run

    @property
    def aborted(self):
        """Return the name of the variable."""
        return self._aborted

    async def prepare_to_run(self, scheduled=True):
        """Initialise the remaining time when the program is started."""

        self._scheduled = scheduled
        self._water_adjust_prior = self.adjustment
        self._remaining_time = await self.calc_run_time(
            repeats=self.repeat, scheduled=scheduled
        )
        await self.remaining_time.set_value(self._remaining_time)
        self._status = CONST_PENDING
        self._state = CONST_ON
        await self.status.set_value(self._status)
        self.async_schedule_update_ha_state()

    async def should_run(self, scheduled=True):
        """Determine if the zone should run."""

        if self.status.state in [
            CONST_DISABLED,
            CONST_PROGRAM_DISABLED,
            CONST_UNAVAILABLE,
            CONST_ADJUSTED_OFF,
            CONST_NO_WATER_SOURCE,
            CONST_RAINING,
            CONST_ZONE_DISABLED,
        ]:
            return False
        if not scheduled:
            return True
        if self.next_run.native_value > dt_util.as_local(dt_util.now()):
            return False

        return True

    # end should_run

    async def pause(self):
        """Pause the zone."""

        if self._status == CONST_PAUSED:
            if self._last_status == CONST_ON:
                await self.async_solenoid_turn_on()
                for _ in range(CONST_LATENCY):
                    if self.hass.states.get(self.solenoid).state in [
                        CONST_ON,
                        CONST_OPEN,
                    ]:
                        break
                    await asyncio.sleep(1)
            self._status = self._last_status
            await self.status.set_value(self._status)
        elif self._status in (CONST_ECO, CONST_ON, CONST_PENDING):
            self._last_status = self._status
            if self._last_status == CONST_ON:
                await self.async_solenoid_turn_off()
            self._status = CONST_PAUSED
            await self.status.set_value(self._status)
        self.async_schedule_update_ha_state()

    async def handle_validation_error(self):
        """Validate if any state change impacts the continued running."""

        while await self.next_run_validation() == CONST_PAUSED:
            # wait until the program is unpaused
            await asyncio.sleep(1)

        v_error = await self.next_run_validation()
        if v_error in (CONST_OFF, CONST_ON, CONST_PENDING, CONST_ECO):
            return v_error
        if (
            self._status in (CONST_ON, CONST_PENDING, CONST_ECO)
            and v_error == CONST_RAINING
        ):
            return self._status

        for _ in range(CONST_LATENCY):
            # allow for false readings/debounce
            v_error = await self.next_run_validation()
            if self._status in (CONST_ON, CONST_PENDING, CONST_ECO):
                # the zone is running so debounce
                await asyncio.sleep(1)
                continue
            # zone is not running so let the status change
            break

        if v_error in (CONST_PROGRAM_DISABLED, CONST_ZONE_DISABLED):
            self._stop = True

        if self._status in (CONST_ON, CONST_PENDING, CONST_ECO):
            if v_error in (CONST_NO_WATER_SOURCE):
                async_create(
                    self.hass,
                    message=f"No water source detected, {self.name} run terminated",
                    title="Irrigation Controller",
                )
                self._stop = True
                await self.async_turn_off_zone()
                await self.calc_next_run()
            if self._status in (CONST_UNAVAILABLE):
                async_create(
                    self.hass,
                    message=f"Switch has appears is offline, {self.name}",
                    title="Irrigation Controller",
                )
                self._stop = True
                await self.async_turn_off_zone()
            if v_error in (CONST_RAINING_STOP):
                async_create(
                    self.hass,
                    message=f"Rain has been detected, {self.name} run terminated",
                    title="Irrigation Controller",
                )
                self._stop = True
                await self.async_turn_off_zone()
        return v_error

    async def next_run_validation(self):
        """Validate the object readyness."""
        if self._programdata.switch.irrigation_on_value == CONST_OFF:
            return CONST_PROGRAM_DISABLED
        if self._programdata.pause.is_on:
            return CONST_PAUSED
        if await self.check_switch_state() is None:
            return CONST_UNAVAILABLE
        if self.water_source == CONST_OFF and not self.ignore_sensors:
            return CONST_NO_WATER_SOURCE
        if self.enabled.state == CONST_OFF:
            return CONST_ZONE_DISABLED
        if (
            self.rain_sensor == CONST_ON
            and not self.ignore_sensors
            and self.rain_behaviour == "continue"
        ):
            return CONST_RAINING
        if self.rain_sensor == CONST_ON and not self.ignore_sensors:
            return CONST_RAINING_STOP
        if self.adjustment <= 0 and not self.ignore_sensors:
            return CONST_ADJUSTED_OFF
        if self._status not in (CONST_ON, CONST_ECO, CONST_PENDING):
            return CONST_OFF
        return self._status

    def clean_up_string(self, data) -> list:
        """Remove spaces, new line, quotes and brackets."""
        return (
            data.replace(" ", "")
            .replace("\n", "")
            .replace("'", "")
            .replace('"', "")
            .strip("[]'")
            .split(",")
        )

    async def calc_next_run(self):
        """Determine when a zone will next attempt to run."""
        # something has changed recalculate the run time

        if self._status == CONST_PAUSED:
            v_error = await self.handle_validation_error()
            if v_error not in (CONST_OFF):
                # real issue reset the zone last status so reflected accurately after pause
                self._last_status = (
                    CONST_RAINING if v_error == CONST_RAINING_STOP else v_error
                )
            return

        if self._status == CONST_PENDING:
            await self.prepare_to_run(scheduled=True)
        if self._status in (CONST_ECO, CONST_ON, CONST_PENDING):
            # zone is running let the process run, debounce process
            return
        # check the sensor states
        v_error = await self.handle_validation_error()
        if v_error not in (CONST_OFF):
            # real issue reset the zone
            self._status = CONST_RAINING if v_error == CONST_RAINING_STOP else v_error
            await self.status.set_value(self._status)
            self._remaining_time = 0
            await self.remaining_time.set_value(self._remaining_time)
            return

        # it must be off
        await self.status.set_value(CONST_OFF)
        self._state = self._status = CONST_OFF
        self.async_schedule_update_ha_state()

        # now the state/status is sorted calc the next start
        string_times = self.clean_up_string(self._programdata.switch.start_time_value)
        string_times.sort()
        starttime = string_times[0]
        time = dt_util.as_local(dt_util.now()).strftime(TIME_STR_FORMAT)
        for stime in string_times:
            if stime > time:
                x = string_times.index(stime)
                starttime = string_times[x]
                break
        firststarttime = string_times[0]

        # the next time to run in a multi start config
        if starttime:
            starthour = int(starttime.split(":")[0])
            startmin = int(starttime.split(":")[1])
        else:
            starthour = 8
            startmin = 0
        # first run time in a multi start config
        if firststarttime:
            firststarthour = int(firststarttime.split(":")[0])
            firststartmin = int(firststarttime.split(":")[1])
        else:
            firststarthour = 8
            firststarthour = 0

        if self.last_ran.native_value is None:
            v_last_ran = dt_util.as_local(dt_util.now()) - timedelta(days=10)
        else:
            v_last_ran = self.last_ran.native_value.replace(
                hour=starthour, minute=startmin, second=00, microsecond=00
            )

        try:  # Frq is numeric
            if self.frequency is None:
                frq = 1
            else:
                frq = int(self.frequency)

            today_start_time = dt_util.as_local(dt_util.now()).replace(
                hour=starthour, minute=startmin, second=00, microsecond=00
            )
            today_begin = dt_util.as_local(dt_util.now()).replace(
                hour=00, minute=00, second=00, microsecond=00
            )
            last_ran_day_begin = v_last_ran.replace(
                hour=00, minute=00, second=00, microsecond=00
            )

            if (today_start_time - v_last_ran).total_seconds() / 86400 >= frq:
                # it has been sometime since the zone ran
                v_next_run = dt_util.as_local(dt_util.now()).replace(
                    hour=starthour, minute=startmin, second=00, microsecond=00
                )
                if today_start_time < dt_util.as_local(dt_util.now()):
                    v_next_run += timedelta(days=1)
            elif (
                today_start_time >= dt_util.as_local(dt_util.now())
                and last_ran_day_begin == today_begin
            ):
                # time is in the future and it previously ran today, supports multiple start times
                v_next_run = dt_util.as_local(dt_util.now()).replace(
                    hour=starthour, minute=startmin, second=00, microsecond=00
                )
            else:  # (today_start_time - last_ran).total_seconds()/86400 < frq:
                # frequency has not been satisfied
                # set last ran datetime to the first runtime of the series and add the frequency
                v_next_run = v_last_ran.replace(
                    hour=firststarthour, minute=firststartmin, second=00, microsecond=00
                ) + timedelta(days=frq)
        except ValueError:
            # Frq is days of week
            string_freq = self.frequency
            string_freq = self.clean_up_string(self.frequency)
            v_last_ran = dt_util.as_local(dt_util.now()).replace(
                hour=starthour, minute=startmin, second=00, microsecond=00
            )
            today = v_last_ran.isoweekday()
            v_next_run = v_last_ran + timedelta(days=100)  # arbitary max
            for day in string_freq:
                # try:
                if self.get_weekday(day) == today and v_last_ran > dt_util.as_local(
                    dt_util.now()
                ):
                    v_next_run = v_last_ran
                else:
                    v_next_run = min(
                        self.get_next_dayofweek_datetime(v_last_ran, day), v_next_run
                    )

        await self.next_run.set_value(v_next_run)
        if self._state not in (CONST_PENDING, CONST_ON, CONST_ECO, CONST_OFF):
            self._state = CONST_OFF
            await self.status.set_value(CONST_OFF)
        return

    def get_weekday(self, day):
        """Determine weekday num."""
        return VALID_DAYS.index(day) + 1

    def get_next_dayofweek_datetime(self, date_time, dayofweek):
        """Next date for the given day."""
        start_time_w = date_time.isoweekday()
        target_w = self.get_weekday(dayofweek)
        if start_time_w < target_w:
            day_diff = target_w - start_time_w
        else:
            day_diff = 7 - (start_time_w - target_w)
        return date_time + timedelta(days=day_diff)

    async def check_switch_state(self):
        """Check the solenoid switch/valve state."""
        # wait a few seconds if offline it may come back
        for _ in range(CONST_LATENCY):
            # latency check if it has gone offline for a short period
            if self.hass.states.get(self.solenoid).state in [CONST_OFF, CONST_CLOSED]:
                return False
            if self.hass.states.get(self.solenoid).state in [CONST_ON, CONST_OPEN]:
                return True
            await asyncio.sleep(1)
        return None

    async def async_solenoid_turn_on(self):
        """Turn on the zone."""
        if await self.check_switch_state() is False:
            if self.controller_type == RAINBIRD:
                # RAINBIRD controller requires a different service call
                duration = await self.calc_run_time(
                    repeats=self.repeat, scheduled=self.scheduled
                )
                await self.hass.services.async_call(
                    RAINBIRD,
                    RAINBIRD_TURN_ON,
                    {
                        ATTR_ENTITY_ID: self.solenoid,
                        RAINBIRD_DURATION: duration,
                    },
                )
            elif self.controller_type == BHYVE:
                # B-Hyve controller requires a different service call
                duration = await self.calc_run_time(
                    repeats=self.repeat, scheduled=self.scheduled
                )
                await self.hass.services.async_call(
                    BHYVE,
                    BHYVE_TURN_ON,
                    {
                        ATTR_ENTITY_ID: self.solenoid,
                        BHYVE_DURATION: duration,
                    },
                )
            elif self.entity_type == CONST_VALVE:
                # valve
                await self.hass.services.async_call(
                    CONST_VALVE, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: self.solenoid}
                )
            else:
                # switch
                await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self.solenoid}
                )

            event_data = {
                "action": "zone_turned_on",
                "device_id": self.solenoid,
                "pump": self.pump,
                "scheduled": self._scheduled,
                "zone": self.name,
                "runtime": self._remaining_time,
                "water": self.water,
                "wait": self.wait,
                "repeat": self.repeat,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)

    async def async_solenoid_turn_off(self):
        """Turn on the zone."""
        # is it a valve or a switch
        if self.entity_type == CONST_VALVE:
            # postion entity defined get the value
            await self.hass.services.async_call(
                CONST_VALVE, SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: self.solenoid}
            )
        else:
            await self.hass.services.async_call(
                CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self.solenoid}
            )
        # raise an event
        state = CONST_OFF
        if self._status == CONST_ECO:
            state = CONST_ECO
        else:
            state = CONST_ABORTED
        event_data = {
            "action": "zone_turned_off",
            "device_id": self.solenoid,
            "zone": self.name,
            "state": state,
        }
        self.hass.bus.async_fire("irrigation_event", event_data)

    async def async_eco_turn_off(self):
        """Signal the zone to stop."""
        self._status = CONST_ECO
        await self.async_solenoid_turn_off()
        await self.status.set_value(self._status)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self._programdata.switch.entity_toggle_zone(self._zonedata)

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return self._extra_attrs

    async def async_turn_off(self, **kwargs):
        """Toggle the entity."""
        await self._programdata.switch.entity_toggle_zone(self._zonedata)

    async def async_turn_off_zone(self, **kwargs):
        """Turn the entity off."""
        if self.flow_sensor and self._state == CONST_ON:
            self._extra_attrs[ATTR_HISTORICAL_FLOW] = self.flow_sensor
            self._hist_flow_rate = self.flow_sensor

        await self.async_solenoid_turn_off()
        self._remaining_time = 0
        await self.remaining_time.set_value(self._remaining_time)
        if self._status in (CONST_PENDING, CONST_ECO, CONST_ON):
            await self.status.set_value(CONST_OFF)
        self._state = CONST_OFF
        self._status = CONST_OFF
        self._stop = True
        self.async_schedule_update_ha_state()

    async def set_scheduled(self, scheduled: bool):
        """Set the scheduled state."""
        self._scheduled = scheduled

    @property
    def scheduled(self) -> bool:
        """Set the scheduled state."""
        return self._scheduled

    async def calc_run_time(
        self, seconds_run=0, volume_delivered=0, repeats=1, scheduled=True
    ):
        """Update the run time component."""
        wait = self.wait

        if self.ignore_sensors:
            adjust = 1
        else:
            adjust = self._water_adjust_prior

        if self.flow_sensor is None:
            # time based
            #            water = self.water * 60
            water = self.water
            run_time = (water * adjust * repeats) + (wait * (repeats - 1))
        else:
            # volume based/flow sensor
            water = self.water  # volume
            flow = self.flow_sensor  # flow rate
            if flow == 0:
                return 999
            delivery_volume = water * adjust
            if volume_delivered > 0:  # the cycle has started
                remaining_volume = (
                    (delivery_volume * (repeats - 1))
                    + delivery_volume
                    - volume_delivered
                )
            else:
                remaining_volume = delivery_volume * repeats

            watertime = remaining_volume / flow * 60
            # remaining watering time + remaining waits
            run_time = watertime + (wait * (repeats - 1))
        # set the program attribute
        return math.ceil(run_time - seconds_run)

    async def latency_check(self, state):
        """Ensure switch has turned off/on as expected and warn, state = true for on."""

        for _ in range(CONST_LATENCY):
            if await self.check_switch_state() is not state:
                # if not the expected state loop again
                await asyncio.sleep(1)
            else:
                return True
        if not self._stop:
            async_create(
                self.hass,
                message=f"Switch has latency exceeding {CONST_LATENCY} seconds, cannot confirm {self.name} state",
                title="Irrigation Controller",
            )

        return False

    async def async_turn_on(self, **kwargs):
        """Start the zone watering cycle."""
        # Zone is multistate so starting from here is not useful
        # this function is here explicitly handle the turn on function
        await self._programdata.switch.entity_toggle_zone(self._zonedata)

    async def async_turn_on_from_program(self, **kwargs):
        """Start the zone watering cycle."""

        self._status = CONST_ON
        await self.status.set_value(CONST_ON)
        self._state = CONST_ON
        self.async_schedule_update_ha_state()
        self._stop = False
        self._aborted = False

        if self.ignore_sensors:
            water_adjust_value = 1
        else:
            water_adjust_value = self._water_adjust_prior

        last_ran = dt_util.as_local(dt_util.now())

        # run the watering cycle, water/wait/repeat
        for reps in range(self.repeat, 0, -1):
            seconds_run = 0
            # run time adjusted to 0 skip this zone
            if int(self.remaining_time.numeric_value) <= 0:
                continue
            self._status = CONST_ON
            await self.status.set_value(self._status)
            if await self.check_switch_state() is False and self._stop is False:
                await self.async_solenoid_turn_on()
                for _ in range(CONST_LATENCY):
                    self._stop = True
                    if self._status == CONST_PAUSED:
                        self._stop = False
                        break
                    if await self.check_switch_state() is not True:
                        # if not the expected state loop again
                        await asyncio.sleep(1)
                        continue
                    self._stop = False
                    break
            # track the watering
            if self.flow_sensor is not None:
                await self.volume(water_adjust_value, reps)
            else:
                seconds_run = await self.time(water_adjust_value, seconds_run, reps)
            # abort
            if self._stop:
                self._aborted = True
                break
            # wait cycle
            if self.wait > 0 and reps > 1:
                await self.async_eco_turn_off()
                for _ in range(self.wait):
                    seconds_run += 1
                    self._remaining_time = await self.calc_run_time(
                        seconds_run, repeats=reps, scheduled=self.scheduled
                    )
                    await self.remaining_time.set_value(self._remaining_time)
                    if self._stop:
                        self._aborted = True
                        break
                    await asyncio.sleep(1)
            # abort
            if self._stop:
                self._aborted = True
                break
        # End of repeat loop
        self._scheduled = False

        if not self._aborted:
            await self.last_ran.set_state(last_ran)
        await self.async_turn_off_zone()

    async def time(self, water_adjust_value, seconds_run, reps):
        """Track watering time based on time."""

        if self._stop:
            return 0
        #        watertime = math.ceil(self.water * 60 * water_adjust_value)
        watertime = math.ceil(self.water * water_adjust_value)
        while watertime > 0:
            if self._status == CONST_PAUSED:
                await asyncio.sleep(1)
                continue
            seconds_run += 1
            #            watertime = math.ceil(self.water * 60 * water_adjust_value) - seconds_run
            watertime = math.ceil(self.water * water_adjust_value) - seconds_run
            self._remaining_time = await self.calc_run_time(
                seconds_run, repeats=reps, scheduled=self.scheduled
            )
            await self.remaining_time.set_value(self._remaining_time)
            if self._stop:
                break
            await asyncio.sleep(1)

            # Check to see if the zone has been stopped
            for _ in range(CONST_LATENCY):
                if self._status == CONST_PAUSED:
                    self._stop = False
                    self._aborted = False
                    break

                self._stop = True
                self._aborted = True
                if (
                    await self.check_switch_state() is not True
                    and self._status != CONST_PAUSED
                ):
                    # if not on loop again
                    await asyncio.sleep(1)
                    continue
                self._stop = False
                self._aborted = False
                break

        return seconds_run

    async def volume(self, water_adjust_value, reps):
        """Track watering time based on volume."""
        if self._stop:
            return
        volume_remaining = self.water * water_adjust_value
        volume_delivered = 0
        zeroflowcount = 0
        while volume_remaining > 0:
            if await self.next_run_validation() == CONST_PAUSED:
                await asyncio.sleep(1)
                continue
            if self._stop:
                break
            volume_delivered += self.flow_sensor / 60
            volume_required = self.water * water_adjust_value
            volume_remaining = volume_required - volume_delivered
            self._remaining_time = await self.calc_run_time(
                volume_delivered=volume_delivered,
                repeats=reps,
                scheduled=self.scheduled,
            )

            await self.remaining_time.set_value(self._remaining_time)

            await asyncio.sleep(1)
            # Check to see if the zone has been stopped
            for _ in range(CONST_LATENCY):
                self._stop = True
                self._aborted = True
                if (
                    await self.check_switch_state() is not True
                    and self._status != CONST_PAUSED
                ):
                    # if not on loop again
                    await asyncio.sleep(1)
                else:
                    self._stop = False
                    self._aborted = False
                    break
            # flow sensor has failed
            if self.flow_sensor == 0:
                zeroflowcount += 1
                if zeroflowcount > CONST_ZERO_FLOW_DELAY:
                    if self.flow_sensor == 0:
                        self._aborted = True
                        async_create(
                            self.hass,
                            message=f"No flow detected, {self.name} abandoned",
                            title="Irrigation Controller",
                        )
                    break
            else:
                zeroflowcount = 0
