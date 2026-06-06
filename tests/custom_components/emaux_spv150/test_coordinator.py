from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.emaux_spv150.coordinator import PumpCoordinator

MOCK_STATUS = {
    "CurrentSpeed": "1500",
    "CurrentWatts": "300",
    "RunningStatus": "1",
    "SpeedSelected": "2",
    "CurrentGPM": "45",
}


@pytest.mark.asyncio
async def test_update_data_success(hass: HomeAssistant, config_entry, mock_pump_api):
    """Coordinator should return a typed PumpStatus on a successful poll."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    with patch.object(coordinator, "api_pump", mock_pump_api):
        data = await coordinator._async_update_data()

    assert data.current_watts == 300.0
    assert data.current_speed == 1500.0
    assert data.speed_selected == 2
    assert data.running is True


@pytest.mark.asyncio
async def test_running_status_normalised_from_int(hass: HomeAssistant, config_entry, mock_pump_api):
    """RunningStatus should be parsed correctly even if the pump returns an int."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": 1})

    with patch.object(coordinator, "api_pump", mock_pump_api):
        data = await coordinator._async_update_data()

    assert data.running is True


@pytest.mark.asyncio
async def test_update_data_empty_raises(hass: HomeAssistant, config_entry):
    """An empty API response should raise UpdateFailed."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    empty_api = AsyncMock()
    empty_api.get_status = AsyncMock(return_value={})

    with patch.object(coordinator, "api_pump", empty_api), pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_switch_off(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """When the linked switch is OFF, coordinator returns zeroed data without calling the API."""
    hass.states.async_set("switch.pool_power", "off")
    config_entry_with_switch.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry_with_switch)

    with patch.object(coordinator, "api_pump", mock_pump_api):
        data = await coordinator._async_update_data()

    assert data.current_watts == 0.0
    assert data.running is False
    assert coordinator.pump_switch_off is True
    mock_pump_api.get_status.assert_not_called()


@pytest.mark.asyncio
async def test_speed_change_throttle(hass: HomeAssistant, config_entry, mock_pump_api):
    """Speed changes should be blocked within the throttle interval."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.speed_change_interval = 60

    with patch.object(coordinator, "api_pump", mock_pump_api):
        result1 = await coordinator.async_set_pump_key("SetCurrentSpeed", 1500)
        assert result1 is not None

        result2 = await coordinator.async_set_pump_key("SetCurrentSpeed", 1800)
        assert result2 is None

    assert mock_pump_api.set_key.call_count == 1


@pytest.mark.asyncio
async def test_speed_change_non_speed_key_not_throttled(hass: HomeAssistant, config_entry, mock_pump_api):
    """Non-speed commands (e.g. RunStop) should not be throttled."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.speed_change_interval = 60

    with patch.object(coordinator, "api_pump", mock_pump_api):
        await coordinator.async_set_pump_key("RunStop", 1)
        await coordinator.async_set_pump_key("RunStop", 0)

    assert mock_pump_api.set_key.call_count == 2


@pytest.mark.asyncio
async def test_priming_sequence_unlocks_solar_after_delay(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """After priming completes, _priming_done becomes True (triggered by switch OFF→ON)."""
    hass.states.async_set("switch.pool_power", "on")
    config_entry_with_switch.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry_with_switch)
    coordinator.control_mode = "solar"
    coordinator.priming_time = 120
    coordinator.speed_change_interval = 0
    # Simulate previous cycle: switch was OFF, so this poll is a fresh OFF→ON.
    coordinator._prev_switch_on = False

    with patch.object(coordinator, "api_pump", mock_pump_api):
        mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": "1"})
        await coordinator._async_update_data()  # OFF→ON transition starts priming
        assert coordinator._pump_started_at is not None
        assert coordinator._priming_done is False

        coordinator._pump_started_at = dt_util.utcnow() - timedelta(seconds=130)
        await coordinator._async_update_data()
        assert coordinator._priming_done is True


@pytest.mark.asyncio
async def test_priming_not_done_before_delay(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """Priming should not complete before the configured delay elapses."""
    hass.states.async_set("switch.pool_power", "on")
    config_entry_with_switch.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry_with_switch)
    coordinator.control_mode = "solar"
    coordinator.priming_time = 120
    coordinator.speed_change_interval = 0
    coordinator._prev_switch_on = False

    with patch.object(coordinator, "api_pump", mock_pump_api):
        mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": "1"})
        await coordinator._async_update_data()
        await coordinator._async_update_data()
        assert coordinator._priming_done is False

    speed_calls = [c for c in mock_pump_api.set_key.call_args_list if c.args[0] == "SetCurrentSpeed"]
    assert not speed_calls


@pytest.mark.asyncio
async def test_energy_accumulation(hass: HomeAssistant, config_entry, mock_pump_api):
    """Energy should accumulate from watts and elapsed time."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "CurrentWatts": "1000"})

    with patch.object(coordinator, "api_pump", mock_pump_api):
        await coordinator._async_update_data()  # first poll: anchor, no accumulation
        assert coordinator.energy_kwh == 0.0

        coordinator._last_energy_update = dt_util.utcnow() - timedelta(hours=1)
        await coordinator._async_update_data()  # 1000 W for 1 h = 1 kWh
        assert coordinator.energy_kwh == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_energy_restore(hass: HomeAssistant, config_entry):
    """restore_energy() should seed the cumulated value."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    coordinator.restore_energy(5.2345)
    assert coordinator.energy_kwh == 5.2345


@pytest.mark.asyncio
async def test_uptime_tracking_and_reset(hass: HomeAssistant, config_entry, mock_pump_api):
    """Uptime should start when running and reset to None when stopped."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    with patch.object(coordinator, "api_pump", mock_pump_api):
        mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": "1"})
        await coordinator._async_update_data()
        assert coordinator._uptime_start is not None

        coordinator._uptime_start = dt_util.utcnow() - timedelta(hours=2)
        assert coordinator.uptime_hours == pytest.approx(2.0, abs=0.1)

        mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": "0"})
        await coordinator._async_update_data()
        assert coordinator._uptime_start is None
        assert coordinator.uptime_hours is None


