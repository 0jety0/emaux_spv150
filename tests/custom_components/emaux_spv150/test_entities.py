"""Platform behaviour, tested through Home Assistant services and states."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.icon import async_get_icons
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.emaux_spv150.const import DOMAIN


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"spv150_{key}")


async def _setup_with_pump_powered_off(hass: HomeAssistant, entry) -> None:
    hass.states.async_set("switch.pool_power", "off")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_control_mode_can_be_changed_while_pump_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """The control mode is a local setting: it must stay usable when the pump is powered off."""
    await _setup_with_pump_powered_off(hass, config_entry_with_switch)
    entity_id = _entity_id(hass, "select", "control_mode")

    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": "manual"}, blocking=True
    )

    assert hass.states.get(entity_id).state == "manual"


@pytest.mark.asyncio
async def test_local_setting_can_be_changed_while_pump_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Regulation parameters are local: they must stay usable when the pump is powered off."""
    await _setup_with_pump_powered_off(hass, config_entry_with_switch)
    entity_id = _entity_id(hass, "number", "setpoint")

    await hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": 120}, blocking=True)

    assert float(hass.states.get(entity_id).state) == 120


@pytest.mark.asyncio
async def test_pump_backed_values_are_unavailable_while_pump_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Values read from the pump cannot be known while it is powered off."""
    await _setup_with_pump_powered_off(hass, config_entry_with_switch)

    assert hass.states.get(_entity_id(hass, "number", "current_speed")).state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_options_flow_change_shows_immediately(hass: HomeAssistant, config_entry, mock_pump_api):
    """A setpoint saved through the options flow is displayed at once, not after the next poll."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.emaux_spv150.config_flow.PumpAPI",
        return_value=AsyncMock(get_status=AsyncMock(return_value=mock_pump_api.get_status.return_value)),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"host": "192.168.1.50", "setpoint": 250}
        )
        await hass.async_block_till_done()

    assert float(hass.states.get(_entity_id(hass, "number", "setpoint")).state) == 250


@pytest.mark.asyncio
async def test_run_command_returns_at_once_and_refreshes_once_the_pump_settled(
    hass: HomeAssistant, config_entry, mock_pump_api
):
    """A command must not block the service call; the status is re-read after the settle delay."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    reads_before = mock_pump_api.get_status.await_count

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": _entity_id(hass, "switch", "running_status")}, blocking=True
    )
    reads_right_after = mock_pump_api.get_status.await_count
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    assert reads_right_after == reads_before
    assert mock_pump_api.get_status.await_count == reads_before + 1


@pytest.mark.asyncio
async def test_settings_and_diagnostics_are_categorised(hass: HomeAssistant, config_entry, mock_pump_api):
    """Regulation settings are config entities and uptime is diagnostic; live pump values stay primary."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    assert registry.async_get(_entity_id(hass, "number", "setpoint")).entity_category is EntityCategory.CONFIG
    assert registry.async_get(_entity_id(hass, "sensor", "uptime_hours")).entity_category is EntityCategory.DIAGNOSTIC
    assert registry.async_get(_entity_id(hass, "number", "current_speed")).entity_category is None


@pytest.mark.asyncio
async def test_switch_flip_is_reflected_without_waiting_for_the_poll(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Turning the power switch off must make the pump values unavailable at once, not after the next poll."""
    hass.states.async_set("switch.pool_power", "on")
    config_entry_with_switch.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_with_switch.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("switch.pool_power", "off")
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, "number", "current_speed")).state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_every_entity_takes_its_icon_from_icons_json(hass: HomeAssistant, config_entry, mock_pump_api):
    """Icons are icon translations (icons.json), not hard-coded on the entities."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    icons = (await async_get_icons(hass, "entity", integrations=[DOMAIN]))[DOMAIN]

    translated = {(platform, key) for platform, keys in icons.items() for key in keys}
    assert {(e.domain, e.translation_key) for e in entries} - translated == set()
    assert [e.entity_id for e in entries if "icon" in hass.states.get(e.entity_id).attributes] == []


@pytest.mark.asyncio
async def test_all_entities_belong_to_one_pump_device(hass: HomeAssistant, config_entry, mock_pump_api):
    """Every entity is grouped under a single Emaux SPV150 device."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)

    assert [(d.manufacturer, d.model, d.name) for d in devices] == [("Emaux", "SPV150", "Emaux SPV150")]
    assert {e.device_id for e in entries} == {devices[0].id}
