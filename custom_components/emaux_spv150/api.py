import asyncio
import json
import logging

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 2
CLIENT_TIMEOUT = ClientTimeout(total=DEFAULT_TIMEOUT)


class PumpAPI:
    """Client API pour la pompe Emaux SPV150."""

    def __init__(
        self, host: str, session: ClientSession | None = None, timeout=CLIENT_TIMEOUT
    ) -> None:
        self._host = host
        self._session = session or ClientSession(timeout=self._timeout)
        self._timeout = timeout

    async def _make_request(self, url: str) -> dict:
        """Effectue une requête GET et retourne les données JSON."""
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                data = await response.text()
                json_data = json.loads(data)
                return json_data
        except ClientError as err:
            _LOGGER.error("Request error %s: %s", url, err)
            return {}
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout lors de la requête %s", url)
            return {}

    async def get_status(self) -> dict:
        """Récupère le statut de la pompe."""
        url = f"http://{self._host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time=Date.now()"
        json_data = await self._make_request(url)
        return json_data

    async def set_key(self, key: str, value: int) -> int:
        """Définit une valeur pour une commande supportée de la pompe."""

        url = f"http://{self._host}/cgi-bin/EpvCgi?name={key}&val={value}&type=set&time=Date.now()"
        json_data = await self._make_request(url)
        value = json_data.get(key, None)
        if key is None:
            raise Exception("Failed to get key")
        return value
