from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.emaux_spv150 import DOMAIN
from custom_components.emaux_spv150.utils import camel_to_snake

from .coordinator import PumpCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configurer le switch de la pompe Emaux SPV150 pour le contrôle du RUN."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [RunStopSwitchEntity(coordinator)],
        update_before_add=True,
    )
    await coordinator.async_refresh()


class RunStopSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Switch pour contrôler l'état de la pompe (Run/Stop)."""

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._name = "RunningStatus"
        self._attr_unique_id = "spv150_" + camel_to_snake(self._name)
        self._attr_is_on = False
        self._attr_icon = "mdi:power"
        self._set_key = "RunStop"

    @property
    def name(self) -> str:
        """Retourne le nom du switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Retourne l'état actuel de la pompe (en marche ou arrêtée)."""
        return self.coordinator.data.get(self._name, "0") == "1"

    async def async_turn_on(self) -> None:
        await self.coordinator.api_pump.set_key(self._set_key, 1)

    async def async_turn_off(self) -> None:
        await self.coordinator.api_pump.set_key(self._set_key, 2)
