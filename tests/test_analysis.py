"""The analysis on its own: averages, the comfort phase, the verdicts and the setpoint hint."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.heating_circuit_advisor.analysis import (
    Loop,
    Memory,
    Peak,
    Readings,
    Room,
    Settings,
    Thermostat,
    sample,
)

START = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
SETTINGS = Settings()


def room(area_id: str, *values: float | None, target: float = 21.0, current: float = 21.0,
         thermostats: bool = True, active: bool = True) -> Room:
    """A room with one thermostat and a loop per value."""
    loops = tuple(Loop(f"switch.{area_id}_{i}", f"{area_id} {i}", value) for i, value in enumerate(values))
    return Room(area_id, area_id.title(), thermostats,
                (Thermostat(target, current),) if thermostats and active else (), loops)


def run(memory: Memory, *rooms: Room, samples: int = 1, target: float = 21.0, outdoor: float = 5.0,
        settings: Settings = SETTINGS, start: datetime = START):
    """Take samples every 4 minutes, all with the same readings: the last result."""
    readings = Readings(target, outdoor, rooms)
    result = None
    for i in range(samples):
        result = sample(memory, readings, settings, start + timedelta(minutes=4 * i))
    return result


def test_the_first_sample_gives_the_full_share() -> None:
    """The bias correction: one sample open is 100 %, not alpha of it."""
    result = run(Memory(), room("bath", 100))
    assert result.neediest_share == pytest.approx(100)
    assert result.evaluating


def test_the_share_is_the_time_open() -> None:
    """A loop open one sample in four is open a quarter of the time."""
    memory = Memory()
    for i in range(360):
        result = run(memory, room("bath", 100 if i % 4 == 0 else 0), start=START + timedelta(minutes=4 * i))
    assert result.neediest_share == pytest.approx(25, abs=2)
    assert result.mean_share == pytest.approx(result.neediest_share)


def test_nothing_counts_in_the_setback() -> None:
    """Below the comfort setpoint seen, the samples do not count."""
    memory = Memory()
    run(memory, room("bath", 0), target=21.0)
    result = run(memory, room("bath", 100), target=18.0, samples=10, start=START + timedelta(minutes=4))
    assert not result.evaluating
    assert result.neediest_share == pytest.approx(0)
    assert result.circuit_comfort_setpoint == 21.0


def test_a_comfort_setpoint_lowered_is_followed_after_a_day() -> None:
    """A lower setpoint is the comfort phase again once the higher one is stale."""
    memory = Memory()
    run(memory, room("bath", 0), target=22.0)
    result = run(memory, room("bath", 0), target=21.0, start=START + timedelta(hours=27))
    assert result.circuit_comfort_setpoint == 21.0
    assert result.evaluating


def test_nothing_counts_when_it_is_warm_outside() -> None:
    """Above the outdoor limit, or with no outdoor temperature, the samples do not count."""
    assert not run(Memory(), room("bath", 100), outdoor=16.0).evaluating
    assert not run(Memory(), room("bath", 100), outdoor=None).evaluating
    assert not run(Memory(), room("bath", 100), target=None).evaluating


def test_collecting_until_enough_time_is_evaluated() -> None:
    """The verdict waits for the data, then judges."""
    memory = Memory()
    assert run(memory, room("bath", 50), samples=100).verdict == "collecting"
    result = run(memory, room("bath", 50), samples=300, start=START + timedelta(minutes=400))
    assert result.verdict == "ok"
    assert result.collected == 100
    assert result.neediest_room == "Bath"


@pytest.mark.parametrize(
    ("value", "current", "verdict"),
    [
        (80, 21.0, "curve_too_low"),
        (10, 21.0, "curve_too_high"),
        (40, 21.0, "ok"),
        (100, 19.5, "emission_insufficient"),
        (100, 21.0, "curve_too_low"),
    ],
)
def test_the_verdicts(value: float, current: float, verdict: str) -> None:
    """The neediest loop decides; open all the time and still cold, the heat does not get in."""
    memory = Memory(coverage=0.9)
    assert run(memory, room("bath", value, current=current)).verdict == verdict


def test_the_neediest_room_decides() -> None:
    """The room that needs most heat decides, not the average."""
    memory = Memory(coverage=0.9)
    result = run(memory, room("bath", 80), room("living", 10, 10))
    assert result.verdict == "curve_too_low"
    assert result.neediest_room == "Bath"
    assert result.neediest_loop == "bath 0"
    assert result.mean_share == pytest.approx(100 / 3)


def test_a_room_switched_off_does_not_decide() -> None:
    """A room whose thermostats are off is listed, but does not judge the curve."""
    memory = Memory(coverage=0.9)
    result = run(memory, room("bath", 100, active=False), room("living", 40))
    assert result.verdict == "ok"
    assert result.rooms[0].status == "off"
    assert result.rooms[0].share == pytest.approx(100)


def test_a_room_without_a_thermostat_counts() -> None:
    """An open kitchen heated by another room's thermostat still shows its valves."""
    result = run(Memory(coverage=0.9), room("kitchen", 90, thermostats=False))
    assert result.rooms[0].status == "no_thermostat"
    assert result.verdict == "curve_too_low"


