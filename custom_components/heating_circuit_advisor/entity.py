"""The base of the circuit's entities: one device per circuit."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AdvisorCoordinator


class AdvisorEntity(CoordinatorEntity[AdvisorCoordinator]):
    """An entity of a circuit's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AdvisorCoordinator, key: str) -> None:
        """Set up the entity of a key, unique within its circuit."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
