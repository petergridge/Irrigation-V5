from collections import OrderedDict
from datetime import timedelta
from logging import getLogger

from homeassistant.components.automation import async_setup as setup_automation, \
    _async_process_config as add_automation, AutomationConfig
from homeassistant.components.input_boolean import async_setup as setup_input_boolean
from homeassistant.components.input_datetime import async_setup as setup_input_datetime
from homeassistant.components.input_number import async_setup as setup_input_number
from homeassistant.components.input_text import async_setup as setup_input_text
from homeassistant.components.input_select import async_setup as setup_input_select
from homeassistant.components.timer import async_setup as setup_timer
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.util import slugify

_LOGGER = getLogger(__name__)

COMPONENT_AUTOMATION = 'automation'
COMPONENT_INPUT_BOOLEAN = 'input_boolean'
COMPONENT_INPUT_DATETIME = 'input_datetime'
COMPONENT_INPUT_NUMBER = 'input_number'
COMPONENT_INPUT_TEXT = 'input_text'
COMPONENT_INPUT_SELECT = 'input_select'
COMPONENT_TIMER = 'timer'

CUSTOM_ENTITY_COMPONENTS = {}

SETUP_FUNCTION = {
    COMPONENT_AUTOMATION: setup_automation
}

AUTOMATIONS = []

# all input_* entities in HA (config + custom)
CONFIG_INPUT_BOOLEAN = {}
CONFIG_INPUT_DATETIME = {}
CONFIG_INPUT_NUMBER = {}
CONFIG_INPUT_TEXT = {}
CONFIG_INPUT_SELECT = {}
CONFIG_TIMER = {}

# save whether custom inputs were declared, so they can be added to HA
CUSTOM_INPUT_BOOLEAN = False
CUSTOM_INPUT_DATETIME = False
CUSTOM_INPUT_NUMBER = False
CUSTOM_INPUT_TEXT = False
CUSTOM_INPUT_SELECT = False
CUSTOM_TIMER = False


def add_host(device_id: str, host: Entity):
    HOSTS[device_id] = host


def get_host(device_id: str) -> Entity:
    return HOSTS.get(device_id, None)


async def _get_platform(hass: HomeAssistant, domain: str):
    platform_list = async_get_platforms(hass, domain)

    for platform in platform_list:
        if platform.domain == domain:
            return platform

    if domain not in CUSTOM_ENTITY_COMPONENTS:
        await SETUP_FUNCTION[domain](hass, {})

        CUSTOM_ENTITY_COMPONENTS[domain] = EntityComponent(
            _LOGGER, domain, hass, timedelta(seconds=86400)
        )

    return CUSTOM_ENTITY_COMPONENTS[domain]


async def create_input_boolean(slugname: str, name: str, icon=None, reset=False) -> str:
    data = {
        'name': name
    }

    if icon:
        data['icon'] = icon

    internal_name = slugname
    
    if not reset:
        CONFIG_INPUT_BOOLEAN[internal_name] = data

    global CUSTOM_INPUT_BOOLEAN
    CUSTOM_INPUT_BOOLEAN = True

    return 'input_boolean.{}'.format(internal_name)


async def create_input_datetime(slugname: str, name: str, has_date: bool, has_time: bool, initial=None,
                                icon=None, reset=False) -> str:
    data = {
        'name': name,
        'has_date': has_date,
        'has_time': has_time
    }

    if initial:
        data['initial'] = initial

    if icon:
        data['icon'] = icon

    internal_name = slugname

    if not reset:
        CONFIG_INPUT_DATETIME[internal_name] = OrderedDict(data)

    global CUSTOM_INPUT_DATETIME
    CUSTOM_INPUT_DATETIME = True

    return 'input_datetime.{}'.format(internal_name)


async def create_input_number(slugname: str, name: str, _min: int, _max: int, step: int, mode: str,
                              unit_of_measurement: str, icon=None, reset=False) -> str:
    data = {
        'name': name,
        'min': _min,
        'max': _max,
        'step': step,
        'mode': mode,
        'unit_of_measurement': unit_of_measurement
    }

    if icon:
        data['icon'] = icon

    internal_name = slugname

    if not reset:
        CONFIG_INPUT_NUMBER[internal_name] = data

    global CUSTOM_INPUT_NUMBER
    CUSTOM_INPUT_NUMBER = True

    return 'input_number.{}'.format(internal_name)


