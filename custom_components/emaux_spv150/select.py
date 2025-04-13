from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

PARALLEL_UPDATES = 1

CONTROL_MODES = ["off", "manual", "solar"]


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Emaux SPV150 select entities."""
    async_add_entities([ControlModeSelect(entry.runtime_data)], update_before_add=True)


class ControlModeSelect(PumpBaseEntity, SelectEntity):
    """Select entity to choose the pump control mode."""

    _attr_translation_key = "control_mode"
    _attr_options = CONTROL_MODES
    _attr_icon = "mdi:tune"

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "spv150_control_mode"

    @property
    def current_option(self) -> str:
        return self.coordinator.control_mode

    async def async_select_option(self, option: str) -> None:
        """Change the control mode and persist it."""
        self.coordinator.set_control_mode(option)
        self.async_write_ha_state()
