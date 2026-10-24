import ipaddress
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig, EntityWithDeviceFilterSelectorConfig

from .api import PumpAPI, PumpError
from .const import (
    CONF_DEAD_BAND_LOWER,
    CONF_DEAD_BAND_UPPER,
    CONF_GRID_POWER_ENTITY,
    CONF_PRIMING_TIME,
    CONF_SETPOINT,
    CONF_SPEED_CHANGE_INTERVAL,
    CONF_STEP_DOWN,
    CONF_STEP_UP,
    CONF_SWITCH_ENTITY,
    DEFAULT_DEAD_BAND_LOWER,
    DEFAULT_DEAD_BAND_UPPER,
    DEFAULT_HOST,
    DEFAULT_PRIMING_TIME,
    DEFAULT_SETPOINT,
    DEFAULT_SPEED_CHANGE_INTERVAL,
    DEFAULT_STEP_DOWN,
    DEFAULT_STEP_UP,
    DOMAIN,
)
from .coordinator import is_pump_expected_on

SWITCH_SELECTOR = EntitySelector(
    EntitySelectorConfig(filter=EntityWithDeviceFilterSelectorConfig(domain=Platform.SWITCH))
)
GRID_POWER_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        filter=EntityWithDeviceFilterSelectorConfig(domain=Platform.SENSOR, device_class=SensorDeviceClass.POWER)
    )
)

_HOSTNAME_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")


def is_valid_host(host: str) -> bool:
    """Return True if host is a valid IP address or hostname."""
    host = (host or "").strip()
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(_HOSTNAME_RE.match(host))


async def _pump_unreachable(hass: HomeAssistant, host: str, switch_entity_id: str | None) -> bool:
    """Return True when the pump should answer but does not.

    The check is skipped unless the external power switch is ON: a powered-off
    pump cannot answer, and that must not block saving the configuration.
    """
    if not is_pump_expected_on(hass, switch_entity_id):
        return False
    try:
        await PumpAPI(host, async_get_clientsession(hass)).get_status()
    except PumpError:
        return True
    return False


