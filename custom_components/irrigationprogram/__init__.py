"""__init__."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.number import NumberEntity
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.text import TextEntity
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from . import utils
from .const import (
    ATTR_CARD_YAML,
    ATTR_CONTINUE_ON_UNEXPECTED_STATE,
    ATTR_DEVICE_TYPE,
    ATTR_FLOW_SENSOR,
    ATTR_FREQUENCY,
    ATTR_FREQUENCY_OPTIONS,
    ATTR_GROUPS,
    ATTR_INPUT_MODE,
    ATTR_INTERLOCK,
    ATTR_LATENCY,
    ATTR_MIN_SEC,
    ATTR_PARALLEL,
    ATTR_PAUSE_WATER_SOURCE,
    ATTR_PUMP,
    ATTR_PUMP_DELAY,
    ATTR_RAIN_BEHAVIOUR,
    ATTR_RAIN_DELAY,
    ATTR_RAIN_SENSOR,
    ATTR_REPEAT,
    ATTR_SHOW_CONFIG,
    ATTR_START_LATENCY,
    ATTR_START_TYPE,
    ATTR_WATER_ADJUST,
    ATTR_WATER_MAX,
    ATTR_WATER_SOURCE,
    ATTR_WATER_TYPE,
    ATTR_ZONE,
    ATTR_ZONE_DELAY_MAX,
    ATTR_ZONES,
    CONST_ECO,
    DOMAIN,
)
from .globals import QUEUEDPROGRAMS

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS: list[str] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
]
PLATFORMS1: list[str] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TEXT,
    Platform.TIME,
]
PLATFORMS2: list[str] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)

type IrrigationConfigEntry = ConfigEntry[IrrigationData]


@dataclass
class IrrigationData:
    """Irrigation data class."""

    program: IrrigationProgram
    zone_data: list[IrrigationZoneData]


@dataclass
class IrrigationZoneData:
    """Zone data class."""

    zone: str  # switch.example, valve.example
    switch: Any|SwitchEntity  # generated object
    type: str  # switch|valve
    name: str
    config: Any|SwitchEntity  # generated object
    eco: bool
    watering_type: str
    water: Any|NumberEntity  # generated object
    wait: Any|NumberEntity  # generated object
    repeat: Any|NumberEntity  # generated object
    frequency: Any|SelectEntity  # generated object
    freq: bool
    ignore_sensors: Any|SwitchEntity  # generated object
    enabled: Any|SwitchEntity  # generated
    status: Any|SensorEntity
    next_run: Any|SensorEntity
    last_ran: Any|SensorEntity
    remaining_time: Any|SensorEntity
    default_run_time: Any|SensorEntity
    rain_sensor: str  # sensor.example
    adjustment: str  # sensor.example
    flow_rate: Any|str  # sensor.example

@dataclass
class IrrigationProgram:
    """Program data class."""
    name: str
    switch: Any
    modified: str
    pause: Any|SwitchEntity
    rain_delay_on: bool
    pump: str # switch.example, valve.example
    flow_sensor: str  # sensor.example
    water_source: str  # sensor.example
    rain_delay: Any|SwitchEntity
    rain_delay_days: Any|NumberEntity
    unique_id: str
    config: Any|SwitchEntity
    start_time: Any|TimeEntity  # generated
    delay_time: Any|SensorEntity  # generated
    remaining_time: Any|SensorEntity  # generated
    default_run_time: Any|SensorEntity
    multitime: Any|TextEntity  # generated
    sunrise_offset: Any|NumberEntity  # generated
    sunset_offset: Any|NumberEntity  # generated
    start_type: str  # selector|multistart|sunrise|sunset
    frequency: Any|SelectEntity  # generated
    freq_options: list
    freq: bool
    repeat: bool
    repeats: Any|NumberEntity
    rain_behaviour: str  # stop|continue
    enabled: Any|SwitchEntity  # generated
    controller_type: str  # rainbird|generic
    inter_zone_delay: Any|NumberEntity  # generated
    interlock: bool
    zone_count: int
    min_sec: str  # minutes|seconds
    water_max: int
    water_step: int
    zone_delay_max: int
    parallel: int
    pump_delay: int
    card_yaml: bool
    latency: int=5
    start_latency: int = 60
    water_source_pause: bool = False
    continue_on_unexpected_state: bool = False
    input_mode: str = "slider"  # slider|box


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up irrigation from a config entry."""

    if entry.options != {}:
        config = entry.options
    else:
        config = entry.data

    TIMEOUT_SECONDS = max(int(config.get(ATTR_START_LATENCY,60)), 60)
    REQUIRED_OBJECTS = []

    for zone in config.get(ATTR_ZONES,[]):
        REQUIRED_OBJECTS.append(zone.get(ATTR_ZONE))
        if zone.get(ATTR_RAIN_SENSOR,None):
            REQUIRED_OBJECTS.append(zone.get(ATTR_RAIN_SENSOR))
        if zone.get(ATTR_WATER_ADJUST,None):
            REQUIRED_OBJECTS.append(zone.get(ATTR_WATER_ADJUST))
    if config.get(ATTR_FLOW_SENSOR, None):
        REQUIRED_OBJECTS.append(config.get(ATTR_FLOW_SENSOR))
    if config.get(ATTR_WATER_SOURCE, None):
        REQUIRED_OBJECTS.append(config.get(ATTR_WATER_SOURCE))


    async def _async_finish_setup(_event=None):
        """Perform the actual setup logic after HA has started."""
        try:
            # Wait for all objects with a strict timeout
            await asyncio.wait_for(_wait_for_objects(), timeout=TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for objects: %s, Proceeding with partial setup",
                REQUIRED_OBJECTS
            )

        program = IrrigationProgram(
            name=entry.title,
            switch=None,
            modified=config.get("updated",""),
            pause=None,
            rain_delay_on=config.get(ATTR_RAIN_DELAY, False),
            pump=config.get(ATTR_PUMP, None),
            flow_sensor=config.get(ATTR_FLOW_SENSOR, None),
            water_source=config.get(ATTR_WATER_SOURCE, None),
            rain_delay=None,
            rain_delay_days=None,
            unique_id=entry.entry_id,
            config=None,
            start_time=None,
            delay_time=None,
            remaining_time=None,
            default_run_time=None,
            multitime=None,
            sunrise_offset=None,
            sunset_offset=None,
            start_type=config.get(ATTR_START_TYPE, "selector"),
            frequency=None,
            freq_options=config.get(ATTR_FREQUENCY_OPTIONS,[]),
            freq=config.get(ATTR_FREQUENCY,False),
            repeat=config.get(ATTR_REPEAT,False),
            repeats=None,
            rain_behaviour=config.get(ATTR_RAIN_BEHAVIOUR, "stop"),
            enabled=None,
            controller_type=config.get(ATTR_DEVICE_TYPE,"Generic"),
            inter_zone_delay=None,
            interlock=config.get(ATTR_INTERLOCK, "strict"),
            zone_count=len(config.get(ATTR_ZONES,0)),
            min_sec=config.get(ATTR_MIN_SEC, "minutes"),
            water_max=config.get(ATTR_WATER_MAX, 30),
            latency=int(config.get(ATTR_LATENCY, 5)),
            start_latency=max(int(config.get(ATTR_START_LATENCY,60)), 60),
            water_step=config.get("water_step", 1),
            zone_delay_max=config.get(ATTR_ZONE_DELAY_MAX, 120),
            parallel=config.get(ATTR_PARALLEL, 1),
            pump_delay=config.get(ATTR_PUMP_DELAY, 1),
            card_yaml=config.get(ATTR_CARD_YAML, False),
            water_source_pause=config.get(ATTR_PAUSE_WATER_SOURCE, False),
            continue_on_unexpected_state=config.get(ATTR_CONTINUE_ON_UNEXPECTED_STATE, False),
            input_mode=config.get(ATTR_INPUT_MODE, "slider")
        )
        # Report if any of the dependant objects haven't loaded,
        # this could be due to a slow registering device or an incorrect entity id,
        # the program will still be loaded but these features won't work until the objects are available
        if program.flow_sensor:
            state = hass.states.get(program.flow_sensor)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                msg = f"Warning, {program.flow_sensor} has not initialised before irrigation program, check your configuration"
                _LOGGER.debug(msg)
        if program.water_source:
            state = hass.states.get(program.water_source)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                msg = f"Warning, {program.water_source} has not initialised before irrigation program, check your configuration"
                _LOGGER.debug(msg)

        zone_data = []
        for zone in config.get(ATTR_ZONES,[]):
            z = IrrigationZoneData(
                zone=zone.get(ATTR_ZONE),
                switch=None,
                type=zone.get(ATTR_ZONE).split(".")[0],
                name=zone.get(ATTR_ZONE).split(".")[1],
                config=None,
                eco=zone.get(CONST_ECO, False),
                watering_type=zone.get(ATTR_WATER_TYPE),
                water=None,
                wait=None,
                repeat=None,
                frequency=None,
                freq=zone.get(ATTR_FREQUENCY),
                ignore_sensors=None,
                enabled=None,
                status=None,
                next_run=None,
                last_ran=None,
                remaining_time=None,
                default_run_time=None,
                rain_sensor=zone.get(ATTR_RAIN_SENSOR),
                adjustment=zone.get(ATTR_WATER_ADJUST),
                flow_rate=None,
            )
            msg = ""
            nl = "\n"
            state = hass.states.get(z.zone)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                msg += f"ERROR {z.zone} has not initialised before the Irrigation Program, this could be a slow registering device, try increasing the 'Wait time from devices that load slowly on startup' setting in the advanced options."
            zone_data.append(z)
            # check if dependant objects are ready
            if z.adjustment:
                state = hass.states.get(z.adjustment)
                if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    if msg is not None:
                        msg = f"{nl}"
                    msg += f"Warning, {z.adjustment} has not initialised before irrigation program, check your configuration{nl}"
            if z.rain_sensor:
                state = hass.states.get(z.rain_sensor)
                if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    if msg is not None:
                        msg = f"{nl}"
                    msg += f"Warning, {z.rain_sensor} has not initialised before irrigation program, check your configuration"
            if msg:
                async_create(
                    hass,
                    message=msg,
                    title="Irrigation Controller",
                    notification_id="irrigation_device_error",
                )
                continue

        entry.runtime_data = IrrigationData(program, zone_data)

        # store an object for your platforms to access
        hass.data[DOMAIN][entry.entry_id] = {ATTR_NAME: entry.data.get(ATTR_NAME)}
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS1)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS2)

        entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))


    async def _wait_for_objects():
        """Wait until all target objects are actually in the state machine."""
        while True:
            all_loaded = True
            for entity_id in REQUIRED_OBJECTS:
                state = hass.states.get(entity_id)
                # Check if state exists and isn't 'unknown' or 'unavailable'
                if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    all_loaded = False
                    break

            if all_loaded:
                break

            # Wait a short period before checking again to avoid blocking
            await asyncio.sleep(.1)

    # Create background task so async_setup can return True immediately
    # 1. Wait for HA to finish its internal startup first
    if  hass.is_running:
        await _async_finish_setup()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_finish_setup)
    return True