@pytest.mark.asyncio
async def test_set_rpm_min_capped_to_max(hass: HomeAssistant, config_entry):
    """rpm_min_solar cannot exceed rpm_max_solar (invariant kept)."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.rpm_max_solar = 2000

    coordinator.set_rpm_min_solar(2500)
    assert coordinator.rpm_min_solar == 2000


@pytest.mark.asyncio
async def test_set_rpm_max_raised_to_min(hass: HomeAssistant, config_entry):
    """rpm_max_solar cannot drop below rpm_min_solar (invariant kept)."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.rpm_min_solar = 1800

    coordinator.set_rpm_max_solar(1000)
    assert coordinator.rpm_max_solar == 1800


@pytest.mark.asyncio
async def test_solar_regulation_speeds_up_when_exporting(hass: HomeAssistant, config_entry, mock_pump_api):
    """Grid power below the dead band lower bound should speed the pump up."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.grid_power_entity = "sensor.grid_power"
    coordinator.setpoint = 1000
    coordinator.dead_band_lower = 500
    coordinator.dead_band_upper = 1500
    coordinator.step_up = 200
    coordinator.rpm_min_solar = 800
    coordinator.rpm_max_solar = 3400

    hass.states.async_set("sensor.grid_power", "200")  # below lower bound

    with patch.object(coordinator, "api_pump", mock_pump_api):
        await coordinator._apply_solar_regulation(1500)

    # error = 1000 - 200 = 800 → step = min(200, 800) = 200 → 1700
    mock_pump_api.set_key.assert_called_once_with("SetCurrentSpeed", 1700)


@pytest.mark.asyncio
async def test_solar_regulation_ignores_stale_grid(hass: HomeAssistant, config_entry, mock_pump_api):
    """Stale grid power (> staleness threshold) must not trigger a speed change."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.grid_power_entity = "sensor.grid_power"
    coordinator.dead_band_lower = 500
    coordinator.dead_band_upper = 1500

    hass.states.async_set("sensor.grid_power", "200")
    # Make "now" 120 s after the state was set so it is considered stale.
    future = dt_util.utcnow() + timedelta(seconds=120)
    with (
        patch("custom_components.emaux_spv150.coordinator.dt_util.utcnow", return_value=future),
        patch.object(coordinator, "api_pump", mock_pump_api),
    ):
        await coordinator._apply_solar_regulation(1500)

    mock_pump_api.set_key.assert_not_called()


@pytest.mark.asyncio
async def test_solar_regulation_no_grid_entity_is_noop(hass: HomeAssistant, config_entry, mock_pump_api):
    """With no grid power entity configured, regulation does nothing."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.grid_power_entity = ""

    with patch.object(coordinator, "api_pump", mock_pump_api):
        await coordinator._apply_solar_regulation(1500)

    mock_pump_api.set_key.assert_not_called()


@pytest.mark.asyncio
async def test_set_dead_band_lower_capped_to_upper(hass: HomeAssistant, config_entry):
    """dead_band_lower cannot exceed dead_band_upper (invariant kept)."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.dead_band_upper = 100

    coordinator.set_dead_band_lower(500)
    assert coordinator.dead_band_lower == 100


@pytest.mark.asyncio
async def test_set_dead_band_upper_raised_to_lower(hass: HomeAssistant, config_entry):
    """dead_band_upper cannot drop below dead_band_lower (invariant kept)."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.dead_band_lower = 200

    coordinator.set_dead_band_upper(50)
    assert coordinator.dead_band_upper == 200


@pytest.mark.asyncio
async def test_connection_settings_changed(hass: HomeAssistant, config_entry):
    """Only host/switch/grid changes count as a connection change (reload trigger)."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    assert coordinator.connection_settings_changed(config_entry) is False

    coordinator.host = "10.0.0.1"
    assert coordinator.connection_settings_changed(config_entry) is True


@pytest.mark.asyncio
async def test_set_request_timeout_updates_api(hass: HomeAssistant, config_entry):
    """Changing the request timeout updates both the coordinator and the API client."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    coordinator.set_request_timeout(12)
    assert coordinator.request_timeout == 12
    assert coordinator.api_pump._timeout.total == 12


@pytest.mark.asyncio
async def test_apply_options_updates_live_params(hass: HomeAssistant, config_entry):
    """apply_options pulls regulation params from entry options without a reload."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "setpoint": 1234, "step_up": 250}
    )
    coordinator.apply_options(config_entry)

    assert coordinator.setpoint == 1234.0
    assert coordinator.step_up == 250
