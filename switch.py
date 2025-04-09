import logging

import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([EmauxSPV150Switch(DEFAULT_HOST)], True)


class EmauxSPV150Switch(SwitchEntity):
    def __init__(self, host):
        self._host = host
        self._attr_name = "Emaux SPV150 Pump"
        self._attr_is_on = False
        self._attr_unique_id = "emaux_spv150_pump"

    async def async_turn_on(self, **kwargs):
        await self._send_command(on=True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._send_command(on=False)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _send_command(self, on):
        val = 1 if on else 0
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=OnOff&val={val}&type=set"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    _LOGGER.debug("Sent power command to pump: %s", resp.status)
        except Exception as e:
            _LOGGER.error("Failed to send power command: %s", e)
