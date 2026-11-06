

import logging

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from . import IrrigationProgram

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow."""

    unique_id = config_entry.entry_id
    p:IrrigationProgram = config_entry.runtime_data.program

    entities = []
    if p.start_type == 'multistart':
        sensor=RunTimes(unique_id,p.name)
        entities.append (sensor)
        config_entry.runtime_data.program.start_time = sensor
        async_add_entities(entities)

class RunTimes(TextEntity,RestoreEntity):

    translation_key='start_times'
    has_entity_name=True
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, unique_id,pname):
        self._attr_unique_id = slugify(f'{unique_id}_start_times')
        self._attr_attribution = f'Irrigation Controller: {pname}'
        self._attr_pattern = '(([0-2][0-9]:[0-5][0-9]:[0-5][0-9])(?:,|$)){1,10}'
        self._current_value = None
        self._default_value = '06:00:00,18:00:00'

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        if last_state is None:
            self._current_value =  self._default_value
        else:
            self._current_value = last_state.state

    @property
    def native_value(self):
        """Return value."""
        return self._current_value

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        self._current_value = value
        self.async_write_ha_state()
