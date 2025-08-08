Support for https://github.com/thomasloven/lovelace-card-mod.
Allows you to apply CSS styles to various elements of the Home Assistant frontend.

!\[image](https://user-images.githubusercontent.com/40281772/219922995-611c4fde-9f5f-48ba-8d5e-544149516704.png)

```
type: custom:irrigation-card-test
program: switch.test\_irrigation
entities:
  - switch.dummy\_2
show\_program: false
card\_mod:
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
|--state-active-color: blue;| change the colour of the input\_boolean icon 'on' state|
|--state-switch-active-color: blue;|change the colour of switch entity icons |
|--paper-item-icon-color: red; |set the icon inactive 'off' state colour|
|--mdc-theme-primary: black; |set the colour of the program run/stop text|
|--paper-slider-active-color: red; |change the slider colour left of the knob|
|--paper-slider-knob-color: red;| knob colour when the slider is not at the minimum value|
|--paper-slider-knob-start-color: red;|Knob colour when the slider is at the minimum value|
|--paper-slider-pin-color: red;|colour of the slider value callout|
|--paper-slider-pin-start-color: red;|colour of the slider value callout when at the minimum value|
|--paper-slider-container-color: red;|colour of the line to the right of the knob|
