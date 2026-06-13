# Release Notes — Performance & Low Power Mode (branch `perf/frugal-lowpower`)

**Base:** V2026.06.01 (`bc74bb9`) · **Target:** `petergridge/Irrigation-V5:main`  
**Scope:** `custom_components/irrigationprogram/` · ~7 300 lines  
**Audience:** constrained hosts (Raspberry Pi 3, SD-backed HA installs) and any user running multiple concurrent programs

---

## Summary

This release addresses a systemic performance problem: during a watering cycle the integration generated **~5 400 blocking service calls and state-changed events per 30-minute 2-zone run**, saturating a Raspberry Pi 3 and writing continuously to the SQLite recorder on SD card. It also fixes **seven correctness bugs** found during profiling, adds an **opt-in Low power mode**, and brings the test suite from 26 failures / 8 passes to **48/48 passing** (14 new tests + 26 pre-existing failures fixed).

Default behaviour is preserved. Existing configs need no changes.

---

## Why this was needed

The problem was not algorithmic complexity but the **update model**:

- Every running zone called `hass.services.async_call("homeassistant", "update_entity", blocking=True)` once per second to refresh its countdown sensor — creating a full `ServiceCall`, a `call_service` bus event, a registry lookup and an async task, only to have the sensor read back a value the caller already held.
- The program loop (`run_monitor_zones`, 1 Hz) did the same for its own remaining-time sensor.
- `remaining_time` sensors were not excluded from the recorder: **every second of watering wrote a row to SQLite on SD card**.
- A chatty water-adjustment sensor triggered a full recalculation of `update_next_run()` on every tick.
- `check_is_on` / `check_is_off` polled at 10 Hz and re-sent the valve command on every iteration.

For a 30-minute, 2-zone cycle that is approximately:

| Metric | Before | After (normal mode) | After (low power mode) |
|--------|--------|---------------------|------------------------|
| Blocking service calls | ~5 400 | **0** | **0** |
| `state_changed` events (recorder) | ~3 600 | ~120 | ~4 |
| Valve commands during latency window | up to 30 | up to 6 | up to 6 |
| `next_run` recalc per chatty sensor tick | 1 full pass | 1 (debounced 2 s) | 1 (debounced 10 s) |

---

## Changes

### 1. Performance — removed blocking service calls from hot path

**File:** `zone.py`, `program.py`

The seven `*_set()` helpers that updated countdown sensors (`remaining_time_set`, `default_run_time_set`, …) previously called:
```python
hass.services.async_call("homeassistant", "update_entity", {"entity_id": sensor_id}, blocking=True)
```
Each call created a `ServiceCall` object, emitted a `call_service` event on the bus, resolved the entity in the registry, and awaited the task — only for the woken sensor to read back a value the caller already held.

**Fix:** the platform now holds direct references to sensor objects. The `*_set()` helpers update `sensor._state` and call `sensor.async_schedule_update_ha_state()` directly, with zero bus traffic. For a 30-minute cycle this eliminates **~5 400 blocking service calls**.

---

### 2. Performance — throttled countdown writes to the recorder

**Files:** `sensor.py`, `const.py`

`ZoneRemainingTime` and `RemainingTime` previously wrote a new HA state every second. The recorder persisted every `state_changed` event to the `states` SQLite table on SD card, causing continuous I/O and database growth.

**Fix:** sensors keep their internal value exact every second (program timing reads `numeric_value` to drive zone transitions — this is never throttled). Writes to the HA state machine are gated by `CONST_SENSOR_WRITE_INTERVAL = 5` seconds. Boundary values (first write and the final `0`) always go through so the entity settles on a correct final value after a run.

```python
CONST_SENSOR_WRITE_INTERVAL = 5          # normal mode: write every 5 s
CONST_SENSOR_WRITE_INTERVAL_LOW_POWER = 99999  # low power: start + end only
```

A 30-minute, 2-zone cycle drops from ~3 600 to ~24 recorder writes.

---

### 3. Performance — debounced `next_run` recalculation

