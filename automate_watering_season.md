There has been interest in automating the start and end of the watering season. THe following automation makes use of the inbuild calendar funtionality.

1. Create a local calendar, https://www.home-assistant.io/integrations/calendar, I named mine 'local'
2. Add the 'Watering Season' entry with the desired start and end dates, using the calendar link in the sidebar
3. For testing, the calendar does not refresh immediately so set the start at least 15 minutes into the future.
4. Check that the 'enable_program' switch name is consistent with your implementation
```
alias: Calendar
description: ""
triggers:
  - trigger: calendar
    entity_id: calendar.local
    event: start
    offset: "0:0:0"
  - trigger: calendar
    entity_id: calendar.local
    event: end
    offset: "0:0:0"
mode: parallel
max: 10
conditions:
  - condition: template
    value_template: "{{ 'Watering Season' in trigger.calendar_event.summary }}"
actions:
  - if:
      - condition: template
        value_template: "{{ trigger.event == 'start' }}"
    then:
      - data: {}
        target:
          entity_id: switch.enable_program
        action: switch.turn_on
      - action: notify.persistent_notification
        metadata: {}
        data:
          message: Watering Season started
    else:
      - data: {}
        target:
          entity_id: switch.enable_program
        action: switch.turn_off
      - action: notify.persistent_notification
        metadata: {}
        data:
          message: Watering Season ended
```
