''' __init__'''

from __future__ import annotations

from ctypes.wintypes import BOOL
import logging
from homeassistant.util import slugify

# -----------Helpers---------------------------
#from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    SERVICE_TURN_OFF,
#    SERVICE_TURN_ON,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant,callback
from homeassistant.helpers.config_validation import string
#from homeassistant.helpers.typing import ConfigType
from homeassistant import config_entries

from .const import (
    DOMAIN,
    SWITCH_ID_FORMAT,
    CONST_SWITCH,
    )

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up irrigtest from a config entry."""
    # store an object for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = {ATTR_NAME:entry.data.get(ATTR_NAME)}
    hass.config_entries.async_setup_platforms(entry, (Platform.SWITCH,))
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True

async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    #figure out how to remove the generated helpers
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, (Platform.SWITCH,)
    ):
        #clean up any related helpers
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_setup(hass, config):
    '''setup the irrigation'''

    async def async_stop_programs(call):
        ''' stop all running programs'''
        for data in hass.data[DOMAIN].values():
            if data.get(ATTR_NAME) == call.data.get("ignore", ""):
                continue
            device = SWITCH_ID_FORMAT.format(slugify(data.get(ATTR_NAME)))
            data = {ATTR_ENTITY_ID: device}
            await hass.services.async_call(CONST_SWITCH, SERVICE_TURN_OFF, data)
    # END async_stop_switches

    # register services
    hass.services.async_register(DOMAIN, "stop_programs", async_stop_programs)

    #import YAML to config entries
    irrig_config = {}
    hass.data.setdefault(DOMAIN, {})
    platforms = config.get(CONST_SWITCH)
    # build list of yaml definitions
    for domain in platforms:
        if domain.get("platform") == DOMAIN:
            irrig_config = domain.get("switches")
            break
    # process each yaml irrigation program
    for item in irrig_config.items():
        irrig_input = {}
        irrig_input[CONF_NAME]=item[0]
        irrig_input.update(item[1])
        #check if this config has already been imported
        if _async_find_matching_config_entry(hass,irrig_input[CONF_NAME]) is False:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=irrig_input,
                )
            )
    return True

@callback
def _async_find_matching_config_entry(
    hass: HomeAssistant, name
) -> BOOL:
    '''determine if a config has been imported from YAML'''
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_NAME) == name:
            return True
    return False
