'''weather history class defn constants'''

CONST_API_CALL          = 'https://api.openweathermap.org/data/2.5/onecall/timemachine?lat=%s&lon=%s&dt=%s&appid=%s&units=%s'

ATTR_ICON_FINE          = 'fine_icon'       #icon to display when factor is 1
ATTR_ICON_LIGHTRAIN     = 'lightrain_icon'  #icon to display when factor is > 0 and <1
ATTR_ICON_RAIN          = 'rain_icon'       #icon to display when factor is 0
DFLT_ICON_FINE          = 'mdi:weather-sunny'
DFLT_ICON_LIGHTRAIN     = 'mdi:weather-rainy'
DFLT_ICON_RAIN          = 'mdi:weather-pouring'

ATTR_0_SIG              = 'day0sig'
ATTR_1_SIG              = 'day1sig'
ATTR_2_SIG              = 'day2sig'
ATTR_3_SIG              = 'day3sig'
ATTR_4_SIG              = 'day4sig'
ATTR_WATERTARGET        = 'watertarget'

