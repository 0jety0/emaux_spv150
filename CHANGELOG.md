# Changelog

## [2.1.0] — 2026-06-06

### Features

- **Configurable request timeout**: new `number` entity "Request timeout" (1–30 s, default 5 s), adjustable at runtime like the polling interval. The pump's embedded CGI server is slow/flaky over the LAN, so the default timeout is raised from 2 s to 5 s to reduce false `timed out`. Both the polling interval and the timeout are adjustable from the UI so the pump is not overloaded.

### Tooling & project

- **Migrated to `uv` + `ruff`**: `pyproject.toml` (PEP 621) replaces `Pipfile`; `ruff` (lint + format) replaces `black` + `isort`; `pytest` config moved into `pyproject` (`pytest.ini` removed); `uv.lock` committed. Dev/CI tooling only — no impact on the HA runtime.
- **GitHub Actions CI**: `ruff check` + `ruff format --check` + `pytest` (via `uv`), in addition to `hassfest` and HACS validation.
- **License**: [PolyForm Noncommercial 1.0.0](LICENSE) (personal / non-commercial use).

### Bug fixes

- **`api.py` — invalid JSON**: `json.JSONDecodeError` is now caught (non-JSON response, error HTML, empty body) and returns `{}` instead of raising an unhandled exception that stopped polling.
- **`api.py` — URL injection**: the command key is encoded (`urllib.parse.quote`) before being inserted into the URL; the value is forced to `int`.
- **`api.py` — information leak**: the pump IP no longer appears in `ERROR` logs (moved to `DEBUG`).
- **`coordinator.py` — spurious reload**: adjusting a local `number` parameter (setpoint, dead band, steps, RPM, interval) no longer reloads the whole integration. The `update_listener` only reloads on a connection change (IP / switch / grid entity). Cumulated energy and uptime are no longer reset on every adjustment.
- **`coordinator.py` / `number.py` — solar invariants**: `rpm_min_solar` ≤ `rpm_max_solar` **and** `dead_band_lower` ≤ `dead_band_upper` are guaranteed; the setters auto-clamp the value (previously only the config flow validated the dead band).
- **`__init__.py` — race-free reload listener**: the reload decision compares connection settings (IP / switch / grid entity) instead of a flag, removing a race window; a value changed via the options form now applies live (no reload).
- **`config_flow.py` — `grid_power_entity` loss**: the options form falls back to `entry.data` (like the switch), avoiding wiping the grid entity when editing options.
- **`sensor.py`**: a failed energy restore is logged (`warning`) instead of being silently swallowed.
- **`RunningStatus`**: normalized via `str()`, so detection works whether the pump returns `"1"` or `1`.
- **Options flow**: a `switch_entity`/`grid_power_entity` set to `None` no longer breaks the options form.

### Technical improvements

- **`PumpStatus` DTO** (`models.py`): the pump data is converted once into a typed object; no more scattered `float(...)` / string comparisons across entities.
- **`SolarRegulator` + `SolarControllerConfig`** (`solar.py`): the P-controller is extracted from the coordinator into a pure, testable unit (SRP).
- **`NumberEntityDescription` / `SensorEntityDescription`**: the `number` and `sensor` entities use the idiomatic HA pattern (dataclass); the three parallel structures in `number.py` are merged into a single source of truth (DRY).
- **`GRID_POWER_STALENESS_SECONDS` constant**: the grid-entity staleness threshold is no longer a magic number.
- **`config_flow.py`**: IP / hostname format validation (`invalid_host`) before the connection test, across all three flows (initial, reconfigure, options).
- **`coordinator` typed** `DataUpdateCoordinator[PumpStatus]`.
- Removed `utils.py` (no longer needed).
- **Tests**: 43 pytest tests (solar regulator, API + error cases, energy/uptime, reconfigure, RPM & dead-band invariants, `RunningStatus` normalization, configurable timeout). The orphaned `enable_maintenance` test was removed.
- `Pipfile`: removed `re` (stdlib module, not a package) and `pydantic` (unused); explicit test dependencies.

---

## [2.0.1] — 2026-05-02

### Bug fixes

- **Entities grayed out when pump is powered off**: when the external switch turns OFF, entities now become `unavailable` (grayed out) instead of showing zero values with an orange warning icon. A new `pump_switch_off` flag on the coordinator is checked in the `available` property of all entities.

---

## [2.0.0] — 2026-04-17

### Features

