import pytest
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.emaux_spv150.const import DOMAIN

MOCK_HOST = "192.168.1.50"
MOCK_STATUS = {
    "CurrentSpeed": "1500",
    "CurrentWatts": "300",
    "RunningStatus": "1",
    "SpeedSelected": "2",
    "CurrentGPM": "45",
}


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
