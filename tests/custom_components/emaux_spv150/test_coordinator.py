import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

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
    """Coordinator should return parsed pump data on a successful poll."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    with patch.object(coordinator, "api_pump", mock_pump_api):
        data = await coordinator._async_update_data()

    assert data["CurrentWatts"] == "300"
    assert data["RunningStatus"] == "1"


@pytest.mark.asyncio
async def test_update_data_empty_raises(hass: HomeAssistant, config_entry):
    """An empty API response should raise UpdateFailed."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)

    empty_api = AsyncMock()
    empty_api.get_status = AsyncMock(return_value={})

    with patch.object(coordinator, "api_pump", empty_api):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_switch_off(hass: HomeAssistant, config_entry, mock_pump_api):
    """When the linked switch is OFF, coordinator should return zeroed data without calling the API."""
    # Add a fake switch entity in state "off"
    hass.states.async_set("switch.pool_power", "off")

    # Override entry data to reference that switch
    config_entry_with_switch = config_entry
    object.__setattr__(config_entry_with_switch, "_data", {
        "host": "192.168.1.50",
        "switch_entity": "switch.pool_power",
    })

    config_entry_with_switch.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry_with_switch)
    coordinator.switch_entity_id = "switch.pool_power"

    with patch.object(coordinator, "api_pump", mock_pump_api):
        data = await coordinator._async_update_data()

    assert data["CurrentWatts"] == "0"
    assert data["RunningStatus"] == "0"
    # API should NOT have been called
    mock_pump_api.get_status.assert_not_called()


@pytest.mark.asyncio
async def test_speed_change_throttle(hass: HomeAssistant, config_entry, mock_pump_api):
    """Speed changes should be blocked within the throttle interval."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.speed_change_interval = 60

    with patch.object(coordinator, "api_pump", mock_pump_api):
        # First change: allowed
        result1 = await coordinator.async_set_pump_key("SetCurrentSpeed", 1500)
        assert result1 is not None

        # Immediate second change: throttled
        result2 = await coordinator.async_set_pump_key("SetCurrentSpeed", 1800)
        assert result2 is None

    # Only the first call should have reached the API
    assert mock_pump_api.set_key.call_count == 1


@pytest.mark.asyncio
async def test_speed_change_throttle_bypass_in_maintenance(hass: HomeAssistant, config_entry, mock_pump_api):
    """Speed changes are blocked in maintenance mode regardless of throttle."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.speed_change_interval = 60
    coordinator.enable_maintenance(30)

    with patch.object(coordinator, "api_pump", mock_pump_api):
        result = await coordinator.async_set_pump_key("SetCurrentSpeed", 1500)
        assert result is None

    mock_pump_api.set_key.assert_not_called()


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
async def test_priming_sequence_unlocks_solar_after_delay(hass: HomeAssistant, config_entry, mock_pump_api):
    """After priming completes, _priming_done should be True and no SetCurrentSpeed sent (solar regulation handles it)."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.control_mode = "solar"
    coordinator.priming_time = 120
    coordinator.speed_change_interval = 0

    with patch.object(coordinator, "api_pump", mock_pump_api):
        mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": "1"})
        await coordinator._async_update_data()  # transition 0→1
        assert coordinator._pump_started_at is not None
        assert coordinator._priming_done is False

        from datetime import timedelta
        from homeassistant.util import dt as dt_util
        coordinator._pump_started_at = dt_util.utcnow() - timedelta(seconds=130)

        await coordinator._async_update_data()
        assert coordinator._priming_done is True

    # Priming itself must NOT send any SetCurrentSpeed — solar regulation handles the speed
    calls = [c for c in mock_pump_api.set_key.call_args_list if c.args[0] == "SetCurrentSpeed"]
    assert not calls


@pytest.mark.asyncio
async def test_priming_not_done_before_delay(hass: HomeAssistant, config_entry, mock_pump_api):
    """rpm_min_solar should NOT be sent before priming time elapses."""
    config_entry.add_to_hass(hass)
    coordinator = PumpCoordinator(hass, config_entry)
    coordinator.control_mode = "solar"
    coordinator.priming_time = 120
    coordinator.speed_change_interval = 0

    with patch.object(coordinator, "api_pump", mock_pump_api):
        mock_pump_api.get_status = AsyncMock(return_value={**MOCK_STATUS, "RunningStatus": "1"})
        await coordinator._async_update_data()  # transition 0→1

        # Immediately poll again (< 120s elapsed)
        await coordinator._async_update_data()
        assert coordinator._priming_done is False

    speed_calls = [c for c in mock_pump_api.set_key.call_args_list if c.args[0] == "SetCurrentSpeed"]
    assert not speed_calls
