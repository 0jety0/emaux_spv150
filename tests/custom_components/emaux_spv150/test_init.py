import logging
from datetime import timedelta

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.emaux_spv150.api import PumpError
from custom_components.emaux_spv150.const import DOMAIN
from custom_components.emaux_spv150.coordinator import PumpCoordinator

from .conftest import MOCK_HOST, MOCK_STATUS, MOCK_SWITCH

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
    hass.states.async_set(MOCK_SWITCH, "off")
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.LOADED
    mock_pump_api.get_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_retries_when_switch_on_and_pump_unreachable(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, freezer
):
    """With the switch ON for longer than the pump takes to boot, an unreachable pump puts the entry in setup retry."""
    hass.states.async_set(MOCK_SWITCH, "on")
    freezer.tick(timedelta(minutes=10))
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.SETUP_RETRY


def _error_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


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

    assert len(_error_records(caplog)) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(STATUS_URL, json=MOCK_STATUS)
    await _next_poll(hass, freezer)

    assert "recovered" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("switch_state", ["unknown", "unavailable"])
async def test_setup_loads_when_switch_state_is_unknown_and_pump_silent(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, caplog, switch_state
):
    """Right after a restart the plug's state is not known yet: a silent pump is powered off, not broken."""
    hass.states.async_set(MOCK_SWITCH, switch_state)
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.LOADED
    assert _error_records(caplog) == []


@pytest.mark.asyncio
async def test_setup_loads_when_switch_entity_is_not_created_yet_and_pump_silent(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, caplog
):
    """The plug's integration may start after this one: a missing switch entity counts as unknown."""
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.state is ConfigEntryState.LOADED
    assert _error_records(caplog) == []


async def _setup_with_switch_on_long_ago(hass: HomeAssistant, entry, freezer) -> None:
    hass.states.async_set(MOCK_SWITCH, "on")
    freezer.tick(timedelta(minutes=10))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_silent_pump_is_quiet_when_switch_goes_unavailable(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, caplog, freezer
):
    """Seen in production: an MQTT plug is unavailable after every restart; that cannot prove an outage."""
    await _setup_with_switch_on_long_ago(hass, config_entry_with_switch, freezer)
    reads_before = mock_pump_api.get_status.await_count

    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    hass.states.async_set(MOCK_SWITCH, "unavailable")
    await hass.async_block_till_done()

    assert mock_pump_api.get_status.await_count == reads_before + 1
    assert config_entry_with_switch.runtime_data.last_update_success
    assert _error_records(caplog) == []


@pytest.mark.asyncio
async def test_silent_pump_is_an_outage_once_running_if_switch_entity_disappears(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, caplog, freezer
):
    """A renamed or deleted switch entity explains nothing: a silent pump is reported, once."""
    await _setup_with_switch_on_long_ago(hass, config_entry_with_switch, freezer)

    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    hass.states.async_remove(MOCK_SWITCH)
    await hass.async_block_till_done()
    await _next_poll(hass, freezer)

    assert not config_entry_with_switch.runtime_data.last_update_success
    assert len(_error_records(caplog)) == 1


@pytest.mark.asyncio
async def test_pump_booting_after_switch_on_is_quiet_then_reported_if_it_never_answers(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, caplog, freezer
):
    """The pump joins Wi-Fi about 2 minutes after power-on: silence is expected only during that time."""
    hass.states.async_set(MOCK_SWITCH, "off")
    config_entry_with_switch.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    hass.states.async_set(MOCK_SWITCH, "on")
    await hass.async_block_till_done()
    await _next_poll(hass, freezer)

    assert config_entry_with_switch.runtime_data.last_update_success
    assert _error_records(caplog) == []

    freezer.tick(timedelta(minutes=5))
    await _next_poll(hass, freezer)

    assert not config_entry_with_switch.runtime_data.last_update_success
    assert len(_error_records(caplog)) == 1


@pytest.mark.asyncio
async def test_switch_not_reported_yet_after_setup_keeps_a_silent_pump_quiet(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, caplog
):
    """Seen in production: after a restart the MQTT plug goes unavailable -> unknown, after setup.

    Unknown means no state received yet since the restart: a silent pump is still not an error.
    """
    hass.states.async_set(MOCK_SWITCH, "unavailable")
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry_with_switch.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()
    reads_before = mock_pump_api.get_status.await_count

    hass.states.async_set(MOCK_SWITCH, "unknown")
    await hass.async_block_till_done()

    assert mock_pump_api.get_status.await_count == reads_before + 1
    assert config_entry_with_switch.runtime_data.last_update_success
    assert _error_records(caplog) == []


@pytest.mark.asyncio
async def test_unknown_switch_at_setup_does_not_start_priming_when_it_reports_on(hass: HomeAssistant, mock_pump_api):
    """A pump silent at setup was not proven off: the switch reporting ON later must not pause the solar mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": MOCK_SWITCH, "grid_power_entity": "sensor.grid_power"},
        options={"control_mode": "solar"},
        unique_id=MOCK_HOST,
    )
    hass.states.async_set(MOCK_SWITCH, "unknown")
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_pump_api.get_status.side_effect = None
    hass.states.async_set("sensor.grid_power", "-2000")  # exporting: the solar mode speeds up
    hass.states.async_set(MOCK_SWITCH, "on")
    await hass.async_block_till_done()

    mock_pump_api.set_key.assert_awaited_once()


@pytest.mark.asyncio
async def test_pump_answering_while_switch_state_is_unknown_is_read(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """An unknown plug state does not hide a pump that answers."""
    hass.states.async_set(MOCK_SWITCH, "unknown")
    config_entry_with_switch.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    assert config_entry_with_switch.runtime_data.data.current_speed == 1500.0


@pytest.mark.asyncio
async def test_setup_retries_when_no_switch_is_configured_and_pump_silent(
    hass: HomeAssistant, config_entry, mock_pump_api
):
    """Without a power switch nothing explains a silent pump: setup is retried."""
    mock_pump_api.get_status.side_effect = PumpError("connection refused")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
