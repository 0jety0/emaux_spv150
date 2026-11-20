from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import REVOLUTIONS_PER_MINUTE, EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEAD_BAND_LOWER,
    CONF_DEAD_BAND_UPPER,
    CONF_POLL_INTERVAL,
    CONF_REQUEST_TIMEOUT,
    CONF_RPM_MAX_SOLAR,
    CONF_RPM_MIN_SOLAR,
    CONF_SETPOINT,
    CONF_STEP_DOWN,
    CONF_STEP_UP,
    POWER_SETTING_MAX,
    POWER_SETTING_MIN,
    STEP_DOWN_MAX,
    STEP_DOWN_MIN,
    STEP_UP_MAX,
    STEP_UP_MIN,
    PumpCommand,
)
from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PumpNumberDescription(NumberEntityDescription):
    """A value read from the pump and written to it with a pump command."""

    value_fn: Callable[[PumpCoordinator], float | None]
    command: PumpCommand


@dataclass(frozen=True, kw_only=True)
class SettingNumberDescription(NumberEntityDescription):
    """A regulation setting kept in the entry options and applied live."""

    value_fn: Callable[[PumpCoordinator], float]
    option_key: str


PUMP_NUMBER_DESCRIPTIONS: tuple[PumpNumberDescription, ...] = (
    PumpNumberDescription(
        key="current_speed",
        translation_key="current_speed",
        native_min_value=800,
        native_max_value=3400,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        mode=NumberMode.SLIDER,
        command=PumpCommand.SET_CURRENT_SPEED,
        value_fn=lambda c: c.data.current_speed,
    ),
    PumpNumberDescription(
        key="speed_selected",
        translation_key="speed_selected",
        native_min_value=1,
        native_max_value=3,
        native_step=1,
        mode=NumberMode.SLIDER,
        command=PumpCommand.SET_SPEED_SELECTED,
        value_fn=lambda c: float(c.data.speed_selected) if c.data.speed_selected is not None else None,
    ),
)

SETTING_NUMBER_DESCRIPTIONS: tuple[SettingNumberDescription, ...] = (
    SettingNumberDescription(
        key="setpoint",
        translation_key="setpoint",
        entity_category=EntityCategory.CONFIG,
        native_min_value=POWER_SETTING_MIN,
        native_max_value=POWER_SETTING_MAX,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        option_key=CONF_SETPOINT,
        value_fn=lambda c: c.setpoint,
    ),
    SettingNumberDescription(
        key="dead_band_lower",
        translation_key="dead_band_lower",
        entity_category=EntityCategory.CONFIG,
        native_min_value=POWER_SETTING_MIN,
        native_max_value=POWER_SETTING_MAX,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        option_key=CONF_DEAD_BAND_LOWER,
        value_fn=lambda c: c.dead_band_lower,
    ),
    SettingNumberDescription(
        key="dead_band_upper",
        translation_key="dead_band_upper",
        entity_category=EntityCategory.CONFIG,
        native_min_value=POWER_SETTING_MIN,
        native_max_value=POWER_SETTING_MAX,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        option_key=CONF_DEAD_BAND_UPPER,
        value_fn=lambda c: c.dead_band_upper,
    ),
    SettingNumberDescription(
        key="step_up",
        translation_key="step_up",
        entity_category=EntityCategory.CONFIG,
        native_min_value=STEP_UP_MIN,
        native_max_value=STEP_UP_MAX,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        mode=NumberMode.BOX,
        option_key=CONF_STEP_UP,
        value_fn=lambda c: float(c.step_up),
    ),
    SettingNumberDescription(
        key="step_down",
        translation_key="step_down",
        entity_category=EntityCategory.CONFIG,
        native_min_value=STEP_DOWN_MIN,
        native_max_value=STEP_DOWN_MAX,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        mode=NumberMode.BOX,
        option_key=CONF_STEP_DOWN,
        value_fn=lambda c: float(c.step_down),
    ),
    SettingNumberDescription(
        key="rpm_min_solar",
        translation_key="rpm_min_solar",
        entity_category=EntityCategory.CONFIG,
        native_min_value=800,
        native_max_value=3400,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        mode=NumberMode.BOX,
        option_key=CONF_RPM_MIN_SOLAR,
        value_fn=lambda c: float(c.rpm_min_solar),
    ),
    SettingNumberDescription(
        key="rpm_max_solar",
        translation_key="rpm_max_solar",
        entity_category=EntityCategory.CONFIG,
        native_min_value=800,
        native_max_value=3400,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        mode=NumberMode.BOX,
        option_key=CONF_RPM_MAX_SOLAR,
        value_fn=lambda c: float(c.rpm_max_solar),
    ),
    SettingNumberDescription(
        key="poll_interval",
        translation_key="poll_interval",
        entity_category=EntityCategory.CONFIG,
        native_min_value=5,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        option_key=CONF_POLL_INTERVAL,
        value_fn=lambda c: float(c.poll_interval),
    ),
    SettingNumberDescription(
        key="request_timeout",
        translation_key="request_timeout",
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=30,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        option_key=CONF_REQUEST_TIMEOUT,
        value_fn=lambda c: float(c.request_timeout),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up Emaux SPV150 number entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    entities: list[NumberEntity] = [PumpNumber(coordinator, description) for description in PUMP_NUMBER_DESCRIPTIONS]
    entities += [SettingNumber(coordinator, description) for description in SETTING_NUMBER_DESCRIPTIONS]
    async_add_entities(entities)


class PumpNumber(PumpBaseEntity, NumberEntity):
    """A pump value: follows the pump's availability and is written to the pump."""

    entity_description: PumpNumberDescription

    def __init__(self, coordinator: PumpCoordinator, description: PumpNumberDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"spv150_{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator)

    @override
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_pump_key(self.entity_description.command, int(value))
        await self.coordinator.async_request_refresh()


class SettingNumber(PumpBaseEntity, NumberEntity):
    """A regulation setting: usable while the pump is off, applied live and kept in the options."""

    entity_description: SettingNumberDescription

    def __init__(self, coordinator: PumpCoordinator, description: SettingNumberDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"spv150_{description.key}"

    @property
    @override
    def available(self) -> bool:
        return True

    @property
    @override
    def native_value(self) -> float:
        return self.entity_description.value_fn(self.coordinator)

    @override
    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.set_option(self.entity_description.option_key, value)
        self.async_write_ha_state()
