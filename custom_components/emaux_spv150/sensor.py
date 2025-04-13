import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMPERATURE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.emaux_spv150 import DOMAIN
from custom_components.emaux_spv150.utils import camel_to_snake

from .coordinator import PumpCoordinator

SENSOR_ENTITY_CONFIG = [
    {
        "name": "CurrentWatts",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:flash",
    },
    {
        "name": "CurrentGPM",
        "unit": "GPM",
        "icon": "mdi:water-pump",
    },
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configurer les capteurs de la pompe Emaux SPV150."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [PompeSensor(coordinator, entity) for entity in SENSOR_ENTITY_CONFIG]

    async_add_entities(entities, update_before_add=True)
    await coordinator.async_refresh()


class PompeSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: PumpCoordinator, entity: dict) -> None:
        super().__init__(coordinator)
        self._name = entity["name"]
        self._unit = entity["unit"]
        self._attr_icon = entity["icon"]
        self._attr_unique_id = "spv150_" + camel_to_snake(self._name)
        self._attr_native_value = 0

    @property
    def name(self) -> str:
        """Retourne le nom du capteur."""
        return self._name

    @property
    def unit_of_measurement(self) -> str:
        """Retourne l'unité du capteur."""
        return self._unit

    @property
    def icon(self) -> str:
        """Retourne l'icône du capteur."""
        return self._attr_icon

    @property
    def native_value(self) -> float | None:
        """Retourne la valeur du capteur."""
        return self.coordinator.data.get(self._name, None)
