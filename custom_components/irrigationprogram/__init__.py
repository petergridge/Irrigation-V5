"""__init__."""

from __future__ import annotations

import asyncio
import contextlib
from ctypes.wintypes import BOOL
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_NAME,
    SERVICE_TURN_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from . import utils

#from homeassistant import config_entries
from .const import (
    ATTR_DEVICE_TYPE,
    ATTR_GROUPS,
    ATTR_SHOW_CONFIG,
    CONST_SWITCH,
    DOMAIN,
    SWITCH_ID_FORMAT,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up irrigtest from a config entry."""
    # store an object for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = {ATTR_NAME:entry.data.get(ATTR_NAME)}
    PLATFORMS: list[str] = ["binary_sensor", "sensor", "switch"]
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True

async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    _LOGGER.warning("reload %s", ConfigEntry)
    await hass.config_entries.async_reload(entry.entry_id)

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    _LOGGER.warning('%s removed from %s configuration',entry.title, entry.domain)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    #clean up any related helpers
    await hass.config_entries.async_unload_platforms(
        entry, (Platform.SENSOR,)
        )
    await hass.config_entries.async_unload_platforms(
        entry, (Platform.BINARY_SENSOR,)
        )
    return await hass.config_entries.async_unload_platforms(
        entry, (Platform.SWITCH,)
    )

async def async_setup(hass:HomeAssistant, config):
    '''Irrigation object.'''
    hass.data.setdefault(DOMAIN, {})

    # 1. Serve lovelace card
    path = Path(__file__).parent / "www"
    utils.register_static_path(hass.http.app, "/irrigationprogram/www/irrigation-card.js", path / "irrigation-card.js")

    # 2. Add card to resources
    version = getattr(hass.data["integrations"][DOMAIN], "version", 0)
    await utils.init_resource(hass, "/irrigationprogram/www/irrigation-card.js", str(version))

    async def async_stop_programs(call):
        '''Stop all running programs.'''

        for data in hass.data[DOMAIN].values():
            if data.get(ATTR_NAME) == call.data.get("ignore", ""):
                await asyncio.sleep(1)
                continue
            device = SWITCH_ID_FORMAT.format(slugify(data.get(ATTR_NAME,'unknown')))
            servicedata = {ATTR_ENTITY_ID: device}

            #warn if the program is terminated by a service call
            try:
                if hass.states.get(device).state == "on":
                    if call.data.get("ignore", ""):
                        _LOGGER.warning("Irrigation Program '%s' terminated by '%s'", data.get(ATTR_NAME), call.data.get("ignore", "") )
                    else:
                        _LOGGER.warning("Irrigation Program '%s' terminated ", data.get(ATTR_NAME))
                    await hass.services.async_call(CONST_SWITCH, SERVICE_TURN_OFF, servicedata)
            except AttributeError:
                _LOGGER.warning('Could not find Program implementation %s, ignored', device)
                continue
    # END async_stop_programs

    # register the service
    hass.services.async_register(DOMAIN, "stop_programs", async_stop_programs)

    async def async_list_config(call):
        '''List programs in a yaml like structure.'''
        output = chr(10)
        for number,entry in enumerate(hass.config_entries.async_entries(DOMAIN)):
            if entry.options == {}:
                data = entry.data
            else:
                data = entry.options
            output += "Program " + str(number+1) + chr(10)
            for attr in data.items():
                if attr[0] == "xx":
                    continue
                if attr[0] == "zones":
                    for number,zone in enumerate(attr[1]):
                        output += "  Zone " + str(number+1) + chr(10)
                        for zoneattr in zone.items():
                            attrvalue = hass.states.get(zoneattr[1]).state
                            output += "    " + str(zoneattr[0]) + ": " + str(zoneattr[1]) + ": "+ attrvalue + chr(10)
                else:
                    try:
                        attrvalue = hass.states.get(attr[1]).state
                        output += "  " + str(attr[0]) + ": " + str(attr[1]) + ": "+ attrvalue + chr(10)
                    except:
                        output += "  " + str(attr[0]) + ": " + str(attr[1]) + chr(10)

        _LOGGER.warning(output)

    # register the service
    hass.services.async_register(DOMAIN, "list_config", async_list_config)

    return True

@callback
def _async_find_matching_config_entry(
    hass: HomeAssistant, name
) -> BOOL:
    '''Determine if a config has been imported from YAML.'''
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_NAME) == name:
            return True
    return False

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version == 2:
        if config_entry.options == {}:
            new = {**config_entry.data} #config_entry.data
        else:
            new = {**config_entry.options} #config_entry.options
        new.update({ATTR_DEVICE_TYPE: 'generic'})
        with contextlib.suppress(KeyError):
            new.pop(ATTR_SHOW_CONFIG)
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=new)

    if config_entry.version == 3:
        if config_entry.options == {}:
            new = {**config_entry.data} #config_entry.data
        else:
            new = {**config_entry.options} #config_entry.options

        try:
            new.pop(ATTR_GROUPS)
            _LOGGER.info("Removing Groups configuration")
        except KeyError:
            pass
        config_entry.version = 4
        hass.config_entries.async_update_entry(config_entry, data=new)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True

