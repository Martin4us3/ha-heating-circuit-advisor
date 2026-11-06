"""Shared fixtures: a house with a circuit, a bathroom and a living room, and an entry for the circuit."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heating_circuit_advisor.const import (
    CONF_AREAS,
    CONF_CIRCUIT,
    CONF_HIGH_SHARE,
    CONF_LABEL,
    CONF_LOW_SHARE,
    CONF_OUTDOOR,
    CONF_OUTDOOR_LIMIT,
    CONF_WINDOW_HOURS,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """The integration lives in custom_components/: Home Assistant loads it only with this fixture."""


@dataclass
class House:
    """The ids of the house's areas and label."""

    bath: str
    living: str
    label: str


@pytest.fixture
def house(hass: HomeAssistant) -> House:
    """A circuit and two rooms.

    The bathroom's thermostat is a device in the area; its valve, a switch, has the area itself. The living room
    has two thermostats, one of them off, and a valve in %. A radiator thermostat in the living room carries the
    label too: it is a loop, not a thermostat.
    """
    areas = ar.async_get(hass)
    labels = lr.async_get(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    bath = areas.async_create("Bath").id
    living = areas.async_create("Living").id
    label = labels.async_create("Heating loop").label_id

    other = MockConfigEntry(domain="test")
    other.add_to_hass(hass)
    device = devices.async_get_or_create(config_entry_id=other.entry_id, identifiers={("test", "bath_thermostat")})
    devices.async_update_device(device.id, area_id=bath)

    def register(domain: str, object_id: str, *, area: str | None = None, labelled: bool = False,
                 device_id: str | None = None) -> None:
        entry = entities.async_get_or_create(domain, "test", object_id, suggested_object_id=object_id,
                                             device_id=device_id, config_entry=other)
        entities.async_update_entity(entry.entity_id, area_id=area, labels={label} if labelled else set())

    register("climate", "bath_thermostat", device_id=device.id)
    register("switch", "bath_valve", area=bath, labelled=True)
    register("climate", "living_thermostat", area=living)
    register("climate", "living_thermostat_off", area=living)
    register("number", "living_valve", area=living, labelled=True)
    register("climate", "living_radiator", area=living, labelled=True)
    # The circuit's own climate in a room is no thermostat of it
    register("climate", "circuit", area=living)

    hass.states.async_set("climate.circuit", "heat", {"temperature": 21.0, "friendly_name": "Circuit"})
    hass.states.async_set("sensor.outdoor", "5.0")
    hass.states.async_set("climate.bath_thermostat", "auto", {"temperature": 22.0, "current_temperature": 21.0})
    hass.states.async_set("switch.bath_valve", "on", {"friendly_name": "Bath valve"})
    hass.states.async_set("climate.living_thermostat", "heat", {"temperature": 21.0, "current_temperature": 21.0})
    hass.states.async_set("climate.living_thermostat_off", "off", {"temperature": 25.0})
    hass.states.async_set("number.living_valve", "30")
    hass.states.async_set("climate.living_radiator", "heat", {"hvac_action": "idle"})
    return House(bath, living, label)


def options(house: House, **changes: object) -> dict[str, object]:
    """The entry's options for the house."""
    return {
        CONF_OUTDOOR: "sensor.outdoor",
        CONF_AREAS: [house.bath, house.living],
        CONF_LABEL: house.label,
        CONF_OUTDOOR_LIMIT: 15.0,
        CONF_WINDOW_HOURS: 24.0,
        CONF_LOW_SHARE: 15.0,
        CONF_HIGH_SHARE: 70.0,
    } | changes


# A circuit observed for a day: its comfort phase is known, its first sample counts
A_DAY_AGO = "2026-01-01T00:00:00+00:00"


def stored(entry: MockConfigEntry, **memory: object) -> dict[str, object]:
    """The store of an entry's memory."""
    key = f"{DOMAIN}.{entry.entry_id}"
    return {"version": 1, "key": key, "data": {"since": A_DAY_AGO} | memory}


@pytest.fixture
def entry(hass: HomeAssistant, house: House, hass_storage: dict) -> MockConfigEntry:
    """The circuit's entry, not set up yet, observed for a day."""
    entry = MockConfigEntry(domain=DOMAIN, title="Circuit", unique_id="climate.circuit",
                            data={CONF_CIRCUIT: "climate.circuit"}, options=options(house))
    entry.add_to_hass(hass)
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = stored(entry)
    return entry
