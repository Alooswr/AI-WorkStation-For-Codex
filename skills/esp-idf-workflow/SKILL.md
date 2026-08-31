---
name: esp-idf-workflow
description: Windows ESP-IDF setup, build, flash, monitor, and troubleshooting workflow for `idf.py` projects. Use when working with ESP-IDF repositories, ESP-IDF components, `sdkconfig`, target selection, toolchain/environment errors, or `idf.py build/flash/monitor` failures. Do not use for Arduino, PlatformIO, Keil MDK, or generic CMake projects that are not driven by ESP-IDF.
---

# ESP-IDF Workflow

Use this skill to execute a reliable `idf.py` development loop on Windows and
to quickly triage common ESP-IDF failures.

## Use When

- The project is driven by ESP-IDF and `idf.py`.
- The request mentions ESP-IDF, `sdkconfig`, ESP-IDF components, target
  selection, flash/monitor, or ESP-IDF environment/toolchain errors.

## Do Not Use When

- The project is Arduino, PlatformIO, Keil MDK, or a generic CMake/Make project
  without ESP-IDF.
- The issue is LVGL-specific UI/display/input behavior inside an ESP-IDF
  project; pair this skill with `lvgl-workflow`.

## Quick Preflight

1. Confirm current directory is an ESP-IDF project (`CMakeLists.txt` present).
2. Confirm project and ESP-IDF paths do not contain spaces.
3. Confirm ESP-IDF environment is activated before running `idf.py`.
4. Confirm baseline state:
```powershell
git -C C:\esp\v6.0\esp-idf describe --tags --always
python C:\esp\v6.0\esp-idf\tools\idf.py --version
```

## Environment Choice (Windows, v6.0+)

1. Prefer EIM-managed activation for ESP-IDF v6.0+.
2. Use legacy scripts only when working from a manually cloned ESP-IDF tree:
```powershell
Set-Location C:\esp\v6.0\esp-idf
.\install.ps1    # first-time or tool refresh
.\export.ps1     # every new shell session
```
3. If `idf.py` reports missing Python modules (for example `No module named 'click'`), treat it as environment/tool setup failure first, not a project code failure.

## Standard Development Loop

1. Start project from example outside the ESP-IDF repo.
2. Set target once per project or when switching chips:
```powershell
idf.py --list-targets
idf.py set-target esp32s3
```
3. Configure and build:
```powershell
idf.py menuconfig
idf.py build
```
4. Flash and monitor:
```powershell
idf.py -p COMx flash monitor
```
5. Fast app-only iteration after first full flash:
```powershell
idf.py app
idf.py -p COMx app-flash monitor
```
6. Reset stale build states as needed:
```powershell
idf.py clean        # keep cmake cache
idf.py fullclean    # remove full build dir
idf.py reconfigure  # force cmake regenerate
```

## Triage Rules

1. Environment first, project second:
- Resolve `idf.py` startup/module errors before touching project code.
2. Port-related operations must be explicit:
- For `efuse` commands in v6.0, always include `--port` (or set `ESPPORT`).
3. Chip switch is destructive to current config cache:
- `idf.py set-target` clears build and regenerates `sdkconfig`.
4. For repeatable logs, prefer single-command pipelines:
```powershell
idf.py -p COMx clean flash monitor
```
5. For size tooling in v6.0+, use `json2` format instead of legacy `json`.

## v6.0 Migration-Sensitive Points

1. Minimum Python version: 3.10.
2. Minimum CMake version: 3.22.1.
3. `idf.py size --legacy` removed.
4. `idf.py size --format json` replaced by `--format json2`.
5. Windows `gdbgui` installation via install script removed; prefer `idf.py gdb` when applicable.

## References To Load On Demand

1. Command cookbook: `references/command-recipes.md`
2. Error signatures and migration notes: `references/v6-triage.md`

Load only the file needed for the current task.
