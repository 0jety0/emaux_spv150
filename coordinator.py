# custom_components/emaux_spv150/coordinator.py

import json
import logging
import time
from datetime import timedelta

import aiohttp
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
            update_interval=timedelta(seconds=1),
        )
        self.host = host

    async def _async_update_data(self):
        """Mise à jour des données depuis l'Emaux"""
        url = f"http://{self.host}/cgi-bin/EpvCgi?name=AllRd&val=0&type=get&time={int(time.time() * 1000)}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    content_type = response.headers.get("Content-Type", "")
                    _LOGGER.info(f"Content-Type: {content_type}")
                    if response.status == 200:
                        if "json" in content_type:
                            return await response.json()
                        else:
                            html_content = await response.text()
                            try:
                                data = json.loads(html_content)
                                return data
                            except json.JSONDecodeError:
                                _LOGGER.error("Erreur de décodage JSON")
                                raise ValueError(
                                    f"Erreur de contenu, impossible de décoder le JSON : {content_type}"
                                )
                    else:
                        _LOGGER.warning(
                            "Réponse invalide de l'API: %s", response.status
                        )
                        raise Exception(f"Erreur HTTP: {response.status}")
        except Exception as err:
            _LOGGER.error("Erreur lors de la récupération des données: %s", err)
            raise
