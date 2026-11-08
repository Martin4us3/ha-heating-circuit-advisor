"""Adding a circuit, changing its climate, and changing its rooms and settings."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

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
)

_DEFAULT_SETTINGS = {
    CONF_OUTDOOR_LIMIT: DEFAULT_OUTDOOR_LIMIT,
    CONF_WINDOW_HOURS: DEFAULT_WINDOW_HOURS,
    CONF_LOW_SHARE: DEFAULT_LOW_SHARE,
    CONF_HIGH_SHARE: DEFAULT_HIGH_SHARE,
}


def _number(minimum: float, maximum: float, step: float, unit: str) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement=unit, mode=selector.NumberSelectorMode.BOX
        )
    )


_CIRCUIT_SCHEMA = vol.Schema(
    {vol.Required(CONF_CIRCUIT): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate"))}
)

_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OUTDOOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.TEMPERATURE)
        ),
        vol.Required(CONF_AREAS): selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
        vol.Required(CONF_LABEL): selector.LabelSelector(),
    }
)

_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OUTDOOR_LIMIT): _number(0, 20, 0.5, "°C"),
        vol.Required(CONF_WINDOW_HOURS): _number(6, 168, 1, "h"),
        vol.Required(CONF_LOW_SHARE): _number(0, 50, 1, "%"),
        vol.Required(CONF_HIGH_SHARE): _number(50, 100, 1, "%"),
    }
)


class AdvisorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a circuit: its climate, the outdoor temperature, its rooms and the loops' label."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The only step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            circuit = user_input.pop(CONF_CIRCUIT)
            await self.async_set_unique_id(circuit)
            self._abort_if_unique_id_configured()
            if not user_input[CONF_AREAS]:
                errors[CONF_AREAS] = "no_areas"
            else:
                state = self.hass.states.get(circuit)
                return self.async_create_entry(
                    title=state.name if state else circuit,
                    data={CONF_CIRCUIT: circuit},
                    options={**user_input, **_DEFAULT_SETTINGS},
                )
            user_input[CONF_CIRCUIT] = circuit

        schema = _CIRCUIT_SCHEMA.extend(_ROOMS_SCHEMA.schema)
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input), errors=errors
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Another climate for the circuit, e.g. after its entity ID was renamed.

        Title, rooms, settings and what the circuit has learned stay.
        """
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            circuit = user_input[CONF_CIRCUIT]
            if circuit != entry.unique_id:
                await self.async_set_unique_id(circuit)
                self._abort_if_unique_id_configured()
            return self.async_update_reload_and_abort(entry, unique_id=circuit, data_updates={CONF_CIRCUIT: circuit})
        return self.async_show_form(
            step_id="reconfigure", data_schema=self.add_suggested_values_to_schema(_CIRCUIT_SCHEMA, entry.data)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AdvisorOptionsFlow:
        """The options: rooms and settings."""
        return AdvisorOptionsFlow()


class AdvisorOptionsFlow(OptionsFlow):
    """Change a circuit's rooms, label, outdoor temperature and settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The only step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_AREAS]:
                return self.async_create_entry(data=user_input)
            errors[CONF_AREAS] = "no_areas"
        schema = _ROOMS_SCHEMA.extend(_SETTINGS_SCHEMA.schema)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or self.config_entry.options),
            errors=errors,
        )
