from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

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
        data={"host": MOCK_HOST, "switch_entity": ""},
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


@pytest.fixture
async def init_integration(hass: HomeAssistant, config_entry, mock_pump_api) -> MockConfigEntry:
    """The default entry, set up with a pump that answers MOCK_STATUS."""
    await setup_integration(hass, config_entry)
    return config_entry


async def setup_integration(hass: HomeAssistant, entry) -> None:
    """Add the entry to Home Assistant and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def poll_after(hass: HomeAssistant, freezer, delay: timedelta) -> None:
    """Let time pass and run the poll that is due."""
    freezer.tick(delay)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    """Entity ID of one of the pump entities, found by its unique ID."""
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"spv150_{key}")


def state(hass: HomeAssistant, platform: str, key: str) -> str:
    """Current state of one of the pump entities."""
    return hass.states.get(entity_id(hass, platform, key)).state
