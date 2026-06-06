import json
import logging
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# The pump's embedded CGI server is slow and sometimes flaky over the LAN, so
# allow a generous default timeout (well under the default 30 s polling interval).
# Both the timeout and the polling interval are user-configurable at runtime.
DEFAULT_TIMEOUT = 5


class PumpAPI:
    """HTTP client for the Emaux SPV150 pump."""

    def __init__(self, host: str, session: ClientSession, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._host = host
        self._session = session
        self._timeout = ClientTimeout(total=timeout)

    def set_timeout(self, seconds: float) -> None:
        """Update the per-request timeout (applied to the next request)."""
        self._timeout = ClientTimeout(total=seconds)

    async def _make_request(self, url: str) -> dict[str, Any]:
        """Perform a GET request and return parsed JSON data.

        Returns an empty dict on any transport or decoding error so the caller
        can treat it as a single "no data" sentinel. The pump IP is never
        included in error logs (only in DEBUG) to avoid leaking LAN topology.
        """
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                response.raise_for_status()
                data = await response.text()
                return json.loads(data)
        except ClientError as err:
            _LOGGER.error("Pump request failed: %s", err)
            _LOGGER.debug("Failing URL: %s", url)
            return {}
        except TimeoutError:
            _LOGGER.error("Pump request timed out after %ss", DEFAULT_TIMEOUT)
            _LOGGER.debug("Timed-out URL: %s", url)
            return {}
        except json.JSONDecodeError as err:
            _LOGGER.error("Pump returned invalid JSON: %s", err)
            _LOGGER.debug("Offending URL: %s", url)
            return {}

    async def get_status(self) -> dict[str, Any]:
        """Fetch the current pump status."""
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time=Date.now()"
        return await self._make_request(url)

    async def set_key(self, key: str, value: int) -> int:
        """Set a supported pump command key to the given value."""
        safe_key = quote(str(key), safe="")
        url = f"http://{self._host}/cgi-bin/EpvCgi?name={safe_key}&val={int(value)}&type=set&time=Date.now()"
        json_data = await self._make_request(url)
        result = json_data.get(key, None)
        if result is None:
            raise HomeAssistantError(f"Pump did not acknowledge command '{key}'")
        return result
