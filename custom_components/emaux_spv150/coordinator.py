import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PumpAPI
from .const import (
    CONF_DEAD_BAND_LOWER,
    CONF_DEAD_BAND_UPPER,
    CONF_GRID_POWER_ENTITY,
    CONF_POLL_INTERVAL,
    CONF_PRIMING_TIME,
    CONF_RPM_MAX_SOLAR,
    CONF_RPM_MIN_SOLAR,
    CONF_SETPOINT,
    CONF_SPEED_CHANGE_INTERVAL,
    CONF_STEP_DOWN,
    CONF_STEP_UP,
    CONF_SWITCH_ENTITY,
    DEFAULT_DEAD_BAND_LOWER,
    DEFAULT_DEAD_BAND_UPPER,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PRIMING_TIME,
    DEFAULT_RPM_MAX_SOLAR,
    DEFAULT_RPM_MIN_SOLAR,
    DEFAULT_SETPOINT,
    DEFAULT_SPEED_CHANGE_INTERVAL,
    DEFAULT_STEP_DOWN,
    DEFAULT_STEP_UP,
)

_LOGGER = logging.getLogger(__name__)

type PumpConfigEntry = ConfigEntry["PumpCoordinator"]


class PumpCoordinator(DataUpdateCoordinator):
    """Coordinator for polling and controlling the Emaux SPV150 pump."""

    config_entry: PumpConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PumpConfigEntry) -> None:
        opts = entry.options
        data = entry.data

        host = opts.get(CONF_HOST) or data[CONF_HOST]
        switch_entity_id = opts[CONF_SWITCH_ENTITY] if CONF_SWITCH_ENTITY in opts else data.get(CONF_SWITCH_ENTITY)
        poll_interval = int(opts.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

        self.api_pump = PumpAPI(host, async_get_clientsession(hass))
        self.switch_entity_id: str | None = switch_entity_id or None

        # Control mode: "off" | "manual" | "solar"
        self.control_mode: str = opts.get("control_mode", "manual")

        # Solar parameters
        self.grid_power_entity: str = opts[CONF_GRID_POWER_ENTITY] if CONF_GRID_POWER_ENTITY in opts else data.get(CONF_GRID_POWER_ENTITY, "")
        self.setpoint: float = float(opts.get(CONF_SETPOINT, DEFAULT_SETPOINT))
        self.dead_band_lower: float = float(opts.get(CONF_DEAD_BAND_LOWER, DEFAULT_DEAD_BAND_LOWER))
        self.dead_band_upper: float = float(opts.get(CONF_DEAD_BAND_UPPER, DEFAULT_DEAD_BAND_UPPER))
        self.step_up: int = int(opts.get(CONF_STEP_UP, DEFAULT_STEP_UP))
        self.step_down: int = int(opts.get(CONF_STEP_DOWN, DEFAULT_STEP_DOWN))
        self.rpm_min_solar: int = int(opts.get(CONF_RPM_MIN_SOLAR, DEFAULT_RPM_MIN_SOLAR))
        self.rpm_max_solar: int = int(opts.get(CONF_RPM_MAX_SOLAR, DEFAULT_RPM_MAX_SOLAR))
        self.priming_time: int = int(opts.get(CONF_PRIMING_TIME, DEFAULT_PRIMING_TIME))
        self.speed_change_interval: int = int(opts.get(CONF_SPEED_CHANGE_INTERVAL, DEFAULT_SPEED_CHANGE_INTERVAL))

        # Speed change throttle
        self._last_speed_change_time: datetime | None = None

        # Startup priming tracking (True = no priming needed until switch OFF→ON)
        self._pump_started_at: datetime | None = None
        self._priming_done: bool = True
        self._prev_running: bool = False
        self._prev_switch_on: bool = True

        # Energy tracking
        self._energy_kwh: float = 0.0
        self._last_energy_update: datetime | None = None

        # Uptime tracking
        self._uptime_start: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="PumpCoordinator",
            update_interval=timedelta(seconds=poll_interval),
            config_entry=entry,
        )

    # -------------------------------------------------------------------------
    # Option persistence
    # -------------------------------------------------------------------------

    def _update_option(self, key: str, value: Any) -> None:
        """Persist a single option to entry.options without triggering a reload."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, key: value},
        )

    def set_control_mode(self, mode: str) -> None:
        self.control_mode = mode
        self._update_option("control_mode", mode)

    def set_setpoint(self, value: float) -> None:
        self.setpoint = value
        self._update_option(CONF_SETPOINT, value)

    def set_dead_band_lower(self, value: float) -> None:
        self.dead_band_lower = value
        self._update_option(CONF_DEAD_BAND_LOWER, value)

    def set_dead_band_upper(self, value: float) -> None:
        self.dead_band_upper = value
        self._update_option(CONF_DEAD_BAND_UPPER, value)

    def set_step_up(self, value: int) -> None:
        self.step_up = value
        self._update_option(CONF_STEP_UP, value)

    def set_step_down(self, value: int) -> None:
        self.step_down = value
        self._update_option(CONF_STEP_DOWN, value)

    def set_rpm_min_solar(self, value: int) -> None:
        self.rpm_min_solar = value
        self._update_option(CONF_RPM_MIN_SOLAR, value)

    def set_rpm_max_solar(self, value: int) -> None:
        self.rpm_max_solar = value
        self._update_option(CONF_RPM_MAX_SOLAR, value)

    # -------------------------------------------------------------------------
    # Pump command
    # -------------------------------------------------------------------------

    async def async_set_pump_key(self, key: str, value: int) -> Any:
        """Send a command to the pump, respecting the speed-change throttle."""
        if key == "SetCurrentSpeed" and self.speed_change_interval > 0:
            now = dt_util.utcnow()
            if self._last_speed_change_time is not None:
                elapsed = (now - self._last_speed_change_time).total_seconds()
                if elapsed < self.speed_change_interval:
                    _LOGGER.debug(
                        "Speed change throttled: %.0fs remaining",
                        self.speed_change_interval - elapsed,
                    )
                    return None
            self._last_speed_change_time = now
        return await self.api_pump.set_key(key, value)

    # -------------------------------------------------------------------------
    # Monitoring helpers
    # -------------------------------------------------------------------------

    @property
    def energy_kwh(self) -> float:
        """Return cumulated energy in kWh."""
        return round(self._energy_kwh, 4)

    def restore_energy(self, value: float) -> None:
        """Restore persisted energy value on HA startup."""
        self._energy_kwh = value

    @property
    def uptime_hours(self) -> float | None:
        """Return hours since the pump started running, or None if stopped."""
        if self._uptime_start is None:
            return None
        return round((dt_util.utcnow() - self._uptime_start).total_seconds() / 3600, 2)

    def _update_energy(self, watts: float) -> None:
        """Accumulate energy based on elapsed time and current power."""
        now = dt_util.utcnow()
        if self._last_energy_update is not None:
            elapsed_hours = (now - self._last_energy_update).total_seconds() / 3600
            self._energy_kwh += (watts / 1000) * elapsed_hours
        self._last_energy_update = now

    def _update_uptime(self, running: bool) -> None:
        """Track pump uptime start time."""
        if running and self._uptime_start is None:
            self._uptime_start = dt_util.utcnow()
        elif not running:
            self._uptime_start = None

    # -------------------------------------------------------------------------
    # Solar regulation — P-controller with dead band
    # -------------------------------------------------------------------------

    async def _apply_solar_regulation(self, current_speed: int) -> None:
        """
        P-controller centred on setpoint with an explicit dead band.

        Dead band: [dead_band_lower, dead_band_upper]  (absolute grid power values)
        Setpoint:  target grid power used as error reference

        error = |grid_power - setpoint|
        step  = min(step_max, max(10, int(error)))   — proportional, capped at step_up/down
        """
        if not self.grid_power_entity:
            return

        grid_state = self.hass.states.get(self.grid_power_entity)
        if grid_state is None:
            _LOGGER.warning("Grid power entity '%s' not found", self.grid_power_entity)
            return
        try:
            grid_power = float(grid_state.state)
        except (ValueError, TypeError):
            return

        if grid_state.last_changed is not None:
            stale_seconds = (dt_util.utcnow() - grid_state.last_changed).total_seconds()
            if stale_seconds > 60:
                _LOGGER.warning(
                    "Grid power entity '%s' unchanged for %.0fs — skipping solar regulation",
                    self.grid_power_entity,
                    stale_seconds,
                )
                return

        if grid_power < self.dead_band_lower:
            error = self.setpoint - grid_power
            step = min(self.step_up, max(10, int(error)))
            new_speed = current_speed + step
        elif grid_power > self.dead_band_upper:
            error = grid_power - self.setpoint
            step = min(self.step_down, max(10, int(error)))
            new_speed = current_speed - step
        else:
            return

        new_speed = max(self.rpm_min_solar, min(self.rpm_max_solar, new_speed))
        new_speed = round(new_speed / 10) * 10

        if new_speed != current_speed:
            _LOGGER.debug(
                "Solar regulation: grid=%.0fW setpoint=%.0fW band=[%.0f, %.0f] → speed %d→%d rpm",
                grid_power, self.setpoint, self.dead_band_lower, self.dead_band_upper,
                current_speed, new_speed,
            )
            await self.async_set_pump_key("SetCurrentSpeed", new_speed)

    # -------------------------------------------------------------------------
    # DataUpdateCoordinator hooks
    # -------------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Verify pump is reachable before entities are set up."""
        if not await self.api_pump.get_status():
            raise ConfigEntryNotReady("Cannot reach pump during setup")

    async def _async_update_data(self) -> dict:
        """Fetch latest pump data and apply solar regulation if active."""
        switch_on = True
        if self.switch_entity_id:
            switch_state = self.hass.states.get(self.switch_entity_id)
            switch_on = not (switch_state and switch_state.state.lower() == "off")
            if not switch_on:
                self._update_uptime(False)
                self._prev_running = False
                self._pump_started_at = None
                self._priming_done = True
                self._last_speed_change_time = None
                self._prev_switch_on = False
                return {
                    "CurrentSpeed": "0",
                    "CurrentWatts": "0",
                    "RunningStatus": "0",
                    "SpeedSelected": "0",
                    "CurrentGPM": "0",
                }

        data = await self.api_pump.get_status()
        if not data:
            raise UpdateFailed("Pump did not respond or returned empty data")

        running = data.get("RunningStatus", "0") == "1"
        self._update_uptime(running)

        try:
            watts = float(data.get("CurrentWatts", 0)) if running else 0.0
            self._update_energy(watts)
        except (ValueError, TypeError):
            pass

        # Priming: only triggered by physical switch OFF→ON
        if self.switch_entity_id:
            if switch_on and not self._prev_switch_on:
                self._pump_started_at = dt_util.utcnow()
                self._priming_done = False
                _LOGGER.debug("Switch turned ON: priming window of %ds begins", self.priming_time)
            self._prev_switch_on = switch_on
        self._prev_running = running

        # After priming window elapses, unlock solar regulation
        if (
            running
            and self.control_mode == "solar"
            and not self._priming_done
            and self._pump_started_at is not None
        ):
            elapsed = (dt_util.utcnow() - self._pump_started_at).total_seconds()
            if elapsed >= self.priming_time:
                _LOGGER.debug("Priming complete after %.0fs — handing off to solar regulation", elapsed)
                self._priming_done = True

        if running and self.control_mode == "solar" and self._priming_done:
            try:
                await self._apply_solar_regulation(int(float(data.get("CurrentSpeed", 0))))
            except (ValueError, TypeError):
                pass

        return data
