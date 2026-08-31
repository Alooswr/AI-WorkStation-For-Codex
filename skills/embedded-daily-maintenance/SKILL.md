---
name: embedded-daily-maintenance
description: Composite embedded firmware maintenance workflow for repo sync, Git delivery, Saleae checklist preparation, new-repository onboarding, and multi-step day-to-day maintenance. Use when the task explicitly combines source sync, build verification, debugging workflow, handoff, or push/PR delivery across tools. Do not use for a single Keil compile, a single ESP-IDF build/flash, LVGL-only triage, serial HMI protocol debugging, or hardware evidence gates; route those to the narrower specialty skill first.
---

# Embedded Daily Maintenance

Use this skill only for composite maintenance flows across editor, build, Git,
and signal-capture planning. It is a workflow wrapper, not the default entry for
single-domain build or protocol tasks.

## Use When

- The request combines repo sync, build verification, debugging workflow, Git
  delivery, or handoff across multiple tools.
- A new firmware repository needs onboarding and durable build/run notes.
- The user asks for Saleae or logic-analyzer checklist preparation as part of a
  broader maintenance run.

## Do Not Use When

- The request is only Keil compile/link triage; use `keil-rebuild-debug`.
- The request is only ESP-IDF build/flash/monitor; use `esp-idf-workflow`.
- The request is only LVGL UI integration/debugging; use `lvgl-workflow`.
- The request is only M&F/DaCai serial HMI protocol work; use `mf-serial-hmi`.
- The request is only runtime or hardware proof; use
  `embedded-debug-verification` after the matching domain skill.

## Tool Baseline

- Compiler: Keil MDK (`UV4.exe`)
- Code navigation and edit: VSCode-compatible file workflow
- Version control: Git (pull/rebase/commit/push)
- Signal verification: Saleae Logic (timing/protocol capture)

## Default Working Pattern

1. Sync source first:
- Check branch and working tree.
- Pull latest remote changes before large edits.

2. Build with Keil:
- Prefer rebuild (`-r`) and save log with `-o`.
- Parse errors/warnings from log; do not rely on exit code only.

3. Debug in code:
- Locate errors by file/line from build log.
- Apply minimal patch.
- Rebuild to verify regression-free status.

4. Validate runtime behavior:
- Use existing runtime logs first.
- If UART/SPI/I2C timing issue suspected, prepare Saleae capture checklist and expected waveform points.

5. Git delivery:
- Stage only intended files.
- Exclude temporary artifacts and logs.
- Push once build is clean and scope is verified.

## Debug Collaboration Rule

For debugging/fix requests, follow this order:

1. Provide execution plan and expected code impact.
2. Wait for user review/approval.
3. Apply changes only after approval.
4. Rebuild and report exact results.

## Sub-agent Coordination Rule

- Main agent autonomously decides whether to spawn child agents and which child agents to use based on task domain.
- Do not call out-of-domain optional agents (for example, skip HMI agent for non-HMI tasks).
- If child-agent outputs conflict, pause edits and escalate to main-agent reconciliation.
- Proceed only with one consolidated decision from the main agent.

## Keil Command Template

```powershell
& "<UV4.exe>" -r "<path-to-project.uvprojx>" -t "<TargetName>" -o "<build.log>"
```

Default preferred path:

- `%LOCALAPPDATA%\Keil_v5\UV4\UV4.exe`

## Keil Reliability Guardrails

- Prefer `%LOCALAPPDATA%\Keil_v5\UV4\UV4.exe` for CLI builds.
- Avoid defaulting to `C:\baidunetdiskdownload\...\UV4.exe` in command-line runs; it may fail with `-1073741515` and produce no log.
- Prefer `Start-Process -Wait` when automation needs deterministic completion.
- Use a generous timeout (recommended `>=600000ms`) for rebuild commands.
- Always verify build-log file exists after run; if missing, treat build as failed and rerun with the preferred UV4 path.

## Git Hygiene Checklist

Keep these out of commits unless explicitly required:

- Keil build logs (`build.log`)
- Temporary integration folders (e.g., `.tmp_ftservo/`)
- Local IDE/session artifacts

## New Repository Onboarding

When a new firmware repo is pulled:

1. Discover `.uvprojx` and target names.
2. Confirm build command works end-to-end.
3. Check `.gitignore` for logs/temp folders.
4. Record project-specific compile target mapping for future runs.

## Python Usage Policy

If Python tooling is needed for automation/validation:

- Network download and Python setup are permitted by user.
- Install only when task requires it.
- Prefer minimal, auditable commands and report what was installed.

## Script Template

This skill bundles a reusable script:

- `scripts/keil-cycle.ps1`

Usage example:

```powershell
powershell -ExecutionPolicy Bypass -File ".\\scripts\\keil-cycle.ps1" `
  -Project "C:\\path\\to\\project\\Project.uvprojx" `
  -Target "target-name" `
  -Mode rebuild `
  -GitPull
```

Optional push after clean build:

```powershell
powershell -ExecutionPolicy Bypass -File ".\\scripts\\keil-cycle.ps1" `
  -Project "C:\\path\\to\\project\\Project.uvprojx" `
  -Target "target-name" `
  -Mode rebuild `
  -GitPull -GitPush
```

## JLCEDA Netlist And Datasheet Sources

Default reference paths (use these first unless user explicitly overrides in current task):

- JLCEDA netlist folder: `<EDA_NETLIST_ROOT>`
- Project datasheet folder: `<DATASHEET_ROOT>`

Standard accuracy-first flow for new hardware projects:

1. Locate netlist files (`.tel`, `.net`, or exported netlist text) from the netlist folder.
2. Locate MCU/peripheral datasheets and schematic exports from the datasheet folder.
3. Build and present a `net -> pin -> GPIO/AF/peripheral` mapping table with source references.
4. Wait for user approval on the mapping table.
5. Apply code changes only after approval, then rebuild and report results.

Do not skip step 4. For GPIO and peripheral initialization, prioritize correctness over speed.



