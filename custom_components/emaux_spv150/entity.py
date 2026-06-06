from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PumpCoordinator


class PumpBaseEntity(CoordinatorEntity[PumpCoordinator]):
    """Base entity for Emaux SPV150 pump entities."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping entities under a single device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="Emaux SPV150",
            manufacturer="Emaux",
            model="SPV150",
        )

    @property
    def available(self) -> bool:
        """Return False when the external switch is OFF or the last update failed."""
        return self.coordinator.last_update_success and not self.coordinator.pump_switch_off
