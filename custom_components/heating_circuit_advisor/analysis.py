"""The analysis of a heating circuit from its rooms' valves: plain Python, without Home Assistant.

Every sample adds each heating loop's opening (0 to 100 %) to its moving average, but only while the circuit is
in its comfort phase and it is cold enough outside: only then does the curve show in the valves. The loop that
needs most heat decides whether the curve fits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median
from typing import Any

# A target this close below the highest one seen is still the comfort phase (setpoints in 0.5 K steps)
COMFORT_TOLERANCE = 0.25
# A comfort setpoint not reached again for a day and some is forgotten: the setpoint was lowered
STALE_AFTER = timedelta(hours=26)
# Until the circuit's target has risen once, or for a day, the highest target seen may be the setback's: set up
# at 22:40 on 2026-11-06, the circuits' night setpoints were taken for their comfort setpoints
SETTLE_AFTER = timedelta(hours=24)
# A loop this open and its room this far below its setpoint: the heat does not get into the room
FULL_OPEN = 95.0
DEFICIT_LIMIT = 0.5
# Of the averaging window's weight: about 0.8 window of evaluated time before a verdict
COVERAGE_NEEDED = 0.55
# K between the circuit's room setpoint and the rooms' before it is worth a hint
SETPOINT_GAP = 1.0

VERDICTS = ["collecting", "no_loops", "ok", "curve_too_low", "curve_too_high", "emission_insufficient"]
SETPOINT_HINTS = ["none", "lower", "raise"]


@dataclass(frozen=True)
class Settings:
    """What the user chose for a circuit."""

    outdoor_limit: float = 15.0
    window_hours: float = 24.0
    low_share: float = 15.0
    high_share: float = 70.0
    sample_minutes: float = 4.0

    @property
    def alpha(self) -> float:
        """The weight of one sample in the moving average."""
        return self.sample_minutes / (self.window_hours * 60)


@dataclass
class Peak:
    """The highest setpoint seen, and when it was last reached."""

    value: float
    seen: datetime


def _track_peak(peak: Peak | None, value: float | None, now: datetime) -> Peak | None:
    """The peak after a setpoint: raised or reached again, or replaced once it is stale."""
    if value is None:
        return peak
    if peak is None or value >= peak.value or peak.seen < now - STALE_AFTER:
        return Peak(value, now)
    return peak


@dataclass
class Memory:
    """What a circuit keeps from sample to sample, and across restarts."""

    coverage: float = 0.0
    # The first sample, and whether the circuit's target has risen since: the comfort phase is known
    since: datetime | None = None
    comfort_known: bool = False
    circuit_comfort: Peak | None = None
    room_comfort: dict[str, Peak] = field(default_factory=dict)
    # Per loop [average, weight]: both start at 0, so that average / weight weighs only the time evaluated,
    # also for a loop added later
    loops: dict[str, tuple[float, float]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """The memory as stored."""

        def peak(p: Peak | None) -> list[Any] | None:
            return [p.value, p.seen.isoformat()] if p else None

        return {
            "coverage": self.coverage,
            "since": self.since.isoformat() if self.since else None,
            "comfort_known": self.comfort_known,
            "circuit_comfort": peak(self.circuit_comfort),
            "room_comfort": {area: peak(p) for area, p in self.room_comfort.items()},
            "loops": {loop: list(values) for loop, values in self.loops.items()},
        }

    @classmethod
    def from_dict(cls, data: Any) -> Memory:
        """The memory stored, leaving out what does not read: a broken entry costs its data, not the circuit."""
        if not isinstance(data, dict):
            return cls()

        def peak(raw: Any) -> Peak | None:
            try:
                return Peak(float(raw[0]), datetime.fromisoformat(raw[1]))
            except (TypeError, ValueError, IndexError, KeyError):
                return None

        def pair(raw: Any) -> tuple[float, float] | None:
            try:
                average, weight = (float(v) for v in raw)
            except (TypeError, ValueError):
                return None
            return average, weight

        try:
            coverage = float(data.get("coverage", 0.0))
        except (TypeError, ValueError):
            coverage = 0.0
        try:
            since = datetime.fromisoformat(data["since"])
        except (TypeError, ValueError, KeyError):
            since = None
        room_raw = data.get("room_comfort")
        loops_raw = data.get("loops")
        room_raw = room_raw if isinstance(room_raw, dict) else {}
        loops_raw = loops_raw if isinstance(loops_raw, dict) else {}
        rooms = {area: p for area, raw in room_raw.items() if (p := peak(raw))}
        loops = {loop: v for loop, raw in loops_raw.items() if (v := pair(raw))}
        return cls(coverage, since, data.get("comfort_known") is True, peak(data.get("circuit_comfort")), rooms, loops)


@dataclass(frozen=True)
class Thermostat:
    """An active thermostat of a room: its target and the temperature it measures."""

    target: float | None
    current: float | None


@dataclass(frozen=True)
class Loop:
    """A heating loop's valve now: its opening in %, None when it does not answer."""

    entity_id: str
    name: str
    value: float | None


