''' __init__'''

from __future__ import annotations

import asyncio
import logging
from homeassistant.util import slugify

# -----------Helpers---------------------------
from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import string

from .const import CONST_SWITCH, DOMAIN, SWITCH_ID_FORMAT

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
    hass.data.setdefault(DOMAIN, {})

#    platforms = config.get(CONST_SWITCH)

#    for domain in platforms:
#        if domain.get("platform") == DOMAIN:
#            switches = domain.get("switches")
#            break

    async def async_stop_programs(call):
        ''' stop all running programs'''
        for data in hass.data[DOMAIN].values():
            if data.get(ATTR_NAME) == call.data.get("ignore", ""):
                continue
            device = SWITCH_ID_FORMAT.format(slugify(data.get(ATTR_NAME)))
            data = {ATTR_ENTITY_ID: device}
            await hass.services.async_call(CONST_SWITCH, SERVICE_TURN_OFF, data)
    # END async_stop_switches

    async def async_run_zone(call):
        ''' run a zone'''
    #    data = {}
    #    await hass.services.async_call(DOMAIN, "stop_programs", data)
    #    await asyncio.sleep(1)
        program = call.data.get("entity_id")
        zone = call.data.get("zone")
        data = {ATTR_ENTITY_ID: program, "zone": zone}
        await hass.services.async_call(DOMAIN, "set_run_zone", data)
        await asyncio.sleep(1)
        data = {ATTR_ENTITY_ID: program}
        await hass.services.async_call(CONST_SWITCH, SERVICE_TURN_ON, data)
    # register services
    hass.services.async_register(DOMAIN, "stop_programs", async_stop_programs)
    hass.services.async_register(DOMAIN, "run_zone", async_run_zone)
    return True
