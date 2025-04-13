from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity
from .utils import camel_to_snake

PARALLEL_UPDATES = 1

SENSOR_ENTITY_CONFIG = [
    {
        "name": "CurrentWatts",
        "translation_key": "current_watts",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:flash",
    },
    {
        "name": "CurrentGPM",
        "translation_key": "current_gpm",
        "unit": UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-pump",
    },
    {
        "name": "UptimeHours",
        "translation_key": "uptime_hours",
        "unit": UnitOfTime.HOURS,
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:clock-start",
        "source": "coordinator",
    },
]


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Emaux SPV150 sensor entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [PumpSensor(coordinator, config) for config in SENSOR_ENTITY_CONFIG]
    entities.append(PumpEnergySensor(coordinator))
    async_add_entities(entities, update_before_add=True)


class PumpSensor(PumpBaseEntity, SensorEntity):
    """Sensor entity for a numeric pump measurement."""

    def __init__(self, coordinator: PumpCoordinator, config: dict) -> None:
        super().__init__(coordinator)
        self._key: str = config["name"]
        self._source: str | None = config.get("source")
        self._attr_translation_key = config["translation_key"]
        self._attr_unique_id = "spv150_" + camel_to_snake(self._key)
        self._attr_native_unit_of_measurement = config["unit"]
        self._attr_device_class = config["device_class"]
        self._attr_state_class = config["state_class"]
        self._attr_icon = config["icon"]

    @property
    def native_value(self) -> float | None:
        """Return the current sensor value from coordinator data or coordinator attributes."""
        if self._source == "coordinator":
            return self.coordinator.uptime_hours if self._key == "UptimeHours" else None
        raw = self.coordinator.data.get(self._key)
        if raw is None:
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None


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
                pass

    @property
    def native_value(self) -> float | None:
        """Return cumulated energy in kWh from coordinator."""
        return self.coordinator.energy_kwh
