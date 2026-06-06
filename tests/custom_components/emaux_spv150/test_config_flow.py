from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.emaux_spv150.const import DOMAIN

MOCK_HOST = "192.168.1.50"
MOCK_STATUS = {
    "CurrentSpeed": "1500",
    "CurrentWatts": "300",
    "RunningStatus": "1",
    "SpeedSelected": "2",
    "CurrentGPM": "45",
}


def _patch_api(return_value=MOCK_STATUS):
    return patch(
        "custom_components.emaux_spv150.config_flow.PumpAPI",
        return_value=AsyncMock(get_status=AsyncMock(return_value=return_value)),
    )


@pytest.mark.asyncio
async def test_user_step_success(hass: HomeAssistant):
    """A valid host that responds should create a config entry."""
    # Patch async_setup_entry so creating the entry does not start the real
    # coordinator (which would leave a lingering poll timer at teardown).
    with (
        _patch_api(),
        patch("custom_components.emaux_spv150.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == MOCK_HOST


@pytest.mark.asyncio
async def test_user_step_cannot_connect(hass: HomeAssistant):
    """An unreachable host should surface the cannot_connect error."""
    with _patch_api(return_value={}):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": MOCK_HOST},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_step_invalid_host(hass: HomeAssistant):
    """A malformed host should surface the invalid_host error before any request."""
    with _patch_api():
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "not a host!!"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


@pytest.mark.asyncio
async def test_reconfigure_success(hass: HomeAssistant, config_entry, mock_pump_api):
    """Reconfiguration with a valid host should update entry data and abort."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    new_host = "192.168.1.77"
    with _patch_api():
        result = await config_entry.start_reconfigure_flow(hass)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": new_host, "grid_power_entity": ""},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["host"] == new_host


@pytest.mark.asyncio
async def test_user_step_already_configured(hass: HomeAssistant, config_entry, mock_pump_api):
    """A duplicate host should abort with already_configured."""
    config_entry.add_to_hass(hass)

    with _patch_api():
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": MOCK_HOST},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_options_flow(hass: HomeAssistant, config_entry, mock_pump_api):
    """Options flow should update host and reload the entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    new_host = "192.168.1.99"

    with _patch_api():
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"host": new_host},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.options["host"] == new_host
