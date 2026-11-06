"""Whether a circuit is being evaluated now."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AdvisorConfigEntry, AdvisorCoordinator
from .entity import AdvisorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AdvisorConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add the circuit's binary sensor."""
    async_add_entities([EvaluatingSensor(entry.runtime_data)])


class EvaluatingSensor(AdvisorEntity, BinarySensorEntity):
    """On while the samples count: the circuit in its comfort phase and cold enough outside."""

    _attr_translation_key = "evaluating"

    def __init__(self, coordinator: AdvisorCoordinator) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, "evaluating")

    @property
    def is_on(self) -> bool:
        """Whether the last sample counted."""
        return self.coordinator.data.evaluating

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Why it counts or not."""
        data = self.coordinator.data
        return {
            "outdoor_temperature": data.outdoor,
            "circuit_setpoint": data.circuit_target,
            "circuit_comfort_setpoint": data.circuit_comfort_setpoint,
            "comfort_known": data.comfort_known,
        }
