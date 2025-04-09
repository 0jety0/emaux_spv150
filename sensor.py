from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging
from .const import DOMAIN
from .coordinator import EmauxCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Emaux SPV150 sensors."""
    coordinator: EmauxCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Add sensors
    async_add_entities(
        [
            EmauxSensor(coordinator, "CurrentWatts", "Puissance", UnitOfPower.WATT, "mdi:flash"),
            EmauxSensor(coordinator, "CurrentSpeed", "Vitesse actuelle", "rpm", "mdi:rotate-right"),
            EmauxSensor(coordinator, "RunningStatus", "Statut pompe", None, "mdi:power"),
            EmauxSensor(coordinator, "Temperature", "Température", "°C", "mdi:thermometer"),
        ]
    )


class EmauxSensor(SensorEntity):
    def __init__(
        self,
        coordinator: EmauxCoordinator,
        key: str,
        name: str,
        unit: str | None,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.host}_{key}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | int:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            _LOGGER.warning(f"No data found for key: {self._key}")
            return None
        if self._key == "RunningStatus":
            return "on" if value == "1" else "off"
        return value

    async def async_update(self):
        """Update the sensor with the latest data from the coordinator."""
        await self.coordinator.async_request_refresh()