def exclude(hass: HomeAssistant):
    """Build list of entities to exclude from config flow selection."""
    output = []
    try:
        for e in hass.config_entries.async_entries(DOMAIN):
            if e.state == ConfigEntryState.NOT_LOADED:
                # this config is disabled
                continue
            i: IrrigationData = e.runtime_data
            p: IrrigationProgram = i.program
            output.extend(
                [
                    p.switch.entity_id,
                    p.enabled.entity_id,
                    p.config.entity_id,
                    p.start_time.entity_id,
                    p.remaining_time.entity_id,
                    p.default_run_time.entity_id,
                    p.delay_time.entity_id,
                ]
            )
            if p.inter_zone_delay:
                output.append(p.inter_zone_delay.entity_id)
            if p.frequency:
                output.append(p.frequency.entity_id)
            if p.repeat:
                output.append(p.repeats.entity_id)
            zs: list[IrrigationZoneData] = i.zone_data
            for zone in zs:
                z: IrrigationZoneData = zone
                output.extend(
                    [
                        z.config.entity_id,
                        z.enabled.entity_id,
                        z.next_run.entity_id,
                        z.status.entity_id,
                        z.water.entity_id,
                        z.last_ran.entity_id,
                        z.remaining_time.entity_id,
                        z.default_run_time.entity_id,
                        z.switch.entity_id,
                    ]
                )
                if z.eco:
                    output.extend([z.wait.entity_id, z.repeat.entity_id])
                if z.frequency:
                    output.append(z.frequency.entity_id)
                if z.ignore_sensors:
                    output.append(z.ignore_sensors.entity_id)
    except AttributeError:
        async_dismiss(hass, "irrigation_device_error")
        async_create(
            hass,
            message="A configured item is no longer available or has been renamed",
            title="Irrigation Controller",
            notification_id="irrigation_device_error",
        )
        return []
    return output


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    _LOGGER.debug("%s reload from %s configuration", entry.title, entry.domain)

    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    _LOGGER.debug("%s removed from %s configuration", entry.title, entry.domain)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("%s unload from %s configuration", entry.title, entry.domain)
    # clean up any related helpers
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS2)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS1)
    if unload_ok:
        # remove the instance of component
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_queue_program(hass: HomeAssistant, program):
    """Queue programs."""

    # await asyncio.sleep(0)
    QUEUEDPROGRAMS.append(program)
    if QUEUEDPROGRAMS[0] != program:
        await program.pause_switch.async_turn_on()


