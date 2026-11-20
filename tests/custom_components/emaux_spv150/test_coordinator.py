"""Polling, energy, uptime, commands and solar regulation, tested through Home Assistant."""

import asyncio
import logging
from datetime import timedelta
from unittest.mock import call

import pytest
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.emaux_spv150.api import PumpError
from custom_components.emaux_spv150.const import DOMAIN
from custom_components.emaux_spv150.coordinator import SpeedChangeThrottled

from .conftest import MOCK_GRID, MOCK_HOST, MOCK_STATUS, MOCK_SWITCH, entity_id, poll_after, setup_integration, state

POLL = timedelta(seconds=30)
UNREACHABLE = PumpError("connection refused")


async def _call(hass: HomeAssistant, platform: str, service: str, key: str, **data: float) -> None:
    await hass.services.async_call(
        platform, service, {"entity_id": entity_id(hass, platform, key), **data}, blocking=True
    )


async def _poll_with_fresh_grid(hass: HomeAssistant, freezer, delay: timedelta) -> None:
    """Let time pass while the grid sensor keeps reporting an export, then run the poll that is due."""
    freezer.tick(delay)
    hass.states.async_set(MOCK_GRID, "-2000")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _grid_logs(caplog, level: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == level and "Grid power entity" in r.getMessage()]


# --- Reading the pump ---


@pytest.mark.asyncio
async def test_pump_status_is_shown(hass: HomeAssistant, init_integration):
    """Each value read from the pump is shown by its entity."""
    assert float(state(hass, "sensor", "current_watts")) == 300
    assert float(state(hass, "number", "current_speed")) == 1500
    assert float(state(hass, "number", "speed_selected")) == 2
    assert state(hass, "switch", "running_status") == STATE_ON


@pytest.mark.asyncio
async def test_running_status_given_as_a_number_is_read(hass: HomeAssistant, config_entry, mock_pump_api):
    """Some firmwares answer RunningStatus as a number instead of a string."""
    mock_pump_api.get_status.return_value = {**MOCK_STATUS, "RunningStatus": 1}

    await setup_integration(hass, config_entry)

    assert state(hass, "switch", "running_status") == STATE_ON


@pytest.mark.asyncio
async def test_failed_poll_makes_the_pump_unavailable_with_the_reason(
    hass: HomeAssistant, init_integration, mock_pump_api, freezer, caplog
):
    """A pump that cannot be read makes its values unavailable and the log says why."""
    mock_pump_api.get_status.side_effect = UNREACHABLE

    await poll_after(hass, freezer, POLL)

    assert state(hass, "number", "current_speed") == STATE_UNAVAILABLE
    assert "Could not read the pump status: connection refused" in caplog.text


# --- Commands ---


@pytest.mark.asyncio
async def test_run_stop_commands_are_not_throttled(hass: HomeAssistant, init_integration, mock_pump_api):
    """Only speed changes have a minimum interval: starting then stopping the pump at once both reach it."""
    await _call(hass, "switch", "turn_on", "running_status")
    await _call(hass, "switch", "turn_off", "running_status")

    assert mock_pump_api.set_key.await_args_list == [call("RunStop", 1), call("RunStop", 2)]


@pytest.mark.asyncio
async def test_failed_speed_change_does_not_block_the_retry(hass: HomeAssistant, init_integration, mock_pump_api):
    """A speed change the pump did not take must not start the minimum interval."""
    mock_pump_api.set_key.side_effect = [UNREACHABLE, "1800"]
    with pytest.raises(HomeAssistantError):
        await _call(hass, "number", "set_value", "current_speed", value=1800)

    await _call(hass, "number", "set_value", "current_speed", value=1800)

    assert mock_pump_api.set_key.await_args_list == [call("SetCurrentSpeed", 1800), call("SetCurrentSpeed", 1800)]


@pytest.mark.asyncio
async def test_concurrent_speed_changes_reach_the_pump_once(hass: HomeAssistant, init_integration, mock_pump_api):
    """A manual speed change sent while the regulator's command is in flight is throttled, not sent too."""

    async def slow_set_key(key: str, value: int) -> str:
        await asyncio.sleep(0)
        return str(value)

    mock_pump_api.set_key.side_effect = slow_set_key
    coordinator = init_integration.runtime_data

    results = await asyncio.gather(
        coordinator.async_set_pump_key("SetCurrentSpeed", 1800),
        coordinator.async_set_pump_key("SetCurrentSpeed", 2000),
        return_exceptions=True,
    )

    assert results[0] == "1800"
    assert isinstance(results[1], SpeedChangeThrottled)
    mock_pump_api.set_key.assert_awaited_once_with("SetCurrentSpeed", 1800)


# --- Energy and uptime ---


