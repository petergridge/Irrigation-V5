[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=homeassistantcommunitystore)](https://github.com/hacs/integration) [![my_badge](https://img.shields.io/badge/Home%20Assistant-Community-41BDF5.svg?logo=homeassistant)](https://community.home-assistant.io/t/irrigation-custom-component-with-custom-card/124370)

![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/hassfest.yml?branch=main&label=hassfest) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/HACS.yml?branch=main&label=HACS) ![GitHub release (latest by date)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/latest/total)

# Deprecation notice:
* yaml configuration support will be depricated from version 5.2.1 - April 2023

# Irrigation Component V5 <img src="https://github.com/petergridge/Irrigation-V5/blob/main/icon.png" alt="drawing" width="30"/>

The **custom card https://github.com/petergridge/Irrigation-Card** V5.2 will render the program options specified in the configuration and is also available in HACS.

The driver for this project is to provide an easy-to-use interface for the gardener of the house. The goal is that once the initial configuration is done all the features can be modified using the custom lovelace card.

This program is essentially a scheduling tool, one user has used this to schedule the running of his lawn mower, so the use is far broader than I anticipated.

The information provided by the configuration is evaluated to trigger the irrigation action according to the inputs provided.

Watering can occur in an ECO mode where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles. The wait and repeat configuration is optional.

The rain sensor is implemented as a binary_sensor, this allows practically any combination of sensors to suspend the irrigation. This can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.

Implemented as a switch, you can start a program using the schedule, manually or using an automation.

## INSTALLATION

### HACS installation
* Adding the repository using HACS is the simplest approach

### Important
* Make sure that all of the objects you reference i.e. switches, sensors etc are defined or you will get errors when the irrigationprogram is triggered. Check the log for errors.

### Config Flow
* Define the program using the UI. From Setting, Devices & Services choose 'ADD INTEGRATION'. Search for Irrigation Controller Component.
* To define groups first complete the setup of the program and then go back into configuration to add zone groups. (V5.1.20)
* Modify programs and zones, add new zones, delete zones
* V4 yaml configuration will be imported, if it fails to load run check configuration first and correct any changes implemented to support this release.

### Pre-requisite
* The time_date integration is required
```yaml
sensor:
  - platform: time_date
    display_options:
      - 'time'
      - 'date'
```
### Basic Configuration
You need to define the entities that allow you to control the features you want. I have have moved away from defining the helpers in YAML and create them via the Helpers tab in the Settings, Devices and services paged, I find it easier and there is no need to restart HA when you add new ones. Create the following for a basic setup.

For the Program:
- Input_datetime for the program start time (time only)
- Input_boolean  to support the toggling of the configuration in the custom card
- Input_boolean to support the enabling/disabling of the program

For each Zone:
- Input_number to provide the duration of the watering cycle
- Input_select to define the frequency you want the zone to run, you can do this on the program if you want and save a few entities but I have different frequencies on some zones

This will get a basic setup running, have a read of the notes below and try a few of the other features.

### Debug
Add the following to your logger section configuration.yaml
```yaml
logger:
    default: warning
    logs:
        custom_components.irrigationprogram: debug
```
The following services support testing and debugging:
* irrigationprogram.reset_runtime service will reset the last run details
* irrigationprogram.run_simulation will list details of the program based on the currently set attributes

### Rain Sensor feature
If a rain sensor is defined the zone will be ignored when the value of the sensor is True.

If the irrigation program is run manually the rain sensor value is ignored and all zones will run.

The rain sensor is defined in each zone. You can:
* Define the same sensor for each zone 
* Have a different sensor for different areas

### Time or Volume based watering
Watering is by default time based, that is, will run for the minutes set in the *water* entity.

You can define a *flow sensor* on a zone that provides a volume/minute rate. eg litres per minute. Once defined the *water* attribute will be read as volume eg 15 litres not 15 minutes. 

### Run Days and Run Frequency
Run frequency allows the definition of when the program will run.

Frequency can be set on the zone or program. If both are set the zone level frequency is used. If no frequency is provided the program will run every day at the specified start time.  Application at the zone level allows different zones to execute at the same time of day but use varying frequencies. for example: Vege Patch every two days and the Lawn once a week.

The values provided can be:
* numeric, representing how often to run every 2 days for example.
* days of the week; Mon, Tue etc. These currently only support english abreviations.
* Off or any unsupported text to stop the zone being run

For Australians you can select to water on specific days of the week to support water restriction rules.

Defining a Dropdown helper to use with the run_freq attribute, for example:
```yaml
    options:
      - Off
      - 1
      - 2
      - 3
      - Wed, Sat
      - Mon, Wed, Fri
      - Mon, Tue, Wed, Thu, Fri, Sat, Sun
```

