from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DEFAULT_HOST, DOMAIN, PLATFORMS
from .coordinator import EmauxCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Emaux SPV150 component."""
    _LOGGER.info("Setting up Emaux SPV150 component")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Emaux SPV150 from a config entry."""
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    _LOGGER.info(f"Setting up Emaux SPV150 with host: {host}")

    coordinator = EmauxCoordinator(hass, host)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "host": host,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(f"Setup completed for Emaux SPV150 with entry ID: {entry.entry_id}")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Emaux SPV150 config entry."""
    _LOGGER.info(f"Unloading Emaux SPV150 with entry ID: {entry.entry_id}")
    await hass.config_entries.async_forward_entry_unload(entry, PLATFORMS)

    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        del hass.data[DOMAIN][entry.entry_id]
        _LOGGER.info(f"Unloaded Emaux SPV150 with entry ID: {entry.entry_id}")

    return True
