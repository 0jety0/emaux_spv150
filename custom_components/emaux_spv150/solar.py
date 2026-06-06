"""Solar regulation logic for the Emaux SPV150 pump.

Extracted from the coordinator so the P-controller is a pure, side-effect-free
unit that can be tested in isolation (Single Responsibility Principle).
"""

from dataclasses import dataclass

# Minimum proportional step (RPM) applied as soon as the grid power leaves the
# dead band, even when the computed error is tiny.
MIN_STEP_RPM = 10
# Speed values are rounded to this resolution before being sent to the pump.
SPEED_ROUNDING_RPM = 10


@dataclass(frozen=True)
class SolarControllerConfig:
    """Tunable parameters of the proportional solar controller."""

    setpoint: float
    dead_band_lower: float
    dead_band_upper: float
    step_up: int
    step_down: int
    rpm_min_solar: int
    rpm_max_solar: int


class SolarRegulator:
    """Proportional (P) controller centred on a setpoint with a dead band.

    ``error = |grid_power - setpoint|``
    ``step  = min(step_max, max(MIN_STEP_RPM, int(error)))``

    - Below ``dead_band_lower`` → speed up (more self-consumption).
    - Above ``dead_band_upper`` → speed down.
    - Inside the dead band → no change.
    """

    def __init__(self, config: SolarControllerConfig) -> None:
        self._config = config

    def compute(self, current_speed: int, grid_power: float) -> int | None:
        """Return the new target speed (RPM), or None when no change is needed."""
        config = self._config

        if grid_power < config.dead_band_lower:
            error = config.setpoint - grid_power
            step = min(config.step_up, max(MIN_STEP_RPM, int(error)))
            new_speed = current_speed + step
        elif grid_power > config.dead_band_upper:
            error = grid_power - config.setpoint
            step = min(config.step_down, max(MIN_STEP_RPM, int(error)))
            new_speed = current_speed - step
        else:
            return None

        new_speed = max(config.rpm_min_solar, min(config.rpm_max_solar, new_speed))
        new_speed = round(new_speed / SPEED_ROUNDING_RPM) * SPEED_ROUNDING_RPM

        return new_speed if new_speed != current_speed else None
