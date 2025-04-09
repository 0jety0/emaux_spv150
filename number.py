from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EmauxCoordinator
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Emaux SPV150 number entity."""
    coordinator: EmauxCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Add number entity
    async_add_entities([EmauxNumber(coordinator)])


class EmauxNumber(NumberEntity):
    def __init__(self, coordinator: EmauxCoordinator) -> None:
        """Initialize the number entity."""
        self.coordinator = coordinator
        self._attr_name = "Set Speed"
        self._attr_native_unit_of_measurement = "rpm"
        self._attr_unique_id = f"{coordinator.host}_set_speed"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.get("SetSpeed")

    async def async_set_native_value(self, value: float) -> None:
        speed = int(value)
        url = f"http://{self.host}/cgi-bin/EpvCgi?name=SetCurrentSpeed&val={speed}&type=set&time=Date.now()"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        _LOGGER.info("Vitesse %s envoyée à la pompe", speed)
                    else:
                        _LOGGER.warning("Erreur HTTP: %s", response.status)
        except aiohttp.ClientError as e:
            _LOGGER.error("Erreur lors de la requête HTTP : %s", e)

        await self._coordinator.async_request_refresh()
