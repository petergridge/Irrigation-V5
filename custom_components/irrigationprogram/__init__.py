import logging
import asyncio

#-----------Helpers---------------------------
from homeassistant.components.automation import EVENT_AUTOMATION_RELOADED
from homeassistant.const import CONF_ENTITY_ID, CONF_STATE, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.config_validation import string
from .helper import create_automations, create_entities_and_automations, CONFIG_INPUT_BOOLEAN, COMPONENT_INPUT_BOOLEAN, \
    CONFIG_INPUT_DATETIME, COMPONENT_INPUT_DATETIME, CONFIG_INPUT_NUMBER, COMPONENT_INPUT_NUMBER, CONFIG_INPUT_TEXT, \
    COMPONENT_INPUT_TEXT, CONFIG_TIMER, COMPONENT_TIMER, CONFIG_INPUT_SELECT, COMPONENT_INPUT_SELECT
#--------------------------------------

from .const import (
    DOMAIN,
    CONST_SWITCH,
    SWITCH_ID_FORMAT,
    ATTR_RESET,
    )


from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ATTR_ENTITY_ID,
    )

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):

    platforms = config.get(CONST_SWITCH)

    for x in platforms:
        if x.get('platform') == DOMAIN:
            switches = x.get('switches')
            break

#---------Helpers-----------------------------
    CONFIG_INPUT_BOOLEAN.update(config.get(COMPONENT_INPUT_BOOLEAN, {}))
    CONFIG_INPUT_DATETIME.update(config.get(COMPONENT_INPUT_DATETIME, {}))
    CONFIG_INPUT_NUMBER.update(config.get(COMPONENT_INPUT_NUMBER, {}))
    CONFIG_INPUT_TEXT.update(config.get(COMPONENT_INPUT_TEXT, {}))
    CONFIG_INPUT_SELECT.update(config.get(COMPONENT_INPUT_SELECT, {}))
    CONFIG_TIMER.update(config.get(COMPONENT_TIMER, {}))

    async def handle_home_assistant_started_event(event: Event):
        await create_entities_and_automations(hass)

    async def handle_automation_reload_event(event: Event):
        await create_automations(hass)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, handle_home_assistant_started_event)
    hass.bus.async_listen(EVENT_AUTOMATION_RELOADED, handle_automation_reload_event)
#---------------------------------------


    async def async_stop_programs(call):

        for x in switches:
            if x == call.data.get('ignore',''):
                continue

            device = SWITCH_ID_FORMAT.format(x)
            DATA = {ATTR_ENTITY_ID: device}
            await hass.services.async_call(CONST_SWITCH,
                                     SERVICE_TURN_OFF,
                                     DATA)
    """ END async_stop_switches """


    async def async_run_zone(call):

        DATA = {}
        await hass.services.async_call(DOMAIN,
                                 'stop_programs',
                                 DATA)

        await asyncio.sleep(1)

        program = call.data.get('entity_id')
        zone = call.data.get('zone')
        DATA = {ATTR_ENTITY_ID: program, 'zone':zone}
        await hass.services.async_call(DOMAIN,
                                 'set_run_zone',
                                 DATA)

        await asyncio.sleep(1)

        DATA = {ATTR_ENTITY_ID: program}
        await hass.services.async_call(CONST_SWITCH,
                                 SERVICE_TURN_ON,
                                 DATA)

    """ register services """
    hass.services.async_register(DOMAIN,
                                 'stop_programs',
                                 async_stop_programs)
    """ register services """
    hass.services.async_register(DOMAIN,
                                 'run_zone',
                                 async_run_zone)


    return True
