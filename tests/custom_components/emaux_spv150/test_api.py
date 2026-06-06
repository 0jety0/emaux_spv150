"""Tests for the low-level pump HTTP client."""

from unittest.mock import MagicMock

import pytest
from aiohttp import ClientError
from homeassistant.exceptions import HomeAssistantError

from custom_components.emaux_spv150.api import PumpAPI


class _FakeResponse:
    """Minimal async-context-manager stand-in for an aiohttp response."""

    def __init__(self, text: str = "", enter_exc: Exception | None = None) -> None:
        self._text = text
        self._enter_exc = enter_exc

    def raise_for_status(self) -> None:
        return None

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> "_FakeResponse":
        if self._enter_exc is not None:
            raise self._enter_exc
        return self

    async def __aexit__(self, *args) -> bool:
        return False


def _session(text: str = "", enter_exc: Exception | None = None) -> MagicMock:
    session = MagicMock()
    session.get = MagicMock(return_value=_FakeResponse(text, enter_exc))
    return session


@pytest.mark.asyncio
async def test_get_status_success():
    api = PumpAPI("192.168.1.50", _session('{"CurrentSpeed": "1500", "RunningStatus": "1"}'))
    result = await api.get_status()
    assert result["CurrentSpeed"] == "1500"


@pytest.mark.asyncio
async def test_get_status_client_error_returns_empty():
    api = PumpAPI("192.168.1.50", _session(enter_exc=ClientError("connection refused")))
    assert await api.get_status() == {}


@pytest.mark.asyncio
async def test_get_status_timeout_returns_empty():
    api = PumpAPI("192.168.1.50", _session(enter_exc=TimeoutError()))
    assert await api.get_status() == {}


@pytest.mark.asyncio
async def test_get_status_invalid_json_returns_empty():
    api = PumpAPI("192.168.1.50", _session("<html>500 error</html>"))
    assert await api.get_status() == {}


@pytest.mark.asyncio
async def test_set_key_success():
    api = PumpAPI("192.168.1.50", _session('{"SetCurrentSpeed": 1800}'))
    assert await api.set_key("SetCurrentSpeed", 1800) == 1800


@pytest.mark.asyncio
async def test_set_key_not_acknowledged_raises():
    api = PumpAPI("192.168.1.50", _session("{}"))
    with pytest.raises(HomeAssistantError, match="did not acknowledge"):
        await api.set_key("SetCurrentSpeed", 1800)


@pytest.mark.asyncio
async def test_set_key_url_is_encoded():
    session = _session('{"Weird&Key": 1}')
    api = PumpAPI("192.168.1.50", session)
    await api.set_key("Weird&Key", 1)
    called_url = session.get.call_args.args[0]
    # The raw "&" must be percent-encoded so it cannot inject extra params.
    assert "Weird&Key" not in called_url
    assert "Weird%26Key" in called_url
