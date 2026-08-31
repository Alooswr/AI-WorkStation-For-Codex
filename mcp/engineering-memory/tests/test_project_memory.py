from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from codex_memory_mcp.project_memory import PROJECT_RESOURCE_ROOTS_ENV, ProjectMemoryStore, infer_progress_status
from codex_memory_mcp.store import MemoryStore


class ProjectMemoryStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.temp_dir.name) / "memory"
        self.memory_root.mkdir()
        self.repo = Path(self.temp_dir.name) / "Payload-SDK"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.store = ProjectMemoryStore(MemoryStore(self.memory_root))
        self.old_resource_roots = os.environ.get(PROJECT_RESOURCE_ROOTS_ENV)

    def tearDown(self) -> None:
        if self.old_resource_roots is None:
            os.environ.pop(PROJECT_RESOURCE_ROOTS_ENV, None)
        else:
            os.environ[PROJECT_RESOURCE_ROOTS_ENV] = self.old_resource_roots
        for attempt in range(5):
            try:
                self.temp_dir.cleanup()
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1)

    def test_first_scan_generates_project_profile(self) -> None:
        (self.repo / "main").mkdir()
        (self.repo / "components" / "sensor_driver").mkdir(parents=True)
        (self.repo / "tests").mkdir()
        (self.repo / "main" / "main.c").write_text(
            "#include <stdio.h>\nvoid app_main(void) {}\n",
            encoding="utf-8",
        )
        (self.repo / "components" / "sensor_driver" / "sensor.c").write_text(
            "void sensor_init(void) {}\n",
            encoding="utf-8",
        )
        (self.repo / "tests" / "test_smoke.py").write_text(
            "def test_smoke():\n    assert True\n",
            encoding="utf-8",
        )
        (self.repo / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\n", encoding="utf-8")
        (self.repo / "sdkconfig").write_text("CONFIG_IDF_TARGET=\"esp32s3\"\n", encoding="utf-8")
        (self.repo / "partitions.csv").write_text("nvs,data,nvs,0x9000,0x6000\n", encoding="utf-8")

        project = self.store.resolve_project(str(self.repo))
        profile = Path(project["project_dir"]) / "profile.md"
        content = profile.read_text(encoding="utf-8")

        self.assertIn("## First Scan", content)
        self.assertIn("project_type: embedded firmware / ESP-IDF", content)
        self.assertIn("build_system: ESP-IDF/CMake, CMake", content)
        self.assertIn("- main/main.c", content)
        self.assertIn("- components/sensor_driver", content)
        self.assertIn("- sdkconfig", content)
        self.assertIn("- partitions.csv", content)
        self.assertIn("ESP-IDF: idf.py -p <PORT> flash", content)
        self.assertIn("Python tests: python -m pytest", content)
        self.assertIn("serial port", content)

        self.store.resolve_project(str(self.repo))
        self.assertEqual(1, profile.read_text(encoding="utf-8").count("## First Scan"))

    def test_add_turn_indexes_sqlite_and_builds_context(self) -> None:
        note = {
            "title": "Codex turn summary - repo",
            "content": "## Assistant Summary\nUpdated parser and ran tests.",
            "display": "Updated parser and ran tests.",
        }
        result = self.store.add_turn_summary(
            str(self.repo),
            note,
            {"session_id": "session-1", "turn_id": "turn-1"},
        )
        self.assertIsNotNone(result)
        self.assertTrue((self.memory_root / "engineering_memory.sqlite").exists())

        projects = self.store.list_projects()
        self.assertEqual(1, len(projects))
        self.assertEqual(str(self.repo.resolve()), projects[0]["project_root"])

        hits = self.store.search_project(str(self.repo), "parser")
        self.assertEqual(1, len(hits["hits"]))
        self.assertEqual("sqlite", hits["hits"][0]["source"])

        context = self.store.project_context(str(self.repo))
        self.assertIn("<codex_project_memory>", context["context"])
        self.assertIn("Updated parser and ran tests.", context["context"])

        progress = self.store.list_project_progress(str(self.repo))["progress"]
        self.assertEqual(1, len(progress))
        self.assertEqual("updated", progress[0]["status"])
        self.assertIn("Updated parser", progress[0]["completed"])

        facts = self.store.list_project_facts(str(self.repo), category="project")["facts"]
        fact_keys = {item["fact_key"] for item in facts}
        self.assertIn("code", fact_keys)
        self.assertIn("root", fact_keys)
        self.assertIn("memory_slug", fact_keys)

    def test_structured_engineering_memory_records_facts_interfaces_and_pins(self) -> None:
        fact = self.store.upsert_project_fact(
            str(self.repo),
            category="serial",
            key="default_baud",
            value="115200",
            source="README.md",
            confidence="verified",
            source_path=str(self.repo / "README.md"),
            verified=True,
        )["fact"]
        self.assertEqual("serial", fact["category"])
        self.assertEqual("default_baud", fact["fact_key"])
        self.assertEqual(1, fact["verified"])

        progress = self.store.update_project_progress(
            str(self.repo),
            status="verified",
            summary="Added UART wiring memory.",
            completed="Recorded debug UART and cross-checked schematic net.",
            next_steps="Confirm bootloader log baud on hardware.",
            verification="Reviewed README and schematic path.",
        )["progress"]
        self.assertEqual("verified", progress["status"])

        action = self.store.upsert_project_action_config(
            str(self.repo),
            action="build",
            command=["idf.py", "build"],
            action_cwd=str(self.repo),
            device_id="demo-device",
            framework="esp-idf",
            config_path=str(self.repo / ".codex-firmware-actions.json"),
            timeout_ms=600000,
            risk="safe",
            source="firmware-mcp devices.json",
            confidence="verified",
            verified=True,
        )["action_config"]
        self.assertEqual("build", action["action"])
        self.assertEqual(["idf.py", "build"], action["command"])
        self.assertEqual("demo-device", action["device_id"])

        interface = self.store.upsert_project_interface(
            str(self.repo),
            name="debug_uart",
            interface_type="uart",
            uart_no="UART0",
            baud_rate="115200",
            tx_pin="GPIO43",
            rx_pin="GPIO44",
            protocol="console_log",
            settings={"parity": "none", "stop_bits": 1},
            source="sdkconfig",
            confidence="observed",
        )["interface"]
        self.assertEqual("debug_uart", interface["name"])
        self.assertEqual("115200", interface["baud_rate"])
        self.assertEqual("none", interface["settings"]["parity"])

        pin = self.store.upsert_project_pin(
            str(self.repo),
            peripheral="UART0",
            signal="TX",
            gpio="GPIO43",
            board="main",
            net_name="U0TXD",
            connector="J1.3",
            direction="output",
            level="3V3",
            source="schematic_pdf",
            confidence="observed",
            verified=True,
        )["pin"]
        self.assertEqual("GPIO43", pin["gpio"])
        self.assertEqual(1, pin["verified"])

        facts = self.store.list_project_facts(str(self.repo), query="baud")["facts"]
        self.assertEqual(1, len(facts))
        actions = self.store.list_project_action_configs(str(self.repo), action="build")["actions"]
        self.assertEqual(1, len(actions))
        interfaces = self.store.list_project_interfaces(str(self.repo), query="debug_uart")["interfaces"]
        self.assertEqual(1, len(interfaces))
        pins = self.store.list_project_pin_map(str(self.repo), query="UART0 TX")["pins"]
        self.assertEqual(1, len(pins))

        context = self.store.project_engineering_context(str(self.repo))["context"]
        self.assertIn("## Working State (most recent first)", context)
        self.assertIn("serial.default_baud: 115200", context)
        self.assertIn("## Standard Actions", context)
        self.assertIn("build: command=idf.py build", context)
        self.assertIn("debug_uart: type=uart", context)
        self.assertIn("UART0.TX: gpio=GPIO43", context)

    def test_infer_progress_status_prefers_not_verified_over_verified(self) -> None:
        self.assertEqual("unverified", infer_progress_status("Build finished but not verified on hardware."))
        self.assertEqual("unverified", infer_progress_status("\u6784\u5efa\u5b8c\u6210\uff0c\u4f46\u672a\u9a8c\u8bc1\u771f\u673a\u3002"))

    def test_indexes_project_resource_paths_without_copying_contents(self) -> None:
        resource_root = Path(self.temp_dir.name) / "shared-resources"
        project_docs = resource_root / "Payload-SDK" / "hardware"
        other_docs = resource_root / "OtherProject"
        project_docs.mkdir(parents=True)
        other_docs.mkdir(parents=True)
        netlist = project_docs / "Payload-SDK_netlist.net"
        schematic = project_docs / "Payload-SDK_schematic.pdf"
        library = project_docs / "libpayloadsdk.a"
        unrelated = other_docs / "OtherProject_schematic.pdf"
        netlist.write_text("net contents should not be copied", encoding="utf-8")
        schematic.write_bytes(b"%PDF-1.4 placeholder")
        library.write_bytes(b"binary library")
        unrelated.write_bytes(b"%PDF-1.4 placeholder")
        os.environ[PROJECT_RESOURCE_ROOTS_ENV] = str(resource_root)

        scan = self.store.refresh_project_resources(str(self.repo), force=True)
        self.assertTrue(scan["scanned"])
        self.assertEqual(2, scan["indexed"])

        resources = self.store.list_project_resources(str(self.repo))["resources"]
        resource_paths = {Path(item["resource_path"]).name for item in resources}
        self.assertEqual({"Payload-SDK_netlist.net", "Payload-SDK_schematic.pdf"}, resource_paths)
        resource_types = {Path(item["resource_path"]).name: item["resource_type"] for item in resources}
        self.assertEqual("eda_netlist", resource_types["Payload-SDK_netlist.net"])
        self.assertEqual("schematic_pdf", resource_types["Payload-SDK_schematic.pdf"])

        netlist_resources = self.store.list_project_resources(str(self.repo), query="eda_netlist")["resources"]
        self.assertEqual(1, len(netlist_resources))
        self.assertEqual(str(netlist.resolve()), netlist_resources[0]["resource_path"])

        context = self.store.project_context(str(self.repo))["context"]
        self.assertIn("## Project Resource Paths", context)
        self.assertIn(str(netlist.resolve()), context)
        self.assertIn("resource_type: schematic_pdf", context)

    def test_indexes_project_resource_paths_by_short_project_code_directory(self) -> None:
        resource_root = Path(self.temp_dir.name) / "shared-resources"
        demo_docs = resource_root / "A100"
        demo_docs.mkdir(parents=True)
        schematic = demo_docs / "main-board-schematic.pdf"
        schematic.write_bytes(b"%PDF-1.4 placeholder")
        os.environ[PROJECT_RESOURCE_ROOTS_ENV] = str(resource_root)

        demo_repo = Path(self.temp_dir.name) / "Example-A100-Firmware"
        demo_repo.mkdir()
        (demo_repo / ".git").mkdir()
        scan = self.store.refresh_project_resources(str(demo_repo), force=True)

        self.assertEqual(1, scan["indexed"])
        resources = self.store.list_project_resources(str(demo_repo))["resources"]
        self.assertEqual(str(schematic.resolve()), resources[0]["resource_path"])
        self.assertEqual("a100", resources[0]["matched_alias"].casefold())

    def test_turn_summary_binds_mentioned_resource_path(self) -> None:
        resource_root = Path(self.temp_dir.name) / "shared-resources"
        resource_root.mkdir()
        netlist = resource_root / "Netlist_Schematic2_2026-03-19.tel"
        schematic = resource_root / "Main Board Schematic.pdf"
        netlist.write_text("generic netlist path", encoding="utf-8")
        schematic.write_bytes(b"%PDF-1.4 placeholder")
        os.environ[PROJECT_RESOURCE_ROOTS_ENV] = str(resource_root)

        note = {
            "title": "Codex turn summary - Payload-SDK",
            "content": "\n".join(
                [
                    "## Assistant Summary",
                    "Checked wiring references.",
                    "",
                    "## Files Mentioned",
                    f"- {netlist.resolve()}",
                    f"- {schematic.resolve()}",
                ]
            ),
            "display": "Checked wiring references.",
        }
        self.store.add_turn_summary(str(self.repo), note, {"session_id": "session-2", "turn_id": "turn-2"})

        resources = self.store.list_project_resources(str(self.repo), query="mentioned_in_turn")["resources"]
        resource_types = {Path(item["resource_path"]).name: item["resource_type"] for item in resources}
        self.assertEqual("eda_netlist", resource_types["Netlist_Schematic2_2026-03-19.tel"])
        self.assertEqual("schematic_pdf", resource_types["Main Board Schematic.pdf"])


if __name__ == "__main__":
    unittest.main()
