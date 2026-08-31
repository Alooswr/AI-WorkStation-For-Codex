---
name: embedded-skill-router
description: Route embedded firmware tasks to the minimum matching local skill(s). Use as the only embedded entrypoint when a request involves firmware build, flash/download, serial logs, peripheral bring-up, Keil MDK, ESP-IDF, LVGL, serial HMI, hardware evidence, or embedded troubleshooting. Do not use this skill to implement the task directly; use it to select the narrow specialty skill(s), adding embedded-debug-verification only when runtime or hardware evidence matters.
---

# Embedded Skill Router

Use this as the embedded task entrypoint. It gives routing advice only; it does
not replace the selected specialty skill and should not carry implementation
details itself.

## Use When

- The request is an embedded firmware task and more than one local skill may
  apply.
- The request is short or ambiguous, such as "build", "flash", "抓串口日志", or
  "烧录测试", and the correct embedded workflow must be chosen first.

## Do Not Use When

- The task is not embedded firmware or hardware related.
- A non-embedded system skill is clearly named by the user, such as
  `skill-creator` or `skill-installer`.

## Route

1. Compile/rebuild/build-log triage (`.uvprojx`, Keil): `keil-rebuild-debug`
2. ESP-IDF setup/build/flash/monitor/triage (`idf.py`, ESP-IDF project): `esp-idf-workflow`
3. LVGL integration/build/porting/triage (`lv_conf.h`, `lv_timer_handler`, display/input): `lvgl-workflow`
4. M&F/DaCai serial screen (UART frame/CRC/notify): `mf-serial-hmi`
5. Repo sync + Git delivery + Saleae checklist + multi-step daily maintenance: `embedded-daily-maintenance`
6. Runtime/hardware evidence, root-cause experiments, flash/log proof, or completion gate: add `embedded-debug-verification`

## Selection Rules

- Choose the narrowest skill that fully covers the core task.
- If both domain and workflow skills apply, use the domain skill first, then the workflow skill.
- If LVGL is inside an ESP-IDF project, use both `esp-idf-workflow` and `lvgl-workflow`.
- If runtime/hardware behavior is being diagnosed or claimed complete, also apply `embedded-debug-verification` as a cross-cutting evidence gate.
- Keep the active skill set minimal.
