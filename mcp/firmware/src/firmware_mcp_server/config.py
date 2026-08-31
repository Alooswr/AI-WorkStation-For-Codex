from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigLoadError, DeviceNotFoundError


STANDARD_ACTIONS = ("build", "flash", "monitor", "clean", "test", "reset")
STANDARD_ACTION_SET = frozenset(STANDARD_ACTIONS)
SUPPORTED_FRAMEWORKS = ("custom", "keil", "esp-idf")
SUPPORTED_FRAMEWORK_SET = frozenset(SUPPORTED_FRAMEWORKS)


class DeviceConfigError(ConfigLoadError):
    pass


@dataclass(frozen=True)
class CommandConfig:
    command: list[str]
    cwd: str | None = None


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baudrate: int
    timeout_ms: int


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str
    framework: str
    build: CommandConfig
    flash: CommandConfig
    reset: CommandConfig | None
    scanner: CommandConfig | None
    serial: SerialConfig
    actions: dict[str, CommandConfig]


@dataclass(frozen=True)
class ConfigFingerprint:
    mtime_ns: int
    size: int


class DeviceRegistry:
    def __init__(
        self,
        config_path: Path,
        devices: dict[str, DeviceConfig],
        fingerprint: ConfigFingerprint,
    ) -> None:
        self._config_path = config_path
        self._devices = devices
        self._fingerprint = fingerprint

    @classmethod
    def load(cls, config_path: str | None = None) -> "DeviceRegistry":
        path = resolve_config_path(config_path)
        devices = load_devices_from_path(path)
        fingerprint = get_config_fingerprint(path)
        return cls(path, devices, fingerprint)

    def reload(self) -> None:
        self._devices = load_devices_from_path(self._config_path)
        self._fingerprint = get_config_fingerprint(self._config_path)

    def reload_if_changed(self, debounce_seconds: float = 0.05) -> bool:
        current = get_config_fingerprint(self._config_path)
        if current == self._fingerprint:
            return False

        current = get_stable_config_fingerprint(self._config_path, debounce_seconds, current)
        if current == self._fingerprint:
            return False

        self._devices = load_devices_from_path(self._config_path)
        self._fingerprint = current
        return True

    def get(self, device_id: str) -> DeviceConfig:
        device = self._devices.get(device_id)
        if device is None:
            available = ", ".join(sorted(self._devices))
            raise DeviceNotFoundError(f"unknown device_id: {device_id}; available devices: {available}")
        return device

    def list_ids(self) -> list[str]:
        return sorted(self._devices)


def get_config_fingerprint(path: Path) -> ConfigFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DeviceConfigError(f"failed to stat device config: {path}") from exc

    return ConfigFingerprint(
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
    )


def get_stable_config_fingerprint(
    path: Path,
    debounce_seconds: float,
    initial: ConfigFingerprint | None = None,
    attempts: int = 3,
) -> ConfigFingerprint:
    previous = initial or get_config_fingerprint(path)

    for _ in range(max(1, attempts)):
        if debounce_seconds > 0:
            time.sleep(debounce_seconds)

        current = get_config_fingerprint(path)
        if current == previous:
            return current
        previous = current

    return previous


