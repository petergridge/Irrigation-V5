"""Switch entity definition."""

import asyncio
import logging

from homeassistant.components.persistent_notification import async_create
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry as MyConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from . import IrrigationData
from .const import CONST_START_LATENCY
from .program import IrrigationProgram
from .zone import Zone

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. from config flow."""
    data: IrrigationData = config_entry.runtime_data
    name = config_entry.runtime_data.program.name
    unique_id = config_entry.entry_id
    switches = []
    programs = []

    # for Program
    switch = EnableProgram(unique_id, name)
    config_entry.runtime_data.program.enabled = switch
    switches.append(switch)
    switch = ProgramConfig(unique_id, name)
    config_entry.runtime_data.program.config = switch
    switches.append(switch)
    switch = ProgramPause(unique_id, name)
    config_entry.runtime_data.program.pause = switch
    switches.append(switch)
    if config_entry.runtime_data.program.rain_delay_on:
        switch = EnableRainDelay(unique_id, name)
        config_entry.runtime_data.program.rain_delay = switch
        switches.append(switch)

    zones = data.zone_data
    for i, zone in enumerate(zones):
        # check if the switch is ready
        for _ in range(CONST_START_LATENCY):
            if not hass.states.async_available(zone.zone):
                friendly_name = hass.states.get(zone.zone).attributes.get(
                    "friendly_name"
                )
                break
            await asyncio.sleep(1)
        else:
            msg = f"{zone.zone} has not initialised before irrigation program, check your configuration."
            _LOGGER.error(msg)
            async_create(
                hass,
                message=msg,
                title="Irrigation Controller",
                notification_id="irrigation_device_error",
            )

        friendly_name = hass.states.get(zone.zone).attributes.get("friendly_name")
        z_name = zone.name
        if zone.rain_sensor or zone.adjustment or zone.water_source:
            switch = IgnoreRainSensor(unique_id, name, z_name)
            switches.append(switch)
            config_entry.runtime_data.zone_data[i].ignore_sensors = switch

        switch = EnableZone(unique_id, name, z_name)
        config_entry.runtime_data.zone_data[i].enabled = switch
        switches.append(switch)

        switch = ZoneConfig(unique_id, name, z_name)
        config_entry.runtime_data.zone_data[i].config = switch
        switches.append(switch)

        switch = Zone(unique_id, name, z_name, friendly_name, zone, data.program)
        config_entry.runtime_data.zone_data[i].switch = switch
        switches.append(switch)
    async_add_entities(switches)

    # add program after switch as program references the switches
    program = IrrigationProgram(hass, unique_id, name, data)
    config_entry.runtime_data.program.switch = program
    programs.append(program)
    async_add_entities(programs)


class ProgramConfig(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "config"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, name) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_{name}_config")
        self._attr_attribution = f"Irrigation Controller: {name}"
        self._state = "off"
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._state = "off"
        else:
            self._state = last_state.state
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == "on":
            return True
        return False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        # self._state = not self._state

        if self._state == "on":
            self._state = "off"
        else:
            self._state = "on"
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = "on"
        self.async_schedule_update_ha_state()


class ProgramPause(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "pause"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, name) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_{name}_pause")
        self._attr_attribution = f"Irrigation Controller: {name}"
        self._state = "off"
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        self._state = "off"

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == "on":
            return True
        return False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        # self._state = not self._state

        if self._state == "on":
            self._state = "off"
        else:
            self._state = "on"
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = "on"
        self.async_schedule_update_ha_state()


class ZoneConfig(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "config"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, pname, name) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_{name}_config")
        self._attr_attribution = f"Irrigation Controller: {pname}, {name}"
        self._state = "off"
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._state = "off"
        else:
            self._state = last_state.state

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == "on":
            return True
        return False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        # self._state = not self._state

        if self._state == "on":
            self._state = "off"
        else:
            self._state = "on"
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = "on"
        self.async_schedule_update_ha_state()


class IgnoreRainSensor(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "ignore_sensor"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, pname, name) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_{name}_ignore_sensors")
        self._attr_attribution = f"Irrigation Controller: {pname}, {name}"
        self._state = "off"
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._state = "off"
        else:
            self._state = last_state.state

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == "on":
            return True
        return False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        # self._state = not self._state

        if self._state == "on":
            self._state = "off"
        else:
            self._state = "on"
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.async_schedule_update_ha_state()
        self._state = "on"


class EnableProgram(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "enable_program"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, pname) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_enable_program")
        self._attr_attribution = f"Irrigation Controller: {pname}"
        self._state = False
        self._pname = pname
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._state = "off"
        else:
            self._state = last_state.state

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == "on":
            return True
        return False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        # self._state = not self._state

        if self._state == "on":
            self._state = "off"
        else:
            self._state = "on"
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = "on"
        self.async_schedule_update_ha_state()


class EnableZone(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "enable_zone"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, pname, zname) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_{zname}_enable_zone")
        self._attr_attribution = f"Irrigation Controller: {pname}, {zname}"
        self._state = False
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._state = True
        else:
            self._state = False
            if last_state.state == "on":
                self._state = True

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        self._state = not self._state
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = False
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = True
        self.async_schedule_update_ha_state()


class EnableRainDelay(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "enable_rain_delay"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id, name) -> None:
        """Initialize a Irrigation program."""
        self._attr_unique_id = slugify(f"{unique_id}_enable_rain_delay")
        self._attr_attribution = f"Irrigation Controller: {name}"
        self._state = "off"
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._state = "off"
        else:
            self._state = last_state.state
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._state == "on":
            return True
        return False

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        # self._state = not self._state

        if self._state == "on":
            self._state = "off"
        else:
            self._state = "on"
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = "on"
        self.async_schedule_update_ha_state()
