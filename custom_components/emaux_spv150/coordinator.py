import logging
from datetime import timedelta

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import PumpAPI

_LOGGER = logging.getLogger(__name__)


class PumpCoordinator(DataUpdateCoordinator):
    """Coordinator pour récupérer les données et contrôler la pompe Emaux SPV150."""

    def __init__(
        self,
        hass,
        host: str,
        update_interval: timedelta,
        switch_entity_id: str | None = None,
    ) -> None:
        """Initialisation du coordinator avec l'API de la pompe."""
        self.api_pump = PumpAPI(host, async_get_clientsession(hass))
        self.switch_entity_id = switch_entity_id
        super().__init__(
            hass, _LOGGER, name="PumpCoordinator", update_interval=update_interval
        )

    async def _async_setup(self) -> None:
        """Effectue l'initialisation nécessaire avant la mise à jour."""
        self.prereq_data = await self.api_pump.get_status()

    async def _async_update_data(self) -> dict:
        """Récupère les dernières données de la pompe si active."""
        if self.switch_entity_id:
            switch_state = self.hass.states.get(self.switch_entity_id)
            if switch_state and switch_state.state.lower() == "off":
                return {
                    "CurrentSpeed": "0",
                    "CurrentWatts": "0",
                    "RunningStatus": "0",
                    "SpeedSelected": "0",
                    "CurrentGPM": "0",
                }
        return await self.api_pump.get_status()
