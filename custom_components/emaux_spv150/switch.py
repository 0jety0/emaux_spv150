import asyncio

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COMMAND_SETTLE_DELAY
from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Emaux SPV150 switch entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    async_add_entities([RunStopSwitchEntity(coordinator)], update_before_add=True)


class RunStopSwitchEntity(PumpBaseEntity, SwitchEntity):
    """Switch entity to control the pump run/stop state."""

    _attr_translation_key = "running_status"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._set_key = "RunStop"
        self._attr_unique_id = "spv150_running_status"

    @property
    def is_on(self) -> bool:
        """Return True when the pump is running."""
        return self.coordinator.data.running

    async def async_turn_on(self, **kwargs) -> None:
        """Start the pump."""
        await self.coordinator.async_set_pump_key(self._set_key, 1)
        await asyncio.sleep(COMMAND_SETTLE_DELAY)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the pump."""
        await self.coordinator.async_set_pump_key(self._set_key, 2)
        await asyncio.sleep(COMMAND_SETTLE_DELAY)
        await self.coordinator.async_request_refresh()
