import json
import logging
import time
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EmauxCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Emaux SPV150 Coordinator",
            update_interval=timedelta(seconds=10),
            update_method=self._async_update_data,
        )
        self.host = host

    async def _async_update_data(self):
        """Fetch data from Emaux SPV150."""
        url = f"http://{self.host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time={int(time.time() * 1000)}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        _LOGGER.debug(f"Content-Type: {content_type}")
                        if "json" in content_type:
                            return await response.json()
                        else:
                            html_content = await response.text()
                            try:
                                data = json.loads(html_content)
                                return data
                            except json.JSONDecodeError:
                                _LOGGER.error("JSON decode error")
                                raise UpdateFailed("Failed to decode JSON")
                    else:
                        _LOGGER.warning("Invalid API response: %s", response.status)
                        raise UpdateFailed(f"HTTP error: {response.status}")
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}")
