# emaux_spv150 for Home Assistant

**English** | [Français](./README.fr.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/0jety0/emaux_spv150?color=blue)](https://github.com/0jety0/emaux_spv150/releases)
[![HACS installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.emaux_spv150.total)](https://analytics.home-assistant.io/custom_integrations)
[![CI](https://github.com/0jety0/emaux_spv150/actions/workflows/ci.yaml/badge.svg)](https://github.com/0jety0/emaux_spv150/actions/workflows/ci.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Stars](https://img.shields.io/github/stars/0jety0/emaux_spv150?style=flat&logo=github)](https://github.com/0jety0/emaux_spv150/stargazers)
[![License: PolyForm NC](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange.svg)](LICENSE)

Custom Home Assistant integration to control and monitor the **Emaux SPV150** variable-speed pool pump.

![image info](/img/main.jpeg)

## Features

### Monitoring
- Power draw (W) and flow rate (GPM) in real time
- Cumulated energy (kWh) — compatible with the HA Energy dashboard
- Uptime since the last start

### Control
- Current speed (RPM) and speed preset (1/2/3) adjustable from the UI
- Configurable throttle between speed changes (default: 60 s) to protect the pump
- Configurable request timeout and polling interval, both adjustable at runtime, so the pump's CGI server is not overloaded
- Startup sequence: automatically waits for priming to finish (default: 120 s, per SPV150 manual section 5) only on a physical power-on (switch OFF→ON)

### Solar mode — P-controller with dead band
- Mode selector: `Off` / `Manual` / `Solar` — **persisted across restarts**
- Configurable grid-power entity (any HA entity, e.g. `sensor.grid_power`)
- **Proportional (P) controller** centred on a configurable setpoint:
  - `error = |grid_power - setpoint|`
  - `step = min(step_max, max(10 W, error))` — proportional to the delta, capped
  - Below the lower dead-band bound → speed up
  - Above the upper bound → speed down
  - Inside the dead band → no action
- Regulation is active immediately if the pump is already running when switching to solar mode
- Stale-data protection: if the grid value has not changed for more than 60 s, regulation is suspended
- All parameters (setpoint, dead band, steps, mode, min/max speeds) **persisted across restarts**

## Installation

### Via HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. In HACS, go to **Integrations**.
3. Click the three dots (⋮) > **Custom repositories**.
4. Add this repository's URL and select **Integration**.
5. Install `emaux_spv150` from HACS.
6. Restart Home Assistant.

### Manual installation

1. Copy the `custom_components/emaux_spv150` folder into your HA instance's `config/custom_components/`.
2. Restart Home Assistant.

## Initial setup

1. **Settings > Devices & Services > Add integration**
2. Search for `emaux_spv150`
3. Enter the pump's IP address
4. (optional) Select an external switch to pause polling when the pump is powered off

The pump is tested (HTTP ping) before validation. The same IP cannot be added twice.

## Configurable options

Available via **Settings > Devices & Services > Emaux SPV150 > Configure**:

| Option | Description | Default |
|--------|-------------|---------|
| IP address | Pump IP | — |
| External switch | Entity used to pause polling | — |
| Polling interval | 5–60 seconds | 30 s |
| Request timeout | HTTP timeout per pump request (1–30 s) | 5 s |
| Grid-power entity | HA sensor for solar mode | — |
| Setpoint (W) | Target grid power for the P-controller | 0 W |
| Dead-band lower bound (W) | Below this: speed up | 0 W |
| Dead-band upper bound (W) | Above this: slow down | 100 W |
| Max step up (RPM) | Cap on the proportional step when speeding up | 300 RPM |
| Max step down (RPM) | Cap on the proportional step when slowing down | 30 RPM |
| Priming delay (s) | Wait after power-on before solar regulation | 120 s |
| Speed-change interval (s) | Throttle between two SetSpeed commands (0 = disabled) | 60 s |

## Created entities

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.power` | Sensor | Power draw (W) |
| `sensor.flow_rate` | Sensor | Flow rate (GPM) |
| `sensor.energy` | Sensor | Cumulated energy (kWh) |
| `sensor.uptime` | Sensor | Uptime (h) |
| `number.speed` | Number | Current speed (RPM) — slider |
| `number.speed_preset` | Number | Speed preset (1/2/3) — slider |
| `number.setpoint` | Number | Controller setpoint (W) |
| `number.dead_band_lower` | Number | Dead-band lower bound (W) |
| `number.dead_band_upper` | Number | Dead-band upper bound (W) |
| `number.step_up` | Number | Max step up (RPM) |
| `number.step_down` | Number | Max step down (RPM) |
| `number.rpm_min_solar` | Number | Min speed in solar mode (RPM) |
| `number.rpm_max_solar` | Number | Max speed in solar mode (RPM) |
| `number.poll_interval` | Number | Polling interval (s) |
| `number.request_timeout` | Number | HTTP request timeout (s) |
| `switch.running` | Switch | Start / stop the pump |
| `select.control_mode` | Select | Off / Manual / Solar |

![image info](/img/page_web.jpeg)

## Development

Tooling: [uv](https://docs.astral.sh/uv/) (environment & dependencies) and [ruff](https://docs.astral.sh/ruff/) (lint + format).

```bash
uv sync                 # venv + dev dependencies (from uv.lock)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pytest -q        # tests
```

CI (GitHub Actions) runs `ruff check`, `ruff format --check` and `pytest`, in addition to `hassfest` and HACS validation.

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — personal / non-commercial use. Any commercial use requires a separate agreement.
