"""Config flow."""

from __future__ import annotations

from datetime import datetime
import logging
import uuid
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector as sel,
)
from homeassistant.util import slugify

from . import exclude
from .const import (
    ATTR_CARD_YAML,
    ATTR_DEVICE_TYPE,
    ATTR_FLOW_SENSOR,
    ATTR_INTERLOCK,
    ATTR_LATENCY,
    ATTR_MIN_SEC,
    ATTR_PARALLEL,
    ATTR_PUMP,
    ATTR_RAIN_BEHAVIOUR,
    ATTR_RAIN_DELAY,
    ATTR_RAIN_SENSOR,
    ATTR_START_LATENCY,
    ATTR_START_TYPE,
    ATTR_WATER_ADJUST,
    ATTR_WATER_MAX,
    ATTR_WATER_SOURCE,
    ATTR_WATER_STEP,
    ATTR_ZONE,
    ATTR_ZONE_DELAY_MAX,
    ATTR_ZONE_ORDER,
    ATTR_ZONES,
    DOMAIN,
)
from .utils import bubble_sort

OPTIONS_DAYS_GROUPED: list = ["Wed,Sat", "Thu,Sun"]
OPTIONS_DAYS_OF_WEEK: list = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
OPTIONS_DAYS: list = ["1", "2", "3", "4", "5"]

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class IrrigationFlowHandler(config_entries.ConfigFlow):
    """FLow handler."""

    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    VERSION = 7

    def __init__(self) -> None:
        """Initialise."""
        self._errors = {}
        self._data = {}
        self._unique_id = str(uuid.uuid4())
        self._data["unique_id"] = self._unique_id
        self._data[ATTR_ZONES] = []
        self._exclude = []
        self.zoneselect = None

    async def async_step_user(self, user_input=None):
        """Initiate a flow via the user interface."""
        self._exclude = exclude(self.hass)
        for zone in self._data.get(ATTR_ZONES, []):
            self._exclude.append(zone.get(ATTR_ZONE))

        errors: dict[str, str] = {}
        if user_input is not None:
            # validate freq options
            # 1 or 'mon,tue,fri' formats are valid
            # if list must be in mon, tue, wed, thu, fri, sat, sun
            # if not list must be numeric or mon, tue, wed, thu, fri, sat, sun

            cleanoptions = []

            for option in user_input.get("freq_options"):
                try:
                    if isinstance(int(option), int):
                        cleanoptions.append(option)
                        continue
                except ValueError:
                    optionlist = (
                        option.replace(" ", "")
                        .replace("\n", "")
                        .replace("'", "")
                        .replace('"', "")
                        .strip("[]'")
                        .split(",")
                    )
                    optionlist = [x.capitalize() for x in optionlist]
                    if len(optionlist) > 1:
                        for item in optionlist:
                            if item.strip() not in OPTIONS_DAYS_OF_WEEK:
                                errors["freq_options"] = "invalid_days_group"
                                break
                        else:
                            cleanoptions.append(", ".join(item))
                            continue
                    if optionlist[0] in OPTIONS_DAYS_OF_WEEK:
                        cleanoptions.append(optionlist[0])
                        continue

                    errors["freq_options"] = "invalid_option"
                    break

            user_input["freq_options"] = cleanoptions

            if not cleanoptions:
                errors["freq_options"] = "mandatory"

            if not errors:
                # Input is valid, set data.
                for attr in user_input:
                    self._data[attr] = user_input[attr]
                self._data[ATTR_START_TYPE] = self._data.get(
                    ATTR_START_TYPE, "selector"
                )
                self._data[ATTR_INTERLOCK] = self._data.get(ATTR_INTERLOCK, "strict")
                # Return the form of the next step.
                if len(self._data.get(ATTR_ZONES, [])) == 0:
                    return await self.async_step_add_zone()
                return await self.async_step_menu()

        # build a dict including entered values on error
        if user_input:
            default_input = user_input
        elif self._data:
            default_input = self._data
        else:
            default_input = {}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    description={"suggested_value": default_input.get(CONF_NAME, None)},
                ): str,
                vol.Optional(
                    "freq",
                    description={"suggested_value": default_input.get("freq", True)},
                ): cv.boolean,
                vol.Required(
                    "freq_options",
                    description={
                        "suggested_value": default_input.get(
                            "freq_options", OPTIONS_DAYS
                        )
                    },
                ): sel.SelectSelector(
                    {
                        "options": OPTIONS_DAYS
                        + OPTIONS_DAYS_OF_WEEK
                        + OPTIONS_DAYS_GROUPED,
                        "multiple": True,
                        "custom_value": True,
                        "translation_key": "freq_options",
                    }
                ),
                vol.Optional(
                    ATTR_DEVICE_TYPE,
                    default=default_input.get(ATTR_DEVICE_TYPE, "generic"),
                ): sel.SelectSelector(
                    {
                        "options": ["generic", "rainbird", "bhyve"],
                        "translation_key": ATTR_DEVICE_TYPE,
                    }
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_menu(self, user_input=None):
        """Add or finalise the flow."""
        self._exclude = exclude(self.hass)
        for zone in self._data.get(ATTR_ZONES, []):
            self._exclude.append(zone.get(ATTR_ZONE))

        xmenu_options = ["user", "add_zone"]
        if len(self._data.get(ATTR_ZONES, [])) > 0:
            xmenu_options.extend(["update_zone"])
        if len(self._data.get(ATTR_ZONES, [])) > 1:
            xmenu_options.extend(["delete_zone"])
        xmenu_options.extend(["advanced", "finalise"])

        return self.async_show_menu(step_id="menu", menu_options=xmenu_options)

    async def async_step_add_zone(self, user_input=None):
        """Add a zone step."""
        errors = {}
        if user_input is not None:
            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"

            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                # add zone to the exclusion list
                self._exclude.append(user_input.get(ATTR_ZONE))

                if self._data.get(ATTR_ZONES, []) == []:
                    # first zone
                    self._data[ATTR_ZONES] = []
                self._data[ATTR_ZONES].append(zone_data)
                return await self.async_step_menu()

        # build a dict including entered values on error
        if user_input is None:
            default_input = {}
        else:
            default_input = user_input

        default_order = (
            len(self._data.get(ATTR_ZONES, [])) + 1
        ) * 10  # increment by 10

        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_ZONE,
                    description={"suggested_value": default_input.get(ATTR_ZONE)},
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    "freq",
                    description={"suggested_value": default_input.get("freq", False)},
                ): cv.boolean,
                vol.Optional(
                    "eco",
                    description={"suggested_value": default_input.get("eco", False)},
                ): cv.boolean,
                vol.Optional(
                    ATTR_PUMP,
                    description={"suggested_value": default_input.get(ATTR_PUMP)},
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_FLOW_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_FLOW_SENSOR)
                    },
                ): sel.EntitySelector(
                    {"domain": ["sensor"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_WATER_ADJUST,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_ADJUST)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["sensor", "input_number"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_RAIN_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_RAIN_SENSOR)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_WATER_SOURCE,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_SOURCE)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_ZONE_ORDER,
                    description={
                        "suggested_value": default_input.get(
                            ATTR_ZONE_ORDER, default_order
                        )
                    },
                ): sel.NumberSelector({"min": 1, "max": 999, "mode": "box"}),
            }
        )

        return self.async_show_form(
            step_id="add_zone",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_delete_zone(self, user_input=None):
        """Delete a zone."""
        errors = {}

        if user_input is not None:
            if user_input == {}:
                # no data provided return to the menu
                return await self.async_step_menu()

            zones = [zone[ATTR_ZONE] for zone in self._data[ATTR_ZONES]]
            self._data[ATTR_ZONES].pop(zones.index(user_input.get(ATTR_ZONE)))
            return await self.async_step_menu()

        # build list of zones
        zones = [zone[ATTR_ZONE] for zone in self._data[ATTR_ZONES]]
        # build the options list
        optionslist = []
        for zone in zones:
            try:
                optionslist.append(
                    {"label": self.hass.states.get(zone).name, "value": zone}
                )
            except:
                optionslist.append({"label": zone + " offline!", "value": zone})

        list_schema = vol.Schema(
            {
                vol.Optional(ATTR_ZONE): sel.SelectSelector(
                    {
                        "options": optionslist,
                    }
                )
            }
        )
        return self.async_show_form(
            step_id="delete_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone(self, user_input=None):
        """List zones for Update."""
        errors = {}

        if user_input is not None:
            if user_input == {}:
                # no data provided return to the menu
                return await self.async_step_menu()
            # Input is valid, set data.
            self.zoneselect = user_input
            # Return the form of the next step.
            return await self.async_step_update_zone_data()

        # sort and display the selection list
        sortedzones = bubble_sort(self._data.get(ATTR_ZONES))
        # build list of zones
        zones = [zone[ATTR_ZONE] for zone in sortedzones]
        # build the options list
        optionslist = []
        for zone in zones:
            try:
                optionslist.append(
                    {"label": self.hass.states.get(zone).name, "value": zone}
                )
            except:
                optionslist.append({"label": zone + " offline!", "value": zone})

        list_schema = vol.Schema(
            {
                vol.Optional(ATTR_ZONE): sel.SelectSelector(
                    {
                        "options": optionslist,
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="update_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone_data(self, user_input=None):
        """Update zone."""
        errors = {}
        newdata = {}
        newdata.update(self._data)
        # get the zone position
        for count, zone in enumerate(newdata.get(ATTR_ZONES)):
            if zone.get(ATTR_ZONE) == self.zoneselect.get(ATTR_ZONE):
                this_zone = zone
                zone_pos = count
                break
        if user_input is not None:
            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"

            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                # update with the new data into the list of zones
                newdata.get(ATTR_ZONES)[zone_pos] = zone_data
                self._data = newdata
                return await self.async_step_update_zone()

        if user_input:
            default_input = user_input
        elif self._data:
            default_input = this_zone
        else:
            default_input = {}
        zone_exclude = []
        zone_exclude.extend(self._exclude)
        zone_exclude.pop(zone_exclude.index(this_zone.get(ATTR_ZONE)))
        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_ZONE,
                    description={"suggested_value": default_input.get(ATTR_ZONE)},
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": zone_exclude}
                ),
                vol.Optional(
                    "freq",
                    description={"suggested_value": default_input.get("freq", False)},
                ): cv.boolean,
                vol.Optional(
                    "eco",
                    description={"suggested_value": default_input.get("eco", False)},
                ): cv.boolean,
                vol.Optional(
                    ATTR_PUMP,
                    description={"suggested_value": default_input.get(ATTR_PUMP)},
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_FLOW_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_FLOW_SENSOR)
                    },
                ): sel.EntitySelector(
                    {"domain": ["sensor"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_WATER_ADJUST,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_ADJUST)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["sensor", "input_number"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_RAIN_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_RAIN_SENSOR)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_WATER_SOURCE,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_SOURCE)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_ZONE_ORDER,
                    description={
                        "suggested_value": default_input.get(ATTR_ZONE_ORDER, 10)
                    },
                ): sel.NumberSelector({"min": 1, "max": 999, "mode": "box"}),
            }
        )

        return self.async_show_form(
            step_id="update_zone_data",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_advanced(self, user_input=None):
        """Add a zone step."""
        errors = {}
        if user_input is not None:
            if not errors:
                self._data[ATTR_INTERLOCK] = user_input[ATTR_INTERLOCK]
                self._data[ATTR_START_TYPE] = user_input[ATTR_START_TYPE]
                self._data[ATTR_RAIN_BEHAVIOUR] = user_input[ATTR_RAIN_BEHAVIOUR]
                self._data[ATTR_WATER_MAX] = user_input[ATTR_WATER_MAX]
                self._data[ATTR_WATER_STEP] = user_input[ATTR_WATER_STEP]
                self._data[ATTR_ZONE_DELAY_MAX] = user_input[ATTR_ZONE_DELAY_MAX]
                self._data[ATTR_LATENCY] = user_input[ATTR_LATENCY]
                self._data[ATTR_START_LATENCY] = user_input[ATTR_START_LATENCY]
                self._data[ATTR_PARALLEL] = user_input[ATTR_PARALLEL]
                self._data[ATTR_CARD_YAML] = user_input[ATTR_CARD_YAML]
                self._data[ATTR_RAIN_DELAY] = user_input[ATTR_RAIN_DELAY]
                return await self.async_step_menu()

        if user_input:
            default_input = user_input
        elif self._data:
            default_input = self._data
        else:
            default_input = {}

        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_INTERLOCK,
                    description={
                        "suggested_value": default_input.get(ATTR_INTERLOCK, "strict")
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["strict", "loose", "off"],
                        "translation_key": ATTR_INTERLOCK,
                    }
                ),
                vol.Optional(
                    ATTR_START_TYPE,
                    description={
                        "suggested_value": default_input.get(
                            ATTR_START_TYPE, "selector"
                        )
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["selector", "multistart", "sunrise", "sunset"],
                        "translation_key": ATTR_START_TYPE,
                    }
                ),
                vol.Optional(
                    ATTR_RAIN_BEHAVIOUR,
                    description={
                        "suggested_value": default_input.get(
                            ATTR_RAIN_BEHAVIOUR, "stop"
                        )
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["stop", "continue"],
                        "translation_key": ATTR_RAIN_BEHAVIOUR,
                    }
                ),
                vol.Optional(
                    ATTR_MIN_SEC,
                    description={
                        "suggested_value": default_input.get(ATTR_MIN_SEC, "minutes")
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["minutes", "seconds"],
                        "translation_key": ATTR_MIN_SEC,
                    }
                ),
                vol.Optional(
                    ATTR_WATER_MAX,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_MAX, 30)
                    },
                ): sel.NumberSelector({"min": 1, "max": 9999, "mode": "box"}),
                vol.Optional(
                    ATTR_WATER_STEP,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_STEP, 1)
                    },
                ): sel.NumberSelector({"min": 1, "max": 100, "mode": "box"}),
                vol.Optional(
                    ATTR_ZONE_DELAY_MAX,
                    description={
                        "suggested_value": default_input.get(ATTR_ZONE_DELAY_MAX, 120)
                    },
                ): sel.NumberSelector({"min": 1, "max": 9999, "mode": "box"}),
                vol.Optional(
                    ATTR_LATENCY,
                    description={"suggested_value": default_input.get(ATTR_LATENCY, 5)},
                ): sel.sel({"min": 5, "max": 60, "mode": "box"}),
                vol.Optional(
                    ATTR_START_LATENCY,
                    description={
                        "suggested_value": default_input.get(ATTR_START_LATENCY, 30)
                    },
                ): sel.sel({"min": 5, "max": 60, "mode": "box"}),
                vol.Optional(
                    ATTR_PARALLEL,
                    description={
                        "suggested_value": default_input.get(ATTR_PARALLEL, 1)
                    },
                ): sel.NumberSelector({"min": 1, "max": 10, "mode": "box"}),
                vol.Optional(
                    ATTR_CARD_YAML,
                    description={
                        "suggested_value": default_input.get(ATTR_CARD_YAML, False)
                    },
                ): cv.boolean,
                vol.Optional(
                    ATTR_RAIN_DELAY,
                    description={
                        "suggested_value": default_input.get(ATTR_RAIN_DELAY, False)
                    },
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="advanced",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_finalise(self, user_input=None):
        """Second step in config flow to add a repo to watch."""
        errors = {}
        # must have at least one zone defined
        if self._data.get(ATTR_ZONES, []) == []:
            errors["base"] = "zone_required"
            return self.async_show_form(
                step_id="menu",
                errors=errors,
            )

        # User is done adding, create the config entry.
        return self.async_create_entry(title=self._data.get(CONF_NAME), data=self._data)

    # --- Options Flow ----------------------------------------------
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create option flow handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Option flow."""

    VERSION = 7

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialise option flow."""
        self._name = config_entry.data.get(CONF_NAME)
        self.zoneselect = None
        self._uid = config_entry.entry_id
        if config_entry.options == {}:
            self._data = config_entry.data
        else:
            self._data = config_entry.options

        self._exclude = []
        self._remove = []
        self._delete = []

    async def async_step_user(self, user_input=None):
        """Initialise step? work around from HA v2023.11."""
        # does nothing but must be there, go figure
        return

    async def async_step_init(self, user_input=None):
        """Initialise step."""
        self._exclude = []
        for zone in self._data.get(ATTR_ZONES, []):
            self._exclude.append(zone.get(ATTR_ZONE))
        self._exclude.extend(exclude(self.hass))

        xmenu_options = ["update_program", "add_zone", "update_zone"]
        # only one zone so don't show delete zone option
        zones = [zone[ATTR_ZONE] for zone in self._data[ATTR_ZONES]]
        # remove zones already flagged for deletion
        zones = [zone for zone in zones if zone not in self._delete]
        if len(zones) > 1:
            xmenu_options.extend(["delete_zone"])
        xmenu_options.extend(["advanced", "finalise"])
        return self.async_show_menu(
            step_id="user",
            menu_options=xmenu_options,
        )

    async def async_step_finalise(self, user_input=None):
        """Create the program config."""
        newdata = {}
        newdata.update(self._data)

        sortedzones = bubble_sort(self._data.get(ATTR_ZONES))
        for zone in self._delete:
            for zonenumber, szone in enumerate(sortedzones):
                if szone["zone"] == zone:
                    sortedzones.pop(zonenumber)

        for zone in sortedzones:
            if zone["freq"] is False:
                # ensure program freq is enabled
                newdata.update({"freq": True})

        newdata.update({ATTR_ZONES: sortedzones})
        # the top level of the dictionary needs to change
        localtimezone = ZoneInfo(self.hass.config.time_zone)
        updated = datetime.now(localtimezone).strftime("%Y-%m-%d %H:%M:%S.%f")
        newdata.update({"updated": updated})

        if len(sortedzones) == 1:
            await self.get_er("number", slugify(f"{self._uid}_inter_zone_delay"))
        # remove entities for deleted zones
        for delete in self._remove:
            er.async_get(self.hass).async_remove(delete)

        # User is done adding, create the config entry.
        return self.async_create_entry(title=self._data.get(CONF_NAME), data=newdata)

    async def async_step_advanced(self, user_input=None):
        """Add a zone step."""
        errors = {}
        newdata = {}
        newdata.update(self._data)
        if user_input is not None:
            if not errors:
                newdata[ATTR_INTERLOCK] = user_input[ATTR_INTERLOCK]
                newdata[ATTR_START_TYPE] = user_input.get(ATTR_START_TYPE, "selector")
                newdata[ATTR_RAIN_BEHAVIOUR] = user_input.get(
                    ATTR_RAIN_BEHAVIOUR, "stop"
                )
                newdata[ATTR_MIN_SEC] = user_input[ATTR_MIN_SEC]
                newdata[ATTR_WATER_MAX] = user_input[ATTR_WATER_MAX]
                newdata[ATTR_WATER_STEP] = user_input[ATTR_WATER_STEP]
                newdata[ATTR_ZONE_DELAY_MAX] = user_input[ATTR_ZONE_DELAY_MAX]
                newdata[ATTR_LATENCY] = user_input[ATTR_LATENCY]
                newdata[ATTR_START_LATENCY] = user_input[ATTR_START_LATENCY]
                newdata[ATTR_PARALLEL] = user_input[ATTR_PARALLEL]
                newdata[ATTR_CARD_YAML] = user_input[ATTR_CARD_YAML]
                newdata[ATTR_RAIN_DELAY] = user_input[ATTR_RAIN_DELAY]
                # Return the form of the next step.
                self._data = newdata
                if user_input[ATTR_START_TYPE] not in ["sunset"]:
                    await self.get_er("number", slugify(f"{self._uid}_sunset_offset"))
                if user_input[ATTR_START_TYPE] not in ["sunrise"]:
                    await self.get_er("number", slugify(f"{self._uid}_sunrise_offset"))
                if user_input[ATTR_START_TYPE] in ["multistart"]:
                    await self.get_er("time", slugify(f"{self._uid}_start_time"))
                if user_input[ATTR_START_TYPE] not in ["multistart"]:
                    await self.get_er("text", slugify(f"{self._uid}_start_times"))
                if not user_input[ATTR_RAIN_DELAY]:
                    await self.get_er("number", slugify(f"{self._uid}_rain_delay_days"))
                    await self.get_er(
                        "switch", slugify(f"{self._uid}_enable_rain_delay")
                    )
                return await self.async_step_init()

        if user_input:
            default_input = user_input
        elif self._data:
            default_input = self._data
        else:
            default_input = {}

        # build a dict including entered values on error
        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_INTERLOCK,
                    description={
                        "suggested_value": default_input.get(ATTR_INTERLOCK, "strict")
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["strict", "loose", "off"],
                        "translation_key": ATTR_INTERLOCK,
                    }
                ),
                vol.Optional(
                    ATTR_START_TYPE,
                    description={"suggested_value": default_input.get(ATTR_START_TYPE)},
                ): sel.SelectSelector(
                    {
                        "options": ["selector", "multistart", "sunrise", "sunset"],
                        "translation_key": ATTR_START_TYPE,
                    }
                ),
                vol.Optional(
                    ATTR_RAIN_BEHAVIOUR,
                    description={
                        "suggested_value": default_input.get(
                            ATTR_RAIN_BEHAVIOUR, "stop"
                        )
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["stop", "continue"],
                        "translation_key": ATTR_RAIN_BEHAVIOUR,
                    }
                ),
                vol.Optional(
                    ATTR_MIN_SEC,
                    description={
                        "suggested_value": default_input.get(ATTR_MIN_SEC, "minutes")
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["minutes", "seconds"],
                        "translation_key": ATTR_MIN_SEC,
                    }
                ),
                vol.Optional(
                    ATTR_WATER_MAX,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_MAX, 30)
                    },
                ): sel.NumberSelector({"min": 1, "max": 9999, "mode": "box"}),
                vol.Optional(
                    ATTR_WATER_STEP,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_STEP, 1)
                    },
                ): sel.NumberSelector({"min": 1, "max": 100, "mode": "box"}),
                vol.Optional(
                    ATTR_ZONE_DELAY_MAX,
                    description={
                        "suggested_value": default_input.get(ATTR_ZONE_DELAY_MAX, 120)
                    },
                ): sel.NumberSelector({"min": 1, "max": 9999, "mode": "box"}),
                vol.Optional(
                    ATTR_LATENCY,
                    description={"suggested_value": default_input.get(ATTR_LATENCY, 5)},
                ): sel.NumberSelector({"min": 5, "max": 60, "mode": "box"}),
                vol.Optional(
                    ATTR_START_LATENCY,
                    description={
                        "suggested_value": default_input.get(ATTR_START_LATENCY, 30)
                    },
                ): sel.NumberSelector({"min": 5, "max": 60, "mode": "box"}),
                vol.Optional(
                    ATTR_PARALLEL,
                    description={
                        "suggested_value": default_input.get(ATTR_PARALLEL, 1)
                    },
                ): sel.NumberSelector({"min": 1, "max": 10, "mode": "box"}),
                vol.Optional(
                    ATTR_CARD_YAML,
                    description={
                        "suggested_value": default_input.get(ATTR_CARD_YAML, False)
                    },
                ): cv.boolean,
                vol.Optional(
                    ATTR_RAIN_DELAY,
                    description={
                        "suggested_value": default_input.get(ATTR_RAIN_DELAY, False)
                    },
                ): cv.boolean,
            }
        )
        return self.async_show_form(
            step_id="advanced",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_update_program(self, user_input=None):
        """Invoke when a user initiates a flow via the user interface."""
        errors = {}
        newdata = {}
        newdata.update(self._data)

        if user_input is not None:
            newdata.update(user_input)
            cleanoptions = []

            for option in user_input.get("freq_options"):
                try:
                    if isinstance(int(option), int):
                        cleanoptions.append(option)
                        continue
                except ValueError:
                    optionlist = (
                        option.replace(" ", "")
                        .replace("\n", "")
                        .replace("'", "")
                        .replace('"', "")
                        .strip("[]'")
                        .split(",")
                    )
                    optionlist = [x.capitalize() for x in optionlist]
                    if len(optionlist) > 1:
                        for item in optionlist:
                            if item.strip() not in OPTIONS_DAYS_OF_WEEK:
                                errors["freq_options"] = "invalid_days_group"
                                break
                        else:
                            cleanoptions.append(", ".join(optionlist))
                            continue
                    if optionlist[0] in OPTIONS_DAYS_OF_WEEK:
                        cleanoptions.append(optionlist[0])
                        continue

                    errors["freq_options"] = "invalid_option"
                    break

            newdata["freq_options"] = cleanoptions

            if not cleanoptions:
                errors["freq_options"] = "mandatory"

            if not errors:
                if user_input["freq"] is False:
                    await self.get_er("select", slugify(f"{self._uid}_frequency"))

                # Return the form of the next step.
                self._data = newdata
                return await self.async_step_init()

        if user_input:
            default_input = user_input
        elif self._data:
            default_input = self._data
        else:
            default_input = {}

        schema = vol.Schema(
            {
                vol.Optional(
                    "freq",
                    description={"suggested_value": default_input.get("freq", True)},
                ): cv.boolean,
                vol.Required(
                    "freq_options",
                    description={
                        "suggested_value": default_input.get("freq_options", None)
                    },
                ): sel.SelectSelector(
                    {
                        "options": OPTIONS_DAYS
                        + OPTIONS_DAYS_OF_WEEK
                        + OPTIONS_DAYS_GROUPED,
                        "multiple": True,
                        "custom_value": True,
                        "translation_key": "freq_options",
                    }
                ),
                vol.Optional(
                    ATTR_DEVICE_TYPE,
                    description={
                        "suggested_value": default_input.get(
                            ATTR_DEVICE_TYPE, "generic"
                        )
                    },
                ): sel.SelectSelector(
                    {
                        "options": ["generic", "rainbird", "bhyve"],
                        "translation_key": ATTR_DEVICE_TYPE,
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="update_program",
            data_schema=schema,
            errors=errors,
        )

    async def get_er(self, domain, uid):
        """Get the entity_id from the unique id."""
        entity_id = er.async_get(self.hass).async_get_entity_id(
            domain=domain, platform="irrigationprogram", unique_id=uid
        )
        if entity_id:
            self._remove.append(entity_id)

    async def async_step_delete_zone(self, user_input=None):
        """Delete a zone."""
        errors = {}

        if user_input is not None:
            if user_input == {}:
                # no data provided return to the menu
                return await self.async_step_init()
            # find the position of the zone in the zones.
            zones = [zone[ATTR_ZONE] for zone in self._data[ATTR_ZONES]]
            # register zone to delete the zone from the list of zones
            self._delete.append(user_input.get(ATTR_ZONE))
            # set up to remove entities when finalising
            friendlyname = user_input.get(ATTR_ZONE).split(".")[1]
            await self.get_er("switch", slugify(f"{self._uid}_{friendlyname}_config"))
            await self.get_er(
                "switch", slugify(f"{self._uid}_{friendlyname}_ignore_sensors")
            )
            await self.get_er(
                "switch", slugify(f"{self._uid}_{friendlyname}_enable_zone")
            )
            await self.get_er("sensor", slugify(f"{self._uid}_{friendlyname}_status"))
            await self.get_er(
                "select", slugify(f"{self._uid}_{friendlyname}_frequency")
            )
            await self.get_er("number", slugify(f"{self._uid}_{friendlyname}_water"))
            await self.get_er("number", slugify(f"{self._uid}_{friendlyname}_wait"))
            await self.get_er("number", slugify(f"{self._uid}_{friendlyname}_repeat"))
            await self.get_er("sensor", slugify(f"{self._uid}_{friendlyname}_next_run"))
            await self.get_er("sensor", slugify(f"{self._uid}_{friendlyname}_last_ran"))
            await self.get_er(
                "sensor", slugify(f"{self._uid}_{friendlyname}_remaining_time")
            )
            return await self.async_step_init()

        # build list of zones
        zones = [zone[ATTR_ZONE] for zone in self._data[ATTR_ZONES]]
        # remove zones already flagged for deletion
        zones = [zone for zone in zones if zone not in self._delete]
        # build the options list
        optionslist = []
        for zone in zones:
            try:
                optionslist.append(
                    {"label": self.hass.states.get(zone).name, "value": zone}
                )
            except AttributeError:
                optionslist.append({"label": zone + " offline!", "value": zone})
        list_schema = vol.Schema(
            {
                vol.Optional(ATTR_ZONE): sel.SelectSelector(
                    {
                        "options": optionslist,
                    }
                )
            }
        )
        return self.async_show_form(
            step_id="delete_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone(self, user_input=None):
        """List zones for Update."""
        errors = {}
        if user_input is not None:
            if user_input == {}:
                # no data provided return to the menu
                return await self.async_step_init()
            # Input is valid, set data.
            self.zoneselect = user_input
            # Return the form of the next step.
            return await self.async_step_update_zone_data()

        # sort and display the selection list
        sortedzones = bubble_sort(self._data.get(ATTR_ZONES))
        # build list of zones
        zones = [zone[ATTR_ZONE] for zone in sortedzones]
        # remove zones already flagged for deletion
        zones = [zone for zone in zones if zone not in self._delete]
        # build the options list
        optionslist = []
        for zone in zones:
            try:
                optionslist.append(
                    {"label": self.hass.states.get(zone).name, "value": zone}
                )
            except AttributeError:
                optionslist.append({"label": zone + " offline!", "value": zone})

        list_schema = vol.Schema(
            {
                vol.Optional(ATTR_ZONE): sel.SelectSelector(
                    {
                        "options": optionslist,
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="update_zone", data_schema=list_schema, errors=errors
        )

    async def async_step_update_zone_data(self, user_input=None):
        """Update zone."""
        errors = {}
        newdata = {}
        newdata.update(self._data)
        # get the zone position
        for count, zone in enumerate(newdata.get(ATTR_ZONES)):
            if zone.get(ATTR_ZONE) == self.zoneselect.get(ATTR_ZONE):
                this_zone = zone
                zone_pos = count
                break
        if user_input is not None:
            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"

            if not errors:
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                # update with the new data into the list of zones
                newdata.get(ATTR_ZONES)[zone_pos] = zone_data
                self._data = newdata
                # remove the wait and repeate if ECO is disabled
                friendlyname = user_input[ATTR_ZONE].split(".")[1]
                if user_input["eco"] is False:
                    await self.get_er(
                        "number", slugify(f"{self._uid}_{friendlyname}_wait_time")
                    )
                    await self.get_er(
                        "number", slugify(f"{self._uid}_{friendlyname}_repeat")
                    )
                if user_input["freq"] is False:
                    await self.get_er(
                        "select", slugify(f"{self._uid}_{friendlyname}_frequency")
                    )

                return await self.async_step_update_zone()

        if user_input:
            default_input = user_input
        elif self._data:
            default_input = this_zone
        else:
            default_input = {}

        zone_exclude = []
        zone_exclude.extend(self._exclude)
        zone_exclude.pop(zone_exclude.index(this_zone.get(ATTR_ZONE)))
        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_ZONE,
                    description={"suggested_value": default_input.get(ATTR_ZONE)},
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": zone_exclude}
                ),
                vol.Optional(
                    "freq",
                    description={"suggested_value": default_input.get("freq", False)},
                ): cv.boolean,
                vol.Optional(
                    "eco",
                    description={"suggested_value": default_input.get("eco", False)},
                ): cv.boolean,
                vol.Optional(
                    ATTR_PUMP,
                    description={"suggested_value": default_input.get(ATTR_PUMP)},
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_FLOW_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_FLOW_SENSOR)
                    },
                ): sel.EntitySelector(
                    {"domain": ["sensor"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_WATER_ADJUST,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_ADJUST)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["sensor", "input_number"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_RAIN_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_RAIN_SENSOR)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_WATER_SOURCE,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_SOURCE)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_ZONE_ORDER,
                    description={
                        "suggested_value": default_input.get(ATTR_ZONE_ORDER, 10)
                    },
                ): sel.NumberSelector({"min": 1, "max": 999, "mode": "box"}),
            }
        )

        return self.async_show_form(
            step_id="update_zone_data",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_zone(self, user_input=None):
        """Add zone."""
        errors = {}
        newdata = {}
        newdata.update(self._data)
        if user_input is not None:
            if user_input == {}:
                # not data input return to the menu
                return await self.async_step_init()

            if user_input.get(ATTR_ZONE) is None:
                errors[ATTR_ZONE] = "mandatory"

            if not errors:
                if user_input == {}:
                    # not data input return to the menu
                    return await self.async_step_init()
                # Input is valid, set data.
                zone_data = {}
                for attr in user_input:
                    zone_data[attr] = user_input[attr]
                newdata[ATTR_ZONES].append(zone_data)
                self._exclude.append(user_input.get(ATTR_ZONE))
                self._data = newdata
                return await self.async_step_init()

        # build a dict including original values
        if user_input is None:
            default_input = {}
        else:
            default_input = user_input

        default_order = (len(newdata.get(ATTR_ZONES)) + 1) * 10  # increment by 10

        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_ZONE, default=default_input.get(ATTR_ZONE, None)
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    "freq", default=default_input.get("freq", False)
                ): cv.boolean,
                vol.Optional(
                    "eco",
                    description={"suggested_value": default_input.get("eco", False)},
                ): cv.boolean,
                vol.Optional(
                    ATTR_PUMP, description=default_input.get(ATTR_PUMP, None)
                ): sel.EntitySelector(
                    {"domain": ["switch", "valve"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_FLOW_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_FLOW_SENSOR, None)
                    },
                ): sel.EntitySelector(
                    {"domain": ["sensor"], "exclude_entities": self._exclude}
                ),
                vol.Optional(
                    ATTR_WATER_ADJUST,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_ADJUST, None)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["sensor", "input_number"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_RAIN_SENSOR,
                    description={
                        "suggested_value": default_input.get(ATTR_RAIN_SENSOR, None)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_WATER_SOURCE,
                    description={
                        "suggested_value": default_input.get(ATTR_WATER_SOURCE, None)
                    },
                ): sel.EntitySelector(
                    {
                        "domain": ["binary_sensor", "input_boolean"],
                        "exclude_entities": self._exclude,
                    }
                ),
                vol.Optional(
                    ATTR_ZONE_ORDER,
                    description={
                        "suggested_value": default_input.get(
                            ATTR_ZONE_ORDER, default_order
                        )
                    },
                ): sel.NumberSelector({"min": 1, "max": 999, "mode": "box"}),
            }
        )

        return self.async_show_form(
            step_id="add_zone",
            data_schema=schema,
            errors=errors,
        )
