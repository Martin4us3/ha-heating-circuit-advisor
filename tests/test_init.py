"""A circuit set up: its entities, its samples, its memory across restarts, its removal."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.heating_circuit_advisor.const import DOMAIN, SAMPLE_INTERVAL, SAVE_DELAY
from custom_components.heating_circuit_advisor.diagnostics import async_get_config_entry_diagnostics

from .conftest import House, options


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, domain: str, key: str) -> str:
    """The entity id of a key: the names are the translations'."""
    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}")
    assert found, key
    return found


def state(hass: HomeAssistant, entry: MockConfigEntry, key: str, domain: str = "sensor"):
    return hass.states.get(entity_id(hass, entry, domain, key))


async def test_the_first_sample(hass: HomeAssistant, entry: MockConfigEntry, house: House) -> None:
    """Set up, the circuit has taken a sample: the bathroom's valve is open, the living room's partly."""
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    verdict = state(hass, entry, "verdict")
    assert verdict.state == "collecting"
    assert verdict.attributes["neediest_room"] == "Bath"
    assert verdict.attributes["neediest_loop"] == "Bath valve"
    assert state(hass, entry, "neediest_share").state == "100"
    # (100 + 30 + 0) / 3: the living room's radiator thermostat is a loop, not a thermostat
    assert state(hass, entry, "mean_share").state == "43"
    assert state(hass, entry, "collected").state == "1"
    assert state(hass, entry, "setpoint_hint").state == "none"
    evaluating = state(hass, entry, "evaluating", "binary_sensor")
    assert evaluating.state == "on"
    assert evaluating.attributes["outdoor_temperature"] == 5.0
    assert evaluating.attributes["circuit_comfort_setpoint"] == 21.0

    bath = state(hass, entry, f"room_{house.bath}")
    assert bath.state == "100"
    assert bath.name == "Circuit Room Bath"
    assert bath.attributes["thermostats"] == "on"
    assert bath.attributes["target"] == 22.0
    assert bath.attributes["current"] == 21.0
    assert bath.attributes["loops"] == [{"name": "Bath valve", "now": 100, "share": 100}]
    living = state(hass, entry, f"room_{house.living}")
    assert living.attributes["target"] == 21.0
    assert [loop["now"] for loop in living.attributes["loops"]] == [0, 30]


async def test_the_samples_follow_the_valves(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Closed for as long as it was open, the bathroom's valve is open half of the time."""
    await setup(hass, entry)
    hass.states.async_set("switch.bath_valve", "off", {"friendly_name": "Bath valve"})
    freezer.tick(SAMPLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, entry, "neediest_share").state == "50"


async def test_nothing_counts_in_the_setback(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """The circuit set back, the samples do not count."""
    await setup(hass, entry)
    hass.states.async_set("climate.circuit", "heat", {"temperature": 18.0})
    hass.states.async_set("switch.bath_valve", "off")
    freezer.tick(SAMPLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, entry, "evaluating", "binary_sensor").state == "off"
    assert state(hass, entry, "neediest_share").state == "100"


async def test_the_memory_is_stored(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory, hass_storage: dict
) -> None:
    """A sample is stored a minute later at most."""
    await setup(hass, entry)
    freezer.tick(timedelta(seconds=SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    assert stored["loops"]["switch.bath_valve"][0] > 0
    assert stored["circuit_comfort"][0] == 21.0


async def test_a_restart_keeps_the_memory(
    hass: HomeAssistant, entry: MockConfigEntry, hass_storage: dict
) -> None:
    """The memory stored is where a restart starts: enough data, the verdict is there at once."""
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {"coverage": 0.6, "loops": {"switch.bath_valve": [0.0, 0.6]}},
    }
    await setup(hass, entry)
    # Closed through 0.6 of weight, open for one sample: about 0.5 %, the living room's 30 % leads
    assert state(hass, entry, "verdict").state == "ok"
    assert state(hass, entry, "verdict").attributes["neediest_room"] == "Living"
    assert state(hass, entry, "collected").state == "100"


async def test_the_options_reload_the_rooms(hass: HomeAssistant, entry: MockConfigEntry, house: House) -> None:
    """A room taken out of the circuit loses its sensor."""
    await setup(hass, entry)
    bath = entity_id(hass, entry, "sensor", f"room_{house.bath}")
    hass.config_entries.async_update_entry(entry, options=options(house, areas=[house.living]))
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(bath) is None
    assert er.async_get(hass).async_get(bath) is None
    assert state(hass, entry, "neediest_share").state == "30"


async def test_removing_the_circuit_removes_its_memory(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory, hass_storage: dict
) -> None:
    """Nothing of a circuit removed is left."""
    await setup(hass, entry)
    freezer.tick(timedelta(seconds=SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" in hass_storage
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" not in hass_storage


async def test_unloading(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """A circuit unloads."""
    await setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_the_diagnostics(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """The diagnostics hold the entry, the memory and the analysis."""
    await setup(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["data"] == {"circuit": "climate.circuit"}
    assert diagnostics["options"]["outdoor_temperature"] == "sensor.outdoor"
    assert "switch.bath_valve" in diagnostics["memory"]["loops"]
    assert diagnostics["result"]["neediest_room"] == "Bath"


@pytest.mark.parametrize("circuit", ["unavailable", None])
async def test_a_circuit_without_value(hass: HomeAssistant, entry: MockConfigEntry, circuit: str | None) -> None:
    """A circuit that does not answer, or is gone, is not evaluated."""
    if circuit is None:
        hass.states.async_remove("climate.circuit")
    else:
        hass.states.async_set("climate.circuit", circuit)
    await setup(hass, entry)
    assert state(hass, entry, "evaluating", "binary_sensor").state == "off"
    assert state(hass, entry, "verdict").state == "collecting"
