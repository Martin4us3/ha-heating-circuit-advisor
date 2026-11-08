"""Adding a circuit, changing its climate, and changing its rooms and settings."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heating_circuit_advisor.const import DOMAIN

from .conftest import House, options


def user_input(house: House, **changes: object) -> dict[str, object]:
    return {
        "circuit": "climate.circuit",
        "outdoor_temperature": "sensor.outdoor",
        "areas": [house.bath],
        "loop_label": house.label,
    } | changes


async def test_adding_a_circuit(hass: HomeAssistant, house: House) -> None:
    """The circuit is named after its climate, and starts with the default settings."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(house))
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Circuit"
    assert result["data"] == {"circuit": "climate.circuit"}
    assert result["options"] == options(house, areas=[house.bath])
    assert result["result"].unique_id == "climate.circuit"


async def test_a_circuit_without_state_is_named_by_its_id(hass: HomeAssistant, house: House) -> None:
    """A climate not there yet still makes a circuit."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(house, circuit="climate.elsewhere")
    )
    await hass.async_block_till_done()
    assert result["title"] == "climate.elsewhere"


async def test_a_circuit_needs_a_room(hass: HomeAssistant, house: House) -> None:
    """No room, no circuit: the form asks again, keeping what was entered."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(house, areas=[]))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"areas": "no_areas"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(house))
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_circuit_is_added_once(hass: HomeAssistant, entry: MockConfigEntry, house: House) -> None:
    """The same climate twice is one circuit."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(house))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_the_options(hass: HomeAssistant, entry: MockConfigEntry, house: House) -> None:
    """Rooms and settings change; at least one room stays."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], options(house, areas=[]))
    assert result["errors"] == {"areas": "no_areas"}
    changed = options(house, areas=[house.living], high_share=80.0)
    result = await hass.config_entries.options.async_configure(result["flow_id"], changed)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == changed
    assert entry.runtime_data.settings.high_share == 80.0


async def test_reconfiguring_the_climate(hass: HomeAssistant, entry: MockConfigEntry, house: House) -> None:
    """A renamed climate: the circuit follows it, keeps title, rooms and settings, and is set up again."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set("climate.renamed", "heat", {"temperature": 21.0, "friendly_name": "Renamed"})

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"circuit": "climate.renamed"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {"circuit": "climate.renamed"}
    assert entry.unique_id == "climate.renamed"
    assert entry.title == "Circuit"
    assert entry.options == options(house)
    assert entry.state is ConfigEntryState.LOADED


async def test_reconfiguring_keeps_the_same_climate(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Saving the form unchanged is no conflict with the circuit itself."""
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"circuit": "climate.circuit"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "climate.circuit"


async def test_reconfiguring_to_another_circuits_climate(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """A climate that already is another circuit is not taken over."""
    MockConfigEntry(domain=DOMAIN, unique_id="climate.other", data={"circuit": "climate.other"}).add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"circuit": "climate.other"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {"circuit": "climate.circuit"}
