from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from codex_memory_mcp.turn_summary_hook import (
    SCOPE_GLOBAL_INFRASTRUCTURE,
    SCOPE_PROJECT_ENGINEERING,
    build_hook_output,
    build_turn_note,
    classify_turn_scope,
)


class TurnSummaryHookTest(unittest.TestCase):
    def test_build_turn_note_from_stop_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "session.jsonl"
            turn_id = "turn-1234567890"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "payload": {
                                    "type": "function_call",
                                    "name": "exec_command",
                                    "arguments": json.dumps({"cmd": "python -m unittest"}),
                                    "metadata": {"turn_id": turn_id},
                                }
                            }
                        ),
                        json.dumps(
                            {
                                "payload": {
                                    "type": "function_call",
                                    "name": "apply_patch",
                                    "arguments": "*** Update File: C:\\\\repo\\\\app.py",
                                    "metadata": {"turn_id": "other"},
                                }
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            note = build_turn_note(
                {
                    "hook_event_name": "Stop",
                    "session_id": "session-1",
                    "turn_id": turn_id,
                    "cwd": r"C:\repo",
                    "transcript_path": str(transcript),
                    "last_assistant_message": "Done. Updated C:\\repo\\app.py\n<oai-mem-citation>noise</oai-mem-citation>",
                }
            )

        self.assertIsNotNone(note)
        assert note is not None
        self.assertIn("Codex turn summary", note["title"])
        self.assertIn("Done. Updated C:\\repo\\app.py", note["content"])
        self.assertIn("exec_command: cmd=python -m unittest", note["content"])
        self.assertIn("- memory_scope: project_engineering", note["content"])
        self.assertEqual(SCOPE_PROJECT_ENGINEERING, note["memory_scope"])
        self.assertNotIn("noise", note["content"])
        self.assertEqual({}, build_hook_output(note))

        os.environ["CODEX_TURN_SUMMARY_DISPLAY"] = "systemMessage"
        self.addCleanup(os.environ.pop, "CODEX_TURN_SUMMARY_DISPLAY", None)
        output = build_hook_output(note)
        self.assertTrue(output["continue"])
        self.assertIn("/* 本轮总结：Done. Updated C:\\repo\\app.py", output["systemMessage"])


    def test_classifies_codex_mcp_work_as_global_infrastructure(self) -> None:
        scope = classify_turn_scope(
            "Updated the Codex memory MCP server, hooks.json, and config.toml.",
            [r"apply_patch: file=X:\tools\codex-memory-mcp\src\server.py"],
            [r"X:\tools\codex\config.toml"],
            r"X:\projects\demo-device",
        )
        self.assertEqual(SCOPE_GLOBAL_INFRASTRUCTURE, scope)

    def test_classifies_firmware_work_as_project_engineering(self) -> None:
        scope = classify_turn_scope(
            "Fixed ESP32 UART CRC handling and verified build.log.",
            ["exec_command: cmd=idf.py build"],
            [r"X:\projects\demo-device\main\uart.c"],
            r"X:\projects\demo-device",
        )
        self.assertEqual(SCOPE_PROJECT_ENGINEERING, scope)


if __name__ == "__main__":
    unittest.main()
