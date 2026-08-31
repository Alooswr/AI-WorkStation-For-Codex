# Firmware MCP Server

[中文文档](README.zh-CN.md)

<p align="center">
  <img src="assets/mascot-catgirl.jpg" alt="Firmware MCP Server mascot" width="320">
</p>

Firmware MCP Server is a local stdio MCP server for embedded firmware automation.
It exposes a small set of tools that let an MCP client build firmware, flash
devices, reset devices, and collect timestamped serial logs through commands
defined in a local device configuration file.

The server is designed for workstation-local automation. It does not start an
HTTP service, does not execute commands through a shell, and keeps local device
paths out of version control by default.

## Features

- Stdio-only MCP server for local clients.
- Standard project action interface for build, flash, monitor, clean, test, and reset.
- Built-in framework profiles for Keil MDK and ESP-IDF projects.
- Compatibility tools for build, flash, reset, and serial log capture.
- Per-device async locks, so operations for the same device are serialized.
- Concurrent operation across different devices.
- Config hot reload when the device config file changes.
- Subprocess execution through `asyncio.create_subprocess_exec`.
- Command arguments are explicit arrays and are never passed to `shell=True`.
- Serial capture through `pyserial`, with incremental JSON trace events on
  stderr.
- Consistent JSON response envelope for success and failure cases.
- Normalized log output levels: `Error`, `Warning`, and `Info`.
- Lightweight deterministic diagnostics based on tool traces and serial log
  patterns.

## Tools

| Tool | Purpose |
| --- | --- |
| `run_project_action` | Run one standard project action: `build`, `flash`, `monitor`, `clean`, `test`, or `reset`. |
| `list_project_actions` | List the standard actions configured for a device. |
| `scan_device` | Run a configured device scanner command, such as launching OpenModScan. |
| `build_firmware` | Run the configured build command for a device. |
| `flash_firmware` | Run the configured flash command for a device. |
| `reset_device` | Run the optional reset command for a device. |
| `read_serial_log` | Read timestamped serial lines from a device. |

`run_project_action` accepts:

```json
{
  "device_id": "demo",
  "action": "build",
  "timeout_ms": 300000
}
```

Allowed actions are `build`, `flash`, `monitor`, `clean`, `test`, and `reset`.
`timeout_ms` is optional. For `monitor`, the server runs `actions.monitor` when
configured; otherwise it reads serial logs using the device `serial` settings.
When using serial fallback, `duration_ms` and `max_lines` are also accepted.

`list_project_actions` accepts:

```json
{
  "device_id": "demo"
}
```

`scan_device` accepts:

```json
{
  "device_id": "demo",
  "timeout_ms": 30000
}
```

`scanner.command` is optional in the device config. It is intended for external
device discovery tools or GUI scanners. For GUI tools, configure a wrapper
command that launches the application and exits.

`build_firmware`, `flash_firmware`, and `reset_device` accept:

```json
{
  "device_id": "demo",
  "timeout_ms": 300000
}
```

`timeout_ms` is optional.

`read_serial_log` accepts:

```json
{
  "device_id": "demo",
  "duration_ms": 3000,
  "max_lines": 500
}
```

`duration_ms` and `max_lines` are optional.

## Response Format

Every tool returns one JSON object encoded as MCP text content.

Success:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Validation or runtime failure:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "error_type": "VALIDATION_ERROR",
    "type": "VALIDATION_ERROR",
    "message": "device_id must be a non-empty string",
    "recoverable": true
  }
}
```

Command failures keep captured process details in `data`:

```json
{
  "ok": false,
  "data": {
    "device_id": "demo",
    "action": "build_firmware",
    "started_at": "2026-01-01T00:00:00.000Z",
    "finished_at": "2026-01-01T00:00:02.000Z",
    "command": ["make"],
    "cwd": "/path/to/project",
    "exit_code": 2,
    "timed_out": false,
    "logs": {
      "levels": ["Error", "Warning", "Info"],
      "counts": {
        "Error": 1,
        "Warning": 0,
        "Info": 0
      },
      "entries": [
        {
          "level": "Error",
          "stream": "stderr",
          "line": "make error"
        }
      ],
      "total": 1,
      "truncated": false
    },
    "stdout": "",
    "stderr": "make error"
  },
  "error": {
    "error_type": "BUILD_FAILED",
    "type": "BUILD_FAILED",
    "message": "build_firmware exited with code 2 for device: demo",
    "recoverable": true
  }
}
```

Command and serial responses keep their original `stdout` / `stderr` / `lines`
fields. The additional `logs` field normalizes output into exactly three levels:
`Error`, `Warning`, and `Info`.

## Requirements

- Python 3.10 or newer.
- A local MCP-compatible client.
- `pyserial` when using serial log capture.
- Local build, flash, or reset commands configured per device.

## Installation

Clone the repository:

```bash
git clone https://github.com/<GITHUB_OWNER>/firmware-mcp-server.git
cd firmware-mcp-server
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bat
.venv\Scripts\activate
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Install the project in editable mode:

