from asyncio import sleep

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import REVOLUTIONS_PER_MINUTE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.emaux_spv150 import DOMAIN
from custom_components.emaux_spv150.utils import camel_to_snake

from .coordinator import PumpCoordinator

NUMBER_ENTITY_CONFIG = [
    {
        "name": "CurrentSpeed",
        "set_key": "SetCurrentSpeed",
        "min_val": 800,
        "max_val": 3400,
        "step": 10,
        "unit": REVOLUTIONS_PER_MINUTE,
        "icon": "mdi:speedometer",
    },
    {
        "name": "SpeedSelected",
        "set_key": "SetSpeedSelected",
        "min_val": 1,
        "max_val": 3,
        "step": 1,
        "unit": "level",
        "icon": "mdi:numeric",
    },
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configurer le contrôle de la pompe Emaux SPV150."""
    coordinator: PumpCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [PumpNumber(coordinator, entity) for entity in NUMBER_ENTITY_CONFIG]

    async_add_entities(entities, update_before_add=True)
    await coordinator.async_refresh()


class PumpNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator: PumpCoordinator, entity: dict) -> None:
        super().__init__(coordinator)
        self._name = entity["name"]
        self._set_key = entity["set_key"]
        self._attr_native_min_value = entity["min_val"]
        self._attr_native_max_value = entity["max_val"]
        self._attr_native_step = entity["step"]
        self._attr_native_unit_of_measurement = entity["unit"]
        self._attr_icon = entity["icon"]
        self._attr_native_value = 0
        self._attr_unique_id = "spv150_" + camel_to_snake(self._name)

    @property
    def name(self) -> str:
        """Retourne le nom du nombre."""
        return self._name

    @property
    def native_value(self) -> float | None:
        """Retourne la valeur native."""
        return self.coordinator.data.get(self._name, None)

    async def async_set_native_value(self, value: float) -> None:
        """Met à jour la valeur de la pompe et rafraîchit les données."""
        self._attr_native_value = await self.coordinator.api_pump.set_key(
            self._set_key, int(value)
        )
        await sleep(2)
        await self.coordinator.async_refresh()