async def create_input_text(slugname: str, name: str, _min=0, _max=100, initial=None,
                            pattern='', mode='text', icon=None, reset=False) -> str:
    data = {
        'name': name,
        'min': _min,
        'max': _max,
        'initial': initial,
        'pattern': pattern,
        'mode': mode
    }

    if icon:
        data['icon'] = icon

    internal_name = slugname

    if not reset:
        CONFIG_INPUT_TEXT[internal_name] = data

    global CUSTOM_INPUT_TEXT
    CUSTOM_INPUT_TEXT = True

    return 'input_text.{}'.format(internal_name)

async def create_input_select(slugname: str, name: str, _options=[], initial=None,
                              icon=None, reset=False) -> str:
    data = {
        'name': name,
        'options': _options,
        'initial': initial
    }

    if icon:
        data['icon'] = icon

    internal_name = slugname

    if not reset:
        CONFIG_INPUT_SELECT[internal_name] = data

    global CUSTOM_INPUT_SELECT
    CUSTOM_INPUT_SELECT = True

    return 'input_text.{}'.format(internal_name)


async def create_timer(name: str, duration='00:00:00', reset=False) -> str:
    data = {
        'name': name,
        'duration': duration
    }

    internal_name = slugify(name)

    if not reset:
        CONFIG_TIMER[internal_name] = data

    global CUSTOM_TIMER
    CUSTOM_TIMER = True

    return 'timer.{}'.format(internal_name)


async def create_entities_and_automations(hass: HomeAssistant):

    if CUSTOM_INPUT_BOOLEAN:
        for entity_id in list(
                filter(lambda eid: COMPONENT_INPUT_BOOLEAN == eid.split('.')[0], hass.states.async_entity_ids())):
            hass.states.async_remove(entity_id)

        await setup_input_boolean(hass, {COMPONENT_INPUT_BOOLEAN: CONFIG_INPUT_BOOLEAN})

    if CUSTOM_INPUT_DATETIME:
        for entity_id in list(
                filter(lambda eid: COMPONENT_INPUT_DATETIME == eid.split('.')[0], hass.states.async_entity_ids())):
            hass.states.async_remove(entity_id)

        await setup_input_datetime(hass, {COMPONENT_INPUT_DATETIME: CONFIG_INPUT_DATETIME})

    if CUSTOM_INPUT_NUMBER:
        for entity_id in list(
                filter(lambda eid: COMPONENT_INPUT_NUMBER == eid.split('.')[0], hass.states.async_entity_ids())):
            hass.states.async_remove(entity_id)

        await setup_input_number(hass, {COMPONENT_INPUT_NUMBER: CONFIG_INPUT_NUMBER})

    if CUSTOM_INPUT_TEXT:
        for entity_id in list(
                filter(lambda eid: COMPONENT_INPUT_TEXT == eid.split('.')[0], hass.states.async_entity_ids())):
            hass.states.async_remove(entity_id)
        await setup_input_text(hass, {COMPONENT_INPUT_TEXT: CONFIG_INPUT_TEXT})

    if CUSTOM_INPUT_SELECT:
        for entity_id in list(
                filter(lambda eid: COMPONENT_INPUT_SELECT == eid.split('.')[0], hass.states.async_entity_ids())):
            hass.states.async_remove(entity_id)

        await setup_input_select(hass, {COMPONENT_INPUT_SELECT: CONFIG_INPUT_SELECT})

    if CUSTOM_TIMER:
        for entity_id in list(
                filter(lambda eid: COMPONENT_TIMER == eid.split('.')[0], hass.states.async_entity_ids())):
            hass.states.async_remove(entity_id)

        await setup_timer(hass, {COMPONENT_TIMER: CONFIG_TIMER})

    await create_automations(hass)


async def create_automation(data: dict):
    automation = AutomationConfig(data)
    raw_config = dict(data)
    automation.raw_config = raw_config
    AUTOMATIONS.append(automation)


async def create_automations(hass: HomeAssistant):
    platform = await _get_platform(hass, "automation")

    data = {
        'automation': AUTOMATIONS
    }

    await add_automation(hass, OrderedDict(data), platform)