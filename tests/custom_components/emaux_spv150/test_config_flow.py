from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.emaux_spv150.const import DOMAIN

MOCK_HOST = "192.168.1.50"
MOCK_SWITCH = "switch.pool_power"
UNREACHABLE = {}
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


async def _setup_with_switch(hass: HomeAssistant, entry, switch_state: str) -> None:
    """Load an entry whose external power switch is in the given state."""
    hass.states.async_set(MOCK_SWITCH, switch_state)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


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


@pytest.mark.asyncio
async def test_user_step_skips_pump_when_switch_off(hass: HomeAssistant):
    """With the given switch OFF, the entry is created without contacting the pump."""
    hass.states.async_set(MOCK_SWITCH, "off")
    with (
        _patch_api(return_value=UNREACHABLE) as api_cls,
        patch("custom_components.emaux_spv150.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": MOCK_HOST, "switch_entity": MOCK_SWITCH},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    api_cls.return_value.get_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconfigure_skips_pump_when_switch_off(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """With the switch OFF, reconfiguration is saved without contacting the pump."""
    await _setup_with_switch(hass, config_entry_with_switch, "off")

    new_host = "192.168.1.77"
    with _patch_api(return_value=UNREACHABLE) as api_cls:
        result = await config_entry_with_switch.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": new_host, "switch_entity": MOCK_SWITCH, "grid_power_entity": ""},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry_with_switch.data["host"] == new_host
    api_cls.return_value.get_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_options_flow_skips_pump_when_switch_off(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """With the switch OFF, options are saved without contacting the pump."""
    await _setup_with_switch(hass, config_entry_with_switch, "off")

    with _patch_api(return_value=UNREACHABLE) as api_cls:
        result = await hass.config_entries.options.async_init(config_entry_with_switch.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"host": MOCK_HOST, "switch_entity": MOCK_SWITCH, "setpoint": 80},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry_with_switch.options["setpoint"] == 80
    api_cls.return_value.get_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_options_flow_cannot_connect_when_switch_on(hass: HomeAssistant, config_entry_with_switch, mock_pump_api):
    """With the switch ON, an unreachable pump still blocks the options with cannot_connect."""
    await _setup_with_switch(hass, config_entry_with_switch, "on")

    with _patch_api(return_value=UNREACHABLE):
        result = await hass.config_entries.options.async_init(config_entry_with_switch.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"host": MOCK_HOST, "switch_entity": MOCK_SWITCH},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_reconfigure_wins_over_host_saved_by_options_flow(hass: HomeAssistant, mock_pump_api):
    """A host set earlier through the options flow must not shadow the reconfigured one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_HOST, "switch_entity": ""},
        options={"host": "192.168.1.99", "setpoint": 80},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    new_host = "192.168.1.77"
    with _patch_api():
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": new_host, "switch_entity": "", "grid_power_entity": ""},
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.runtime_data.host == new_host
    assert entry.unique_id == new_host
    assert entry.options["setpoint"] == 80


@pytest.mark.asyncio
async def test_reconfigure_does_not_use_deprecated_reload_helper(
    hass: HomeAssistant, config_entry, mock_pump_api, caplog
):
    """Reconfigure must let the update listener reload (the reload helper breaks in HA 2026.12)."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with _patch_api():
        result = await config_entry.start_reconfigure_flow(hass)
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"host": "192.168.1.77", "switch_entity": "", "grid_power_entity": ""},
        )
        await hass.async_block_till_done()

    assert "should use it for scheduling a reload" not in caplog.text
