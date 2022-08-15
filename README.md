# Irrigation Component V5 <img src="https://github.com/petergridge/irrigation_component_v4/blob/main/icon.png" alt="drawing" width="75"/>

This release is a significant change in the configuration from Version 4. While the functionality remains the same the configuration load is greatly reduced. 

Helpers are now automatically created when the display name is defined. 
* Input_text, input_number and input_boolean helpers are automatically created. 
* Providing the display text will trigger the creation of the helpers. 
* Where the helpers are mandatory or provide core funtionality they will be created with default display text. 

sees the delivery of a **custom card https://github.com/petergridge/irrigation_card** to render the program options specified in the configuration.

The driver for this project is to provide an easy to use interface for the gardener of the house. The goal is that once the inital configuration is done all the features can be modified using the custom lovelace card. With this upgrade the component is also simple to configure.

This program is essentially a scheduling tool, one user has also used this to schedule the running of his lawn mower, so the use is far broader than I anticipated.

The information provided by the configuraton is evaluated to trigger the irrigation action according to the inputs provided.

Watering can occur in an ECO mode where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles. The wait and repeat configuration is optional.

The rain sensor is implemented as a binary_sensor, this allows practically any combination of sensors to suspend the irrigation. This can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.

Implemented as a switch, you can start a program using the schedule, manually or using an automation. Manually starting a program by turning the switch on will not evaluate the rain sensor rules it will just run the program, as there is an assumption that there is an intent to run the program regardless of sensors.

Only one program can run at a time by default to prevent multiple solenoids being activated. If program start times result in an overlap the running program will be stopped. Zones can be configured to run concurrently or sequentially.

## INSTALLATION

### To create a working sample
* Copy the custom_components/irrigationprogram folder to the ‘config/custom components/’ directory
* Restart Home Assistant
* Copy the 'irrigationtest.yaml' file to the packages directory or into configuration.yaml
* Restart Home Assistant
* Install irrigation_custom_card from this repository **https://github.com/petergridge/irrigation_card**
* Follow the custom card instructions to add a card for each of: switch.morning, switch.afternoon and switch.night

### Important
* Make sure that all of the objects you reference i.e. switch etc are defined or you will get errors when the irrigationprogram is triggered. Check the log for errors.

### Pre-requisite
* The time_date integration is required
```yaml
sensor:
  - platform: time_date
    display_options:
      - 'time'
      - 'date'
```
### Debug
Add the following to your logger section configuration.yaml
```yaml
logger:
    default: warning
    logs:
        custom_components.irrigationprogram: debug
```
### Rain Sensor feature
If a rain sensor is  defined the zone will be ignored when the value of the sensor is True.

If the irrigation program is run manually the rain sensor value is ignored and all zones will run.

The rain sensor is defined in each zone. You can:
* Define the same sensor for each zone 
* Have a different sensor for different areas
If you configure this oprion a helper to ignore the rain sensor is automatically created

### Time or Volume based watering
You can define a 'flow sensor' that provides a volume/minute rate. eg litres per minute. Once defied the 'water' attribute will be read as volume eg 15 litres not 15 minutes.

This example is for a zone that has been defined with a flow sensor
```yaml
zones:
  - zone: switch.zone_1
    name: Lawn
    water: Water
    flow_sensor: sensor.irrigation_flow_sensor
```

### Zone Group
You can optionally group zones to run concurrently or sequentially. Inputs are from an input_text or input_select helper defined for each zone. Blank groups or where a zone_group is not defined will be sequential zones. Zones are grouped by having the same text value, for example each zone with a value of 'A' will run concurrently.

```
zones:
  - zone: switch.zone_1
    name: Lawn
    water: Water
    zone_group: Zone Group
```

### Monitor Controller feature
If this binary sensor is defined it will not execute a schedule if the controller is offline. This is ideal for ESP Home implementations.

### Watering Adjuster feature
As an alternative to the rain sensor you can also use the watering adjustment. With this feature the integrator is responsible to provide the value using a input_number component. I imagine that this would be based on weather data or a moisture sensor.

See the **https://github.com/petergridge/openweathremaphistory** for a companion custom sensor that may be useful.

Setting *water_adjustment* attribute allows a factor to be applied to the watering time.

* If the factor is 0 no watering will occur
* If the factor is 0.5 watering will run for only half the configured watering time/volume. Wait and repeat attributes are unaffected.
* A factor of 1.1 could also be used to apply 10% more water if required.