def test_no_loops() -> None:
    """Without a labelled valve, or with only rooms switched off, there is nothing to judge."""
    assert run(Memory(), room("bath")).verdict == "no_loops"
    assert run(Memory(coverage=0.9), room("bath", 50, active=False)).verdict == "no_loops"


def test_loops_not_evaluated_yet_are_collecting() -> None:
    """Loops without a share yet: the data is still to come."""
    result = run(Memory(coverage=0.9), room("bath", 50), outdoor=20.0)
    assert result.verdict == "collecting"
    assert result.neediest_share is None


def test_a_loop_without_value_keeps_its_share() -> None:
    """A valve that does not answer is not counted closed."""
    memory = Memory()
    run(memory, room("bath", 100))
    result = run(memory, room("bath", None), start=START + timedelta(minutes=4))
    assert result.neediest_share == pytest.approx(100)
    assert result.rooms[0].loops[0].now is None


def test_a_loop_removed_is_forgotten() -> None:
    """The memory keeps only the loops still there."""
    memory = Memory()
    run(memory, room("bath", 100, 50))
    run(memory, room("bath", 100), start=START + timedelta(minutes=4))
    assert list(memory.loops) == ["switch.bath_0"]


@pytest.mark.parametrize(
    ("circuit", "rooms", "hint", "difference"),
    [
        (23.0, (21.0, 21.0, 20.0), "lower", 2.0),
        (23.0, (21.0, 24.0), "none", None),
        (20.0, (22.0, 22.0, 20.0), "raise", 2.0),
        (20.0, (24.0, 20.0, 20.0), "none", None),
    ],
)
def test_the_setpoint_hint(circuit: float, rooms: tuple[float, ...], hint: str, difference: float | None) -> None:
    """Lower only above every room, raise only below most of them."""
    result = run(Memory(), *(room(f"room{i}", 50, target=t, current=t) for i, t in enumerate(rooms)), target=circuit)
    assert result.setpoint_hint == hint
    assert result.setpoint_difference == difference


def test_a_room_switched_off_has_no_say_in_the_hint() -> None:
    """Only rooms asking for heat compare with the circuit's setpoint."""
    result = run(Memory(), room("bath", 50, target=18.0, active=False), room("living", 50, target=21.0), target=21.0)
    assert result.setpoint_hint == "none"
    assert result.rooms_highest_setpoint == 21.0


def test_the_memory_survives_its_storage() -> None:
    """What is stored reads back the same."""
    memory = Memory()
    run(memory, room("bath", 100), samples=5)
    again = Memory.from_dict(memory.as_dict())
    assert again == memory


@pytest.mark.parametrize(
    "stored",
    [
        None,
        "broken",
        {"coverage": "x", "circuit_comfort": [1], "room_comfort": [], "loops": {"a": "b", "c": [1]}},
        {"room_comfort": {"bath": [21.0, "not a date"]}, "loops": None},
    ],
)
def test_a_broken_memory_starts_over(stored: object) -> None:
    """A store that does not read costs its data, not the circuit."""
    assert Memory.from_dict(stored) == Memory()


def test_a_memory_partly_broken_keeps_the_rest() -> None:
    """Each value reads on its own."""
    memory = Memory.from_dict({"coverage": 0.5, "loops": {"a": [10, 0.1], "b": None}})
    assert memory.coverage == 0.5
    assert memory.loops == {"a": (10.0, 0.1)}
    assert memory.circuit_comfort is None


def test_a_peak_kept() -> None:
    """A lower setpoint within the day keeps the peak."""
    memory = Memory(circuit_comfort=Peak(22.0, START))
    run(memory, room("bath", 0), target=21.0, start=START + timedelta(hours=1))
    assert memory.circuit_comfort == Peak(22.0, START)
