'''__init__.'''

from __future__ import annotations

import logging
import os
from os.path import exists
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, storage as store

from . import utils
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up irrigtest from a config entry."""
    # store an object for your platforms to access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    PLATFORMS: list[str] = ["sensor"]
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True

async def async_setup(hass:HomeAssistant, config):
    '''Card setup.'''

    # 1. Serve lovelace card
    path = Path(__file__).parent / "www"
    utils.register_static_path(hass.http.app, "/openweathermaphistory/www/openweathermaphistory.js", path / "openweathermaphistory.js")

    # 2. Add card to resources
    version = getattr(hass.data["integrations"][DOMAIN], "version", 0)
    await utils.init_resource(hass, "/openweathermaphistory/www/openweathermaphistory.js", str(version))

    return True

async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, (Platform.SENSOR,))
    if unload_ok:
        #remove the instance of component
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        dname = config_entry.data.get(CONF_NAME,'unknown')
#        name = config_entry.options.get(CONF_NAME)
        name = config_entry.options.get(CONF_NAME,dname)
        try:
            file = os.path.join(hass.config.path(), cv.slugify(name)  + '.pickle')
            if exists(file):
                os.remove(file)
        except FileNotFoundError:
            pass
        try:
            file = os.path.join(hass.config.path(), cv.slugify('owm_api_count')  + '.pickle')
            os.remove(file)
        except FileNotFoundError:
            pass
        hass.config_entries.async_update_entry(config_entry,data=new,minor_version=1,version=2)
    return True

async def async_remove_entry(hass: HomeAssistant,entry: ConfigEntry):
    """Handle removal of entry."""
    name = "OWMH_" + entry.title
    x = store.Store[dict[any]](hass,1,name)
    await x.async_remove()
