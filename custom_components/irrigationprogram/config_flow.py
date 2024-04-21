"""Config flow."""

from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector as sel

from .const import (
    ATTR_DELAY,
    ATTR_DEVICE_TYPE,
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_INTERLOCK,
    ATTR_IRRIGATION_ON,
    ATTR_MONITOR_CONTROLLER,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REPEAT,
    ATTR_RUN_FREQ,
    ATTR_START,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_ZONE,
    ATTR_ZONES,
    DOMAIN,
)

ATTR_TEMP = "temp"
ATTR_FREQ = "freq"

PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(ATTR_START): sel.EntitySelector({"domain": ["input_datetime", "input_text"]}),
        vol.Optional(ATTR_RUN_FREQ): sel.EntitySelector({"domain": "input_select"}),
        vol.Optional(ATTR_MONITOR_CONTROLLER): sel.EntitySelector(
            {"domain": "binary_sensor"}
        ),
        vol.Optional(ATTR_IRRIGATION_ON): sel.EntitySelector({"domain": "input_boolean"}),
        vol.Optional(ATTR_DEVICE_TYPE, default='generic'): sel.SelectSelector({"options": ["generic", "rainbird"], "translation_key":ATTR_DEVICE_TYPE}),
        vol.Optional(ATTR_DELAY): sel.EntitySelector({"domain": "input_number"}),
        vol.Optional(ATTR_INTERLOCK, default=True): cv.boolean,
    }
)

PROGRAM_ATTR = [
    [True,  ATTR_START, sel.EntitySelector({"domain": ["input_datetime", "input_text"]})],
    [False, ATTR_RUN_FREQ, sel.EntitySelector({"domain": ["input_select","sensor"]})],
    [False, ATTR_MONITOR_CONTROLLER, sel.EntitySelector({"domain": "binary_sensor"})],
    [False, ATTR_IRRIGATION_ON, sel.EntitySelector({"domain": "input_boolean"})],
    [False, ATTR_DEVICE_TYPE, sel.SelectSelector({"options": ["generic", "rainbird"], "translation_key":ATTR_DEVICE_TYPE})],
    [False, ATTR_DELAY, sel.EntitySelector({"domain": "input_number"})],
    [False, ATTR_INTERLOCK,cv.boolean]
]

# Required,attribute,type
ZONE_ATTR = [
    [False, ATTR_ZONE, sel.EntitySelector({"domain": ["switch"]})],
    [False, ATTR_WATER, sel.EntitySelector({"domain": ["sensor","input_number"]})],
    [False, ATTR_WAIT, sel.EntitySelector({"domain": "input_number"})],
    [False, ATTR_REPEAT, sel.EntitySelector({"domain": "input_number"})],
    [False, ATTR_PUMP, sel.EntitySelector({"domain": "switch"})],
    [False, ATTR_FLOW_SENSOR, sel.EntitySelector({"domain": ["sensor","input_number"]})],
    [False, ATTR_WATER_ADJUST, sel.EntitySelector({"domain": ["sensor","input_number"]})],
    [False, ATTR_RUN_FREQ, sel.EntitySelector({"domain": ["input_select","sensor"]})],
    [False, ATTR_RAIN_SENSOR, sel.EntitySelector({"domain": ["binary_sensor","input_boolean"]})],
    [False, ATTR_IGNORE_RAIN_SENSOR, sel.EntitySelector({"domain": "input_boolean"})],
    [False, ATTR_ENABLE_ZONE, sel.EntitySelector({"domain": "input_boolean"})],
]

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)

