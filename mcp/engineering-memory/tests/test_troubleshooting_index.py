from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from codex_memory_mcp.project_context_hook import HOOK_MODE_ENV, main as project_context_main
from codex_memory_mcp.store import MemoryStore, MemoryStoreError
from codex_memory_mcp.troubleshooting_index import TroubleshootingIndex


class TroubleshootingIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.temp_dir.name) / "memory"
        self.memory_root.mkdir()
        self.index = TroubleshootingIndex(MemoryStore(self.memory_root))
        self.old_memory_root = os.environ.get("CODEX_MEMORY_ROOT")
        self.old_hook_mode = os.environ.get(HOOK_MODE_ENV)
        os.environ["CODEX_MEMORY_ROOT"] = str(self.memory_root)

    def tearDown(self) -> None:
        if self.old_memory_root is None:
            os.environ.pop("CODEX_MEMORY_ROOT", None)
        else:
            os.environ["CODEX_MEMORY_ROOT"] = self.old_memory_root
        if self.old_hook_mode is None:
            os.environ.pop(HOOK_MODE_ENV, None)
        else:
            os.environ[HOOK_MODE_ENV] = self.old_hook_mode
        self.temp_dir.cleanup()

    def test_search_seeded_fault_case(self) -> None:
        matches = self.index.search("Stop hook warning systemMessage", max_results=3)
        self.assertTrue(matches)
        self.assertEqual("codex-hook-systemmessage-warning", matches[0]["case_id"])
        self.assertIn("Do not use systemMessage", matches[0]["reminder"])

    def test_search_rejects_more_than_three_troubleshooting_hints(self) -> None:
        with self.assertRaises(MemoryStoreError):
            self.index.search("hook warning sqlite mcp powershell", max_results=4)

    def test_prompt_context_limits_to_top_three_matches(self) -> None:
        prompt = (
            "Stop hook warning systemMessage. PowerShell Chinese mojibake ????. "
            "SQLite WinError 32 file locked. MCP not loaded missing tool required. "
            "hook trust /hooks not running."
        )
        matches = self.index.search(prompt, max_results=3)
        context = self.index.context_for_prompt(prompt)
        headings = [line for line in context.splitlines() if line.startswith("## ")]
        self.assertEqual(3, len(headings))
        self.assertEqual([f"## {match['title']}" for match in matches], headings)
        self.assertEqual(
            sorted((int(match["score"]) for match in matches), reverse=True),
            [int(match["score"]) for match in matches],
        )

    def test_hook_adds_troubleshooting_context_from_prompt(self) -> None:
        os.environ[HOOK_MODE_ENV] = "alerts"
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "cwd": "",
            "prompt": "PowerShell pipe makes Chinese text mojibake and ???? in hook output",
        }
        stdin_path = self.memory_root / "payload.json"
        stdin_path.write_text(json.dumps(payload), encoding="utf-8")

        import io
        import sys

        old_stdin = sys.stdin
        old_stdout = sys.stdout
        try:
            sys.stdin = open(stdin_path, "r", encoding="utf-8")
            sys.stdout = io.StringIO()
            self.assertEqual(0, project_context_main())
            output = sys.stdout.getvalue()
        finally:
            sys.stdin.close()
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        decoded = json.loads(output)
        context = decoded["hookSpecificOutput"]["additionalContext"]
        self.assertIn("<codex_troubleshooting_memory>", context)
        self.assertIn("Chinese text becomes question marks", context)

    def test_hook_is_silent_by_default_to_avoid_cli_context_dump(self) -> None:
        os.environ.pop(HOOK_MODE_ENV, None)
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "cwd": "",
            "prompt": "PowerShell pipe makes Chinese text mojibake and ???? in hook output",
        }
        stdin_path = self.memory_root / "payload.json"
        stdin_path.write_text(json.dumps(payload), encoding="utf-8")

        import io
        import sys

        old_stdin = sys.stdin
        old_stdout = sys.stdout
        try:
            sys.stdin = open(stdin_path, "r", encoding="utf-8")
            sys.stdout = io.StringIO()
            self.assertEqual(0, project_context_main())
            output = sys.stdout.getvalue()
        finally:
            sys.stdin.close()
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        self.assertEqual("", output)


if __name__ == "__main__":
    unittest.main()
