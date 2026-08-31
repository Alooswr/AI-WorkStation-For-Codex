---
name: keil-rebuild-debug
description: Keil MDK rebuild and build-log triage for `.uvprojx` targets. Use when the request involves UV4.exe, Keil targets, `build.log`, compile errors, link errors, warnings, missing packs/toolchain diagnostics, or verifying a Keil rebuild. Do not use for ESP-IDF, Arduino, PlatformIO, runtime hardware proof, serial protocols, or Git delivery workflows.
---

# Keil Rebuild Debug (Minimal)

Use when users ask to compile/rebuild Keil projects, analyze build logs, or
locate compile/link errors and warnings.

## Use When

- The project has a `.uvprojx` target or the user mentions Keil MDK, UV4, or
  `build.log`.
- The task is compile, rebuild, warning/error triage, linker failure triage, or
  verifying a Keil build boundary.

## Do Not Use When

- The target is ESP-IDF, Arduino, PlatformIO, CMake-only, or Make-only.
- The result must prove flashed firmware or hardware behavior; use this for the
  build layer, then add `embedded-debug-verification`.
- The core task is repo sync, Git delivery, or a multi-step maintenance run; use
  `embedded-daily-maintenance`.

## Defaults

- Rebuild with `-r`.
- Prefer `%LOCALAPPDATA%\Keil_v5\UV4\UV4.exe`.
- UV4 path resolution order:
  1) `%LOCALAPPDATA%\Keil_v5\UV4\UV4.exe` (project owner default)
  2) `where UV4.exe`
- If sandbox reports UV4 missing, rerun the check with escalated permissions before judging the path invalid.
- Run via `Start-Process -Wait`.
- Use timeout `>= 600000ms`.
- Always write `build.log` with `-o`.
- Result is valid only if `build.log` exists and contains `X Error(s), Y Warning(s)`.

## Workflow

1. Discover `.uvprojx` and target `<TargetName>`.
2. Rebuild command:

```powershell
& "<UV4.exe>" -r "<project.uvprojx>" -t "<TargetName>" -o "<build.log>"
```

3. Parse summary + top error/warning lines (file/line/message).
4. If user asks to fix, give a short plan first, then patch minimally and rebuild.

## Report Checklist

- Project path + target name
- UV4 exit code
- `X Error(s), Y Warning(s)` summary
- Blocking errors (if any)
- Next action

## Git Hygiene

Exclude temporary build artifacts before push:

- `project/mdk_app/build.log`
- `project/mdk_bootloader/build.log`
- `.tmp_ftservo/`
