from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import PumpConfigEntry, PumpCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: PumpConfigEntry) -> bool:
    """Set up the Emaux SPV150 integration from a config entry."""
    coordinator = PumpCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Emaux SPV150 integration cleanly."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when the user updates options."""
    await hass.config_entries.async_reload(entry.entry_id)
