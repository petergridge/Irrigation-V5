### Smart Irrigation 

#### Evapotranspiration watering time calculation.

While you cannot set the watering time directly from another sensor this is a workaround to achieve the same result.

- In the advanced options set the watering unit to seconds:
- Set the adjustment sensor to the Smart Irrigation sensor that provides the watering time for the zone.
- In the zone set the watering time to 1s.

Now when the zone runs the watering time (1) will be multiplied by the Smart Irrigation value to provide the actual run time in seconds.
