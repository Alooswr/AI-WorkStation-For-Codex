from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_memory_mcp.store import MemoryStore, MemoryStoreError


class MemoryStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "MEMORY.md").write_text(
            "# Memory\n\n- conclusion first and concise reporting\n",
            encoding="utf-8",
        )
        nested = self.root / "rollout_summaries"
        nested.mkdir()
        (nested / "session.jsonl").write_text(
            '{"event":"embedded-skill-router used"}\n',
            encoding="utf-8",
        )
        self.store = MemoryStore(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_search_returns_line_hits(self) -> None:
        hits = self.store.search("conclusion first", 5)
        self.assertEqual(1, len(hits))
        self.assertEqual("MEMORY.md", hits[0]["path"])
        self.assertEqual(3, hits[0]["line"])

    def test_read_rejects_path_escape(self) -> None:
        outside = self.root.parent / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        with self.assertRaises(MemoryStoreError):
            self.store.read(str(outside))

    def test_read_truncates(self) -> None:
        result = self.store.read("MEMORY.md", max_chars=8)
        self.assertTrue(result["truncated"])
        self.assertEqual("# Memory", result["text"])

    def test_add_note_sanitizes_title_and_tags(self) -> None:
        result = self.store.add_note("Smoke\nTest", "temporary note content", ["alpha\nbeta", ""])
        path = self.root / result["path"]
        text = path.read_text(encoding="utf-8")
        self.assertIn("# Smoke Test", text)
        self.assertIn("- tags: alpha beta", text)
        self.assertIn("temporary note content", text)

    def test_invalid_limits_are_rejected(self) -> None:
        with self.assertRaises(MemoryStoreError):
            self.store.search("memory", 0)

    def test_invalid_tags_are_rejected(self) -> None:
        with self.assertRaises(MemoryStoreError):
            self.store.add_note("Title", "content", "not-a-list")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
