from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PumpAPI
from .const import (
    CONF_DEAD_BAND_LOWER,
    CONF_DEAD_BAND_UPPER,
    CONF_GRID_POWER_ENTITY,
    CONF_POLL_INTERVAL,
    CONF_PRIMING_TIME,
    CONF_SETPOINT,
    CONF_SPEED_CHANGE_INTERVAL,
    CONF_STEP_DOWN,
    CONF_STEP_UP,
    CONF_SWITCH_ENTITY,
    DEFAULT_DEAD_BAND_LOWER,
    DEFAULT_DEAD_BAND_UPPER,
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PRIMING_TIME,
    DEFAULT_SETPOINT,
    DEFAULT_SPEED_CHANGE_INTERVAL,
    DEFAULT_STEP_DOWN,
    DEFAULT_STEP_UP,
    DOMAIN,
)


class EmauxSpv150ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emaux SPV150."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            status = await PumpAPI(host, async_get_clientsession(self.hass)).get_status()
            if not status:
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

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Optional(CONF_SWITCH_ENTITY): str,
                    vol.Optional(CONF_GRID_POWER_ENTITY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            status = await PumpAPI(host, async_get_clientsession(self.hass)).get_status()
            if not status:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_SWITCH_ENTITY: user_input.get(CONF_SWITCH_ENTITY) or "",
                        CONF_GRID_POWER_ENTITY: user_input.get(CONF_GRID_POWER_ENTITY) or "",
                    },
                )

        current_host = (entry.data or {}).get(CONF_HOST, DEFAULT_HOST)
        current_switch = (entry.data or {}).get(CONF_SWITCH_ENTITY) or ""
        current_grid = (entry.data or {}).get(CONF_GRID_POWER_ENTITY, "")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                    vol.Optional(CONF_SWITCH_ENTITY, default=current_switch): str,
                    vol.Optional(CONF_GRID_POWER_ENTITY, default=current_grid): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "EmauxSpv150OptionsFlow":
        """Return the options flow handler."""
        return EmauxSpv150OptionsFlow()


class EmauxSpv150OptionsFlow(config_entries.OptionsFlow):
    """Handle options for Emaux SPV150."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options update."""
        errors: dict[str, str] = {}
        opts = self.config_entry.options
        data = self.config_entry.data

        if user_input is not None:
            if user_input.get(CONF_DEAD_BAND_LOWER, 0) > user_input.get(CONF_DEAD_BAND_UPPER, 1):
                errors[CONF_DEAD_BAND_LOWER] = "dead_band_range_invalid"

            if not errors:
                host = user_input[CONF_HOST]
                status = await PumpAPI(host, async_get_clientsession(self.hass)).get_status()
                if not status:
                    errors["base"] = "cannot_connect"
                else:
                    preserved = {k: v for k, v in self.config_entry.options.items() if k not in user_input}
                    return self.async_create_entry(title="", data={**preserved, **user_input})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=opts.get(CONF_HOST, data.get(CONF_HOST, DEFAULT_HOST))): str,
                    vol.Optional(CONF_SWITCH_ENTITY, default=opts.get(CONF_SWITCH_ENTITY, data.get(CONF_SWITCH_ENTITY, ""))): str,
                    vol.Optional(CONF_POLL_INTERVAL, default=opts.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): vol.In([5, 15, 30, 60]),
                    vol.Optional(CONF_GRID_POWER_ENTITY, default=opts.get(CONF_GRID_POWER_ENTITY, "")): str,
                    vol.Optional(CONF_SETPOINT, default=opts.get(CONF_SETPOINT, DEFAULT_SETPOINT)): vol.Coerce(float),
                    vol.Optional(CONF_DEAD_BAND_LOWER, default=opts.get(CONF_DEAD_BAND_LOWER, DEFAULT_DEAD_BAND_LOWER)): vol.Coerce(float),
                    vol.Optional(CONF_DEAD_BAND_UPPER, default=opts.get(CONF_DEAD_BAND_UPPER, DEFAULT_DEAD_BAND_UPPER)): vol.Coerce(float),
                    vol.Optional(CONF_STEP_UP, default=opts.get(CONF_STEP_UP, DEFAULT_STEP_UP)): vol.Coerce(int),
                    vol.Optional(CONF_STEP_DOWN, default=opts.get(CONF_STEP_DOWN, DEFAULT_STEP_DOWN)): vol.Coerce(int),
                    vol.Optional(CONF_PRIMING_TIME, default=opts.get(CONF_PRIMING_TIME, DEFAULT_PRIMING_TIME)): vol.All(vol.Coerce(int), vol.Range(min=60, max=1200)),
                    vol.Optional(CONF_SPEED_CHANGE_INTERVAL, default=opts.get(CONF_SPEED_CHANGE_INTERVAL, DEFAULT_SPEED_CHANGE_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
                }
            ),
            errors=errors,
        )