The following automation is an example of how the input_number.adjust_run_time could be maintained
```yaml
automation:
- id: '1553507967550'
  alias: rain adjuster
  mode: restart
  trigger:
  - platform: time_pattern
    minutes: "/1"
  action:
    - service: input_number.set_value
      entity_id: input_number.rain_adjuster
      data:
        value: "{{ value template calculation }}"
```

### Run Days and Run Frequency
Run frequency allows the definition of when the program will run.

This can be a specific set of days or the number of days between watering events. This can be defined at the Program or zone level. Application at the zone level allows different zones to execute at the same time but using varying frequencies. for example: Vege Patch every two days and the Lawn once a week.

* *Run Freq* allows the water to occur at a specified frequency, for example, every 3 days or only on Monday, Wednesday and Saturday. 

Defining a selection list to use with the run_freq attribute, remove the options you don't want to use.
```yaml
input_select:
  irrigation_freq:
    name: Zone1 Frequency
    options:
      - "1"
      - "2"
      - "3"
      - "4"
      - "5"
      - "6"
      - "7"
      - "['Wed','Sat']"
      - "['Sun','Thu']"
      - "['Mon','Fri']"
      - "['Tue','Sat']"
      - "['Sun','Wed']"
      - "['Mon','Thu']"
      - "['Tue','Fri']"
      - "['Mon','Wed','Fri']"
      - "['Mon','Tue','Wed','Thu','Fri','Sat','Sun']"
```

### ECO feature
The ECO feature allows multiple short watering cycles to be configure for a zone in the program to minimise run off and wastage. Setting the optional configuration of the Wait, Repeat attributes of a zone will enable the feature. 

* *wait* sets the length of time to wait between watering cycles
* *repeat* defines the number of watering cycles to run

## CONFIGURATION

A self contained working sample configuration is provided in the packages directory of this repository.

