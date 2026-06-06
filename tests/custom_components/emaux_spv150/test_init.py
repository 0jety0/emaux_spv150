import pytest
from homeassistant.core import HomeAssistant

from custom_components.emaux_spv150.coordinator import PumpCoordinator


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant, config_entry, mock_pump_api):
    """Setup should store a PumpCoordinator in entry.runtime_data."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert isinstance(config_entry.runtime_data, PumpCoordinator)


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant, config_entry, mock_pump_api):
    """Unloading the entry should return True and remove all forwarded platforms."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # After unload no states from the domain should remain loaded
    assert config_entry.state.name == "NOT_LOADED"
