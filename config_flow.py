import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_HOST, DOMAIN


class EmauxSpv150ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emaux SPV150."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            return self.async_create_entry(title="SPV150", data={CONF_HOST: host})

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
