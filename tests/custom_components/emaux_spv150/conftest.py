from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.emaux_spv150.const import DOMAIN

MOCK_HOST = "192.168.1.50"
MOCK_SWITCH = "switch.pool_power"
MOCK_GRID = "sensor.grid_power"
MOCK_STATUS = {
    "CurrentSpeed": "1500",
    "CurrentWatts": "300",
    "RunningStatus": "1",
    "SpeedSelected": "2",
    "CurrentGPM": "45",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the custom integration for every test."""
    yield


@pytest.fixture
def mock_pump_api():
    with patch("custom_components.emaux_spv150.coordinator.PumpAPI") as mock:
        instance = mock.return_value
        instance.get_status = AsyncMock(return_value=MOCK_STATUS)
        instance.set_key = AsyncMock(return_value="1500")
        yield instance


@pytest.fixture
def config_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": None},
        options={},
        entry_id="test_entry_id",
        unique_id=MOCK_HOST,
    )


@pytest.fixture
def config_entry_with_switch():
    """Config entry that references an external power switch."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": MOCK_SWITCH},
        options={},
        entry_id="test_entry_switch",
        unique_id=MOCK_HOST,
    )


@pytest.fixture
def solar_entry():
    """Config entry in solar mode, reading a grid-power sensor, without a power switch."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": "", "grid_power_entity": MOCK_GRID},
        options={"control_mode": "solar"},
        entry_id="test_entry_solar",
        unique_id=MOCK_HOST,
    )


async def setup_integration(hass, entry) -> None:
    """Add the entry to Home Assistant and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
