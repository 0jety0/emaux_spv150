"""Platform behaviour, tested through Home Assistant services and states."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.icon import async_get_icons
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, mock_restore_cache_with_extra_data

from custom_components.emaux_spv150.const import DOMAIN

from .conftest import MOCK_SWITCH, entity_id, setup_integration


async def _setup_with_pump_powered_off(hass: HomeAssistant, entry) -> None:
    hass.states.async_set(MOCK_SWITCH, "off")
    await setup_integration(hass, entry)


@pytest.mark.asyncio
async def test_control_mode_can_be_changed_while_pump_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """The control mode is a local setting: it must stay usable when the pump is powered off."""
    await _setup_with_pump_powered_off(hass, config_entry_with_switch)
    target = entity_id(hass, "select", "control_mode")

    await hass.services.async_call("select", "select_option", {"entity_id": target, "option": "manual"}, blocking=True)

    assert hass.states.get(target).state == "manual"


@pytest.mark.asyncio
async def test_local_setting_can_be_changed_while_pump_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Regulation parameters are local: they must stay usable when the pump is powered off."""
    await _setup_with_pump_powered_off(hass, config_entry_with_switch)
    target = entity_id(hass, "number", "setpoint")

    await hass.services.async_call("number", "set_value", {"entity_id": target, "value": 120}, blocking=True)

    assert float(hass.states.get(target).state) == 120


@pytest.mark.asyncio
async def test_pump_backed_values_are_unavailable_while_pump_is_off(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Values read from the pump cannot be known while it is powered off."""
    await _setup_with_pump_powered_off(hass, config_entry_with_switch)

    assert hass.states.get(entity_id(hass, "number", "current_speed")).state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_options_flow_change_shows_immediately(hass: HomeAssistant, config_entry, mock_pump_api):
    """A setpoint saved through the options flow is displayed at once, not after the next poll."""
    await setup_integration(hass, config_entry)

    with patch(
        "custom_components.emaux_spv150.config_flow.PumpAPI",
        return_value=AsyncMock(get_status=AsyncMock(return_value=mock_pump_api.get_status.return_value)),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"host": "192.168.1.50", "setpoint": 250}
        )
        await hass.async_block_till_done()

    assert float(hass.states.get(entity_id(hass, "number", "setpoint")).state) == 250


@pytest.mark.asyncio
async def test_run_command_returns_at_once_and_refreshes_once_the_pump_settled(
    hass: HomeAssistant, config_entry, mock_pump_api
):
    """A command must not block the service call; the status is re-read after the settle delay."""
    await setup_integration(hass, config_entry)
    reads_before = mock_pump_api.get_status.await_count

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id(hass, "switch", "running_status")}, blocking=True
    )
    reads_right_after = mock_pump_api.get_status.await_count
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    assert reads_right_after == reads_before
    assert mock_pump_api.get_status.await_count == reads_before + 1


@pytest.mark.asyncio
async def test_settings_and_diagnostics_are_categorised(hass: HomeAssistant, config_entry, mock_pump_api):
    """Regulation settings are config entities and uptime is diagnostic; live pump values stay primary."""
    await setup_integration(hass, config_entry)
    registry = er.async_get(hass)

    assert registry.async_get(entity_id(hass, "number", "setpoint")).entity_category is EntityCategory.CONFIG
    assert registry.async_get(entity_id(hass, "sensor", "uptime_hours")).entity_category is EntityCategory.DIAGNOSTIC
    assert registry.async_get(entity_id(hass, "number", "current_speed")).entity_category is None


@pytest.mark.asyncio
async def test_switch_flip_is_reflected_without_waiting_for_the_poll(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Turning the power switch off must make the pump values unavailable at once, not after the next poll."""
    hass.states.async_set(MOCK_SWITCH, "on")
    await setup_integration(hass, config_entry_with_switch)

    hass.states.async_set(MOCK_SWITCH, "off")
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(hass, "number", "current_speed")).state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_every_entity_takes_its_icon_from_icons_json(hass: HomeAssistant, config_entry, mock_pump_api):
    """Icons are icon translations (icons.json), not hard-coded on the entities."""
    await setup_integration(hass, config_entry)
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    icons = (await async_get_icons(hass, "entity", integrations=[DOMAIN]))[DOMAIN]

    translated = {(platform, key) for platform, keys in icons.items() for key in keys}
    assert {(e.domain, e.translation_key) for e in entries} - translated == set()
    assert [e.entity_id for e in entries if "icon" in hass.states.get(e.entity_id).attributes] == []


@pytest.mark.asyncio
async def test_all_entities_belong_to_one_pump_device(hass: HomeAssistant, config_entry, mock_pump_api):
    """Every entity is grouped under a single Emaux SPV150 device."""
    await setup_integration(hass, config_entry)
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)

    assert [(d.manufacturer, d.model, d.name) for d in devices] == [("Emaux", "SPV150", "Emaux SPV150")]
    assert {e.device_id for e in entries} == {devices[0].id}


