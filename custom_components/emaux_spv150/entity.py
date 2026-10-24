from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PumpCoordinator


class PumpBaseEntity(CoordinatorEntity[PumpCoordinator]):
    """Base entity for Emaux SPV150 pump entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Emaux SPV150",
            manufacturer="Emaux",
            model="SPV150",
        )

    @property
    def available(self) -> bool:
        """Return False when the pump has no power or the last update failed."""
        return self.coordinator.last_update_success and not self.coordinator.pump_powered_off
