# Emaux SPV150 for Home Assistant

**English** | [Français](./README.fr.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/0jety0/emaux_spv150?color=blue)](https://github.com/0jety0/emaux_spv150/releases)
[![HACS installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.emaux_spv150.total)](https://analytics.home-assistant.io/custom_integrations)
[![CI](https://github.com/0jety0/emaux_spv150/actions/workflows/ci.yaml/badge.svg)](https://github.com/0jety0/emaux_spv150/actions/workflows/ci.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Custom Home Assistant integration to monitor and control the **Emaux SPV150** variable-speed pool pump over
your local network, with a **solar mode** that adjusts the pump speed to your solar surplus.

![Emaux SPV150 variable-speed pool pump](img/main.jpeg)

## Features

### Monitoring
- Power draw (W) and flow rate (shown in L/min) in real time
- Cumulated energy (kWh), usable in the Home Assistant Energy dashboard
- Uptime since the last start

### Control
- Current speed (RPM) and speed preset (1/2/3) adjustable from the UI
- Minimum interval between two speed changes (default: 60 s) to protect the pump
- Request timeout and polling interval adjustable at runtime, so the pump's small web server is not overloaded
- Optional smart plug or switch that powers the pump: while it is off, the pump is not polled and nothing is reported as an error
- Startup sequence: after the switch turns the pump on, the solar mode waits for priming to finish (default: 120 s, per the SPV150 manual, section 5)

### Solar mode
- Mode selector: `Off` / `Manual` / `Solar`, kept across restarts
- Reads a grid-power sensor (positive when importing, negative when exporting) and moves the pump speed so that the grid power stays close to a setpoint: see [How the solar mode works](#how-the-solar-mode-works)
- Setpoint, dead band, maximum steps and min/max speeds are entities: change them from a dashboard or an automation

## Installation

Requires **Home Assistant 2026.10** or later.

### Via HACS (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=0jety0&repository=emaux_spv150&category=integration)

Or by hand:

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. In HACS, open the menu (⋮) > **Custom repositories**.
3. Add `https://github.com/0jety0/emaux_spv150` with the type **Integration**.
4. Install **Emaux SPV150**, then restart Home Assistant.

Updates then show up in **Settings > Updates**.

### Manual installation

1. Copy the `custom_components/emaux_spv150` folder into your Home Assistant `config/custom_components/`.
2. Restart Home Assistant.

## Initial setup

[![Open your Home Assistant instance and start setting up the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=emaux_spv150)

Or **Settings > Devices & Services > Add integration > Emaux SPV150**, then:

1. Enter the pump's IP address.
2. (optional) Pick the smart plug or switch that powers the pump.
3. (optional) Pick the grid-power sensor used by the solar mode.

The pump is contacted before the entry is created (skipped while the selected switch is off). The same IP address
cannot be added twice. To change the IP address or the entities later, use **⋮ > Reconfigure**.

## Configurable options

**Settings > Devices & Services > Emaux SPV150 > Configure**:

| Option | Description | Default |
|--------|-------------|---------|
| IP address | Pump IP address | — |
| External switch | Plug or switch powering the pump: while it is off, the pump is not polled | — |
| Grid-power sensor | Power sensor used by the solar mode | — |
| Setpoint (W) | Grid power the solar mode aims for | 0 W |
| Dead-band lower bound (W) | Below this grid power: speed up | 0 W |
| Dead-band upper bound (W) | Above this grid power: slow down | 100 W |
| Max step up (RPM) | Largest speed increase in one step | 300 RPM |
| Max step down (RPM) | Largest speed decrease in one step | 30 RPM |
| Priming delay (s) | Wait after the switch turns the pump on, before the solar mode acts | 120 s |
| Speed-change interval (s) | Minimum time between two speed changes (0 = no limit) | 60 s |

The polling interval (5–60 s, default 30 s), the request timeout (1–30 s, default 5 s) and the min/max speeds of
the solar mode are number entities.

## How the solar mode works

At each poll, the regulator compares the grid power with the dead band and moves the pump speed by one step:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/regulation-dark.svg">
  <img alt="Speed change per regulation step as a function of grid power: +300 RPM at most when exporting, nothing inside the dead band, −30 RPM at most when importing." src="img/regulation-light.svg">
</picture>

- **Exporting** (grid power below the dead band): the pump speeds up by `setpoint − grid power` RPM, at least 10,
  at most the max step up. More surplus, bigger step.
- **Inside the dead band**: nothing changes.
- **Importing** (above the dead band): the pump slows down by `grid power − setpoint` RPM, at least 10, at most the
  max step down.
- The new speed is kept between the min and max solar speeds and rounded to 10 RPM.

With the settings of the chart (setpoint 50 W, dead band −50…+50 W, max steps +300 / −30 RPM):

| Grid power | −400 W | −150 W | −100 W | −50…+50 W | +60 W | +200 W |
|---|---|---|---|---|---|---|
| Speed change | +300 RPM | +200 RPM | +150 RPM | none | −10 RPM | −30 RPM |

The dead band keeps the pump from hunting around the setpoint. A large up step and a small down step make it
catch a surplus fast and give it back gently when a cloud passes. A step is applied only when all of these hold:

- the control mode is `Solar` and the pump is running;
- the priming delay has elapsed since the external switch turned the pump on;
- the grid-power sensor has a numeric value reported less than 60 s ago;
- the speed-change interval has elapsed since the last change (60 s by default): at most one step per minute.

## Created entities

Default entity IDs on a new installation (they follow the device and entity names):

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.emaux_spv150_power` | Sensor | Power draw (W) |
| `sensor.emaux_spv150_flow_rate` | Sensor | Flow rate (shown in L/min) |
| `sensor.emaux_spv150_energy` | Sensor | Cumulated energy (kWh) |
| `sensor.emaux_spv150_uptime` | Sensor | Uptime (h), diagnostic |
| `number.emaux_spv150_speed` | Number | Current speed (RPM), slider |
| `number.emaux_spv150_speed_preset` | Number | Speed preset (1/2/3), slider |
| `number.emaux_spv150_setpoint` | Number | Solar mode setpoint (W) |
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

## Examples

Run the pump on solar surplus during the day, through the smart plug that powers it
(replace `switch.pool_pump_plug` with yours):

```yaml
automation:
  - alias: "Pool pump: start on solar in the morning"
    triggers:
      - trigger: time
        at: "10:00:00"
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.pool_pump_plug
      - action: select.select_option
        target:
          entity_id: select.emaux_spv150_control_mode
        data:
          option: solar

  - alias: "Pool pump: stop in the evening"
    triggers:
      - trigger: time
        at: "19:00:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.pool_pump_plug
```

Fall back to a fixed speed when the solar production stays low (replace `sensor.solar_power` with yours):

```yaml
automation:
  - alias: "Pool pump: fixed speed when the sun is gone"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.solar_power
        below: 300
        for: "00:15:00"
    actions:
      - action: select.select_option
        target:
          entity_id: select.emaux_spv150_control_mode
        data:
          option: manual
      - action: number.set_value
        target:
          entity_id: number.emaux_spv150_speed
        data:
          value: 1500
```

## How data is updated

- The pump is polled every 30 s by default (5–60 s, adjustable at runtime) with a single HTTP request.
- After a command (speed, preset, run/stop) the pump is read again once it has settled (2 s).
- A change of the external switch triggers an immediate read.
- While the external switch is off, the pump is not polled: its values show as unavailable and nothing is reported as an error.
- A pump that does not answer is not an error while its switch is not on (off, unknown or unavailable, as a smart plug is for a while after every Home Assistant restart), nor during the 3 minutes after the switch turns on, while the pump joins Wi-Fi. Otherwise it is reported: logged once, values unavailable.

## Supported devices

Emaux SPV150 variable-speed pumps with the built-in Wi-Fi module, the ones you can drive from the Emaux mobile app.
The integration talks to the same local web server. Other Emaux models have not been tested.

<img alt="The Emaux mobile app showing the pump speed, power and the three speed presets" src="img/page_web.jpeg" width="240">

## Known limitations

- The pump's web interface has no authentication and uses plain HTTP: keep it on a trusted local network.
- One pump per Home Assistant instance: entity unique IDs are not yet prefixed per config entry.
- The `Off` mode only disables the solar regulation; it does not stop the pump (use the run/stop switch).
- Energy is computed by the integration from the power read at each poll, so it is an estimate.
- The priming wait only applies when the external switch turns the pump on, not after a Home Assistant restart.
- A pump that stays silent while its external switch is unavailable is not reported: the integration cannot tell whether it is powered.

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

- **Diagnostics**: **Settings > Devices & Services > Emaux SPV150 > ⋮ > Download diagnostics** (the pump address is removed). Attach the file to an [issue](https://github.com/0jety0/emaux_spv150/issues/new/choose).

## Removal

1. **Settings > Devices & Services > Emaux SPV150 > ⋮ > Delete**.
2. In HACS, open the integration and choose **Remove** (manual install: delete `config/custom_components/emaux_spv150`).
3. Restart Home Assistant.

## Development

Tooling: [mise](https://mise.jdx.dev/) (tool versions and tasks), [uv](https://docs.astral.sh/uv/) (environment and
dependencies), [ruff](https://docs.astral.sh/ruff/) (lint and format) and [mypy](https://mypy.readthedocs.io/) in
strict mode, as in Home Assistant core.

```bash
mise run install        # venv + dev dependencies (from uv.lock)
mise run lint           # ruff check + ruff format --check
mise run typecheck      # mypy --strict
mise run test           # pytest
mise run docs           # redraw the solar mode chart from the regulator code
```

CI (GitHub Actions) runs the same lint, type check and tests, plus `hassfest` and the HACS validation.
Changes are listed in the [CHANGELOG](CHANGELOG.md).

## License

[MIT](LICENSE).
