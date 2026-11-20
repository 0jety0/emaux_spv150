from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PumpCommand
from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the Emaux SPV150 switch entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    async_add_entities([RunStopSwitchEntity(coordinator)])


class RunStopSwitchEntity(PumpBaseEntity, SwitchEntity):
    """Switch entity to control the pump run/stop state."""

    _attr_translation_key = "running_status"

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "spv150_running_status"

    @property
    @override
    def is_on(self) -> bool:
        """Return True when the pump is running."""
        return self.coordinator.data.running

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the pump."""
        await self.coordinator.async_set_pump_key(PumpCommand.RUN_STOP, 1)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the pump."""
        await self.coordinator.async_set_pump_key(PumpCommand.RUN_STOP, 2)
        await self.coordinator.async_request_refresh()
