# Integration Triage

## Local Observation (2026-04-14)

- Repo: `%USERPROFILE%\work\LVGL\lvgl`
- `git describe --tags --always`: `v9.5.0-120-gcf300e48a`
- `lv_version.h`: `9.6.0-dev`

Treat this tree as post-v9.5 development state.

## High-Value Failure Signatures

1. Screen remains blank.
- Typical causes:
  - `lv_display_set_flush_cb()` not set.
  - `flush_cb` forgets `lv_display_flush_ready(...)`.
  - Wrong buffer size or color format mismatch.
- First checks:
  - Confirm `flush_cb` call count.
  - Confirm color depth and buffer bytes-per-pixel assumptions.

2. UI freezes or animations never progress.
- Typical causes:
  - Missing/invalid tick source.
  - `lv_timer_handler()` not called or called too rarely.
- First checks:
  - Confirm `lv_tick_set_cb(...)` or equivalent tick update exists.
  - Confirm main loop cadence around 5-10ms.

3. Touch/key/encoder input not working.
- Typical causes:
  - `lv_indev_set_read_cb(...)` not registered.
  - Wrong state transitions or coordinate mapping.
- First checks:
  - Log indev callback values.
  - Validate calibration and axis mapping.

4. ESP-IDF project behaves differently from bare-metal examples.
- Typical causes:
  - Using `esp_lvgl_port` but still manually managing LVGL loop in conflicting way.
  - `sdkconfig`/`sdkconfig.defaults` drift.
- First checks:
  - Confirm initialization path (`bsp_display_start()` / `lvgl_port_init()`).
  - Confirm whether a background LVGL task already handles `lv_timer_handler()`.

5. Performance regression (low FPS, high CPU, stutter).
- First checks:
  - Enable `LV_USE_PERF_MONITOR` and `LV_USE_MEM_MONITOR`.
  - Enable profiler (`LV_USE_PROFILER`) and process trace with `scripts/trace_filter.py`.
  - On ESP32, review optimization and memory options before changing UI logic.

## Debug Configuration Snippets

```c
#define LV_USE_LOG 1
#define LV_LOG_LEVEL LV_LOG_LEVEL_INFO
#define LV_LOG_PRINTF 1
```

```c
#define LV_USE_SYSMON 1
#define LV_USE_PERF_MONITOR 1
#define LV_USE_MEM_MONITOR 1
```

```c
#define LV_USE_PROFILER 1
```

## ESP32-Specific Notes (From LVGL Docs)

- Performance-focused compile option can materially improve speed:
  - `CONFIG_COMPILER_OPTIMIZATION_PERF=y`
- IRAM placement option for LVGL fast paths:
  - `CONFIG_LV_ATTRIBUTE_FAST_MEM_USE_IRAM=y`
- If using PPA and seeing alignment-related crashes:
  - `CONFIG_LV_DRAW_BUF_ALIGN=64`

## Source Links

- https://docs.lvgl.io/master/getting_started/learn_the_basics.html
- https://docs.lvgl.io/master/debugging/log.html
- https://docs.lvgl.io/master/debugging/sysmon.html
- https://docs.lvgl.io/master/debugging/profiler.html
- https://docs.lvgl.io/master/integration/chip_vendors/espressif/tips_and_tricks.html
