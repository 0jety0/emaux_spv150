import logging

import aiohttp
from homeassistant.components.number import NumberEntity

from .const import DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([EmauxSPV150SpeedNumber(DEFAULT_HOST)], True)


class EmauxSPV150SpeedNumber(NumberEntity):
    def __init__(self, host):
        self._host = host
        self._attr_name = "Emaux SPV150 Speed"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 3
        self._attr_native_step = 1
        self._attr_native_value = 1
        self._attr_unique_id = "emaux_spv150_speed"

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=SetSpeedSelected&val={int(value)}&type=set"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    _LOGGER.debug("Sent speed command to pump: %s", resp.status)
        except Exception as e:
            _LOGGER.error("Failed to set pump speed: %s", e)
        self.async_write_ha_state()
