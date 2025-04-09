import logging

import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature, UnitOfPower
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "CurrentSpeed": {"name": "Vitesse actuelle", "unit": "rpm", "icon": "mdi:rotate-right"},
    "CurrentWatts": {"name": "Puissance", "unit": UnitOfPower.WATT, "icon": "mdi:flash"},
    "CurrentTemperuture": {"name": "Température", "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:thermometer"},
    "CurrentGPM": {"name": "Débit", "unit": "GPM", "icon": "mdi:water"},
}


async def async_setup_entry(hass, entry, async_add_entities):
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    entities = [EmauxSensor(host, key, info) for key, info in SENSOR_TYPES.items()]
    async_add_entities(entities, update_before_add=True)


class EmauxSensor(SensorEntity):
    def __init__(self, host, sensor_key, sensor_info):
        self._host = host
        self._sensor_key = sensor_key
        self._attr_name = sensor_info["name"]
        self._attr_native_unit_of_measurement = sensor_info["unit"]
        self._attr_icon = sensor_info["icon"]
        self._attr_unique_id = f"{host}_{sensor_key.lower()}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._value = None

    @property
    def native_value(self):
        return self._value

    async def async_update(self):
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._value = int(data.get(self._sensor_key, 0))
                    else:
                        _LOGGER.warning("Erreur lors de la requête capteur: %s", response.status)
        except Exception as e:
            _LOGGER.error("Exception dans le capteur %s: %s", self._sensor_key, e)
