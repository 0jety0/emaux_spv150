from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import PumpConfigEntry

# The pump address reveals the LAN layout.
TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PumpConfigEntry) -> dict[str, Any]:
    """Return the entry settings, the coordinator state and the last pump status."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "poll_interval_seconds": coordinator.poll_interval,
            "pump_powered_off": coordinator.pump_powered_off,
            "control_mode": coordinator.control_mode,
            "energy_kwh": coordinator.energy_kwh,
        },
        "status": asdict(coordinator.data),
    }
