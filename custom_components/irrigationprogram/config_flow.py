""" Config flow """

from __future__ import annotations

import logging
from typing import Any, Optional #, cast
import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector as sel
from .const import (
    ATTR_DELAY,
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_IRRIGATION_ON,
    ATTR_MONITOR_CONTROLLER,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REPEAT,
    ATTR_RUN_FREQ,
    ATTR_SHOW_CONFIG,
    ATTR_START,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_ZONE,
    ATTR_ZONE_GROUP,
    ATTR_ZONES,
    DOMAIN,
)

PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(ATTR_START): sel.EntitySelector({"domain": "input_datetime"}),
        vol.Optional(ATTR_RUN_FREQ): sel.EntitySelector({"domain": "input_select"}),
        vol.Optional(ATTR_MONITOR_CONTROLLER): sel.EntitySelector(
            {"domain": "binary_sensor"}
        ),
        vol.Optional(ATTR_IRRIGATION_ON): sel.EntitySelector({"domain": "input_boolean"}),
        vol.Optional(ATTR_SHOW_CONFIG): sel.EntitySelector({"domain": "input_boolean"}),
        vol.Optional(ATTR_DELAY): sel.EntitySelector({"domain": "input_number"}),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): sel.EntitySelector({"domain": "switch"}),
        vol.Required(ATTR_WATER): sel.EntitySelector({"domain": "input_number"}),
        vol.Optional(ATTR_WAIT): sel.EntitySelector({"domain": "input_number"}),
        vol.Optional(ATTR_REPEAT): sel.EntitySelector({"domain": "input_number"}),
        vol.Optional(ATTR_PUMP): sel.EntitySelector({"domain": "switch"}),
        vol.Optional(ATTR_FLOW_SENSOR): sel.EntitySelector({"domain": ["sensor","input_number"]}),
        vol.Optional(ATTR_WATER_ADJUST): sel.EntitySelector({"domain": ["sensor","input_number"]}),
        vol.Optional(ATTR_RUN_FREQ): sel.EntitySelector({"domain": "input_select"}),
        vol.Optional(ATTR_RAIN_SENSOR): sel.EntitySelector({"domain": ["binary_sensor","input_boolean"]}),
        vol.Optional(ATTR_ZONE_GROUP): sel.EntitySelector({"domain": "input_text"}),
        vol.Optional(ATTR_IGNORE_RAIN_SENSOR): sel.EntitySelector({"domain": "input_boolean"}),
        vol.Optional(ATTR_ENABLE_ZONE): sel.EntitySelector({"domain": "input_boolean"}),
        vol.Optional("add_another"): cv.boolean,
    }
)

PROGRAM_ATTR = [
    [True, ATTR_START, sel.EntitySelector({"domain": "input_datetime"})],
    [False, ATTR_RUN_FREQ, sel.EntitySelector({"domain": "input_select"})],
    [False, ATTR_MONITOR_CONTROLLER, sel.EntitySelector({"domain": "sensor"})],
    [False, ATTR_IRRIGATION_ON, sel.EntitySelector({"domain": "input_boolean"})],
    [False, ATTR_SHOW_CONFIG, sel.EntitySelector({"domain": "input_boolean"})],
    [False, ATTR_DELAY, sel.EntitySelector({"domain": "input_number"})],
]

# Required,attribute,type
ZONE_ATTR = [
    [True, ATTR_ZONE, sel.EntitySelector({"domain": "switch"})],
    [True, ATTR_WATER, sel.EntitySelector({"domain": "input_number"})],
    [False, ATTR_WAIT, sel.EntitySelector({"domain": "input_number"})],
    [False, ATTR_REPEAT, sel.EntitySelector({"domain": "input_number"})],
    [False, ATTR_PUMP, sel.EntitySelector({"domain": "switch"})],
    [False, ATTR_FLOW_SENSOR, sel.EntitySelector({"domain": ["sensor","input_number"]})],
    [False, ATTR_WATER_ADJUST, sel.EntitySelector({"domain": ["sensor","input_number"]})],
    [False, ATTR_RUN_FREQ, sel.EntitySelector({"domain": "input_select"})],
    [False, ATTR_RAIN_SENSOR, sel.EntitySelector({"domain": ["binary_sensor","input_boolean"]})],
    [False, ATTR_ZONE_GROUP, sel.EntitySelector({"domain": "input_text"})],
    [False, ATTR_IGNORE_RAIN_SENSOR, sel.EntitySelector({"domain": "input_boolean"})],
    [False, ATTR_ENABLE_ZONE, sel.EntitySelector({"domain": "input_boolean"})],
]

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)

