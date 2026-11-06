"""The coordinator: it samples a circuit's rooms, keeps the memory and stores it."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_OPEN, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .analysis import Loop, Memory, Readings, Result, Room, Settings, Thermostat, sample
from .const import (
    CONF_AREAS,
    CONF_CIRCUIT,
    CONF_HIGH_SHARE,
    CONF_LABEL,
    CONF_LOW_SHARE,
    CONF_OUTDOOR,
    CONF_OUTDOOR_LIMIT,
    CONF_WINDOW_HOURS,
    DEFAULT_HIGH_SHARE,
    DEFAULT_LOW_SHARE,
    DEFAULT_OUTDOOR_LIMIT,
    DEFAULT_WINDOW_HOURS,
    DOMAIN,
    LOGGER,
    SAMPLE_INTERVAL,
    SAVE_DELAY,
    STORAGE_VERSION,
)

type AdvisorConfigEntry = ConfigEntry[AdvisorCoordinator]

_NO_VALUE = (STATE_UNAVAILABLE, STATE_UNKNOWN)
_ON_OFF_DOMAINS = ("switch", "binary_sensor", "input_boolean")


def store_for(hass: HomeAssistant, entry_id: str) -> Store:
    """The store of an entry's memory."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


def _number(value: object) -> float | None:
    """A number, None when it is none."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def loop_opening(state: State | None) -> float | None:
    """A loop's opening in %: a switch on, a valve's position, a level, a thermostat heating."""
    if state is None or state.state in _NO_VALUE:
        return None
    if state.domain in _ON_OFF_DOMAINS:
        return 100.0 if state.state == STATE_ON else 0.0
    if state.domain == "valve":
        position = _number(state.attributes.get("current_position"))
        if position is not None:
            return position
        return 100.0 if state.state == STATE_OPEN else 0.0
    if state.domain == "climate":
        return 100.0 if state.attributes.get("hvac_action") == "heating" else 0.0
    value = _number(state.state)
    return None if value is None else min(max(value, 0.0), 100.0)


class AdvisorCoordinator(DataUpdateCoordinator[Result]):
    """Samples one circuit every few minutes."""

    config_entry: AdvisorConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AdvisorConfigEntry) -> None:
        """Set up the coordinator of an entry, its memory still empty."""
        super().__init__(hass, LOGGER, config_entry=entry, name=entry.title, update_interval=SAMPLE_INTERVAL)
        self._store = store_for(hass, entry.entry_id)
        self.memory = Memory()

    @property
    def settings(self) -> Settings:
        """The entry's settings."""
        options = self.config_entry.options
        return Settings(
            outdoor_limit=float(options.get(CONF_OUTDOOR_LIMIT, DEFAULT_OUTDOOR_LIMIT)),
            window_hours=float(options.get(CONF_WINDOW_HOURS, DEFAULT_WINDOW_HOURS)),
            low_share=float(options.get(CONF_LOW_SHARE, DEFAULT_LOW_SHARE)),
            high_share=float(options.get(CONF_HIGH_SHARE, DEFAULT_HIGH_SHARE)),
            sample_minutes=SAMPLE_INTERVAL.total_seconds() / 60,
        )

    async def _async_setup(self) -> None:
        """Load the memory a restart kept."""
        self.memory = Memory.from_dict(await self._store.async_load())

    async def _async_update_data(self) -> Result:
        """Take a sample."""
        result = sample(self.memory, self.read(), self.settings, dt_util.utcnow())
        self._store.async_delay_save(self.memory.as_dict, SAVE_DELAY)
        return result

    def read(self) -> Readings:
        """Read the circuit, the outdoor temperature and every room."""
        hass = self.hass
        circuit = self.config_entry.data[CONF_CIRCUIT]
        options = self.config_entry.options
        entities = er.async_get(hass)
        devices = dr.async_get(hass)
        areas = ar.async_get(hass)
        labelled = {
            e.entity_id for e in er.async_entries_for_label(entities, options[CONF_LABEL]) if not e.disabled_by
        }

        circuit_state = hass.states.get(circuit)
        circuit_target = None
        if circuit_state is not None and circuit_state.state not in _NO_VALUE:
            circuit_target = _number(circuit_state.attributes.get("temperature"))
        outdoor_state = hass.states.get(options[CONF_OUTDOOR])
        outdoor = _number(outdoor_state.state) if outdoor_state is not None else None

        rooms = []
        for area_id in options[CONF_AREAS]:
            area = areas.async_get_area(area_id)
            members = self._area_entities(entities, devices, area_id)
            thermostats = sorted(
                entity_id for entity_id in members
                if entity_id.startswith("climate.") and entity_id != circuit and entity_id not in labelled
            )
            active = []
            for entity_id in thermostats:
                state = hass.states.get(entity_id)
                if state is None or state.state in (*_NO_VALUE, STATE_OFF):
                    continue
                active.append(Thermostat(_number(state.attributes.get("temperature")),
                                         _number(state.attributes.get("current_temperature"))))
            loops = []
            for entity_id in sorted(members & labelled):
                state = hass.states.get(entity_id)
                loops.append(Loop(entity_id, state.name if state else entity_id, loop_opening(state)))
            rooms.append(Room(area_id, area.name if area else area_id, bool(thermostats), tuple(active), tuple(loops)))
        return Readings(circuit_target, outdoor, tuple(rooms))

    @staticmethod
    def _area_entities(entities: er.EntityRegistry, devices: dr.DeviceRegistry, area_id: str) -> set[str]:
        """An area's entities: its own, and those of its devices that have no area of their own."""
        members = {e.entity_id for e in er.async_entries_for_area(entities, area_id) if not e.disabled_by}
        for device in dr.async_entries_for_area(devices, area_id):
            members.update(e.entity_id for e in er.async_entries_for_device(entities, device.id) if e.area_id is None)
        return members
