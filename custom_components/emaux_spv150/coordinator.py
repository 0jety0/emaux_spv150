import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, CONF_HOST, STATE_OFF, STATE_ON, UnitOfPower
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import PowerConverter

from .api import PumpAPI, PumpError
from .const import (
    COMMAND_SETTLE_DELAY,
    CONF_CONTROL_MODE,
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
    DOMAIN,
    GRID_POWER_STALENESS_SECONDS,
    OPTION_DEFAULTS,
    PUMP_BOOT_TIME,
    ControlMode,
    PumpCommand,
)
from .models import PumpStatus, to_float
from .solar import SolarControllerConfig, SolarRegulator

_LOGGER = logging.getLogger(__name__)

type PumpConfigEntry = ConfigEntry["PumpCoordinator"]


@dataclass(frozen=True)
class ConnectionSettings:
    """Settings that need a reload when they change."""

    host: str
    switch_entity_id: str | None
    grid_power_entity: str


def connection_settings(entry: ConfigEntry) -> ConnectionSettings:
    """Return the connection settings in use: options win over data.

    The options flow stores all three (an empty entity as ""), so an entity present in the options
    wins even when empty; the host in the options wins only when set.
    """
    opts, data = entry.options, entry.data
    switch = opts[CONF_SWITCH_ENTITY] if CONF_SWITCH_ENTITY in opts else data.get(CONF_SWITCH_ENTITY)
    grid = opts[CONF_GRID_POWER_ENTITY] if CONF_GRID_POWER_ENTITY in opts else data.get(CONF_GRID_POWER_ENTITY)
    return ConnectionSettings(
        host=opts.get(CONF_HOST) or data[CONF_HOST],
        switch_entity_id=switch or None,
        grid_power_entity=grid or "",
    )


def is_switch_off(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Return True when an external power switch is configured and explicitly OFF.

    Unknown or unavailable states count as ON: the pump may still be powered.
    """
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    return state is not None and state.state.lower() == STATE_OFF


def is_pump_silence_expected(hass: HomeAssistant, entity_id: str | None, *, setting_up: bool) -> bool:
    """Return True when a silent pump is most likely without power or still booting.

    That is a power switch that is not ON (off, unknown or unavailable, as an MQTT plug
    is for a while after every restart), or that turned ON less than PUMP_BOOT_TIME ago.
    A switch entity that does not exist explains the silence only during setup: the plug's
    integration may start later. No switch configured explains nothing.
    """
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    if state is None:
        return setting_up
    if state.state.lower() != STATE_ON:
        return True
    return (dt_util.utcnow() - state.last_changed).total_seconds() < PUMP_BOOT_TIME


def grid_power_watts(state: State) -> float | None:
    """Return the grid power of a sensor state in W, or None when the state is not a number.

    The grid selector accepts any power sensor (W, kW, MW...). A sensor without a unit, or with a unit
    that is not a power unit (any entity could be picked before 2.3.2), is read as W as it always was.
    """
    value = to_float(state.state)
    if value is None:
        return None
    if not is_power_unit(state):
        return value
    return PowerConverter.convert(value, state.attributes[ATTR_UNIT_OF_MEASUREMENT], UnitOfPower.WATT)


def is_power_unit(state: State) -> bool:
    """Return True when the state's unit of measurement is a power unit Home Assistant can convert."""
    return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) in PowerConverter.VALID_UNITS


class SpeedChangeThrottled(ServiceValidationError):
    """A speed change was asked before the minimum interval since the previous one."""


