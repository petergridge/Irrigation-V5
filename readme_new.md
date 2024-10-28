## Content
- [Custom card](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#custom-card)
- [Operation](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#operation)
- [Configuration](https://github.com/petergridge/Irrigation-V5/blob/main/readme_new.md#configuration)
- Release notes

# Custom Card
The custom card is installed with the component.
![image](https://github.com/user-attachments/assets/a1a802aa-661c-4d06-90d1-d4a894093475)



# Operation
This section provides details of how the program operates.

### Enable options
![image](https://github.com/user-attachments/assets/fa08bd64-ab21-4176-9887-f18688ad7205)

Helpers are created to allow the disabling of the program or zones.
- Program is disabled
  - Program and zones will not start in any circumstance
- Zone is disabled
  - Will still start on the manual execution of the Program or zone
  - Will not start on a scheduled event

### Ignore options
Helpers are created to support ignoring sensors that impact the operation of the program
- Ignore rain sensor
- Ignore adjustment
The water source sensor is always honoured as this may impact install pumps.

### Zone Transition
![image](https://github.com/user-attachments/assets/aa29dc28-47d1-411a-b8b8-15b4f9f501c9)

Sets the overlap or wait time when zones start. This can be used to manage 'hammering' when zones stop and start








# Configuration
The configuration of the program initiates the creation of supporting helper entities that support the provision of the various capabilities.

## Program definition

### Name
The name of the program is used to generate a recognisable switch entity that is the foundation of the component.

### Program wide frequency
This provides the frequency of operation for all zones that do not have a specific frequency option defined. If you intend to enable independant frequency for each zone this can be disabled.

### Frequency options
The options selected/created here are used across the program and zone frequency selectors.
This supports:
- numeric values: 1 = every day, 2 = every second day and so on.
- day of week: valid values are mon,tue,wed,thu,fri,sat,sun. When mon is selected the program will only execute on Monday
- day groups: mon,wed,thu. When selected the program will run on Monday, Wednesday and Thursday.

### Monitor controller
This option supports monitoring if the controller is online. If the controller is offline the program will not attempt to start.

### Controller type
If you have a RainBird controller this will result in the RainBird API being used to start the zones bypassing the default runtime limitation.

## Zone Definition

### Zone
The Valve or Switch that is exposed in home assistant that operates the irrigation solenoid.

### Zone Frequency
Specifying the Zone frequency option will provide the ability for a zone to have an independant frequency from the rest of the program. For example, pot plants can be watered daily but lawns every three days in a single program definition.

The frequency options are defined in the program configuration.

### ECO feature
Selecting the ECO feature will provide the Wait/Repeat options to support multiple short watering cycles to limit the run off. Particularly useful to allow water to penetrate pot plants.

### Pump
Defining the Pump valve/switch supports the control of a pump or master solenoid. The pump remains on for several seconds after a zone completes.

### Flow sensor
When defined the system operates on the delivery of volume rather than watering for a specified time. The flow sensor is monitored to determine the volume of water delivered for each cycle.

When coupled with the ECO setting the specified volume is delivered for each repeated cycle.

When the Adjustment sensor is defined the volume to be delivered will be adjusted by thefactor provided

### Adjustment Sensor
It is expected that the senor will provide a multiplying factor to change the defined watering time. If there has been rain or rain is expected you could reduce the watering requirement or if a hot spell is expected you can increase the watering requirement.

💡check out this component [OpenWeatherMap History](https://github.com/petergridge/openweathermaphistory)

### Rain Sensor
This expects a true/false binary input. If the value is True the zone will be suspended and the zone status indication updated. Watering will continue if the rain sensor is activated once watering commences.

### Water Source
This expects a true/false binary input. Used to monitor a well status and prevent watering if the water drops below a certain level. Watering will be stopped if this sensor is activated.

### Zone Order
Use this to alter the run sequence of the zones. The value increments by 10 as a default to support easier redefintion of the sort order.


## Advanced options

### Concurrent program execution (interlock)

This option prevents two programs executing concurrently, the second program to run will terminate the running program. A log entry will is created to highlight the occurence.

⚠️ Warning: if both programs have identical start times neither program will run. 

### Start time options

Options available:
- Time selector, supporting the selction of a single start time for the program
- Multistart, provides an text input that accepts multiple start times for example 08:00:00,18:00:00 to run at 6am and 6pm. 
- Sunrise, this provides the base start time of sunrise with an option to offet the time using a numeric slider
- Sunset, this provides the base start time of sunset with an option to offet the time using a numeric slider

Sunrise and sunset are obtained from the SUN integration.

### Latency
Set the wait time before a zone is reported as offline, This supports implementation where there is a delay in setting the switch/valve state when turned on/off

### Pump delay
Set the delay between a zone stopping and the pump/master solenoid turning off.
