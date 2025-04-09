# custom_components/emaux_spv150/coordinator.py

import logging
import time

import aiohttp
import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EmauxCoordinator(DataUpdateCoordinator[dict[str, str]]):
    def __init__(self, hass: HomeAssistant, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Emaux SPV150 Coordinator",
            update_interval=None,
        )
        self.host = host

    async def _async_update_data(self) -> dict[str, str]:
        url = f"http://{self.host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time={int(time.time() * 1000)}"
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise UpdateFailed(f"HTTP error: {response.status}")

                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" not in content_type:
                            raise UpdateFailed(f"Unexpected Content-Type: {content_type}")

                        return await response.json()

        except Exception as err:
            raise UpdateFailed(f"Error fetching Emaux data: {err}") from err
