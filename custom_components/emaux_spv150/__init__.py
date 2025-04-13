import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import PumpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialisation de l'intégration Emaux SPV150 via une config entry."""
    host = entry.data["host"]
    switch_entity = entry.data["switch_entity"]
    _LOGGER.info(f"switch_entity entry ID: {switch_entity}")
    coordinator = PumpCoordinator(hass, host, timedelta(seconds=5), switch_entity)
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Déchargement propre de l'intégration."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info(f"Emaux SPV150 unloaded for entry ID: {entry.entry_id}")
    return unloaded


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Appelé quand l'utilisateur met à jour les options."""
    await hass.config_entries.async_reload(entry.entry_id)