@pytest.mark.asyncio
async def test_energy_is_integrated_from_the_pump_power(hass: HomeAssistant, config_entry, mock_pump_api, freezer):
    """1000 W for one hour adds 1 kWh."""
    mock_pump_api.get_status.return_value = {**MOCK_STATUS, "CurrentWatts": "1000"}
    await setup_integration(hass, config_entry)

    await poll_after(hass, freezer, timedelta(hours=1))

    assert float(state(hass, "sensor", "energy_kwh")) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_energy_is_not_counted_while_the_pump_is_stopped(
    hass: HomeAssistant, config_entry, mock_pump_api, freezer
):
    """A stopped pump (RunningStatus 0) uses no energy, whatever power value it still reports."""
    mock_pump_api.get_status.return_value = {**MOCK_STATUS, "RunningStatus": "0", "CurrentWatts": "1000"}
    await setup_integration(hass, config_entry)

    await poll_after(hass, freezer, timedelta(hours=1))

    assert float(state(hass, "sensor", "energy_kwh")) == 0


@pytest.mark.asyncio
async def test_energy_is_not_counted_while_the_switch_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api, freezer
):
    """Hours spent with the power switch OFF must not be billed at the next running poll."""
    mock_pump_api.get_status.return_value = {**MOCK_STATUS, "CurrentWatts": "1000"}
    hass.states.async_set(MOCK_SWITCH, "on")
    await setup_integration(hass, config_entry_with_switch)
    hass.states.async_set(MOCK_SWITCH, "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(hours=12))

    hass.states.async_set(MOCK_SWITCH, "on")
    await hass.async_block_till_done()

    assert float(state(hass, "sensor", "energy_kwh")) == 0


@pytest.mark.asyncio
async def test_energy_is_not_counted_across_an_outage(hass: HomeAssistant, config_entry, mock_pump_api, freezer):
    """A pump outage must not be billed at full power once it answers again."""
    mock_pump_api.get_status.return_value = {**MOCK_STATUS, "CurrentWatts": "1000"}
    await setup_integration(hass, config_entry)
    mock_pump_api.get_status.side_effect = UNREACHABLE
    await poll_after(hass, freezer, POLL)

    mock_pump_api.get_status.side_effect = None
    await poll_after(hass, freezer, timedelta(hours=12))

    assert float(state(hass, "sensor", "energy_kwh")) == 0


@pytest.mark.asyncio
async def test_uptime_counts_while_running_and_clears_when_stopped(
    hass: HomeAssistant, init_integration, mock_pump_api, freezer
):
    """Uptime counts the hours since the pump started and is unknown once it stops."""
    await poll_after(hass, freezer, timedelta(hours=2))

    assert float(state(hass, "sensor", "uptime_hours")) == 2

    mock_pump_api.get_status.return_value = {**MOCK_STATUS, "RunningStatus": "0"}
    await poll_after(hass, freezer, POLL)

    assert state(hass, "sensor", "uptime_hours") == STATE_UNKNOWN


@pytest.mark.asyncio
async def test_uptime_restarts_after_an_outage(hass: HomeAssistant, init_integration, mock_pump_api, freezer):
    """Running time is unknown while the pump does not answer: uptime counts again from its recovery."""
    mock_pump_api.get_status.side_effect = UNREACHABLE
    await poll_after(hass, freezer, POLL)
    await poll_after(hass, freezer, timedelta(hours=5))

    mock_pump_api.get_status.side_effect = None
    await poll_after(hass, freezer, POLL)

    assert float(state(hass, "sensor", "uptime_hours")) == 0


# --- Solar regulation ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state_value", "attributes"),
    [("-2000", {"unit_of_measurement": "W"}), ("-2", {"unit_of_measurement": "kW"}), ("-2000", {})],
    ids=["W", "kW", "no_unit"],
)
async def test_solar_regulation_reads_the_grid_power_in_its_unit(
    hass: HomeAssistant, solar_entry, mock_pump_api, state_value, attributes
):
    """A grid sensor in kW exporting 2 kW speeds the pump up as much as one exporting 2000 W."""
    hass.states.async_set(MOCK_GRID, state_value, attributes)

    await setup_integration(hass, solar_entry)

    # error = 0 - (-2000) = 2000 -> step capped to step_up 300 -> 1500 + 300
    mock_pump_api.set_key.assert_awaited_once_with("SetCurrentSpeed", 1800)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("grid_entity", "state_value", "attributes"),
    [
        (MOCK_GRID, "unavailable", {}),
        ("sensor.other_grid_power", "-2000", {}),
        (MOCK_GRID, "-2000", {"unit_of_measurement": "VA"}),
    ],
    ids=["unavailable", "missing", "unknown_unit"],
)
async def test_solar_regulation_waits_for_a_usable_grid_reading(
    hass: HomeAssistant, solar_entry, mock_pump_api, grid_entity, state_value, attributes
):
    """A missing, non-numeric or non-power grid reading never moves the pump."""
    hass.states.async_set(grid_entity, state_value, attributes)

    await setup_integration(hass, solar_entry)

    mock_pump_api.set_key.assert_not_called()


