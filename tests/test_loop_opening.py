"""A loop's opening, whatever kind of entity its valve is."""

from __future__ import annotations

import pytest
from homeassistant.core import State

from custom_components.heating_circuit_advisor.coordinator import loop_opening


@pytest.mark.parametrize(
    ("entity_id", "value", "attributes", "opening"),
    [
        ("switch.valve", "on", {}, 100),
        ("switch.valve", "off", {}, 0),
        ("binary_sensor.valve", "on", {}, 100),
        ("input_boolean.valve", "off", {}, 0),
        ("valve.loop", "open", {"current_position": 40}, 40),
        ("valve.loop", "open", {}, 100),
        ("valve.loop", "closed", {}, 0),
        ("climate.radiator", "heat", {"hvac_action": "heating"}, 100),
        ("climate.radiator", "heat", {"hvac_action": "idle"}, 0),
        ("number.level", "55.5", {}, 55.5),
        ("sensor.level", "120", {}, 100),
        ("sensor.level", "-3", {}, 0),
        ("sensor.level", "open", {}, None),
        ("sensor.level", "unavailable", {}, None),
        ("switch.valve", "unknown", {}, None),
    ],
)
def test_the_opening(entity_id: str, value: str, attributes: dict, opening: float | None) -> None:
    """A switch on, a valve's position, a level in %, a thermostat heating."""
    assert loop_opening(State(entity_id, value, attributes)) == opening


def test_a_loop_gone() -> None:
    """A valve without state has no opening."""
    assert loop_opening(None) is None
