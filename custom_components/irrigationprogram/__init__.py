"""__init__."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import logging
from pathlib import Path

from homeassistant.components.number import NumberEntity
from homeassistant.components.persistent_notification import async_create
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.text import TextEntity
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, SERVICE_TURN_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from . import utils
from .const import (
    ATTR_DEVICE_TYPE,
    ATTR_FLOW_SENSOR,
    ATTR_GROUPS,
    ATTR_INTERLOCK,
    ATTR_PUMP,
    ATTR_RAIN_BEHAVIOUR,
    ATTR_RAIN_SENSOR,
    ATTR_SHOW_CONFIG,
    ATTR_START_TYPE,
    ATTR_WATER_ADJUST,
    ATTR_WATER_SOURCE,
    ATTR_ZONE,
    ATTR_ZONES,
    CONST_SWITCH,
    DOMAIN,
    SWITCH_ID_FORMAT,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS:  list[str] = [Platform.NUMBER,Platform.SELECT, Platform.SENSOR, Platform.SWITCH, Platform.TEXT, Platform.TIME]
PLATFORMS1: list[str] = [Platform.NUMBER,Platform.SELECT, Platform.SENSOR, Platform.TEXT, Platform.TIME]
PLATFORMS2: list[str] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)

type IrrigationConfigEntry = ConfigEntry[IrrigationData]

@dataclass
class IrrigationData:
    program: IrrigationProgram
    zone_data: list[IrrigationZoneData]

@dataclass
class IrrigationZoneData:
    zone: str #switch.example, valve.example
    switch:SwitchEntity #generated object
    type: str #switch|valve
    name: str
    config: SwitchEntity #generated object
    eco: bool
    water: NumberEntity #generated object
    wait: NumberEntity #generated object
    repeat: NumberEntity #generated object
    frequency: SelectEntity #generated object
    freq: bool
    ignore_sensors: SwitchEntity #generated object
    enabled: SwitchEntity #generated
    status: SensorEntity
    next_run: SensorEntity
    last_ran: SensorEntity
    remaining_time: SensorEntity
    rain_sensor: str  #sensor.example
    pump: str #switch.example, valve.example
    flow_sensor: str #sensor.example
    adjustment: str #sensor.example
    water_source: str #sensor.example
    flow_rate: str #sensor.example

@dataclass
class IrrigationProgram:
    name: str
    switch: SwitchEntity
    pause: SwitchEntity
    unique_id: str
    config: SwitchEntity
    start_time: TimeEntity #generated
    remaining_time: SensorEntity #generated
    multitime: TextEntity #generated
    sunrise_offset: NumberEntity #generated
    sunset_offset: NumberEntity #generated
    start_type: str #selector|multistart|sunrise|sunset
    frequency: SelectEntity #generated
    freq_options: list
    freq: bool
    rain_behaviour: str #stop|continue
    enabled: SwitchEntity #generated
    controller_type: str #rainbird|generic
    inter_zone_delay: NumberEntity #generated
    interlock: bool
    zone_count: int
    water_max: int
    water_step: int
    parallel: int


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up irrigation from a config entry."""
    if entry.options != {}:
        config = entry.options
    else:
        config = entry.data

    program = IrrigationProgram(
        name = entry.title,
        switch= None,
        pause=None,
        unique_id = entry.entry_id,
        config = None,
        start_time = None,
        remaining_time = None,
        multitime = None,
        sunrise_offset = None,
        sunset_offset = None,
        start_type = config.get(ATTR_START_TYPE),
        frequency = None,
        freq_options = config.get("freq_options"),
        freq = config.get("freq"),
        rain_behaviour = config.get(ATTR_RAIN_BEHAVIOUR),
        enabled = None,
        controller_type = config.get(ATTR_DEVICE_TYPE),
        inter_zone_delay = None,
        interlock = config.get(ATTR_INTERLOCK),
        zone_count = len(config.get(ATTR_ZONES)),
        water_max = config.get('water_max',30),
        water_step = config.get('water_step',1),
        parallel = config.get('parallel',1)
        )

    zone_data=[]
    for zone in config.get(ATTR_ZONES):

        z= IrrigationZoneData (
            zone=zone.get(ATTR_ZONE),
            switch=None,
            type= zone.get(ATTR_ZONE).split(".")[0],
            name = zone.get(ATTR_ZONE).split(".")[1],
            config = None,
            eco = zone.get('eco'),
            water = None,
            wait = None,
            repeat = None,
            frequency=None,
            freq = zone.get("freq"),
            ignore_sensors=None,
            enabled=None,
            status=None,
            next_run=None,
            last_ran = None,
            remaining_time = None,
            rain_sensor = zone.get(ATTR_RAIN_SENSOR),
            pump = zone.get(ATTR_PUMP),
            flow_sensor = zone.get(ATTR_FLOW_SENSOR),
            adjustment = zone.get(ATTR_WATER_ADJUST),
            water_source = zone.get(ATTR_WATER_SOURCE),
            flow_rate = None
            )
        zone_data.append(z)
    entry.runtime_data = IrrigationData(program,zone_data)

    # store an object for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = {ATTR_NAME:entry.data.get(ATTR_NAME)}
    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS1)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS2)

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True

