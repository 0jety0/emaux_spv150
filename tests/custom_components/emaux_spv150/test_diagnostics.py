"""Diagnostics download, tested through the Home Assistant diagnostics endpoint."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from .conftest import MOCK_HOST


@pytest.fixture
async def diagnostics(hass: HomeAssistant, hass_client, config_entry, mock_pump_api) -> dict:
    assert await async_setup_component(hass, "diagnostics", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return await get_diagnostics_for_config_entry(hass, hass_client, config_entry)


@pytest.mark.asyncio
async def test_diagnostics_show_the_last_status_and_settings(diagnostics):
    """A diagnostics download tells what the pump last reported and how the regulation is set."""
    assert diagnostics["status"]["current_speed"] == 1500.0
    assert diagnostics["status"]["running"] is True
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["control_mode"] == "manual"


@pytest.mark.asyncio
async def test_diagnostics_hide_the_pump_address(diagnostics):
    """The pump IP reveals the LAN layout: it never appears in a diagnostics download."""
    assert MOCK_HOST not in str(diagnostics)