```bash
python -m pip install -e .
```

You can also install dependencies directly:

```bash
python -m pip install -r requirements.txt
```

## Device Configuration

The default device config path is:

```text
./config/devices.json
```

Create a local config from the example:

```bash
cp config/devices.example.json config/devices.json
```

On Windows Command Prompt:

```bat
copy config\devices.example.json config\devices.json
```

`config/devices.json` is intentionally ignored by git because it commonly
contains local paths, serial ports, and private build commands.

You can override the config path with `FIRMWARE_MCP_DEVICES_CONFIG`.

Linux or macOS:

```bash
export FIRMWARE_MCP_DEVICES_CONFIG=/path/to/devices.json
```

Windows Command Prompt:

```bat
set FIRMWARE_MCP_DEVICES_CONFIG=C:\path\to\devices.json
```

Device entry shape:

```json
{
  "device_id": "demo-esp-idf",
  "framework": "esp-idf",
  "esp_idf": {
    "project_root": "C:\\path\\to\\esp-idf-project",
    "idf_py": "idf.py"
  },
  "actions": {
    "test": {
      "command": ["python", "-m", "pytest"],
      "cwd": "C:\\path\\to\\esp-idf-project"
    },
    "reset": {
      "command": ["python", "tools\\reset_device.py", "--port", "COM7"],
      "cwd": "C:\\path\\to\\esp-idf-project"
    }
  },
  "serial": {
    "port": "COM7",
    "baudrate": 115200,
    "timeout_ms": 3000
  }
}
```

Notes:

- `device_id` must be unique.
- `framework` can be `custom`, `keil`, or `esp-idf`; the default is `custom`.
- `framework=keil` requires `keil.project_root`, `keil.uv4_path`,
  `keil.project_file`, and `keil.target`. It generates `build` and `flash`.
- `framework=esp-idf` requires `esp_idf.project_root`. It generates `build`,
  `flash`, `monitor`, and `clean`; serial `port` is used for flash/monitor.
- `actions` can override generated framework actions or add missing actions
  such as `test` and `reset`.
- Legacy top-level `build`, `flash`, and `reset` fields are still accepted and
  are merged into `actions` when the same action is not explicitly configured.
- `cwd` is optional.
- `command` must be a non-empty array of strings.
- Commands are executed directly and are not interpreted by a shell.

## MCP Client Configuration

Example client configuration when running from a cloned repository:

```json
{
  "mcpServers": {
    "firmware": {
      "command": "python",
      "args": ["-m", "firmware_mcp_server"],
      "cwd": "/absolute/path/to/firmware-mcp-server"
    }
  }
}
```

Example with an explicit device config:

```json
{
  "mcpServers": {
    "firmware": {
      "command": "python",
      "args": ["-m", "firmware_mcp_server"],
      "cwd": "/absolute/path/to/firmware-mcp-server",
      "env": {
        "FIRMWARE_MCP_DEVICES_CONFIG": "/absolute/path/to/devices.json"
      }
    }
  }
}
```

## Run Locally

From the project root:

```bash
python -m firmware_mcp_server
```

The process uses stdio for MCP transport. Regular runtime traces are written to
stderr as compact JSON log events.

## Diagnostics

The runtime keeps an in-memory diagnostic timeline that combines tool execution
traces and serial events. This internal layer does not add public MCP tools and
does not change tool response formats.

Serial events are tagged with semantic states:

- `BOOT`
- `CRASH`
- `HANG`
- `REBOOT_LOOP`
- `UNKNOWN`

The deterministic classifier can return failure types such as:

- `BUILD_FAILED`
- `FLASH_FAILED`
- `RESET_FAILED`
- `CRASH_AFTER_FLASH`
- `REBOOT_LOOP`
- `NO_BOOT`
- `UNKNOWN`

Execution trace example:

```json
{
  "event": "tool_execution_trace",
  "tool_name": "build_firmware",
  "device_id": "demo",
  "start_time": "2026-01-01T00:00:00.000Z",
  "end_time": "2026-01-01T00:00:02.000Z",
  "status": "ok"
}
```

Serial trace example:

```json
{
  "event": "serial_log_line",
  "source": "serial",
  "device_id": "demo",
  "port": "COM3",
  "timestamp": "2026-01-01T00:00:00.000Z",
  "line": "boot",
  "state": "BOOT"
}
```

## Development

Install development dependencies:

```bash
python -m pip install -e .
```

Run tests:

```bash
python -m unittest discover -s tests
```

Check ignored local files:

```bash
git status --ignored --short
```

## Security Model

This server runs local commands from your device configuration. Treat
`devices.json` as trusted local configuration and review commands before using
them with an MCP client.

Important defaults:

- No HTTP listener is started.
- Commands are executed without `shell=True`.
- Device-local configuration is excluded from git by default.
- stdout is reserved for MCP protocol traffic.
- logs and traces are emitted to stderr.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and operational
guidance.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

## License

This project is licensed under the [MIT License](LICENSE).

Image assets are documented separately in [ASSETS.md](ASSETS.md).
