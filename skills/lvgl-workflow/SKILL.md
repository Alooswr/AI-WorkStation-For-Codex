---
name: lvgl-workflow
description: Workflow for integrating, configuring, building, and debugging LVGL v9 UI projects on embedded targets and host simulators. Use when tasks involve `lv_conf.h`, display/input driver hookup, `lv_timer_handler`, tick/flush behavior, blank screens, touch/input issues, LVGL CMake presets, LVGL tests, or ESP-IDF integration with `lvgl/lvgl` or `espressif/esp_lvgl_port`. Do not use for non-LVGL GUI work, generic ESP-IDF build failures, or Keil-only compile triage.
---

# LVGL Workflow

Use this skill to run a consistent LVGL bring-up and triage flow, especially for display blank-screen, touch/input no-response, render performance, and build-system issues.

## Use When

- The issue is LVGL configuration, display flush, tick/timer handling, input
  device callbacks, UI update behavior, simulator runs, or LVGL performance.
- LVGL is integrated in ESP-IDF; pair this skill with `esp-idf-workflow` for
  `idf.py` environment/build/flash mechanics.

## Do Not Use When

- The task is not LVGL-specific.
- The failure is only ESP-IDF environment/toolchain setup; use
  `esp-idf-workflow`.
- The failure is only Keil compile/link triage; use `keil-rebuild-debug`.

## Local Baseline (This Machine)

1. LVGL repo path: `%USERPROFILE%\work\LVGL\lvgl`
2. Observed git describe: `v9.5.0-120-gcf300e48a`
3. Header version macro: `LVGL_VERSION_MAJOR 9`, `LVGL_VERSION_MINOR 6`, `LVGL_VERSION_PATCH 0`, `LVGL_VERSION_INFO "dev"`

Re-check quickly before work:
```powershell
Set-Location %USERPROFILE%\work\LVGL\lvgl
git describe --tags --always
git status --short --branch
```

## Core Bring-Up Sequence

1. Configure LVGL:
- Copy `lv_conf_template.h` to `lv_conf.h`.
- Set the first `#if 0` in `lv_conf.h` to `#if 1`.
2. Initialize runtime:
- `lv_init()`
- `lv_tick_set_cb(...)`
3. Register display:
- `lv_display_create(...)`
- `lv_display_set_buffers(...)`
- `lv_display_set_flush_cb(...)`
4. Register input device(s):
- `lv_indev_create()` and `lv_indev_set_read_cb(...)`
5. Run LVGL tasks:
- Standard loop: call `lv_timer_handler()` periodically.
- ESP-IDF with `esp_lvgl_port`: handler is run in background task after `lvgl_port_init()`/`bsp_display_start()`.

## Workflow Paths

1. LVGL as library in CMake project:
- Use `add_subdirectory(lvgl)` and set `LV_BUILD_CONF_PATH`/`LV_BUILD_CONF_DIR` as needed.
- Use presets (`windows-base`, `windows-kconfig`, `linux-base`, `linux-kconfig`) when working in the LVGL repo itself.
2. LVGL with ESP-IDF:
- Preferred helper: `idf.py add-dependency "espressif/esp_lvgl_port^2.3.0"`.
- Direct component: `idf.py add-dependency "lvgl/lvgl^9.*"`.
3. LVGL on PC via SDL:
- Enable `LV_USE_SDL 1`, link SDL2, and use SDL display/input creators for simulator runs.

## Triage Priority

1. `idf.py`/toolchain/build error:
- Fix environment and build settings first.
2. Screen stays blank:
- Verify `flush_cb` is called and `lv_display_flush_ready(...)` is executed.
- Verify color format and draw buffer configuration are coherent.
3. UI does not update / no animation:
- Verify tick source is running (`lv_tick_set_cb` or equivalent tick feed).
- Verify `lv_timer_handler()` cadence or background LVGL task state.
4. Touch/key input not working:
- Verify indev read callback and coordinate/state values.
5. Performance issues (low FPS/high latency):
- Enable logs, sysmon, and profiler to confirm bottleneck before changing configuration.

## Debug Modules To Enable

- Logging: `LV_USE_LOG`, `LV_LOG_LEVEL`, `LV_LOG_PRINTF`
- System monitor: `LV_USE_SYSMON`, `LV_USE_PERF_MONITOR`, `LV_USE_MEM_MONITOR`
- Profiler: `LV_USE_PROFILER` + built-in profiler config, then inspect the
  captured profiler output directly or with project-local tooling.

## References To Load On Demand

1. Commands and common build/test actions:
- `references/command-recipes.md`
2. Integration and troubleshooting signatures:
- `references/integration-triage.md`

Load only the file needed for the current task.
