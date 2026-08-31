---
name: embedded-debug-verification
description: Evidence gate and root-cause verification chain for embedded firmware work. Use after the narrow domain skill when a task involves flashing, serial logs, ports, permissions, paths, environment variables, peripheral initialization, timing, power/reset, registers, protocols, black-box SDKs, hardware behavior, or short prompts such as "burn test", "flash and capture logs", "烧录测试", or "抓串口日志". Do not use as a substitute for keil-rebuild-debug, esp-idf-workflow, lvgl-workflow, or mf-serial-hmi; use it to prove or bound runtime behavior before completion.
---

# Embedded Debug Verification

This is a cross-cutting evidence skill. Use the narrow domain skill first when
one applies (`keil-rebuild-debug`, `esp-idf-workflow`, `mf-serial-hmi`,
`lvgl-workflow`), then apply this skill as the debugging and evidence gate.

## Use When

- Hardware, firmware runtime, port, flash, serial, register, timing, protocol,
  or black-box SDK behavior must be diagnosed or proven.
- A task is not complete unless build, flash/download, boot logs, protocol state,
  or physical behavior has been separated and reported clearly.

## Do Not Use When

- The task is only Keil compile/link triage; use `keil-rebuild-debug`.
- The task is only ESP-IDF environment/build/flash mechanics; use
  `esp-idf-workflow`.
- The task is only LVGL integration behavior; use `lvgl-workflow`.
- The task is only M&F/DaCai serial HMI framing/CRC/notify; use `mf-serial-hmi`.

## Operating Rules

- Start from current evidence, not hypotheses. Read code, build logs, serial logs,
  register values, tool output, and project memory before changing code.
- Separate layers: build -> flash/download -> boot log -> peripheral init ->
  protocol handshake -> business state machine -> user-visible behavior.
- Change one variable per experiment unless the user explicitly asks for a broad
  patch. Record what changed and what signal would prove it worked.
- Keep noisy systems quiet. For black-box SDKs or private protocols, disable or
  ignore unrelated logs and keep the minimum chain needed to observe the failing
  edge.
- Do not claim hardware behavior is proven from a compile result. State the
  boundary clearly: source checked, build verified, flashed, booted, log-verified,
  or physically observed.

## First Pass

1. Identify the exact target: repo/path, MCU/chip, board/device, build system,
   flash method, serial port and baud rate when relevant.
2. Query project memory or injected context for similar failures and standing
   rules. Treat memory as a lead; verify against current files and logs.
3. Inspect the minimum current artifacts: project files, build script, recent
   logs, changed files, and the code path nearest the symptom.
4. State the next edit or experiment before making it.

## Embedded Evidence Gates

- Keil: prefer `%LOCALAPPDATA%\Keil_v5\UV4\UV4.exe`; verification
  is valid only when `build.log` contains the canonical `X Error(s), Y Warning(s)`
  summary. Do not rely on UV4 exit code alone.
- ESP-IDF: distinguish `idf.py build`, `flash`, `monitor`, reset, and startup
  evidence. A successful build is not a radio/sensor/network proof.
- Serial/HMI/protocol: preserve the exact port, baud/parity, frame bytes,
  checksum/CRC setting, and parsed notification/state transition.
- Hardware prompts: for "burn test", "flash and capture logs", or equivalent
  short prompts, default to build -> flash -> capture serial evidence when doing
  so is safe and already authorized. If flashing may move motors, change power
  state, or affect production hardware, stop and ask for confirmation.
- Risky actions: ask before deleting files, large refactors, modifying flash or
  power/reset scripts, changing credentials/permissions/deployment config, or
  running irreversible git operations.

## Completion Report

Every embedded completion report should answer:

- What requirement was handled.
- Which key files changed.
- Which verification commands ran.
- Whether verification passed, with the strongest observed evidence.
- What remains unverified and why.
- Whether a reusable failure pattern or project rule was discovered.

Keep the report concise and conclusion-first. If verification could not run,
say so plainly and name the remaining risk.