def load_devices_from_path(path: Path) -> dict[str, DeviceConfig]:
    try:
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except OSError as exc:
        raise DeviceConfigError(f"failed to read device config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeviceConfigError(f"invalid device config JSON: {path}") from exc

    devices_raw = raw.get("devices")
    if not isinstance(devices_raw, list) or not devices_raw:
        raise DeviceConfigError("config/devices.json must contain a non-empty devices array")

    devices: dict[str, DeviceConfig] = {}
    for entry in devices_raw:
        device = parse_device(entry)
        if device.device_id in devices:
            raise DeviceConfigError(f"duplicate device_id: {device.device_id}")
        devices[device.device_id] = device

    return devices


def resolve_config_path(config_path: str | None) -> Path:
    if config_path:
        path = Path(config_path)
    elif os.environ.get("FIRMWARE_MCP_DEVICES_CONFIG"):
        path = Path(os.environ["FIRMWARE_MCP_DEVICES_CONFIG"])
    else:
        path = Path.cwd() / "config" / "devices.json"

    if not path.exists():
        raise DeviceConfigError(f"device config file does not exist: {path}")

    return path


def parse_device(raw: Any) -> DeviceConfig:
    if not isinstance(raw, dict):
        raise DeviceConfigError("each device entry must be a JSON object")

    device_id = raw.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise DeviceConfigError("device_id must be a non-empty string")

    framework = parse_framework(raw.get("framework"), device_id)
    actions = parse_framework_actions(raw, device_id, framework)
    actions.update(parse_actions(raw.get("actions"), device_id))
    legacy_build = parse_command(raw.get("build"), f"{device_id}.build", required=False)
    legacy_flash = parse_command(raw.get("flash"), f"{device_id}.flash", required=False)
    legacy_reset = parse_command(raw.get("reset"), f"{device_id}.reset", required=False)
    scanner = parse_command(raw.get("scanner"), f"{device_id}.scanner", required=False)

    if legacy_build is not None:
        actions.setdefault("build", legacy_build)
    if legacy_flash is not None:
        actions.setdefault("flash", legacy_flash)
    if legacy_reset is not None:
        actions.setdefault("reset", legacy_reset)

    build = actions.get("build")
    if build is None:
        raise DeviceConfigError(f"{device_id}.build or {device_id}.actions.build is required")

    flash = actions.get("flash")
    if flash is None:
        raise DeviceConfigError(f"{device_id}.flash or {device_id}.actions.flash is required")

    return DeviceConfig(
        device_id=device_id,
        framework=framework,
        build=build,
        flash=flash,
        reset=actions.get("reset"),
        scanner=scanner,
        serial=parse_serial(raw.get("serial"), device_id),
        actions=actions,
    )


def parse_framework(raw: Any, device_id: str) -> str:
    if raw is None:
        return "custom"
    if not isinstance(raw, str) or not raw.strip():
        raise DeviceConfigError(f"{device_id}.framework must be a non-empty string when provided")
    value = raw.strip().casefold().replace("_", "-")
    aliases = {
        "espidf": "esp-idf",
        "idf": "esp-idf",
        "keil-mdk": "keil",
        "mdk": "keil",
        "uv4": "keil",
    }
    framework = aliases.get(value, value)
    if framework not in SUPPORTED_FRAMEWORK_SET:
        allowed = ", ".join(SUPPORTED_FRAMEWORKS)
        raise DeviceConfigError(f"{device_id}.framework must be one of: {allowed}")
    return framework


def parse_framework_actions(raw: dict[str, Any], device_id: str, framework: str) -> dict[str, CommandConfig]:
    if framework == "custom":
        return {}
    if framework == "keil":
        return parse_keil_actions(raw, device_id)
    if framework == "esp-idf":
        return parse_esp_idf_actions(raw, device_id)
    raise DeviceConfigError(f"unsupported framework: {framework}")


def parse_keil_actions(raw: dict[str, Any], device_id: str) -> dict[str, CommandConfig]:
    keil = raw.get("keil")
    if not isinstance(keil, dict):
        raise DeviceConfigError(f"{device_id}.keil is required when framework is keil")

    project_root = parse_profile_string(keil.get("project_root") or raw.get("project_root"), f"{device_id}.keil.project_root")
    uv4_path = parse_profile_string(keil.get("uv4_path") or keil.get("uv4"), f"{device_id}.keil.uv4_path")
    project_file = parse_profile_string(keil.get("project_file") or keil.get("uvprojx"), f"{device_id}.keil.project_file")
    target = parse_profile_string(keil.get("target"), f"{device_id}.keil.target")
    build_log = parse_optional_profile_string(keil.get("build_log")) or "build.log"
    flash_log = parse_optional_profile_string(keil.get("flash_log")) or "flash.log"

    return {
        "build": CommandConfig(
            command=[uv4_path, "-r", project_file, "-t", target, "-o", build_log],
            cwd=project_root,
        ),
        "flash": CommandConfig(
            command=[uv4_path, "-f", project_file, "-t", target, "-o", flash_log],
            cwd=project_root,
        ),
    }


def parse_esp_idf_actions(raw: dict[str, Any], device_id: str) -> dict[str, CommandConfig]:
    esp_idf = raw.get("esp_idf") or raw.get("esp-idf")
    if not isinstance(esp_idf, dict):
        raise DeviceConfigError(f"{device_id}.esp_idf is required when framework is esp-idf")

    project_root = parse_profile_string(
        esp_idf.get("project_root") or raw.get("project_root"),
        f"{device_id}.esp_idf.project_root",
    )
    idf_py = parse_optional_profile_string(esp_idf.get("idf_py")) or "idf.py"
    port = parse_optional_profile_string(esp_idf.get("port")) or serial_port_from_raw(raw.get("serial"))
    actions = {
        "build": CommandConfig(command=[idf_py, "build"], cwd=project_root),
        "clean": CommandConfig(command=[idf_py, "clean"], cwd=project_root),
    }

    flash_command = [idf_py]
    monitor_command = [idf_py]
    if port:
        flash_command.extend(["-p", port])
        monitor_command.extend(["-p", port])
    flash_command.append("flash")
    monitor_command.append("monitor")
    actions["flash"] = CommandConfig(command=flash_command, cwd=project_root)
    actions["monitor"] = CommandConfig(command=monitor_command, cwd=project_root)
    return actions


def parse_profile_string(raw: Any, name: str) -> str:
    value = parse_optional_profile_string(raw)
    if value is None:
        raise DeviceConfigError(f"{name} must be a non-empty string")
    return value


def parse_optional_profile_string(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


def serial_port_from_raw(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    return parse_optional_profile_string(raw.get("port"))


def parse_actions(raw: Any, device_id: str) -> dict[str, CommandConfig]:
    if raw is None:
        return {}

    if not isinstance(raw, dict):
        raise DeviceConfigError(f"{device_id}.actions must be a JSON object")

    actions: dict[str, CommandConfig] = {}
    for action, command_raw in raw.items():
        if not isinstance(action, str) or not action.strip():
            raise DeviceConfigError(f"{device_id}.actions keys must be non-empty strings")
        action_name = action.strip()
        if action_name not in STANDARD_ACTION_SET:
            allowed = ", ".join(STANDARD_ACTIONS)
            raise DeviceConfigError(f"{device_id}.actions.{action_name} is not supported; allowed actions: {allowed}")
        actions[action_name] = parse_command(command_raw, f"{device_id}.actions.{action_name}", required=True)

    return actions


def parse_command(raw: Any, name: str, required: bool) -> CommandConfig | None:
    if raw is None:
        if required:
            raise DeviceConfigError(f"{name} is required")
        return None

    if not isinstance(raw, dict):
        raise DeviceConfigError(f"{name} must be a JSON object")

    command = raw.get("command")
    if not isinstance(command, list) or not command:
        raise DeviceConfigError(f"{name}.command must be a non-empty string array")

    for index, arg in enumerate(command):
        if not isinstance(arg, str) or not arg:
            raise DeviceConfigError(f"{name}.command[{index}] must be a non-empty string")

    cwd = raw.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd.strip()):
        raise DeviceConfigError(f"{name}.cwd must be a non-empty string when provided")

    return CommandConfig(command=command, cwd=cwd)


def parse_serial(raw: Any, device_id: str) -> SerialConfig:
    if not isinstance(raw, dict):
        raise DeviceConfigError(f"{device_id}.serial is required and must be a JSON object")

    port = raw.get("port")
    baudrate = raw.get("baudrate")
    timeout_ms = raw.get("timeout_ms")

    if not isinstance(port, str) or not port.strip():
        raise DeviceConfigError(f"{device_id}.serial.port must be a non-empty string")
    if not isinstance(baudrate, int) or baudrate <= 0:
        raise DeviceConfigError(f"{device_id}.serial.baudrate must be a positive integer")
    if not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise DeviceConfigError(f"{device_id}.serial.timeout_ms must be a positive integer")

    return SerialConfig(port=port, baudrate=baudrate, timeout_ms=timeout_ms)