@pytest.mark.asyncio
async def test_solar_mode_without_a_grid_sensor_leaves_the_speed_alone(hass: HomeAssistant, mock_pump_api):
    """With no grid sensor configured the solar mode has nothing to regulate on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": "", "grid_power_entity": ""},
        options={"control_mode": "solar"},
        unique_id=MOCK_HOST,
    )

    await setup_integration(hass, entry)

    mock_pump_api.set_key.assert_not_called()


@pytest.mark.asyncio
async def test_solar_regulation_acts_on_a_steady_but_fresh_grid_value(
    hass: HomeAssistant, solar_entry, mock_pump_api, freezer
):
    """A grid sensor re-reporting the same value is fresh: a steady export must still be regulated."""
    hass.states.async_set(MOCK_GRID, "-2000")
    freezer.tick(timedelta(seconds=120))
    hass.states.async_set(MOCK_GRID, "-2000")  # same value, reported again

    await setup_integration(hass, solar_entry)

    mock_pump_api.set_key.assert_awaited_once()


@pytest.mark.asyncio
async def test_solar_regulation_ignores_a_stale_grid_value(hass: HomeAssistant, solar_entry, mock_pump_api, freezer):
    """A grid reading older than the staleness limit must not trigger a speed change."""
    hass.states.async_set(MOCK_GRID, "-2000")
    freezer.tick(timedelta(seconds=120))

    await setup_integration(hass, solar_entry)

    mock_pump_api.set_key.assert_not_called()


@pytest.mark.asyncio
async def test_failed_solar_command_keeps_the_poll_result(hass: HomeAssistant, solar_entry, mock_pump_api):
    """A rejected speed command must not throw away the status that was read successfully."""
    hass.states.async_set(MOCK_GRID, "-2000")  # exporting: the regulator speeds up
    mock_pump_api.set_key.side_effect = UNREACHABLE

    await setup_integration(hass, solar_entry)

    assert float(state(hass, "number", "current_speed")) == 1500
    mock_pump_api.set_key.assert_awaited_once()


@pytest.mark.asyncio
async def test_throttled_solar_step_is_skipped_quietly(
    hass: HomeAssistant, solar_entry, mock_pump_api, caplog, freezer
):
    """The solar mode waits for the next allowed change without logging a warning at every poll."""
    hass.states.async_set(MOCK_GRID, "-2000")  # exporting: the regulator speeds up
    await setup_integration(hass, solar_entry)

    await _poll_with_fresh_grid(hass, freezer, POLL)

    mock_pump_api.set_key.assert_awaited_once()
    assert "failed" not in caplog.text


@pytest.mark.asyncio
async def test_missing_grid_sensor_is_logged_once_until_it_appears(
    hass: HomeAssistant, solar_entry, mock_pump_api, caplog, freezer
):
    """A missing grid sensor is reported once, not at every poll, then once when regulation resumes."""
    await setup_integration(hass, solar_entry)
    await poll_after(hass, freezer, POLL)
    await poll_after(hass, freezer, POLL)

    assert _grid_logs(caplog, logging.WARNING) == ["Grid power entity 'sensor.grid_power' not found"]

    hass.states.async_set(MOCK_GRID, "50")
    await poll_after(hass, freezer, POLL)
    await poll_after(hass, freezer, POLL)

    assert _grid_logs(caplog, logging.INFO) == [
        "Grid power entity 'sensor.grid_power' usable again: solar regulation resumes"
    ]


@pytest.mark.asyncio
async def test_stale_grid_sensor_is_logged_once_until_it_reports_again(
    hass: HomeAssistant, solar_entry, mock_pump_api, caplog, freezer
):
    """A grid sensor that stopped reporting is reported once, not at every poll, then once when it reports again."""
    hass.states.async_set(MOCK_GRID, "50")
    await setup_integration(hass, solar_entry)
    await poll_after(hass, freezer, timedelta(seconds=90))
    await poll_after(hass, freezer, POLL)

    assert len(_grid_logs(caplog, logging.WARNING)) == 1

    hass.states.async_set(MOCK_GRID, "50")
    await poll_after(hass, freezer, POLL)
    await poll_after(hass, freezer, POLL)

    assert len(_grid_logs(caplog, logging.INFO)) == 1


@pytest.mark.asyncio
async def test_solar_regulation_waits_for_the_priming_after_the_switch_turns_on(
    hass: HomeAssistant, mock_pump_api, freezer
):
    """After the power switch turns on, the pump primes at its own speed before the solar mode drives it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": MOCK_SWITCH, "grid_power_entity": MOCK_GRID},
        options={"control_mode": "solar", "priming_time": 120},
        unique_id=MOCK_HOST,
    )
    hass.states.async_set(MOCK_SWITCH, "off")
    await setup_integration(hass, entry)
    hass.states.async_set(MOCK_GRID, "-2000")
    hass.states.async_set(MOCK_SWITCH, "on")
    await hass.async_block_till_done()
    await _poll_with_fresh_grid(hass, freezer, POLL)

    mock_pump_api.set_key.assert_not_called()

    await _poll_with_fresh_grid(hass, freezer, timedelta(seconds=90))

    mock_pump_api.set_key.assert_awaited_once_with("SetCurrentSpeed", 1800)
