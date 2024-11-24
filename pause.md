## Sample Pause Automation:

One use case for automating the pause feature is to fill a tank from a slow well. 

In this example it takes 30 Minutes to fill the tank and 4 minutes to empty it once watering commences.

The requirement for the automations is:
1. Turn on the pump
2. Repeat while the irrigation program is on
   - Water for 4 Minutes
   - Pause the program
   - Wait for 30 minutes
   - Un-pause the program
3. Turn the pump off

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
