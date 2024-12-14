'''Constants.'''

TIME_STR_FORMAT = "%H:%M:%S"

RAINBIRD_TURN_ON = 'start_irrigation'
RAINBIRD = 'rainbird'
RAINBIRD_DURATION = 'duration'

DOMAIN = "irrigationprogram"
SWITCH_ID_FORMAT = "switch.{}"

ATTR_DEVICE_TYPE = "device_type"
ATTR_RAIN_SENSOR = "rain_sensor"
ATTR_IRRIGATION_ON = "irrigation_on"
ATTR_START = "start_time"
ATTR_START_TYPE = "start_type"
ATTR_IGNORE_SENSOR = "ignore_sensors"
ATTR_SHOW_CONFIG = "show_config"
ATTR_RAIN_BEHAVIOUR = "rain_behaviour"
ATTR_RUN_FREQ = "run_freq"
ATTR_REMAINING = "remaining"
ATTR_REPEAT = "repeat"
ATTR_RUNTIME = "runtime"
ATTR_WAIT = "wait"
ATTR_DELAY = "inter_zone_delay"
ATTR_FLOW_SENSOR = "flow_sensor"
ATTR_WATER = "water"
ATTR_WATER_ADJUST = "water_adjustment"
ATTR_ZONES = "zones"
ATTR_ZONE = "zone"
ATTR_ZONE_GROUP = "group"
ATTR_ZONE_ORDER = "order"
ATTR_PUMP = "pump"
ATTR_LAST_RAN = "last_ran"
ATTR_NEXT_RUN = "next_run"
ATTR_SWITCHES = "switches"
ATTR_MONITOR_CONTROLLER = "controller_monitor"
ATTR_PAUSE = "pause"
ATTR_DISABLE_ZONE = "disable_zone"
ATTR_ENABLE_ZONE = "enable_zone"
ATTR_RESET = "reset"
ATTR_GROUPS = "groups"
ATTR_GROUP = "group"
ATTR_GROUP_NAME = "group_name"
ATTR_HISTORICAL_FLOW = "historical_flow"
ATTR_INTERLOCK = "interlock"
ATTR_SCHEDULED = "scheduled"
ATTR_WATER_SOURCE = "water_source_active"


CONST_LATENCY = 5
CONST_ZERO_FLOW_DELAY = 5
CONST_OFF_DELAY = 5
CONST_SUN_OFFSET = 240
CONST_DELAY_OFFSET = 10

CONST_ENTITY = "entity_id"
CONST_SWITCH = "switch"
# valid sensor values
CONST_ON =  'on'
CONST_PENDING =  'pending'
CONST_OPEN =  'open'
CONST_CLOSED =  'closed'
CONST_ECO =  'eco'
CONST_OFF =  'off'
CONST_ABORTED = 'aborted'
CONST_DISABLED =  'disabled'
CONST_PROGRAM_DISABLED =  'program_disabled'
CONST_CONTROLLER_DISABLED =  "controller_disabled"
CONST_UNAVAILABLE =  "unavailable"
CONST_RAINING =  "raining"
CONST_RAINING_STOP = "raining_stop"
CONST_ADJUSTED_OFF =  "adjusted_off"
CONST_NO_WATER_SOURCE =  "no_water_source"
CONST_ZONE_DISABLED =  'zone_disabled'
CONST_VALVE = 'valve'
CONST_PAUSED = 'paused'