@dataclass(frozen=True)
class Room:
    """A room (an area) of the circuit: its active thermostats and its loops."""

    area_id: str
    name: str
    has_thermostats: bool
    thermostats: tuple[Thermostat, ...]
    loops: tuple[Loop, ...]

    @property
    def status(self) -> str:
        """Whether the room's thermostats ask for heat: a room switched off does not judge the curve."""
        if not self.has_thermostats:
            return "no_thermostat"
        return "on" if self.thermostats else "off"


@dataclass(frozen=True)
class Readings:
    """What one sample reads."""

    circuit_target: float | None
    outdoor: float | None
    rooms: tuple[Room, ...]


@dataclass(frozen=True)
class LoopResult:
    """A loop's opening now and its share of the evaluated time."""

    entity_id: str
    name: str
    now: float | None
    share: float | None


@dataclass(frozen=True)
class RoomResult:
    """A room's state and its loops."""

    area_id: str
    name: str
    status: str
    target: float | None
    current: float | None
    comfort_setpoint: float | None
    share: float | None
    loops: tuple[LoopResult, ...]


@dataclass(frozen=True)
class Result:
    """The circuit's analysis after a sample."""

    verdict: str
    evaluating: bool
    comfort_known: bool
    coverage: float
    outdoor: float | None
    circuit_target: float | None
    circuit_comfort_setpoint: float | None
    neediest_room: str | None
    neediest_loop: str | None
    neediest_share: float | None
    mean_share: float | None
    setpoint_hint: str
    setpoint_difference: float | None
    rooms_highest_setpoint: float | None
    rooms_median_setpoint: float | None
    rooms: tuple[RoomResult, ...]

    @property
    def collected(self) -> float:
        """How much of the data a verdict needs is there, in %."""
        return min(100.0, self.coverage / COVERAGE_NEEDED * 100)


