from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

from firmware_mcp_server.config import DeviceRegistry


class DeviceRegistryTests(unittest.TestCase):
    def test_load_device_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": ["python", "--version"],
                                },
                                "flash": {
                                    "command": ["python", "--version"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            registry = DeviceRegistry.load(str(config_path))
            device = registry.get("test-device")

            self.assertEqual(device.device_id, "test-device")
            self.assertEqual(device.framework, "custom")
            self.assertEqual(device.build.command, ["python", "--version"])
            self.assertEqual(device.flash.command, ["python", "--version"])
            self.assertIsNone(device.reset)
            self.assertIsNone(device.scanner)
            self.assertEqual(device.serial.port, "COM1")
            self.assertEqual(device.actions["build"].command, ["python", "--version"])
            self.assertEqual(device.actions["flash"].command, ["python", "--version"])

    def test_load_scanner_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "scanner-device",
                                "build": {
                                    "command": [sys.executable, "--version"],
                                },
                                "flash": {
                                    "command": [sys.executable, "--version"],
                                },
                                "scanner": {
                                    "command": [sys.executable, "-c", "print('scan')"],
                                    "cwd": "C:/tools/scanner",
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            registry = DeviceRegistry.load(str(config_path))
            device = registry.get("scanner-device")

            self.assertIsNotNone(device.scanner)
            self.assertEqual(device.scanner.command, [sys.executable, "-c", "print('scan')"])
            self.assertEqual(device.scanner.cwd, "C:/tools/scanner")

    def test_load_actions_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "actions-device",
                                "actions": {
                                    "build": {
                                        "command": [sys.executable, "-c", "print('build')"],
                                    },
                                    "flash": {
                                        "command": [sys.executable, "-c", "print('flash')"],
                                    },
                                    "clean": {
                                        "command": [sys.executable, "-c", "print('clean')"],
                                    },
                                    "test": {
                                        "command": [sys.executable, "-c", "print('test')"],
                                    },
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            registry = DeviceRegistry.load(str(config_path))
            device = registry.get("actions-device")

            self.assertEqual(device.framework, "custom")
            self.assertEqual(device.build.command, [sys.executable, "-c", "print('build')"])
            self.assertEqual(device.flash.command, [sys.executable, "-c", "print('flash')"])
            self.assertEqual(device.actions["clean"].command, [sys.executable, "-c", "print('clean')"])
            self.assertEqual(device.actions["test"].command, [sys.executable, "-c", "print('test')"])

    def test_load_keil_framework_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "keil-device",
                                "framework": "keil",
                                "keil": {
                                    "project_root": "C:/work/app",
                                    "uv4_path": "C:/Keil/UV4/UV4.exe",
                                    "project_file": "project/app.uvprojx",
                                    "target": "app",
                                    "build_log": "out/build.log",
                                    "flash_log": "out/flash.log",
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            registry = DeviceRegistry.load(str(config_path))
            device = registry.get("keil-device")

            self.assertEqual(device.framework, "keil")
            self.assertEqual(
                device.actions["build"].command,
                ["C:/Keil/UV4/UV4.exe", "-r", "project/app.uvprojx", "-t", "app", "-o", "out/build.log"],
            )
            self.assertEqual(
                device.actions["flash"].command,
                ["C:/Keil/UV4/UV4.exe", "-f", "project/app.uvprojx", "-t", "app", "-o", "out/flash.log"],
            )

    def test_load_esp_idf_framework_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "esp-device",
                                "framework": "esp-idf",
                                "esp_idf": {
                                    "project_root": "C:/work/esp",
                                    "idf_py": "idf.py",
                                },
                                "serial": {
                                    "port": "COM7",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            registry = DeviceRegistry.load(str(config_path))
            device = registry.get("esp-device")

            self.assertEqual(device.framework, "esp-idf")
            self.assertEqual(device.actions["build"].command, ["idf.py", "build"])
            self.assertEqual(device.actions["flash"].command, ["idf.py", "-p", "COM7", "flash"])
            self.assertEqual(device.actions["monitor"].command, ["idf.py", "-p", "COM7", "monitor"])
            self.assertEqual(device.actions["clean"].command, ["idf.py", "clean"])

    def test_reload_if_changed_only_reloads_after_file_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "device-a",
                                "build": {
                                    "command": ["python", "--version"],
                                },
                                "flash": {
                                    "command": ["python", "--version"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            registry = DeviceRegistry.load(str(config_path))

            self.assertFalse(registry.reload_if_changed())

            time.sleep(0.01)
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "device-b",
                                "build": {
                                    "command": ["python", "--version"],
                                },
                                "flash": {
                                    "command": ["python", "--version"],
                                },
                                "serial": {
                                    "port": "COM2",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(registry.reload_if_changed())
            self.assertEqual(registry.get("device-b").serial.port, "COM2")
            self.assertFalse(registry.reload_if_changed())


if __name__ == "__main__":
    unittest.main()
