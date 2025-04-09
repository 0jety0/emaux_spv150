# custom_components/emaux_spv150/sensor.py

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EmauxCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EmauxCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            EmauxSensor(
                coordinator, "CurrentWatts", "Puissance", UnitOfPower.WATT, "mdi:flash"
            ),
            EmauxSensor(
                coordinator,
                "CurrentSpeed",
                "Vitesse actuelle",
                "rpm",
                "mdi:rotate-right",
            ),
            EmauxSensor(
                coordinator, "RunningStatus", "Statut pompe", None, "mdi:power"
            ),
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
        self.coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.host}_{key}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | int:
        value = self.coordinator.data.get(self._key)
        if self._key == "RunningStatus":
            return "on" if value == "1" else "off"
        return value