#### Quality & architecture (HA Quality Scale Bronze/Silver/Gold)
- **Single device in HA**: all entities grouped under a single "Emaux SPV150" device
- **Long-term statistics**: `CurrentWatts` and `CurrentGPM` use `SensorStateClass.MEASUREMENT`
- **Reconfigure without removal**: a "Reconfigure" button to change IP/switch without reinstalling
- **Editable options**: IP, switch, polling interval and solar parameters via "Configure"
- **Connection test**: the pump is pinged before the configuration is validated
- **Duplicate protection**: the same IP cannot be added twice
- **Device classes**: `SensorDeviceClass.POWER` on watts, `SensorDeviceClass.VOLUME_FLOW_RATE` on GPM
- **Translations**: `strings.json` + `translations/en.json`

#### Monitoring
- **Cumulated energy** (`sensor.energy`): accumulated kWh, `SensorStateClass.TOTAL_INCREASING`, compatible with the Energy dashboard
- **Uptime** (`sensor.uptime`): hours since the last start
- **Configurable polling interval**: 5 / 15 / 30 / 60 seconds (default: 30 s)

#### Speed control — protection and sequencing
- **Configurable throttle** (`speed_change_interval`): minimum interval between two speed changes (default: 60 s)
- **Priming on physical start**: on power-on via the external switch (OFF→ON), wait for priming to finish (default: 120 s) before enabling solar regulation. In all other cases, regulation applies immediately.

#### Solar mode — P-controller with dead band
- **Mode selector** (`select.control_mode`): `Off` / `Manual` / `Solar` — **persisted across restarts**
- **Configurable grid-power entity**: accepts any HA entity
- **Proportional (P) controller** centred on a configurable setpoint:
  - `error = |grid_power - setpoint|`
  - `step = min(step_max, max(10, int(error)))` — proportional to the delta, capped
  - Below the lower bound → speed up
  - Above the upper bound → speed down
  - Inside the dead band → no change
- **Stale-data protection**: if the grid-power entity has not changed for more than 60 s, regulation is suspended
- **Full persistence**: mode, setpoint, dead band and steps survive restarts
- **UI-adjustable parameters** (`number` entities, direct input):
  - Setpoint (W) — default: 0 W
  - Dead-band lower bound (W) — default: 0 W
  - Dead-band upper bound (W) — default: 100 W
  - Max step up (RPM) — default: 300 RPM
  - Max step down (RPM) — default: 30 RPM
  - Min solar speed (RPM) — default: 1400 RPM
  - Max solar speed (RPM) — default: 3000 RPM

### Technical improvements
- `entry.runtime_data` replaces `hass.data[DOMAIN]`
- `PumpBaseEntity`: shared base class (`DeviceInfo`, `available`, `has_entity_name`)
- `PARALLEL_UPDATES = 1` on all platforms
- `UpdateFailed` when the pump stops responding (entities → `unavailable`, automatic recovery on the next poll)
- `async_config_entry_first_refresh` at startup
- Options flow: persisted keys (mode, solar parameters) are preserved when updating options
- HTTP timeout applied to every request (shared HA session)
- `ConfigEntryNotReady` in `_async_setup` for automatic retry if the pump is offline at boot
- Energy accumulated only when `RunningStatus == 1`
- `NumberMode.BOX` on all input parameters (no slider)
- `restore_energy()` public method on the coordinator

### Bug fixes
- `api.py`: timeout ignored on the shared HA session → now passed on every request
- `coordinator.py`: `UpdateFailed` → `ConfigEntryNotReady` in `_async_setup`
- `coordinator.py`: energy accumulated before the `running` check → fixed
- `coordinator.py`: a falsy `switch_entity=""` fell back to `entry.data` → key-existence check
- `coordinator.py`: an empty response did not raise an error → `UpdateFailed`
- `switch.py`: no refresh after `turn_on` / `turn_off`
- Options flow: saving overwrote the persisted control mode
- Priming: spurious trigger on every configuration reload
- Absolute imports → relative imports
- f-string logs → `%s` format

---

## [1.0.0] — 2025-04-14

- Initial commit: monitoring and control of the Emaux SPV150 pump
- Entities: `CurrentWatts`, `CurrentGPM` (sensors), `CurrentSpeed`, `SpeedSelected` (numbers), `RunningStatus` (switch)
- Polling every 5 seconds via HTTP CGI
- Support for an external switch entity to pause polling
- Config flow UI
- HACS-compatible