async def async_setup(hass: HomeAssistant, config):
    """Irrigation object."""

    hass.data.setdefault(DOMAIN, {})
    #    if not config.get("card_yaml", False):
    # 1. Serve lovelace card
    path = Path(__file__).parent / "www"

    try:

        await hass.http.async_register_static_paths(
            [StaticPathConfig("/irrigationprogram/www/irrigation-card.js", str(path / "irrigation-card.js"))]
        )

        # 2. Add card to resources
        version = getattr(hass.data["integrations"][DOMAIN], "version", 0)
        await utils.init_resource(
            hass, "/irrigationprogram/www/irrigation-card.js", str(version)
        )
    except Exception as error:
        _LOGGER.error(error)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version == 2:
        migrate_2(hass, config_entry)

    if config_entry.version == 3:
        migrate_3(hass, config_entry)

    if config_entry.version == 4:
        migrate_4(hass, config_entry)

    if config_entry.version == 5:
        migrate_5(hass, config_entry)

    if config_entry.version == 6:
        migrate_6(hass, config_entry)

    if config_entry.version == 7:
        migrate_7(hass, config_entry)

    if config_entry.version == 8:
        migrate_8(hass, config_entry)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


def migrate_2(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 2 to version 3 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}
    new.update({ATTR_DEVICE_TYPE: "generic"})
    with contextlib.suppress(KeyError):
        new.pop(ATTR_SHOW_CONFIG)
    hass.config_entries.async_update_entry(config_entry, data=new, version=3)


