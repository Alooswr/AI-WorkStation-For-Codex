# Command Recipes

Use these commands in PowerShell unless the user asks for another shell.

## 1) Verify ESP-IDF Root And Version

```powershell
Set-Location C:\esp\v6.0\esp-idf
git describe --tags --always
git status --short --branch
```

## 2) Activate Environment (Legacy Script Flow)

Use this when working from a manually cloned tree (not EIM-managed shell).

```powershell
Set-Location C:\esp\v6.0\esp-idf
.\install.ps1   # first-time setup or tool refresh
.\export.ps1    # run in each new shell before idf.py
```

## 3) Start A New Project From Example

```powershell
cd $env:USERPROFILE\esp
xcopy /e /i $env:IDF_PATH\examples\get-started\hello_world hello_world
cd $env:USERPROFILE\esp\hello_world
idf.py --list-targets
idf.py set-target esp32s3
idf.py menuconfig
```

## 4) Build And Flash Loop

```powershell
idf.py build
idf.py -p COM5 flash
idf.py -p COM5 monitor
idf.py -p COM5 flash monitor
```

## 5) Faster Incremental Loop

```powershell
idf.py app
idf.py -p COM5 app-flash monitor
```

## 6) Recover From Stale Build State

```powershell
idf.py clean
idf.py fullclean
idf.py reconfigure
```

## 7) Size And Artifact Utilities (v6+)

```powershell
idf.py size --format text
idf.py size --format json2
idf.py merge-bin -o merged.bin -f raw
idf.py uf2
```

## 8) Useful Defaults

```powershell
$env:ESPPORT = 'COM5'
$env:ESPBAUD = '921600'
idf.py flash monitor
```

## 9) Port-Sensitive eFuse Commands

In v6.0, include a port explicitly:

```powershell
idf.py --port COM5 efuse-summary
```

## Source Links

- https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/windows-setup.html
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/windows-setup-update-legacy.html
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/idf-py.html
