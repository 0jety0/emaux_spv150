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
    CONF_REQUEST_TIMEOUT,
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
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RPM_MAX_SOLAR,
    DEFAULT_RPM_MIN_SOLAR,
    DEFAULT_SETPOINT,
    DEFAULT_SPEED_CHANGE_INTERVAL,
    DEFAULT_STEP_DOWN,
    DEFAULT_STEP_UP,
    GRID_POWER_STALENESS_SECONDS,
)
from .models import PumpStatus, to_float
from .solar import SolarControllerConfig, SolarRegulator

_LOGGER = logging.getLogger(__name__)

type PumpConfigEntry = ConfigEntry["PumpCoordinator"]


class PumpCoordinator(DataUpdateCoordinator[PumpStatus]):
    """Coordinator for polling and controlling the Emaux SPV150 pump."""

    config_entry: PumpConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PumpConfigEntry) -> None:
        opts = entry.options
        data = entry.data

        host = opts.get(CONF_HOST) or data[CONF_HOST]
        switch_entity_id = opts[CONF_SWITCH_ENTITY] if CONF_SWITCH_ENTITY in opts else data.get(CONF_SWITCH_ENTITY)
        poll_interval = int(opts.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

        # Connection-relevant settings: a change in any of these requires a full
        # reload (handled by the update listener in __init__.py).
        self.host: str = host
        self.request_timeout: int = int(opts.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT))
        self.api_pump = PumpAPI(host, async_get_clientsession(hass), self.request_timeout)
        self.switch_entity_id: str | None = switch_entity_id or None

        # Control mode: "off" | "manual" | "solar"
        self.control_mode: str = opts.get("control_mode", "manual")

        # Solar parameters
        self.grid_power_entity: str = (
            opts[CONF_GRID_POWER_ENTITY] if CONF_GRID_POWER_ENTITY in opts else data.get(CONF_GRID_POWER_ENTITY, "")
        )
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

        # True when the external switch entity is explicitly OFF
        self.pump_switch_off: bool = False

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
        """Persist a single option to entry.options.

        The value is already applied live on this coordinator. The update
        listener (see __init__.py) compares connection settings and only
        reloads when those change, so this local persist does not reload.
        """
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, key: value},
        )

    def connection_settings_changed(self, entry: PumpConfigEntry) -> bool:
        """Return True if host / switch / grid entity differ from the live values.

        These are the only settings that require a full reload; everything else
        is applied live via apply_options().
        """
        opts, data = entry.options, entry.data
        new_host = opts.get(CONF_HOST) or data[CONF_HOST]
        new_switch = (opts[CONF_SWITCH_ENTITY] if CONF_SWITCH_ENTITY in opts else data.get(CONF_SWITCH_ENTITY)) or None
        new_grid = (
            opts[CONF_GRID_POWER_ENTITY] if CONF_GRID_POWER_ENTITY in opts else data.get(CONF_GRID_POWER_ENTITY, "")
        ) or ""
        return new_host != self.host or new_switch != self.switch_entity_id or new_grid != self.grid_power_entity

    def apply_options(self, entry: PumpConfigEntry) -> None:
        """Re-read regulation parameters from the entry options into live state.

        Called by the update listener when no connection setting changed, so an
        options-flow edit applies without a reload (and a number-entity write is
        simply re-applied idempotently).
        """
        opts = entry.options
        self.control_mode = opts.get("control_mode", self.control_mode)
        self.setpoint = float(opts.get(CONF_SETPOINT, self.setpoint))
        self.dead_band_lower = float(opts.get(CONF_DEAD_BAND_LOWER, self.dead_band_lower))
        self.dead_band_upper = float(opts.get(CONF_DEAD_BAND_UPPER, self.dead_band_upper))
        self.step_up = int(opts.get(CONF_STEP_UP, self.step_up))
        self.step_down = int(opts.get(CONF_STEP_DOWN, self.step_down))
        self.rpm_min_solar = int(opts.get(CONF_RPM_MIN_SOLAR, self.rpm_min_solar))
        self.rpm_max_solar = int(opts.get(CONF_RPM_MAX_SOLAR, self.rpm_max_solar))
        self.priming_time = int(opts.get(CONF_PRIMING_TIME, self.priming_time))
        self.speed_change_interval = int(opts.get(CONF_SPEED_CHANGE_INTERVAL, self.speed_change_interval))
        poll = int(opts.get(CONF_POLL_INTERVAL, int(self.update_interval.total_seconds())))
        self.update_interval = timedelta(seconds=poll)
        self.request_timeout = int(opts.get(CONF_REQUEST_TIMEOUT, self.request_timeout))
        self.api_pump.set_timeout(self.request_timeout)

    def set_control_mode(self, mode: str) -> None:
        self.control_mode = mode
        self._update_option("control_mode", mode)

    def set_setpoint(self, value: float) -> None:
        self.setpoint = value
        self._update_option(CONF_SETPOINT, value)

    def set_dead_band_lower(self, value: float) -> None:
        # Keep the invariant lower <= upper so the P-controller dead band stays valid.
        if value > self.dead_band_upper:
            _LOGGER.warning("dead_band_lower (%s) capped to dead_band_upper (%s)", value, self.dead_band_upper)
            value = self.dead_band_upper
        self.dead_band_lower = value
        self._update_option(CONF_DEAD_BAND_LOWER, value)

    def set_dead_band_upper(self, value: float) -> None:
        if value < self.dead_band_lower:
            _LOGGER.warning("dead_band_upper (%s) raised to dead_band_lower (%s)", value, self.dead_band_lower)
            value = self.dead_band_lower
        self.dead_band_upper = value
        self._update_option(CONF_DEAD_BAND_UPPER, value)

    def set_step_up(self, value: int) -> None:
        self.step_up = value
        self._update_option(CONF_STEP_UP, value)

    def set_step_down(self, value: int) -> None:
        self.step_down = value
        self._update_option(CONF_STEP_DOWN, value)

    def set_rpm_min_solar(self, value: int) -> None:
        # Keep the invariant rpm_min <= rpm_max so the P-controller stays valid.
        if value > self.rpm_max_solar:
            _LOGGER.warning("rpm_min_solar (%d) capped to rpm_max_solar (%d)", value, self.rpm_max_solar)
            value = self.rpm_max_solar
        self.rpm_min_solar = value
        self._update_option(CONF_RPM_MIN_SOLAR, value)

    def set_rpm_max_solar(self, value: int) -> None:
        if value < self.rpm_min_solar:
            _LOGGER.warning("rpm_max_solar (%d) raised to rpm_min_solar (%d)", value, self.rpm_min_solar)
            value = self.rpm_min_solar
        self.rpm_max_solar = value
        self._update_option(CONF_RPM_MAX_SOLAR, value)

    def set_poll_interval(self, value: int) -> None:
        self.update_interval = timedelta(seconds=value)
        self._update_option(CONF_POLL_INTERVAL, value)

    def set_request_timeout(self, value: int) -> None:
        self.request_timeout = value
        self.api_pump.set_timeout(value)
        self._update_option(CONF_REQUEST_TIMEOUT, value)

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

    def _solar_config(self) -> SolarControllerConfig:
        """Build the immutable controller config from the live parameters."""
        return SolarControllerConfig(
            setpoint=self.setpoint,
            dead_band_lower=self.dead_band_lower,
            dead_band_upper=self.dead_band_upper,
            step_up=self.step_up,
            step_down=self.step_down,
            rpm_min_solar=self.rpm_min_solar,
            rpm_max_solar=self.rpm_max_solar,
        )

    async def _apply_solar_regulation(self, current_speed: int) -> None:
        """Read the grid-power entity and apply one P-controller step if needed."""
        if not self.grid_power_entity:
            return

        grid_state = self.hass.states.get(self.grid_power_entity)
        if grid_state is None:
            _LOGGER.warning("Grid power entity '%s' not found", self.grid_power_entity)
            return

        grid_power = to_float(grid_state.state)
        if grid_power is None:
            return

        if grid_state.last_changed is not None:
            stale_seconds = (dt_util.utcnow() - grid_state.last_changed).total_seconds()
            if stale_seconds > GRID_POWER_STALENESS_SECONDS:
                _LOGGER.warning(
                    "Grid power entity '%s' unchanged for %.0fs — skipping solar regulation",
                    self.grid_power_entity,
                    stale_seconds,
                )
                return

        new_speed = SolarRegulator(self._solar_config()).compute(current_speed, grid_power)
        if new_speed is not None:
            _LOGGER.debug(
                "Solar regulation: grid=%.0fW setpoint=%.0fW band=[%.0f, %.0f] → speed %d→%d rpm",
                grid_power,
                self.setpoint,
                self.dead_band_lower,
                self.dead_band_upper,
                current_speed,
                new_speed,
            )
            await self.async_set_pump_key("SetCurrentSpeed", new_speed)

    # -------------------------------------------------------------------------
    # DataUpdateCoordinator hooks
    # -------------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Verify pump is reachable before entities are set up."""
        if not await self.api_pump.get_status():
            raise ConfigEntryNotReady("Cannot reach pump during setup")

    async def _async_update_data(self) -> PumpStatus:
        """Fetch latest pump data and apply solar regulation if active."""
        switch_on = True
        if self.switch_entity_id:
            switch_state = self.hass.states.get(self.switch_entity_id)
            switch_on = not (switch_state and switch_state.state.lower() == "off")
            if not switch_on:
                self.pump_switch_off = True
                self._update_uptime(False)
                self._prev_running = False
                self._pump_started_at = None
                self._priming_done = True
                self._last_speed_change_time = None
                self._prev_switch_on = False
                return PumpStatus.zeroed()

        self.pump_switch_off = False
        raw = await self.api_pump.get_status()
        if not raw:
            raise UpdateFailed("Pump did not respond or returned empty data")

        status = PumpStatus.from_raw(raw)
        self._update_uptime(status.running)

        watts = status.current_watts if (status.running and status.current_watts is not None) else 0.0
        self._update_energy(watts)

        # Priming: only triggered by physical switch OFF→ON
        if self.switch_entity_id:
            if switch_on and not self._prev_switch_on:
                self._pump_started_at = dt_util.utcnow()
                self._priming_done = False
                _LOGGER.debug("Switch turned ON: priming window of %ds begins", self.priming_time)
            self._prev_switch_on = switch_on
        self._prev_running = status.running

        # After priming window elapses, unlock solar regulation
        if (
            status.running
            and self.control_mode == "solar"
            and not self._priming_done
            and self._pump_started_at is not None
        ):
            elapsed = (dt_util.utcnow() - self._pump_started_at).total_seconds()
            if elapsed >= self.priming_time:
                _LOGGER.debug("Priming complete after %.0fs — handing off to solar regulation", elapsed)
                self._priming_done = True

        if status.running and self.control_mode == "solar" and self._priming_done and status.current_speed is not None:
            await self._apply_solar_regulation(int(status.current_speed))

        return status
