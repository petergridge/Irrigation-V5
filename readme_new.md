
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=homeassistantcommunitystore)](https://github.com/hacs/integration) [![my_badge](https://img.shields.io/badge/Home%20Assistant-Community-41BDF5.svg?logo=homeassistant)](https://community.home-assistant.io/t/irrigation-custom-component-with-custom-card/124370) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/hassfest.yml?branch=main&label=hassfest) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/HACS.yml?branch=main&label=HACS)  ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/total) ![GitHub release (latest by date)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/latest/total) ![GitHub Downloads (all assets, specific tag)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/V2024.10.03/total)

### Can you help with a translation? Contact me!
Now more than in previous versions a translation will help users. Translations are easier than ever to create and will add to the home assistant community.

Create a PR, contact me using the community link above, or raise and issue on GitHub, [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/translate.md).

## This Release V2024.11.xx

This has been a significant redevelopment.
All helper objects are now created automatically. All you need to configure now are the switches/valves and sensors.

Naming of entities is determined using the translation files. These have gaps so please volunteer to update or provide new file. Contact me if you can help, it is not a complex process.

The custom card has been updated for this release, the move to entities rather than attributes on the program switch have allowed for a richer experience leveraging the icon translation capabilities introduced in January.

It is now easier to get data with the integration of the [Diagnostics](#Diagnostics)

Frequency can now be determined as an offset of Sunrise or Sunset.

However this is a **BREAKING CHANGE**:
- I recommend that you remove your existing configuration, you will get a few configuration errors if you do not, but it will work.
- You can remove the helpers that have been created for Frequency, Start time ... These will be automatically created now.
- The name of entities entities is dependant on the translation files. Please reach out if you can help translate the files.
- Setting frequency and start time via a sensor is no longer possible

## Content
- [Installation](#Installation)
- [Custom card](#custom-card)
- [Features](#features)
- [Configuration](#configuration)
- [Release history](#release-history)

# Overview

The driver for this project is to provide an easy-to-use interface for the gardener of the house. The goal is that once the initial configuration is done all the features can be modified using the custom lovelace card.

The [Start time](#what-time-will-the-program-start) can be based on sunrise, sunset, single or multiple times.

Watering can occur in an [ECO mode](#what-is-eco-mode) where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles. Great for pots.

Supports watering by [time or volume](#Time-v-Volume).

A number of sensor inputs are available to stop or modify the watering based on external inputs.
* The [rain sensor](#rain-sensor-feature) this requires a binary sensor. This can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.
* The [water adjustment](#what-do-sensors-do) provides for a factor to be applied to the watering time/volume either increasing or decreasing watering based on external inputs
  * The [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory) control provides sensors that may be useful, this provides access to history and forecast weather information to allow you to expose sensors that can be used.

The program issues Home Assistant [events](#events) so you can undertake other automations if required.

There is also support for a [pump or master solenoid](#Pump-or-master-solenoid) and running [programs](#Concurrent-programs) sequentially or concurrently.

The included [custom card](#custom-card) renders the program configuration as a card and is installed automatically.


# Installation[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)

### HACS installation
* Adding the repository using HACS is the simplest approach. The Custom Card deployed with the component, no need to install separately.

### Config Flow
* Define the program using the UI. From Setting, Devices & Services choose 'ADD INTEGRATION'. Search for Irrigation Controller Component.
* Add the integration many times if you want more than one program.
* Modify programs and zones, add new zones, delete zones

### Basic Configuration
All entities to support the features are created automatically. You only need to provide the switches, valves for zones and pumps and external sensors that provide information to the system.

### Test configuration
[testhelpers.yaml](https://raw.githubusercontent.com/petergridge/Irrigation-V5/main/testhelpers.yaml) provides the configuration to support all the objects for three zones. A set of template switches for the zones and pump as well as inputs to emulate rain and flow sensors.

This allows you to test the program without triggering any 'real' solenoids and will allow you to mimic your configuration in new versions to ensure an operational configuration after coming out your winter hibernation.

Be aware this is a simulation, variations in latency or behaviour of individual implementations will have an impact.

### Diagnostics
Diagnostic information can be downloaded and shared using from the integration menu
<img width="615" alt="image" src="https://github.com/user-attachments/assets/8d9ba4f7-d86e-46b5-a3d6-8962070fd49d">


# Custom Card[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)
The custom card is installed with the component.
<img width="656" alt="image" src="https://github.com/user-attachments/assets/4f62ed90-6a51-46f1-983d-ca5ce3423baa">

The card can be set to display one or more zones to support flexibility
- The program selection will list only Irrigation Controller entities
- If no zones are selected all zones will be displayed in the card
- The show program option show/hides the program component of the card
- :mdi:cog


# Features[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)
This section provides details of how the program operates.

### Are Rain Bird controllers supported?
Controllers supported by the [Rain Bird](https://www.home-assistant.io/integrations/rainbird/) Home Assistant integration are supported. The RainBird API will be used to start the zones bypassing the default runtime limitation.


### What time will the program start?
Four options are available to configure the start time. These can be selected from the 'Advanced option' menu in the configuration.
- Selector
  - Provides a time selector to input the scheduled start time.
- Multi time
  - Provides a text input to all the entry of multiple state times for a program, for example 6am and 6pm
- Sunrise
  - calculates the start time based on the sunrise time provided by the sun integration. A slider provides the ability to offset the time by +/- 4 hours
- Sunset
  - calculates the start time based on the sunset time provided by the sun integration. A slider provides the ability to offset the time by +/- 4 hours

### When will the program run?
The schedule can be configured to:
- To run every 'n' days, 1 = every day, 2 = every two days and so on.
- On specific week days, 'sun,tue,thu' will run the program on Sunday, Tuesday and Thursday only.

The schedule can be set at:
- The program level to apply to all zones.
- On each zone. This allows the program to run different zones at varying tempos allowing the lawn to be watered weekly and the pots every 2.
- A combination of both
    - If both are set the zone level frequency is used.

### What will stop a program or zone while it is running?
- When the program is disabled all zones will stop
- When the zone is disabled the zone will stop
- When the water source (well) sensor is no longer active
- The rain sensor will allow currently running program to complete

There is a short delay to allow for false readings, a change in state will not immediately terminate the program or zone.

### Why don't changes in the rain sensor and adjustment impact running zones
- Some users have soil sensors to determine the adjustment. If this sensor modified the operation of the zone it would impact the watering time adversly.
- When the rain sensor activates during a watering cycle the program will continue until completed.

### What will stop the program initiating?
- When the Program is disabled (off)
- When all zones are disabled

### What will disable a zone?
- When it is disabled (off)
- When the rain sensor is active (on)
- When the adjustment value is zero (0)
- When the water source (well) sensor is inactive (off)

### Can I bypass the sensors?
- Ignore sensors
    - This will ignore the state of the Rain Sensor
    - Adjustment will default to one (1)
    - Water source sensor will me ignored

### What is zone transition?
The zone transition sets the overlap or wait time between zones. This can be used to manage 'hammering' when zones stop and start, or support occasions where your solenoid requires back pressure to operate effectively.

### What do the sensors do?
Several sensors can be defined
- A rain sensor can be defined on each zone if active this will prevent the zone activating.
- Water source or well sensor, if inactive it will prevent any activation and stop running zones after a 5 second delay.
- Adjustment, this sensor is expected to provide a factor greater than or equal to 0, this is a multiplier applied to the watering time/volume. Use this to adjust the amount of water applied, less on rainy days, more on hot days.

### You can ignore the sensors
Ignoring sensors will result in the program running regardless of the state of the three sensors.

### Time v Volume
- Watering can be controlled using time
- If you have a calibrated flow sensor water can be measured by volume. If flow falls to zero for longer than 5 seconds the zone will stop.

### Pump or master solenoid
You can define a pump or master solenoid to be triggered with each zone. This valve will remain on for 5 seconds between zones to limit unnecessary cycling of the pump.

### What is ECO mode?
Configuring ECO mode on a zone will provision the wait and repeat options. This is used to limit run off by allowing for multiple short watering cycles to encourage the water to penetrate the soil. Ideal for pot plants.

### Concurrent programs
You can configure multiple programs, by default if program executions overlap the second program will terminate the active one. This can be disabled in the advance options of the configuration. The setting must be updated on each program instance.

### Next run behaviour
The next run is set from the start time and frequency provided. Changing the start time forward will initialise a new run even if it has already run on that day.

### Last ran
This is set after any successful completion of the zone. All zones triggered together will have the same last ran value set.

### Events
Events allow you to trigger other actions when the irrigation program progresses through a program.

*program_turned_on*
- scheduled: false indicates the program was run manually
```event_type: irrigation_event
data:
  action: program_turned_on
  device_id: switch.test
  scheduled: true|false
  program: test
```
*program_turned_off*
- completed:  indicates the program was not teminated during the run by a sensor or manually
```
event_type: irrigation_event
data:
  action: program_turned_off
  device_id: switch.test
  program: test
```
*zone_turned_on*
- scheduled: true|false indicates the zone was run manually
```
event_type: irrigation_event
data:
  action: zone_turned_on
  device_id: switch.zone_3
  scheduled: true|false
  zone:  Zone 3
  pump: null
  runtime: 59
  water: 1
  wait: 0
  repeat: 1
```
*zone_turned_off*
- state: The state after the zone was turned off
```
event_type: irrigation_event
data:
  action: zone_turned_off
  device_id: switch.dummy_3
  zone: dummy_3
  latency: false
  state: eco|off|aborted
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

# Configuration[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)
The configuration of the program initiates the creation of supporting helper entities that enable scheduling you irrigation system.

The most basic implementation only requires:
- The program name
- zone switch
All supporting entities are created for you.

## Program definition

### Name
The name you enter for the program is used to generate a recognisable switch entity that is the foundation of the component.

### Program wide frequency
Selecting this provides the frequency of operation for all zones that do not have a zone frequency option defined. If you do not select this a zone frequency will be automatically created for each zone.

### Frequency options
The options selected/created here are used across the program and zone frequency selectors and supports:
- Numeric values: 1 = every day, 2 = every second day and so on.
- Day of week: valid values are Mon, Tue, Wed, Thu, Fri, Sat, Sun. When a day is selected the program will only execute the defined day.
- Days of the week: Wed,Sat. When selected the program will run on Wednesday and Saturday. This supports specific water restriction is some jurisdictions.

📝 You can extend this by entering your own frequency options for example Mon, Wed, Fri. New groups can only be made up of days of the week.


### Controller type
Selecting the RainBird controller this will result in the RainBird API being used to start the zones bypassing the default runtime limitation.

Uses the rainbird.start_irrigation action to run for a specific period see: [Rain Bird](https://www.home-assistant.io/integrations/rainbird/)

## Zone Definition

### Zone Group
You can optionally configure multiple solenoids to activate concurrently.
- Create a switch group, group helper. This feature allows you to group switches to operate as a single switch.
- All solenoids will operate for the same time.
- You can use this 'new' switch/valve to define a zone.

### Zone
The Valve or Switch that is exposed in home assistant to operate the irrigation solenoid.
📝 Only open and close commands are supported for the valve implementation. Position based valves are not supported.

### Zone Frequency
Specifying the Zone frequency option will provide the ability for a zone to have an independent frequency from the rest of the program. For example, pot plants can be watered daily but lawns every three days in a single program definition.
📝 The frequency options are defined in the program configuration.

### ECO feature
Selecting the ECO feature will provide the Wait/Repeat options to support multiple short watering cycles to limit the runoff. Particularly useful to allow water to penetrate pot plants.

### Pump
Defining the Pump valve/switch supports the control of a pump or master solenoid.
📝 Only open and close commands are supported for the valve implementation. Position based valves are not supported.

### Flow sensor
When defined the system operates on the delivery of volume rather than watering for a specified time.
- The flow sensor is monitored to determine the volume of water delivered and varies the watering time dynamically.
- If the flow sensor value is 0, the zone will terminate after 5 minutes.
- The ignore senor feature has no impact on this sensor.

### Adjustment Sensor
This expects a numeric sensor, input value greater than or equal to 0.

The value is multiplied against the watering time/volume.
- If there has been rain or rain is expected. you could reduce the water time by the a value being < 1.
- Or if a hot spell is expected you can increase the watering requirement by the value being > 1.
- When the ignore senor option is active, treats this value as 1.
💡Check out [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory)
- This exposes weather data to support the creation of sensors that can be used for this feature.

### Rain Sensor
This expects a true/false binary sensor input. If the value is True, the zone will be suspended and the zone status indication updated. Watering will continue if the rain sensor is activated once watering commences.
- When the ignore senor feature is active, treats this value as false.

### Water Source
This expects a true/false binary sensor input. Used to monitor a well status and prevent watering if the water drops below a certain level. Watering will be stopped if this sensor is activated.
- When the ignore senor feature is active, treats this value as true.

### Zone Order
Use this to alter the run sequence of the zones. The value increments by 10 as a default to support easier redefinition of the sort order.


## Advanced options

### Concurrent program execution (interlock)
This option allows or prevents two programs executing concurrently, when enabled (default) the second program to run will terminate the running program. A persistent notification is created to highlight the occurrence.

### Start time options
Select an option to change the method that the start time is defined.
Options available:
- Time selector, supporting the selection of a single start time for the program
- Multi start, provides a text input that accepts multiple start times for example 08:00:00,18:00:00 to run at 6am and 6pm.
- Sunrise, this provides the base start time of sunrise with an option to offset the time using a numeric slider
- Sunset, this provides the base start time of sunset with an option to offset the time using a numeric slider

Sunrise and sunset are obtained from the SUN integration.



# Release history[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)
### V2024.11.01
**Breaking Change**
- Recommend removing and re-adding the configuration
- Removed capability to set frequency via a sensor
- Helpers defined to support start time, frequency, config... are no longer required
- Remove controller monitor functionality
- Custom card refined

A significant redevelopment
  - Updated documentation
  - New start time options
  - Internalised the frequency capability
  - All entities that previously required helpers are now created (and cleaned up) automatically
  - Functionality is updated and reflects the documentation
  - Ignore sensor functions operates on Well, Rain and Adjustment sensors
  - Remove controller monitor functionality
  - Add persistent notifications when the program is terminated as a result of sensor input.
### V2024.10.xx
* Manage entity register when zone is deleted
* Fix run frequency issues
### V2024.09.xx
* Reorder zones in the config flow
* Modify the listing config action to include values of the items
* Support sensor for start time, for example the sun sensor to start a program at dawn.
* Support +/- inter zone delay (delay between zone/overlap of zones)
* Improve start/stop processing of zones while a program is running, if a zone is started while a program is running it will be appended to the run.
* Add translation for status values in the card
* Add French translation
* Support for Valve objects - Open/Close only, Position not supported
* Refactor datetime usage for a more consistent approach
* Fix system monitor notification
* Update to hass.config_entries.async_forward_entry_setups
