''' __init__'''

from __future__ import annotations
from ctypes.wintypes import BOOL
import logging
from homeassistant.util import slugify
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    SERVICE_TURN_OFF,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant,callback
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

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            entry, Platform.SWITCH
        )
    )

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True

async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    #clean up any related helpers
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, (Platform.SWITCH,)
    ):
        return unload_ok

async def async_setup(hass:HomeAssistant, config):
    '''setup the irrigation'''

    async def async_stop_programs(call):
        ''' stop all running programs'''

        for data in hass.data[DOMAIN].values():
            if data.get(ATTR_NAME) == call.data.get("ignore", ""):
                await asyncio.sleep(1)
                continue
            device = SWITCH_ID_FORMAT.format(slugify(data.get(ATTR_NAME)))
            servicedata = {ATTR_ENTITY_ID: device}

            #warn if the program is terminated by a service call
            if hass.states.get(device).state == "on":
                if call.data.get("ignore", ""):
                    _LOGGER.warning("Irrigation Program '%s' terminated by '%s'", data.get(ATTR_NAME), call.data.get("ignore", "") )
                else:
                    _LOGGER.warning("Irrigation Program '%s' terminated ", data.get(ATTR_NAME))
                await hass.services.async_call(CONST_SWITCH, SERVICE_TURN_OFF, servicedata)

    # END async_stop_switches
    # register service
    hass.services.async_register(DOMAIN, "stop_programs", async_stop_programs)

    #import YAML to config entries
    irrig_config = {}
    hass.data.setdefault(DOMAIN, {})
    platforms = config.get(CONST_SWITCH)
    # build list of yaml definitions
    if platforms:
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

#async def async_migrate_entry(hass:HomeAssistant, config_entry: ConfigEntry):
#    """Migrate old entry."""
#    _LOGGER.debug("Migrating from version %s", config_entry.version)

#---- REVERT to UI based impementation ----#

# uncomment this when removing old group method and inputs
#    if config_entry.version == 1:
#        if config_entry.options == {}:
#            new = config_entry.data
#        else:
#            new = config_entry.options
#        if ATTR_GROUPS in new:
#            #new grouping model implemented
#            for zonecount, zone in enumerate(new[ATTR_ZONES]):
#                if ATTR_ZONE_GROUP in zone:
#                    #delete old grouping method
#                    new[ATTR_ZONES][zonecount].pop(ATTR_ZONE_GROUP)
#            config_entry.version = 2
#        hass.config_entries.async_update_entry(config_entry, data=new)
#        _LOGGER.info("Migration to version %s successful", config_entry.version)

#    return True