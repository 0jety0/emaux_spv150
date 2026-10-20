import pytest
from homeassistant.config_entries import ConfigEntryState
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


@pytest.mark.asyncio
async def test_setup_skips_pump_when_switch_off(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """A powered-off pump must not block setup: the pump is not contacted at all."""
    hass.states.async_set("switch.pool_power", "off")
    mock_pump_api.get_status.return_value = {}
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.LOADED
    mock_pump_api.get_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_retries_when_switch_on_and_pump_unreachable(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """With the switch ON, an unreachable pump still puts the entry in setup retry."""
    hass.states.async_set("switch.pool_power", "on")
    mock_pump_api.get_status.return_value = {}
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.SETUP_RETRY
