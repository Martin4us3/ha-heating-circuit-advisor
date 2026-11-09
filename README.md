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

Later, **Configure** changes the rooms, the label, the outdoor temperature and the settings. **Reconfigure** changes
the circuit's climate, e.g. after its entity ID was renamed; title, rooms, settings and what the circuit has
learned stay. Renamed loops are found again by their label, but start their averages anew.

Special cases:

- **A room without a thermostat** (an open kitchen heated by the dining room's thermostat): put it in the circuit
  with its valves; it counts with its valves.
- **A room switched off:** its thermostats off, it is listed but does not judge the curve.
- **A radiator thermostat** is a climate too: give its valve level entity the label. A climate entity with the
  label is a loop (heating or not), not a thermostat.

## Acting on a verdict

The integration only advises; you change the curve on the heater, the way its manual describes.

1. **Wait for a verdict.** Collecting data takes at least a day of cold comfort phases; a mild week takes longer.
2. **Check the neediest room first.** Its attributes list its thermostats, setpoint, temperature and loops. A
   window left open, a thermostat set far above the others, or a loop that is off for good can make one room
   look needy. Fix that, not the curve.
3. **Check the circuit's room setpoint.** If the setpoint hint says lower or raise, do that first: it shifts the
   flow temperature like the curve does, and it is the smaller change.
4. **Change one thing, by one step:** the curve's correction (or parallel shift) by 1 K, or its slope by one
   step. Note the date.
5. **Wait two days** at similar outdoor temperatures. A new curve changes the shares only as fast as the window
   moves on; the floor's own heat store slows it down further.
6. **Repeat** until the verdict says it fits. If the neediest room changes with every step, the curve is close:
   leave it.

An example: a floor-heating circuit, 6 °C outside. The bathroom's loop is open 85 % of the comfort phase, every
other room's 20 to 40 %. The verdict is *Too low*. The bathroom's attributes show its setpoint at 24 °C, the
others at 21 °C: the bathroom asks for more than the curve was made for. Lowering it to 22 °C brings its share
to 55 %, and the verdict to *Fits*, without touching the curve.

## Feedback wanted

This integration was built on one house: underfloor heating with time-proportioned and motorised actuators,
two radiator thermostats, and a pellet boiler that runs four circuits. It should fit many more, and I would like
to hear how it does on yours:

- **Your setup:** the heater, the circuits (floor, radiators, mixed), the thermostats and valves.
- **The verdicts:** do they match what you see in the rooms? Did a change of the curve that it suggested help?
- **The limits:** are 15 % and 70 % right for your loops, and is 24 hours a good window?
- **What is missing:** a room or valve type it does not understand, a hint you would like, a translation.

Open a [discussion](../../discussions) for results and ideas, or an [issue](../../issues/new/choose) for a bug.
Please leave out personal details: rooms named "Room 1" or "bathroom" are enough.

Planned next: aligning the heater's schedule with the thermostats' (any room in comfort → the circuit in
comfort), first in a mode that only shows what it would do. Tell me whether you would use it.

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

Through the Marketplace (Settings → Marketplace → Add from link; [HACS](https://hacs.xyz/) as a custom
repository before Home Assistant 2026.11), or copy `custom_components/heating_circuit_advisor` into your
configuration's `custom_components`.

## License

MIT