### ECO feature
The ECO feature allows multiple short watering cycles to be configure for a zone in the program to minimise run off and wastage. Setting the optional configuration of the Wait, Repeat attributes of a zone will enable the feature. Perfect for pots and can reduce water used by 50%, try it.

* *wait* sets the length of time to wait between watering cycles
* *repeat* defines the number of watering cycles to run

### Pump or master solenoid
You can optionally define a pump/master soleniod to turn on concurrently with the zone. The pump class then monitors the zones that require it and will remain active during zone transitions. The will shut off a few seconds after a zone has completed alowing a smooth transition between zones. Currently the pump class only monitors during a program run cycle.

### Zone Group
You can optionally group zones to run concurrently or sequentially. 

**New V5.2.0** Zone groups are now setup in the config flow. Any existing groups are automatically migrated.

This provides for greater validation, for example:
* a group must have at least two zones, 
* if a zone is deleted the related group will also be deleted, also 
* if the switch associated to a zone is changed the related group will be deleted. 

**Legacy model:** V5.1 and earlier, zones are grouped by having the same text in the input value, for example each zone with a value of 'A' will run concurrently.

### Monitor Controller Feature
If you binary sensor that indicates the status of the watering system hardware, you can use this to prevent this system from initiating watering until the system is active.

For example I use an ESPHome implementation to control the hardware it exposes a status sensor, should the controller lose power or connectivity to Wi-Fi the custom control will not initiate the watering. There is also be a visual indication on the custom card of the status of the controller.

Zone switches that are not in a known (on, off) state will not be executed.

### Watering Adjuster feature
As an alternative to the rain sensor you can use the watering adjustment. With this feature the integrator is responsible to provide a multiplier value using a input_number or sensor component. I imagine that this would be based on weather data or a moisture sensor.

If a program or zone is run manually the adjustment is ignored run as if the adjuster has a value of 1.

See the **https://github.com/petergridge/openweathremaphistory** for a companion custom sensor that may be useful.

Setting *water_adjustment* attribute allows a factor to be applied to the watering time.

* If the factor is 0 no watering will occur
* If the factor is 0.5 watering will run for only half the configured watering time/volume. Wait and repeat attributes are unaffected.
* A factor of 1.1 could also be used to apply 10% more water if required.
* The watering time will always be rounded up to the nearest minute when applying the factor.

The following automation is an example of how an entity could be maintained using template calculation.
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
### Interlock

Turn off running programs when a new program is started, this is the default.
**Note** Change this on all program configurations to get consistent behaviour. 

With interlock enabled:
* If Program 1 and Program 2 have the same start time neither program will run and a warning is logged.
* If Program 2 starts while Program 1 is running Program 1 will be terminated and Program 2 will run, a warning will be logged.

With interlock disabled:
* If Program 1 and 2 overlap both programs will continue to run.
* If a running zone is started by the second program a warning is logged.

### Events

The *zone_turned_on* event provides this information:
```
event_type: irrigation_event
data:
  device_id: switch.test_irrigation
  action: zone_turned_on
  zone: zone_3
  pump: switch.pump
  runtime: 60
  water: 1
  wait: 0
  repeat: 1
time_fired: "2022-08-15T23:33:36.358814+00:00"
context:
  id: 01GAHXP1F6KQWTM6Z6PEJ69KDM
  parent_id: null
  user_id: null
```
An automation can then use this data to fire on the event, in this example it the automation would run only when the *pump* event data is '*switch.pump*'. but you could refine it more to include a specific zone or remove the event data clause and it would run every time the event is triggered. Other triggers can be added if there is a use case for them. Let me know.
``` yaml
alias: pump_keep_alive
description: "Let the pump device know that HA is still alive so it does not time out and shut down"
trigger:
  - platform: event
    event_type: irrigation_event
    event_data:
      pump: switch.pump
      action: zone_turned_on
action: ---- Put your action here ----
mode: single
```

## CONFIGURATION

