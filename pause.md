## Sample Pause Automation:

One use case for automating the pause feature is to fill a tank from a slow well. 

This example could pauses the program when the well is empty and start again when the well is full.

```
alias: Pause Irrigation when well is empty
description: ""
triggers:
  - trigger: state
    entity_id:
      - switch.entity_id: sensor.well_empty
    to: "on"
conditions: []
	- condition: state
	  entity_id: switch.your_irrigrion_program
	  state: "on"
actions:
	- action: homeassistant.turn_on
	  metadata: {}
	  data: {}
	  target:
		entity_id: switch.pause
mode: single


alias: Restart Irrigation when well is full
description: ""
triggers:
  - trigger: state
    entity_id:
      - switch.entity_id: sensor.well_full
    to: "on"
conditions: []
	- condition: state
	  entity_id: entity_id: switch.pause
	  state: "on"
actions:
	- action: homeassistant.turn_off
	  metadata: {}
	  data: {}
	  target:
		entity_id: switch.pause
mode: single
```

In this example it takes 30 Minutes to fill the tank and 4 minutes to empty it once watering commences.
### Triggered when the program starts.
1. Turn on the pump to fill the cistern
2. Repeat while the irrigation program is on
   - Water for 4 Minutes
   - Pause the program
   - Wait for 30 minutes
   - Resume the program
3. Turn the cistern pump off

```
alias: Pause Irrigation to fill from well
description: ""
triggers:
  - trigger: state
    entity_id:
      - switch.irrigation_program
    to: "on"
conditions: []
actions:
  - action: switch.turn_on
    metadata: {}
    data: {}
    target:
      entity_id: switch.pump
  - repeat:
      sequence:
        - delay:
            hours: 0
            minutes: 4
            seconds: 0
            milliseconds: 0
        - action: switch.turn_on
          metadata: {}
          data: {}
          target:
            entity_id: switch.pause
        - delay:
            hours: 0
            minutes: 30
            seconds: 0
            milliseconds: 0
        - action: switch.turn_off
          metadata: {}
          data: {}
          target:
            entity_id: >-
              switch.pause
      while:
        - condition: state
          entity_id: switch.irrigation_program
          state: "on"
  - action: switch.turn_off
    metadata: {}
    data: {}
    target:
      entity_id: switch.pump
mode: single
```
