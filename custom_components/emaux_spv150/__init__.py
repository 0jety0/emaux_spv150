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
    """Reload only when connection settings change; otherwise apply options live.

    Only host / switch / grid-power entity require a full reload. Regulation
    parameters (setpoint, dead band, steps, RPM, poll interval, mode) are applied
    live on the coordinator — whether they came from a number entity or the
    options flow — so energy, uptime and the regulation state machine are not
    reset on every adjustment. Comparing values (rather than a flag) makes this
    race-free.
    """
    coordinator = entry.runtime_data
    if coordinator.connection_settings_changed(entry):
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        coordinator.apply_options(entry)