@pytest.mark.asyncio
async def test_speed_change_within_the_minimum_interval_is_refused_with_a_reason(
    hass: HomeAssistant, config_entry, mock_pump_api
):
    """A throttled speed change tells the user why instead of being dropped silently."""
    await setup_integration(hass, config_entry)
    target = entity_id(hass, "number", "current_speed")
    await hass.services.async_call("number", "set_value", {"entity_id": target, "value": 1800}, blocking=True)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call("number", "set_value", {"entity_id": target, "value": 2000}, blocking=True)

    assert exc_info.value.translation_key == "speed_change_throttled"
    mock_pump_api.set_key.assert_awaited_once_with("SetCurrentSpeed", 1800)


@pytest.mark.asyncio
@pytest.mark.parametrize(("service", "value"), [("turn_on", 1), ("turn_off", 2)])
async def test_run_stop_switch_sends_run_stop(hass: HomeAssistant, config_entry, mock_pump_api, service, value):
    """The run/stop switch starts the pump with RunStop = 1 and stops it with RunStop = 2."""
    await setup_integration(hass, config_entry)

    await hass.services.async_call(
        "switch", service, {"entity_id": entity_id(hass, "switch", "running_status")}, blocking=True
    )

    mock_pump_api.set_key.assert_awaited_once_with("RunStop", value)


@pytest.mark.asyncio
@pytest.mark.parametrize(("key", "value"), [("step_up", 200), ("step_down", 50), ("poll_interval", 15)])
async def test_local_setting_is_shown_and_saved(hass: HomeAssistant, config_entry, mock_pump_api, key, value):
    """A regulation setting changed from its entity is displayed at once and kept in the entry options."""
    await setup_integration(hass, config_entry)
    target = entity_id(hass, "number", key)

    await hass.services.async_call("number", "set_value", {"entity_id": target, "value": value}, blocking=True)

    assert float(hass.states.get(target).state) == value
    assert config_entry.options[key] == value


@pytest.mark.asyncio
async def test_saved_energy_is_restored_at_startup(hass: HomeAssistant, config_entry, mock_pump_api):
    """The energy counter goes on from the value saved before the restart instead of starting from zero."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.emaux_spv150_energy", "5.2345"),
                {"native_value": 5.2345, "native_unit_of_measurement": "kWh"},
            )
        ],
    )

    await setup_integration(hass, config_entry)

    assert float(hass.states.get(entity_id(hass, "sensor", "energy_kwh")).state) == 5.2345


@pytest.mark.asyncio
async def test_unreadable_saved_energy_restarts_from_zero(hass: HomeAssistant, config_entry, mock_pump_api, caplog):
    """A corrupt saved energy value is reported and the counter starts from zero instead of failing."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State("sensor.emaux_spv150_energy", "abc"), {"native_value": "abc", "native_unit_of_measurement": "kWh"})],
    )

    await setup_integration(hass, config_entry)

    assert float(hass.states.get(entity_id(hass, "sensor", "energy_kwh")).state) == 0
    assert "Could not restore energy value: abc" in caplog.text


@pytest.mark.asyncio
async def test_switch_attribute_change_does_not_poll_the_pump(
    hass: HomeAssistant, config_entry_with_switch, mock_pump_api
):
    """Only a real on/off change of the power switch triggers an immediate poll."""
    hass.states.async_set(MOCK_SWITCH, "on")
    await setup_integration(hass, config_entry_with_switch)
    reads_before = mock_pump_api.get_status.await_count

    hass.states.async_set(MOCK_SWITCH, "on", {"power": 12})
    await hass.async_block_till_done()

    assert mock_pump_api.get_status.await_count == reads_before


@pytest.mark.asyncio
async def test_new_polling_interval_applies_without_a_reload(hass: HomeAssistant, config_entry, mock_pump_api, freezer):
    """A polling interval changed from its entity spaces the polls from the next one on (30 s, then 10 s)."""
    await setup_integration(hass, config_entry)
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id(hass, "number", "poll_interval"), "value": 10}, blocking=True
    )
    reads_before = mock_pump_api.get_status.await_count

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_pump_api.get_status.await_count == reads_before + 2


async def _set_number(hass: HomeAssistant, key: str, value: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id(hass, "number", key), "value": value}, blocking=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bound", "key", "value", "kept"),
    [
        (("rpm_max_solar", 2000), "rpm_min_solar", 2500, 2000),
        (("rpm_min_solar", 1800), "rpm_max_solar", 1000, 1800),
        (("dead_band_upper", 100), "dead_band_lower", 500, 100),
        (("dead_band_lower", 50), "dead_band_upper", 0, 50),
    ],
)
async def test_regulation_ranges_stay_ordered(
    hass: HomeAssistant, config_entry, mock_pump_api, caplog, bound, key, value, kept
):
    """A lower bound is capped to its upper bound and the other way round, so the regulator stays valid."""
    await setup_integration(hass, config_entry)
    await _set_number(hass, *bound)

    await _set_number(hass, key, value)

    assert float(hass.states.get(entity_id(hass, "number", key)).state) == kept
    assert config_entry.options[key] == kept
    assert f"{key} ({value}" in caplog.text


@pytest.mark.asyncio
async def test_new_request_timeout_applies_to_the_next_request(hass: HomeAssistant, config_entry, mock_pump_api):
    """A request timeout changed from its entity is used by the pump client without a reload."""
    await setup_integration(hass, config_entry)

    await _set_number(hass, "request_timeout", 12)

    mock_pump_api.set_timeout.assert_called_with(12)
