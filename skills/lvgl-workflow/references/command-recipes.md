# Command Recipes

Use these commands in PowerShell unless the user asks for another shell.

## 1) Confirm LVGL Repo State

```powershell
Set-Location %USERPROFILE%\work\LVGL\lvgl
git describe --tags --always
git status --short --branch
```

## 2) Build LVGL Repo With CMake Presets

```powershell
Set-Location %USERPROFILE%\work\LVGL\lvgl
cmake --preset windows-base
cmake --build --preset windows-base_dbg
ctest --preset windows-base_dbg
```

## 3) Generic CMake Build Without Presets

```powershell
Set-Location %USERPROFILE%\work\LVGL\lvgl
cmake -B build
cmake --build build
```

## 4) Prepare And Run LVGL Tests

```powershell
Set-Location %USERPROFILE%\work\LVGL\lvgl
.\scripts\install-prerequisites.bat
python .\tests\main.py test
```

Build-only tests:

```powershell
python .\tests\main.py build
```

## 5) Add LVGL To ESP-IDF Project

Preferred high-level port:

```powershell
idf.py add-dependency "espressif/esp_lvgl_port^2.3.0"
```

Direct LVGL component:

```powershell
idf.py add-dependency "lvgl/lvgl^9.*"
```

Then:

```powershell
idf.py menuconfig
idf.py build flash monitor
```

## 6) Use Local LVGL Source In ESP-IDF Project

```powershell
git submodule add https://github.com/lvgl/lvgl.git components/lvgl
```

## 7) Minimum lv_conf.h Activation

1. Copy `lv_conf_template.h` -> `lv_conf.h`.
2. Change first `#if 0` to `#if 1`.
3. Rebuild and verify `lv_conf.h` is in include path.

## 8) SDL PC Simulation Hints

Required compile-time enable:

```c
#define LV_USE_SDL 1
```

On Windows apps, if needed:

```c
#define SDL_MAIN_HANDLED
```

## Source Links

- https://github.com/lvgl/lvgl/blob/master/README.md
- https://docs.lvgl.io/master/integration/building/cmake.html
- https://docs.lvgl.io/master/integration/chip_vendors/espressif/add_lvgl_to_esp32_idf_project.html
- https://docs.lvgl.io/master/integration/pc/sdl.html