def migrate_3(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 3 to version 4 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}

    with contextlib.suppress(KeyError):
        new.pop(ATTR_GROUPS)
    hass.config_entries.async_update_entry(config_entry, data=new, version=4)


def migrate_4(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 4 to version 5 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}

    with contextlib.suppress(KeyError):
        new.pop("xx")
    hass.config_entries.async_update_entry(config_entry, data=new, version=5)


def migrate_5(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 5 to version 6 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}

    msg = "Migration warnings:"
    msg += (
        chr(10)
        + chr(10)
        + 'Frequency Options have defaulted to "1", reconfigure the program to add more options'
    )
    msg += chr(10) + chr(10) + "Remove " + new.get("start_time","")
    with contextlib.suppress(KeyError):
        new.pop("start_time")
    # if this has a value set the flag and collect the options
    if new.get("run_freq"):
        msg += chr(10) + chr(10) + "Remove " + new.get("run_freq","")
        with contextlib.suppress(KeyError):
            new.pop("run_freq")
        new[ATTR_FREQUENCY] = True
    if new.get("controller_monitor"):
        msg += chr(10) + chr(10) + "Remove " + new.get("controller_monitor","")
        with contextlib.suppress(KeyError):
            new.pop("controller_monitor")
    if new.get("inter_zone_delay"):
        msg += chr(10) + chr(10) + "Remove " + new.get("inter_zone_delay","")
        with contextlib.suppress(KeyError):
            new.pop("inter_zone_delay")
    if new.get("irrigation_on"):
        msg += chr(10) + chr(10) + "Remove " + new.get("irrigation_on","")
        with contextlib.suppress(KeyError):
            new.pop("irrigation_on")
        # add required defaults
    new[ATTR_START_TYPE] = "selector"
    new[ATTR_RAIN_BEHAVIOUR] = "stop"

    # process the zones
    zones = new.get(ATTR_ZONES,[])
    newzones = []
    for zone in zones:
        newzone = zone
        # remove unused
        if newzone.get("water", None):
            msg += chr(10) + chr(10) + "Remove " + newzone.get("water")
            with contextlib.suppress(KeyError):
                newzone.pop("water")
        if newzone.get("wait", None):
            msg += chr(10) + chr(10) + "Remove " + newzone.get("wait")
            with contextlib.suppress(KeyError):
                newzone.pop("wait")
            newzone["eco"] = True
        if newzone.get("repeat", None):
            msg += chr(10) + chr(10) + "Remove " + newzone.get("repeat")
            with contextlib.suppress(KeyError):
                newzone.pop("repeat")
        # if this has a value set the flag and collect the options
        if newzone.get("run_freq", None):
            msg += chr(10) + chr(10) + "Remove " + newzone.get("run_freq")
            with contextlib.suppress(KeyError):
                newzone.pop("run_freq")
            newzone[ATTR_FREQUENCY] = True
        if newzone.get("ignore_rain_sensor", None):
            msg += chr(10) + chr(10) + "Remove " + newzone.get("ignore_rain_sensor")
            with contextlib.suppress(KeyError):
                newzone.pop("ignore_rain_sensor")
        if newzone.get("enable_zone", None):
            msg += chr(10) + chr(10) + "Remove " + newzone.get("enable_zone")
            with contextlib.suppress(KeyError):
                newzone.pop("enable_zone")
        # remove the entries with wrong data type
        if newzone.get("water_adjustment", None):
            if newzone.get("water_adjustment", None).split(".")[0] != "sensor":
                msg += (
                    chr(10)
                    + chr(10)
                    + newzone.get("water_adjustment", None)
                    + ' must of type "sensor"'
                )
                newzone.pop("water_adjustment")
        if newzone.get("flow_sensor", None):
            if newzone.get("flow_sensor", None).split(".")[0] != "sensor":
                msg += (
                    chr(10)
                    + chr(10)
                    + newzone.get("flow_sensor")
                    + ' must be of type "sensor"'
                )
                newzone.pop("flow_sensor")
        if newzone.get("rain_sensor", None):
            if newzone.get("rain_sensor", None).split(".")[0] != "binary_sensor":
                msg += (
                    chr(10)
                    + chr(10)
                    + newzone.get("rain_sensor", None)
                    + ' must it be of type "binary_sensor"'
                )
                newzone.pop("rain_sensor")
        if newzone.get("water_source_active", None):
            if (
                newzone.get("water_source_active", None).split(".")[0]
                != "binary_sensor"
            ):
                msg += (
                    chr(10)
                    + chr(10)
                    + newzone.get("water_source_active")
                    + ' must of type "binary_sensor"'
                )
                newzone.pop("water_source_active")

        newzones.append(newzone)

    new[ATTR_ZONES] = newzones

    # create the persistent notification
    async_dismiss(hass,"irrigation_card")
    async_create(
        hass,
        message=msg,
        title="Irrigation Controller",
        notification_id="irrigation_card",
    )
    hass.config_entries.async_update_entry(config_entry, data=new, version=6)