def exclude(hass:HomeAssistant):
    """Build list of entities to exclude from config flow selection."""
    output = []
    for e in hass.config_entries.async_entries(DOMAIN):
        i:IrrigationData = e.runtime_data
        p:IrrigationProgram = i.program
        output.extend([p.switch.entity_id, p.enabled.entity_id,
                       p.config.entity_id, p.start_time.entity_id,
                       p.remaining_time.entity_id])
        if p.inter_zone_delay:
            output.append(p.inter_zone_delay.entity_id)
        if p.frequency:
            output.append(p.frequency.entity_id)
        zs:IrrigationZoneData = i.zone_data
        for zone in zs:
            z:IrrigationZoneData = zone
            output.extend([z.config.entity_id,z.enabled.entity_id,
                            z.next_run.entity_id,z.status.entity_id,
                            z.water.entity_id,z.last_ran.entity_id,
                            z.remaining_time.entity_id,
                            z.switch.entity_id])
            if z.eco:
                output.extend([z.wait.entity_id,z.repeat.entity_id])
            if z.frequency:
                output.append(z.frequency.entity_id)
            if z.ignore_sensors:
                output.append(z.ignore_sensors.entity_id)
    return output

async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    _LOGGER.debug("reload %s", ConfigEntry)
    await hass.config_entries.async_reload(entry.entry_id)

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    _LOGGER.warning('%s removed from %s configuration',entry.title, entry.domain)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    #clean up any related helpers
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_stop_programs(hass,ignore_program):
    '''Stop all running programs.'''

    for n, data in enumerate(hass.data[DOMAIN].values()):
        if data.get(ATTR_NAME) == ignore_program:
            continue
        device = SWITCH_ID_FORMAT.format(slugify(data.get(ATTR_NAME,'unknown')))
        servicedata = {ATTR_ENTITY_ID: device}
        #warn if the program is terminated
        await asyncio.sleep(n)
        if hass.states.get(device).is_on:
            async_create(
                hass,
                message=f"Irrigation Program {data.get(ATTR_NAME)} terminated by {ignore_program}",
                title="Irrigation Controller"
            )
            await hass.services.async_call(CONST_SWITCH, SERVICE_TURN_OFF, servicedata)

