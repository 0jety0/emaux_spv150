"""Unit tests for the pure P-controller (no Home Assistant runtime needed)."""

from custom_components.emaux_spv150.solar import SolarControllerConfig, SolarRegulator


def _config(**overrides):
    base = {
        "setpoint": 1000,
        "dead_band_lower": 500,
        "dead_band_upper": 1500,
        "step_up": 200,
        "step_down": 150,
        "rpm_min_solar": 800,
        "rpm_max_solar": 3400,
    }
    base.update(overrides)
    return SolarControllerConfig(**base)


def test_speeds_up_below_dead_band():
    """Grid power below the lower bound increases speed (capped by step_up)."""
    regulator = SolarRegulator(_config())
    # error = 1000 - 200 = 800 → step = min(200, 800) = 200 → 1500 + 200
    assert regulator.compute(1500, 200) == 1700


def test_slows_down_above_dead_band():
    """Grid power above the upper bound decreases speed (capped by step_down)."""
    regulator = SolarRegulator(_config())
    # error = 2000 - 1000 = 1000 → step = min(150, 1000) = 150 → 2000 - 150
    assert regulator.compute(2000, 2000) == 1850


def test_no_change_inside_dead_band():
    """Inside the dead band no change is requested."""
    regulator = SolarRegulator(_config(dead_band_lower=900, dead_band_upper=1100))
    assert regulator.compute(1500, 1000) is None


def test_minimum_step_applied():
    """A tiny error still moves by at least MIN_STEP_RPM."""
    regulator = SolarRegulator(_config(setpoint=499))
    # grid=498 < lower(500); error = 499-498 = 1 → step = max(10, 1) = 10
    assert regulator.compute(1500, 498) == 1510


def test_clamped_to_rpm_max():
    """The new speed never exceeds rpm_max_solar."""
    regulator = SolarRegulator(_config(rpm_max_solar=1600, step_up=1000))
    assert regulator.compute(1500, 0) == 1600


def test_clamped_to_rpm_min():
    """The new speed never drops below rpm_min_solar."""
    regulator = SolarRegulator(_config(rpm_min_solar=1400, step_down=1000))
    assert regulator.compute(1500, 5000) == 1400


def test_rounded_to_ten():
    """Result is rounded to the nearest 10 RPM."""
    regulator = SolarRegulator(_config(step_up=23))
    # 1500 + min(23, error) = 1523 → rounded to 1520
    assert regulator.compute(1500, 0) == 1520