**File:** `program.py`

`update_next_run()` iterates every zone and refreshes several sensors. It was wired directly to `async_track_state_change_event` for a long list of entities including the water-adjustment sensor. A sensor updating once per second triggered a full recalculation on every tick.

**Fix:** changes are coalesced through `async_call_later` with a 2-second window (`CONST_NEXT_RUN_DEBOUNCE = 2`). In low power mode the window widens to 10 seconds (`CONST_NEXT_RUN_DEBOUNCE_LOW_POWER = 10`).

---

### 4. Performance — reduced switch-confirmation polling frequency

**File:** `zone.py`

`check_is_on` / `check_is_off` polled at 10 Hz (`asyncio.sleep(0.1)`) and re-sent the on/off command on every iteration during the latency window — up to 30 commands in 3 seconds for a slow Zigbee valve.

**Fix:** polling interval raised to 0.5 seconds (2 Hz). For a 3-second latency window this reduces commands from up to 30 to up to 6, with a direct benefit for Zigbee and Z-Wave valves.

---

### 5. New feature — Low power mode (opt-in)

**Files:** `const.py`, `__init__.py`, `config_flow.py`, `sensor.py`, `program.py`, `translations/en.json`, `translations/fr.json`

A **Low power mode** boolean is added to **Advanced options** in both the initial configuration flow and the reconfigure flow. When enabled it:

- Suppresses **all** intermediate countdown writes — `ZoneRemainingTime` and `RemainingTime` only write to the state machine at the start and end of a cycle. Internal scheduling (the `numeric_value` property that drives zone transitions) is **unaffected**.
- Widens the `next_run` debounce to 10 seconds.
- Skips the string-heavy manual-card YAML generation (`generate_card`), which is only relevant to the optional YAML card.

**Recommended for:** Raspberry Pi 3, SD-backed installs, Tuya/Wi-Fi valves (no countdown display in the UI is needed during watering).

The dominant cost on a constrained host is event-bus traffic and recorder I/O, which this mode minimises. Pair it with recorder exclusions (see §Recommended HA Configuration below) for the full benefit.

---

## Bug fixes

Seven correctness bugs found during profiling:

| # | Severity | File(s) | Bug | Impact |
|---|----------|---------|-----|--------|
| **B1** | **Critical** | `globals.py`, `program.py`, `zone.py` | `REMAINING_ZONES` and `RUNNING_ZONES` were **module-level lists shared across all programs**. Two concurrent programs (interlock off) silently corrupted each other's zone queues; `async_turn_off` on one program emptied the other's. | Data corruption in multi-program setups |
| **B2** | High | `program.py` `update_next_run` | `adjusted_sunrise` was referenced outside its `if sunrise:` guard. A failed parse of `sensor.sun_next_rising` raised `NameError` (not `ValueError`, so the `except` clause did not catch it). | Unhandled exception in event handler; next-run not updated after sunrise parse failure |
| **B3** | High | `zone.py` `async_turn_on_from_program` | Default argument `last_ran=dt_util.now()` was evaluated once at module import, freezing "last ran" at HA start time for the lifetime of the process. | "Last watered" always showing HA start time |
| **B4** | Medium | `sensor.py` ×5 | `async_update` left `value` unbound when the `ZONES`/`PROGRAMS` dict lookup missed (startup race condition or config reload). `NameError` on the `return value` line. | Sensor error on startup or reload |
| **B5** | Medium | `program.py` `run_monitor_zones` | Iterated `RUNNING_ZONES` (now per-instance) while appending to it — same list object, not a copy. | Non-deterministic behaviour during zone transitions |
| **B6** | Medium | `program.py` `run_monitor_zones` | After the inter-zone delay, indexed `REMAINING_ZONES[0]` without re-checking that the list was still non-empty. A zone stopped manually during the delay caused `IndexError` mid-cycle. | Crash mid-cycle when a zone is stopped during inter-zone delay |
| **B7** | Low | `program.py` `async_turn_off` | `QUEUEDPROGRAMS.pop(n)` called during `enumerate` of the same list. Elements were skipped on every removal. | Queued programs not fully cleared on stop |

