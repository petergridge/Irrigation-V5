"""Platform for historical rain factor Sensor integration."""
from .weatherhistory import WeatherHist
from .data import RestData

import logging
import voluptuous as vol
from datetime import datetime, timedelta, timezone
from homeassistant.util.unit_system import METRIC_SYSTEM

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
)

from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    )

from .const import (
    CONST_API_CALL,
    ATTR_0_SIG,
    ATTR_1_SIG,
    ATTR_2_SIG,
    ATTR_3_SIG,
    ATTR_4_SIG,
    ATTR_WATERTARGET,
    ATTR_ICON_FINE,
    ATTR_ICON_LIGHTRAIN,
    ATTR_ICON_RAIN,
    DFLT_ICON_FINE,
    DFLT_ICON_LIGHTRAIN,
    DFLT_ICON_RAIN,
    )
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "rainfactor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,

        vol.Optional(ATTR_0_SIG, default=1): cv.positive_float,
        vol.Optional(ATTR_1_SIG, default=0.5): cv.positive_float,
        vol.Optional(ATTR_2_SIG, default=0.25): cv.positive_float,
        vol.Optional(ATTR_3_SIG, default=0.12): cv.positive_float,
        vol.Optional(ATTR_4_SIG, default=0.06): cv.positive_float,
        vol.Optional(ATTR_WATERTARGET, default=10): cv.positive_float,

        vol.Optional(ATTR_ICON_FINE, default=DFLT_ICON_FINE): cv.icon,
        vol.Optional(ATTR_ICON_LIGHTRAIN, default=DFLT_ICON_LIGHTRAIN): cv.icon,
        vol.Optional(ATTR_ICON_RAIN, default=DFLT_ICON_RAIN): cv.icon,
    }
)

SCAN_INTERVAL = timedelta(seconds=1800) #default to 30 minute intervals

_LOGGER = logging.getLogger(__name__)

async def _async_create_entities(hass, config, weather):
    """Create the Template switches."""
    sensors = []

    name      = config[CONF_NAME]

    daysig = [config[ATTR_0_SIG],config[ATTR_1_SIG],config[ATTR_2_SIG],config[ATTR_3_SIG],config[ATTR_4_SIG]]
    watertarget = config[ATTR_WATERTARGET]

    if hass.config.units is METRIC_SYSTEM:
        units = 'metric'
    else:
        units = 'imperial'

    sensors.append(
        RainFactor(
            hass,
            config,
            weather,
            name,
            daysig,
            watertarget,
            units
        )
    )

    return sensors

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensors."""
    weather = []
    key     = config[CONF_API_KEY]
    if hass.config.units is METRIC_SYSTEM:
        units = 'metric'
    else:
        units = 'imperial'

    lat = config.get(CONF_LATITUDE,hass.config.latitude)
    lon = config.get(CONF_LONGITUDE,hass.config.longitude)
    _LOGGER.debug('setup_platform %s, %s', lat, lon)
    today = datetime.now(tz=timezone.utc).replace(hour=0, minute=0,second=0,microsecond=0)
    for day in range(6):
        rest = RestData()
        date = int((today- timedelta(days=day)).timestamp())
        url = CONST_API_CALL % (lat, lon, date, key, units)
        _LOGGER.debug( url )
        await rest.set_resource(hass, url)
        await rest.async_update(log_errors=False)
        weather.append (rest)
    async_add_entities(await _async_create_entities(hass, config, weather))
    _LOGGER.debug('setup_platform has run successfully')

class RainFactor(SensorEntity):
    ''' Rain factor class defn'''
    _attr_has_entity_name = True

    def __init__(
        self,
        hass,
        config,
        weather,
        name: str,
        daysig: list,
        watertarget,
        units
    ):
        """Initialize the sensor."""
        self._name               = name
        self._hass               = hass
        self._weather            = weather
        self._state              = 1
        self._daysig             = daysig
        self._watertarget        = watertarget

        self._extra_attributes   = None
        self._icon               = config[ATTR_ICON_FINE]
        self._icon_fine          = config[ATTR_ICON_FINE]
        self._icon_lightrain     = config[ATTR_ICON_LIGHTRAIN]
        self._icon_rain          = config[ATTR_ICON_RAIN]
        self._ran_today          = datetime.utcnow().date().strftime('%Y-%m-%d')
        self._key                = config[CONF_API_KEY]
        self._units              = units
        self._weatherhist        = None
        self._call_count         = 6

        self._lat = config.get(CONF_LATITUDE,hass.config.latitude)
        self._lon = config.get(CONF_LONGITUDE,hass.config.longitude)
        self._timezone = config.get(CONF_LONGITUDE,hass.config.time_zone)
        self._today = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._name}-{self._lat}-{self._lon}"

    @property
    def native_value(self):
        """Return the state."""
        return self._state

    @property
    def icon(self):
        """Return the unit of measurement."""
        return self._icon

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_attributes

    async def async_added_to_hass(self):

        self._weatherhist = WeatherHist()
        await self._weatherhist.set_weather(self._weather,self._daysig,self._watertarget, self._units, self._timezone)
        await self._weatherhist.async_update()
        self._today = datetime.now(tz=timezone.utc).replace(hour=0, minute=0,second=0,microsecond=0)
        self._state = self._weatherhist.factor
        self._extra_attributes = self._weatherhist.attrs
        self._extra_attributes["call_count"] = self._call_count

        if self._weatherhist.factor == 0:
            self._icon = self._icon_rain
        elif self._weatherhist.factor == 1:
            self._icon = self._icon_fine
        else:
            self._icon = self._icon_lightrain

        self.async_write_ha_state()
        await super().async_added_to_hass()
        _LOGGER.debug('added to hass has run successfully')

    async def async_update(self):
        ''' update the sensor'''
        if self._today == datetime.now(tz=timezone.utc).replace(hour=0, minute=0,second=0,microsecond=0):
            #update only today's weather
            date = int((datetime.now(tz=timezone.utc)- timedelta(days=0)).timestamp())
            url = CONST_API_CALL % (self._lat,self._lon,date,self._key,self._units)
            await self._weather[0].set_resource(self._hass,url)
            await self._weather[0].async_update(log_errors=False)
            self._call_count += 1
        else:
            #first time today reload the weather for all days
            self._call_count = 0
            self._today = datetime.now(tz=timezone.utc).replace(hour=0, minute=0,second=0,microsecond=0)
            for day, weather in enumerate(self._weather):
                #reset the url for each day
                date = int((self._today- timedelta(days=day)).timestamp())
                url = CONST_API_CALL % (self._lat,self._lon,date,self._key,self._units)
                await weather.set_resource(self._hass,url)
                await weather.async_update(log_errors=False)
                self._call_count += 1

        await self._weatherhist.set_weather(self._weather, self._daysig, self._watertarget, self._units, self._timezone)
        await self._weatherhist.async_update()

        self._extra_attributes = self._weatherhist.attrs
#        self._extra_attributes["call_count"] = self._call_count
        self._state = self._weatherhist.factor

        if self._weatherhist.factor == 0:
            self._icon = self._icon_rain
        elif self._weatherhist.factor == 1:
            self._icon = self._icon_fine
        else:
            self._icon = self._icon_lightrain

        self.async_write_ha_state()
        _LOGGER.debug('sensor update successful')