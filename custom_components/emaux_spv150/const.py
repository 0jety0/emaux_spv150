from collections.abc import Mapping

from homeassistant.const import Platform

DOMAIN = "emaux_spv150"
DEFAULT_HOST = "192.168.1.1"
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.SELECT]

CONF_SWITCH_ENTITY = "switch_entity"
CONF_POLL_INTERVAL = "poll_interval"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_SETPOINT = "setpoint"
CONF_DEAD_BAND_LOWER = "dead_band_lower"
CONF_DEAD_BAND_UPPER = "dead_band_upper"
CONF_STEP_UP = "step_up"
CONF_STEP_DOWN = "step_down"
CONF_RPM_MIN_SOLAR = "rpm_min_solar"
CONF_RPM_MAX_SOLAR = "rpm_max_solar"
CONF_PRIMING_TIME = "priming_time"
CONF_SPEED_CHANGE_INTERVAL = "speed_change_interval"
CONF_REQUEST_TIMEOUT = "request_timeout"

# Default of each option, used while the option is not in the entry options.
OPTION_DEFAULTS: Mapping[str, str | float] = {
    "control_mode": "manual",
    CONF_POLL_INTERVAL: 30,
    CONF_SETPOINT: 0.0,
    CONF_DEAD_BAND_LOWER: 0.0,
    CONF_DEAD_BAND_UPPER: 100.0,
    CONF_STEP_UP: 300,
    CONF_STEP_DOWN: 30,
    CONF_RPM_MIN_SOLAR: 1400,
    CONF_RPM_MAX_SOLAR: 3000,
    CONF_PRIMING_TIME: 120,
    CONF_SPEED_CHANGE_INTERVAL: 60,
    CONF_REQUEST_TIMEOUT: 5,
}

# Bounds shared by the number entities and the options flow.
POWER_SETTING_MIN = -5000  # setpoint and dead band, W
POWER_SETTING_MAX = 5000
STEP_UP_MIN = 10
STEP_UP_MAX = 1000
STEP_DOWN_MIN = 10
STEP_DOWN_MAX = 500

COMMAND_SETTLE_DELAY = 2

# The pump joins Wi-Fi about 1-2 minutes after its power switch turns on: until then
# it cannot answer, and that is not an outage.
PUMP_BOOT_TIME = 180

# Solar regulation is suspended when the grid-power entity has not changed for
# longer than this, to avoid acting on stale readings.
GRID_POWER_STALENESS_SECONDS = 60