def _connection_schema(host: str) -> vol.Schema:
    """Fields shared by the user and reconfigure steps."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Optional(CONF_SWITCH_ENTITY): SWITCH_SELECTOR,
            vol.Optional(CONF_GRID_POWER_ENTITY): GRID_POWER_SELECTOR,
        }
    )


def _suggested_entities(switch_entity: str, grid_power_entity: str) -> dict[str, str]:
    """Suggested values for the entity fields, leaving out the empty ones (no entity to preselect)."""
    entities = {CONF_SWITCH_ENTITY: switch_entity, CONF_GRID_POWER_ENTITY: grid_power_entity}
    return {key: value for key, value in entities.items() if value}


class EmauxSpv150ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emaux SPV150."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not is_valid_host(host):
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()

                if await _pump_unreachable(self.hass, host, user_input.get(CONF_SWITCH_ENTITY)):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="SPV150",
                        data={
                            CONF_HOST: host,
                            CONF_SWITCH_ENTITY: user_input.get(CONF_SWITCH_ENTITY) or "",
                            CONF_GRID_POWER_ENTITY: user_input.get(CONF_GRID_POWER_ENTITY) or "",
                        },
                    )

        return self.async_show_form(step_id="user", data_schema=_connection_schema(DEFAULT_HOST), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not is_valid_host(host):
                errors["base"] = "invalid_host"
            else:
                if await _pump_unreachable(self.hass, host, user_input.get(CONF_SWITCH_ENTITY)):
                    errors["base"] = "cannot_connect"
                else:
                    connection = {
                        CONF_HOST: host,
                        CONF_SWITCH_ENTITY: user_input.get(CONF_SWITCH_ENTITY) or "",
                        CONF_GRID_POWER_ENTITY: user_input.get(CONF_GRID_POWER_ENTITY) or "",
                    }
                    # The coordinator reads options first: drop the copies the options flow may
                    # have stored so the reconfigured values win. The update listener reloads.
                    return self.async_update_and_abort(
                        entry,
                        unique_id=host,
                        data_updates=connection,
                        options={k: v for k, v in entry.options.items() if k not in connection},
                    )

        # Show the values actually in use (options win over data, as in the coordinator).
        settings = {**entry.data, **entry.options}
        current_host = settings.get(CONF_HOST) or DEFAULT_HOST
        current_switch = settings.get(CONF_SWITCH_ENTITY) or ""
        current_grid = settings.get(CONF_GRID_POWER_ENTITY) or ""

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _connection_schema(current_host), _suggested_entities(current_switch, current_grid)
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "EmauxSpv150OptionsFlow":
        """Return the options flow handler."""
        return EmauxSpv150OptionsFlow()


class EmauxSpv150OptionsFlow(config_entries.OptionsFlow):
    """Handle options for Emaux SPV150."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options update."""
        errors: dict[str, str] = {}
        opts = self.config_entry.options
        data = self.config_entry.data

        if user_input is not None:
            # A cleared optional entity field is absent from user_input: store it as "none".
            user_input = {
                CONF_SWITCH_ENTITY: "",
                CONF_GRID_POWER_ENTITY: "",
                **user_input,
                CONF_HOST: user_input.get(CONF_HOST, "").strip(),
            }
            if not is_valid_host(user_input.get(CONF_HOST, "")):
                errors["base"] = "invalid_host"

            if user_input.get(CONF_DEAD_BAND_LOWER, 0) > user_input.get(CONF_DEAD_BAND_UPPER, 1):
                errors[CONF_DEAD_BAND_LOWER] = "dead_band_range_invalid"

            if not errors:
                if await _pump_unreachable(self.hass, user_input[CONF_HOST], user_input.get(CONF_SWITCH_ENTITY)):
                    errors["base"] = "cannot_connect"
                else:
                    preserved = {k: v for k, v in self.config_entry.options.items() if k not in user_input}
                    return self.async_create_entry(title="", data={**preserved, **user_input})

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=opts.get(CONF_HOST, data.get(CONF_HOST, DEFAULT_HOST))): str,
                # Suggested (not default) values: a default would come back when the field is cleared.
                vol.Optional(CONF_SWITCH_ENTITY): SWITCH_SELECTOR,
                vol.Optional(CONF_GRID_POWER_ENTITY): GRID_POWER_SELECTOR,
                vol.Optional(CONF_SETPOINT, default=opts.get(CONF_SETPOINT, DEFAULT_SETPOINT)): vol.Coerce(float),
                vol.Optional(
                    CONF_DEAD_BAND_LOWER, default=opts.get(CONF_DEAD_BAND_LOWER, DEFAULT_DEAD_BAND_LOWER)
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_DEAD_BAND_UPPER, default=opts.get(CONF_DEAD_BAND_UPPER, DEFAULT_DEAD_BAND_UPPER)
                ): vol.Coerce(float),
                vol.Optional(CONF_STEP_UP, default=opts.get(CONF_STEP_UP, DEFAULT_STEP_UP)): vol.Coerce(int),
                vol.Optional(CONF_STEP_DOWN, default=opts.get(CONF_STEP_DOWN, DEFAULT_STEP_DOWN)): vol.Coerce(int),
                vol.Optional(CONF_PRIMING_TIME, default=opts.get(CONF_PRIMING_TIME, DEFAULT_PRIMING_TIME)): vol.All(
                    vol.Coerce(int), vol.Range(min=60, max=1200)
                ),
                vol.Optional(
                    CONF_SPEED_CHANGE_INTERVAL,
                    default=opts.get(CONF_SPEED_CHANGE_INTERVAL, DEFAULT_SPEED_CHANGE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
            }
        )
        current = _suggested_entities(
            opts.get(CONF_SWITCH_ENTITY, data.get(CONF_SWITCH_ENTITY)) or "",
            opts.get(CONF_GRID_POWER_ENTITY, data.get(CONF_GRID_POWER_ENTITY)) or "",
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current),
            errors=errors,
        )