## CONFIGURATION VARIABLES
The definition of the YAML configuration:
|Attribute       |Type   |Mandatory|Description|
|:---            |:---   |:---     |:---       |
|&nbsp;&nbsp;&nbsp;&nbsp;start_time|input_datetime |Required| entity to set the start time of the program|
|&nbsp;&nbsp;&nbsp;&nbsp;show_config|input_boolean |Optional| 'Show configuration' used to show/hide the configuration in the companion card |
|&nbsp;&nbsp;&nbsp;&nbsp;[run_freq](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will run every day|
|&nbsp;&nbsp;&nbsp;&nbsp;[controller_monitor](#monitor-controller-feature)|binary_sensor|Optional|Detect if the irrigation controller is online. Schedule will not execute if offline|
|&nbsp;&nbsp;&nbsp;&nbsp;irrigation_on|input_boolean|Optional|Allows the entire program to be suspend, winter mode|
|&nbsp;&nbsp;&nbsp;&nbsp;inter_zone_delay|input_number|Optional|Allows provision for a delay between a zone completing and the next one starting. **Will move to to config flow in a future release**|
|&nbsp;&nbsp;&nbsp;&nbsp;zones|||data for setting up a zone|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;zone|switch|Required|This is the switch that represents the solenoid to be triggered|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[water](#time-or-volume-based-watering)|input_number |Required|The time to run or volume to supply for this zone |
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[water_adjustment](#watering-adjuster-feature)|sensor, input_number|Optional|A factor, applied to the watering time to decrease or increase the watering time|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[wait](#eco-feature)|input_number |Optional|Display name for the auto generated helper, for example 'Wait'. Wait time of the water/wait/repeat ECO option|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[repeat](#eco-feature)|input_number |Optional|Display name for the auto generated helper, for example 'Repeat'. The number of cycles to run water/wait/repeat|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[pump](#pump-or-master-solenoid)|switch|Optional|Define the switch that will turn on the pump or master soleniod|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[flow_sensor](#time-or-volume-based-watering)|sensor|Optional|Provides flow rate per minute. The water value will now be assessed as volume|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[rain_sensor](#rain-sensor-feature)|binary_sensor|Optional|True or On will prevent the irrigation starting|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ignore_rain_sensor|input_boolean |Optional|Ignore rain sensor allows a zone to run even if the rain sensor is active|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[zone_group](#zone-group)|input_text |Optional|Zone Group supports running zones concurrently. **Will move to to config flow in a future release V5.2.0**|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[frequency](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will default to the program level value|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;enable_zone|input_boolean |Optional|Disabling a zone, prevents it from running in either manual or scheduled executions, adding 'Off' or similar text value to the run_freq helper will have the same result|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[interlock](#interlock)|input_boolean |Optional|**new V5.1.20** If set, the default, the program will stop other running programs when triggered|

## SERVICES
```yaml
irrigationprogram.stop_programs:
    description: Stop any running program.
```
## REVISION HISTORY

## 5.2.1 - under development - Planned April
* Remove yaml configuration support
## 5.2.0
* Groups in config flow
* Vary Interlock behaviour of programs
* Expand event data provided
* Italian translation file
* Support interactive value changes during program execution
* Link solenoid switch behaviour (off only) with the custom component
* Ability to turn off zones instead of the whole program
* Warnings raised in the log when a program is stopped by another program or service call
* Additional attributes have been added to the event data for the start of a zone
* Add a 5 second delay before zone stops when zero flow is indicated by the flow meter
* Implement hass.config_entries.async_forward_entry_setups required for HA
* Exclude inactive zones, switch is unavailable, from program runs
## 5.1.19
* Fix issue with reloading after a config flow change
* Add program remaining time attribute
* Optimise start and stop logic
* Optimise polling logic
## 5.1.18
* Modify HACS deployment to provide download count from GITHUB
## 5.1.16
* Correct weekday list to work with legacy model
## 5.1.15
* Initial HACS release
* correct config flow handling on a new install
* correct initialisation of last run time on new install
* correct recording of run time against disabled zones
* confirm non numeric/day values in the frequency helper will disable the zone, e.g. 'Off'
* allow comma separated text for weekday list, not case sensitive
* add German translation for config flow
## 5.1.0
* Config Flow - configure via UI
* REMOVED - generated helpers as they are incompatible with config flow
## 5.0.10
* Generated helpers based on entity name not friendly name
* Correct pump issue
* Requires custom Card 5.0.10
## 5.0.9
* Optimise pump class
* Correct watering adjustment and runtime issues
## V5.0.7/8
* Still fixing water adjustment defect
* Improve validation
## V5.0.6
* Fix water adjustment defect
* Modify zone monitoring for pump activation
* Added configuration option for watering time min, max & step
### V5.0.5
* Fix bugs
### V5.0.4
* Fix bug introduced with reset/uninstall
### V5.0.3
* Create selection list helper for frequency if one is not defined
* Add config option to reset/uninstall created helpers
### 5.0.2
* Update Event model now *irrigation_event* event with *action* of 'zone_turned_on'. 
### 5.0.1
* Implement zone_turned_on event to allow custom triggering of other automations if required
* Bug fixed where get_last_state is None
### 5.0.0
* Essentially the same functionality as version 4
* Major redevelopment of the configuration 
* Auto create helper entities that do not require intervention. All input_boolean, input_text, input_number, input_datetime are now created automatically if required.
* When optional functionality requires a helper only the friendly name is required to trigger the creation of the object.
* Requires Irrigation Custom Card V5.0.0

