from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_HOST, DOMAIN


class EmauxSpv150ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère un flux de configuration pour Emaux SPV150."""

    VERSION = 1

    def __init__(self):
        """Initialisation du flux de configuration."""
        self._switch_entity = None

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Gère l'étape initiale du flux de configuration."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            self._switch_entity = user_input.get("switch_entity")

            return self.async_create_entry(
                title="SPV150",
                data={
                    CONF_HOST: host,
                    "switch_entity": self._switch_entity,
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Optional("switch_entity"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )
