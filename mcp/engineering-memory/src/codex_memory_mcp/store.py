from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MEMORY_ROOT = Path.home() / ".codex" / "memories"
NOTE_DIR = Path("extensions") / "ad_hoc" / "notes"
SEARCH_EXTENSIONS = {".md", ".txt", ".jsonl"}
SKIP_DIRS = {".git", "__pycache__", "backups"}
MAX_SNIPPET_CHARS = 500
MAX_HITS_PER_FILE = 3

# Auto-generated turn summaries can outnumber hand-written memory by orders of
# magnitude, so files are visited best-tier-first and a single file cannot flood
# a result set. Lower tier wins.
TIER_CURATED = 0  # root-level memory files and skills/
TIER_DIGEST = 1  # per-thread rollups and hand-written ad hoc notes
TIER_PROJECT_TURN = 2  # per-turn summaries scoped to one project
TIER_AUTO_TURN = 3  # per-turn summaries in the global catch-all
AUTO_TURN_MARKER = "turn-summary"


class MemoryStoreError(ValueError):
    """Raised when a memory operation is invalid."""


@dataclass(frozen=True)
class SearchHit:
    path: str
    line: int
    snippet: str


class MemoryStore:
    def __init__(self, root: Path | None = None) -> None:
        env_root = os.environ.get("CODEX_MEMORY_ROOT")
        chosen_root = root if root is not None else Path(env_root) if env_root else DEFAULT_MEMORY_ROOT
        self.root = chosen_root.expanduser().resolve()
        self.notes_dir = self.root / NOTE_DIR

    def ensure_ready(self) -> None:
        if not self.root.is_dir():
            raise MemoryStoreError(f"memory root is not a directory: {self.root}")
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def list_files(self, limit: int = 200) -> list[dict[str, Any]]:
        self.ensure_ready()
        limit = self._positive_int(limit, "limit", maximum=1000)
        items: list[dict[str, Any]] = []
        for path in self._iter_memory_files():
            stat = path.stat()
            items.append(
                {
                    "path": self._relative(path),
                    "size": stat.st_size,
                    "modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
            if len(items) >= limit:
                break
        return items

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        self.ensure_ready()
        max_results = self._positive_int(max_results, "max_results", maximum=100)
        query = query.strip()
        if not query:
            raise MemoryStoreError("query must not be empty")

        tokens = [token.casefold() for token in re.findall(r"[\w\-.\\:/]+", query)]
        if not tokens:
            tokens = [query.casefold()]

        hits: list[SearchHit] = []
        for path in self._iter_memory_files():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            relative = self._relative(path)
            file_hits = 0
            for line_no, line in enumerate(lines, start=1):
                lower = line.casefold()
                if all(token in lower for token in tokens):
                    hits.append(SearchHit(relative, line_no, self._compact(line)))
                    if len(hits) >= max_results:
                        return [hit.__dict__ for hit in hits]
                    file_hits += 1
                    if file_hits >= MAX_HITS_PER_FILE:
                        break
        return [hit.__dict__ for hit in hits]

    def read(self, path: str, max_chars: int = 12000) -> dict[str, Any]:
        self.ensure_ready()
        max_chars = self._positive_int(max_chars, "max_chars", maximum=100000)
        target = self._resolve_user_path(path)
        if target.suffix.lower() not in SEARCH_EXTENSIONS:
            raise MemoryStoreError(f"unsupported memory file extension: {target.suffix}")
        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_chars
        return {
            "path": self._relative(target),
            "truncated": truncated,
            "text": text[:max_chars],
        }

    def add_note(self, title: str, content: str, tags: list[str] | None = None) -> dict[str, Any]:
        self.ensure_ready()
        title = self._single_line(title, maximum=160)
        content = content.strip()
        if tags is None:
            tags = []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise MemoryStoreError("tags must be a list of strings")
        clean_tags = [self._single_line(tag, maximum=64) for tag in tags]
        clean_tags = [tag for tag in clean_tags if tag]
        if not title:
            raise MemoryStoreError("title must not be empty")
        if not content:
            raise MemoryStoreError("content must not be empty")

        now = dt.datetime.now().astimezone()
        slug = self._slug(title)
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        path = self._next_note_path(timestamp, slug)
        tag_line = ", ".join(clean_tags)
        body = [
            f"# {title}",
            "",
            f"- created_at: {now.isoformat(timespec='seconds')}",
            f"- source: codex-memory-mcp",
        ]
        if tag_line:
            body.append(f"- tags: {tag_line}")
        body.extend(["", content, ""])
        path.write_text("\n".join(body), encoding="utf-8")
        return {"path": self._relative(path), "absolute_path": str(path)}

    def _iter_memory_files(self) -> list[Path]:
        entries: list[tuple[int, float, str, Path]] = []
        for path in self.root.rglob("*"):
            parts = path.relative_to(self.root).parts
            if any(part in SKIP_DIRS for part in parts):
                continue
            if path.suffix.lower() not in SEARCH_EXTENSIONS or not path.is_file():
                continue
            relative = "/".join(parts).lower()
            try:
                recency = -path.stat().st_mtime
            except OSError:
                recency = 0.0
            entries.append((self._rank_tier(relative), recency, relative, path))
        entries.sort(key=lambda entry: entry[:3])
        return [entry[3] for entry in entries]

    @staticmethod
    def _rank_tier(relative: str) -> int:
        if AUTO_TURN_MARKER in relative.rsplit("/", 1)[-1]:
            return TIER_AUTO_TURN
        if relative.startswith("projects/"):
            return TIER_PROJECT_TURN
        if relative.startswith("rollout_summaries/") or relative.startswith("extensions/"):
            return TIER_DIGEST
        return TIER_CURATED

    def _resolve_user_path(self, path: str) -> Path:
        if not path.strip():
            raise MemoryStoreError("path must not be empty")
        raw = Path(path)
        target = raw if raw.is_absolute() else self.root / raw
        resolved = target.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise MemoryStoreError("path must stay inside memory root") from exc
        if not resolved.exists() or not resolved.is_file():
            raise MemoryStoreError(f"memory file does not exist: {path}")
        return resolved

    def _relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root)).replace("\\", "/")

    @staticmethod
    def _compact(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()[:MAX_SNIPPET_CHARS]

    @staticmethod
    def _slug(title: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title.lower()).strip("-")
        return slug[:80] or "note"

    def _next_note_path(self, timestamp: str, slug: str) -> Path:
        path = self.notes_dir / f"{timestamp}-{slug}.md"
        counter = 2
        while path.exists():
            path = self.notes_dir / f"{timestamp}-{slug}-{counter}.md"
            counter += 1
        return path

    @staticmethod
    def _single_line(value: str, maximum: int) -> str:
        return re.sub(r"\s+", " ", str(value)).strip()[:maximum]

    @staticmethod
    def _positive_int(value: int, name: str, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise MemoryStoreError(f"{name} must be an integer") from exc
        if parsed < 1:
            raise MemoryStoreError(f"{name} must be at least 1")
        if parsed > maximum:
            raise MemoryStoreError(f"{name} must be at most {maximum}")
        return parsed
