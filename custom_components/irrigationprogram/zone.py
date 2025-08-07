"""Zone definition."""

import asyncio
from datetime import timedelta
import logging
import math

from homeassistant.components.number import NumberEntity
from homeassistant.components.persistent_notification import async_create, async_dismiss
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
    ATTR_DEFAULT_RUN_TIME,
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
        self._rain_stop_count = 0
        self._source_stop_count = 0
        self._remaining_time = 0
        self._default_run_time = 0
        self._state = CONST_OFF  # switch state
        self._status = CONST_OFF  # zone run status
        self._last_status = None
        self._stop = False
        self._aborted = True
        self._scheduled = False
        self._hist_flow_rate = 1
        self._water_adjust_prior = 1
        self._zone_manual_start = False
        self._latency = programdata.latency
        self._pump_on_delay = 0

    async def async_added_to_hass(self):
        """Run when HA starts."""
        last_state = await self.async_get_last_state()
        self._hist_flow_rate = 1
        if last_state:
            self._hist_flow_rate = last_state.attributes.get(ATTR_HISTORICAL_FLOW, 1)
        # Build attributes
        self._extra_attrs = {}
        self._extra_attrs[ATTR_SHOW_CONFIG] = self._zonedata.config.entity_id
        self._extra_attrs[ATTR_DEFAULT_RUN_TIME] = (
            self._zonedata.default_run_time.entity_id
        )
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
        if self._zonedata.watering_type == "volume":
            self._extra_attrs[ATTR_FLOW_SENSOR] = self._programdata.flow_sensor
            self._extra_attrs[ATTR_HISTORICAL_FLOW] = self._hist_flow_rate
        if self._zonedata.adjustment is not None:
            self._extra_attrs[ATTR_WATER_ADJUST] = self._zonedata.adjustment
        if self._programdata.water_source is not None:
            self._extra_attrs[ATTR_WATER_SOURCE] = self._programdata.water_source
        if self._zonedata.rain_sensor is not None:
            self._extra_attrs[ATTR_RAIN_SENSOR] = self._zonedata.rain_sensor
        if self._zonedata.ignore_sensors is not None:
            self._extra_attrs[ATTR_IGNORE_SENSOR] = (
                self._zonedata.ignore_sensors.entity_id
            )
        self.calc_default_run_time()
        self.async_schedule_update_ha_state()
        # on reload/restart ensure the zone is off
        await self.async_solenoid_turn_off()

    @property
    def start_pump(self) -> bool:
        """Return true if switch is on."""
        return False

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
        return self._programdata.pump

    @property
    def pump_on_delay(self) -> int:
        """Delay to start pump before(-) or after(+) zone starts."""
        return int(self._programdata.pump_delay)  # self._pump_on_delay

    @property
    def entity_type(self) -> str:
        """Switch or Valve."""
        return self._zonedata.type

    @property
    def measurement(self) -> str:
        """Switch or Valve."""
        return self._programdata.min_sec

    @property
    def watering_type(self) -> str:
        """Time or volume."""
        if self._zonedata.watering_type:
            return self._zonedata.watering_type
        return "time"

    @property
    def water(self) -> NumberEntity:
        """Water entity number."""
        # allow seconds alongside minutes
        if self.watering_type == "volume":
            return int(self._zonedata.water.value)

        if self.measurement == "seconds":
            return int(self._zonedata.water.value)
        if self.measurement == "minutes":
            return int(self._zonedata.water.value) * 60

        return int(self._zonedata.water.value)

    @property
    def wait(self) -> NumberEntity:
        """Wait entity number."""
        if self._zonedata.wait:
            if self.measurement == "seconds":
                return int(self._zonedata.wait.value)
            if self.measurement == "minutes":
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
        # manage the impact of the rain delay on frequency
        delay = 0
        if self._programdata.rain_delay:
            if self._programdata.rain_delay.state == CONST_ON:
                delay = int(self._programdata.rain_delay_days.state)

        if self._zonedata.frequency:
            frq = self._zonedata.frequency.current_option
            if frq == "unknown":
                frq = self._programdata.freq_options[0]
            if frq.isnumeric():
                return int(frq) + delay
            return self._zonedata.frequency.state

        if self._programdata.frequency:
            frq = self._programdata.frequency.current_option
            if frq.split(".")[0] == "sensor":
                return self.hass.states.get(frq).state
            if frq == "unknown":
                frq = "1"  # self._programdata.freq_options[0]
            if frq.isnumeric():
                return int(frq) + delay

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
    def default_run_time(self) -> SensorEntity:
        """Last ran entity time."""
        return self._default_run_time

    @property
    def remaining_time(self) -> SensorEntity:
        """Remaining time entity number."""
        return self._zonedata.remaining_time

    @property
    def rain_behaviour(self) -> bool:
        """Raining value Bool."""
        return self._programdata.rain_behaviour

    @property
    def flow_sensor(self) -> float:
        """Flow rate value."""
        if self._programdata.flow_sensor:
            try:
                flow = float(self.hass.states.get(self._programdata.flow_sensor).state)
                if self._state == CONST_ON:
                    return flow
            except AttributeError:
                return None
            except ValueError:
                return self._hist_flow_rate
            return self._hist_flow_rate
        return None

    @property
    def rain_sensor(self) -> bool:
        """Raining value Bool."""
        if self._zonedata.rain_sensor:
            try:
                return self.hass.states.get(self._zonedata.rain_sensor).state
            except AttributeError:
                # rain sensor is not available
                return False
            except ValueError:
                return False
        return None

    @property
    def adjustment(self) -> float:
        """Adjustment value."""
        if self._zonedata.adjustment:
            try:
                return float(self.hass.states.get(self._zonedata.adjustment).state)
            except AttributeError:
                return 1
            except ValueError:
                return 1
        return 1

    @property
    def water_source(self) -> bool:
        """Water Source value Bool."""
        if self._programdata.water_source:
            try:
                return self.hass.states.get(self._programdata.water_source).state
            except AttributeError:
                return None
            except ValueError:
                return None
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
            repeats_remaining=self.repeat, scheduled=scheduled
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
            CONST_UNAVAILABLE,
            CONST_ADJUSTED_OFF,
            CONST_NO_WATER_SOURCE,
            CONST_RAINING,
        ]:
            return False

        # Zone is diabled and not started from the zone (from the program)
        if self.status.state in [CONST_ZONE_DISABLED] and not self._zone_manual_start:
            return False

        # A manual start
        if not scheduled:
            return True

        # lastly check the scheduled run time
        if self.next_run.native_value:
            if self.next_run.native_value > dt_util.as_local(dt_util.now()):
                return False
        else:
            # report an issue
            _LOGGER.debug(
                "No next run calculated for %s. Your frequency may not be set correctly",
                self.name,
            )
            async_dismiss(self.hass, "irrigation_frequency")
            async_create(
                self.hass,
                message=f"No next run calculated for {self.name}. Your frequency may not be set correctly",
                title="Irrigation Controller",
                notification_id="irrigation_frequency",
            )

        # turn off the rain delay feature
        if self._programdata.rain_delay:
            await self._programdata.rain_delay.async_turn_off()
            return True

        return True

    # end should_run

    async def check_switch_state(self):
        """Check the solenoid switch/valve state."""
        if self.hass.states.get(self.solenoid).state in [
            CONST_OFF,
            CONST_CLOSED,
        ]:
            return False, self.hass.states.get(self.solenoid).state
        if self.hass.states.get(self.solenoid).state in [CONST_ON, CONST_OPEN]:
            return True, self.hass.states.get(self.solenoid).state

        return None, self.hass.states.get(self.solenoid).state

    async def check_is_on(self):
        """Ensure the switch has turned on."""
        for _ in range(self._latency):
            if self._aborted:
                break
            if self._status == CONST_PAUSED:
                break
            # try to turn the switch on again
            # this is an attempt to handle zigbee/bluetooth devices that sleep
            await asyncio.sleep(1)
            check_state, value = await self.check_switch_state()
            if check_state is not True:
                # if not the expected state loop again
                await self.async_solenoid_turn_on()
                continue
            break
        else:
            _LOGGER.debug(
                "Switch has latency exceeding %s seconds, cannot confirm %s state is ON",
                self._latency,
                self.name,
            )
            event_data = {
                "action": "error",
                "error": "Switch cannot be confirmed as ON",
                "device_id": self.entity_id,
                "scheduled": self._scheduled,
                "program": self.name,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)

    async def check_is_off(self):
        """Ensure the switch is off."""
        for _ in range(self._latency):
            if self._aborted:
                break
            if self._status == CONST_PAUSED:
                self._stop = False
                break
            # try to turn the switch on again
            # this is an attempt to handle zigbee devices that sleep
            await asyncio.sleep(1)
            check_state, value = await self.check_switch_state()
            if check_state is not False:
                # if not the expected state loop again
                await self.async_solenoid_turn_off()
                continue
            break
        else:
            _LOGGER.debug(
                "Switch has latency exceeding %s seconds, cannot confirm %s state is OFF",
                self._latency,
                self.name,
            )
            async_dismiss(self.hass, "irrigation_latency")
            async_create(
                self.hass,
                message=f"Switch has latency exceeding {self._latency} seconds, cannot confirm {self.name} state is off.",
                title="Irrigation Controller",
                notification_id="irrigation_latency",
            )
            event_data = {
                "action": "error",
                "error": "Switch can not be confirmed as OFF",
                "device_id": self.entity_id,
                "scheduled": self._scheduled,
                "program": self.name,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)

    async def toggle_pause(self):
        """Pause the zone."""
        if self._status == CONST_PAUSED:
            if self._last_status == CONST_ON:
                await self.async_solenoid_turn_on()
                await self.check_is_on()
            self._status = self._last_status
            await self.status.set_value(self._status)
        elif self._status in (CONST_ECO, CONST_ON, CONST_PENDING):
            self._last_status = self._status
            self._status = CONST_PAUSED
            if self._last_status == CONST_ON:
                if self.pump:
                    event_data = {
                        "action": "turn_off_pump",
                        "device_id": self.solenoid,
                        "pump": self.pump,
                        "program": self._programdata.switch.entity_id,
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)
                    await asyncio.sleep(3)
                await self.async_solenoid_turn_off()
                await self.check_is_off()
            await self.status.set_value(self._status)
        self.async_schedule_update_ha_state()

    async def handle_state_change(self):
        """Validate if any state change impacts the continued running."""

        while await self.get_status() == CONST_PAUSED:
            # wait until the program is unpaused
            await asyncio.sleep(1)

        status = await self.get_status()
        if status in (CONST_OFF, CONST_ON, CONST_PENDING, CONST_ECO):
            return status

        if self._status in (CONST_ON, CONST_PENDING, CONST_ECO, CONST_PROGRAM_DISABLED):
            if status == CONST_RAINING:
                # rain option to continue
                return self._status
            if status == CONST_RAINING_STOP:
                event_data = {
                    "action": "error",
                    "error": "Rain has been detected",
                    "device_id": self.entity_id,
                    "scheduled": self._scheduled,
                    "program": self.name,
                }
                self.hass.bus.async_fire("irrigation_event", event_data)

                # rain option to stop
                _LOGGER.debug("Rain has been detected, %s terminated", self.name)
                async_dismiss(self.hass, "irrigation_rain_detected")
                async_create(
                    self.hass,
                    message=f"Rain has been detected, {self.name} terminated",
                    title="Irrigation Controller",
                    notification_id="irrigation_rain_detected",
                )
                self._stop = True
                self._aborted = True

            if status in (CONST_NO_WATER_SOURCE):
                # No water source, sensor is off
                _LOGGER.debug(
                    "No water source detected, %s terminated",
                    self.name,
                )
                async_dismiss(self.hass, "irrigation_water_source")
                async_create(
                    self.hass,
                    message=f"No water source detected, {self.name} terminated.",
                    title="Irrigation Controller",
                    notification_id="irrigation_water_source",
                )
                event_data = {
                    "action": "error",
                    "error": "No water source detected",
                    "device_id": self.entity_id,
                    "scheduled": self._scheduled,
                    "program": self.name,
                }
                self.hass.bus.async_fire("irrigation_event", event_data)
                self._stop = True
                self._aborted = True

        return status

    async def get_status(self):
        """Validate the object readyness."""

        if self.enabled.state == CONST_OFF:
            status = CONST_ZONE_DISABLED
        elif not self._programdata.enabled.is_on:
            status = CONST_PROGRAM_DISABLED
        elif self._programdata.pause.is_on:
            status = CONST_PAUSED

        elif self.water_source == CONST_OFF:
            status = CONST_NO_WATER_SOURCE
        elif (
            self.rain_sensor == CONST_ON
            and not self.ignore_sensors
            and self.rain_behaviour == "continue"
        ):
            status = CONST_RAINING
        elif self.rain_sensor == CONST_ON and not self.ignore_sensors:
            status = CONST_RAINING_STOP
        elif self.adjustment <= 0 and not self.ignore_sensors:
            status = CONST_ADJUSTED_OFF
        elif self._status not in (CONST_ON, CONST_ECO, CONST_PENDING):
            status = CONST_OFF
        else:
            status = self._status

        check_state, value = await self.check_switch_state()
        if check_state is None:
            status = CONST_UNAVAILABLE

        return status

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
        if self._status in (CONST_ECO, CONST_ON, CONST_PENDING):
            # zone is running no need to recalc next run until it has completed
            return

        if self._status == CONST_PAUSED:
            status = await self.handle_state_change()
            if status not in (CONST_OFF):
                # reset the zone last status so reflected accurately after pause
                self._last_status = (
                    CONST_RAINING if status == CONST_RAINING_STOP else status
                )
            return

        if self._status == CONST_PENDING:
            await self.prepare_to_run(scheduled=True)

        # check the sensor states
        status = await self.handle_state_change()
        if status not in (CONST_OFF):
            # real issue reset the zone
            self._status = CONST_RAINING if status == CONST_RAINING_STOP else status
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
            firststartmin = 0

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
                number_as_float = float(self.frequency)
                frq = int(number_as_float)

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
                if self.get_weekday(day) == today and v_last_ran > dt_util.as_local(
                    dt_util.now()
                ):
                    v_next_run = v_last_ran
                else:
                    v_next_run = min(
                        self.get_next_dayofweek_datetime(v_last_ran, day), v_next_run
                    )
        if v_next_run is None:
            _LOGGER.debug(
                "No next run calculated for %s. Your frequency may not be set correctly",
                self.name,
            )
            async_dismiss(self.hass, "irrigation_frequency")
            async_create(
                self.hass,
                message=f"No next run calculated for {self.name}. Your frequency may not be set correctly",
                title="Irrigation Controller",
                notification_id="irrigation_frequency",
            )

        await self.next_run.set_value(v_next_run)
        if self._state not in (CONST_PENDING, CONST_ON, CONST_ECO, CONST_OFF):
            self._state = CONST_OFF
            await self.status.set_value(CONST_OFF)
        return

    def get_weekday(self, day):
        """Determine weekday num."""
        try:
            return VALID_DAYS.index(day) + 1
        except ValueError:
            # put a persistent error up
            # frquency sensor does not contain valid values
            _LOGGER.debug(
                "Frequency sensor, %s, value is not valid",
                self._zonedata.frequency.current_option,
            )
            async_dismiss(self.hass, "irrigation_frequency")
            async_create(
                self.hass,
                message=f"Frequency sensor, {self._zonedata.frequency.current_option}, value is not valid.",
                title="Irrigation Controller",
                notification_id="irrigation_frequency",
            )

    def get_next_dayofweek_datetime(self, date_time, dayofweek):
        """Next date for the given day."""
        start_time_w = date_time.isoweekday()
        target_w = self.get_weekday(dayofweek)
        if start_time_w < target_w:
            day_diff = target_w - start_time_w
        else:
            day_diff = 7 - (start_time_w - target_w)
        return date_time + timedelta(days=day_diff)

    async def async_solenoid_turn_on(self):
        """Turn on the zone."""

        if self.pump_on_delay < 0 and self.pump:
            # start the pump before the zone starts
            event_data = {
                "action": "turn_on_pump",
                "device_id": self.solenoid,
                "pump": self.pump,
                "program": self._programdata.switch.entity_id,
                "delay": 0,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)
            await asyncio.sleep(abs(self.pump_on_delay))

        if self.pump_on_delay >= 0 and self.pump:
            # turn the pump on after the zone starts
            event_data = {
                "action": "turn_on_pump",
                "device_id": self.solenoid,
                "pump": self.pump,
                "program": self._programdata.switch.entity_id,
                "delay": self.pump_on_delay,
            }
            self.hass.bus.async_fire("irrigation_event", event_data)

        check_state, value = await self.check_switch_state()
        if check_state is False:
            if self.controller_type == RAINBIRD:
                # RAINBIRD controller requires a different service call
                duration = await self.calc_run_time(
                    repeats_remaining=self.repeat, scheduled=self.scheduled
                )

                duration = math.ceil(duration / 60)

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
                    repeats_remaining=self.repeat, scheduled=self.scheduled
                )

                duration = math.ceil(duration / 60)

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
        if self.controller_type == BHYVE:
            await self.hass.services.async_call(
                BHYVE, "stop_watering", {ATTR_ENTITY_ID: self.solenoid}
            )
        elif self.entity_type == CONST_VALVE:
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
        check_state, value = await self.check_switch_state()
        if check_state is False:
            # check the switch has actually turned off
            pass

    async def async_eco_turn_off(self):
        """Signal the zone to stop."""
        self._status = CONST_ECO
        await self.async_solenoid_turn_off()
        await self.check_is_off()
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
        self._aborted = True
        await self.async_turn_off_zone()

    async def async_turn_off_zone(self, **kwargs):
        """Turn the entity off."""
        if self.flow_sensor and self._state == CONST_ON:
            self._extra_attrs[ATTR_HISTORICAL_FLOW] = self.flow_sensor
            self._hist_flow_rate = self.flow_sensor

        await self.async_solenoid_turn_off()
        await self.check_is_off()

        self._remaining_time = 0
        await self.remaining_time.set_value(self._remaining_time)
        if self._status in (CONST_PENDING, CONST_ECO, CONST_ON, CONST_PAUSED):
            await self.status.set_value(CONST_OFF)
        self._state = CONST_OFF
        self._status = CONST_OFF
        self._stop = True
        self._zone_manual_start = False

        self.async_schedule_update_ha_state()

    async def set_scheduled(self, scheduled: bool):
        """Set the scheduled state."""
        self._scheduled = scheduled

    @property
    def scheduled(self) -> bool:
        """Set the scheduled state."""
        return self._scheduled

    def calc_default_run_time(self):
        """Update the run time component."""
        if CONST_OFF in (self.enabled.state, self.water_source):
            self._default_run_time = 0
            self._zonedata.default_run_time.set_value(self._default_run_time)
            return 0

        wait = self.wait
        if self.ignore_sensors:
            adjust = 1
        else:
            adjust = self.adjustment
            if self.rain_sensor == CONST_ON:
                self._default_run_time = 0
                self._zonedata.default_run_time.set_value(self._default_run_time)
                return 0

        if self.watering_type == "time":
            water = self.water
            run_time = (water * adjust * self.repeat) + (wait * (self.repeat - 1))
        else:
            # volume based/flow sensor
            water = self.water  # volume
            flow = self.flow_sensor  # flow rate
            if flow == 0:
                self._default_run_time = 999
                self._zonedata.default_run_time.set_value(self._default_run_time)
                return 999
            remaining_volume = water * adjust * self.repeat
            watertime = remaining_volume / flow * 60
            run_time = watertime + (wait * (self.repeat - 1))

        # set the zone attribute
        if math.ceil(run_time) < 0:
            self._default_run_time = 0
            self._zonedata.default_run_time.set_value(self._default_run_time)
            return 0
        self._default_run_time = math.ceil(run_time)
        self._zonedata.default_run_time.set_value(self._default_run_time)
        return math.ceil(run_time)

    async def calc_run_time(
        self, seconds_run=0, volume_delivered=0, repeats_remaining=1, scheduled=True
    ):
        """Update the run time component."""
        if self.ignore_sensors:
            adjust = 1
        else:
            adjust = self._water_adjust_prior

        if self.flow_sensor is None:
            run_time = (self.water * adjust * repeats_remaining) + (
                self.wait * (repeats_remaining - 1)
            )
        else:
            # volume based/flow sensor
            if self.flow_sensor == 0:
                return 999
            delivery_volume = self.water * adjust
            if volume_delivered > 0:  # the cycle has started
                remaining_volume = (
                    (delivery_volume * (repeats_remaining - 1))
                    + delivery_volume
                    - volume_delivered
                )
            else:
                remaining_volume = delivery_volume * repeats_remaining

            watertime = remaining_volume / self.flow_sensor * 60
            # remaining watering time + remaining waits
            run_time = watertime + (self.wait * (repeats_remaining - 1))

        # set the program attribute
        if math.ceil(run_time - seconds_run) < 0:
            return 0

        return math.ceil(run_time - seconds_run)

    async def async_turn_on(self, **kwargs):
        """Start the zone watering cycle."""
        check_state, value = await self.check_switch_state()
        if check_state is not True:
            self._zone_manual_start = True
            await self._programdata.switch.entity_toggle_zone(self._zonedata)

    async def async_turn_on_from_program(self, last=None):
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
            volume_delivered = 0
            # run time adjusted to 0 skip this zone
            if int(self.remaining_time.numeric_value) <= 0:
                continue
            self._status = CONST_ON
            await self.status.set_value(self._status)

            # abort
            if self._stop:
                break
            # track the watering

            if self.flow_sensor is not None:
                volume_delivered = await self.volume(water_adjust_value, reps, last)
            else:
                seconds_run = await self.time(
                    water_adjust_value, seconds_run, reps, last
                )
            # abort
            if self._stop:
                break

            # wait cycle
            if self.wait > 0 and reps > 1:
                if self.pump:
                    event_data = {
                        "action": "turn_off_pump",
                        "device_id": self.solenoid,
                        "pump": self.pump,
                        "program": self._programdata.switch.entity_id,
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)
                    await asyncio.sleep(3)
                await self.async_eco_turn_off()
                for x in range(self.wait, 0, -1):
                    seconds_run += 1
                    self._remaining_time = await self.calc_run_time(
                        seconds_run=seconds_run,
                        volume_delivered=volume_delivered,
                        repeats_remaining=reps,
                        scheduled=self.scheduled,
                    )
                    await self.remaining_time.set_value(self._remaining_time)
                    if self._stop:
                        break
                    # -- if pump and on_delay < 0:
                    # -- start the pump
                    if (
                        self.pump
                        and self.pump_on_delay < 0
                        and x < abs(self.pump_on_delay)
                    ):
                        event_data = {
                            "action": "turn_on_pump",
                            "device_id": self.solenoid,
                            "pump": self.pump,
                            "program": self._programdata.switch.entity_id,
                            "delay": 0,
                        }
                        self.hass.bus.async_fire("irrigation_event", event_data)
                    await asyncio.sleep(1)

            # abort
            if self._stop:
                break
        # End of repeat loop
        self._scheduled = False

        # update last ran only on successful commpletion
        if not self._aborted:
            await self.last_ran.set_state(last_ran)
        await self.async_turn_off_zone()

    async def time(self, water_adjust_value, seconds_run, reps, last=None):
        """Track watering time based on time."""
        warning_issued = False
        if self._scheduled:
            if await self.get_status() not in (
                CONST_ON,
                CONST_RAINING,
            ):
                self._stop = True
                self._aborted = True

        if self._stop:
            return 0

        await self.async_solenoid_turn_on()

        watertime = math.ceil(self.water * water_adjust_value)
        start_time = dt_util.now()
        end_time = dt_util.now() + timedelta(seconds=watertime)

        while dt_util.now() < end_time:
            # -- if pump turn off when 3 seconds remaining
            time_difference = (end_time - dt_util.now()).total_seconds()
            if time_difference <= 3 and self.pump and last:
                event_data = {
                    "action": "turn_off_pump",
                    "device_id": self.solenoid,
                    "pump": self.pump,
                    "program": self._programdata.switch.entity_id,
                }
                self.hass.bus.async_fire("irrigation_event", event_data)

            if self._status == CONST_PAUSED:
                # now I need to add time to the expected end time
                end_time += timedelta(seconds=1)
                await asyncio.sleep(1)
                continue

            # checkif one of the sensors (water source, rain) has changed that needs the zone to stop
            await self.handle_state_change()
            if self._stop:
                return 0

            # Check to see if the zone has been stopped, this is abnormal
            for _ in range(self._latency):
                seconds_run = (dt_util.now() - start_time).total_seconds()
                self._remaining_time = await self.calc_run_time(
                    seconds_run,
                    volume_delivered=0,
                    repeats_remaining=reps,
                    scheduled=self.scheduled,
                )

                await self.remaining_time.set_value(self._remaining_time)
                if self._aborted:
                    break
                # check the switch, rain and water source
                await asyncio.sleep(1)
                status = await self.get_status()
                if status not in (CONST_ON, CONST_RAINING):
                    continue
                check_state, value = await self.check_switch_state()
                if not check_state:
                    # if not on loop again
                    status = value
                    continue
                break
            else:
                if not warning_issued:
                    _LOGGER.debug(
                        "%s returned an unexpected state, %s for %s consecutive checks",
                        self.name,
                        status,
                        self._latency,
                    )
                warning_issued = True
                event_data = {
                    "action": "error",
                    "error": "Returned an unexpected state",
                    "device_id": self.entity_id,
                    "scheduled": self._scheduled,
                    "program": self.name,
                    "state": status,
                }
                self.hass.bus.async_fire("irrigation_event", event_data)

        return seconds_run

    async def volume(self, water_adjust_value, reps, last=None):
        """Track watering time based on volume."""

        warning_issued = False
        await asyncio.sleep(0)

        if self._scheduled:
            if await self.get_status() not in (
                CONST_ON,
                CONST_RAINING,
            ):
                self._stop = True
                self._aborted = True
        if self._stop:
            return 0

        await self.async_solenoid_turn_on()

        volume_remaining = self.water * water_adjust_value
        volume_delivered = 0
        zeroflowcount = 0
        while volume_remaining > 0:
            if self._status == CONST_PAUSED:
                await asyncio.sleep(1)
                continue

            # check if one of the sensors (water source, rain) has changed that needs the zone to stop
            await self.handle_state_change()

            if self._stop:
                break

            # Check to see if the zone is not on, this is abnormal
            for _ in range(self._latency):
                volume_delivered += self.flow_sensor / 60
                volume_required = self.water * water_adjust_value
                volume_remaining = volume_required - volume_delivered
                self._remaining_time = await self.calc_run_time(
                    volume_delivered=volume_delivered,
                    repeats_remaining=reps,
                    scheduled=self.scheduled,
                )
                await self.remaining_time.set_value(self._remaining_time)

                # -- turn of pump if < 3 seconds remaining
                if self._remaining_time <= 3 and self.pump and last:
                    event_data = {
                        "action": "turn_off_pump",
                        "device_id": self.solenoid,
                        "pump": self.pump,
                        "program": self._programdata.switch.entity_id,
                    }
                    self.hass.bus.async_fire("irrigation_event", event_data)

                if volume_remaining < 0:
                    break
                if self._aborted:
                    break
                # check the switch, rain and water source
                await asyncio.sleep(1)
                status = await self.get_status()
                if status not in (CONST_ON, CONST_RAINING):
                    continue
                check_state, value = await self.check_switch_state()
                if not check_state:
                    # if not on loop again
                    status = value
                    continue
                break
            else:
                if not warning_issued:
                    _LOGGER.debug(
                        "%s returned an unexpected state, %s for %s consecutive checks",
                        self.name,
                        status,
                        self._latency,
                    )
                warning_issued = True
                event_data = {
                    "action": "error",
                    "error": "Returned an unexpected state",
                    "device_id": self.entity_id,
                    "scheduled": self._scheduled,
                    "program": self.name,
                    "state": status,
                }
                self.hass.bus.async_fire("irrigation_event", event_data)

            # If no flow for 5 cycles, shut off, possible flow sensor has failed
            if self.flow_sensor == 0:
                zeroflowcount += 1
                if zeroflowcount > CONST_ZERO_FLOW_DELAY:
                    if self.flow_sensor == 0:
                        self._stop = True
                        self._aborted = True
                        _LOGGER.debug("No flow detected, %s terminated", self.name)
                        async_dismiss(self.hass, "irrigation_no_flow")
                        async_create(
                            self.hass,
                            message=f"No flow detected, {self.name} terminated.",
                            title="Irrigation Controller",
                            notification_id="irrigation_no_flow",
                        )
                        event_data = {
                            "action": "error",
                            "error": "No flow detected",
                            "device_id": self.entity_id,
                            "scheduled": self._scheduled,
                            "program": self.name,
                        }
                        self.hass.bus.async_fire("irrigation_event", event_data)
                        self._stop = True
                        self._aborted = True
                    break
            else:
                zeroflowcount = 0
        return volume_delivered
