
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=homeassistantcommunitystore)](https://github.com/hacs/integration) [![my_badge](https://img.shields.io/badge/Home%20Assistant-Community-41BDF5.svg?logo=homeassistant)](https://community.home-assistant.io/t/irrigation-custom-component-with-custom-card/124370) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/hassfest.yml?branch=main&label=hassfest) ![GitHub Workflow Status (with branch)](https://img.shields.io/github/actions/workflow/status/petergridge/Irrigation-V5/HACS.yml?branch=main&label=HACS)  ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/total) ![GitHub release (latest by date)](https://img.shields.io/github/downloads/petergridge/Irrigation-V5/latest/total) 


## V2025.08.02
### Breaking Change
Pump, Water Source and Flow Meter definition have moved from the Zone configuration to the Program configuration to support better pump handling functionality.

A migration will run to populate from the configuration from zone information however the configuration should should be checked.


# IrrigationProgram Custom Component

### Can you help with a translation? Contact me!
Now more than in previous versions a translation will help users. Translations are easier than ever to create and will add to the home assistant community.

Create a PR, contact me using the community link above, or raise and issue on GitHub, [tutorial](https://github.com/petergridge/Irrigation-V5/blob/main/translate.md).

#### German, Spanish. French, Italian, Dutch, Polish and Portuguese translations are now available.


## Experiencing issues with the custom card?
Enable the manual card yaml feature in the advanced setting of the program.This provides the yaml to recreate the custom card as an entities card.
- The script is regenerated each time the configuration is modified.
- Copy the script to a manual card and save.
You will now have the equivalent of the custom card.


## Content
- [Installation](#Installation)
- [Custom card](#custom-card)
- [Important information](#important-information)
- [Features](#features)
- [Configuration](#configuration)
- [Release history](#release-history)

# Overview

The driver for this project is to provide an easy-to-use interface for the gardener of the house. The goal is that once the initial configuration is done all the features can be modified using the custom lovelace card.

The [start time](#what-time-will-the-program-start) can be based on sunrise, sunset, single or multiple times.

Watering can occur in an [ECO mode](#what-is-eco-mode) where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles.

Supports watering by [time or volume](#Time-v-Volume).

A number of sensor inputs can be configured to stop or modify the watering based on external inputs.
* The [rain sensor](#rain-sensor-feature), this requires a binary sensor and can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.
* Water source sensor can be used to ensure that a well has water or stop watering when the well sensor is off.
* [Water adjustment](#what-do-sensors-do) provides for a factor to be applied to the watering time/volume either increasing or decreasing watering based on external inputs.
  * The [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory) component provides sensors that may be useful, this provides history and forecast weather information to allow you to expose sensors that can be used.

The program issues Home Assistant [events](#events) so you can undertake other automations if required.

There is also support for a [pump or master solenoid](#Pump-or-master-solenoid) and running [programs](#Concurrent-programs) sequentially or concurrently.

The included [custom card](#custom-card) renders the program configuration as a card and is installed automatically.


# Installation[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)

### HACS installation
* Adding the repository using HACS is the simplest approach. The Custom Card deployed with the component, no need to install separately.
* look for IrrigationProgram Custom Component
<img width="277" alt="image" src="https://github.com/user-attachments/assets/065f9d00-c223-4112-8158-22e1bdae0633">


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
Diagnostic information can be downloaded from the integration menu
<img width="615" alt="image" src="https://github.com/user-attachments/assets/8d9ba4f7-d86e-46b5-a3d6-8962070fd49d">

### Errors
Issues identified will be shown in the Notification section of the side bar.

# Custom Card[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)
The custom card is installed with the component.
<img width="656" alt="image" src="https://github.com/user-attachments/assets/4f62ed90-6a51-46f1-983d-ca5ce3423baa">

- You can choose to display each zone or the program data in a standalone card. Particularly useful when there are many zones to control the look and feel of the dashboard.
- The program selection will list only Irrigation Controller entities.
- If no zones are selected only the Program will be displayed, use CTRL-CLICK to select multiple zones.
- The show program option shows or hides the program component of the card.

### Additional configuraton options
The following items can be configured by adding the confiugration using the code editor option in the card.

**title:** (optional) The title to be set in the card.

**icon:** (optional) An icon to display to the left of the title.

**theme:** (optional) Override the used theme for this card with any loaded theme. For more information about themes, see the [frontend documentation](https://www.home-assistant.io/integrations/frontend/).

**header:** (optional) Header widget to render an image. See [header/footer documentation](https://www.home-assistant.io/lovelace/header-footer/).

**footer:** (optional) Header widget to render an image. See [header/footer documentation](https://www.home-assistant.io/lovelace/header-footer/).

### Card-Mod

Support for https://github.com/thomasloven/lovelace-card-mod.
Allows you to apply CSS styles to various elements of the Home Assistant frontend.

![image](https://user-images.githubusercontent.com/40281772/219922995-611c4fde-9f5f-48ba-8d5e-544149516704.png)

```
type: custom:irrigation-card-test
program: switch.test_irrigation
entities:
  - switch.dummy_2
show_program: false
card_mod:
  style: |
    ha-card {
      background-image: url('/local/lawn.png');
      --mdc-theme-primary: black;
      }
```
Note: /local/ is the path to the /config/www directory in you home assistant install.

These are some examples, use F12 on Chrome to discover other style options. My explanation of the action are not definitive the style change can affect other components as well. There are many more style options available that will have an impact. Please share examples and action for me to update this list.
 
|example     |action   |
|:---        |:---     |
|background-image: url('/local/lawn.png');|to set a background image|
|background-repeat: no-repeat; |to prevent the image repeating to fill the card|
|color: red; |set the general text colour|
|--state-active-color: blue;| change the colour of the input_boolean icon 'on' state|
|--state-switch-active-color: blue;|change the colour of switch entity icons |
|--paper-item-icon-color: red; |set the icon inactive 'off' state colour|
|--mdc-theme-primary: black; |set the colour of the program run/stop text|
|--paper-slider-active-color: red; |change the slider colour left of the knob|
|--paper-slider-knob-color: red;| knob colour when the slider is not at the minimum value|
|--paper-slider-knob-start-color: red;|Knob colour when the slider is at the minimum value|
|--paper-slider-pin-color: red;|colour of the slider value callout|
|--paper-slider-pin-start-color: red;|colour of the slider value callout when at the minimum value|
|--paper-slider-container-color: red;|colour of the line to the right of the knob|


# Important information[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)

### Switch State
The component relies on accurate switch state information. Some hardware does not update the state of a switch when it turns on or off. The program will wait 5 seconds for the switch to change state after attempting to turn it on or off. If the state has not updated to the expected value the zone will abort and a notification raised.

If the switch becomes unavailable the program the zone will abort and a notification raised

### Debounce Delay
When a change that results in a program being aborted occurs, there is a 5 second delay to accommodate any false readings. For example if the rain sensor switched from off to on and then off again within 5 seconds the program will continue.


# Features[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)
This section provides details of how the program operates.

### Are Rain Bird controllers supported?
Controllers supported by the [Rain Bird](https://www.home-assistant.io/integrations/rainbird/) Home Assistant integration are supported. The RainBird API will be used to start the zones bypassing the default runtime limitation. There have been reports of issues with the Rain Bird implementation not updating the state of the switch in some circumstances. This will result in a notification indicating a latency problem. This has been noted when using a negative zone transition value.

### Are B-Hyve controllers supported?
Controllers supported by the [Orbit B-Hyve](https://github.com/sebr/bhyve-home-assistant) from HACS are supported. The B-HYVEAPI will be used to start the zones bypassing the default runtime limitation. There may be issues with using a negative zone transition values.

### What time will the program start?
Four options are available to configure the start time. These can be selected from the [Advanced option](#advanced-options) menu in the configuration.
- Selector
  - Provides a time selector to input the scheduled start time.
- Multi time
  - Provides a text input to enter multiple start times for a program, for example 6am and 6pm
- Sunrise
  - calculates the start time based on the sunrise time provided by the sun integration. A slider provides the ability to offset the time by +/- 4 hours
- Sunset
  - calculates the start time based on the sunset time provided by the sun integration. A slider provides the ability to offset the time by +/- 4 hours

### When will the program run?
The schedule can be configured to:
- To run every 'n' days, 1 = every day, 2 = every two days and so on.
- On specific week days, 'Sun, Tue, Thu' will run the program on Sunday, Tuesday and Thursday only.

The schedule can be set at:
- The program level to apply to all zones.
- On each zone. This allows the program to run different zones at varying tempos allowing the lawn to be watered weekly and the pots every 2.
- A combination of both, if both are set the zone level frequency is used.


Automate the watering season using inbuilt [calendar funtionality](https://github.com/petergridge/Irrigation-V5/blob/main/automate_watering_season.md) to enable/disable the program.

### What will stop a program or zone while it is running?
- When the program is disabled all zones will stop.
- When the zone is disabled the zone will stop.
- When the water source (well) sensor is no longer active.
- The rain sensor will stop a currently running program, [advanced options](#advanced-options) support running completion.

### Why don't changes in the rain sensor and adjustment impact running zones
- Some users have soil sensors to determine the adjustment. If this sensor modified the operation of the zone it would impact the watering time adversely.
- When the rain sensor activates during a watering cycle it is optional for the program to continue until completed.

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
    - Water source sensor will be ignored

### What is zone transition?
The zone transition sets the overlap or wait time between zones. This can be used to manage 'hammering' when zones stop and start, or support occasions where your solenoid requires back pressure to operate effectively. A slider allowing +/- 10 seconds is provided.

### Pause a program.
You can pause and resume a program from the custom card or programaticaly. When paused the running zone will be turned off and the remaining program suspended until the program is resumed.

There is an example of automating the pause feature [here](https://github.com/petergridge/Irrigation-V5/blob/main/pause.md)

### What do the sensors do?
Several sensors can be defined
- A rain sensor can be defined on each zone if active this will prevent the zone activating. [Advanced options](#advanced-options) are available to allow a running program to complete.
- Water source or well sensor, if inactive it will prevent any activation and stop running zones after a 5 second delay.
- Adjustment, this sensor is expected to provide a factor greater than or equal to 0, this is a multiplier applied to the watering time/volume. Use this to adjust the amount of water applied, less on rainy days, more on hot days. If the value is 0 the zone will not run.

### Can multiple zones run at the same time?
You can set the degree of parallel run in the program configuration. A value of 1 will result in the zones runing sequentially. A value of 2 will let two zones run simultanteously the practical limit is the water pressure and number of sprinklers in your zones.

You can also create a switch group using HomeAssistant helper functionality. A group set up this way will allow multiple zones to be treated as a single switch. All the grouped switches will have the same run profile/duration.

### Can two programs run at the same time.
You can configure multiple programs to run together, by default if program executions overlap the second program will terminate the active one. This can be disabled in the advance options of the configuration. The setting must be updated on each program instance.

### Time v Volume
- Watering can be controlled using time
- If you have a calibrated flow sensor water can be measured by volume. If flow falls to zero for longer than 5 seconds the zone will stop.

### Pump or master solenoid
You can define a pump or master solenoid to be triggered with each zone. This valve will remain on for 5 seconds between zones to limit unnecessary cycling of the pump.

### What is ECO mode?
Configuring ECO mode on a zone will provision the wait and repeat options. This is used to limit run off by allowing for multiple short watering cycles to encourage the water to penetrate the soil. Ideal for pot plants.

### Next run behaviour
The next run is set from the start time and frequency provided. Changing the start time forward will initialise a new run even if it has already run on that day.

### Last ran
This is set after any successful completion of the zone. All zones triggered together will have the same last ran value set.

### Events
The following events are raised by this component and could be used to trigger other actions when the irrigation program is processed.

  #### Program events
  1. Fired when the program is turned on
```
  event_data = {
      "action": "program_turned_on",
      "device_id": entity_id,
      "scheduled": True/False,
      "program": name,
  }
```
  2. Fired when the program is turned off
```
  event_data = {
    "action": "program_turned_off",
    "device_id": entity_id,
    "program": name,
  }
```
  #### Zone events
  1. fired when the switch is not reporting 'OFF' after being turned off.
```
  event_data = {
    "action": "error",
    "error": "Switch can not be confirmed as OFF",
    "device_id": entity_id,
    "scheduled": True/False,
    "program": name,
  }
```
  2. fired when the switch is not reporting ON after being turned on.
```
  event_data = {
    "action": "error",
    "error": "Switch cannot be confirmed as ON",
    "device_id": entity_id,
    "scheduled": True/False,
    "program": name,
  }
```
  3. Reported when rain is detected with settings that will stop the program
```
  event_data = {
    "action": "error",
    "error": "Rain has been detected",
    "device_id": entity_id,
    "scheduled": True/False,
    "program": name,
  }
```
  4. Fired when the water source is reporting no water is available
```
  event_data = {
    "action": "error",
    "error": "No water source detected",
    "device_id": entity_id,
    "scheduled": True/False,
    "program": name,
  }
```
  5. Fired when a solenoid is turned on
```
  event_data = {
    "action": "zone_turned_on",
    "device_id": solenoid,
    "pump": pump,
    "scheduled": True/False,
    "zone": name,
    "runtime": remaining_time,
    "water": water,
    "wait": wait,
    "repeat": repeat,
  }
```
  6. Fired when a solenoid is turned off
```
  event_data = {
    "action": "zone_turned_off",
    "device_id": solenoid,
    "zone": name,
    "state": state,
  }
```
  7. Fired when an unexpected status is reported continuosly for the latency check period while the solenoid is on
```
  event_data = {
    "action": "error",
    "error": "Returned an unexpected state",
    "device_id": entity_id,
    "scheduled": True/False,
    "program": name,
    "state":  status
  }
```
  8. Fired when the flow sensor continuously reports 0 flow for the latency check period
```
  event_data = {
    "action": "error",
    "error": "No flow detected",
    "device_id": entity_id,
    "scheduled": True/False,
    "program": name,
  }
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
- Days of the week: Enter combinations of days ```Wed, Sat```. When selected the program will run on Wednesday and Saturday. This supports specific water restriction is some jurisdictions.

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
- If the flow sensor value is 0, the zone will terminate after 5 seconds.
- The ignore senor feature has no impact on this sensor.

### Adjustment Sensor
This expects a numeric sensor, input value greater than or equal to 0.

The value is multiplied against the watering time/volume.
- If there has been rain or rain is expected. Reduce the water time with a value < 1.
- Or if a hot spell is expected, increase the watering requirement with a value > 1.
- When the ignore senor option is active, treats this value as 1.
💡Check out [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory)
  - This exposes weather data to support the creation of sensors that can be used for this feature.

#### Using Smart Irrigation - Evapotranspiration watering time calculation.

While you cannot set the watering time directly from another sensor this is a workaround to allow the use of this custom component, https://jeroenterheerdt.github.io/HAsmartirrigation/ available in HACS.

- In the advanced options set the watering unit to seconds:
- Set the adjustment sensor to the Smart Irrigation sensor that provides the watering time for the zone.
- In the zone set the watering time to 1s.

Now when the zone runs the watering time (1) will be multiplied by the Smart Irrigation value to provide the actual run time in seconds.


### Rain Sensor
This expects a true/false binary sensor input. If the value is True, the zone will be suspended and the zone status indication updated.
- When the ignore senor feature is active, treats this value as false.
- [Advanced options](#advanced-options) allows selecting the behaviour when the program is already running:
  - Stop: the program will stop after a short delay, a persistent notification is created to highlight the occurrence
  - Continue: the program will continue to completion


### Water Source
This expects a true/false binary sensor input. Used to monitor a well status and prevent watering if the water drops below a certain level. Watering will be stopped if this sensor is activated.
- When the ignore senor feature is active, treats this value as true.

### Zone Order
Use this to alter the run sequence of the zones. The value increments by 10 as a default to support easier redefinition of the sort order.


## Advanced options

### Concurrent program execution (interlock)
This option allows or prevents two programs executing concurrently.
- Strict - turn off other programs when starting, turn off when another program starts
- Loose - turn off all other programs when starting, stay running unless a 'strict' program starts
- Off - turn off 'strict' programs only, stay running unless a 'strict' program starts

### Start time options
Select an option to change the method that the start time is defined.
Options available:
- Time selector, supporting the selection of a single start time for the program
- Multi start, provides a text input that accepts multiple start times for example 08:00:00,18:00:00 to run at 6am and 6pm.
- Sunrise, this provides the base start time of sunrise with an option to offset the time using a numeric slider
- Sunset, this provides the base start time of sunset with an option to offset the time using a numeric slider

Sunrise and sunset are obtained from the SUN integration.

### Rain sensor behaviour
Allows selecting the behaviour when the program is already running:
  - Stop: the program will stop after a short delay
  - Continue: the program will continue to completion

### Maximum watering time/step
These options change the default settings for the slider to enter time/volume in the custom card.

### Maximum zone transistion delay
Sets the max interzone delay displayed on the card

### Wait time for slow responding devices
Some devices are slow to update this sets the wait time before the program cancels

### Wait time for devices that are slow to start
Similar to above, this a a one off wait time as the program starts to wait for devices to connect to HA.

### Zone parallel execution
This setting allows multiple zones to run concurrently in a program. if set to two, two zones will start and as one finishes another will start. If this setting is selected the zone transition is not available.

### Entities Card yaml generation
This setting enables the production of yaml to implement the equivalent to the custom card. Some users are experiencing issues with the custom card requiring this alternative. The custom card is also based on the entities cards.
The yaml is generated on start and when a program configuration is created or modified.
Insert the generated yaml into a Manual Card.

### Vent exccess pressure after pump stop
This option opens one valve for three seconds after the pump has stop on program completion to release presure from the system.

### Delay next run when rain detected
Enables a delay function to add a number of days before the next run of the program. This feature is designed to be manually enabled, it is not currently related to the rain sensor.

# Release history[🔝](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#Content)

### V2025.08.02
### Breaking Change
Move Pump, Water Source and Flow Meter definition from the Zone to the Program.
A migration will run to populate from the zone information however configuration should should be checked.

- Rewrite of the pump management
  - New option in the advanced setting to set a lead or lag time for starting the pump
    - Negative values will start the pump before the zone starts
    - Positive value will start the pump after the zone starts
- Fix Issue #224, manual start of disabled program

### V2025.08.01
- Prevent programs running concurrently is now binary, ON will prevent programs running concurrently, OFF will allow programs to run together
- Make line venting default not an option
  - Review pump model to improve responsiveness, i.e. start immediately a zone starts. Wait 3 seconds to shut down in all circumstances
- Add Polish translation
- Only create manual card yaml if the configuration has change
- Remove strict validation and termination when latency issues are detected.
  - remove the termination of zones if not reporting the correct status, i.e. reporting a state of on when it is expected to be off.
    - User can control actions by using the events fired to initiate automations to perform the actions required locally.
    - This functionality has been causing issues with some implementations.
  - Attempts to align the state by continuing to send an Off or On command for several cycles
  - Log a debug message when this occurs
  - Report and handle failure when a zone is renamed or removed, but the program not updated
- Add defensive coding to default values for dependant devices that are not ready when the program starts
- Add expected duration to the custom card & entities card yaml alternative.
- Correct remaining time calculation for volume/flow based watering
- Reviewed Program and Zone events https://github.com/petergridge/Irrigation-V5/blob/main/readme.md#events
- Add code to stop zone solenoids and pumps on restart/reload.

### V2025.07.03
  - Update Portugese and German translations
  - More work on slow loading devices, provide warnings is referencecd devices are not available before the program is setup/
  - Modify Zone timing to use datedif instead of a second counter for more accurated zone run time
    - add a warning to identify when the running switch is not indicating the expected state to logging. This may indicate communicaton issues with the irrigation controller/switch
  - Update UI to more clearly show when the program is disabled

### V2025.07.02
- Update venting funtion to turn pump off before zones when a program ends. Issue #199
  - NOTE: The venting function DOES NOT work if ZONES are ended manually
- More French translation updates
- re instate the ability to define a sensor for frequency Issue #154
  - Add the sensor in the same way you add days, validation that the sensor exists occurs.
  - The sensor will appear as one of the selectable options
  - The validation of the sensor value at runtime is limited
  - Check the log if the program does not start as expected
- Add functionality to pause a running program when the water source state becomes OFF Issue #181
  - program resumes when the water source becomes ON
  - Zone will not start if water source is OFF
  - NOTE: There is no timeout
  - Functionality enabled in advanced options
 
### V2025.07.01
- Correct default on interlock option to "strict"
- Update French translation
- More work to support slow loading devices
- Add function to vent the system when a pump is used to release pressure in the system

### V2025.06.05
- Improve check of slow loading devices on start up. Some controllers are slow to reconnect the HA. Issue #182
  - zone
  - rain sensor
  - water source sensor
  - adjustment sensor
  - flow sensor
  Waits up to the configurable 'start latency' value for devices to start.
  Raises an error when times out without the device becoming avaiable
- Add 'start latency' option to the advanced options. Issue #182
  - default 30 seconds, minimum 5 seconds, maximum 60 seconds
  There is no impact to performance if the devices are avaiable immediately
- Update French translations Issue #193
- Correct the pause function, fix delay when enabling pause. Issue #194
- Default frequency to the first option is none is selected. Issue #195

### 2025.06.02
- Allow input_boolean for Rain and Water source
- Allow input number for Adjustment
- During latency check, start solenoid with each 1 second cycle, could assist with zigbee devices
- allow adjustment of latency constant
- add option to create a rain delay
  - adds n days to the frequency intiated.
  - extends the calculated next run by n days, i.e. from last ran date
  - behaviour
    - when turned on adds the selected number of days to the calculated next run
    - turns off whe the program runs
    - can be turned off.
    - applies to all zones of the program
  implementaion
    - Switch to turn off and on
    - input number to set delay
    - option to enable in advanced features

###  V2025.05.02
- Fix lag on stopping programs, prevent program being started until it has completely stopped (1-2 seconds)
###  V2025.05.01
- Handle duration longer than 24 hours. If duration is > 24 hours the remaining time will be 23:59:59 until the remaining time reduces
- Update Dutch translation
- Update max transition time to 120 seconds
- Make wait time seconds based when runtime is defined as seconds
- Fix code to stop the creation of the custom card yaml on start

###  V2025.04.01
- Add Dutch translations
- Add support for B-Hyve (Beta)
- Change remaining time from Duration to Date, renders sensor as h:mm:ss now.

### V2024.12.01
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