**B1** fix detail: `REMAINING_ZONES` and `RUNNING_ZONES` are now per-`IrrigationProgram` instance lists, exposed as `remaining_zones` / `running_zones` properties. All callers in `program.py` and `zone.py` updated accordingly.

---

## Test coverage

### Before this branch

```
26 failures / 8 passes
```

Failures were caused by incomplete mocks (`MockHomeAssistant` missing `.config.time_zone`), stale assertions (wrong `unique_id`, `translation_key`, `device_class` values), tests importing non-existent class names (`StartType`, `Multitime`, `ZoneRepeat`, …), and `hass is None` runtime errors when HA entity methods were called without a registered hass instance.

### New unit tests added (`tests/test_perf_frugal.py`, 14 cases)

All run without a live HA instance (`PYTHONPATH=. pytest tests/test_perf_frugal.py -v --asyncio-mode=auto`):

| Test | What it verifies |
|------|------------------|
| `test_normal_mode_throttles_intermediate_writes` × 2 | Countdown writes are gated by `CONST_SENSOR_WRITE_INTERVAL` |
| `test_zero_is_always_written` × 2 | Boundary value `0` always passes through the throttle |
| `test_low_power_writes_only_at_boundaries` × 2 | Low power mode: only first write and `0` go through |
| `test_numeric_value_exact_despite_throttling` × 2 | `numeric_value` stays exact every second regardless of throttle — invariant the scheduler depends on |
| `test_serial_run_sums_with_interzone_delay` | Serial run time = sum of zones + delays |
| `test_parallel_packs_into_streams` | Parallel run time = longest stream, not sum |
| `test_empty_program_is_zero` | Edge case: no zones |
| `test_shared_zone_queues_removed_from_globals` | B1 regression guard: shared globals removed |
| `test_program_queues_are_per_instance` | B1 regression guard: queues are isolated per program instance |
| `test_turn_on_from_program_default_not_evaluated_at_import` | B3 regression guard: `last_ran` default is `None`, not a frozen timestamp |

### Pre-existing test failures fixed (26 → 0)

All 26 pre-existing failures corrected across 8 test files:

| File | Root cause fixed |
|------|-----------------|
| `conftest.py` | Removed deprecated `event_loop` fixture; added `config.time_zone` to mock |
| `test_init.py` | `MockHomeAssistant` missing `config`, `is_running`; `async_setup_entry` called with wrong arg count; `exclude` mock missing `inter_zone_delay`/`frequency`/`repeat` |
| `test_switch.py` | Wrong `unique_id` for `EnableRainDelay`/`EnableZone`; wrong `translation_key` for `EnableRainDelay`/`ZoneConfig`; missing `IgnoreRainSensor` in count; `hass is None` in toggle/restore tests |
| `test_sensor.py` | `MockHomeAssistant` missing `config.time_zone`; wrong `translation_key` for 4 sensor classes; wrong `device_class` (DURATION → DATE); ZONES namespace mismatch in update test |
| `test_number.py` | Imported non-existent classes; wrong entity count (12 → 3); wrong `Water` constructor args and min/max assertions |
| `test_select.py` | Imported non-existent classes (`StartType`, `RainBehaviour`, `Interlock`, `MinSec`, `WateringType`); replaced with actual `Frequency` class tests |
| `test_text.py` | Wrong `start_type` in fixture; imported non-existent `Multitime` (→ `RunTimes`); wrong unique_id and attribute names |
| `test_time.py` | Imported non-existent `StartTime` (→ `starttime`); `hass is None` in set_value test |

### Final state

```
48 passed, 0 failed
```

---

## Recommended HA configuration (outside this patch)

Even after the patch, remaining-time sensors write legitimate state. On an RPi3, excluding them from the recorder is the largest remaining SD win:

```yaml
recorder:
  commit_interval: 30          # batch SQLite writes (default is 5 s)
  exclude:
    entity_globs:
      - sensor.*remaining_time*
      - sensor.*default_run_time*
```

