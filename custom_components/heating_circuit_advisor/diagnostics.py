"""The diagnostics: the entry, the memory and the last analysis."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AdvisorConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: AdvisorConfigEntry) -> dict[str, Any]:
    """The entry's diagnostics: nothing in them is secret."""
    coordinator = entry.runtime_data
    return {
        "data": dict(entry.data),
        "options": dict(entry.options),
        "memory": coordinator.memory.as_dict(),
        "result": asdict(coordinator.data) if coordinator.data else None,
    }