def migrate_6(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 6 to version 7 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}

    if new.get(ATTR_INTERLOCK, True):
        new.update({ATTR_INTERLOCK: "strict"})
    else:
        new.update({ATTR_INTERLOCK: "off"})
    new[ATTR_MIN_SEC] = "minutes"
    hass.config_entries.async_update_entry(config_entry, data=new, version=7)


def migrate_7(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 7 to version 8 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}

    with contextlib.suppress(KeyError):
        del new["vent"]

    if new.get(ATTR_INTERLOCK) == "strict":
        new.update({ATTR_INTERLOCK: True})
    else:
        new.update({ATTR_INTERLOCK: False})
    localtimezone = ZoneInfo(hass.config.time_zone)
    updated = datetime.now(localtimezone).strftime("%Y-%m-%d %H:%M:%S.%f")
    new.update({"updated": updated})

    hass.config_entries.async_update_entry(
        config_entry,
        data=new,
        options=new,
        version=8,
    )


def migrate_8(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate from version 8 to version 9 configuration."""
    if config_entry.options == {}:
        new = {**config_entry.data}
    else:
        new = {**config_entry.options}

    zones = new.get(ATTR_ZONES,[])
    newzones = []
    for zone in zones:
        newzone = zone
        if newzone.get("ATTR_PUMP", None):
            new[ATTR_PUMP] = newzone.get("ATTR_PUMP")
            newzone.pop(ATTR_PUMP)
        if newzone.get("ATTR_WATER_SOURCE", None):
            new[ATTR_WATER_SOURCE] = newzone.get("ATTR_WATER_SOURCE")
            newzone.pop(ATTR_WATER_SOURCE)
        if newzone.get("ATTR_FLOW_SENSOR", None):
            new[ATTR_FLOW_SENSOR] = newzone.get("ATTR_FLOW_SENSOR")
            newzone.pop(ATTR_FLOW_SENSOR)
        newzones.append(newzone)
    new[ATTR_ZONES] = newzones

    localtimezone = ZoneInfo(hass.config.time_zone)
    updated = datetime.now(localtimezone)
    new.update({"updated": updated})

    hass.config_entries.async_update_entry(
        config_entry,
        data=new,
        options=new,
        version=9,
    )