class IrrigationFlowHandler(config_entries.ConfigFlow):
    """FLow handler"""

    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    VERSION = 1

    def __init__(self):
        self._errors = {}
        self._data = {}
        self._data["unique_id"] = str(uuid.uuid4())
        self.data = {}

    async def async_step_import(self, user_input: dict[str, Any]):
        """Handle import."""

        #validate the imported data
        #loop through the user_input and validate that each object
        for item, value in user_input.items():
            error = False
            if item != 'name':
                #is it a valid object?
                if item == 'zones':
                    for zattr in value:
                        for zitem, zvalue in zattr:
                            if self.hass.states.async_available(zvalue):
                                _LOGGER.error('Config item %s:%s is not a valid entry',zitem,zvalue)
                                error = True
                else:
                    if self.hass.states.async_available(value):
                        _LOGGER.error('Config item %s:%s is not a valid entry',item,value)
                        error = True
        if error is True:
            _LOGGER.error('Only irrigation V4 configuration can be imported')
            return self.async_abort(reason="import_error")

        return self.async_create_entry(
            title=user_input.get(CONF_NAME), data=user_input
        )

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ):  # pylint: disable=unused-argument
        """Invoked when a user initiates a flow via the user interface."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not errors:
                # Input is valid, set data.
                self.data = user_input
                self.data[ATTR_ZONES] = []
                # Return the form of the next step.
                return await self.async_step_zones()
        return self.async_show_form(
            step_id="user", data_schema=PROGRAM_SCHEMA, errors=errors
        )

    async def async_step_zones(self, user_input: Optional[dict[str, Any]] = None):
        """Second step in config flow to add a repo to watch."""
        errors: dict[str, str] = {}
        if user_input is not None:

            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    if attr != "add_another":
                        zone_data[attr] = user_input[attr]

                self.data[ATTR_ZONES].append(zone_data)

                # If user ticked the box show this form again so
                # they can add an additional zone.
                if user_input.get("add_another", False):
                    return await self.async_step_zones()

                # User is done adding repos, create the config entry.
                return self.async_create_entry(
                    title=self.data.get(CONF_NAME), data=self.data
                )

        return self.async_show_form(
            step_id="zones", data_schema=ZONE_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    ''' option flow'''
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._data = {}
        self._data["unique_id"] = config_entry.options.get("unique_id")
        self._name = self.config_entry.data.get(CONF_NAME)
        self.zoneselect = None
        if self.config_entry.options == {}:
            self.data = self.config_entry.data
        else:
            self.data = self.config_entry.options

    async def async_step_init(self, user_input=None):
        '''initial step'''
        if self.config_entry.options == {}:
            data = self.config_entry.data
        else:
            data = self.config_entry.options

        if len(data.get(ATTR_ZONES)) > 1:
            return self.async_show_menu(
                step_id="user",
                menu_options=[
                    "update_program",
                    "update_zone",
                    "delete_zone",
                    "add_zone",
                ],
            )
        # only one zone so don't show delete zone option
        return self.async_show_menu(
            step_id="user",
            menu_options=["update_program", "update_zone", "add_zone"],
        )

    async def async_step_update_program(self, user_input=None):
        """Invoked when a user initiates a flow via the user interface."""
        errors = {}
        newdata = {}
        data_schema = {}
        if user_input is not None:
            if not errors:
                # build the new set of data, note conf_name is not in the update schema
                # and zones are updated in another menu item
                newdata.update({CONF_NAME: self.data.get(CONF_NAME)})
                newdata.update(user_input)
                newdata.update({ATTR_ZONES: self.data.get(ATTR_ZONES)})
                # Return the form of the next step.
                return self.async_create_entry(title=self._name, data=newdata)

        # build the program schema with original data
        for attr in PROGRAM_ATTR:
            default = self.data.get(attr[1])
            if default is not None:
                if attr[0] is True:
                    data_schema[
                        vol.Required(
                            attr[1],
                            description={"suggested_value": default}
                        )
                    ] = attr[2]
                else:
                    data_schema[
                        vol.Optional(
                            attr[1],
                            description={"suggested_value": default}
                        )
                    ] = attr[2]
            else:
                data_schema[vol.Optional(attr[1])] = attr[2]

        return self.async_show_form(
            step_id="update_program",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_delete_zone(self, user_input=None):
        '''delete a zone'''
        errors = {}
        zones = []

        if user_input is not None:
            if user_input != {}:
                # find the position of the zone in the zones.
                zones = self.data[ATTR_ZONES]
                zonenumber = 0
                for zone in zones:
                    zonenumber += 1
                    friendlyname = self.hass.states.get(zone.get(ATTR_ZONE)).attributes.get('friendly_name')
                    if ('zone ' +  str(zonenumber) + ':' +friendlyname) == user_input.get(ATTR_ZONE):
                        # delete the zone from the list of zones
                        self.data[ATTR_ZONES].pop(zonenumber-1)
                        break
                newdata = {}
                newdata.update(self.data)
                # a dodgy way to force the update
                if newdata.get('xx') == 'x':
                    newdata.update({'xx': 'y'})
                else:
                    newdata.update({'xx': 'x'})
                return self.async_create_entry(title=self._name, data=newdata)

        # build list of zones
        zonenumber = 0
        for zone in self.data.get(ATTR_ZONES):
            friendlyname = self.hass.states.get(zone.get(ATTR_ZONE)).attributes.get('friendly_name')
            zonenumber += 1
            text = ('zone ' +  str(zonenumber) + ':' +friendlyname)
            zones.append(text)
        # define the display schema
        list_schema = vol.Schema({vol.Optional(ATTR_ZONE): vol.In(zones)})

        return self.async_show_form(
            step_id="delete_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone(self, user_input=None):
        '''update zone'''
        errors = {}
        zones = []

        if user_input is not None:
            if user_input != {}:
                # Input is valid, set data.
                self.zoneselect = user_input
                # Return the form of the next step.
                return await self.async_step_update_zone_data()

        zonenumber = 0
        for zone in self.data.get(ATTR_ZONES):
            friendlyname = self.hass.states.get(zone.get(ATTR_ZONE)).attributes.get('friendly_name')
            zonenumber += 1
            text = ('zone ' +  str(zonenumber) + ':' +friendlyname)
            zones.append(text)

        list_schema = vol.Schema({vol.Optional(ATTR_ZONE): vol.In(zones)})

        return self.async_show_form(
            step_id="update_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone_data(self, user_input=None):
        '''update zone'''
        errors = {}
        data_schema = {}

        # get the zone position
        zones = self.data.get(ATTR_ZONES)
        zone_pos = 0
        for zone in zones:
            friendlyname = self.hass.states.get(zone.get(ATTR_ZONE)).attributes.get('friendly_name')
            if friendlyname == self.zoneselect.get(ATTR_ZONE).split(':',1)[1]:
                this_zone = zone
                break
            zone_pos += 1

        if user_input is not None:
            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                # update with the new data into the list of zones
                self.data.get(ATTR_ZONES)[zone_pos] = zone_data
                # a dodgy way to force the update
                newdata = {}
                newdata.update(self.data)
                if newdata.get('xx') == 'x':
                    newdata.update({'xx': 'y'})
                else:
                    newdata.update({'xx': 'x'})
                # User is done, create the config entry.
                return self.async_create_entry(title=self._name, data=newdata)

        # build a dict including original values
        for attr in ZONE_ATTR:
            default = this_zone.get(attr[1])
            if default is not None:
                if attr[0] is True:
                    data_schema[
                        vol.Required(
                            attr[1],
                            description={"suggested_value": default}
                        )
                    ] = attr[2]
                else:
                    data_schema[
                        vol.Optional(
                            attr[1],
                            description={"suggested_value": default}
                        )
                    ] = attr[2]
            else:
                data_schema[vol.Optional(attr[1])] = attr[2]

        return self.async_show_form(
            step_id="update_zone_data",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_add_zone(self, user_input=None):
        '''add zone'''
        errors = {}
        if user_input is not None:
            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    if attr != "add_another":
                        zone_data[attr] = user_input[attr]
                self.data[ATTR_ZONES].append(zone_data)
                # If user ticked the box show this form again
                # to add an additional zone.
                if user_input.get("add_another", False):
                    return await self.async_step_add_zone()
                # User is done adding, create the config entry.
                newdata = {}
                newdata.update(self.data)
                # a dodgy way to force the update
                if newdata.get('xx') == 'x':
                    newdata.update({'xx': 'y'})
                else:
                    newdata.update({'xx': 'x'})
                return self.async_create_entry(title=self._name, data=newdata)
                #return await self.async_step_update_program(newdata)

        return self.async_show_form(
            step_id="add_zone", data_schema=ZONE_SCHEMA, errors=errors
        )
