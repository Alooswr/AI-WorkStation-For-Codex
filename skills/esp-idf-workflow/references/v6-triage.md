# v6 Triage

## Local Observation (2026-04-14)

From `C:\esp\v6.0\esp-idf`, running `python .\tools\idf.py --version` returned `No module named 'click'`.

Interpretation: ESP-IDF Python environment was not activated or dependencies were not installed for the current shell.

## High-Value Error Signatures

1. `No module named 'click'`
- Cause: Shell is outside ESP-IDF activated environment, or toolchain install is incomplete.
- Action: Run `install.ps1` then `export.ps1`, or switch to EIM-provisioned ESP-IDF terminal.

2. `idf.py` command cannot find serial port / connect fails
- Cause: Wrong COM port, busy port, board not in download mode, driver missing.
- Action: Re-check `COMx`, close serial monitors, retry with explicit `-p COMx`, verify cable/driver.

3. `idf.py efuse*` fails without port in v6.0+
- Cause: Behavior change in v6.0 migration.
- Action: Always pass `--port COMx` or set `ESPPORT`.

4. Unexpected config resets after `set-target`
- Cause: Expected behavior. `set-target` clears build output and regenerates `sdkconfig`.
- Action: Back up known-good sdkconfig values before target switch.

5. `idf.py size --format json` pipeline breakage
- Cause: v6.0 replaced `json` with `json2` format.
- Action: Update scripts to `idf.py size --format json2`.

## v6.0 Migration Notes To Remember

- Minimum Python version is 3.10.
- Minimum CMake version is 3.22.1.
- `idf.py size --legacy` removed.
- Install-script support for `--enable-gdbgui` removed.

## Source Links

- https://docs.espressif.com/projects/esp-idf/en/stable/esp32/migration-guides/release-6.x/6.0/tools.html
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/idf-py.html
- https://github.com/espressif/esp-idf/releases/tag/v6.0
