import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import REVOLUTIONS_PER_MINUTE, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COMMAND_SETTLE_DELAY
from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PumpNumberDescription(NumberEntityDescription):
    """Describes an Emaux SPV150 number entity.

    Single source of truth: each entry carries its presentation (inherited from
    NumberEntityDescription) and its behaviour. ``value_fn`` reads the current
    value; writes go either to the pump (``set_key``) or locally (``set_fn``).
    """

    value_fn: Callable[[PumpCoordinator], float | None]
    set_key: str | None = None
    set_fn: Callable[[PumpCoordinator, float], None] | None = None


NUMBER_DESCRIPTIONS: tuple[PumpNumberDescription, ...] = (
    # --- Pump-backed values (written over HTTP) ---
    PumpNumberDescription(
        key="current_speed",
        translation_key="current_speed",
        native_min_value=800,
        native_max_value=3400,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:speedometer",
        mode=NumberMode.SLIDER,
        set_key="SetCurrentSpeed",
        value_fn=lambda c: c.data.current_speed,
    ),
    PumpNumberDescription(
        key="speed_selected",
        translation_key="speed_selected",
        native_min_value=1,
        native_max_value=3,
        native_step=1,
        icon="mdi:numeric",
        mode=NumberMode.SLIDER,
        set_key="SetSpeedSelected",
        value_fn=lambda c: float(c.data.speed_selected) if c.data.speed_selected is not None else None,
    ),
    # --- Local regulation parameters (applied live, persisted in options) ---
    PumpNumberDescription(
        key="setpoint",
        translation_key="setpoint",
        native_min_value=-5000,
        native_max_value=5000,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:target",
        mode=NumberMode.BOX,
        value_fn=lambda c: c.setpoint,
        set_fn=lambda c, v: c.set_setpoint(float(v)),
    ),
    PumpNumberDescription(
        key="dead_band_lower",
        translation_key="dead_band_lower",
        native_min_value=-5000,
        native_max_value=5000,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:solar-power",
        mode=NumberMode.BOX,
        value_fn=lambda c: c.dead_band_lower,
        set_fn=lambda c, v: c.set_dead_band_lower(float(v)),
    ),
    PumpNumberDescription(
        key="dead_band_upper",
        translation_key="dead_band_upper",
        native_min_value=-5000,
        native_max_value=5000,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:transmission-tower",
        mode=NumberMode.BOX,
        value_fn=lambda c: c.dead_band_upper,
        set_fn=lambda c, v: c.set_dead_band_upper(float(v)),
    ),
    PumpNumberDescription(
        key="step_up",
        translation_key="step_up",
        native_min_value=10,
        native_max_value=1000,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:chevron-up-circle",
        mode=NumberMode.BOX,
        value_fn=lambda c: float(c.step_up),
        set_fn=lambda c, v: c.set_step_up(int(v)),
    ),
    PumpNumberDescription(
        key="step_down",
        translation_key="step_down",
        native_min_value=10,
        native_max_value=500,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:chevron-down-circle",
        mode=NumberMode.BOX,
        value_fn=lambda c: float(c.step_down),
        set_fn=lambda c, v: c.set_step_down(int(v)),
    ),
    PumpNumberDescription(
        key="rpm_min_solar",
        translation_key="rpm_min_solar",
        native_min_value=800,
        native_max_value=3400,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:speedometer-slow",
        mode=NumberMode.BOX,
        value_fn=lambda c: float(c.rpm_min_solar),
        set_fn=lambda c, v: c.set_rpm_min_solar(int(v)),
    ),
    PumpNumberDescription(
        key="rpm_max_solar",
        translation_key="rpm_max_solar",
        native_min_value=800,
        native_max_value=3400,
        native_step=10,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:speedometer",
        mode=NumberMode.BOX,
        value_fn=lambda c: float(c.rpm_max_solar),
        set_fn=lambda c, v: c.set_rpm_max_solar(int(v)),
    ),
    PumpNumberDescription(
        key="poll_interval",
        translation_key="poll_interval",
        native_min_value=5,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        mode=NumberMode.BOX,
        value_fn=lambda c: float(int(c.update_interval.total_seconds())),
        set_fn=lambda c, v: c.set_poll_interval(int(v)),
    ),
    PumpNumberDescription(
        key="request_timeout",
        translation_key="request_timeout",
        native_min_value=1,
        native_max_value=30,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        mode=NumberMode.BOX,
        value_fn=lambda c: float(c.request_timeout),
        set_fn=lambda c, v: c.set_request_timeout(int(v)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Emaux SPV150 number entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    async_add_entities(
        [PumpNumber(coordinator, description) for description in NUMBER_DESCRIPTIONS],
        update_before_add=True,
    )


class PumpNumber(PumpBaseEntity, NumberEntity):
    """Number entity for a controllable pump parameter."""

    entity_description: PumpNumberDescription

    def __init__(self, coordinator: PumpCoordinator, description: PumpNumberDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"spv150_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value via the description's value_fn."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Send the new value to the pump or apply it locally on the coordinator."""
        description = self.entity_description
        if description.set_key is not None:
            await self.coordinator.async_set_pump_key(description.set_key, int(value))
            await asyncio.sleep(COMMAND_SETTLE_DELAY)
            await self.coordinator.async_request_refresh()
        elif description.set_fn is not None:
            description.set_fn(self.coordinator, value)
            self.async_write_ha_state()
