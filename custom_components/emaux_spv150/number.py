import asyncio

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import REVOLUTIONS_PER_MINUTE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COMMAND_SETTLE_DELAY
from .coordinator import PumpConfigEntry, PumpCoordinator
from .entity import PumpBaseEntity
from .utils import camel_to_snake

PARALLEL_UPDATES = 1

NUMBER_ENTITY_CONFIG = [
    {
        "name": "CurrentSpeed",
        "translation_key": "current_speed",
        "set_key": "SetCurrentSpeed",
        "min_val": 800,
        "max_val": 3400,
        "step": 10,
        "unit": REVOLUTIONS_PER_MINUTE,
        "icon": "mdi:speedometer",
        "mode": NumberMode.SLIDER,
    },
    {
        "name": "SpeedSelected",
        "translation_key": "speed_selected",
        "set_key": "SetSpeedSelected",
        "min_val": 1,
        "max_val": 3,
        "step": 1,
        "unit": None,
        "icon": "mdi:numeric",
        "mode": NumberMode.SLIDER,
    },
    {
        "name": "Setpoint",
        "translation_key": "setpoint",
        "set_key": None,
        "min_val": -5000,
        "max_val": 5000,
        "step": 10,
        "unit": UnitOfPower.WATT,
        "icon": "mdi:target",
        "mode": NumberMode.BOX,
    },
    {
        "name": "DeadBandLower",
        "translation_key": "dead_band_lower",
        "set_key": None,
        "min_val": -5000,
        "max_val": 5000,
        "step": 10,
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-power",
        "mode": NumberMode.BOX,
    },
    {
        "name": "DeadBandUpper",
        "translation_key": "dead_band_upper",
        "set_key": None,
        "min_val": -5000,
        "max_val": 5000,
        "step": 10,
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower",
        "mode": NumberMode.BOX,
    },
    {
        "name": "StepUp",
        "translation_key": "step_up",
        "set_key": None,
        "min_val": 10,
        "max_val": 1000,
        "step": 10,
        "unit": REVOLUTIONS_PER_MINUTE,
        "icon": "mdi:chevron-up-circle",
        "mode": NumberMode.BOX,
    },
    {
        "name": "StepDown",
        "translation_key": "step_down",
        "set_key": None,
        "min_val": 10,
        "max_val": 500,
        "step": 10,
        "unit": REVOLUTIONS_PER_MINUTE,
        "icon": "mdi:chevron-down-circle",
        "mode": NumberMode.BOX,
    },
    {
        "name": "RpmMinSolar",
        "translation_key": "rpm_min_solar",
        "set_key": None,
        "min_val": 800,
        "max_val": 3400,
        "step": 10,
        "unit": REVOLUTIONS_PER_MINUTE,
        "icon": "mdi:speedometer-slow",
        "mode": NumberMode.BOX,
    },
    {
        "name": "RpmMaxSolar",
        "translation_key": "rpm_max_solar",
        "set_key": None,
        "min_val": 800,
        "max_val": 3400,
        "step": 10,
        "unit": REVOLUTIONS_PER_MINUTE,
        "icon": "mdi:speedometer",
        "mode": NumberMode.BOX,
    },
]

_LOCAL_GETTERS: dict = {
    "Setpoint": lambda c: c.setpoint,
    "DeadBandLower": lambda c: c.dead_band_lower,
    "DeadBandUpper": lambda c: c.dead_band_upper,
    "StepUp": lambda c: float(c.step_up),
    "StepDown": lambda c: float(c.step_down),
    "RpmMinSolar": lambda c: float(c.rpm_min_solar),
    "RpmMaxSolar": lambda c: float(c.rpm_max_solar),
}

_LOCAL_SETTERS: dict = {
    "Setpoint": lambda c, v: c.set_setpoint(float(v)),
    "DeadBandLower": lambda c, v: c.set_dead_band_lower(float(v)),
    "DeadBandUpper": lambda c, v: c.set_dead_band_upper(float(v)),
    "StepUp": lambda c, v: c.set_step_up(int(v)),
    "StepDown": lambda c, v: c.set_step_down(int(v)),
    "RpmMinSolar": lambda c, v: c.set_rpm_min_solar(int(v)),
    "RpmMaxSolar": lambda c, v: c.set_rpm_max_solar(int(v)),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: PumpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Emaux SPV150 number entities."""
    coordinator: PumpCoordinator = entry.runtime_data
    async_add_entities(
        [PumpNumber(coordinator, config) for config in NUMBER_ENTITY_CONFIG],
        update_before_add=True,
    )


class PumpNumber(PumpBaseEntity, NumberEntity):
    """Number entity for a controllable pump parameter."""

    def __init__(self, coordinator: PumpCoordinator, config: dict) -> None:
        super().__init__(coordinator)
        self._key = config["name"]
        self._set_key = config["set_key"]
        self._attr_translation_key = config["translation_key"]
        self._attr_unique_id = "spv150_" + camel_to_snake(self._key)
        self._attr_native_min_value = config["min_val"]
        self._attr_native_max_value = config["max_val"]
        self._attr_native_step = config["step"]
        self._attr_native_unit_of_measurement = config["unit"]
        self._attr_icon = config["icon"]
        self._attr_mode = config["mode"]

    @property
    def native_value(self) -> float | None:
        """Return the current value from coordinator data or coordinator attributes."""
        if self._set_key is None:
            getter = _LOCAL_GETTERS.get(self._key)
            return getter(self.coordinator) if getter else None
        raw = self.coordinator.data.get(self._key)
        if raw is None:
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Send the new value to the pump or update coordinator attributes."""
        if self._set_key is None:
            setter = _LOCAL_SETTERS.get(self._key)
            if setter:
                setter(self.coordinator, value)
            self.async_write_ha_state()
            return

        await self.coordinator.async_set_pump_key(self._set_key, int(value))
        await asyncio.sleep(COMMAND_SETTLE_DELAY)
        await self.coordinator.async_request_refresh()
