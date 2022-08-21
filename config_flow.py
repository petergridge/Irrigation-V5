""" Config flow """
from collections import OrderedDict
from homeassistant.core import callback
import voluptuous as vol
from homeassistant import config_entries
import uuid

from .const import (
    DOMAIN,
    ATTR_START,
    ATTR_HIDE_CONFIG,
    ATTR_RUN_FREQ,
    ATTR_IRRIGATION_ON,
    ATTR_RAIN_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_ENABLE_ZONE,
    ATTR_ZONES,
    ATTR_ZONE,
    ATTR_ZONE_GROUP,
    ATTR_PUMP,
    ATTR_FLOW_SENSOR,
    ATTR_WATER,
    ATTR_DELAY,
    ATTR_WATER_ADJUST,
    ATTR_WAIT,
    ATTR_REPEAT,
    ATTR_REMAINING,
    ATTR_LAST_RAN,
    ATTR_MONITOR_CONTROLLER,
    ATTR_RESET,

    DFLT_IRRIGATION_ON,
    DFLT_START,
    DFLT_IGNORE_RAIN_SENSOR,
    DFLT_HIDE_CONFIG,
    DFLT_REPEAT,
    DFLT_WATER,
    DFLT_WAIT,
    DFLT_DELAY,
    DFLT_FLOW_SENSOR,
    DFLT_WATER_ADJUST,
    DFLT_ENABLE_ZONE,
    DFLT_ZONE_GROUP,
    DFLT_WATER_INITIAL_M,
    DFLT_WATER_MAX_M,
    DFLT_WATER_STEP_M,
    DFLT_WATER_INITIAL_I,
    DFLT_WATER_MAX_I,
    DFLT_WATER_STEP_I,
    DFLT_WAIT_MAX,
    DFLT_REPEAT_MAX,
    DFLT_WATER_INITIAL_T,
    DFLT_WATER_MAX_T,
    DFLT_WATER_STEP_T,
    DFLT_RUN_FREQ,)

from homeassistant.const import (
#    EVENT_HOMEASSISTANT_START,
#    CONF_SWITCHES,
#    CONF_UNIQUE_ID,
    CONF_NAME,
    CONF_FRIENDLY_NAME,
#    SERVICE_TURN_OFF,
#    SERVICE_TURN_ON,
)

@config_entries.HANDLERS.register(DOMAIN)
class AnniversariesFlowHandler(config_entries.ConfigFlow):
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self._errors = {}
        self._data = {}
        self._data["unique_id"] = str(uuid.uuid4())

    async def async_step_user(self, user_input=None):   # pylint: disable=unused-argument
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
 #           if is_not_date(user_input[CONF_DATE], user_input[CONF_ONE_TIME]):
 #               self._errors["base"] = "invalid_date"
 #           if self._errors == {}:
 #               self.init_info = user_input
 #               return await self.async_step_icons()
        return await self._show_program_form(user_input)

    async def async_step_icons(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=self._data["name"], data=self._data)
        return await self._show_zone_form(user_input)

    async def _show_program_form(self, user_input):
        name = ""
        if user_input is not None:
            if CONF_NAME in user_input:
                name = user_input[CONF_NAME]
            if CONF_FRIENDLY_NAME in user_input:
                friendly_name = user_input[CONF_FRIENDLY_NAME]
            if ATTR_RUN_FREQ in user_input:
                run_freq = user_input[ATTR_RUN_FREQ]
            if ATTR_MONITOR_CONTROLLER in user_input:
                monitor_controller = user_input[ATTR_MONITOR_CONTROLLER]
            if ATTR_START in user_input:
                start = user_input[ATTR_START]
            if ATTR_IRRIGATION_ON in user_input:
                irrigation_0n = user_input[ATTR_IRRIGATION_ON]
            if ATTR_HIDE_CONFIG in user_input:
                hide_config = user_input[ATTR_HIDE_CONFIG]
            if ATTR_DELAY in user_input:
                delay = user_input[ATTR_DELAY]
            if ATTR_RESET in user_input:
                reset = user_input[ATTR_RESET]


        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_NAME, default=name)] = str
        data_schema[vol.Optional(CONF_FRIENDLY_NAME)}
        data_schema[vol.Optional(ATTR_RUN_FREQ)}
        data_schema[vol.Optional(ATTR_MONITOR_CONTROLLER)]]
        data_schema[vol.Optional(ATTR_START, default=DFLT_START)]
        data_schema[vol.Optional(ATTR_IRRIGATION_ON, default=DFLT_IRRIGATION_ON)]
        data_schema[vol.Optional(ATTR_HIDE_CONFIG, default=DFLT_HIDE_CONFIG)]
        data_schema[vol.Optional(ATTR_DELAY)]
        data_schema[vol.Optional(ATTR_RESET,default=False)]


       return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema), errors=self._errors)

    async def _show_zone_form(self, user_input):
