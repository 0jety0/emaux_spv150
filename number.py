# custom_components/emaux_spv150/number.py

from __future__ import annotations

import logging

import aiohttp
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EmauxCoordinator

_LOGGER = logging.getLogger(__name__)

MIN_SPEED = 800
MAX_SPEED = 3400
STEP_SPEED = 100


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    host = entry.data[CONF_HOST]
    coordinator: EmauxCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([EmauxPumpSpeedNumberEntity(host, coordinator)])


class EmauxPumpSpeedNumberEntity(NumberEntity):
    def __init__(self, host: str, coordinator: EmauxCoordinator) -> None:
        self._host = host
        self._coordinator = coordinator

        self._attr_name = "Vitesse pompe Emaux"
        self._attr_unique_id = f"{host}_pump_speed"
        self._attr_native_min_value = MIN_SPEED
        self._attr_native_max_value = MAX_SPEED
        self._attr_native_step = STEP_SPEED
        self._attr_native_unit_of_measurement = "rpm"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:pump"

    @property
    def native_value(self) -> int:
        return int(self._coordinator.data.get("CurrentSpeed", 0))

    async def async_set_native_value(self, value: float) -> None:
        speed = int(value)
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=SetCurrentSpeed&val={speed}&type=set&time=Date.now()"
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