### Example configuration.yaml entry
```yaml

switch:
      - platform: irrigationprogram
        switches: 
          afternoon:
            irrigation_on: Enable irrigation
            friendly_name: Afternoon Program
            start_time: Start time
            show_config: Show configuration
            run_freq: input_select.irrigation_freq
            inter_zone_delay: Inter zone delay
            controller_monitor: binary_sensor.controller_active
            zones:
              - zone: switch.zone_1
                pump: switch.pump
                zone_group: Zone group
                water: Water
                wait: Wait
                repeat: Repeat
                rain_sensor: binary_sensor.raining
                enable_zone: Enable zone
                water_adjustment: input_number.irrigation_adjust_water
                flow_sensor: input_number.irrigation_flow_sensor
                run_freq: input_select.afternoon_zone1_frequency
```
## MANUALLY CREATED INPUTS
You will need to created the following entities if you want to use the features.
|Attribute       |Valid types   |Description|
|:---            |:---   |:---       |
|zone|switch|This is the switch that represents the solenoid to be triggered. This is the only mandatory manually created element|
|[run_freq](#run-days-and-run-frequency)|input_select|Indicate how often to run. If not provided will run every day|
|[controller_monitor](#monitor-controller-feature)|binary_sensor|If your controller can provide a sensor to detect if the irrigation controller is online. Schedule will not execute if offline|
|[water_adjustment](#water-adjustment-feature)|sensor, input_number|Provide this if you want to affect the amount of watering without changing the base timing based on external information. A multiplication factor applied to decrease or increase the watering time|
|[flow_sensor](#time-or-volume-based-watering)|sensor|Provide this sensoe if you have a flow meter and want to water based on volume not time|
|[rain_sensor](#rain-sensor-feature)|binary_sensor|True or On will prevent the irrigation starting|

## AUTOMATICALLY CREATED INPUTS
These inputs will be created for every instance. If no friendly name is provided a default value will be used.
The naming convention for inputs is:
* program_entity for program level inputs. e.g. afternoon_start_time
* program_zone_entity for zone level inputs e.g. afternoon_lawn_enable_zone

|Attribute       |Description|
|:---            |:---       |
|start_time|If the friendly name is not defined the defaul value will be 'Start time'|
|show_config|If the friendly name is not defined the defaul value will be 'Show configuration'|
|irrigation_on|If the friendly name is not defined the defaul value will be 'Enable irrigation' |
|water|If the friendly name is not defined the defaul value will be 'Water'|
|enable_zone|If the friendly name is not defined the defaul value will be 'Enable zone'|
|ignore_rain_sensor|This item will created if rain sensor is defined. If the friendly name is not defined the defaul value will be 'Ignore rain sensor'|

## INPUTS CREATED ONLY WHEN FUNCTIONALITY IS NEEDED
These inputs will be created only if a friendly name is defined. Create these if you need to implent the funtionality they provide.
|Attribute       |Description|
|:---            |:---       |
|inter_zone_delay|Display name for the auto generated helper, for example 'Inter zone Delay' |
|name|This is the name displayed for the zone, if not provided the friendly name from the associated switch will be used|
|[wait](#eco-feature)|Display name for the auto generated helper, for example 'Wait'. Wait time of the water/wait/repeat ECO option|
|[repeat](#eco-feature)|Display name for the auto generated helper, for example 'Repeat'. The number of cycles to run water/wait/repeat|
|[zone_group](#zone-group)|Display name for the auto generated helper, default is Zone Group|

## CONFIGURATION VARIABLES
The definition of the YAML configuration:
|Attribute       |Type   |Mandatory|Description|
|:---            |:---   |:---     |:---       |
|&nbsp;&nbsp;&nbsp;&nbsp;friendly_name|string|Optional|Display name for the irrigationprogram switch|
|&nbsp;&nbsp;&nbsp;&nbsp;start_time|string |Optional|Display name for the auto generated helper, this item will created if not defined with a display value of 'Start time'|
|&nbsp;&nbsp;&nbsp;&nbsp;show_config|string |Optional|Display name for the auto generated helper, this item will created if not defined with a display value of 'Show configuration' |
|&nbsp;&nbsp;&nbsp;&nbsp;[run_freq](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will run every day|
|&nbsp;&nbsp;&nbsp;&nbsp;[controller_monitor](#monitor-controller-feature)|binary_sensor|Optional|Detect if the irrigation controller is online. Schedule will not execute if offline|
|&nbsp;&nbsp;&nbsp;&nbsp;irrigation_on|string |Optional|Display name for the auto generated helper, this item will created if not defined with a display value of 'Enable irrigation'|
|&nbsp;&nbsp;&nbsp;&nbsp;inter_zone_delay|string |Optional|Display name for the auto generated helper, for example 'Inter zone Delay' |
|&nbsp;&nbsp;&nbsp;&nbsp;zones|list|Required|List of zones to run|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;zone|switch|Required|This is the switch that represents the solenoid to be triggered|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name|string|Optional|This is the name displayed for the zone|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;water|string |Optional|Display name for the auto generated helper, this item will created if not defined with a display value of 'Water' |
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[water_adjustment](#water-adjustment-feature)|sensor, input_number|Optional|A factor,applied to the watering time to decrease or increase the watering time|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[wait](#eco-feature)|string |Optional|Display name for the auto generated helper, for example 'Wait'. Wait time of the water/wait/repeat ECO option|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[repeat](#eco-feature)|string |Optional|Display name for the auto generated helper, for example 'Repeat'. The number of cycles to run water/wait/repeat|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[flow_sensor](#time-or-volume-based-watering)|sensor|Optional|Provides flow rate per minute. The water value will now be assessed as volume|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[rain_sensor](#rain-sensor-feature)|binary_sensor  |Optional|True or On will prevent the irrigation starting|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ignore_rain_sensor|string |Optional|Display name for the auto generated helper, this item will created if rain sensor is defined with a display value of 'Ignore rain sensor'|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[zone_group](#zone-group)|string |Optional|Display name for the auto generated helper, default is Zone Group|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[run_freq](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will default to the Program level value|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;enable_zone|string |Optional|Display name for the auto generated helper, this item will created if not defined with a display value of 'Enable zone'. Disableing a zone, prevents it from running in either manual or scheduled executions|

## SERVICES
```yaml
irrigationprogram.stop_programs:
    description: Stop any running program.
```

## REVISION HISTORY

### 5.0.0
* Essentially the same functionality as version 4
* Major redevelopment of the configuration 
* auto create helper entities that do not require intervention. All input_boolean, input_text, input_number, input_datetime are now created automatically if required.
* When optional funtionality requires a helper only the friendly name is required to trigger the creation of the object.
* Requires Irrigration Custom Card V5.0.0

