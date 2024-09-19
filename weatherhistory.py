"""Define the weather class."""

from datetime import date, datetime
import json
import logging
import re
from zoneinfo import ZoneInfo

from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage as store

#from homeassistant.helpers import config_validation as cv, storage as store
from .const import (
    CONF_INTIAL_DAYS,
    CONF_MAX_CALLS,
    CONF_MAX_DAYS,
    CONST_API_CALL,
    CONST_API_FORECAST,
    CONST_CALLS,
    CONST_INITIAL,
)
from .data import RestData

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "OpenWeatherMap History"

class Weather:
    """weather class."""

    def __init__(  # noqa: D107
        self,
        hass: HomeAssistant,
        config,
    ) -> None:

        self._timezone     = hass.config.time_zone
        self._hass         = hass
        self._config       = config
        self._processed    = {}
        self._num_days     = 0
        self._name      = config.get(CONF_NAME,DEFAULT_NAME)
        self._lat       = config[CONF_LOCATION].get(CONF_LATITUDE,hass.config.latitude)
        self._lon       = config[CONF_LOCATION].get(CONF_LONGITUDE,hass.config.longitude)
        self._key       = config[CONF_API_KEY]
        self._initdays  = config.get(CONF_INTIAL_DAYS,5)
        self._maxdays   = config.get(CONF_MAX_DAYS,5)
        self._maxcalls  = config.get(CONF_MAX_CALLS,1000)
        self._backlog   = 0
        self._processing_type = None
        self._daily_count     = 1
        self._cumulative_rain = 0
        self._cumulative_snow = 0
        self._warning_issued  = False

    async def async_get_stored_data(self, key):
        """Get data from .storage."""
        data = {}
        x = store.Store[dict[any]](self._hass,1,key)
        data = await x.async_load()
        if data is None:
            data = {}
        return data

    async def async_store_data(self,content,key):
        """Put data into .storage."""
        x = store.Store[dict[any]](self._hass,1,key)
        await x.async_save(content)

    def validate_data(self, data) -> bool:
        """Check if the call was successful."""

        if data is None:
            _LOGGER.error('OpenWeatherMap call failed 1')
            return {}

        try:
            jdata = json.loads(data)
        except TypeError:
            _LOGGER.error('OpenWeatherMap call failed 2')
            return {}

        try:
            code    = jdata["cod"]
            message = jdata["message"]
            _LOGGER.error('OpenWeatherMap call failed code: %s: %s', code, message)
            return {}
        except KeyError:
           return data
        else:
            _LOGGER.error('OpenWeatherMap call failed 3')
            return {}

    def remaining_backlog(self):
        "Return remaining days to collect."
        return self._backlog

    def remaining_calls(self):
        """Return remaining call count."""
        return self._maxcalls - self._daily_count

    def call_limit_warning(self):
        """Issue a warning when the call limit is exceeded."""
        if not self._warning_issued:
            _LOGGER.warning('Maximum daily allowance of API calls have been used')
            self._warning_issued = True

    async def get_forecastdata(self):
        """Get forecast data."""
        #do not process when no calls remaining
        if self.remaining_calls() < 1:
            #only issue a single warning each day
            self.call_limit_warning()
            return {}

        url = CONST_API_FORECAST % (self._lat,self._lon, self._key)
        rest = RestData()
        await rest.set_resource(self._hass, url)
        await rest.async_update(log_errors=True)
        data = self.validate_data(rest.data)
        self._daily_count += 1

        try:
            data = json.loads(data)
            #check if the call was successful
            days = data.get('daily',{})
            current = data.get('current',{})
        except TypeError:
            return None

        #current observations
        currentdata = {"rain":current.get('rain',{}).get('1h',0)
                    , "snow":current.get('snow',{}).get('1h',0)
                    , "temp":current.get("temp",0)
                    , "humidity":current.get("humidity",0)
                    , "pressure":current.get("pressure",0)}
        #build forecast
        forecastdaily = {}
        for day in days:
            temp = day.get('temp',{})
            daydata = {'max_temp':temp.get('max',0),
                       'min_temp':temp.get('min',0),
                       'pressure':day.get('pressure',0),
                       'humidity':day.get('humidity',0),
                       'pop':day.get('pop',0),
                       'rain': day.get('rain',0),
                       'snow':day.get('snow',0)}
            forecastdaily.update({day.get('dt') : daydata})

        return currentdata, forecastdaily

    async def processcurrent(self,current):
        """Process the currrent data."""
        return { 'current': {'rain': current.get('rain')
                                   , 'snow': current.get('snow')
                                   , 'humidity': current.get('humidity')
                                   , 'temp': current.get('temp')
                                   , 'pressure': current.get('pressure')}
                                   }

    async def processdailyforecast(self,dailydata):
        "Process daily forecast data."
        processed_data = {}
        for i, data in enumerate(dailydata.values()):
            #get the days data
            day = {}
            #update the days data
            day.update({"pop":data.get('pop',0)})
            day.update({"rain":data.get('rain',0)})
            day.update({"snow":data.get('snow',0)})
            day.update({"min_temp":data.get('min_temp',0)})
            day.update({"max_temp":data.get('max_temp',0)})
            day.update({"humidity":data.get('humidity',0)})
            day.update({"pressure":data.get('pressure',0)})
            processed_data.update({f'f{i}':day})
        return processed_data

    async def processhistory(self,historydata):
        """Process history data."""
        removehours = []
        processed_data = {}
        for hour, data in historydata.items():
            localday = datetime.fromtimestamp(int(hour),tz=ZoneInfo(self._timezone))
            localnow = datetime.now(ZoneInfo(self._timezone))
            localdaynum = (localnow - localday).days
            self._num_days = max(self._num_days,localdaynum)
            if localdaynum > self._maxdays-1:
                #identify data to age out
                removehours.append(hour)
                continue
            #get the days data
            day = processed_data.get(localdaynum,{})
            #process the new data
            rain = day.get('rain',0) + data["rain"]
            snow = day.get('snow',0) + data["snow"]
            mintemp = min(data["temp"],day.get('min_temp',999), 999)
            maxtemp = max(data["temp"],day.get('max_temp',-999), -999)
            #update the days data
            day.update({"rain":rain})
            day.update({"snow":snow})
            day.update({"min_temp":mintemp})
            day.update({"max_temp":maxtemp})
            processed_data.update({localdaynum:day})
        #age out old data
        for hour in removehours:
            historydata.pop(hour)
        return historydata,processed_data

    def set_processing_type(self,option):
        """Allow setting of the processing type."""
        self._processing_type = option
    def get_processing_type(self):
        """Allow setting of the processing type."""
        return self._processing_type

    def num_days(self) -> int:
        """Return how many days of data has been collected."""
        return self._num_days

    def max_days(self) -> int:
        """Return how many days of data has been collected."""
        return self._maxdays

    def daily_count(self) -> int:
        """Return daily of data has been collected."""
        return self._daily_count

    def cumulative_rain(self) -> float:
        """Return data has been collected."""
        return self._cumulative_rain

    def cumulative_snow(self) -> float:
        """Return data has been collected."""
        return self._cumulative_snow

    def processed_value(self, period, value) -> float:
        """Return data has been collected."""
        data = self._processed.get(period,{})
        return data.get(value,0)

    async def show_call_data(self):
        """Call the api and show the result."""
        hour = datetime(date.today().year, date.today().month, date.today().day,datetime.now().hour)
        thishour = int(datetime.timestamp(hour))
        url = CONST_API_CALL % (self._lat,self._lon, thishour, self._key) #self._key
        rest = RestData()
        await rest.set_resource(self._hass, url)
        await rest.async_update(log_errors=True)
        self._daily_count += 1
        _LOGGER.warning(url)
        _LOGGER.warning(self.validate_data(rest.data))
        _LOGGER.warning(rest.data)


    async def async_update(self):
        '''Update the weather stats.'''
        hour = datetime(date.today().year, date.today().month, date.today().day,datetime.now().hour)
        thishour = int(datetime.timestamp(hour))
        day = datetime(date.today().year, date.today().month, date.today().day)
        #GMT midnight
        midnight = int(datetime.timestamp(day))
        #restore saved data
        storeddata = await self.async_get_stored_data("OWMH_" + self._name)
        historydata = storeddata.get("history",{})
        currentdata = storeddata.get('current',{})
        dailydata = storeddata.get('dailyforecast',{})
        cumulative = storeddata.get('dailyforecast',{})
        self._cumulative_rain = cumulative.get('cumulativerain',0)
        self._cumulative_snow = cumulative.get('cumulativesnow',0)
        dailycalls = storeddata.get('dailycalls',{})
        self._daily_count = dailycalls.get("count",0)
        #reset the daily count on new UTC day
        if dailycalls.get('time',0) < midnight:
            self._daily_count = 1
            self._warning_issued = False

        dailycalls = {'time': midnight,'count':self._daily_count}

        if self._processing_type == CONST_INITIAL:
            #on start up just get the latest hour
            last_data_point = self.maxdict(historydata)
            if last_data_point is None:
                last_data_point = thishour - 3600
            _LOGGER.debug('initial %s',last_data_point)
            historydata = await self.async_backload(historydata)
        else:
            last_data_point = self.maxdict(historydata)
            historydata = await self.async_backload(historydata)

        #empty file
        if last_data_point is None:
            last_data_point = thishour - 3600
        _LOGGER.debug('update %s',self._processing_type)
        #get new data if required
        if last_data_point < thishour:
            data = await self.get_forecastdata()
            if data is None or data == {}:
                #httpx request failed
                return
            currentdata = data[0]
            dailydata = data[1]
            _LOGGER.debug('get data %s',self._processing_type)
            historydata = await self.get_data(historydata)

        #recaculate the backlog
        data = historydata
        hour = datetime(date.today().year, date.today().month, date.today().day,datetime.now().hour)
        thishour = int(datetime.timestamp(hour))
        if data == {}:
            earliestdata = thishour
        else:
            try:
                earliestdata = self.mindict(data)
                #earliestdata = int(self.mindict(data))
            except ValueError:
                earliestdata = thishour

        self._backlog = max(0,((self._initdays*24*3600) - (thishour - earliestdata))/3600)
        #Process the available data
        processedcurrent = await self.processcurrent(currentdata)
        processeddaily = await  self.processdailyforecast(dailydata)
        data = await self.processhistory(historydata)
        historydata = data[0]
        processedweather = data[1]
        #build data to support template variables
        self._processed = {**processeddaily, **processedcurrent, **processedweather}
        dailycalls = {'time':midnight,'count':self._daily_count}

        zone_data = {'history':historydata,
                    'current':currentdata,
                    'dailyforecast':dailydata,
                    'dailycalls':dailycalls,
                    'cumlative':{
                    'cumulativerain':self._cumulative_rain,
                    'cumulativesnow':self._cumulative_snow
                    }
        }
        await self.async_store_data(zone_data,"OWMH_" + self._name)

    async def get_data(self,historydata):
        """Get data from the newest timestamp forward."""
        hour = datetime(date.today().year, date.today().month, date.today().day,datetime.now().hour)
        thishour = int(datetime.timestamp(hour))
        data = historydata
        #on startup only get one hour of data to not impact HA start
        if self._processing_type == CONST_INITIAL:
            hours = 1
        else:
            hours = CONST_CALLS

        last_data_point = self.maxdict(data)
        if last_data_point is None:
            #no data yet just get this hours dataaset
            last_data_point = thishour - 3600
        #iterate until caught up to current hour
        #or exceeded the call limit
        target = min(thishour,last_data_point+hours*3600)

        while last_data_point < target:
            #increment last date by an hour
            last_data_point += 3600
            hourdata = await self.gethourdata(last_data_point)
            if hourdata == {}:
                break
            self._cumulative_rain += hourdata.get("rain",0)
            self._cumulative_snow += hourdata.get("snow",0)
            data.update({last_data_point : hourdata })
        #end rest loop
        return data

    def mindict(self,data):
        """Find minimum dictionary key."""
        if data == {}:
            return None
        mini = int(next(iter(data)))
        for x in data:
            mini = min(int(x), mini)
        return mini

    def maxdict(self,data):
        """Find minimum dictionary key."""
        if data == {}:
            return None
        maxi = int(next(iter(data)))
        for x in data:
            maxi = max(int(x), maxi)
        return maxi

    async def async_backload(self,historydata):
        """Backload data."""
        #from the oldest recieved data backward
        #until all the backlog is processed
        data = historydata
        hour = datetime(date.today().year, date.today().month, date.today().day,datetime.now().hour)
        thishour = int(datetime.timestamp(hour))
        #limit the number of API calls in a single execution
        if self._processing_type == CONST_INITIAL:
            hours = 1
        else:
            hours = CONST_CALLS

        if data == {}: #new location
            #the oldest data collected so far
            earliestdata = thishour
        else:
            try:
                earliestdata = self.mindict(data)
            except ValueError:
                earliestdata = thishour

        expected_earliest_data = thishour - (self._initdays*24*3600)
        backlog = earliestdata - expected_earliest_data - 3600
        self._backlog = max(0,backlog/3600)
        if  self._backlog < 1:
            return data

        x = 1
        while x <= hours:
            #get the data for the hour
            data_piont_time = earliestdata-(3600*x)
            hourdata = await self.gethourdata(data_piont_time)
            if hourdata == {}:
                #no data found so abort the loop
                break
            #Add the data collected oected to the weather history
            data.update({str(data_piont_time) : hourdata })
            #decrement the backlog
            self._backlog -= 1
            if self._backlog < 1:
                break
            x+=1

        return data

    async def gethourdata(self,timestamp):
        """Get one hours data."""
        #do not process when no calls remaining
        if self.remaining_calls() < 1:
            #only issue a single warning each day
            self.call_limit_warning()
            return {}

        url = CONST_API_CALL % (self._lat,self._lon, timestamp, self._key)
        rest = RestData()
        await rest.set_resource(self._hass, url)
        await rest.async_update(log_errors=True)
        data = self.validate_data(rest.data)
        self._daily_count += 1

        try:
            data = json.loads(data)
            current = data.get('data')[0]
            if current is None:
                current = {}
        except TypeError:
            _LOGGER.warning('OpenWeatherMap history call failed')
            return {}
        #build this hours data
        precipval = {}
        preciptypes = ['rain','snow']
        for preciptype in preciptypes:
            if preciptype in current:
                #get the rain/snow eg 'rain': {'1h':0.89}
                precip = current[preciptype]
                #get the first key eg 1h, 3h
                key = next(iter(precip))
                #get the number component assuming only a singe digit
                divby = float(re.search(r'\d+', key).group())
                try:
                    volume = precip.get(key,0)/divby
                except ZeroDivisionError:
                    volume = 0
                precipval.update({preciptype:volume})

        rain = precipval.get('rain',0)
        snow = precipval.get('snow',0)
        return {"rain": rain
                ,"snow":snow
                ,"temp":current.get("temp",0)
                ,"humidity":current.get("humidity",0)
                ,"pressure":current.get("pressure",0)}
