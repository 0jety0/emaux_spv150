import logging
from datetime import timedelta

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.emaux_spv150.api import PumpError
from custom_components.emaux_spv150.coordinator import PumpCoordinator

from .conftest import MOCK_HOST, MOCK_STATUS

STATUS_URL = f"http://{MOCK_HOST}/cgi-bin/EpvCgi?name=AllRd"


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
async def test_setup_reads_the_pump_once(hass: HomeAssistant, config_entry, mock_pump_api):
    """Setup needs a single status read: the slow pump CGI must not be hit several times."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_pump_api.get_status.await_count == 1


@pytest.mark.asyncio
async def test_setup_skips_pump_when_switch_off(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """A powered-off pump must not block setup: the pump is not contacted at all."""
    hass.states.async_set("switch.pool_power", "off")
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
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
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.SETUP_RETRY


async def _next_poll(hass: HomeAssistant, freezer) -> None:
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_pump_outage_is_logged_once_until_it_recovers(
    hass: HomeAssistant, config_entry, aioclient_mock, caplog, freezer
):
    """An unreachable pump logs one error, not one per poll, then one line when it answers again."""
    aioclient_mock.get(STATUS_URL, json=MOCK_STATUS)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS_URL, exc=ClientError("connection refused"))
    for _ in range(3):
        await _next_poll(hass, freezer)

    assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS_URL, json=MOCK_STATUS)
    await _next_poll(hass, freezer)

    assert "recovered" in caplog.text