async def async_setup(hass:HomeAssistant, config):
    '''Irrigation object.'''
    hass.data.setdefault(DOMAIN, {})

    # 1. Serve lovelace card
    path = Path(__file__).parent / "www"
    utils.register_static_path(hass.http.app, "/irrigationprogram/www/irrigation-card.js", path / "irrigation-card.js")

    # 2. Add card to resources
    version = getattr(hass.data["integrations"][DOMAIN], "version", 0)
    await utils.init_resource(hass, "/irrigationprogram/www/irrigation-card.js", str(version))

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version == 2:
        if config_entry.options == {}:
            new = {**config_entry.data}
        else:
            new = {**config_entry.options}
        new.update({ATTR_DEVICE_TYPE: 'generic'})
        with contextlib.suppress(KeyError):
            new.pop(ATTR_SHOW_CONFIG)
        hass.config_entries.async_update_entry(config_entry, data=new, version=3)

    if config_entry.version == 3:
        if config_entry.options == {}:
            new = {**config_entry.data}
        else:
            new = {**config_entry.options}

        with contextlib.suppress(KeyError):
            new.pop(ATTR_GROUPS)
        hass.config_entries.async_update_entry(config_entry, data=new, version = 4)

    if config_entry.version == 4:
        if config_entry.options == {}:
            new = {**config_entry.data}
        else:
            new = {**config_entry.options}

        with contextlib.suppress(KeyError):
            new.pop('xx')
        hass.config_entries.async_update_entry(config_entry, data=new, version=5)

    if config_entry.version == 5:
        if config_entry.options == {}:
            new = {**config_entry.data}
        else:
            new = {**config_entry.options}

        msg='Migration warnings:'
        msg += chr(10) + chr(10) + 'Frequency Options have defaulted to "1", reconfigure the program to add more options'
        with contextlib.suppress(KeyError):
            new.pop('start_time')
        #if this has a value set the flag and collect the options
        if new.get('run_freq',None):
            with contextlib.suppress(KeyError):
                new.pop('run_freq')
            new['freq'] = True
        with contextlib.suppress(KeyError):
            new.pop('controller_monitor')
        with contextlib.suppress(KeyError):
            new.pop('inter_zone_delay')
        with contextlib.suppress(KeyError):
            new.pop('irrigation_on')
            #add required defaults
        new[ATTR_START_TYPE] = "selector"
        new[ATTR_RAIN_BEHAVIOUR] = "stop"

            #process the zones
        zones = new.get(ATTR_ZONES)
        newzones = []
        for zone in zones:
            newzone = zone
            #remove unused
            with contextlib.suppress(KeyError):
                newzone.pop('water')
            with contextlib.suppress(KeyError):
                newzone.pop('wait')
            with contextlib.suppress(KeyError):
                newzone.pop('repeat')
            #if this has a value set the flag and collect the options
            if newzone.get('run_freq',None):
                with contextlib.suppress(KeyError):
                    newzone.pop('run_freq')
                newzone['freq'] = True
            with contextlib.suppress(KeyError):
                newzone.pop('run_freq')
            with contextlib.suppress(KeyError):
                newzone.pop('ignore_rain_sensor')
            with contextlib.suppress(KeyError):
                newzone.pop('enable_zone')
            #remove the entries with wrong data type
            if newzone.get('water_adjustment',None):
                if newzone.get('water_adjustment',None).split('.')[0] != 'sensor':
                    msg += chr(10) + chr(10) + newzone.get('water_adjustment',None) + ' must of type "sensor"'
                    newzone.pop('water_adjustment')
            if newzone.get('flow_sensor',None):
                if newzone.get('flow_sensor',None).split('.')[0] != 'sensor':
                    msg += chr(10) + chr(10) + newzone.get('flow_sensor') + ' must be of type "sensor"'
                    newzone.pop('flow_sensor')
            if newzone.get('rain_sensor',None):
                if newzone.get('rain_sensor',None).split('.')[0] != 'binary_sensor':
                    msg += chr(10) + chr(10) + newzone.get('rain_sensor',None) + ' must it be of type "binary_sensor"'
                    newzone.pop('rain_sensor')
            if newzone.get('water_source_active',None):
                if newzone.get('water_source_active',None).split('.')[0] != 'binary_sensor':
                    msg += chr(10) + chr(10) + newzone.get('water_source_active') + ' must of type "binary_sensor"'
                    newzone.pop('water_source_active')

            newzones.append(newzone)

        new[ATTR_ZONES] = newzones

        #create the persistent notification
        async_create(
                hass,
                message=msg,
                title="Irrigation Controller"
            )

        hass.config_entries.async_update_entry(config_entry, data=new, version=6)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True