class IrrigationFlowHandler(config_entries.ConfigFlow):
    """FLow handler."""

    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    VERSION = 4

    def __init__(self) -> None:
        """Initialise."""
        self._errors = {}
        self._data = {}
        self._data["unique_id"] = str(uuid.uuid4())

    def process_schema_row(self, data_schema, attr, default):
        """Process a row of the data schema."""
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
        return data_schema

    async def async_step_import(self, user_input: dict[str, Any]):
        """Handle import."""

        return self.async_create_entry(
            title=user_input.get(CONF_NAME), data=user_input
        )

    async def async_step_user(
        self, user_input=None
    ):
        """Initiate a flow via the user interface."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_NAME].strip() == '':
                errors[CONF_NAME] = "Program name is required"
            if not errors:
                # Input is valid, set data.
                self._data = user_input
                self._data[ATTR_ZONES] = []
                # Return the form of the next step.
                return await self.async_step_zones()
        return self.async_show_form(
            step_id="user", data_schema=PROGRAM_SCHEMA, errors=errors
        )

    async def async_step_zones(self, user_input=None):
        """Add a zone step."""
        errors = {}
        data_schema = {}
        if user_input is not None:
            if user_input == {}:
                #must have at least one zone defined
                if self._data.get(ATTR_ZONES) != []:
                #not data input return to the menu
                    return await self.async_step_menu()
                #at least on zone is required
                errors["base"] = "zone_required"

            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"
            else:
                for zone in self._data.get(ATTR_ZONES):
                    if user_input.get(ATTR_ZONE) == zone.get(ATTR_ZONE):
                        errors[ATTR_ZONE] = "zone_defined"
                        break

            if user_input.get(ATTR_WATER) is None:
                errors[ATTR_WATER] = "mandatory"

            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]

                self._data[ATTR_ZONES].append(zone_data)
                return await self.async_step_menu()

        # build a dict including entered values on error
        if user_input is None:
            default_input = {}
        else:
            default_input = user_input
        for attr in ZONE_ATTR:
            default = default_input.get(attr[1])
            data_schema = self.process_schema_row(data_schema, attr, default)

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_menu(self, user_input=None):
        '''Add or finalise the flow.'''
        xmenu_options = ["zones"]
        xmenu_options.extend(["finalise"])

        return self.async_show_menu(
            step_id="menu",
            menu_options=xmenu_options
        )

    async def async_step_finalise(self, user_input=None):
        """Second step in config flow to add a repo to watch."""
        # User is done adding, create the config entry.
        return self.async_create_entry(
            title=self._data.get(CONF_NAME), data=self._data
        )


#--- Options Flow ----------------------------------------------
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):  # noqa: D102
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    '''Option flow.'''

    VERSION = 4
    def __init__(self, config_entry) -> None:  # noqa: D107
        self.config_entry = config_entry
        self._name = self.config_entry.data.get(CONF_NAME)
        self.zoneselect = None
        if self.config_entry.options == {}:
            self._data = self.config_entry.data
        else:
            self._data = self.config_entry.options

    def process_schema_row(self, data_schema, attr, default):
        """Process a row of the data schema."""
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
        return data_schema

    async def async_step_user(self, user_input=None):
        '''Initial step? work around from HA v2023.11.'''  # noqa: D401
        return

    async def async_step_init(self, user_input=None):
        '''Initial step.'''  # noqa: D401
        if self.config_entry.options == {}:
            data = self.config_entry.data
        else:
            data = self.config_entry.options

        xmenu_options = ["update_program", "update_zone", "add_zone"]
        # only one zone so don't show delete zone option
        if len(data.get(ATTR_ZONES)) > 1:
            xmenu_options.extend(["delete_zone"])
        xmenu_options.extend(["finalise"])
        return self.async_show_menu(
            step_id="user",
            menu_options=xmenu_options,
        )

    async def async_step_finalise(self, user_input=None):
        """Create the program config."""
        newdata = {}
        newdata.update(self._data)

        #the top level of the dictionary needs to change
        #for HA update to trigger, bug?
        if newdata.get('xx') == 'x':
            newdata.update({'xx': 'y'})
        else:
            newdata.update({'xx': 'x'})
        # User is done adding, create the config entry.
        return self.async_create_entry(
            title=self._data.get(CONF_NAME), data=newdata
        )

    async def async_step_update_program(self, user_input=None):
        """Invoked when a user initiates a flow via the user interface."""  # noqa: D401
        errors = {}
        newdata = {}
        newdata.update(self._data)
        data_schema = {}
        if user_input is not None:
            if user_input[CONF_NAME].strip() == '':
                errors[CONF_NAME] = "Program name is required"
            if not errors:
                if newdata.get(ATTR_RUN_FREQ):
                    newdata.pop(ATTR_RUN_FREQ)
                if newdata.get(ATTR_MONITOR_CONTROLLER):
                    newdata.pop(ATTR_MONITOR_CONTROLLER)
                if newdata.get(ATTR_IRRIGATION_ON):
                    newdata.pop(ATTR_IRRIGATION_ON)
                if newdata.get(ATTR_INTERLOCK):
                    newdata.pop(ATTR_INTERLOCK)
                if newdata.get(ATTR_DELAY):
                    newdata.pop(ATTR_DELAY)
                newdata.update(user_input)
                # Return the form of the next step.
                self._data = newdata
                return await self.async_step_init()

        # build the program schema with original data
        for attr in PROGRAM_ATTR:
            default = self._data.get(attr[1])
            data_schema = self.process_schema_row(data_schema, attr, default)

        return self.async_show_form(
            step_id="update_program",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_delete_zone(self, user_input=None):
        '''Delete a zone.'''
        errors = {}
        zones = []
        newdata = {}
        newdata.update(self._data)

        if user_input is not None:
            if user_input == {}:
                #no data provided return to the menu
                return await self.async_step_init()

            # find the position of the zone in the zones.
            zones = newdata[ATTR_ZONES]
            for zonenumber, zone in enumerate(zones):
                friendlyname = zone.get(ATTR_ZONE).split(".")[1]
                if (friendlyname) == user_input.get(ATTR_ZONE):
                    # delete the zone from the list of zones
                    newdata[ATTR_ZONES].pop(zonenumber)
#                    delzone = zone[ATTR_ZONE]
                    break

            self._data = newdata
            return await self.async_step_init()

        # build list of zones
        for zone in self._data.get(ATTR_ZONES):
            zones.append(zone.get(ATTR_ZONE).split(".")[1])
        # define the display schema
        list_schema = vol.Schema({vol.Optional(ATTR_ZONE): vol.In(zones)})

        return self.async_show_form(
            step_id="delete_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone(self, user_input=None):
        '''Update zone.'''
        errors = {}
        zones = []

        if user_input is not None:
            if user_input == {}:
                #no data provided return to the menu
                return await self.async_step_init()

            # Input is valid, set data.
            self.zoneselect = user_input
            # Return the form of the next step.
            return await self.async_step_update_zone_data()

        zonenumber = 0
        for zone in self._data.get(ATTR_ZONES):
            friendlyname = zone.get(ATTR_ZONE)
            zonenumber += 1
            text = (str(zonenumber) + ': ' +friendlyname)
            zones.append(text)

        list_schema = vol.Schema({vol.Optional(ATTR_ZONE): vol.In(zones)})

        return self.async_show_form(
            step_id="update_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone_data(self, user_input=None):
        '''Update zone.'''
        errors = {}
        data_schema = {}
        newdata = {}
        newdata.update(self._data)
        # get the zone position
        for count, zone in enumerate(newdata.get(ATTR_ZONES)):
            if zone.get(ATTR_ZONE) == self.zoneselect.get(ATTR_ZONE).split(':',1)[1].strip():
                this_zone = zone
                zone_pos = count
                break

        if user_input is not None:

            if user_input == {}:
                if len(self._data.get(ATTR_ZONES)) == 1:
                    #at least on zone is required
                    errors["base"] = "zone_required"
                if self._data.get(ATTR_ZONES) != [] and len(self._data.get(ATTR_ZONES)) == 0:
                    #no data, input return to the menu
                    return await self.async_step_init()

            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"
            else:
                this_zone_str = self.zoneselect.get(ATTR_ZONE).split(':',1)[1].strip()
                if user_input.get(ATTR_ZONE) != this_zone_str:
                    for zone in self._data.get(ATTR_ZONES):
                        if user_input.get(ATTR_ZONE) == zone.get(ATTR_ZONE):
                            errors[ATTR_ZONE] = "zone_defined"
                            break

            if user_input.get(ATTR_WATER) is None:
                errors[ATTR_WATER] = "mandatory"

            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                # update with the new data into the list of zones
                newdata.get(ATTR_ZONES)[zone_pos] = zone_data

                self._data = newdata
                return await self.async_step_init()

        # build a dict including original values
        for attr in ZONE_ATTR:
            if user_input is not None:
                #an error has been raised show entered data
                default = user_input.get(attr[1])
            else:
                #present original data
                default = this_zone.get(attr[1])

            data_schema = self.process_schema_row(data_schema, attr, default)

        return self.async_show_form(
            step_id="update_zone_data",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_add_zone(self, user_input=None):
        '''Add zone.'''
        errors = {}
        data_schema = {}
        newdata = {}
        newdata.update(self._data)
        if user_input is not None:
            if user_input == {}:
                #not data input return to the menu
                return await self.async_step_init()

            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"
            else:
                for zone in self._data.get(ATTR_ZONES):
                    if user_input.get(ATTR_ZONE) == zone.get(ATTR_ZONE):
                        errors[ATTR_ZONE] = "zone_defined"
                        break

            if user_input.get(ATTR_WATER) is None:
                errors[ATTR_WATER] = "mandatory"

            if not errors:
                if user_input == {}:
                    #not data input return to the menu
                    return await self.async_step_init()
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                newdata[ATTR_ZONES].append(zone_data)

                self._data = newdata
                return await self.async_step_init()

        # build a dict including original values
        if user_input is None:
            default_input = {}
        else:
            default_input = user_input
        for attr in ZONE_ATTR:
            default = default_input.get(attr[1])
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

        return self.async_show_form(
            step_id="add_zone",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

