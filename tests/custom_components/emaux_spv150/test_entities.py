"""Platform behaviour, tested through Home Assistant services and states."""

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
