"""Support for RESTful API."""
import logging
import json
import math
from datetime import datetime, timezone
import pytz

_LOGGER = logging.getLogger(__name__)

class WeatherHist:
    """Class for handling the data retrieval."""

    def __init__(self):
        """Initialize the data object."""
        self._weather      = None
        self._daysig       = None
        self._water_target = None
        self.attrs         = None
        self.factor        = None
        self._units        = None
        self._timezone     = None

    async def set_weather(self, weather, daysig, watertarget, units, time_zone):
        """Set url."""
        self._weather      = weather
        self._daysig       = daysig
        self._water_target = watertarget
        self._units        = units
        self._timezone     = time_zone

    async def async_update(self):
        '''update the weather stats'''
        _LOGGER.debug("Updating weatherhistory")
        factor = 1
        mintemp = {0:999,1:999,2:999,3:999,4:999,5:999}
        maxtemp = {0:-999,1:-999,2:-999,3:-999,4:-999,5:-999}
        attrs = {}
        attrsrain = {'day_0_rain':0,'day_1_rain':0,'day_2_rain':0,'day_3_rain':0,'day_4_rain':0,'day_5_rain':0}
        attrssnow = {'day_0_snow':0,'day_1_snow':0,'day_2_snow':0,'day_3_snow':0,'day_4_snow':0,'day_5_snow':0}
        attrmin = {}
        attrmax = {}
        totalrain = {0:0,1:0,2:0,3:0,4:0,5:0}
        totalsnow = {0:0,1:0,2:0,3:0,4:0,5:0}

        for rest in self._weather:
            data = json.loads(rest.data)

            try:
                localtimezone = pytz.timezone(data["timezone"])
            except KeyError:
                localtimezone =   pytz.timezone(self._timezone)

            current = data["current"]
            if 'dt' in current:
                date = current["dt"]
                formatted_dt = datetime.utcfromtimestamp(date).replace(tzinfo=timezone.utc).astimezone(tz=None).strftime('%Y-%m-%d %H:%M:%S')
                attrs ["As at"] = formatted_dt

            hourly = data["hourly"]
            for hour in hourly:

                # now determine the local day the last 24hrs = 0 24-48 = 1...
                localday = datetime.utcfromtimestamp(hour["dt"]).replace(tzinfo=timezone.utc).astimezone(tz=localtimezone)
                localnow = datetime.now(localtimezone)
                localdaynum = (localnow - localday).days
                _LOGGER.debug("Day: %s", localdaynum)
                if 'rain' in hour:
                    rain = hour["rain"]
                    if not math.isnan(rain["1h"]):
                        totalrain.update({localdaynum: totalrain[localdaynum] + rain["1h"]})
                        _LOGGER.debug("Day: %s Rain: %s", localdaynum, rain)
                        if self._units == "imperial":
                            #convert rainfall to inches
                            attrsrain.update({"day_%d_rain"%(localdaynum) : round(totalrain[localdaynum]/25.4,2)})
                        else:
                            attrsrain.update({"day_%d_rain"%(localdaynum) : round(totalrain[localdaynum],2)})

                if 'snow' in hour:
                    snow = hour["snow"]
                    if not math.isnan(snow["1h"]):
                        totalsnow.update({localdaynum: totalsnow[localdaynum] + snow["1h"]})
                        if self._units == "imperial":
                            #convert snow to inches
                            attrssnow.update({"day_%d_snow"%(localdaynum) : round(totalsnow[localdaynum]/25.4,2)})
                        else:
                            attrssnow.update({"day_%d_snow"%(localdaynum) : round(totalsnow[localdaynum],2)})

                if 'temp' in hour:
                    if hour["temp"] < mintemp[localdaynum]:
                        mintemp.update({localdaynum : hour["temp"]})
                        attrmin.update({"day_%d_min"%(localdaynum): hour["temp"]})
                    if hour["temp"] > maxtemp[localdaynum]:
                        maxtemp.update({localdaynum : hour["temp"]})
                        attrmax.update({"day_%d_max"%(localdaynum): hour["temp"]})
            #end hour loop
        #end rest loop

        #now loop through the data to calculate the adjustment factor
        equivalent = 0
        for day, daysig in enumerate(self._daysig):
            #calculate rainfall equivalent watering
            #each days rain has varying significance
            #e.g. yesterdays rain is less significant than todays rain
            equivalent += attrsrain ["day_%d_rain"%(day)] * daysig

        try:
            if equivalent < self._water_target:
                #calculate the factor
                factor = (self._water_target - equivalent) / self._water_target
                factor = max(0,factor)
            else:
                factor = 0
        except ZeroDivisionError:
            #watering target has been set as 0
            factor = 1

        self.factor = ('%.2f' %factor)
        #only return 5 entries as the 6th is not a complete 24hrs
        attrsrain.popitem()
        attrssnow.popitem()
        attrmin.popitem()
        attrmax.popitem()
        self.attrs = {**attrsrain, **attrssnow, **attrmin, **attrmax}
