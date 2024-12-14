
import datetime as py_datetime
import logging

import voluptuous as vol

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util, slugify

from . import IrrigationProgram

FMT_TIME = "%H:%M:%S"
CONF_HAS_DATE = "has_date"
CONF_HAS_TIME = "has_time"
CONF_INITIAL = "initial"
DEFAULT_TIME = py_datetime.time(0, 0, 0)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry. form config flow."""
    p:IrrigationProgram = config_entry.runtime_data.program

    unique_id = config_entry.entry_id
    entities = []
    if p.start_type != 'multistart':
        sensor = starttime(unique_id,p.name)
        entities.append (sensor)
        config_entry.runtime_data.program.start_time = sensor
    async_add_entities(entities)

def parse_initial_datetime(initial) -> py_datetime.datetime:
    """Check the initial value is valid."""

    if (time := dt_util.parse_time(initial)) is not None:
        return py_datetime.datetime.combine(py_datetime.date.today(), time)
    raise vol.Invalid(f"Initial value '{initial}' can't be parsed as a time")


class starttime(TimeEntity,RestoreEntity):

    _attr_has_entity_name = True
    _attr_translation_key ='start_time'
    _unrecorded_attributes = frozenset({MATCH_ALL})


    def __init__(self, unique_id,pname):
        self._attr_unique_id   = slugify(f'{unique_id}_start_time')
        self._native_value     = None
        self._current_datetime = None
        self._attr_attribution = f'Irrigation Controller: {pname}'

    async def async_added_to_hass(self):
        """HA has started."""
        last_state = await self.async_get_last_state()
        datetime = dt_util.as_local(dt_util.utc_from_timestamp(py_datetime.datetime.now().timestamp()))
        date = datetime.date()
        time = datetime.time()
        self._current_datetime = py_datetime.datetime.combine(
                    date, time, dt_util.get_default_time_zone()
                ).time().replace(second=00,microsecond=00)
        if last_state:
            if last_state.state != 'unknown':
                last_time = py_datetime.datetime.strptime(last_state.state,"%H:%M:%S")
                current_datetime = parse_initial_datetime(last_time.time().replace(second=00,microsecond=00))

            # If the user passed in an initial value with a timezone, convert it to right tz
            if current_datetime.tzinfo is not None:
                self._current_datetime = current_datetime.astimezone(
                    dt_util.get_default_time_zone().replace(second=00, microsecond=00)
                ).time()
            else:
                self._current_datetime = current_datetime.replace(
                    tzinfo=dt_util.get_default_time_zone(),second=00, microsecond=00
                ).time()

    @property
    def native_value(self):
        return self._current_datetime

    async def async_set_value(self, value):
        self._current_datetime = value
        self.async_write_ha_state()
