import logging

from homeassistant.components.number import NumberDeviceClass, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import IrrigationData, IrrigationProgram
from .const import CONST_DELAY_OFFSET, CONST_SUN_OFFSET

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow."""
    unique_id = config_entry.entry_id
    data: IrrigationData = config_entry.runtime_data
    p: IrrigationProgram = config_entry.runtime_data.program
    sensors = []

    if p.rain_delay_on:
        sensor = InputNumberProgram(
            unique_id,
            p.name,
            "rain_delay_days",
            "days",
            10,
            0,
            1,
        )
        sensors.append(sensor)
        config_entry.runtime_data.program.rain_delay_days = sensor

    # Inter Zone Delay for program
    if p.zone_count > 1 and p.parallel == 1:
        sensor = InputNumberProgram(
            unique_id,
            p.name,
            "inter_zone_delay",
            "sec",
            p.zone_delay_max,
            CONST_DELAY_OFFSET,
            1,
        )
        sensors.append(sensor)
        config_entry.runtime_data.program.inter_zone_delay = sensor

    if p.start_type == "sunrise":
        sensor = InputNumberProgram(
            unique_id,
            p.name,
            "sunrise_offset",
            "min",
            CONST_SUN_OFFSET,
            -CONST_SUN_OFFSET,
            30,
        )
        sensors.append(sensor)
        config_entry.runtime_data.program.sunrise_offset = sensor

    elif p.start_type == "sunset":
        sensor = InputNumberProgram(
            unique_id,
            p.name,
            "sunset_offset",
            "min",
            CONST_SUN_OFFSET,
            -CONST_SUN_OFFSET,
            30,
        )
        sensors.append(sensor)
        config_entry.runtime_data.program.sunset_offset = sensor

    zones = data.zone_data
    for i, zone in enumerate(zones):
        sensor = Water(
            unique_id,
            p.name,
            zone.name,
            p.flow_sensor,
            p.water_max,
            p.water_step,
            p.min_sec,
        )

        sensors.append(sensor)
        config_entry.runtime_data.zone_data[i].water = sensor
        if zone.eco:
            sensor = Wait(unique_id, p.name, zone.name, p.min_sec)
            sensors.append(sensor)
            config_entry.runtime_data.zone_data[i].wait = sensor

            sensor = Repeat(unique_id, p.name, zone.name)
            sensors.append(sensor)
            config_entry.runtime_data.zone_data[i].repeat = sensor

    async_add_entities(sensors)


class InputNumberProgram(RestoreNumber):
    _attr_has_entity_name = True
    _attr_editable = True
    _attr_mode = "slider"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self, unique_id, pname, translation_key, unit_of_measure, max, min, step
    ):
        self._attr_unique_id = slugify(f"{unique_id}_{translation_key}")
        self._attr_attribution = f"Irrigation Controller: {pname}"

        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit_of_measure
        self._attr_native_min_value = min
        self._attr_native_max_value = max
        self._attr_native_step = step

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_number_data()

        if last_state is not None:
            await self.async_set_native_value(last_state.native_value)
        else:
            await self.async_set_native_value(0)

    @property
    def native_value(self):
        return self._attr_native_value

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()


class Water(RestoreNumber):
    _attr_has_entity_name = True
    _attr_editable = True
    _attr_mode = "slider"

    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        unique_id,
        pname,
        zone_name,
        flow_sensor=None,
        water_max=1,
        step=30,
        min_sec="minutes",
    ):
        self._attr_unique_id = slugify(f"{unique_id}_{zone_name}_water")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone_name}"
        self._attr_native_max_value = water_max
        self._attr_native_step = step
        self._attr_native_min_value = step
        if flow_sensor:
            self._attr_device_class = NumberDeviceClass.VOLUME
            self._attr_native_unit_of_measurement = "L"
            self._attr_translation_key = "volume"
        else:
            if min_sec == "seconds":
                self._attr_native_unit_of_measurement = "s"
            if min_sec == "minutes":
                self._attr_native_unit_of_measurement = "min"
            self._attr_device_class = NumberDeviceClass.DURATION
            self._attr_translation_key = "water"

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_number_data()
        if last_state is not None:
            await self.async_set_native_value(last_state.native_value)
        else:
            await self.async_set_native_value(1)

    @property
    def native_value(self):
        return self._attr_native_value

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()


class Wait(RestoreNumber):
    _attr_has_entity_name = True
    _attr_editable = True
    _attr_mode = "slider"
    _attr_native_min_value = 1
    _attr_native_step = 1
    _attr_translation_key = "wait"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, pname, zone_name, min_sec="minutes"):
        self._attr_unique_id = slugify(f"{unique_id}_{zone_name}_wait")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone_name}"
        self._attr_device_class = NumberDeviceClass.DURATION
        if min_sec == "seconds":
            self._attr_native_max_value = 120
            self._attr_native_unit_of_measurement = "s"
        else:
            self._attr_native_unit_of_measurement = "min"
            self._attr_native_max_value = 10

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_number_data()
        if last_state is not None:
            await self.async_set_native_value(last_state.native_value)
        else:
            await self.async_set_native_value(1)

    @property
    def native_value(self):
        return self._attr_native_value

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()


class Repeat(RestoreNumber):
    _attr_has_entity_name = True
    _attr_editable = True
    _attr_mode = "slider"
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_translation_key = "repeat"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, pname, zone_name):
        self._attr_unique_id = slugify(f"{unique_id}_{zone_name}_repeat")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zone_name}"
        self._attr_native_unit_of_measurement = "reps"

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_number_data()
        if last_state is not None:
            await self.async_set_native_value(last_state.native_value)
        else:
            await self.async_set_native_value(1)

    @property
    def native_value(self):
        return self._attr_native_value

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()
