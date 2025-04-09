from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import EntityCategory
import requests
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_SPEED = 800
MAX_SPEED = 3400
STEP_SPEED = 100


async def async_setup_entry(hass, config_entry, async_add_entities):
    host = config_entry.data[CONF_HOST]
    entity = EmauxPumpSpeedNumberEntity(host)
    async_add_entities([entity])


class EmauxPumpSpeedNumberEntity(NumberEntity):
    def __init__(self, host):
        self._attr_name = "Vitesse pompe Emaux"
        self._attr_unique_id = f"{host}_pump_speed"
        self._attr_native_min_value = MIN_SPEED
        self._attr_native_max_value = MAX_SPEED
        self._attr_native_step = STEP_SPEED
        self._attr_native_unit_of_measurement = "rpm"
        self._attr_entity_category = EntityCategory.CONFIG
        self._host = host
        self._value = 2350

    @property
    def native_value(self):
        return self._value

    def set_speed(self, speed: int):
        """Envoie la commande à la pompe via HTTP GET."""
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=SetCurrentSpeed&val={speed}&type=set&time=Date.now()"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                _LOGGER.info("Commande envoyée à la pompe : %s", url)
            else:
                _LOGGER.warning("Réponse invalide de la pompe: %s", response.status_code)
        except requests.RequestException as e:
            _LOGGER.error("Erreur lors de la requête HTTP : %s", e)

    async def async_set_native_value(self, value: float) -> None:
        self._value = int(value)
        self.set_speed(self._value)
