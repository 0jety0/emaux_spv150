import json
import logging
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

# The pump's embedded CGI server is slow and sometimes flaky over the LAN, so
# allow a generous default timeout (well under the default 30 s polling interval).
# Both the timeout and the polling interval are user-configurable at runtime.
DEFAULT_TIMEOUT = 5


class PumpError(Exception):
    """The pump could not be reached, gave an unusable answer or refused a command."""


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
        """Perform a GET request and return the parsed JSON object.

        Raises PumpError on any transport or decoding error. Logging is left to
        the caller (the coordinator logs an outage once, not on every poll). The
        pump IP is never put in the error, only in DEBUG, to avoid leaking LAN topology.
        """
        _LOGGER.debug("Requesting %s", url)
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                response.raise_for_status()
                payload = json.loads(await response.text())
        except ClientError as err:
            raise PumpError(f"Pump request failed: {err}") from err
        except TimeoutError as err:
            raise PumpError(f"Pump request timed out after {self._timeout.total:g}s") from err
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            raise PumpError(f"Pump returned an unreadable response: {err}") from err
        if not isinstance(payload, dict):
            raise PumpError(f"Pump returned JSON that is not an object: {type(payload).__name__}")
        return payload

    async def get_status(self) -> dict[str, Any]:
        """Fetch the current pump status."""
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time=Date.now()"
        status = await self._make_request(url)
        if not status:
            raise PumpError("Pump returned an empty status")
        return status

    async def set_key(self, key: str, value: int) -> int:
        """Set a supported pump command key to the given value."""
        safe_key = quote(str(key), safe="")
        url = f"http://{self._host}/cgi-bin/EpvCgi?name={safe_key}&val={int(value)}&type=set&time=Date.now()"
        json_data = await self._make_request(url)
        result = json_data.get(key)
        if result is None:
            raise PumpError(f"Pump did not acknowledge command '{key}'")
        return result