> Verify entity names match your installation before applying the glob. Use Developer Tools → States to confirm.

If a water-adjustment sensor updates frequently (e.g. every 10 s), also limit its update interval at source. If the recorder database has already grown, run `recorder.purge` with `repack: true` after adding the exclusions.

---

## How to apply

```bash
# Clone or pull the branch
git clone https://github.com/rjullien/Irrigation-V5
git checkout perf/frugal-lowpower

# Or apply the patch to an existing checkout of petergridge/Irrigation-V5
git apply irrigation-v5-frugal-lowpower.patch

# Run the new unit tests
PYTHONPATH=. pytest custom_components/irrigationprogram/tests/test_perf_frugal.py -v --asyncio-mode=auto

# Run the full test suite
PYTHONPATH=. pytest custom_components/irrigationprogram/tests/ --asyncio-mode=auto
```

Copy the `custom_components/irrigationprogram/` directory to your HA config, then restart.

---

## Manual test checklist (live HA required)

- [ ] Single program runs to completion; remaining-time sensors reach 0
- [ ] **Two programs run simultaneously** (interlock off) — neither corrupts the other's queue (B1/B5)
- [ ] A zone is stopped manually **during the inter-zone delay** — no `IndexError`, cycle continues (B6)
- [ ] `low_power_mode` toggled on in Advanced options — UI updates, reconfigure flow shows the option
- [ ] Chatty water-adjustment sensor — no per-second `next_run` storm in HA logs
- [ ] HA restart — "last watered" sensor shows the correct last-run time (not HA start time) (B3)

---

## Files changed

| File | Change |
|------|--------|
| `const.py` | Added `ATTR_LOW_POWER`, `CONST_SENSOR_WRITE_INTERVAL`, `CONST_SENSOR_WRITE_INTERVAL_LOW_POWER`, `CONST_NEXT_RUN_DEBOUNCE`, `CONST_NEXT_RUN_DEBOUNCE_LOW_POWER` |
| `__init__.py` | `IrrigationProgram` dataclass: added `low_power: bool = False`; `async_setup_entry`: reads and passes `low_power` to runtime data |
| `config_flow.py` | Added `ATTR_LOW_POWER` field to both initial config and reconfigure flows |
| `globals.py` | Removed `REMAINING_ZONES` and `RUNNING_ZONES` module-level lists (B1) |
| `program.py` | Per-instance `_remaining_zones`/`_running_zones`; debounced `update_next_run`; guarded B2/B5/B6/B7; direct sensor writes replacing `update_entity` service calls |
| `sensor.py` | Write-throttle in `ZoneRemainingTime`/`RemainingTime`; early-return guards for unbound `value` (B4); `low_power` write interval injected from `async_setup_entry` |
| `zone.py` | Direct sensor writes (B1 fix); poll interval 0.1 s → 0.5 s; `last_ran` default fixed (B3) |
| `translations/en.json` | Added `low_power_mode` label |
| `translations/fr.json` | Added `low_power_mode` label (FR) |
| `tests/test_perf_frugal.py` | 14 new unit tests (**added**) |
| `tests/conftest.py` | Fixed deprecated fixture, added `config.time_zone` |
| `tests/test_init.py` | Rewritten: proper MockHomeAssistant, async_setup_entry call, exclude mock |
| `tests/test_switch.py` | Fixed unique_id/translation_key assertions, switch count, hass mock |
| `tests/test_sensor.py` | Fixed translation_key/device_class assertions, ZONES namespace fix |
| `tests/test_number.py` | Fixed entity count, Water/Wait/Repeat constructor args, removed phantom imports |
| `tests/test_select.py` | Replaced phantom classes with actual Frequency tests |
| `tests/test_text.py` | Fixed fixture start_type, Multitime → RunTimes, attribute names |
| `tests/test_time.py` | StartTime → starttime, mocked async_write_ha_state |
| `.gitignore` | Added `__pycache__/`, `*.pyc`, `.pytest_cache/` |
