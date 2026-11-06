"""The circuit's verdict, its shares and its rooms."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analysis import SETPOINT_HINTS, VERDICTS, Result, RoomResult
from .coordinator import AdvisorConfigEntry, AdvisorCoordinator
from .entity import AdvisorEntity


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value)


@dataclass(frozen=True, kw_only=True)
class AdvisorSensorDescription(SensorEntityDescription):
    """A circuit sensor: its value and its attributes from the analysis."""

    value: Callable[[Result], Any]
    attributes: Callable[[Result], dict[str, Any]] = lambda _: {}


SENSORS = (
    AdvisorSensorDescription(
        key="verdict",
        translation_key="verdict",
        device_class=SensorDeviceClass.ENUM,
        options=VERDICTS,
        value=lambda r: r.verdict,
        attributes=lambda r: {"neediest_room": r.neediest_room, "neediest_loop": r.neediest_loop},
    ),
    AdvisorSensorDescription(
        key="neediest_share",
        translation_key="neediest_share",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda r: _rounded(r.neediest_share),
        attributes=lambda r: {"room": r.neediest_room, "loop": r.neediest_loop},
    ),
    AdvisorSensorDescription(
        key="mean_share",
        translation_key="mean_share",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda r: _rounded(r.mean_share),
    ),
    AdvisorSensorDescription(
        key="setpoint_hint",
        translation_key="setpoint_hint",
        device_class=SensorDeviceClass.ENUM,
        options=SETPOINT_HINTS,
        value=lambda r: r.setpoint_hint,
        attributes=lambda r: {
            "difference": r.setpoint_difference,
            "circuit_comfort_setpoint": r.circuit_comfort_setpoint,
            "rooms_highest_setpoint": r.rooms_highest_setpoint,
            "rooms_median_setpoint": r.rooms_median_setpoint,
        },
    ),
    AdvisorSensorDescription(
        key="collected",
        translation_key="collected",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: _rounded(r.collected),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AdvisorConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add the circuit's sensors and one per room."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [AdvisorSensor(coordinator, description) for description in SENSORS]
    rooms = [RoomSensor(coordinator, room.area_id, room.name) for room in coordinator.data.rooms]
    # A room taken out of the circuit takes its sensor with it
    registry = er.async_get(hass)
    kept = {room.unique_id for room in rooms}
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registered.unique_id.startswith(f"{entry.entry_id}_room_") and registered.unique_id not in kept:
            registry.async_remove(registered.entity_id)
    async_add_entities(entities + rooms)


class AdvisorSensor(AdvisorEntity, SensorEntity):
    """A value of the circuit's analysis."""

    entity_description: AdvisorSensorDescription

    def __init__(self, coordinator: AdvisorCoordinator, description: AdvisorSensorDescription) -> None:
        """Set up the sensor of a description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """The value."""
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The details."""
        return self.entity_description.attributes(self.coordinator.data)


class RoomSensor(AdvisorEntity, SensorEntity):
    """A room's share: its neediest loop's share of the evaluated time open."""

    _attr_translation_key = "room_share"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # The loops change every sample: the recorder keeps the share, not them
    _unrecorded_attributes = frozenset({"loops"})

    def __init__(self, coordinator: AdvisorCoordinator, area_id: str, area_name: str) -> None:
        """Set up the sensor of a room."""
        super().__init__(coordinator, f"room_{area_id}")
        self._area_id = area_id
        self._attr_translation_placeholders = {"room": area_name}

    @property
    def _room(self) -> RoomResult:
        """The room in the last analysis: the circuit reloads when its rooms change."""
        return next(room for room in self.coordinator.data.rooms if room.area_id == self._area_id)

    @property
    def native_value(self) -> float | None:
        """The share."""
        return _rounded(self._room.share)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The room's thermostats and loops."""
        room = self._room
        return {
            "thermostats": room.status,
            "target": room.target,
            "current": room.current,
            "comfort_setpoint": room.comfort_setpoint,
            "loops": [
                {"name": loop.name, "now": _rounded(loop.now), "share": _rounded(loop.share)} for loop in room.loops
            ],
        }
