"""Platform for recording current irrigation zone status."""
from datetime import datetime
import logging

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    ATTR_ZONE,
    ATTR_ZONES,
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

_LOGGER = logging.getLogger(__name__)

async def _async_create_entities(hass: HomeAssistant, config, unique_id):

    sensors = []
    #append multiple sensors
    for zone in config.get(ATTR_ZONES):
        status = ZoneStatus(hass,config.get(CONF_NAME),zone.get(ATTR_ZONE).split(".")[1],unique_id)
        sensors.append(status)
        nextrun = ZoneNextRun(hass,config.get(CONF_NAME),zone.get(ATTR_ZONE).split(".")[1],unique_id)
        sensors.append(nextrun)
    return sensors

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow."""

    unique_id = config_entry.entry_id
    if config_entry.options != {}:
        config = config_entry.options
    else:
        config = config_entry.data

    async_add_entities(await _async_create_entities(hass, config, unique_id))
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_zone_status",
        {
            vol.Required('status'): str,
        },
        "set_zone_status",
    )
    platform.async_register_entity_service(
        "set_zone_next_run",
        {
            vol.Required('status'): datetime,
        },
        "set_zone_next_run",
    )

class ZoneStatus(SensorEntity):
    '''Rain factor class defn.'''

    def __init__(  # noqa: D107
        self,
        hass: HomeAssistant,
        program,
        zone,
        unique_id
    ) -> None:

        self._state             = 'off'
        self._uuid              = slugify(f'{unique_id}_{zone}_status')
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_has_entity_name = True
        self._attr_name = slugify(f'{program}_{zone}_status')
        self._attr_should_poll = False
        self._attr_translation_key = 'zonestatus'

    async def set_zone_status(self, status='off'):
        '''Set the runtime state value.'''
        self._state = status
        self.async_schedule_update_ha_state()

    @property
    def options(self):
        """Return the sensor state options."""
        return  [
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
            CONST_ZONE_DISABLED
            ]

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid
    @property
    def native_value(self):
        """Return the state."""
        return self._state

class ZoneNextRun(SensorEntity):
    '''Next zone run date time class defn.'''

    def __init__(  # noqa: D107
        self,
        hass: HomeAssistant,
        program,
        zone,
        unique_id
    ) -> None:

        self._state             = None #datetime.now()
        self._uuid              = slugify(f'{unique_id}_{zone}_next_run')
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_has_entity_name = True
        self._attr_name = slugify(f'{program}_{zone}_next_run')
        self._attr_should_poll = False

    async def set_zone_next_run(self, status=None):
        '''Set the runtime state value.'''
        self._state = status
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._uuid
    @property
    def native_value(self):
        """Return the state."""
        return self._state
