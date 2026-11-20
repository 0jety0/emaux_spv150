import ipaddress
import re
from typing import Any, override

import probatio
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
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
    DEFAULT_HOST,
    DOMAIN,
    OPTION_DEFAULTS,
    POWER_SETTING_MAX,
    POWER_SETTING_MIN,
    STEP_DOWN_MAX,
    STEP_DOWN_MIN,
    STEP_UP_MAX,
    STEP_UP_MIN,
)
from .coordinator import connection_settings, is_switch_off

SWITCH_SELECTOR = EntitySelector(
    EntitySelectorConfig(filter=EntityWithDeviceFilterSelectorConfig(domain=Platform.SWITCH))
)
GRID_POWER_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        filter=EntityWithDeviceFilterSelectorConfig(domain=Platform.SENSOR, device_class=SensorDeviceClass.POWER)
    )
)

POWER_SETTING = probatio.All(probatio.Coerce(float), probatio.Range(min=POWER_SETTING_MIN, max=POWER_SETTING_MAX))

_HOSTNAME_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")


def is_valid_host(host: str) -> bool:
    """Return True if host is a valid IP address or hostname."""
    host = host.strip()
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(_HOSTNAME_RE.match(host))


async def _pump_unreachable(hass: HomeAssistant, host: str, switch_entity_id: str | None) -> bool:
    """Return True when the pump should answer but does not.

    The check is skipped while the external power switch is OFF: a powered-off
    pump cannot answer, and that must not block saving the configuration.
    """
    if is_switch_off(hass, switch_entity_id):
        return False
    try:
        await PumpAPI(host, async_get_clientsession(hass)).get_status()
    except PumpError:
        return True
    return False


def _connection_schema(host: str) -> probatio.Schema:
    """Fields shared by the user and reconfigure steps."""
    return probatio.Schema(
        {
            probatio.Required(CONF_HOST, default=host): str,
            probatio.Optional(CONF_SWITCH_ENTITY): SWITCH_SELECTOR,
            probatio.Optional(CONF_GRID_POWER_ENTITY): GRID_POWER_SELECTOR,
        }
    )


def _suggested_entities(switch_entity: str | None, grid_power_entity: str | None) -> dict[str, str]:
    """Suggested values for the entity fields, leaving out the empty ones (no entity to preselect)."""
    entities = {CONF_SWITCH_ENTITY: switch_entity, CONF_GRID_POWER_ENTITY: grid_power_entity}
    return {key: value for key, value in entities.items() if value}


class EmauxSpv150ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emaux SPV150."""

    VERSION = 1

    @override
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
                if host != entry.unique_id:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()

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

        # Show the values actually in use.
        settings = connection_settings(entry)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _connection_schema(settings.host),
                _suggested_entities(settings.switch_entity_id, settings.grid_power_entity),
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> EmauxSpv150OptionsFlow:
        """Return the options flow handler."""
        return EmauxSpv150OptionsFlow()


class EmauxSpv150OptionsFlow(config_entries.OptionsFlow):
    """Handle options for Emaux SPV150."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options update."""
        errors: dict[str, str] = {}
        values = {**OPTION_DEFAULTS, **self.config_entry.options}
        settings = connection_settings(self.config_entry)

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
                # Only a new host needs checking: a booting or unplugged pump must not block saving a setting.
                host_changed = user_input[CONF_HOST] != settings.host
                if host_changed and await _pump_unreachable(
                    self.hass, user_input[CONF_HOST], user_input.get(CONF_SWITCH_ENTITY)
                ):
                    errors["base"] = "cannot_connect"
                else:
                    preserved = {k: v for k, v in self.config_entry.options.items() if k not in user_input}
                    return self.async_create_entry(title="", data={**preserved, **user_input})

        schema = probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=settings.host): str,
                # Suggested (not default) values: a default would come back when the field is cleared.
                probatio.Optional(CONF_SWITCH_ENTITY): SWITCH_SELECTOR,
                probatio.Optional(CONF_GRID_POWER_ENTITY): GRID_POWER_SELECTOR,
                probatio.Optional(CONF_SETPOINT, default=values[CONF_SETPOINT]): POWER_SETTING,
                probatio.Optional(CONF_DEAD_BAND_LOWER, default=values[CONF_DEAD_BAND_LOWER]): POWER_SETTING,
                probatio.Optional(CONF_DEAD_BAND_UPPER, default=values[CONF_DEAD_BAND_UPPER]): POWER_SETTING,
                probatio.Optional(CONF_STEP_UP, default=values[CONF_STEP_UP]): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=STEP_UP_MIN, max=STEP_UP_MAX)
                ),
                probatio.Optional(CONF_STEP_DOWN, default=values[CONF_STEP_DOWN]): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=STEP_DOWN_MIN, max=STEP_DOWN_MAX)
                ),
                probatio.Optional(CONF_PRIMING_TIME, default=values[CONF_PRIMING_TIME]): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=60, max=1200)
                ),
                probatio.Optional(
                    CONF_SPEED_CHANGE_INTERVAL,
                    default=values[CONF_SPEED_CHANGE_INTERVAL],
                ): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=300)),
            }
        )
        suggested = _suggested_entities(settings.switch_entity_id, settings.grid_power_entity)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )
