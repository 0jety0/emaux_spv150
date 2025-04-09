import logging
import time
import async_timeout
import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EmauxCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str):
        super().__init__(
            hass,
            _LOGGER,
            name="Emaux SPV150 Coordinator",
            update_interval=None,  # uniquement quand demandé, pas de polling auto
        )
        self.host = host

    async def _async_update_data(self):
        url = f"http://{self.host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time={int(time.time() * 1000)}"
        _LOGGER.debug("Fetching Emaux status from %s", url)

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise UpdateFailed(f"HTTP Error: {response.status}")
                        data = await response.json()

                        _LOGGER.debug("Received data: %s", data)

                        return {
                            "CurrentSpeed": data.get("CurrentSpeed"),
                            "CurrentWatts": data.get("CurrentWatts"),
                            "RunningStatus": data.get("RunningStatus"),
                        }
        except Exception as err:
            raise UpdateFailed(f"Error fetching Emaux data: {err}") from err
