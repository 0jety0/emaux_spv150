from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CONTROL_MODE, ControlMode
from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up Emaux SPV150 select entities."""
    async_add_entities([ControlModeSelect(entry.runtime_data)])


class ControlModeSelect(PumpBaseEntity, SelectEntity):
    """Select entity to choose the pump control mode."""

    _attr_translation_key = "control_mode"

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "spv150_control_mode"
        self._attr_options = [mode.value for mode in ControlMode]

    @property
    @override
    def available(self) -> bool:
        """Always available: the mode is a local setting, usable while the pump is off."""
        return True

    @property
    @override
    def current_option(self) -> str:
        return self.coordinator.control_mode

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the control mode and persist it."""
        self.coordinator.set_option(CONF_CONTROL_MODE, option)
        self.async_write_ha_state()
