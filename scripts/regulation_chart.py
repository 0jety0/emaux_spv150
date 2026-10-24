"""Draw the solar regulation response curve used in the README (light and dark SVG).

The curve is computed with the real SolarRegulator, so the picture cannot drift
from the code. Run it again after changing solar.py:

    mise run docs
"""

from pathlib import Path

from custom_components.emaux_spv150.solar import SolarControllerConfig, SolarRegulator

# Example settings (the author's own): setpoint 50 W, dead band -50..+50 W, max steps +300 / -30 RPM.
CONFIG = SolarControllerConfig(
    setpoint=50,
    dead_band_lower=-50,
    dead_band_upper=50,
    step_up=300,
    step_down=30,
    rpm_min_solar=800,
    rpm_max_solar=3400,
)
CURRENT_SPEED = 2000  # mid-range, so the min/max solar speed clamps never apply
X_MIN, X_MAX = -450, 250  # grid power range shown (W)
Y_MIN, Y_MAX = -60, 330  # speed change range shown (RPM)

# Chart chrome and diverging pair from the dataviz reference palette (validated light and dark).
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "band": "#f0efec",
        "up": "#2a78d6",
        "down": "#e34948",
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#f0efec",
        "ink2": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "band": "#383835",
        "up": "#3987e5",
        "down": "#e66767",
    },
}

# Typographic minus sign for the chart labels (U+2212, wider than the hyphen).
MINUS = "\u2212"

WIDTH, HEIGHT = 760, 420
LEFT, RIGHT, TOP, BOTTOM = 70, 24, 70, 62


def speed_change(grid_power: float) -> int:
    """Speed change (RPM) one regulation step applies at this grid power."""
    new_speed = SolarRegulator(CONFIG).compute(CURRENT_SPEED, grid_power)
    return 0 if new_speed is None else new_speed - CURRENT_SPEED


def x_px(watts: float) -> float:
    return LEFT + (watts - X_MIN) / (X_MAX - X_MIN) * (WIDTH - LEFT - RIGHT)


def y_px(rpm: float) -> float:
    return TOP + (Y_MAX - rpm) / (Y_MAX - Y_MIN) * (HEIGHT - TOP - BOTTOM)


def curve_segments() -> list[tuple[int, list[tuple[float, float]]]]:
    """Split the curve into runs of the same sign (-1, 0, +1): each run is drawn on its own."""
    segments: list[tuple[int, list[tuple[float, float]]]] = []
    for watts in range(X_MIN, X_MAX + 1):
        rpm = speed_change(watts)
        sign = (rpm > 0) - (rpm < 0)
        if not segments or segments[-1][0] != sign:
            segments.append((sign, []))
        segments[-1][1].append((x_px(watts), y_px(rpm)))
    return segments


def text(x: float, y: float, content: str, fill: str, size: int = 13, anchor: str = "start", weight: int = 400) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{content}</text>'
    )


def render(theme: dict[str, str]) -> str:
    t = theme
    plot_bottom = HEIGHT - BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif" role="img" '
        'aria-label="Speed change per regulation step as a function of grid power">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="8" fill="{t["surface"]}"/>',
        text(LEFT, 30, "Solar mode: speed change per regulation step", t["ink"], 16, weight=600),
        text(
            LEFT,
            50,
            f"Example: setpoint 50 W, dead band {MINUS}50…+50 W, max steps +300 / {MINUS}30 RPM",
            t["ink2"],
            12,
        ),
    ]
    # Dead band: no change.
    band_left, band_right = x_px(CONFIG.dead_band_lower), x_px(CONFIG.dead_band_upper)
    parts.append(
        f'<rect x="{band_left:.1f}" y="{TOP}" width="{band_right - band_left:.1f}" '
        f'height="{plot_bottom - TOP}" fill="{t["band"]}"/>'
    )
    parts.append(text((band_left + band_right) / 2, TOP + 16, "dead band", t["ink2"], 12, "middle"))
    parts.append(text((band_left + band_right) / 2, TOP + 31, "no change", t["muted"], 12, "middle"))
    # Gridlines and y ticks.
    for rpm in (-30, 0, 100, 200, 300):
        y = y_px(rpm)
        color = t["axis"] if rpm == 0 else t["grid"]
        parts.append(f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{color}"/>')
        label = f"+{rpm}" if rpm > 0 else ("0" if rpm == 0 else f"{MINUS}{-rpm}")
        parts.append(text(LEFT - 8, y + 4, label, t["muted"], 12, "end"))
    # X ticks.
    for watts in range(-400, X_MAX + 1, 100):
        x = x_px(watts)
        parts.append(
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{plot_bottom}" y2="{plot_bottom + 4}" stroke="{t["axis"]}"/>'
        )
        label = f"{watts}" if watts >= 0 else f"{MINUS}{-watts}"
        parts.append(text(x, plot_bottom + 18, label, t["muted"], 12, "middle"))
    # Setpoint reference.
    sx = x_px(CONFIG.setpoint)
    parts.append(f'<line x1="{sx:.1f}" x2="{sx:.1f}" y1="{TOP + 40}" y2="{plot_bottom}" stroke="{t["muted"]}"/>')
    parts.append(text(sx + 6, y_px(150), "setpoint", t["ink2"], 12))
    # Curve.
    colors = {1: t["up"], 0: t["muted"], -1: t["down"]}
    for sign, points in curve_segments():
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        parts.append(
            f'<polyline points="{path}" fill="none" stroke="{colors[sign]}" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # Direct labels (ink text, a short colored key carries identity).
    def key(x: float, y: float, color: str, label: str, details: tuple[str, ...]) -> list[str]:
        lines = [
            f'<line x1="{x:.1f}" x2="{x + 16:.1f}" y1="{y - 4:.1f}" y2="{y - 4:.1f}" stroke="{color}" '
            'stroke-width="2" stroke-linecap="round"/>',
            text(x + 22, y, label, t["ink"], 13, weight=600),
        ]
        lines += [text(x + 22, y + 16 * (i + 1), detail, t["ink2"], 12) for i, detail in enumerate(details)]
        return lines

    parts += key(
        x_px(-440),
        y_px(190),
        t["up"],
        "Exporting: speed up",
        ("step = setpoint " + MINUS + " grid", "capped at +300 RPM"),
    )
    parts += key(
        x_px(64),
        y_px(95),
        t["down"],
        "Importing: slow down",
        ("step = grid " + MINUS + " setpoint", f"capped at {MINUS}30 RPM"),
    )
    # Axis titles.
    parts.append(
        text(
            (LEFT + WIDTH - RIGHT) / 2,
            HEIGHT - 16,
            "Grid power (W) · negative = exporting to the grid",
            t["ink2"],
            12,
            "middle",
        )
    )
    parts.append(
        f'<text transform="translate(18 {(TOP + plot_bottom) / 2:.1f}) rotate(-90)" fill="{t["ink2"]}" '
        'font-size="12" text-anchor="middle">Speed change (RPM)</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "img"
    for name, theme in THEMES.items():
        (out / f"regulation-{name}.svg").write_text(render(theme), encoding="utf-8")
        print(f"wrote img/regulation-{name}.svg")


if __name__ == "__main__":
    main()
