import asyncio
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 2
CLIENT_TIMEOUT = ClientTimeout(total=DEFAULT_TIMEOUT)


class PumpAPI:
    """HTTP client for the Emaux SPV150 pump."""

    def __init__(self, host: str, session: ClientSession, timeout: ClientTimeout = CLIENT_TIMEOUT) -> None:
        self._host = host
        self._timeout = timeout
        self._session = session

    async def _make_request(self, url: str) -> dict[str, Any]:
        """Perform a GET request and return parsed JSON data."""
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                response.raise_for_status()
                data = await response.text()
                return json.loads(data)
        except ClientError as err:
            _LOGGER.error("Request error %s: %s", url, err)
            return {}
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on request %s", url)
            return {}

    async def get_status(self) -> dict[str, Any]:
        """Fetch the current pump status."""
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time=Date.now()"
        return await self._make_request(url)

    async def set_key(self, key: str, value: int) -> int:
        """Set a supported pump command key to the given value."""
        url = f"http://{self._host}/cgi-bin/EpvCgi?name={key}&val={value}&type=set&time=Date.now()"
        json_data = await self._make_request(url)
        result = json_data.get(key, None)
        if result is None:
            raise HomeAssistantError(f"Pump did not acknowledge command '{key}'")
        return result
