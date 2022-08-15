from .irrigationzone import irrigationzone
from .pump import pumpclass
from .helper import create_input_datetime, create_input_number, create_input_boolean, create_input_text

import logging
import asyncio
import voluptuous as vol
from datetime import timedelta
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

from homeassistant.helpers.restore_state import (
    RestoreEntity,
)

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)

from .const import (
    CONST_SWITCH,

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
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_NAME,
    CONF_FRIENDLY_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)

SWITCH_SCHEMA = vol.All(
    vol.Schema(
        {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(ATTR_RUN_FREQ): cv.entity_domain('input_select'),
        vol.Optional(ATTR_MONITOR_CONTROLLER): cv.entity_domain(['binary_sensor','input_boolean']),
        vol.Optional(ATTR_START, default=DFLT_START): cv.string,
        vol.Optional(ATTR_IRRIGATION_ON, default=DFLT_IRRIGATION_ON): cv.string,
        vol.Optional(ATTR_HIDE_CONFIG, default=DFLT_HIDE_CONFIG): cv.string,
        vol.Optional(ATTR_DELAY): cv.string,
        vol.Optional(ATTR_RESET,default=False): cv.boolean,
        vol.Required(ATTR_ZONES): [{
            vol.Required(ATTR_ZONE): cv.entity_domain(CONST_SWITCH),
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(ATTR_PUMP): cv.entity_domain(CONST_SWITCH),
            vol.Optional(ATTR_FLOW_SENSOR): cv.entity_domain(['input_number','sensor']),
            vol.Optional(ATTR_WATER_ADJUST): cv.entity_domain(['input_number','sensor']),
            vol.Optional(ATTR_RUN_FREQ): cv.entity_domain('input_select'),
            vol.Optional(ATTR_RAIN_SENSOR): cv.entity_domain('binary_sensor'),
            vol.Optional(ATTR_ZONE_GROUP): cv.string,
            vol.Optional(ATTR_WATER,default=DFLT_WATER): cv.string,
            vol.Optional(ATTR_WAIT): cv.string,
            vol.Optional(ATTR_REPEAT): cv.string,
            vol.Optional(ATTR_IGNORE_RAIN_SENSOR): cv.string,
            vol.Optional(ATTR_ENABLE_ZONE, DFLT_ENABLE_ZONE): cv.string,
        }],
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

_LOGGER = logging.getLogger(__name__)


async def _async_create_entities(hass, config):
    '''Create the Template switches.'''
    switches = []

    for device, device_config in config[CONF_SWITCHES].items():
        friendly_name           = device_config.get(CONF_FRIENDLY_NAME)
        start_time              = device_config.get(ATTR_START)
        show_config             = device_config.get(ATTR_HIDE_CONFIG)
        run_freq                = device_config.get(ATTR_RUN_FREQ)
        irrigation_on           = device_config.get(ATTR_IRRIGATION_ON)
        reset                   = device_config.get(ATTR_RESET)
        zones                   = device_config.get(ATTR_ZONES)
        unique_id               = device_config.get(CONF_UNIQUE_ID)
        monitor_controller      = device_config.get(ATTR_MONITOR_CONTROLLER)
        inter_zone_delay        = device_config.get(ATTR_DELAY)

        switches.append(
            IrrigationProgram(
                hass,
                device,
                friendly_name,
                start_time,
                show_config,
                run_freq,
                irrigation_on,
                monitor_controller,
                inter_zone_delay,
                reset,
                zones,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    '''Set up the irrigation switches.'''
    async_add_entities(await _async_create_entities(hass, config))

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        'set_run_zone',
        {
            vol.Required(ATTR_ZONE): cv.string,
        },
        "entity_run_zone",
    )


class IrrigationProgram(SwitchEntity, RestoreEntity):
    '''Representation of an Irrigation program.'''
    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        start_time,
        show_config,
        run_freq,
        irrigation_on,
        monitor_controller,
        inter_zone_delay,
        reset,
        zones,
        unique_id,
    ):

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )

        '''Initialize a Irrigation program.'''
        self.hass                = hass
        self._friendly_name      = friendly_name
        if self._friendly_name is None:
            self._friendly_name  = str(device_id).title()        
        self._start_time         = start_time
        self._show_config        = show_config
        self._run_freq           = run_freq
        self._irrigation_on      = irrigation_on
        self._monitor_controller = monitor_controller
        self._inter_zone_delay   = inter_zone_delay
        self._zones              = zones
        self._state_attributes   = None
        self._state              = False
        self._unique_id          = unique_id
        self._stop               = False
        self._device_id          = device_id
        self._last_run           = None
        self._triggered_manually = True
        self._template           = None
        self._reset_last_ran     = reset
        self._irrigationzones    = []
        self._pumps              = []
        self._run_zone           = None

        ''' defaults for metric and imperial '''
#todo: add to the config for user setting
        if self.hass.config.units.name == 'metric':
            self._water_intial = DFLT_WATER_INITIAL_M
            self._water_max    = DFLT_WATER_MAX_M
            self._water_step   = DFLT_WATER_STEP_M
            self._water_uom    = 'L'
        else:
            self._water_intial = DFLT_WATER_INITIAL_I
            self._water_max    = DFLT_WATER_MAX_I
            self._water_step   = DFLT_WATER_STEP_I
            self._water_uom    = 'Gal'
        self._wait_max         = DFLT_WAIT_MAX
        self._repeat_max       = DFLT_REPEAT_MAX
#        if zone.get(ATTR_FLOW_SENSOR) is not None:
#            self._water_intial = DFLT_WATER_INITIAL_T
#            self._water_max    = DFLT_WATER_MAX_T
#            self._water_step   = DFLT_WATER_STEP_T
#            self._water_uom    = 'min'
            

        ''' Validate and Build a template from the attributes provided '''
        a = 'input_datetime.'+slugify(self._friendly_name + "_" + ATTR_START)
        template = "states('sensor.time')" + " + ':00' == states('" + a + "') "

        a = 'input_boolean.'+slugify(self._friendly_name + "_" + ATTR_IRRIGATION_ON)
        template = template + " and is_state('" + a + "', 'on') "

        if self._monitor_controller is not None:
            template = template + " and is_state('" + self._monitor_controller + "', 'on') "

        template = "{{ " + template + " }}"

        _LOGGER.debug('-------------------- on start: %s ----------------------------',self._friendly_name)
        _LOGGER.debug('Template: %s', template)

        template       = cv.template(template)
        template.hass  = hass
        self._template = template


    @callback
    def _update_state(self, result):
        super()._update_state(result)

    async def async_added_to_hass(self):

        state = await self.async_get_last_state()
        self._last_run = None
        if state is not None:
            self._last_run = state.attributes.get(ATTR_LAST_RAN)
        '''ensure the last ran date is set'''
        try:
            z = dt_util.as_timestamp(self._last_run)
        except:
            self._last_run = dt_util.now() - timedelta(days=10)

        self._ATTRS = {}
        self._ATTRS [ATTR_LAST_RAN]    = self._last_run

        local_name = self._start_time
        a = slugify(self._friendly_name + "_" + ATTR_START)
        await create_input_datetime(a, local_name, False, True)
        
        local_name = self._show_config
        a = slugify(self._friendly_name + "_" + ATTR_HIDE_CONFIG)
        await create_input_boolean(a, local_name,icon='mdi:cog-outline')
        
        local_name = self._irrigation_on
        a = slugify(self._friendly_name + "_" + ATTR_IRRIGATION_ON)
        await create_input_boolean(a, local_name,icon='mdi:power')
        self._slug_irrigation_on = a

        if self._inter_zone_delay is not None:
            local_name = self._inter_zone_delay
            a = slugify(self._friendly_name + "_" + ATTR_DELAY)
            await create_input_number(a,local_name,0,30,1,'slider','sec','mdi:timelapse')
            self._slug_inter_zone_delay = a

        if self._run_freq is not None:
            self._ATTRS [ATTR_RUN_FREQ] = self._run_freq
        if self._monitor_controller is not None:
            self._ATTRS [ATTR_MONITOR_CONTROLLER] = self._monitor_controller

        ''' zone loop to set the attributes '''
        zn = 0
        pumps = {}
        for zone in self._zones:
            zn += 1

            '''create pump - zone list '''
            if zone.get(ATTR_PUMP) is not None:
                if zone.get(ATTR_PUMP) not in pumps:
                    pumps[zone.get(ATTR_PUMP)] = [zone.get(ATTR_ZONE)]
                else:
                    pumps[zone.get(ATTR_PUMP)].append(zone.get(ATTR_ZONE))

            ''' Build Zone Attributes to support the custom card '''
            z_name = slugify(zone.get(CONF_NAME,self.hass.states.get(zone.get(ATTR_ZONE)).name))
            a = slugify('zone%s_%s' % (zn, CONF_NAME))
            self._ATTRS [a] = z_name

            ''' set the last ran time '''
            a =  slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_LAST_RAN))
            z_last_ran = None
            try:
                z_last_ran = state.attributes.get(a)
                try:
                    z = dt_util.as_timestamp(z_last_ran)
                except:
                    z_last_ran = dt_util.now() - timedelta(days=10)
            except:
                pass
            if z_last_ran is None:
                z_last_ran = dt_util.now() - timedelta(days=10)
            self._ATTRS [a] = z_last_ran

            a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_REMAINING))
            self._ATTRS [a] = ('%d:%02d:%02d' % (0, 0, 0))

            if zone.get(ATTR_FLOW_SENSOR) is not None:
                self._water_intial = DFLT_WATER_INITIAL_T
                self._water_max    = DFLT_WATER_MAX_T
                self._water_step   = DFLT_WATER_STEP_T
                self._water_uom    = 'min'

            a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_WATER))
            local_name = zone.get(ATTR_WATER, DFLT_WATER)
            await create_input_number(a,local_name,self._water_intial,self._water_max,self._water_step,'slider',self._water_uom,'mdi:water')
            z_water = ('%s.%s'% ('input_number',a))

            z_hist_flow = None
            if zone.get(ATTR_FLOW_SENSOR) is not None:
                a = slugify('%s_%s_%s' % (self._friendly_name ,z_name, ATTR_FLOW_SENSOR))
                self._ATTRS [a] = zone.get(ATTR_FLOW_SENSOR)
                a = slugify('%s_%s_%s' % (self._friendly_name ,z_name, 'historical_flow'))
                if state is not None:
                    z_hist_flow = state.attributes.get(a)
                if z_hist_flow is None:
                    z_hist_flow = 1

            z_wait = None
            z_repeat = None
            if zone.get(ATTR_WAIT) is not None or zone.get(ATTR_REPEAT) is not None:
                a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_WAIT))
                local_name = zone.get(ATTR_WAIT, DFLT_WAIT)
                await create_input_number(a,local_name,1,self._wait_max,1,'slider','min','mdi:timer-sand')
                z_wait = ('%s.%s' % ('input_number',a))
                a = slugify('%s_%s_%s' % (self._friendly_name, z_name, ATTR_REPEAT))
                local_name = zone.get(ATTR_REPEAT, DFLT_REPEAT)
                await create_input_number(a,local_name,1,self._repeat_max,1,'slider','','mdi:repeat')
                z_repeat = ('%s.%s' % ('input_number',a))

            z_zone_group = None
            if zone.get(ATTR_ZONE_GROUP) is not None:
                a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_ZONE_GROUP))
                local_name = zone.get(ATTR_ZONE_GROUP, DFLT_ZONE_GROUP)
                await create_input_text(a,local_name,1,10, icon='mdi:home-group')
                z_zone_group = ('%s.%s' % ('input_text',a))

            if zone.get(ATTR_WATER_ADJUST) is not None:
                a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_WATER_ADJUST))
                self._ATTRS [a] = zone.get(ATTR_WATER_ADJUST)
            if zone.get(ATTR_RUN_FREQ) is not None:
                a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_RUN_FREQ))
                self._ATTRS [a] = zone.get(ATTR_RUN_FREQ)

            z_ignore_rain_sensor = None
            if zone.get(ATTR_RAIN_SENSOR) is not None:
                a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_RAIN_SENSOR))
                self._ATTRS [a] = zone.get(ATTR_RAIN_SENSOR)
                ''' create the ignore feature'''
                a = slugify('%s_%s_%s' % (self._friendly_name, z_name, ATTR_IGNORE_RAIN_SENSOR))
                local_name = zone.get(ATTR_IGNORE_RAIN_SENSOR, DFLT_IGNORE_RAIN_SENSOR)
                await create_input_boolean(a, local_name,icon='mdi:water-alert-outline')
                z_ignore_rain_sensor = ('%s.%s' % ('input_boolean',a))

            a = slugify('%s_%s_%s' % (self._friendly_name,z_name, ATTR_ENABLE_ZONE))
            local_name = zone.get(ATTR_ENABLE_ZONE, DFLT_ENABLE_ZONE)
            await create_input_boolean(a, local_name,icon='mdi:power')
            z_enable_zone = ('%s.%s' % ('input_boolean',a))
            

            self._irrigationzones.append(irrigationzone(self.hass,
                                                        z_name,
                                                        zone.get(ATTR_ZONE),
                                                        zone.get(ATTR_PUMP),
                                                        zone.get(ATTR_RUN_FREQ,self._run_freq),
                                                        zone.get(ATTR_RAIN_SENSOR),
                                                        z_ignore_rain_sensor,
                                                        z_enable_zone,
                                                        zone.get(ATTR_FLOW_SENSOR),
                                                        z_hist_flow,
                                                        z_water,
                                                        zone.get(ATTR_WATER_ADJUST),
                                                        z_wait,
                                                        z_repeat,
                                                        z_last_ran,
                                                        z_zone_group,
                                                        ))


        self._ATTRS ['zone_count'] = zn
        setattr(self, '_state_attributes', self._ATTRS)
        ''' create pump class to start/stop pumps '''
        for thispump in pumps:
            self._pumps.append (pumpclass(self.hass, thispump, pumps[thispump]))
        ''' start pump monitoring '''

        loop = asyncio.get_event_loop()
        for thispump in self._pumps:
            loop.create_task(thispump.async_monitor())

        ''' house keeping to help ensure solenoids are in a safe state '''
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.async_turn_off())

        @callback
        async def template_check(entity, old_state, new_state):
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            '''Triggered when HASS has fully started'''

            ''' Validate the referenced objects now that HASS has started'''
            if  self.hass.states.async_available('sensor.time'):
                _LOGGER.error('%s not defined check your configuration, ' + \
                                'if sensor.time has not been defined the irriagtion program will not behave as expected' \
                                ,'sensor.time')

            if self._monitor_controller is not None:
                if  self.hass.states.async_available(self._monitor_controller):
                    _LOGGER.warning('%s not found, check your configuration',self._monitor_controller)

            if self._run_freq is not None:
                if  self.hass.states.async_available(self._run_freq):
                    _LOGGER.warning('%s not found, check your configuration',self._run_freq)

            ''' run validation over the zones '''
            zn = 0
            for zone in self._zones:
                x = self._irrigationzones[zn-1].validate()
                zn += 1

            '''Update template on startup '''
            async_track_state_change(
                self.hass, 'sensor.time', template_check)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)

        await super().async_added_to_hass()

    def entity_run_zone(self, zone: str) -> None:
        self._run_zone = zone
        self._triggered_manually = True

    @property
    def name(self):
        '''Return the name of the variable.'''
        return self._friendly_name

    @property
    def friendly_name(self):
        '''Return the name of the variable.'''
        if self._friendly_name is None:
            self._friendly_name      = str(self._device_id).title()
        else:
            self._friendly_name      = str(self._friendly_name).title()
        return self._friendly_name

    @property
    def unique_id(self):
        '''Return the unique id of this switch.'''
        return self._unique_id

    @property
    def is_on(self):
        '''Return true if light is on.'''
        return self._state

    @property
    def should_poll(self):
        '''If entity should be polled.'''
        return False

    @property
    def state_attributes(self):
        '''Return the state attributes.
        Implemented by component base class.
        '''
        return self._state_attributes

    async def async_update(self):

        '''Turn on the irrigation based on the input parameters'''
        if self._state == False:
            if self._template.async_render():
                self._run_zone = None
                self._triggered_manually = False
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):

        def format_run_time(runtime):
            hourmin = divmod(runtime,3600)
            minsec = divmod(hourmin[1],60)
            return ('%d:%02d:%02d' % (hourmin[0], minsec[0], minsec[1]))

        def delay_required(groups, runninggroup):
            delay_required = False
            findnext = False
            for group in groups:
                if group == runninggroup:
                    findnext = True
                    continue
                if findnext == True:
                    delay_required = True
                    break           
            return delay_required

        ''' Initialise for stop programs service call '''
        z_zone_found  = False
        self._stop    = False

        ''' use this to set the last ran attribute of the zones '''
        p_last_ran = dt_util.now()

        groups = {}
        zn = 0
        for zone in self._zones:
            zn += 1
            z_name  = self._irrigationzones[zn-1].name()
            ''' determine if the zone has been manually run'''
            if self._run_zone:
                if z_name != self._run_zone:
                    continue
            '''should the zone run, rain, frequency ...'''
            if self._irrigationzones[zn-1].enable_zone_value() == False:
                continue
            if not self._triggered_manually:
                if self._irrigationzones[zn-1].is_raining():
                    continue
                if self._irrigationzones[zn-1].should_run() == False:
                    continue
            '''build zone groupings that will run concurrently'''
            if self._irrigationzones[zn-1].zone_group_value() is not None:
                zone_group = self._irrigationzones[zn-1].zone_group_value()
                if not zone_group:
                    groupkey = zn
                else:
                    groupkey = "G" + zone_group
                if groupkey in groups:
                  groups[groupkey].append(zn)
                else:
                  groups[groupkey] = [zn]
            else:
                groups[zn] = [zn]
            
            zoneremaining = slugify('%s_%s_%s' % (self._friendly_name,z_name,ATTR_REMAINING))
            self._ATTRS [zoneremaining] = format_run_time(self._irrigationzones[zn-1].run_time())
        setattr(self, '_state_attributes', self._ATTRS)

        zone_groups = groups.values()
        _LOGGER.debug('zone_groups %s', zone_groups)
        self._state   = True
        self.async_write_ha_state()

        '''loop through zone_groups'''
        first_group = True
        for group in zone_groups:
            ''' if this is the second set trigger interzone delay if defined'''
            if not self._stop:
                if not first_group and self._slug_inter_zone_delay is not None:
                    izd = int(float(self.hass.states.get('input_number.' + self._slug_inter_zone_delay).state))
                    '''check if there is a next zone'''
                    if delay_required(groups, group):
                        if izd > 0 :
                            await asyncio.sleep(izd)
            first_group = False
            
            '''start each zone'''
            loop = asyncio.get_event_loop()
            if not self._stop:
                for zn in group:
                    loop.create_task(self._irrigationzones[zn-1].async_turn_on())
                    event_data = {
                        "device_id": self._device_id,
                        "zone": self._irrigationzones[zn-1].name(),
                        "pump": self._irrigationzones[zn-1].pump(),
                    }
                    self.hass.bus.async_fire("zone_turned_on", event_data)
                    await asyncio.sleep(1)

            '''wait for the zones to complete'''
            zns_running = True
            while zns_running:
                zns_running = False
                for zn in group:
                    a = slugify('%s_%s_%s' % (self._friendly_name,self._irrigationzones[zn-1].name(),ATTR_REMAINING))
                    self._ATTRS [a] = format_run_time(self._irrigationzones[zn-1].remaining_time())
                    '''continue running until all zones have completed'''
                    if self._irrigationzones[zn-1].remaining_time() != 0:
                        zns_running = True
                setattr(self, '_state_attributes', self._ATTRS)
                self.async_write_ha_state()
                await asyncio.sleep(1)

            '''set last run datetime for each zone'''
            for zn in group:
                ''' Update the zones last ran time '''
                zonelastran = slugify('%s_%s_%s' % (self._friendly_name,self._irrigationzones[zn-1].name(), ATTR_LAST_RAN))                
                if not self._triggered_manually and not self._stop:
                    self._ATTRS[zonelastran] = p_last_ran
                    self._irrigationzones[zn-1].set_last_ran(p_last_ran)
                ''' reset the last ran time to 23 hours ago - for debug'''
                if self._reset_last_ran:
                    self._ATTRS[zonelastran] = dt_util.now() - timedelta(hours=23)
                ''' update the historical flow rate '''
                if self._irrigationzones[zn-1].flow_sensor():
                    a = slugify('%s_%s_%s' % (self._friendly_name ,self._irrigationzones[zn-1].name(), 'historical_flow'))
                    self._ATTRS [a] = self._irrigationzones[zn-1].hist_flow_rate()
                ''' reset the time remaining to 0 '''
                if self._irrigationzones[zn-1].flow_sensor():
                    a = slugify('%s_%s_%s' % (self._friendly_name,self._irrigationzones[zn-1].name(),ATTR_REMAINING))
                    self._ATTRS [a] = ('%d:%02d:%02d' % (0, 0, 0))

                setattr(self, '_state_attributes', self._ATTRS)
                result = self.async_schedule_update_ha_state()

        setattr(self, '_state_attributes', self._ATTRS)

        self._run_zone              = None
        self._state                 = False
        self._triggered_manually    = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):

        self._stop          = True

        zn = 0
        for zone in self._zones:
            await self._irrigationzones[zn].async_turn_off()
            zn += 1
