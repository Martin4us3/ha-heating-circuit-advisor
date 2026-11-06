"""The Heating Circuit Advisor: read-only advice on a heating circuit's curve, from its rooms' valves."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AdvisorConfigEntry, AdvisorCoordinator, store_for

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AdvisorConfigEntry) -> bool:
    """Set up a circuit: its memory loaded, a first sample taken."""
    coordinator = AdvisorCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdvisorConfigEntry) -> bool:
    """Unload a circuit."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: AdvisorConfigEntry) -> None:
    """Remove a circuit's memory with it."""
    await store_for(hass, entry.entry_id).async_remove()


async def _async_options_updated(hass: HomeAssistant, entry: AdvisorConfigEntry) -> None:
    """Reload a circuit whose rooms or settings changed: its rooms' sensors follow."""
    await hass.config_entries.async_reload(entry.entry_id)
