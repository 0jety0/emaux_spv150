"""Typed data model for the Emaux SPV150 pump.

Centralises the conversion of the pump's raw JSON (string values) into a single
typed object so every entity reads strongly-typed fields instead of repeating
``float(...)`` / ``== "1"`` conversions on the raw dict.
"""

from dataclasses import dataclass
from typing import Any


def to_float(value: Any) -> float | None:
    """Coerce a raw pump value to float, or None when it cannot be parsed."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PumpStatus:
    """Snapshot of the pump state for one polling cycle."""

    current_speed: float | None = None
    current_watts: float | None = None
    current_gpm: float | None = None
    speed_selected: int | None = None
    running: bool = False

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "PumpStatus":
        """Build a typed status from the pump's raw JSON response.

        ``RunningStatus`` is normalised through ``str()`` so the comparison stays
        correct whether the firmware returns ``"1"`` or ``1``.
        """
        speed_selected = to_float(raw.get("SpeedSelected"))
        return cls(
            current_speed=to_float(raw.get("CurrentSpeed")),
            current_watts=to_float(raw.get("CurrentWatts")),
            current_gpm=to_float(raw.get("CurrentGPM")),
            speed_selected=int(speed_selected) if speed_selected is not None else None,
            running=str(raw.get("RunningStatus", "0")) == "1",
        )

    @classmethod
    def zeroed(cls) -> "PumpStatus":
        """Return an all-zero status used when the external switch is OFF."""
        return cls(current_speed=0.0, current_watts=0.0, current_gpm=0.0, speed_selected=0, running=False)
