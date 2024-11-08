
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=homeassistantcommunitystore)](https://github.com/hacs/integration) [![my_badge](https://img.shields.io/badge/Home%20Assistant-Community-41BDF5.svg?logo=homeassistant)](https://community.home-assistant.io/t/irrigation-custom-component-with-custom-card/124370) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/hassfest.yml?branch=main&label=hassfest) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/HACS.yml?branch=main&label=HACS)  ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/total) ![GitHub release (latest by date)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/latest/total) ![GitHub Downloads (all assets, specific tag)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/V2024.10.03/total)

### Can you help with a translation? Contact me!
Now more than in previous versions a translation will help users. Translations are easier than ever to create and will add to the home assistant community.

Create a PR, contact me using the community link above, or raise and issue on GitHub, [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/translate.md).

## This Release V2024.11.xx

This has been a significant redevelopment all helper objects are now created automatically.

Naming of entities is determined using the translation files.

The custom card has been updated for this release, the move to entities rather than attributes on the program switch have allowed for a richer experience leveraging the icon translation capabilities introduced in January.

It is now easier to get support data with the integration of the [Diagnostics](#Diagnostics).

Frequency can now be determined as an offset of Sunrise or Sunset.

However this is a **BREAKING CHANGE**:
- I recommend that you remove your existing configuration, you will get a few configuration errors if you do not, but it will work.
- You can remove the helpers that have been created for Frequency, Start time ... These will be automatically created.
- The name of entities entities is dependant on the translation files. Please reach out if you can help translate the files.
- Setting frequency via a sensor is no longer possible

## Content
- [Installation](#Installation)
- [Custom card](#custom-card)
- [Features](#features)
- [Configuration](#configuration)
- [Release history](#release-history)

# Overview

The driver for this project is to provide an easy-to-use interface for the gardener of the house. The goal is that once the initial configuration is done all the features can be modified using the custom lovelace card.

The [Start time](#start-time) can be based on sunrise, sunset, single or multiple times.

Watering can occur in an [ECO mode](#eco-feature) where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles. Great for pots.

Supports watering by [time or volume](#Time-v-Volume).

A number of sensor inputs are available to stop or modify the watering based on external inputs.
* The [rain sensor](#rain-sensor-feature) is implemented as a binary sensor, this allows a sensor to suspend the irrigation. This can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.
* The [water adjustment](#Impact-of-sensors) provides for a factor to be applied to the watering time/volume either increasing or decreasing watering based on external inputs
* [Scheduling](#Frequency) can be configured to support regular watering every number of days or it can be configured to only water on specific days of the week.
* The [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory) control provides sensors that may be useful, this provides access to history and forecast weather information to allow you to expose sensors that can be used.

The program issues Home Assistant [events](#events) so you can undertake other automations if required.

There is also support for a [pump or master solenoid](#Pump-or-master-solenoid), running [programs](#Concurrent-programs) sequentially or concurrently.

The included [custom card](#custom-card) renders the program configuration as a card and is installed automatically.

This [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/help/help_new.md) will get a basic setup running.


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
[testhelpers.yaml](https://raw.githubusercontent.com/petergridge/Irrigation-V5/main/testhelpers.yaml) provides the helper configuration to support all the objects for three zones. A set of template switches for the zones and pump as well as inputs to emulate rain and flow sensors.

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
- To run every n days, 1 = every day, 2 = every two days and so on.
- On specific week days, 'sun,tue,thu' will run the program on Sunday, Tuesday and Thursday only.

The schedule can be set at:
- The program level to apply to all zones.
- On each zone. This allows the program to run different zones at varying tempos allowing the lawn to be watered weekly and the pots every 2.
- A combination of both
    - If both are set the zone level frequency takes precedence.

### What will stop a program or zone while it is running?
- When the program is disabled all zones will stop
- When the zone is disabled the zone will stop
- When the water source (well) sensor is no longer active
- The rain sensor will allow currently running zone to complete, but subsequent zones will not run

There is a short delay to allow for false readings where a change in state will not immediately terminate the program or zone.

### Why don't the rain sensor and adjustment impact running zones
- Some users have soil sensors to determine the adjustment. If this sensor modified the operation of the zone it would impact the watering time adversly.
- When the rain sensor activates during a watering cycle the program will continue

### What will stop the program initiating?
- The controller sensor is inactive (off)
- When the Program is disabled (off)
- When all zones are disabled

### What will disable a zone?
- When it is disabled
- When the rain sensor is active (on)
- When the adjustment value is zero (0)
- When the water source (well) sensor is inactive (off)

### What can you do to bypass a zone that will not run
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
- If you have a calibrated flow sensor water can be measured by volume.

### Pump or master solenoid
You can define a pump or master solenoid to be triggered with each zone. This valve will remain on for 5 seconds between zones to limit unnecessary cycling of the pump.

### What is ECO mode?
Configuring ECO mode on a zone will provision the wait and repeat options. This is used to limit run off by allowing for multiple short watering cycles to encourage the water to penetrate the soil. Ideal for pot plants.

### Concurrent programs
You can configure multiple programs, by default if program executions overlap the second program will terminate the active one. This can be disabled in the advance options of the configuration. The setting must be updated on each program instance.

### Next run behaviour
The next run is set from the start time and frequency provided. Changing the start time forward will initialise a new run if it has already run on that day.

### Last ran
This is set after any successful completion of the zone. All zones triggered together will have the same last ran value set.

### Events
Events allow you to trigger other actions when the irrigation program progresses through a program.

The *program_turned_on* event provides the following:
- scheduled: false indicates the program was run manually
```event_type: irrigation_event
data:
  action: program_turned_on
  device_id: switch.test
  scheduled: true
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
- state: The state after the zone was turned off, off, eco or aborted
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
The configuration of the program initiates the creation of supporting helper entities that support the provision of the various capabilities.

## Program definition

### Name
The name of the program is used to generate a recognisable switch entity that is the foundation of the component.

### Program wide frequency
Selecting this provides the frequency of operation for all zones that do not have a zone frequency option defined. If you do not select this a zone frequency will be automatically created for each zone.

### Frequency options
The options selected/created here are used across the program and zone frequency selectors and supports:
- numeric values: 1 = every day, 2 = every second day and so on.
- day of week: valid values are Mon, Tue, Wed, Thu, Fri, Sat, Sun. When a day/s is selected the program will only execute the defined days.
- day groups: wed,sat. When selected the program will run on Wednesday and Saturday.

📝 You can extend this by entering your own frequency options for example Mon, Wed, Fri.


### Controller type
Selecting the RainBird controller this will result in the RainBird API being used to start the zones bypassing the default runtime limitation.

## Zone Definition

### Zone
The Valve or Switch that is exposed in home assistant that operates the irrigation solenoid.

### Zone Frequency
Specifying the Zone frequency option will provide the ability for a zone to have an independent frequency from the rest of the program. For example, pot plants can be watered daily but lawns every three days in a single program definition.

📝 The frequency options are defined in the program configuration.

### ECO feature
Selecting the ECO feature will provide the Wait/Repeat options to support multiple short watering cycles to limit the runoff. Particularly useful to allow water to penetrate pot plants.

### Pump
Defining the Pump valve/switch supports the control of a pump or master solenoid. The pump remains on for five seconds after a zone completes.

### Flow sensor
When defined the system operates on the delivery of volume rather than watering for a specified time.
- The flow sensor is monitored to determine the volume of water delivered for each cycle.
- When coupled with the ECO setting the specified volume is delivered for each repeated cycle.
- When the Adjustment sensor is defined the volume to be delivered will be adjusted by the factor provided

### Adjustment Sensor
It is expected that the senor will provide a multiplying factor to change the defined watering time. If there has been rain or rain is expected. you could reduce the watering requirement or if a hot spell is expected you can increase the watering requirement.

💡check out this component [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory)

### Rain Sensor
This expects a true/false binary input. If the value is True, the zone will be suspended and the zone status indication updated. Watering will continue if the rain sensor is activated once watering commences.

### Water Source
This expects a true/false binary input. Used to monitor a well status and prevent watering if the water drops below a certain level. Watering will be stopped if this sensor is activated.

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