#        icon_normal = DEFAULT_ICON_NORMAL
#        icon_today = DEFAULT_ICON_TODAY
#        days_as_soon = DEFAULT_SOON
#        icon_soon = DEFAULT_ICON_SOON
#        if user_input is not None:
#            if CONF_ICON_NORMAL in user_input:
#                icon_normal = user_input[CONF_ICON_NORMAL]
#            if CONF_ICON_TODAY in user_input:
#                icon_today = user_input[CONF_ICON_TODAY]
#            if CONF_SOON in user_input:
#                days_as_soon = user_input[CONF_SOON]
#            if CONF_ICON_SOON in user_input:
#                icon_soon = user_input[CONF_ICON_SOON]
#        data_schema = OrderedDict()
#        data_schema[vol.Required(CONF_ICON_NORMAL, default=icon_normal)] = str
#        data_schema[vol.Required(CONF_ICON_TODAY, default=icon_today)] = str
#        data_schema[vol.Required(CONF_SOON, default=days_as_soon)] = int
#        data_schema[vol.Required(CONF_ICON_SOON, default=icon_soon)] = str
 #       return self.async_show_form(step_id="icons", data_schema=vol.Schema(data_schema), errors=self._errors)
        return True

    async def async_step_import(self, user_input):  # pylint: disable=unused-argument
        """Import a config entry.
        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="configuration.yaml", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        if config_entry.options.get("unique_id", None) is not None:
            return OptionsFlowHandler(config_entry)
        else:
            return EmptyOptions(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._data = {}
        self._data["unique_id"] = config_entry.options.get("unique_id")

    async def async_step_init(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
#            if is_not_date(user_input[CONF_DATE], user_input[CONF_ONE_TIME]):
#                self._errors["base"] = "invalid_date"
#            if self._errors == {}:
#                return await self.async_step_icons()
        return await self._show_init_form(user_input)

    async def async_step_icons(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)
        return await self._show_zone_form(user_input)

    async def _show_init_form(self, user_input):
        data_schema = OrderedDict()
        run_freq = self.config_entry.options.get(ATTR_RUN_FREQ)
        if run_freq is None:
            run_freq = DFLT_RUN_FREQ
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_NAME, default=name)] = str
        data_schema[vol.Optional(CONF_FRIENDLY_NAME)] = str
        data_schema[vol.Optional(ATTR_RUN_FREQ)] = str
        data_schema[vol.Optional(ATTR_MONITOR_CONTROLLER)]] = str
        data_schema[vol.Optional(ATTR_START, default=DFLT_START)] = str
        data_schema[vol.Optional(ATTR_IRRIGATION_ON, default=DFLT_IRRIGATION_ON)] = str
        data_schema[vol.Optional(ATTR_HIDE_CONFIG, default=DFLT_HIDE_CONFIG)] = str
        data_schema[vol.Optional(ATTR_DELAY)] = str
        data_schema[vol.Optional(ATTR_RESET,default=False)] = bool

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=self._errors
        )

    async def _show_zone_form(self, user_input):
#        data_schema = OrderedDict()
#        data_schema[vol.Required(CONF_ICON_NORMAL,default=self.config_entry.options.get(CONF_ICON_NORMAL),)] = str
#        data_schema[vol.Required(CONF_ICON_TODAY,default=self.config_entry.options.get(CONF_ICON_TODAY),)] = str
#        data_schema[vol.Required(CONF_SOON,default=self.config_entry.options.get(CONF_SOON),)] = int
#        data_schema[vol.Required(CONF_ICON_SOON,default=self.config_entry.options.get(CONF_ICON_SOON),)] = str
#        return self.async_show_form(step_id="icons", data_schema=vol.Schema(data_schema), errors=self._errors)
        return True

class EmptyOptions(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry