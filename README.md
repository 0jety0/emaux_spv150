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
- Power draw (W) and flow rate (shown in L/min) in real time
- Cumulated energy (kWh) — compatible with the HA Energy dashboard
- Uptime since the last start

### Control
- Current speed (RPM) and speed preset (1/2/3) adjustable from the UI
- Configurable throttle between speed changes (default: 60 s) to protect the pump
- Configurable request timeout and polling interval, both adjustable at runtime, so the pump's CGI server is not overloaded
- Startup sequence: automatically waits for priming to finish (default: 120 s, per SPV150 manual section 5) only on a physical power-on (switch OFF→ON)

### Solar mode — P-controller with dead band
- Mode selector: `Off` / `Manual` / `Solar` — **persisted across restarts**
- Grid-power sensor (a `power` sensor, positive when importing, negative when exporting)
- **Proportional (P) controller** centred on a configurable setpoint:
  - `error = |grid_power - setpoint|`
  - `step = min(step_max, max(10 W, error))` — proportional to the delta, capped
  - Below the lower dead-band bound → speed up
  - Above the upper bound → speed down
  - Inside the dead band → no action
- Regulation is active immediately if the pump is already running when switching to solar mode
- Stale-data protection: if the grid sensor has not reported for more than 60 s, regulation is suspended
- All parameters (setpoint, dead band, steps, mode, min/max speeds) **persisted across restarts**

## Installation

Requires Home Assistant 2026.10 or later.

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
4. (optional) Pick the smart plug or switch that powers the pump, and the grid-power sensor for the solar mode

The pump is tested (HTTP ping) before validation. The same IP cannot be added twice.

## Configurable options

Available via **Settings > Devices & Services > Emaux SPV150 > Configure**:

| Option | Description | Default |
|--------|-------------|---------|
| IP address | Pump IP | — |
| External switch | Plug or switch powering the pump: while it is off, the pump is not polled | — |
| Polling interval | 5–60 seconds | 30 s |
| Request timeout | HTTP timeout per pump request (1–30 s) | 5 s |
| Grid-power sensor | Power sensor for solar mode | — |
| Setpoint (W) | Target grid power for the P-controller | 0 W |
| Dead-band lower bound (W) | Below this: speed up | 0 W |
| Dead-band upper bound (W) | Above this: slow down | 100 W |
| Max step up (RPM) | Cap on the proportional step when speeding up | 300 RPM |
| Max step down (RPM) | Cap on the proportional step when slowing down | 30 RPM |
| Priming delay (s) | Wait after power-on before solar regulation | 120 s |
| Speed-change interval (s) | Throttle between two SetSpeed commands (0 = disabled) | 60 s |

## Created entities

Default entity IDs on a new installation (they follow the device and entity names):

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.emaux_spv150_power` | Sensor | Power draw (W) |
| `sensor.emaux_spv150_flow_rate` | Sensor | Flow rate (shown in L/min) |
| `sensor.emaux_spv150_energy` | Sensor | Cumulated energy (kWh) |
| `sensor.emaux_spv150_uptime` | Sensor | Uptime (h) — diagnostic |
| `number.emaux_spv150_speed` | Number | Current speed (RPM) — slider |
| `number.emaux_spv150_speed_preset` | Number | Speed preset (1/2/3) — slider |
| `number.emaux_spv150_setpoint` | Number | Controller setpoint (W) |
| `number.emaux_spv150_dead_band_lower_bound` | Number | Dead-band lower bound (W) |
| `number.emaux_spv150_dead_band_upper_bound` | Number | Dead-band upper bound (W) |
| `number.emaux_spv150_max_speed_increase_step` | Number | Max step up (RPM) |
| `number.emaux_spv150_max_speed_decrease_step` | Number | Max step down (RPM) |
| `number.emaux_spv150_min_speed_solar` | Number | Min speed in solar mode (RPM) |
| `number.emaux_spv150_max_speed_solar` | Number | Max speed in solar mode (RPM) |
| `number.emaux_spv150_polling_interval` | Number | Polling interval (s) |
| `number.emaux_spv150_request_timeout` | Number | HTTP request timeout (s) |
| `switch.emaux_spv150_running` | Switch | Start / stop the pump |
| `select.emaux_spv150_control_mode` | Select | Off / Manual / Solar |

![image info](/img/page_web.jpeg)

## How data is updated

- The pump is polled every 30 s by default (5–60 s, adjustable at runtime) with a single HTTP request.
- After a command (speed, preset, run/stop) the pump is read again once it has settled (2 s).
- A change of the external power switch triggers an immediate read.
- While the external switch is off, the pump is not polled: its values show as unavailable and nothing is reported as an error.
- Right after a Home Assistant restart the switch state can stay unknown for a minute or two: a pump that does not answer then does not fail the setup. Once running, a pump that does not answer is reported as unavailable, whatever the switch state.

## Supported devices

Emaux SPV150 variable-speed pumps with the built-in Wi-Fi web interface (local CGI server). Other Emaux models have not been tested.

## Known limitations

- The pump's web interface has no authentication and uses plain HTTP: keep it on a trusted local network.
- One pump per Home Assistant instance: entity unique IDs are not yet prefixed per config entry.
- The `Off` mode only disables the solar regulation; it does not stop the pump (use the run/stop switch).
- Energy is computed by the integration from the power read at each poll, so it is an estimate.
- The priming wait only applies when the external switch turns the pump on, not after a Home Assistant restart.

## Troubleshooting

- **"Cannot connect" during setup**: check the IP address, that the pump is powered and on the same network. When the selected external switch is off, the check is skipped.
- **Entities unavailable**: the pump is powered off or does not answer. One error is logged when it stops answering and one line when it answers again.
- **Speed change refused**: changes are limited to one per speed-change interval (60 s by default, 0 disables the limit).
- **Debug logs**: add to `configuration.yaml`, then restart:

  ```yaml
  logger:
    logs:
      custom_components.emaux_spv150: debug
  ```

- **Diagnostics**: **Settings > Devices & Services > Emaux SPV150 > ⋮ > Download diagnostics** (the pump address is removed). Attach the file to an issue.

## Removal

1. **Settings > Devices & Services > Emaux SPV150 > ⋮ > Delete**.
2. In HACS, open the integration and choose **Remove** (manual install: delete `config/custom_components/emaux_spv150`).
3. Restart Home Assistant.

## Development

Tooling: [mise](https://mise.jdx.dev/) (tool versions and tasks), [uv](https://docs.astral.sh/uv/) (environment & dependencies), [ruff](https://docs.astral.sh/ruff/) (lint + format) and [mypy](https://mypy.readthedocs.io/) in strict mode, as in Home Assistant core.

```bash
mise run install        # venv + dev dependencies (from uv.lock)
mise run lint           # ruff check + ruff format --check
mise run typecheck      # mypy --strict
mise run test           # pytest
```

CI (GitHub Actions) runs the same lint, type check and tests, in addition to `hassfest` and HACS validation.

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — personal / non-commercial use. Any commercial use requires a separate agreement.
