"""Platform for recording current irrigation zone status."""

from datetime import UTC, datetime, time
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from . import IrrigationData
from .const import (
    CONST_ADJUSTED_OFF,
    CONST_CLOSED,
    CONST_CONTROLLER_DISABLED,
    CONST_DISABLED,
    CONST_ECO,
    CONST_NO_WATER_SOURCE,
    CONST_OFF,
    CONST_ON,
    CONST_OPEN,
    CONST_PENDING,
    CONST_PROGRAM_DISABLED,
    CONST_RAINING,
    CONST_UNAVAILABLE,
    CONST_ZONE_DISABLED,
)
from .globals import PROGRAMS, ZONES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow."""

    data: IrrigationData = config_entry.runtime_data
    unique_id = config_entry.entry_id
    pname = config_entry.runtime_data.program.name

    sensors = []
    sensor = RemainingTime(hass, pname, unique_id)
    sensors.append(sensor)
    config_entry.runtime_data.program.remaining_time = sensor

    sensor = DefaultRunTime(hass, pname, unique_id)
    sensors.append(sensor)
    config_entry.runtime_data.program.default_run_time = sensor

    sensor = DelayTime(hass, pname, unique_id)
    sensors.append(sensor)
    config_entry.runtime_data.program.delay_time = sensor

    zones = data.zone_data
    for i, zone in enumerate(zones):
        zname = zone.name

        sensor = ZoneStatus(hass, pname, zname, unique_id)
        sensors.append(sensor)
        config_entry.runtime_data.zone_data[i].status = sensor

        sensor = ZoneNextRun(hass, pname, zname, unique_id)
        sensors.append(sensor)
        config_entry.runtime_data.zone_data[i].next_run = sensor

        sensor = ZoneLastRan(hass, pname, zname, unique_id)
        sensors.append(sensor)
        config_entry.runtime_data.zone_data[i].last_ran = sensor

        sensor = ZoneRemainingTime(hass, pname, zname, unique_id)
        sensors.append(sensor)
        config_entry.runtime_data.zone_data[i].remaining_time = sensor

        sensor = ZoneDefaultRunTime(hass, pname, zname, unique_id)
        sensors.append(sensor)
        config_entry.runtime_data.zone_data[i].default_run_time = sensor

    async_add_entities(sensors)


class ZoneStatus(SensorEntity):
    """Rain factor class defn."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "zone_status"

    def __init__(  # noqa: D107
        self, hass: HomeAssistant, pname, zone, unique_id
    ) -> None:
        self._state = "off"
        self._uuid = slugify(f"{unique_id}_{zone}_status")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone}"
        self._pname = pname
        self._zname = zone

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        zonename = self._pname+'.'+self._zname
        x = ZONES.get(zonename)
        if x is None:
            return
        await self.set_value(x.status_sensor_value)

    async def set_value(self, status=CONST_OFF):
        """Set the runtime state value."""
        self._state = status
        self.async_schedule_update_ha_state()

    @property
    def options(self):
        """Return the sensor state options."""
        return [
            CONST_ADJUSTED_OFF,
            CONST_CLOSED,
            CONST_CONTROLLER_DISABLED,
            CONST_DISABLED,
            CONST_ECO,
            CONST_NO_WATER_SOURCE,
            CONST_OFF,
            CONST_ON,
            CONST_OPEN,
            CONST_PENDING,
            CONST_PROGRAM_DISABLED,
            CONST_RAINING,
            CONST_UNAVAILABLE,
            CONST_ZONE_DISABLED,
            "paused",
        ]

    @property
    def friendly_name(self):
        """Return a unique_id for this entity."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state


class ZoneNextRun(SensorEntity):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "zone_next_run"

    def __init__(self, hass: HomeAssistant, pname, zone, unique_id) -> None:
        """Init."""
        self._state:datetime = dt_util.as_local(dt_util.now())
        self._uuid = slugify(f"{unique_id}_{zone}_next_run")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone}"
        self._pname = pname
        self._zname = zone

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        zonename = self._pname+'.'+self._zname
        x = ZONES.get(zonename)
         # Get the property object from the class
        if x and type(x.next_run_value) is datetime:
            self._state = x.next_run_value
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self) -> datetime:
        """Return the state."""
        return self._state


class ZoneLastRan(RestoreSensor):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "zone_last_ran"

    def __init__(self, hass: HomeAssistant, pname, zone, unique_id) -> None:
        """Init."""
        self._state = None
        self._uuid = slugify(f"{unique_id}_{zone}_last_ran")
        self._localtimezone = ZoneInfo(hass.config.time_zone)
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone}"
        self._pname = pname
        self._zname = zone

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_sensor_data()
        if last_state:
            self._state = last_state.native_value

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        zonename = self._pname+'.'+self._zname
        x = ZONES.get(zonename)
         # Get the property object from the class
        if x and type(x.last_run_value) is datetime:
            self._state = x.last_run_value
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state


class ZoneRemainingTime(SensorEntity):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "remaining_time"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, hass: HomeAssistant, pname, zone, unique_id) -> None:
        """Init."""
        self._state: time = time(hour=0, minute=0, second=0)
        self._uuid = slugify(f"{unique_id}_{zone}_remaining_time")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone}"
        self._pname = pname
        self._zname = zone

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        zonename = self._pname+'.'+self._zname
        x = ZONES.get(zonename)
        if x is None:
            return
        await self.set_value(x.remaining_time_value)

    async def set_value(self, value):
        """Set the remaining time state value."""
        # convert seconds to datetime
        minute, second = divmod(value, 60)
        hour, minute = divmod(minute, 60)
        if value / 60 / 60 / 24 >= 1:
            rem = time(hour=23, minute=59, second=59)
        else:
            rem = time(hour=hour, minute=minute, second=second)
        self._state = rem
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state

    @property
    def numeric_value(self):
        """Return the state."""
        return self._state.hour * 3600 + self._state.minute * 60 + self._state.second


class ZoneDefaultRunTime(SensorEntity):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "default_run_time"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, hass: HomeAssistant, pname, zone, unique_id) -> None:
        """Init."""
        self._state: time = time(hour=0, minute=0, second=0)
        self._uuid = slugify(f"{unique_id}_{zone}_default_run_time")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone}"
        self._pname = pname
        self._zname = zone

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        zonename = self._pname+'.'+self._zname
        x = ZONES.get(zonename)
        if x is None:
            return
        await self.set_value(x.default_run_time)

    async def set_value(self, value):
        """Set the remaining time state value."""
        # convert seconds to datetime
        minute, second = divmod(value, 60)
        hour, minute = divmod(minute, 60)
        if value / 60 / 60 / 24 >= 1:
            rem = time(hour=23, minute=59, second=59)
        else:
            rem = time(hour=hour, minute=minute, second=second)
        self._state = rem
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state

    @property
    def numeric_value(self):
        """Return the state."""
        return self._state.hour * 3600 + self._state.minute * 60 + self._state.second


class RemainingTime(SensorEntity):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "remaining_time"
    _attr_attribution = "Irrigation Controller"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, hass: HomeAssistant, pname, unique_id) -> None:
        """Init."""
        self._state: time = time(hour=0, minute=0, second=0)
        self._uuid = slugify(f"{unique_id}_remaining_time")
        self._attr_attribution = f"Irrigation Controller: {pname}"
        self._pname = pname

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        x = PROGRAMS.get(self._pname)
        if x is None:
            return
        await self.set_value(x.remaining_time_value)

    async def set_value(self, value):
        """Set the runtime state value."""
        # convert seconds to datetime
        minute, second = divmod(value, 60)
        hour, minute = divmod(minute, 60)
        if value / 60 / 60 / 24 >= 1:
            rem = time(hour=23, minute=59, second=59)
        else:
            rem = time(hour=max(0,hour), minute=max(0,minute), second=max(0,second))
        self._state = rem
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state

    @property
    def numeric_value(self):
        """Return the state."""
        return self._state.hour * 3600 + self._state.minute * 60 + self._state.second


class DefaultRunTime(SensorEntity):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "default_run_time"
    _attr_attribution = "Irrigation Controller"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, hass: HomeAssistant, pname, unique_id) -> None:
        """Init."""
        self._state: time = time(hour=0, minute=0, second=0)
        self._uuid = slugify(f"{unique_id}_default_run_time")
        self._attr_attribution = f"Irrigation Controller: {pname}"
        self._pname = pname

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        x = PROGRAMS.get(self._pname)
        if x is None:
            return
        await self.set_value(x.default_run_time_value)

    async def set_value(self, value):
        """Set the runtime state value."""
        # convert seconds to datetime
        minute, second = divmod(value, 60)
        hour, minute = divmod(minute, 60)
        if value / 60 / 60 / 24 >= 1:
            rem = time(hour=23, minute=59, second=59)
        else:
            rem = time(hour=max(0,hour), minute=max(0,minute), second=max(0,second))
        self._state = rem
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state

    @property
    def numeric_value(self):
        """Return the state."""
        return self._state.hour * 3600 + self._state.minute * 60 + self._state.second


class DelayTime(RestoreSensor):
    """Next zone run date time class defn."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "delay_time"
    _attr_attribution = "Irrigation Controller"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, hass: HomeAssistant, pname, unique_id) -> None:
        """Init."""
        self._state = None
        self._uuid = slugify(f"{unique_id}_delay_time")
        self._localtimezone = ZoneInfo(hass.config.time_zone)
        self._attr_attribution = f"Irrigation Controller: {pname}"
        self._pname = pname

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_sensor_data()
        if last_state:
            self._state = last_state.native_value

    async def async_update(self):
        """Triggered on update freq."""
        #get the value from the program/zone
        x = PROGRAMS.get(self._pname)
         # Get the property object from the class
        if x and type(x.delay_time_value) is datetime:
            self._state = x.delay_time_value
        self.async_schedule_update_ha_state()



    async def set_value(self):
        """Set the runtime state value."""
        self._state = datetime.now(UTC)
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid

    @property
    def native_value(self):
        """Return the state."""
        return self._state
