import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PumpSensorDescription(SensorEntityDescription):
    """Describes an Emaux SPV150 sensor entity."""

    value_fn: Callable[[PumpCoordinator], float | None]


SENSOR_DESCRIPTIONS: tuple[PumpSensorDescription, ...] = (
    PumpSensorDescription(
        key="current_watts",
        translation_key="current_watts",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda c: c.data.current_watts,
    ),
    PumpSensorDescription(
        key="current_gpm",
        translation_key="current_gpm",
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-pump",
        value_fn=lambda c: c.data.current_gpm,
    ),
    PumpSensorDescription(
        key="uptime_hours",
        translation_key="uptime_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-start",
        value_fn=lambda c: c.uptime_hours,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Emaux SPV150 sensor entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [PumpSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS]
    entities.append(PumpEnergySensor(coordinator))
    async_add_entities(entities, update_before_add=True)


class PumpSensor(PumpBaseEntity, SensorEntity):
    """Sensor entity for a numeric pump measurement."""

    entity_description: PumpSensorDescription

    def __init__(self, coordinator: PumpCoordinator, description: PumpSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"spv150_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current sensor value via the description's value_fn."""
        return self.entity_description.value_fn(self.coordinator)


class PumpEnergySensor(PumpBaseEntity, RestoreSensor):
    """Energy sensor that persists its cumulated kWh value across HA restarts and reloads."""

    _attr_translation_key = "energy_kwh"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt-circle"

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "spv150_energy_kwh"

    async def async_added_to_hass(self) -> None:
        """Restore the last known energy value on startup."""
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self.coordinator.restore_energy(float(last.native_value))
            except (ValueError, TypeError):
                _LOGGER.warning("Could not restore energy value: %s", last.native_value)

    @property
    def native_value(self) -> float | None:
        """Return cumulated energy in kWh from coordinator."""
        return self.coordinator.energy_kwh
