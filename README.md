[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=homeassistantcommunitystore)](https://github.com/hacs/integration) [![my_badge](https://img.shields.io/badge/Home%20Assistant-Community-41BDF5.svg?logo=homeassistant)](https://community.home-assistant.io/t/irrigation-custom-component-with-custom-card/124370)

![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/hassfest.yml?branch=main&label=hassfest) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/HACS.yml?branch=main&label=HACS) ![GitHub release (latest by date)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/latest/total)

### Would you like more language support? Can you help with a translation? Contact me!
Create a PR, contact me using the community link above, or raise and issue on github, [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/translate.md).

### V5.4.13
* Stop pump monitoring starting when program is not required to run
* Add list_configurtion service to support debugging
* Prevent blank names for a program
* Correct issue where program update was not recognised unless a restart
* update HA calls being deprecated

# Irrigation Component V5 <img src="https://github.com/petergridge/Irrigation-V5/blob/main/icon.png" alt="drawing" width="30"/>

The driver for this project is to provide an easy-to-use interface for the gardener of the house. The goal is that once the initial configuration is done all the features can be modified using the custom lovelace card.

This program is essentially a scheduling tool, one user has used this to schedule the running of his lawn mower, so the use is far broader than I anticipated.

Watering can occur in an [ECO mode](#eco-feature) where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles. Great for pots.

Supports watering by [time or volume](#time-or-volume-based-watering).

A number of sensor inputs are available to stop or modify the watering based on external inputs.
* The [rain sensor](#rain-sensor-feature) is implemented as a binary_sensor, this allows a sensor to suspend the irrigation. This can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.
* The [water adjustment](#watering-adjuster-feature) provides for a factor to be applied to the watering time/volume either increasing or decreasing watering based on external inputs
* [Scheduling](#run-days-and-run-frequency) can be configured to support regular watering every number of days or it can be configured to only water on specific days of the week. The schedule can also be supplied by a sensor to allow for changing the watering frequecy automatically based on the season or forecast data.
* The [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory) control provides sensors that may be useful, this provides access to history and forecast weather information to allow you to expose sensors that can be used.

The program issues Home Assistant [events](#events) so you can undertake other automations if required.

There is also support for a [pump or master solenoid](#pump-or-master-solenoid), running [programs](#interlock) or [zones](#zone-group) sequentially or concurrently.

The [custom card](https://github.com/petergridge/Irrigation-Card) renders the program configuration as a card ans is installed automatically. It exposes in addition to the state of each of the configured helpers:
* the remaining run time for the program and zone
* the last run and/or next run details

This [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/help/help.md) will get a basic setup running.

## INSTALLATION

### HACS installation
* Adding the repository using HACS is the simplest approach. From V5.3 a Custom Card deployed with the component, no need to install separately.

### Important
* Make sure that all of the objects you reference i.e. switches, sensors etc are defined or you will get errors when the irrigationprogram is triggered. Check the log for errors.

### Config Flow
* Define the program using the UI. From Setting, Devices & Services choose 'ADD INTEGRATION'. Search for Irrigation Controller Component. 
* Add the integration many times if you want more than one program.
* Modify programs and zones, add new zones, delete zones

### Basic Configuration
You need to define the entities that allow you to control the features you want. I have have moved away from defining the helpers in YAML and create them via the Helpers tab in the Settings, Devices and services paged, I find it easier and there is no need to restart HA when you add new ones. Create the following for a basic setup.

For the Program create these helpers:
- Input_datetime for the program start time (time only)
- Input_boolean to support the enabling/disabling of the program
- Input_select to define the frequency you want the zone to run, you can do this on the program if you want and save a few entities but I have different frequencies on some zones

For each Zone create these helpers:
- Input_number to provide the duration of the watering cycle

This [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/help/help.md) will get a basic setup running, have a read of the notes below and try a few of the other features.

### Test configuration
[testhelpers.yaml](https://raw.githubusercontent.com/petergridge/Irrigation-V5/main/testhelpers.yaml) provides the helper configuration to support all the objects for three zones. A set of template switches for the zones and pump as well as inputs to emulate rain and flow sensors.

This allow me to test the program without triggering any 'real' solenoids, and will allow you to mimic your configuration in new versions to ensure an operational configuration after coming out your winter hinernation.

Be aware this is a sumulation, variatons in latency or behaviour of indivdual implementations will have an impact.

### Debug
Add the following to your logger section configuration.yaml
```yaml
logger:
    default: warning
    logs:
        custom_components.irrigationprogram: debug
```
The following [services](#services) support testing and debugging:
* irrigationprogram.reset_runtime service will reset the last run details
* irrigationprogram.run_simulation will list details of the program based on the currently set attributes

### Rain Sensor feature
If a rain sensor is defined the zone will be ignored when the value of the sensor is True.

If the irrigation program is run manually the rain sensor value is ignored and all zones will run.

The rain sensor is defined in each zone. You can:
* Define the same sensor for each zone 
* Have a different sensor for different areas

If the rain sensor (or other sensor) prevents scheduled watering the program will retry the next day.

### Time or Volume based watering
Watering is by default time based, that is, will run for the minutes set in the *water* entity.

You can define a *flow sensor* on a zone that provides a volume/minute rate. eg litres per minute. Once defined the *water* attribute will be read as volume eg 15 litres not 15 minutes. 

### Start time
You can define the start time using two methods.
* As an input_datetime
   * This supports selecting the start time

![image](https://github.com/petergridge/Irrigation-V5/assets/40281772/9cb6b488-ddab-4b64-beca-0843e956cb19)

* As an input_text
   * This allows you to input multiple start times for the program
   * Time format **MUST** be hh:mm:00, 24 hour time format with 00 as seconds e.g. 18:55:00
   * Each time **MUST** be seperated by a ','
   * Use this regex pattern to help ensure the correct time structure (([0-2][0-9]:[0-5][0-9]:00)(?:,|$)){1,10}
   * If no valid time is supplied the start time will be defaulted to 08:00:00

![image](https://github.com/petergridge/Irrigation-V5/assets/40281772/65dc4606-43e3-43a8-9151-2ea67cab38ed)

### Run Days and Run Frequency
Run frequency allows the definition of when the program will run. This can be provided as dropdown helper or a sensor, see [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory)

Frequency can be set on the zone or program. If both are set the zone level frequency is used. If no frequency is provided the program will run every day at the specified start time.  Application at the zone level allows different zones to execute at the same time of day but use varying frequencies. for example: Vege Patch every two days and the Lawn once a week.

The values provided can be:
* numeric, representing how often to run every 2 days for example.
* days of the week; Mon, Tue etc. These currently only support english abreviations.
* Off or any unsupported text to stop the zone being run.

For Australians you can select to water on specific days of the week to support water restriction rules.

Defining a Dropdown helper to use with the run_freq attribute, for example:
```yaml
    options:
      - off
      - 1
      - 2
      - 3
      - Wed, Sat
      - Mon, Wed, Fri
      - Mon, Tue, Wed, Thu, Fri, Sat, Sun
```
### Unscheduled execution of a zone or program
When a program or zone is triggered manually the following rules are applied:

If the Program is disabled it can still be initiated manually to run all enabled zones.
* If the Program is disabled and the Zone is enabled the zone will run if manually started,
* If the Program is disabled and the Zone is disabled the zone will not run,

If the Zone is disabled it will not run until it is enabled.
* the zone is disabled, or
* the zone frequency is 'Off'

These sensors will be defaulted:
- Water Adjustment will default to 1
- Rain sensor will default to off

### ECO feature
The ECO feature allows multiple short watering cycles to be configure for a zone in the program to minimise run off and wastage. Setting the optional configuration of the Wait, Repeat attributes of a zone will enable the feature. Perfect for pots and can reduce water used by 50%.

* *wait* sets the length of time to wait between watering cycles
* *repeat* defines the number of watering cycles to run

### Pump or master solenoid
You can optionally define a pump/master soleniod to turn on concurrently with the zone. The pump class then monitors the zones that require it and will remain active during zone transitions. The pump will shut off a few seconds after a zone has completed alowing a smooth transition between zones. The pump is only started and monitored when water in started by the custom control.

### Zone Group
You can optionally configure zones to run concurrently. 
Create a switch group, [group helper](https://www.home-assistant.io/integrations/group/). This feature allows you to group switches together to operate as a single switch.

You can use this 'new' switch to define a zone in the program.

### Monitor Controller Feature
If you have binary binary sensor that indicates the status of the watering system hardware, you can use this to prevent this system from initiating watering until the system is active.

For example I use an ESPHome implementation to control the hardware it exposes a status sensor, should the controller lose power or connectivity to Wi-Fi the custom control will not initiate the watering. There is also be a visual indication on the custom card of the status of the controller.

Additionaly, zone switches that are not in a known (on, off) state will not be executed, and a warning message will be logged.

### Watering Adjuster feature
As an alternative to the rain sensor you can use the watering adjustment feature. With this feature the integrator is responsible to provide a multiplier value using a input_number or sensor component. I imagine that this would be based on weather data or a moisture sensor.

If a program or zone is run manually the adjustment is ignored and executed with the adjuster value of 1.

See the **https://github.com/petergridge/openweathermaphistory** for a companion custom sensor that may be useful.

Setting *water_adjustment* attribute allows a factor to be applied to the watering time.
* If the factor is 0 no watering will occur
* If the factor is 0.5 watering will run for only half (50%) the configured watering time/volume. Wait and repeat attributes are unaffected.
* A factor of 1.1 could also be used to apply 110% of the water defined watering.
* If you want to water in seconds apply a factor of .0167 will be an approximate solution

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
The *program_turned_on* event provides the following:
- scheduled: false indicates the program was run manually
```
event_type: irrigation_event
data:
  action: program_turned_on
  device_id: switch.test
  scheduled: true
  program: test
```
The *program_turned_off* event provides the following:
- completed:  true indicates the program was not teminated manually
```
event_type: irrigation_event
data:
  action: program_turned_off
  device_id: switch.test
  completed: true
  program: test
```
The *zone_turned_on* event provides this information:
- scheduled: false indicates the zone was run manually
```
event_type: irrigation_event
data:
  action: zone_turned_on
  device_id: switch.test
  scheduled: true
  zone: dummy_3
  pump: null
  runtime: 59
  water: 1
  wait: 0
  repeat: 1
```
The *zone_turned_off* event provides this information:
- latency: true indicates that the zone could not be confirmed as off
- state:  the state of the switch when the event was raised
```
event_type: irrigation_event
data:
  action: zone_turned_off
  device_id: switch.dummy_3
  zone: dummy_3
  latency: false
  state: "off"
```
The *zone_became_unavailable* event provides this information:
```
event_type: irrigation_event
data:
  action: zone_became_unavailable
  device_id: switch.test
  scheduled: false
  zone: dummy_2
  pump: switch.dummy_pump
  runtime: 59
  water: 1
  wait: 0
  repeat: 1
```

An automation can then use this data to fire on the event you can refine it by adding specific event data.
``` yaml
alias: irrigation_program_starts
description: "do something when the program is initiated on schedule, not manually"
trigger:
  - platform: event
    event_type: irrigation_event
    event_data:
      action: program_turned_on
      scheduled: true
action: ---- Put your action here ----
mode: single
```

## CONFIGURATION

## CONFIGURATION VARIABLES
The definition of the YAML configuration:
|Attribute       |Type   |Mandatory|Description|
|:---            |:---   |:---     |:---       |
|&nbsp;&nbsp;&nbsp;&nbsp;[start_time](#start-time)|input_datetime, input_text |Required| Entity to set the start time of the program. From V5.4 a list of times from an input_text helper will allow the program to run multiple times e.g. 10:00:00, 12:00:00, 14:30:00. Format must be HH24:MM:00 |
|&nbsp;&nbsp;&nbsp;&nbsp;[run_freq](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will run every day|
|&nbsp;&nbsp;&nbsp;&nbsp;[controller_monitor](#monitor-controller-feature)|binary_sensor|Optional|Detect if the irrigation controller is online. Schedule will not execute if offline|
|&nbsp;&nbsp;&nbsp;&nbsp;irrigation_on|input_boolean|Optional|Allows the entire program to be suspend, winter mode|
|&nbsp;&nbsp;&nbsp;&nbsp;inter_zone_delay|input_number|Optional|Allows provision for a delay, in seconds, between a zone completing and the next one starting.|
|&nbsp;&nbsp;&nbsp;&nbsp;zones|||data for setting up a zone|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;zone|switch|Required|This is the switch that represents the solenoid to be triggered|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[water](#time-or-volume-based-watering)|input_number, sensor |Required|The time to run or volume to supply for this zone |
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[water_adjustment](#watering-adjuster-feature)|sensor, input_number|Optional|A factor, applied to the watering time to decrease or increase the watering time|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[wait](#eco-feature)|input_number |Optional|Wait time,in minutes, of the water/wait/repeat ECO option. The effective irrigation time of a zone is water * repeat. Example : If 5 minutes is define in wait and repeat = 2, the final watering duration will be 10 minutes but the run time will be 15 minutes|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[repeat](#eco-feature)|input_number |Optional|The number of cycles to run water/wait/repeat|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[pump](#pump-or-master-solenoid)|switch|Optional|Define the switch that will turn on the pump or master soleniod|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[flow_sensor](#time-or-volume-based-watering)|sensor|Optional|Provides flow rate per minute. The water value will now be assessed as volume|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[rain_sensor](#rain-sensor-feature)|binary_sensor|Optional|True or On will prevent the irrigation starting|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ignore_rain_sensor|input_boolean |Optional|Ignore rain sensor allows a zone to run even if the rain sensor is active|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[zone_group](#zone-group)|input_text |Optional|Zone Group supports running zones concurrently.
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[frequency](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will default to the program level value|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;enable_zone|input_boolean |Optional|Disabling a zone, prevents it from running in either manual or scheduled executions, adding 'Off' or similar text value to the run_freq helper will have the same result|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[interlock](#interlock)|input_boolean |Optional|If set, the default, the program will stop other running programs when triggered|

## SERVICES
```yaml
stop_programs:
  description: Stop any running programs and zones.

run_zone:
  description: run a specific zone.
  fields:
    entity_id:
      name: Irrigation Program
      description: The irrigation program to run
      required: true
      selector:
        entity:
            integration: irrigationprogram
    zone:
      name: Zone
      description: Zones to run
      required: true
      selector:
          entity:
            domain: switch
            multiple: true

reset_runtime:
  description: reset the runtime back to none for the program supports testing.
  fields:
    entity_id:
      name: Entity ID
      description: The irrigation program to run
      required: true
      selector:
        entity:
            integration: irrigationprogram

run_simulation:
  description: Simulate running a program, exectution logic is not called, the functions are and results shown in the log.
  fields:
    entity_id:
      name: Entity ID
      description: The irrigation program to test
      required: true
      selector:
        entity:
            integration: irrigationprogram
```
## REVISION HISTORY
### V5.4.13
* Stop pump monitoring starting when program is not required to run
* Add list_configurtion service to support debugging
* Prevent blank names for a program
* Correct issue where program update was not recognised unless a restart
* update HA calls being depricated
### V5.4.10
* Fix issue with pump monitoring
* Fix issue when no frequency is specified
* Fix issue when program manual run overlaps with scheduled run of the program
* add icons.json
### V5.4.5
* **BREAKING CHANGE: Remove group functionality**.
  * Grouping zones can now be achieved using a switch [group helper](https://www.home-assistant.io/integrations/group/) provided by Home Assistant to present multiple switches as a single switch that can be configured as a zone in this component.
  * There is some loss of functionality, in this new model all switches will have the same parameters, you will no longer be able to have a goup of zones that have different watering times but run concurrently.
  * The helper grouping model is supported already in the current version.
* Correct numeric frequency problem
* Fix issue introduced with V2023.11 of HomeAssistant
### V5.4.2
* Handle scenario where zone switch becomes unavailable mid run
   * Add irrigation_event/zone_became_unavailable event see [Events](#events)
* Codify the behaviour when a zone or program is disabled see [Unscheduled execution of a zone or program](#unscheduled-execution-of-a-zone-or-program)
* Remove warning messages
## 5.4.0
* improved handling of offline solenoid switches
* support multiple start times for a program
## 5.3.5
* Custom Card deployed with this component, no need to install separately. **Uninstall the old HACS Custom Card**.
* Custom Card updated so each zone setting can be expanded independently.
* Custom Card updated to add configuration form
* Fixed issue with WeatherHistory Frequency and water adjustment.
* Added support for RainBird controller 
* Add scheduled/manual options for program simulation

## 5.2.10
* addded support for watering time to be supplied using a sensor
## 5.2.9
* Fix issue with rain sensor
* Fixed issue with next run attribute
## 5.2.8
* resolve incorrect next run for numeric frequency where scheduled run did not proceed 
* Add scheduled/manual options for program simulation
## 5.2.7
* Add next run time attribute. Custom Card will also need to be updated
* Fix spelling mistakes in en.json and strings.json
* Fix stop not working as expected in custom card
## 5.2.6
* refine the manual run behavior, zones will run unless explicitly disabled.
* expand events: program_turned_on, program_turned_off, zone_turned_on, zone_turned_off when a program starts.
* remove requirement for datetime sensor.
## 5.2.5
* remove zone switch monitoring to get around problem with zone switch latency causing the program not to run
* Add warning when latency exceeds 5 seconds when turning off the switch, the switch was not in an 'off' state after 5 seconds
## 5.2.4
* Handle high latency switches
## 5.2.2
# Deprecation notice:
* yaml configuration support has been depricated
* Add input via a sensor for frequency.
## 5.2.1
* Correct issue #15
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