class PumpCoordinator(DataUpdateCoordinator[PumpStatus]):
    """Coordinator for polling and controlling the Emaux SPV150 pump."""

    config_entry: PumpConfigEntry

    # Settings read from the entry options (or their default) by apply_options()
    control_mode: ControlMode
    poll_interval: int
    request_timeout: int
    setpoint: float
    dead_band_lower: float
    dead_band_upper: float
    step_up: int
    step_down: int
    rpm_min_solar: int
    rpm_max_solar: int
    priming_time: int
    speed_change_interval: int

    def __init__(self, hass: HomeAssistant, entry: PumpConfigEntry) -> None:
        # Connection-relevant settings: a change in any of these requires a full
        # reload (handled by the update listener in __init__.py).
        settings = connection_settings(entry)
        self.host: str = settings.host
        self.switch_entity_id: str | None = settings.switch_entity_id
        self.grid_power_entity: str = settings.grid_power_entity
        self.api_pump = PumpAPI(settings.host, async_get_clientsession(hass))

        # Speed change throttle
        self._last_speed_change_time: datetime | None = None
        self._speed_change_lock = asyncio.Lock()

        # Priming: set when the switch turns OFF→ON, cleared once priming_time has elapsed (None = not priming)
        self._pump_started_at: datetime | None = None
        self._prev_switch_on: bool = True

        # True once a missing or stale grid sensor has been logged, until it is usable again
        self._grid_unusable_logged: bool = False
        # True once an unrecognised grid sensor unit has been logged
        self._grid_unit_warned: bool = False

        # Energy tracking
        self._energy_kwh: float = 0.0
        self._last_energy_update: datetime | None = None

        # Uptime tracking
        self._uptime_start: datetime | None = None

        # True when the pump has no power: switch OFF, or silent while its switch is not ON or it is booting
        self.pump_powered_off: bool = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            # After a command, re-read the pump once it has settled, without blocking the service call.
            request_refresh_debouncer=Debouncer(hass, _LOGGER, cooldown=COMMAND_SETTLE_DELAY, immediate=False),
        )
        self.apply_options(entry)

    # -------------------------------------------------------------------------
    # Options
    # -------------------------------------------------------------------------

    def connection_settings_changed(self, entry: PumpConfigEntry) -> bool:
        """Return True if host / switch / grid entity differ from the live values.

        These are the only settings that require a full reload; everything else
        is applied live via apply_options().
        """
        live = ConnectionSettings(self.host, self.switch_entity_id, self.grid_power_entity)
        return connection_settings(entry) != live

    def apply_options(self, entry: PumpConfigEntry) -> None:
        """Read the settings from the entry options (or their default) into the live state.

        Called at start-up and by the update listener when no connection setting changed, so an
        options-flow edit applies without a reload (and a number-entity write is simply re-applied).
        """
        opts = {**OPTION_DEFAULTS, **entry.options}
        self.control_mode = ControlMode(opts[CONF_CONTROL_MODE])
        self.setpoint = float(opts[CONF_SETPOINT])
        self.dead_band_lower = float(opts[CONF_DEAD_BAND_LOWER])
        self.dead_band_upper = float(opts[CONF_DEAD_BAND_UPPER])
        self.step_up = int(opts[CONF_STEP_UP])
        self.step_down = int(opts[CONF_STEP_DOWN])
        self.rpm_min_solar = int(opts[CONF_RPM_MIN_SOLAR])
        self.rpm_max_solar = int(opts[CONF_RPM_MAX_SOLAR])
        self.priming_time = int(opts[CONF_PRIMING_TIME])
        self.speed_change_interval = int(opts[CONF_SPEED_CHANGE_INTERVAL])
        self.poll_interval = int(opts[CONF_POLL_INTERVAL])
        self.update_interval = timedelta(seconds=self.poll_interval)
        self.request_timeout = int(opts[CONF_REQUEST_TIMEOUT])
        self.api_pump.set_timeout(self.request_timeout)
        self.async_update_listeners()

    def set_option(self, key: str, value: float | str) -> None:
        """Keep one setting in the entry options and apply it live.

        Whole-number settings are stored as int, as the options flow stores them. Saving does not
        reload: the update listener (see __init__.py) only reloads on a connection change.
        """
        if isinstance(OPTION_DEFAULTS[key], int):
            value = int(value)
        value = self._keep_ranges_ordered(key, value)
        self.hass.config_entries.async_update_entry(
            self.config_entry, options={**self.config_entry.options, key: value}
        )
        self.apply_options(self.config_entry)

    def _keep_ranges_ordered(self, key: str, value: float | str) -> float | str:
        """Keep dead_band_lower <= dead_band_upper and rpm_min_solar <= rpm_max_solar, so the regulator stays valid."""
        if key == CONF_DEAD_BAND_LOWER and float(value) > self.dead_band_upper:
            _LOGGER.warning("dead_band_lower (%s) capped to dead_band_upper (%s)", value, self.dead_band_upper)
            return self.dead_band_upper
        if key == CONF_DEAD_BAND_UPPER and float(value) < self.dead_band_lower:
            _LOGGER.warning("dead_band_upper (%s) raised to dead_band_lower (%s)", value, self.dead_band_lower)
            return self.dead_band_lower
        if key == CONF_RPM_MIN_SOLAR and float(value) > self.rpm_max_solar:
            _LOGGER.warning("rpm_min_solar (%d) capped to rpm_max_solar (%d)", value, self.rpm_max_solar)
            return self.rpm_max_solar
        if key == CONF_RPM_MAX_SOLAR and float(value) < self.rpm_min_solar:
            _LOGGER.warning("rpm_max_solar (%d) raised to rpm_min_solar (%d)", value, self.rpm_min_solar)
            return self.rpm_min_solar
        return value

    # -------------------------------------------------------------------------
    # Pump command
    # -------------------------------------------------------------------------

    async def async_set_pump_key(self, key: PumpCommand, value: int) -> str:
        """Send a command to the pump; a speed change within the minimum interval raises SpeedChangeThrottled."""
        if key != PumpCommand.SET_CURRENT_SPEED:
            return await self._send_pump_key(key, value)
        # The check and the arming must not be split by the request: a manual change sent while the
        # regulator's change is in flight would pass the check too.
        async with self._speed_change_lock:
            self._raise_if_speed_change_throttled()
            result = await self._send_pump_key(key, value)
            # Armed only once the pump accepted the change, so a failure does not block the retry.
            self._last_speed_change_time = dt_util.utcnow()
            return result

    def _raise_if_speed_change_throttled(self) -> None:
        if self.speed_change_interval <= 0 or self._last_speed_change_time is None:
            return
        elapsed = (dt_util.utcnow() - self._last_speed_change_time).total_seconds()
        if elapsed < self.speed_change_interval:
            raise SpeedChangeThrottled(
                translation_domain=DOMAIN,
                translation_key="speed_change_throttled",
                translation_placeholders={"interval": str(self.speed_change_interval)},
            )

    async def _send_pump_key(self, key: PumpCommand, value: int) -> str:
        try:
            return await self.api_pump.set_key(key, value)
        except PumpError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"command": key, "error": str(err)},
            ) from err

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

    def _log_grid_unusable(self, message: str, *args: object) -> None:
        """Warn once when the grid sensor blocks the regulation, not at every poll."""
        if not self._grid_unusable_logged:
            _LOGGER.warning(message, *args)
            self._grid_unusable_logged = True

    async def _apply_solar_regulation(self, current_speed: int) -> None:
        """Read the grid-power entity and apply one P-controller step if needed."""
        if not self.grid_power_entity:
            return

        grid_state = self.hass.states.get(self.grid_power_entity)
        if grid_state is None:
            self._log_grid_unusable("Grid power entity '%s' not found", self.grid_power_entity)
            return

        grid_power = grid_power_watts(grid_state)
        if grid_power is None:
            return
        unit = grid_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit is not None and not is_power_unit(grid_state) and not self._grid_unit_warned:
            _LOGGER.warning(
                "Grid power entity '%s' unit '%s' is not recognised: its value is read as watts",
                self.grid_power_entity,
                unit,
            )
            self._grid_unit_warned = True

        # last_reported moves on every report, even with an unchanged value (last_changed does not).
        stale_seconds = (dt_util.utcnow() - grid_state.last_reported).total_seconds()
        if stale_seconds > GRID_POWER_STALENESS_SECONDS:
            self._log_grid_unusable(
                "Grid power entity '%s' not reported for %.0fs — skipping solar regulation",
                self.grid_power_entity,
                stale_seconds,
            )
            return

        if self._grid_unusable_logged:
            _LOGGER.info("Grid power entity '%s' usable again: solar regulation resumes", self.grid_power_entity)
            self._grid_unusable_logged = False

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
            try:
                await self.async_set_pump_key(PumpCommand.SET_CURRENT_SPEED, new_speed)
            except SpeedChangeThrottled:
                _LOGGER.debug("Solar regulation: speed change to %d rpm throttled", new_speed)
            except HomeAssistantError as err:
                # The status was read fine: keep it, the regulator retries on the next poll.
                _LOGGER.warning("Solar regulation: speed change to %d rpm failed: %s", new_speed, err)

    @callback
    def async_on_switch_change(self, event: Event[EventStateChangedData]) -> None:
        """Re-poll as soon as the power switch flips instead of waiting for the next poll."""
        old, new = event.data["old_state"], event.data["new_state"]
        if old is not None and new is not None and old.state == new.state:
            return  # attribute-only update
        self.config_entry.async_create_background_task(self.hass, self.async_refresh(), "emaux_spv150_switch_refresh")

    def _powered_off(self) -> PumpStatus:
        """Stop the uptime and energy tracking and return the status of a pump without power."""
        self.pump_powered_off = True
        self._update_uptime(False)
        self._last_speed_change_time = None
        self._last_energy_update = None
        return PumpStatus.zeroed()

    # -------------------------------------------------------------------------
    # DataUpdateCoordinator hooks
    # -------------------------------------------------------------------------

    @override
    async def _async_update_data(self) -> PumpStatus:
        """Fetch latest pump data and apply solar regulation if active."""
        switch_on = not is_switch_off(self.hass, self.switch_entity_id)
        if not switch_on:
            # Priming starts again on the next OFF→ON flip of the switch.
            self._pump_started_at = None
            self._prev_switch_on = False
            return self._powered_off()

        self.pump_powered_off = False
        try:
            raw = await self.api_pump.get_status()
        except PumpError as err:
            setting_up = self.config_entry.state is ConfigEntryState.SETUP_IN_PROGRESS
            if is_pump_silence_expected(self.hass, self.switch_entity_id, setting_up=setting_up):
                _LOGGER.debug("Pump silent while its switch is not ON or it is booting: taken as powered off")
                return self._powered_off()
            # Unknown power and running state during the outage: restart energy and uptime on the next answer.
            self._last_energy_update = None
            self._uptime_start = None
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        status = PumpStatus.from_raw(raw)
        self._update_uptime(status.running)

        watts = status.current_watts if (status.running and status.current_watts is not None) else 0.0
        self._update_energy(watts)

        # Priming: only triggered by physical switch OFF→ON
        if self.switch_entity_id:
            if switch_on and not self._prev_switch_on:
                self._pump_started_at = dt_util.utcnow()
                _LOGGER.debug("Switch turned ON: priming window of %ds begins", self.priming_time)
            self._prev_switch_on = switch_on

        # After priming window elapses, unlock solar regulation
        if status.running and self.control_mode == ControlMode.SOLAR and self._pump_started_at is not None:
            elapsed = (dt_util.utcnow() - self._pump_started_at).total_seconds()
            if elapsed >= self.priming_time:
                _LOGGER.debug("Priming complete after %.0fs — handing off to solar regulation", elapsed)
                self._pump_started_at = None

        priming = self._pump_started_at is not None
        if (
            status.running
            and self.control_mode == ControlMode.SOLAR
            and not priming
            and status.current_speed is not None
        ):
            await self._apply_solar_regulation(int(status.current_speed))

        return status
