# Heating Circuit Advisor

A Home Assistant integration that tells whether a heating circuit's **heating curve** fits, from how long the
valves of the rooms it heats are open. It works with any heater whose circuit is a climate entity in Home
Assistant, and any room thermostats and valves: it only reads them, it never writes.

## Why the valves

A heater with a weather-compensated curve sets the flow temperature from the outdoor temperature. The room
thermostats then open and close their valves to hold their setpoints. Their valves show how well the curve fits:

- **Open most of the time** in the room that needs most heat: the flow is barely warm enough. Raise the curve.
- **Rarely open, even there:** the flow is warmer than needed, and heat is wasted. Lower the curve.
- **Open all the time and the room still too cold:** a higher curve would help only a little. Check the loop's
  flow (hydraulic balance) first, then its heating surface.

The room that needs most heat decides, not the average: the curve has to serve it.

## How it judges

- Every 4 minutes it samples each valve's opening (0 to 100 %). For valves switched on and off by a
  time-proportioned thermostat (often a 15-minute cycle), 4 minutes spread the samples over every minute of
  the cycle.
- Each valve's share of time open is a moving average over a window, 24 hours by default.
- Samples count only while the circuit is at its **comfort setpoint** (the highest target seen in the last day)
  and it is colder outside than a limit (15 °C by default). In the setback, or when it is mild, the valves say
  nothing about the curve.
- A verdict needs about 0.8 of the window evaluated. The memory is stored, so a restart loses nothing.
- It compares the circuit's room setpoint with the rooms' too. The flow temperature follows it as well, so a
  circuit setpoint far above every room's heats for nothing. It suggests lowering it only above every room,
  and raising it only below most of them, so that one room set apart does not decide.

| Verdict | Meaning |
|---|---|
| Collecting data | Not enough evaluated time yet |
| Fits | The neediest loop is open between the two limits (15 % and 70 % by default) |
| Too low | The neediest loop is open more than the upper limit: raise the curve, e.g. its correction by 1 K |
| Too high | Even the neediest loop is open less than the lower limit: lower the curve, e.g. its correction by 1 K |
| Heating surface insufficient | The neediest loop is open all the time and its room stays below its setpoint |
| No heating loops | No valve with the label in the rooms, or only rooms switched off |

## Setting it up

1. **Areas:** every room is an area. Its thermostats are the area's climate entities; a thermostat whose device
   is in the area counts too.
2. **Label:** put one label, e.g. `heating loop`, on every valve entity: a floor loop's actuator (a switch, or a
   level in %), a `valve`, or a radiator thermostat's valve level. A valve whose device sits elsewhere (an
   actuator in the boiler room) gets the room's area on the entity itself.
3. **Add the integration** (Settings → Devices & services → Add integration → Heating Circuit Advisor) once per
   circuit: the circuit's climate, the outdoor temperature, the circuit's rooms and the label.

Special cases:

- **A room without a thermostat** (an open kitchen heated by the dining room's thermostat): put it in the circuit
  with its valves; it counts with its valves.
- **A room switched off:** its thermostats off, it is listed but does not judge the curve.
- **A radiator thermostat** is a climate too: give its valve level entity the label. A climate entity with the
  label is a loop (heating or not), not a thermostat.

## Entities

One device per circuit:

| Entity | Content |
|---|---|
| Heating curve | The verdict; the neediest room and loop as attributes |
| Neediest loop open | That loop's share of the time open, in % |
| Loops open on average | All loops' mean share, in % |
| Room setpoint hint | None, lower or raise the circuit's room setpoint; the difference in K as an attribute |
| Evaluating | On while the samples count |
| Data collected | How much of the data a verdict needs is there (diagnostic) |
| Room … | Per room: its neediest loop's share; its thermostats, setpoint, temperature and loops as attributes (diagnostic) |

## Limits

- A valve's level in % is not its heat: a valve 30 % open may pass most of the flow. Shares of levels compare
  well over time and between similar valves, less between a switch and a level.
- Balance the loops' flows first: an unbalanced loop shows as needy whatever the curve.
- Two schedules, the heater's and the thermostats', fight each other: in the heater's setback the thermostats
  open wide to catch up. The comfort phase evaluated is the heater's.

## Installation

Through [HACS](https://hacs.xyz/) as a custom repository (category integration), or copy
`custom_components/heating_circuit_advisor` into your configuration's `custom_components`.

## License

MIT