def sample(memory: Memory, readings: Readings, settings: Settings, now: datetime) -> Result:
    """Add one sample to the memory and judge the circuit."""
    alpha = settings.alpha

    # The circuit's comfort phase: its target at the highest seen in the last day
    target = readings.circuit_target
    if memory.since is None:
        memory.since = now
    previous = memory.circuit_comfort
    if previous is not None and target is not None and target > previous.value:
        memory.comfort_known = True
    memory.circuit_comfort = _track_peak(previous, target, now)
    comfort = memory.circuit_comfort
    settled = memory.since <= now - SETTLE_AFTER
    known = memory.comfort_known or settled
    in_comfort = target is not None and comfort is not None and target >= comfort.value - COMFORT_TOLERANCE
    evaluating = known and in_comfort and readings.outdoor is not None and readings.outdoor < settings.outdoor_limit
    if evaluating:
        memory.coverage += (1 - memory.coverage) * alpha

    loops: dict[str, tuple[float, float]] = {}
    room_comfort: dict[str, Peak] = {}
    rooms: list[RoomResult] = []
    comforts: list[float] = []
    shares: list[float] = []
    judged = False
    needy: tuple[float, RoomResult, LoopResult, float | None] | None = None

    for room in readings.rooms:
        # The room's setpoint and how far it is below: its neediest thermostat
        targets = [t.target for t in room.thermostats if t.target is not None]
        room_target = max(targets, default=None)
        deficits = [(t.target - t.current, t.current) for t in room.thermostats
                    if t.target is not None and t.current is not None]
        deficit, current = max(deficits, default=(None, None))

        peak = _track_peak(memory.room_comfort.get(room.area_id), room_target, now)
        if peak:
            room_comfort[room.area_id] = peak
            if room.status == "on":
                comforts.append(peak.value)

        loop_results: list[LoopResult] = []
        for loop in sorted(room.loops, key=lambda loop: loop.entity_id):
            average, weight = memory.loops.get(loop.entity_id, (0.0, 0.0))
            if loop.value is not None and evaluating:
                average += (loop.value - average) * alpha
                weight += (1 - weight) * alpha
            share = average / weight if weight > 0 else None
            if weight > 0:
                loops[loop.entity_id] = (average, weight)
            loop_results.append(LoopResult(loop.entity_id, loop.name, loop.value, share))

        room_shares = [r.share for r in loop_results if r.share is not None]
        result = RoomResult(room.area_id, room.name, room.status, room_target, current,
                            peak.value if peak else None, max(room_shares, default=None), tuple(loop_results))
        rooms.append(result)
        if room.status != "off":
            judged = judged or bool(loop_results)
            shares.extend(room_shares)
            for loop_result in loop_results:
                if loop_result.share is not None and (needy is None or loop_result.share > needy[0]):
                    needy = (loop_result.share, result, loop_result, deficit)

    memory.loops = loops
    memory.room_comfort = room_comfort

    # The verdict: the curve has to serve the room that needs most heat
    if not judged:
        verdict = "no_loops"
    elif needy is None or memory.coverage < COVERAGE_NEEDED:
        verdict = "collecting"
    elif needy[0] >= FULL_OPEN and (needy[3] or 0) > DEFICIT_LIMIT:
        verdict = "emission_insufficient"
    elif needy[0] > settings.high_share:
        verdict = "curve_too_low"
    elif needy[0] < settings.low_share:
        verdict = "curve_too_high"
    else:
        verdict = "ok"

    # The circuit's room setpoint against the rooms': the flow follows it as well. Lower it only above every
    # room, raise it only below most of them (their median), so that one room set apart does not decide. The
    # rooms' schedules are their own: only a day of them tells their comfort setpoints
    if not settled:
        comforts = []
    highest = max(comforts, default=None)
    middle = median(comforts) if comforts else None
    hint, difference = "none", None
    if comfort is not None and highest is not None and comfort.value - highest > SETPOINT_GAP:
        hint, difference = "lower", round(comfort.value - highest, 1)
    elif comfort is not None and middle is not None and middle - comfort.value > SETPOINT_GAP:
        hint, difference = "raise", round(middle - comfort.value, 1)

    return Result(
        verdict=verdict,
        evaluating=evaluating,
        comfort_known=known,
        coverage=memory.coverage,
        outdoor=readings.outdoor,
        circuit_target=target,
        circuit_comfort_setpoint=comfort.value if comfort else None,
        neediest_room=needy[1].name if needy else None,
        neediest_loop=needy[2].name if needy else None,
        neediest_share=needy[0] if needy else None,
        mean_share=sum(shares) / len(shares) if shares else None,
        setpoint_hint=hint,
        setpoint_difference=difference,
        rooms_highest_setpoint=highest,
        rooms_median_setpoint=middle,
        rooms=tuple(rooms),
    )
