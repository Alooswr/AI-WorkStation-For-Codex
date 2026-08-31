from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .store import MemoryStore, MemoryStoreError


PROJECTS_DIR = Path("projects")
TURNS_DIR = "turns"
PROJECT_JSON = "project.json"
PROFILE_MD = "profile.md"
MAX_CONTEXT_CHARS = 8000
MAX_RECENT_TURNS = 6
MAX_RECENT_PROGRESS = 3
MAX_ENGINEERING_FACTS_IN_CONTEXT = 20
MAX_ENGINEERING_ACTIONS_IN_CONTEXT = 12
MAX_ENGINEERING_INTERFACES_IN_CONTEXT = 20
MAX_ENGINEERING_PINS_IN_CONTEXT = 30
STANDARD_PROJECT_ACTIONS = ("build", "flash", "monitor", "clean", "test", "reset")
STANDARD_PROJECT_ACTION_SET = frozenset(STANDARD_PROJECT_ACTIONS)
DB_FILENAME = "engineering_memory.sqlite"
PROJECT_RESOURCE_ROOTS_ENV = "CODEX_PROJECT_RESOURCE_ROOTS"
PROJECT_RESOURCE_MAX_SCAN_FILES_ENV = "CODEX_PROJECT_RESOURCE_MAX_SCAN_FILES"
PROJECT_RESOURCE_REFRESH_SECONDS_ENV = "CODEX_PROJECT_RESOURCE_REFRESH_SECONDS"
PROJECT_RESOURCE_ROOTS_JSON = "project_resource_roots.json"
MAX_PROJECT_RESOURCES_IN_CONTEXT = 12
MAX_RESOURCE_SCAN_FILES = 20000
MAX_PROJECT_PROFILE_SCAN_FILES = 5000
MAX_PROJECT_PROFILE_ITEMS = 12
SESSION_INTENT_DIR = ".session_intent"
MAX_INTENT_CHARS = 400
ROLLOUT_SUMMARIES_DIR = "rollout_summaries"
MAX_ROLLOUT_SUMMARY_CHARS = 700
DEFAULT_RESOURCE_REFRESH_SECONDS = 3600
SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".s", ".asm", ".py"}
ENTRY_SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".py"}
CONFIG_FILE_NAMES = {
    "CMakeLists.txt",
    "Makefile",
    "makefile",
    "Kconfig",
    "sdkconfig",
    "sdkconfig.defaults",
    "idf_component.yml",
    "idf_component.yaml",
    "pyproject.toml",
    "package.json",
    "platformio.ini",
    "lv_conf.h",
}
CONFIG_EXTENSIONS = {".uvprojx", ".uvproj", ".ewp", ".eww", ".ioc", ".ld", ".csv", ".ini", ".toml", ".yml", ".yaml"}
ENTRY_MARKERS = (
    "void app_main(",
    "int main(",
    "void main(",
    "int core_main(",
    "def main(",
    "if __name__ == \"__main__\"",
    "if __name__ == '__main__'",
)
EDA_NETLIST_EXTENSIONS = {".net", ".cir", ".sp", ".spice", ".tel"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
RESOURCE_TYPE_SCORE = {
    "eda_netlist": 40,
    "schematic_pdf": 35,
    "pdf": 10,
    "document": 5,
    "archive": 3,
    "other": 0,
}
IGNORED_RESOURCE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".idea",
    ".vscode",
}
GENERIC_RESOURCE_ALIASES = {
    "codex",
    "desktop",
    "documents",
    "downloads",
    "esp32",
    "esp32s2",
    "esp32s3",
    "esp32c2",
    "esp32c3",
    "esp32c5",
    "esp32c6",
    "esp32p4",
    "firmware",
    "project",
    "projects",
    "repo",
    "repos",
    "source",
    "src",
    "user",
    "users",
    "work",
    "工程",
    "工程资料",
    "文档",
    "资料",
    "项目",
}


class ProjectMemoryStore:
    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self.memory_store = memory_store or MemoryStore()
        self.root = self.memory_store.root
        self.projects_dir = self.root / PROJECTS_DIR
        self.db_path = self.root / DB_FILENAME

    def ensure_ready(self) -> None:
        self.memory_store.ensure_ready()
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _intent_paths(self, session_id: str, cwd: str) -> list[Path]:
        # Keyed by session when the client supplies one, with a cwd key as fallback so
        # the Stop hook still finds the prompt if only one of the two hooks sees an id.
        keys = [safe_slug(str(value)) for value in (session_id, cwd) if str(value or "").strip()]
        keys = [key for key in keys if key] or ["unknown"]
        folder = self.root / SESSION_INTENT_DIR
        return [folder / f"{key}.txt" for key in keys]

    def stash_user_intent(self, session_id: str, cwd: str, prompt: str) -> None:
        """Record the user's own wording so the Stop hook can state intent without a model."""
        text = re.sub(r"\s+", " ", str(prompt or "")).strip()
        if not text:
            return
        for path in self._intent_paths(session_id, cwd):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text[:MAX_INTENT_CHARS], encoding="utf-8")
            except OSError:
                continue


    def _latest_rollout_summary(self, project_root: str) -> str:
        """Newest per-thread rollout summary recorded for this project, if any."""
        folder = self.root / ROLLOUT_SUMMARIES_DIR
        if not folder.is_dir():
            return ""
        target = str(project_root or "").strip().rstrip("\\").casefold()
        if not target:
            return ""
        best: tuple[float, str] | None = None
        for path in folder.glob("*.md"):
            try:
                head = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = re.search(r"^cwd:\s*(.+)$", head[:600], re.M)
            if not match:
                continue
            cwd = match.group(1).strip()
            if cwd.startswith("\\\\?\\"):  # Windows extended-length path prefix
                cwd = cwd[4:]
            if cwd.rstrip("\\").casefold() != target:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if best is None or mtime > best[0]:
                best = (mtime, head)
        if best is None:
            return ""
        lines = best[1].splitlines()
        # drop the machine header block that precedes the narrative
        start = next((i for i, line in enumerate(lines) if line.startswith("#")), len(lines))
        body = []
        for line in lines[start:]:
            # demote the summary's own headings so they cannot be mistaken for
            # sections of the surrounding context pack
            body.append(f"##{line}" if line.startswith("#") else line)
        return "\n".join(body).strip()[:MAX_ROLLOUT_SUMMARY_CHARS]

    def take_user_intent(self, session_id: str, cwd: str) -> str:
        text = ""
        for path in self._intent_paths(session_id, cwd):
            try:
                if not text:
                    text = path.read_text(encoding="utf-8", errors="replace").strip()
                path.unlink()
            except OSError:
                continue
        return text

    def resolve_project(self, cwd: str | Path) -> dict[str, Any]:
        self.ensure_ready()
        project_root = find_project_root(Path(cwd))
        slug = project_slug(project_root)
        project_dir = self.projects_dir / slug
        project_dir.mkdir(parents=True, exist_ok=True)

        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        meta = self._read_project_json(project_dir)
        meta.update(
            {
                "slug": slug,
                "project_root": str(project_root),
                "last_seen": now,
            }
        )
        meta.setdefault("created_at", now)
        aliases = set(meta.get("aliases") or [])
        aliases.add(str(Path(cwd).resolve()))
        aliases.add(str(project_root))
        meta["aliases"] = sorted(aliases)
        self._write_project_json(project_dir, meta)
        self._ensure_profile(project_dir, meta)
        self._upsert_project(meta)
        self._ensure_project_identity_facts(meta)
        return {"slug": slug, "project_root": str(project_root), "project_dir": project_dir, "meta": meta}

    def add_turn_summary(self, cwd: str, note: dict[str, str], payload: dict[str, Any]) -> dict[str, Any] | None:
        if not cwd:
            return None
        project = self.resolve_project(cwd)
        project_dir: Path = project["project_dir"]
        turns_dir = project_dir / TURNS_DIR
        turns_dir.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now().astimezone()
        turn_id = str(payload.get("turn_id") or "unknown")
        path = next_available_path(turns_dir / f"{now.strftime('%Y%m%d-%H%M%S')}-{safe_slug(turn_id[:16] or 'turn')}.md")
        body = [
            f"# {note.get('title') or 'Codex turn summary'}",
            "",
            f"- created_at: {now.isoformat(timespec='seconds')}",
            f"- source: codex-memory-mcp-project",
            f"- project_root: {project['project_root']}",
            f"- session_id: {payload.get('session_id') or 'unknown'}",
            f"- turn_id: {turn_id}",
            "",
            note.get("content", "").strip(),
            "",
        ]
        path.write_text("\n".join(body), encoding="utf-8")
        rel_path = self._relative(path)
        self._insert_turn(
            project_slug=project["slug"],
            path=rel_path,
            title=note.get("title") or "Codex turn summary",
            summary=note.get("display") or "",
            content=note.get("content", ""),
            payload=payload,
            created_at=now.isoformat(timespec="seconds"),
        )
        self._insert_project_progress(
            project_slug=project["slug"],
            status=infer_progress_status(note.get("content", "")),
            summary=note.get("user_intent") or note.get("display") or note.get("title") or "Codex turn summary",
            completed=extract_progress_completed(note.get("content", "")),
            blockers=extract_progress_blockers(note.get("content", "")),
            next_steps=extract_progress_next_steps(note.get("content", "")),
            verification=extract_progress_verification(note.get("content", "")),
            source_turn_path=rel_path,
            payload=payload,
            created_at=now.isoformat(timespec="seconds"),
        )
        self._index_mentioned_project_resources(project, note.get("content", ""))
        return {"slug": project["slug"], "path": rel_path, "absolute_path": str(path)}

    def project_context(self, cwd: str, max_chars: int = MAX_CONTEXT_CHARS) -> dict[str, Any]:
        self.ensure_ready()
        max_chars = positive_int(max_chars, "max_chars", maximum=50000)
        self.refresh_project_resources(cwd)
        project = self.resolve_project(cwd)
        project_dir: Path = project["project_dir"]
        profile = read_text_if_exists(project_dir / PROFILE_MD)
        recent = self._recent_turns_from_db(project["slug"], limit=MAX_RECENT_TURNS)
        if not recent:
            recent = self._recent_turns(project_dir, limit=MAX_RECENT_TURNS)
        resources = self._project_resources_from_db(project["slug"], limit=MAX_PROJECT_RESOURCES_IN_CONTEXT)
        if not profile and not recent and not resources:
            return {"slug": project["slug"], "project_root": project["project_root"], "context": ""}

        sections = [
            "<codex_project_memory>",
            f"Project root: {project['project_root']}",
            f"Project memory slug: {project['slug']}",
            (
                "Automatic memory policy: the Stop hook writes global turn summaries automatically; "
                "only project_engineering turns are stored in this project memory."
            ),
            (
                "Manual MCP note writes still require an explicit user request via add_engineering_memory_note."
            ),
            "",
        ]
        if profile:
            sections.extend(["## Project Profile", profile.strip(), ""])
        if recent:
            sections.append("## Recent Project Turn Summaries")
            for item in recent:
                sections.extend([f"### {item['path']}", item["text"].strip(), ""])
        if resources:
            sections.append("## Project Resource Paths")
            sections.extend(
                [
                    "These are indexed file locations from the configured shared project-resource folders.",
                    "Do not assume file contents are stored in memory; open the referenced files when needed.",
                    "",
                ]
            )
            for item in resources:
                sections.extend(
                    [
                        f"### {item['resource_path']}",
                        f"- name: {item['name']}",
                        f"- resource_type: {item['resource_type']}",
                        f"- matched_alias: {item['matched_alias']}",
                        f"- extension: {item['extension']}",
                        f"- modified_at: {item['mtime']}",
                        "",
                    ]
                )
        sections.append("</codex_project_memory>")
        context = "\n".join(sections).strip()
        return {
            "slug": project["slug"],
            "project_root": project["project_root"],
            "context": context[:max_chars],
            "truncated": len(context) > max_chars,
        }

    def search_project(self, cwd: str, query: str, max_results: int = 20) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        hits = self._search_turns_from_db(project["slug"], query, max_results)
        if not hits:
            project_dir: Path = project["project_dir"]
            hits = search_files(project_dir, self.root, query, max_results)
        return {"slug": project["slug"], "project_root": project["project_root"], "hits": hits}

    def project_engineering_context(self, cwd: str, max_chars: int = MAX_CONTEXT_CHARS) -> dict[str, Any]:
        self.ensure_ready()
        max_chars = positive_int(max_chars, "max_chars", maximum=50000)
        self.refresh_project_resources(cwd)
        project = self.resolve_project(cwd)
        progress = self._project_progress_from_db(project["slug"], limit=MAX_RECENT_PROGRESS)
        facts = self._project_facts_from_db(project["slug"], limit=MAX_ENGINEERING_FACTS_IN_CONTEXT)
        actions = self._project_actions_from_db(project["slug"], limit=MAX_ENGINEERING_ACTIONS_IN_CONTEXT)
        interfaces = self._project_interfaces_from_db(project["slug"], limit=MAX_ENGINEERING_INTERFACES_IN_CONTEXT)
        pins = self._project_pin_map_from_db(project["slug"], limit=MAX_ENGINEERING_PINS_IN_CONTEXT)
        resources = self._project_resources_from_db(project["slug"], limit=MAX_PROJECT_RESOURCES_IN_CONTEXT)

        sections = [
            "<codex_project_engineering_context>",
            f"Project root: {project['project_root']}",
            f"Project memory slug: {project['slug']}",
            "",
        ]
        thread_summary = self._latest_rollout_summary(project["project_root"])
        if thread_summary:
            sections.extend(["## Current Thread", thread_summary, ""])
        if progress:
            sections.append("## Working State (most recent first)")
            for item in progress:
                sections.append(f"### {item['created_at']} ({item['status']})")
                intent = trim_state_field(item["summary"])
                sections.append(f"- intent: {intent}")
                # did/blockers/next_steps are keyword-extracted from the same sentences,
                # so emit each distinct value once and keep it short.
                seen = {intent}
                for label in ("completed", "blockers", "next_steps"):
                    value = trim_state_field(item[label])
                    if value and value not in seen:
                        seen.add(value)
                        sections.append(f"- {'did' if label == 'completed' else label}: {value}")
                sections.append("")
        if facts:
            sections.append("## Project Facts")
            for item in facts:
                sections.append(
                    f"- {item['category']}.{item['fact_key']}: {item['fact_value']} "
                    f"(confidence={item['confidence']}, source={item['source']})"
                )
            sections.append("")
        if actions:
            sections.append("## Standard Actions")
            for item in actions:
                command = " ".join(item["command"])
                sections.append(
                    f"- {item['action']}: command={command}, cwd={item['cwd']}, "
                    f"device_id={item['device_id']}, framework={item['framework']}, "
                    f"config_path={item['config_path']}, timeout_ms={item['timeout_ms']}, "
                    f"risk={item['risk']}, confidence={item['confidence']}"
                )
            sections.append("")
        if interfaces:
            sections.append("## Interfaces")
            for item in interfaces:
                sections.append(
                    f"- {item['name']}: type={item['interface_type']}, uart={item['uart_no']}, "
                    f"baud={item['baud_rate']}, tx={item['tx_pin']}, rx={item['rx_pin']}, "
                    f"protocol={item['protocol']}, confidence={item['confidence']}"
                )
            sections.append("")
        if pins:
            sections.append("## Pin Map")
            for item in pins:
                sections.append(
                    f"- {item['peripheral']}.{item['signal']}: gpio={item['gpio']}, "
                    f"net={item['net_name']}, connector={item['connector']}, "
                    f"direction={item['direction']}, verified={bool(item['verified'])}"
                )
            sections.append("")
        if resources:
            sections.append("## Resource Paths")
            for item in resources:
                sections.append(f"- {item['resource_type']}: {item['resource_path']}")
            sections.append("")
        sections.append("</codex_project_engineering_context>")
        context = "\n".join(sections).strip()
        return {
            "slug": project["slug"],
            "project_root": project["project_root"],
            "context": context[:max_chars],
            "truncated": len(context) > max_chars,
        }

    def upsert_project_fact(
        self,
        cwd: str,
        category: str,
        key: str,
        value: str,
        source: str = "manual",
        confidence: str = "manual",
        notes: str = "",
        source_path: str = "",
        verified: bool = False,
    ) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        item = self._upsert_project_fact(
            project["slug"],
            category,
            key,
            value,
            source,
            confidence,
            notes,
            source_path,
            verified,
        )
        return {"slug": project["slug"], "project_root": project["project_root"], "fact": item}

    def list_project_facts(self, cwd: str, category: str = "", query: str = "", limit: int = 100) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        facts = self._project_facts_from_db(project["slug"], category=category, query=query, limit=limit)
        return {"slug": project["slug"], "project_root": project["project_root"], "facts": facts}

    def update_project_progress(
        self,
        cwd: str,
        status: str,
        summary: str,
        completed: str = "",
        blockers: str = "",
        next_steps: str = "",
        verification: str = "",
    ) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        item = self._insert_project_progress(
            project_slug=project["slug"],
            status=status,
            summary=summary,
            completed=completed,
            blockers=blockers,
            next_steps=next_steps,
            verification=verification,
            source_turn_path="",
            payload={},
        )
        return {"slug": project["slug"], "project_root": project["project_root"], "progress": item}

    def list_project_progress(self, cwd: str, limit: int = 20) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        progress = self._project_progress_from_db(project["slug"], limit=limit)
        return {"slug": project["slug"], "project_root": project["project_root"], "progress": progress}

    def upsert_project_action_config(
        self,
        cwd: str,
        action: str,
        command: list[str],
        action_cwd: str = "",
        device_id: str = "",
        framework: str = "",
        config_path: str = "",
        timeout_ms: int | None = None,
        risk: str = "",
        source: str = "manual",
        confidence: str = "manual",
        verified: bool = False,
        notes: str = "",
    ) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        item = self._upsert_project_action_config(
            project["slug"],
            action,
            command,
            action_cwd,
            device_id,
            framework,
            config_path,
            timeout_ms,
            risk,
            source,
            confidence,
            verified,
            notes,
        )
        return {"slug": project["slug"], "project_root": project["project_root"], "action_config": item}

    def list_project_action_configs(
        self,
        cwd: str,
        action: str = "",
        query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        actions = self._project_actions_from_db(project["slug"], action=action, query=query, limit=limit)
        return {"slug": project["slug"], "project_root": project["project_root"], "actions": actions}

    def upsert_project_interface(
        self,
        cwd: str,
        name: str,
        interface_type: str = "",
        uart_no: str = "",
        baud_rate: str = "",
        tx_pin: str = "",
        rx_pin: str = "",
        protocol: str = "",
        settings: dict[str, Any] | None = None,
        source: str = "manual",
        confidence: str = "manual",
        notes: str = "",
    ) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        item = self._upsert_project_interface(
            project["slug"],
            name,
            interface_type,
            uart_no,
            baud_rate,
            tx_pin,
            rx_pin,
            protocol,
            settings or {},
            source,
            confidence,
            notes,
        )
        return {"slug": project["slug"], "project_root": project["project_root"], "interface": item}

    def list_project_interfaces(self, cwd: str, query: str = "", limit: int = 100) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        interfaces = self._project_interfaces_from_db(project["slug"], query=query, limit=limit)
        return {"slug": project["slug"], "project_root": project["project_root"], "interfaces": interfaces}

    def upsert_project_pin(
        self,
        cwd: str,
        peripheral: str,
        signal: str,
        gpio: str = "",
        board: str = "",
        net_name: str = "",
        connector: str = "",
        direction: str = "",
        level: str = "",
        pull: str = "",
        source: str = "manual",
        confidence: str = "manual",
        verified: bool = False,
        notes: str = "",
    ) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        item = self._upsert_project_pin(
            project["slug"],
            peripheral,
            signal,
            gpio,
            board,
            net_name,
            connector,
            direction,
            level,
            pull,
            source,
            confidence,
            verified,
            notes,
        )
        return {"slug": project["slug"], "project_root": project["project_root"], "pin": item}

    def list_project_pin_map(self, cwd: str, query: str = "", limit: int = 200) -> dict[str, Any]:
        project = self.resolve_project(cwd)
        pins = self._project_pin_map_from_db(project["slug"], query=query, limit=limit)
        return {"slug": project["slug"], "project_root": project["project_root"], "pins": pins}

    def refresh_project_resources(
        self,
        cwd: str,
        force: bool = False,
        max_files: int = MAX_RESOURCE_SCAN_FILES,
    ) -> dict[str, Any]:
        self.ensure_ready()
        if max_files == MAX_RESOURCE_SCAN_FILES:
            max_files = configured_max_resource_scan_files()
        max_files = positive_int(max_files, "max_files", maximum=200000)
        project = self.resolve_project(cwd)
        roots = configured_project_resource_roots(self.root)
        if not roots:
            return {
                "slug": project["slug"],
                "project_root": project["project_root"],
                "configured_roots": [],
                "scanned": False,
                "reason": f"{PROJECT_RESOURCE_ROOTS_ENV} is not configured",
                "indexed": 0,
            }

        meta = dict(project["meta"])
        if not force and not resource_refresh_due(str(meta.get("last_resource_scan_at") or "")):
            return {
                "slug": project["slug"],
                "project_root": project["project_root"],
                "configured_roots": [str(root) for root in roots],
                "scanned": False,
                "reason": "refresh interval has not elapsed",
                "indexed": len(self._project_resources_from_db(project["slug"], limit=1000)),
            }

        scan = self._scan_project_resources(project, roots, max_files)
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        meta["resource_roots"] = [str(root) for root in roots]
        meta["last_resource_scan_at"] = now
        self._write_project_json(project["project_dir"], meta)
        return scan

    def list_project_resources(self, cwd: str, query: str = "", limit: int = 50) -> dict[str, Any]:
        self.refresh_project_resources(cwd)
        project = self.resolve_project(cwd)
        resources = self._project_resources_from_db(project["slug"], query=query, limit=limit)
        return {
            "slug": project["slug"],
            "project_root": project["project_root"],
            "resource_roots": [str(root) for root in configured_project_resource_roots(self.root)],
            "resources": resources,
        }

    def list_projects(self, limit: int = 200) -> list[dict[str, Any]]:
        self.ensure_ready()
        limit = positive_int(limit, "limit", maximum=1000)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT slug, project_root, created_at, last_seen
                FROM projects
                ORDER BY last_seen DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _recent_turns(self, project_dir: Path, limit: int) -> list[dict[str, str]]:
        turns_dir = project_dir / TURNS_DIR
        if not turns_dir.is_dir():
            return []
        items = sorted(turns_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
        return [{"path": self._relative(path), "text": path.read_text(encoding="utf-8", errors="replace")} for path in items]

    def _recent_turns_from_db(self, project_slug: str, limit: int) -> list[dict[str, str]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT path, content
                FROM project_turns
                WHERE project_slug = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (project_slug, limit),
            ).fetchall()
        return [{"path": row["path"], "text": row["content"]} for row in rows]

    def _ensure_profile(self, project_dir: Path, meta: dict[str, Any]) -> None:
        profile = project_dir / PROFILE_MD
        scan = scan_project_profile(Path(str(meta["project_root"])))
        first_scan = render_first_scan_section(scan)
        if profile.exists():
            existing = profile.read_text(encoding="utf-8", errors="replace")
            if "## First Scan" in existing:
                return
            profile.write_text(insert_first_scan_section(existing, first_scan), encoding="utf-8")
            return
        lines = [
            f"# Project Memory: {Path(str(meta['project_root'])).name}",
            "",
            f"- project_root: {meta['project_root']}",
            f"- slug: {meta['slug']}",
            f"- created_at: {meta['created_at']}",
            "",
            first_scan,
            "",
            "## Stable Notes",
            "",
            "- Add durable project conventions, build commands, architecture notes, and recurring pitfalls here.",
            "",
        ]
        profile.write_text("\n".join(lines), encoding="utf-8")

    def _read_project_json(self, project_dir: Path) -> dict[str, Any]:
        path = project_dir / PROJECT_JSON
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _write_project_json(project_dir: Path, meta: dict[str, Any]) -> None:
        (project_dir / PROJECT_JSON).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root)).replace("\\", "/")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.executescript(
                    """
                    PRAGMA journal_mode = DELETE;
                    CREATE TABLE IF NOT EXISTS projects (
                        slug TEXT PRIMARY KEY,
                        project_root TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_seen TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS project_aliases (
                        alias TEXT PRIMARY KEY,
                        project_slug TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug)
                    );
                    CREATE TABLE IF NOT EXISTS project_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        path TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        content TEXT NOT NULL,
                        session_id TEXT,
                        turn_id TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_turns_project_created
                        ON project_turns(project_slug, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_project_turns_summary
                        ON project_turns(project_slug, summary);
                    CREATE TABLE IF NOT EXISTS project_resources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        resource_path TEXT NOT NULL,
                        resource_root TEXT NOT NULL,
                        name TEXT NOT NULL,
                        extension TEXT NOT NULL,
                        resource_type TEXT NOT NULL DEFAULT 'other',
                        size_bytes INTEGER,
                        mtime TEXT,
                        matched_alias TEXT NOT NULL,
                        match_score INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        exists_now INTEGER NOT NULL DEFAULT 1,
                        UNIQUE(project_slug, resource_path),
                        FOREIGN KEY(project_slug) REFERENCES projects(slug)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_resources_project_score
                        ON project_resources(project_slug, match_score DESC, mtime DESC);
                    CREATE INDEX IF NOT EXISTS idx_project_resources_path
                        ON project_resources(resource_path);
                    CREATE TABLE IF NOT EXISTS project_facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        category TEXT NOT NULL,
                        fact_key TEXT NOT NULL,
                        fact_value TEXT NOT NULL,
                        confidence TEXT NOT NULL,
                        source TEXT NOT NULL,
                        source_path TEXT NOT NULL DEFAULT '',
                        notes TEXT NOT NULL DEFAULT '',
                        verified INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug),
                        UNIQUE(project_slug, category, fact_key)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_facts_project_category
                        ON project_facts(project_slug, category, fact_key);
                    CREATE TABLE IF NOT EXISTS project_progress (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        status TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        completed TEXT NOT NULL DEFAULT '',
                        blockers TEXT NOT NULL DEFAULT '',
                        next_steps TEXT NOT NULL DEFAULT '',
                        verification TEXT NOT NULL DEFAULT '',
                        source_turn_path TEXT NOT NULL DEFAULT '',
                        session_id TEXT NOT NULL DEFAULT '',
                        turn_id TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_progress_project_created
                        ON project_progress(project_slug, created_at DESC, id DESC);
                    CREATE TABLE IF NOT EXISTS project_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        action TEXT NOT NULL,
                        command_json TEXT NOT NULL,
                        cwd TEXT NOT NULL DEFAULT '',
                        device_id TEXT NOT NULL DEFAULT '',
                        framework TEXT NOT NULL DEFAULT '',
                        config_path TEXT NOT NULL DEFAULT '',
                        timeout_ms INTEGER,
                        risk TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        confidence TEXT NOT NULL DEFAULT '',
                        verified INTEGER NOT NULL DEFAULT 0,
                        notes TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug),
                        UNIQUE(project_slug, action, device_id, cwd)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_actions_project_action
                        ON project_actions(project_slug, action, device_id);
                    CREATE TABLE IF NOT EXISTS project_interfaces (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        name TEXT NOT NULL,
                        interface_type TEXT NOT NULL DEFAULT '',
                        uart_no TEXT NOT NULL DEFAULT '',
                        baud_rate TEXT NOT NULL DEFAULT '',
                        tx_pin TEXT NOT NULL DEFAULT '',
                        rx_pin TEXT NOT NULL DEFAULT '',
                        protocol TEXT NOT NULL DEFAULT '',
                        settings_json TEXT NOT NULL DEFAULT '{}',
                        source TEXT NOT NULL DEFAULT '',
                        confidence TEXT NOT NULL DEFAULT 'observed',
                        notes TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug),
                        UNIQUE(project_slug, name)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_interfaces_project
                        ON project_interfaces(project_slug, interface_type, name);
                    CREATE TABLE IF NOT EXISTS project_pin_map (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_slug TEXT NOT NULL,
                        board TEXT NOT NULL DEFAULT '',
                        peripheral TEXT NOT NULL,
                        signal TEXT NOT NULL,
                        gpio TEXT NOT NULL DEFAULT '',
                        net_name TEXT NOT NULL DEFAULT '',
                        connector TEXT NOT NULL DEFAULT '',
                        direction TEXT NOT NULL DEFAULT '',
                        level TEXT NOT NULL DEFAULT '',
                        pull TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        confidence TEXT NOT NULL DEFAULT 'observed',
                        verified INTEGER NOT NULL DEFAULT 0,
                        notes TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(project_slug) REFERENCES projects(slug),
                        UNIQUE(project_slug, board, peripheral, signal, gpio)
                    );
                    CREATE INDEX IF NOT EXISTS idx_project_pin_map_project
                        ON project_pin_map(project_slug, peripheral, signal, gpio);
                    """
                )
                columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(project_resources)").fetchall()
                }
                if "resource_type" not in columns:
                    conn.execute(
                        "ALTER TABLE project_resources ADD COLUMN resource_type TEXT NOT NULL DEFAULT 'other'"
                    )

    def _upsert_project(self, meta: dict[str, Any]) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO projects(slug, project_root, created_at, last_seen)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        project_root = excluded.project_root,
                        last_seen = excluded.last_seen
                    """,
                    (meta["slug"], meta["project_root"], meta["created_at"], meta["last_seen"]),
                )
                for alias in meta.get("aliases") or []:
                    conn.execute(
                        """
                        INSERT INTO project_aliases(alias, project_slug)
                        VALUES(?, ?)
                        ON CONFLICT(alias) DO UPDATE SET project_slug = excluded.project_slug
                        """,
                        (alias, meta["slug"]),
                    )

    def _insert_turn(
        self,
        project_slug: str,
        path: str,
        title: str,
        summary: str,
        content: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_turns(project_slug, path, title, summary, content, session_id, turn_id, created_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        title = excluded.title,
                        summary = excluded.summary,
                        content = excluded.content,
                        session_id = excluded.session_id,
                        turn_id = excluded.turn_id,
                        created_at = excluded.created_at
                    """,
                    (
                        project_slug,
                        path,
                        title,
                        summary,
                        content,
                        str(payload.get("session_id") or ""),
                        str(payload.get("turn_id") or ""),
                        created_at,
                    ),
                )

    def _ensure_project_identity_facts(self, meta: dict[str, Any]) -> None:
        project_slug_value = str(meta["slug"])
        project_root = Path(str(meta["project_root"]))
        project_code = project_root.name or project_slug_value
        self._upsert_project_fact(
            project_slug_value,
            "project",
            "code",
            project_code,
            "project_root",
            "observed",
            "Derived from project root directory name.",
            str(project_root),
            False,
        )
        self._upsert_project_fact(
            project_slug_value,
            "project",
            "root",
            str(project_root),
            "project_root",
            "observed",
            "",
            str(project_root),
            False,
        )
        self._upsert_project_fact(
            project_slug_value,
            "project",
            "memory_slug",
            project_slug_value,
            "project_memory",
            "observed",
            "",
            "",
            False,
        )

    def _upsert_project_fact(
        self,
        project_slug: str,
        category: str,
        key: str,
        value: str,
        source: str,
        confidence: str,
        notes: str,
        source_path: str,
        verified: bool,
    ) -> dict[str, Any]:
        category = clean_field(category, "category")
        key = clean_field(key, "key")
        value = clean_field(value, "value", maximum=2000)
        source = clean_optional_field(source, maximum=200)
        confidence = clean_optional_field(confidence or "observed", maximum=32)
        notes = clean_optional_field(notes, maximum=2000)
        source_path = clean_optional_field(source_path, maximum=1000)
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_facts(
                        project_slug, category, fact_key, fact_value, confidence,
                        source, source_path, notes, verified, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_slug, category, fact_key) DO UPDATE SET
                        fact_value = excluded.fact_value,
                        confidence = excluded.confidence,
                        source = excluded.source,
                        source_path = excluded.source_path,
                        notes = excluded.notes,
                        verified = excluded.verified,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project_slug,
                        category,
                        key,
                        value,
                        confidence,
                        source,
                        source_path,
                        notes,
                        1 if verified else 0,
                        now,
                        now,
                    ),
                )
        return self._project_facts_from_db(project_slug, category=category, query=key, limit=1)[0]

    def _project_facts_from_db(
        self,
        project_slug: str,
        category: str = "",
        query: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = positive_int(limit, "limit", maximum=1000)
        params: list[Any] = [project_slug]
        where = "project_slug = ?"
        category = category.strip()
        query = query.strip()
        if category:
            where += " AND category = ?"
            params.append(category)
        if query:
            like = f"%{query}%"
            where += " AND (fact_key LIKE ? OR fact_value LIKE ? OR source LIKE ? OR notes LIKE ?)"
            params.extend([like, like, like, like])
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT category, fact_key, fact_value, confidence, source, source_path,
                       notes, verified, created_at, updated_at
                FROM project_facts
                WHERE {where}
                ORDER BY category, fact_key
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def _insert_project_progress(
        self,
        project_slug: str,
        status: str,
        summary: str,
        completed: str,
        blockers: str,
        next_steps: str,
        verification: str,
        source_turn_path: str,
        payload: dict[str, Any],
        created_at: str | None = None,
    ) -> dict[str, Any]:
        status = clean_optional_field(status or "updated", maximum=80)
        summary = clean_field(summary or "Project progress updated", "summary", maximum=1000)
        completed = clean_optional_field(completed, maximum=3000)
        blockers = clean_optional_field(blockers, maximum=2000)
        next_steps = clean_optional_field(next_steps, maximum=2000)
        verification = clean_optional_field(verification, maximum=2000)
        source_turn_path = clean_optional_field(source_turn_path, maximum=1000)
        created_at = created_at or dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO project_progress(
                        project_slug, status, summary, completed, blockers, next_steps,
                        verification, source_turn_path, session_id, turn_id, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_slug,
                        status,
                        summary,
                        completed,
                        blockers,
                        next_steps,
                        verification,
                        source_turn_path,
                        str(payload.get("session_id") or ""),
                        str(payload.get("turn_id") or ""),
                        created_at,
                    ),
                )
                row_id = cursor.lastrowid
                row = conn.execute(
                    """
                    SELECT status, summary, completed, blockers, next_steps, verification,
                           source_turn_path, session_id, turn_id, created_at
                    FROM project_progress
                    WHERE id = ?
                    """,
                    (row_id,),
                ).fetchone()
        return dict(row)

    def _project_progress_from_db(self, project_slug: str, limit: int = 20) -> list[dict[str, Any]]:
        limit = positive_int(limit, "limit", maximum=1000)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT status, summary, completed, blockers, next_steps, verification,
                       source_turn_path, session_id, turn_id, created_at
                FROM project_progress
                WHERE project_slug = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (project_slug, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _upsert_project_action_config(
        self,
        project_slug: str,
        action: str,
        command: list[str],
        action_cwd: str,
        device_id: str,
        framework: str,
        config_path: str,
        timeout_ms: int | None,
        risk: str,
        source: str,
        confidence: str,
        verified: bool,
        notes: str,
    ) -> dict[str, Any]:
        action = clean_project_action(action)
        command = clean_command_list(command)
        action_cwd = clean_optional_field(action_cwd, maximum=1000)
        device_id = clean_optional_field(device_id, maximum=200)
        framework = clean_optional_field(framework, maximum=120)
        config_path = clean_optional_field(config_path, maximum=1000)
        timeout_value = optional_positive_int(timeout_ms, "timeout_ms", maximum=86_400_000)
        risk = clean_optional_field(risk, maximum=120)
        source = clean_optional_field(source, maximum=200)
        confidence = clean_optional_field(confidence or "observed", maximum=32)
        notes = clean_optional_field(notes, maximum=2000)
        command_json = json.dumps(command, ensure_ascii=False)
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_actions(
                        project_slug, action, command_json, cwd, device_id, framework,
                        config_path, timeout_ms, risk, source, confidence, verified,
                        notes, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_slug, action, device_id, cwd) DO UPDATE SET
                        command_json = excluded.command_json,
                        framework = excluded.framework,
                        config_path = excluded.config_path,
                        timeout_ms = excluded.timeout_ms,
                        risk = excluded.risk,
                        source = excluded.source,
                        confidence = excluded.confidence,
                        verified = excluded.verified,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project_slug,
                        action,
                        command_json,
                        action_cwd,
                        device_id,
                        framework,
                        config_path,
                        timeout_value,
                        risk,
                        source,
                        confidence,
                        1 if verified else 0,
                        notes,
                        now,
                        now,
                    ),
                )
        return self._project_actions_from_db(project_slug, action=action, query=device_id or action_cwd, limit=1)[0]

    def _project_actions_from_db(
        self,
        project_slug: str,
        action: str = "",
        query: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = positive_int(limit, "limit", maximum=1000)
        params: list[Any] = [project_slug]
        where = "project_slug = ?"
        action = action.strip()
        query = query.strip()
        if action:
            action = clean_project_action(action)
            where += " AND action = ?"
            params.append(action)
        if query:
            like = f"%{query}%"
            where += (
                " AND (action LIKE ? OR command_json LIKE ? OR cwd LIKE ? OR device_id LIKE ? "
                "OR framework LIKE ? OR config_path LIKE ? OR notes LIKE ?)"
            )
            params.extend([like, like, like, like, like, like, like])
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT action, command_json, cwd, device_id, framework, config_path,
                       timeout_ms, risk, source, confidence, verified, notes,
                       created_at, updated_at
                FROM project_actions
                WHERE {where}
                ORDER BY CASE action
                    WHEN 'build' THEN 1
                    WHEN 'flash' THEN 2
                    WHEN 'monitor' THEN 3
                    WHEN 'clean' THEN 4
                    WHEN 'test' THEN 5
                    WHEN 'reset' THEN 6
                    ELSE 99
                END, device_id, cwd
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                command = json.loads(item.pop("command_json") or "[]")
            except json.JSONDecodeError:
                command = []
            item["command"] = command if isinstance(command, list) else []
            items.append(item)
        return items

    def _upsert_project_interface(
        self,
        project_slug: str,
        name: str,
        interface_type: str,
        uart_no: str,
        baud_rate: str,
        tx_pin: str,
        rx_pin: str,
        protocol: str,
        settings: dict[str, Any],
        source: str,
        confidence: str,
        notes: str,
    ) -> dict[str, Any]:
        name = clean_field(name, "name")
        interface_type = clean_optional_field(interface_type, maximum=80)
        uart_no = clean_optional_field(uart_no, maximum=80)
        baud_rate = clean_optional_field(baud_rate, maximum=80)
        tx_pin = clean_optional_field(tx_pin, maximum=80)
        rx_pin = clean_optional_field(rx_pin, maximum=80)
        protocol = clean_optional_field(protocol, maximum=120)
        source = clean_optional_field(source, maximum=200)
        confidence = clean_optional_field(confidence or "observed", maximum=32)
        notes = clean_optional_field(notes, maximum=2000)
        settings_json = json.dumps(settings or {}, ensure_ascii=False, sort_keys=True)
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_interfaces(
                        project_slug, name, interface_type, uart_no, baud_rate, tx_pin,
                        rx_pin, protocol, settings_json, source, confidence, notes,
                        created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_slug, name) DO UPDATE SET
                        interface_type = excluded.interface_type,
                        uart_no = excluded.uart_no,
                        baud_rate = excluded.baud_rate,
                        tx_pin = excluded.tx_pin,
                        rx_pin = excluded.rx_pin,
                        protocol = excluded.protocol,
                        settings_json = excluded.settings_json,
                        source = excluded.source,
                        confidence = excluded.confidence,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project_slug,
                        name,
                        interface_type,
                        uart_no,
                        baud_rate,
                        tx_pin,
                        rx_pin,
                        protocol,
                        settings_json,
                        source,
                        confidence,
                        notes,
                        now,
                        now,
                    ),
                )
        return self._project_interfaces_from_db(project_slug, query=name, limit=1)[0]

    def _project_interfaces_from_db(
        self,
        project_slug: str,
        query: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = positive_int(limit, "limit", maximum=1000)
        params: list[Any] = [project_slug]
        where = "project_slug = ?"
        query = query.strip()
        if query:
            like = f"%{query}%"
            where += " AND (name LIKE ? OR interface_type LIKE ? OR uart_no LIKE ? OR baud_rate LIKE ? OR protocol LIKE ? OR notes LIKE ?)"
            params.extend([like, like, like, like, like, like])
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT name, interface_type, uart_no, baud_rate, tx_pin, rx_pin,
                       protocol, settings_json, source, confidence, notes,
                       created_at, updated_at
                FROM project_interfaces
                WHERE {where}
                ORDER BY interface_type, name
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["settings"] = json.loads(item.pop("settings_json") or "{}")
            except json.JSONDecodeError:
                item["settings"] = {}
            items.append(item)
        return items

    def _upsert_project_pin(
        self,
        project_slug: str,
        peripheral: str,
        signal: str,
        gpio: str,
        board: str,
        net_name: str,
        connector: str,
        direction: str,
        level: str,
        pull: str,
        source: str,
        confidence: str,
        verified: bool,
        notes: str,
    ) -> dict[str, Any]:
        peripheral = clean_field(peripheral, "peripheral")
        signal = clean_field(signal, "signal")
        gpio = clean_optional_field(gpio, maximum=80)
        board = clean_optional_field(board, maximum=120)
        net_name = clean_optional_field(net_name, maximum=160)
        connector = clean_optional_field(connector, maximum=160)
        direction = clean_optional_field(direction, maximum=80)
        level = clean_optional_field(level, maximum=80)
        pull = clean_optional_field(pull, maximum=80)
        source = clean_optional_field(source, maximum=200)
        confidence = clean_optional_field(confidence or "observed", maximum=32)
        notes = clean_optional_field(notes, maximum=2000)
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO project_pin_map(
                        project_slug, board, peripheral, signal, gpio, net_name,
                        connector, direction, level, pull, source, confidence,
                        verified, notes, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_slug, board, peripheral, signal, gpio) DO UPDATE SET
                        net_name = excluded.net_name,
                        connector = excluded.connector,
                        direction = excluded.direction,
                        level = excluded.level,
                        pull = excluded.pull,
                        source = excluded.source,
                        confidence = excluded.confidence,
                        verified = excluded.verified,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        project_slug,
                        board,
                        peripheral,
                        signal,
                        gpio,
                        net_name,
                        connector,
                        direction,
                        level,
                        pull,
                        source,
                        confidence,
                        1 if verified else 0,
                        notes,
                        now,
                        now,
                    ),
                )
        return self._project_pin_map_from_db(project_slug, query=f"{peripheral} {signal}", limit=1)[0]

    def _project_pin_map_from_db(
        self,
        project_slug: str,
        query: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        limit = positive_int(limit, "limit", maximum=1000)
        params: list[Any] = [project_slug]
        where = "project_slug = ?"
        query = query.strip()
        if query:
            tokens = [token for token in re.findall(r"[\w\-.\\:/]+", query) if token]
            for token in tokens:
                like = f"%{token}%"
                where += (
                    " AND (board LIKE ? OR peripheral LIKE ? OR signal LIKE ? OR gpio LIKE ? "
                    "OR net_name LIKE ? OR connector LIKE ? OR notes LIKE ?)"
                )
                params.extend([like, like, like, like, like, like, like])
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT board, peripheral, signal, gpio, net_name, connector,
                       direction, level, pull, source, confidence, verified,
                       notes, created_at, updated_at
                FROM project_pin_map
                WHERE {where}
                ORDER BY peripheral, signal, gpio
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def _search_turns_from_db(self, project_slug: str, query: str, max_results: int) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise MemoryStoreError("query must not be empty")
        max_results = positive_int(max_results, "max_results", maximum=100)
        like = f"%{query}%"
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT path, title, summary, content, created_at
                FROM project_turns
                WHERE project_slug = ?
                  AND (title LIKE ? OR summary LIKE ? OR content LIKE ?)
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (project_slug, like, like, like, max_results),
            ).fetchall()
        return [
            {
                "path": row["path"],
                "line": 1,
                "snippet": (row["summary"] or row["title"] or row["content"])[:500],
                "created_at": row["created_at"],
                "source": "sqlite",
            }
            for row in rows
        ]

    def _scan_project_resources(
        self,
        project: dict[str, Any],
        roots: list[Path],
        max_files: int,
    ) -> dict[str, Any]:
        aliases = project_resource_aliases(Path(str(project["project_root"])), project["meta"])
        if not aliases:
            return {
                "slug": project["slug"],
                "project_root": project["project_root"],
                "configured_roots": [str(root) for root in roots],
                "scanned": True,
                "scanned_files": 0,
                "indexed": 0,
                "aliases": [],
                "truncated": False,
            }

        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        found: list[dict[str, Any]] = []
        scanned_files = 0
        truncated = False
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in IGNORED_RESOURCE_DIRS]
                for filename in filenames:
                    scanned_files += 1
                    if scanned_files > max_files:
                        truncated = True
                        break
                    path = Path(dirpath) / filename
                    if not should_index_project_resource(path):
                        continue
                    matched_alias, score = match_resource_path(path, root, aliases)
                    if score <= 0:
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    resource_type = classify_project_resource(path)
                    found.append(
                        {
                            "project_slug": project["slug"],
                            "resource_path": str(path.resolve()),
                            "resource_root": str(root),
                            "name": path.name,
                            "extension": path.suffix.casefold(),
                            "resource_type": resource_type,
                            "size_bytes": stat.st_size,
                            "mtime": dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                            "matched_alias": matched_alias,
                            "match_score": score + RESOURCE_TYPE_SCORE.get(resource_type, 0),
                            "source": "shared-resource-folder",
                            "seen_at": now,
                        }
                    )
                if truncated:
                    break
            if truncated:
                break

        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE project_resources
                    SET exists_now = 0
                    WHERE project_slug = ? AND source = 'shared-resource-folder'
                    """,
                    (project["slug"],),
                )
                for item in found:
                    conn.execute(
                        """
                        INSERT INTO project_resources(
                            project_slug, resource_path, resource_root, name, extension,
                            resource_type, size_bytes, mtime, matched_alias, match_score, source,
                            first_seen, last_seen, exists_now
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(project_slug, resource_path) DO UPDATE SET
                            resource_root = excluded.resource_root,
                            name = excluded.name,
                            extension = excluded.extension,
                            resource_type = excluded.resource_type,
                            size_bytes = excluded.size_bytes,
                            mtime = excluded.mtime,
                            matched_alias = excluded.matched_alias,
                            match_score = excluded.match_score,
                            source = excluded.source,
                            last_seen = excluded.last_seen,
                            exists_now = 1
                        """,
                        (
                            item["project_slug"],
                            item["resource_path"],
                            item["resource_root"],
                            item["name"],
                            item["extension"],
                            item["resource_type"],
                            item["size_bytes"],
                            item["mtime"],
                            item["matched_alias"],
                            item["match_score"],
                            item["source"],
                            item["seen_at"],
                            item["seen_at"],
                        ),
                    )

        return {
            "slug": project["slug"],
            "project_root": project["project_root"],
            "configured_roots": [str(root) for root in roots],
            "scanned": True,
            "scanned_files": scanned_files,
            "indexed": len(found),
            "aliases": [alias["text"] for alias in aliases],
            "truncated": truncated,
        }

    def _index_mentioned_project_resources(self, project: dict[str, Any], text: str) -> int:
        roots = configured_project_resource_roots(self.root)
        if not roots:
            return 0
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        items: list[dict[str, Any]] = []
        for path in resource_paths_from_text(text):
            root = resource_root_for_path(path, roots)
            if root is None or not path.is_file() or not should_index_project_resource(path):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            resource_type = classify_project_resource(path)
            items.append(
                {
                    "project_slug": project["slug"],
                    "resource_path": str(path.resolve()),
                    "resource_root": str(root),
                    "name": path.name,
                    "extension": path.suffix.casefold(),
                    "resource_type": resource_type,
                    "size_bytes": stat.st_size,
                    "mtime": dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    "matched_alias": "mentioned_in_turn",
                    "match_score": 200 + RESOURCE_TYPE_SCORE.get(resource_type, 0),
                    "source": "turn-summary-mentioned",
                    "seen_at": now,
                }
            )
        if not items:
            return 0
        with closing(self._connect()) as conn:
            with conn:
                for item in items:
                    conn.execute(
                        """
                        INSERT INTO project_resources(
                            project_slug, resource_path, resource_root, name, extension,
                            resource_type, size_bytes, mtime, matched_alias, match_score, source,
                            first_seen, last_seen, exists_now
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(project_slug, resource_path) DO UPDATE SET
                            resource_root = excluded.resource_root,
                            name = excluded.name,
                            extension = excluded.extension,
                            resource_type = excluded.resource_type,
                            size_bytes = excluded.size_bytes,
                            mtime = excluded.mtime,
                            matched_alias = excluded.matched_alias,
                            match_score = excluded.match_score,
                            source = excluded.source,
                            last_seen = excluded.last_seen,
                            exists_now = 1
                        """,
                        (
                            item["project_slug"],
                            item["resource_path"],
                            item["resource_root"],
                            item["name"],
                            item["extension"],
                            item["resource_type"],
                            item["size_bytes"],
                            item["mtime"],
                            item["matched_alias"],
                            item["match_score"],
                            item["source"],
                            item["seen_at"],
                            item["seen_at"],
                        ),
                    )
        return len(items)

    def _project_resources_from_db(self, project_slug: str, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        limit = positive_int(limit, "limit", maximum=1000)
        query = query.strip()
        params: list[Any] = [project_slug]
        where = "project_slug = ? AND exists_now = 1"
        if query:
            like = f"%{query}%"
            where += " AND (resource_path LIKE ? OR name LIKE ? OR matched_alias LIKE ? OR extension LIKE ? OR resource_type LIKE ?)"
            params.extend([like, like, like, like, like])
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT resource_path, resource_root, name, extension, resource_type, size_bytes, mtime,
                       matched_alias, match_score, source, first_seen, last_seen
                FROM project_resources
                WHERE {where}
                ORDER BY match_score DESC, mtime DESC, resource_path
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]


def scan_project_profile(project_root: Path) -> dict[str, Any]:
    files, truncated = collect_project_scan_files(project_root)
    build_systems = detect_build_systems(files)
    config_files = detect_config_files(files)
    entry_files = detect_entry_files(files)
    modules = detect_main_modules(files)
    driver_dirs = detect_driver_dirs(files)
    project_type = detect_project_type(files, build_systems)
    flash_methods = detect_flash_methods(files, build_systems)
    test_methods = detect_test_methods(files, build_systems)
    risks = detect_project_risks(files, build_systems, flash_methods, test_methods, truncated)
    return {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "project_type": project_type,
        "build_systems": build_systems or ["unknown"],
        "entry_files": entry_files or ["not detected"],
        "main_modules": modules or ["not detected"],
        "driver_dirs": driver_dirs or ["not detected"],
        "config_files": config_files or ["not detected"],
        "flash_methods": flash_methods or ["not detected"],
        "test_methods": test_methods or ["not detected"],
        "risks": risks or ["No obvious risks detected by the first-pass scanner."],
        "scanned_files": len(files),
        "truncated": truncated,
    }


def collect_project_scan_files(project_root: Path) -> tuple[list[dict[str, Any]], bool]:
    files: list[dict[str, Any]] = []
    truncated = False
    if not project_root.is_dir():
        return files, False

    for dirpath, dirnames, filenames in os.walk(project_root):
        current_dir = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not should_ignore_profile_scan_dir(name, current_dir / name)
        ]
        for filename in filenames:
            if len(files) >= MAX_PROJECT_PROFILE_SCAN_FILES:
                truncated = True
                break
            path = current_dir / filename
            try:
                rel = path.resolve().relative_to(project_root.resolve()).as_posix()
            except (OSError, ValueError):
                continue
            suffix = path.suffix.casefold()
            files.append(
                {
                    "path": rel,
                    "lower": rel.casefold(),
                    "name": path.name,
                    "name_lower": path.name.casefold(),
                    "suffix": suffix,
                    "is_source": suffix in SOURCE_EXTENSIONS,
                    "path_obj": path,
                }
            )
        if truncated:
            break
    return files, truncated


def should_ignore_profile_scan_dir(name: str, path: Path) -> bool:
    lower = name.casefold()
    if lower in IGNORED_RESOURCE_DIRS:
        return True
    if lower in {".pytest_cache", ".mypy_cache", ".cache", "out", "cmake-build-debug", "cmake-build-release"}:
        return True
    if lower.startswith(".") and lower not in {".github"}:
        return True
    return False


def detect_project_type(files: list[dict[str, Any]], build_systems: list[str]) -> str:
    if "ESP-IDF/CMake" in build_systems:
        return "embedded firmware / ESP-IDF"
    if "Keil MDK" in build_systems:
        return "embedded firmware / Keil MDK"
    if "IAR EWARM" in build_systems:
        return "embedded firmware / IAR EWARM"
    if any(file["suffix"] == ".ioc" for file in files):
        return "embedded firmware / STM32Cube"
    if any(file["suffix"] in {".c", ".cpp", ".h", ".s", ".asm"} for file in files):
        if any(segment_in_path(file["lower"], {"bsp", "hal", "driver", "drivers", "cmsis", "sdk"}) for file in files):
            return "embedded firmware / C/C++"
        return "C/C++ project"
    if any(file["name_lower"] == "pyproject.toml" for file in files):
        return "Python project"
    if any(file["name_lower"] == "package.json" for file in files):
        return "Node.js project"
    return "unknown"


def detect_build_systems(files: list[dict[str, Any]]) -> list[str]:
    systems: list[str] = []
    names = {file["name"] for file in files}
    lower_names = {file["name_lower"] for file in files}
    suffixes = {file["suffix"] for file in files}
    lower_paths = {file["lower"] for file in files}

    if {"sdkconfig", "idf_component.yml", "idf_component.yaml"} & lower_names or any(
        path.endswith("/idf_component.yml") or path.endswith("/idf_component.yaml") for path in lower_paths
    ):
        systems.append("ESP-IDF/CMake")
    if ".uvprojx" in suffixes or ".uvproj" in suffixes:
        systems.append("Keil MDK")
    if ".ewp" in suffixes or ".eww" in suffixes:
        systems.append("IAR EWARM")
    if "CMakeLists.txt" in names:
        systems.append("CMake")
    if "Makefile" in names or "makefile" in names:
        systems.append("Make")
    if "platformio.ini" in lower_names:
        systems.append("PlatformIO")
    if "pyproject.toml" in lower_names:
        systems.append("Python/pyproject")
    if "package.json" in lower_names:
        systems.append("Node/package.json")
    return unique_keep_order(systems)


def detect_entry_files(files: list[dict[str, Any]]) -> list[str]:
    priority_names = {
        "main.c",
        "main.cpp",
        "main.cc",
        "app_main.c",
        "app_main.cpp",
        "core_main.c",
        "__main__.py",
    }
    candidates: list[str] = []
    for file in files:
        if file["name_lower"] in priority_names:
            candidates.append(file["path"])

    marker_candidates = [
        file
        for file in files
        if file["suffix"] in ENTRY_SOURCE_EXTENSIONS
        and (file["name_lower"].startswith("main") or "main" in file["lower"] or file["suffix"] == ".py")
    ][:200]
    for file in marker_candidates:
        text = read_small_text(file["path_obj"])
        if any(marker in text for marker in ENTRY_MARKERS):
            candidates.append(file["path"])
    return unique_keep_order(candidates)[:MAX_PROJECT_PROFILE_ITEMS]


def detect_main_modules(files: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for file in files:
        if not file["is_source"]:
            continue
        module = module_name_for_path(file["path"])
        if not module:
            continue
        counts[module] = counts.get(module, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:MAX_PROJECT_PROFILE_ITEMS]]


def module_name_for_path(rel_path: str) -> str:
    parts = rel_path.split("/")
    if not parts:
        return ""
    if len(parts) >= 2 and parts[0] in {"components", "modules", "drivers", "middleware"}:
        return f"{parts[0]}/{parts[1]}"
    if parts[0] in {"main", "src", "source", "app", "core", "components", "drivers", "bsp", "hal", "include", "inc"}:
        return parts[0]
    if len(parts) > 1:
        return parts[0]
    return "."


def detect_driver_dirs(files: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    markers = {"driver", "drivers", "drv", "dev", "bsp", "hal", "peripheral", "peripherals"}
    for file in files:
        if not file["is_source"]:
            continue
        parts = file["path"].split("/")[:-1]
        lowered = [part.casefold() for part in parts]
        if not any(part in markers or part.endswith("_driver") or part.endswith("drivers") for part in lowered):
            continue
        if len(parts) >= 2 and lowered[0] in {"components", "drivers", "bsp", "hal"}:
            key = "/".join(parts[:2])
        elif parts:
            key = "/".join(parts[: min(3, len(parts))])
        else:
            continue
        counts[key] = counts.get(key, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:MAX_PROJECT_PROFILE_ITEMS]]


def detect_config_files(files: list[dict[str, Any]]) -> list[str]:
    config_paths: list[str] = []
    for file in files:
        name = file["name"]
        name_lower = file["name_lower"]
        if name in CONFIG_FILE_NAMES or name_lower in {item.casefold() for item in CONFIG_FILE_NAMES}:
            config_paths.append(file["path"])
            continue
        if file["suffix"] in CONFIG_EXTENSIONS:
            if file["suffix"] != ".csv" or "partition" in name_lower or "partitions" in file["lower"]:
                config_paths.append(file["path"])
    return unique_keep_order(config_paths)[:MAX_PROJECT_PROFILE_ITEMS]


def detect_flash_methods(files: list[dict[str, Any]], build_systems: list[str]) -> list[str]:
    methods: list[str] = []
    if "ESP-IDF/CMake" in build_systems:
        methods.append("ESP-IDF: idf.py -p <PORT> flash (confirm serial port and power first)")
    if "Keil MDK" in build_systems:
        project = first_file_with_suffix(files, {".uvprojx", ".uvproj"})
        if project:
            methods.append(f"Keil MDK: UV4.exe -f {project} -t <TARGET> -o <flash.log> (confirm probe/target first)")
        else:
            methods.append("Keil MDK: UV4.exe -f <project.uvprojx> -t <TARGET> (confirm probe/target first)")
    if "IAR EWARM" in build_systems:
        methods.append("IAR EWARM: project-specific flash/debug command required")
    if "PlatformIO" in build_systems:
        methods.append("PlatformIO: pio run -t upload")
    if "Make" in build_systems and makefile_has_target(files, "flash"):
        methods.append("Make: make flash")
    return unique_keep_order(methods)


def detect_test_methods(files: list[dict[str, Any]], build_systems: list[str]) -> list[str]:
    methods: list[str] = []
    lower_paths = [file["lower"] for file in files]
    if any(path.startswith("tests/") or path.startswith("test/") for path in lower_paths):
        if any(path.startswith(("tests/", "test/")) and path.endswith(".py") for path in lower_paths):
            methods.append("Python tests: python -m pytest (confirm project environment)")
        else:
            methods.append("Tests directory detected; inspect project-specific test runner")
    if "Make" in build_systems and makefile_has_target(files, "test"):
        methods.append("Make: make test")
    if "CMake" in build_systems and cmake_has_testing(files):
        methods.append("CMake/CTest: ctest --test-dir <build-dir>")
    return unique_keep_order(methods)


def detect_project_risks(
    files: list[dict[str, Any]],
    build_systems: list[str],
    flash_methods: list[str],
    test_methods: list[str],
    truncated: bool,
) -> list[str]:
    risks: list[str] = []
    if truncated:
        risks.append("Scan hit file limit; profile may miss modules/configs in later directories.")
    if not build_systems:
        risks.append("Build system not detected; confirm build command before editing.")
    if len(build_systems) > 1:
        risks.append(f"Multiple build systems detected ({', '.join(build_systems)}); choose the active one before running builds.")
    if not flash_methods:
        risks.append("Flash method not detected; do not assume a safe hardware command.")
    if not test_methods:
        risks.append("Test method not detected; verification may require build-only or hardware smoke testing.")
    lower_paths = [file["lower"] for file in files]
    if any(path.startswith(("sdk/", "cmsis/", "vendor/", "third_party/", "managed_components/")) for path in lower_paths):
        risks.append("Vendor/SDK code detected; avoid broad refactors without narrowing ownership.")
    if "Keil MDK" in build_systems:
        risks.append("Keil flashing/debugging can affect real hardware; confirm target, probe, and power state.")
    if "ESP-IDF/CMake" in build_systems:
        risks.append("ESP-IDF flashing/monitoring requires confirmed chip target, serial port, baud rate, and boot mode.")
    return unique_keep_order(risks)


def render_first_scan_section(scan: dict[str, Any]) -> str:
    lines = [
        "## First Scan",
        "",
        f"- generated_at: {scan['generated_at']}",
        f"- project_type: {scan['project_type']}",
        f"- build_system: {', '.join(scan['build_systems'])}",
        f"- scanned_files: {scan['scanned_files']}",
        f"- scan_truncated: {bool(scan['truncated'])}",
        "",
        "### Entry Files",
        *markdown_list(scan["entry_files"]),
        "",
        "### Main Modules",
        *markdown_list(scan["main_modules"]),
        "",
        "### Driver Directories",
        *markdown_list(scan["driver_dirs"]),
        "",
        "### Config Files",
        *markdown_list(scan["config_files"]),
        "",
        "### Flash Method",
        *markdown_list(scan["flash_methods"]),
        "",
        "### Test Method",
        *markdown_list(scan["test_methods"]),
        "",
        "### Potential Risks",
        *markdown_list(scan["risks"]),
    ]
    return "\n".join(lines)


def insert_first_scan_section(existing: str, first_scan: str) -> str:
    text = existing.rstrip()
    marker = "\n## Stable Notes"
    if marker in text:
        return text.replace(marker, f"\n\n{first_scan}\n{marker}", 1) + "\n"
    return f"{text}\n\n{first_scan}\n"


def markdown_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def segment_in_path(path: str, segments: set[str]) -> bool:
    return any(part in segments for part in path.split("/"))


def first_file_with_suffix(files: list[dict[str, Any]], suffixes: set[str]) -> str:
    for file in files:
        if file["suffix"] in suffixes:
            return file["path"]
    return ""


def makefile_has_target(files: list[dict[str, Any]], target: str) -> bool:
    for file in files:
        if file["name"] not in {"Makefile", "makefile"}:
            continue
        text = read_small_text(file["path_obj"])
        if re.search(rf"^{re.escape(target)}\s*:", text, flags=re.MULTILINE):
            return True
    return False


def cmake_has_testing(files: list[dict[str, Any]]) -> bool:
    for file in files:
        if file["name"] != "CMakeLists.txt":
            continue
        text = read_small_text(file["path_obj"]).casefold()
        if "enable_testing" in text or "add_test" in text:
            return True
    return False


def read_small_text(path: Path, limit: int = 120_000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def find_project_root(cwd: Path) -> Path:
    current = cwd.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


def project_slug(project_root: Path) -> str:
    root_text = str(project_root.resolve()).casefold()
    digest = hashlib.sha1(root_text.encode("utf-8")).hexdigest()[:10]
    name = safe_slug(project_root.name or "project")[:60]
    return f"{name}-{digest}"


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", str(value).lower()).strip("-")
    return slug or "project"


def next_available_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def read_text_if_exists(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def search_files(root: Path, memory_root: Path, query: str, max_results: int) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        raise MemoryStoreError("query must not be empty")
    max_results = positive_int(max_results, "max_results", maximum=100)
    tokens = [token.casefold() for token in re.findall(r"[\w\-.\\:/]+", query)] or [query.casefold()]
    hits: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            lower = line.casefold()
            if all(token in lower for token in tokens):
                hits.append(
                    {
                        "path": str(path.resolve().relative_to(memory_root)).replace("\\", "/"),
                        "line": line_no,
                        "snippet": re.sub(r"\s+", " ", line).strip()[:500],
                    }
                )
                if len(hits) >= max_results:
                    return hits
    return hits


def configured_project_resource_roots(memory_root: Path) -> list[Path]:
    raw_roots: list[str] = []
    raw_roots.extend(split_resource_roots(os.environ.get(PROJECT_RESOURCE_ROOTS_ENV, "")))
    config_path = memory_root / PROJECT_RESOURCE_ROOTS_JSON
    if config_path.is_file():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = []
        if isinstance(payload, list):
            raw_roots.extend(str(item) for item in payload)
        elif isinstance(payload, dict):
            roots = payload.get("roots") or []
            if isinstance(roots, list):
                raw_roots.extend(str(item) for item in roots)

    roots: list[Path] = []
    seen: set[str] = set()
    for raw in raw_roots:
        value = raw.strip().strip('"')
        if not value:
            continue
        path = Path(value).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        key = str(resolved).casefold()
        if key in seen:
            continue
        roots.append(resolved)
        seen.add(key)
    return roots


def resource_root_for_path(path: Path, roots: list[Path]) -> Path | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    for root in roots:
        try:
            resolved.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def resource_paths_from_text(text: str) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = re.search(r"[A-Za-z]:\\", line)
        if not match:
            continue
        candidate = line[match.start() :].strip().strip("`")
        candidate = candidate.rstrip(").,;:]")
        path = Path(candidate)
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def split_resource_roots(raw: str) -> list[str]:
    if not raw.strip():
        return []
    if raw.strip().startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return [part for part in re.split(r"[;\n]+", raw) if part.strip()]


def configured_max_resource_scan_files(default: int = MAX_RESOURCE_SCAN_FILES) -> int:
    value = os.environ.get(PROJECT_RESOURCE_MAX_SCAN_FILES_ENV)
    if not value:
        return default
    try:
        return positive_int(int(value), PROJECT_RESOURCE_MAX_SCAN_FILES_ENV, maximum=200000)
    except MemoryStoreError:
        return default


def configured_resource_refresh_seconds(default: int = DEFAULT_RESOURCE_REFRESH_SECONDS) -> int:
    value = os.environ.get(PROJECT_RESOURCE_REFRESH_SECONDS_ENV)
    if not value:
        return default
    try:
        return positive_int(int(value), PROJECT_RESOURCE_REFRESH_SECONDS_ENV, maximum=86400)
    except MemoryStoreError:
        return default


def resource_refresh_due(last_scan_at: str) -> bool:
    if not last_scan_at:
        return True
    try:
        last = dt.datetime.fromisoformat(last_scan_at)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    elapsed = dt.datetime.now().astimezone() - last
    return elapsed.total_seconds() >= configured_resource_refresh_seconds()


def project_resource_aliases(project_root: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[tuple[str, int]] = []

    def add(value: str, weight: int) -> None:
        text = value.strip()
        if not text:
            return
        for variant in alias_variants(text):
            compact = compact_resource_text(variant)
            if len(compact) < 3:
                continue
            if compact.isdigit() or re.fullmatch(r"\d{6,12}", compact):
                continue
            if normalize_resource_text(variant) in normalized_generic_aliases():
                continue
            candidates.append((variant, weight))

    add(project_root.name, 100)
    for token_alias in project_name_token_aliases(project_root.name):
        add(token_alias, 55)
    for part in list(project_root.parts)[-4:]:
        add(part, 30)
    for alias in meta.get("aliases") or []:
        try:
            add(Path(str(alias)).name, 60)
        except OSError:
            continue
    for remote_name in git_remote_repo_names(project_root):
        add(remote_name, 120)

    unique: dict[str, dict[str, Any]] = {}
    for text, weight in candidates:
        key = compact_resource_text(text)
        current = unique.get(key)
        if current is None or weight > int(current["weight"]):
            unique[key] = {"text": text, "weight": weight}
    return sorted(unique.values(), key=lambda item: (-int(item["weight"]), -len(str(item["text"]))))


def alias_variants(value: str) -> set[str]:
    normalized = normalize_resource_text(value)
    compact = compact_resource_text(value)
    variants = {value, normalized, compact}
    variants.add(value.replace("_", "-"))
    variants.add(value.replace("-", "_"))
    variants.add(re.sub(r"[_\-.]+", " ", value))
    return {variant.strip() for variant in variants if variant.strip()}


def project_name_token_aliases(value: str) -> list[str]:
    tokens = [
        token
        for token in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", str(value))
        if token and normalize_resource_text(token) not in normalized_generic_aliases()
    ]
    aliases: list[str] = []
    for token in tokens:
        compact = compact_resource_text(token)
        if len(compact) >= 2 and not compact.isdigit() and re.search(r"[a-z\u4e00-\u9fff]", compact) and re.search(r"\d", compact):
            aliases.append(token)
    for index in range(len(tokens) - 1):
        aliases.append(f"{tokens[index]} {tokens[index + 1]}")
    return unique_keep_order(aliases)


def git_remote_repo_names(project_root: Path) -> list[str]:
    config_path = project_root / ".git" / "config"
    if not config_path.is_file():
        return []
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    names: list[str] = []
    for match in re.finditer(r"url\s*=\s*(.+)", text):
        url = match.group(1).strip()
        tail = re.split(r"[/\\:]", url.rstrip("/"))[-1]
        if tail.endswith(".git"):
            tail = tail[:-4]
        if tail:
            names.append(tail)
    return names


def normalized_generic_aliases() -> set[str]:
    aliases = set(GENERIC_RESOURCE_ALIASES)
    aliases.update(
        {
            "\u5de5\u7a0b",
            "\u5de5\u7a0b\u8d44\u6599",
            "\u6587\u6863",
            "\u8d44\u6599",
            "\u9879\u76ee",
        }
    )
    return {normalize_resource_text(alias) for alias in aliases}


def match_resource_path(path: Path, root: Path, aliases: list[dict[str, Any]]) -> tuple[str, int]:
    try:
        relative_text = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        relative_text = str(path)
    target = normalize_resource_text(relative_text)
    target_compact = compact_resource_text(relative_text)
    filename = normalize_resource_text(path.name)
    filename_compact = compact_resource_text(path.name)
    best_alias = ""
    best_score = 0
    for alias in aliases:
        text = str(alias["text"])
        alias_norm = normalize_resource_text(text)
        alias_compact = compact_resource_text(text)
        if not alias_norm and not alias_compact:
            continue
        matched = alias_norm in target or (alias_compact and alias_compact in target_compact)
        if not matched:
            continue
        score = int(alias["weight"])
        if alias_norm in filename or (alias_compact and alias_compact in filename_compact):
            score += 25
        if score > best_score:
            best_alias = text
            best_score = score
    return best_alias, best_score


def classify_project_resource(path: Path) -> str:
    extension = path.suffix.casefold()
    full_text = normalize_resource_text(str(path))
    name_text = normalize_resource_text(path.name)
    if extension in EDA_NETLIST_EXTENSIONS or "netlist" in name_text or "\u7f51\u8868" in full_text:
        return "eda_netlist"
    schematic_tokens = {
        "schematic",
        "sch",
        "eda",
        "\u539f\u7406\u56fe",
        "\u7535\u8def\u56fe",
    }
    if extension == ".pdf" and any(token in full_text for token in schematic_tokens):
        return "schematic_pdf"
    if extension == ".pdf":
        return "pdf"
    if extension in DOCUMENT_EXTENSIONS:
        return "document"
    if extension in ARCHIVE_EXTENSIONS:
        return "archive"
    return "other"


def should_index_project_resource(path: Path) -> bool:
    extension = path.suffix.casefold()
    if extension in EDA_NETLIST_EXTENSIONS | DOCUMENT_EXTENSIONS | ARCHIVE_EXTENSIONS:
        return True
    resource_type = classify_project_resource(path)
    return resource_type in {"eda_netlist", "schematic_pdf"}


def normalize_resource_text(value: str) -> str:
    return re.sub(r"[\s_\-.]+", " ", str(value).casefold()).strip()


def compact_resource_text(value: str) -> str:
    normalized = normalize_resource_text(value)
    return re.sub("[^0-9a-z\\u4e00-\\u9fff]+", "", normalized)


def infer_progress_status(content: str) -> str:
    text = content.casefold()
    if any(token in text for token in ["not verified", "\u672a\u9a8c\u8bc1", "\u6ca1\u6709\u9a8c\u8bc1"]):
        return "unverified"
    if any(token in text for token in ["blocked", "failed", "error", "\u963b\u585e", "\u5931\u8d25", "\u672a\u901a\u8fc7"]):
        return "needs_attention"
    if any(token in text for token in ["verified", "passed", "ok", "\u901a\u8fc7", "\u9a8c\u8bc1\u5b8c\u6210"]):
        return "verified"
    return "updated"


def extract_progress_completed(content: str) -> str:
    summary = extract_section(content, "## Assistant Summary")
    return limit_plain_text(summary or content, 1200)


def extract_progress_blockers(content: str) -> str:
    lines = [
        line.strip("- ").strip()
        for line in content.splitlines()
        if re.search(r"blocked|blocker|failed|error|\u963b\u585e|\u5931\u8d25|\u98ce\u9669", line, re.IGNORECASE)
    ]
    return limit_plain_text("\n".join(lines), 1000)


def extract_progress_next_steps(content: str) -> str:
    lines = [
        line.strip("- ").strip()
        for line in content.splitlines()
        if re.search(r"next|todo|follow|remaining|\u4e0b\u4e00\u6b65|\u540e\u7eed|\u5269\u4f59", line, re.IGNORECASE)
    ]
    return limit_plain_text("\n".join(lines), 1000)


def extract_progress_verification(content: str) -> str:
    lines = [
        line.strip("- ").strip()
        for line in content.splitlines()
        if re.search(r"test|build|compile|verify|passed|failed|\u6d4b\u8bd5|\u6784\u5efa|\u7f16\u8bd1|\u9a8c\u8bc1|\u901a\u8fc7|\u5931\u8d25", line, re.IGNORECASE)
    ]
    return limit_plain_text("\n".join(lines), 1200)


def extract_section(content: str, heading: str) -> str:
    lines = content.splitlines()
    start = -1
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start < 0:
        return ""
    collected: list[str] = []
    for line in lines[start:]:
        if line.startswith("## ") and collected:
            break
        collected.append(line)
    return "\n".join(collected).strip()


def limit_plain_text(text: str, maximum: int) -> str:
    compact = "\n".join(line.rstrip() for line in str(text).strip().splitlines()).strip()
    if len(compact) <= maximum:
        return compact
    return compact[: maximum - 15].rstrip() + "\n...[truncated]"


def clean_field(value: str, name: str, maximum: int = 300) -> str:
    cleaned = clean_optional_field(value, maximum)
    if not cleaned:
        raise MemoryStoreError(f"{name} must not be empty")
    return cleaned


def clean_project_action(value: str) -> str:
    action = clean_field(value, "action", maximum=40)
    if action not in STANDARD_PROJECT_ACTION_SET:
        allowed = ", ".join(STANDARD_PROJECT_ACTIONS)
        raise MemoryStoreError(f"action must be one of: {allowed}")
    return action


def clean_command_list(value: list[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        raise MemoryStoreError("command must be a non-empty string array")
    command: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise MemoryStoreError(f"command[{index}] must be a non-empty string")
        command.append(item.strip())
    return command


def clean_optional_field(value: str, maximum: int = 300) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


def optional_positive_int(value: int | None, name: str, maximum: int) -> int | None:
    if value is None:
        return None
    return positive_int(value, name, maximum)


def positive_int(value: int, name: str, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MemoryStoreError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise MemoryStoreError(f"{name} must be at least 1")
    if parsed > maximum:
        raise MemoryStoreError(f"{name} must be at most {maximum}")
    return parsed


def trim_state_field(value: str, maximum: int = 240) -> str:
    """Collapse an extracted progress field to a single short line."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= maximum:
        return text
    return text[: maximum - 3].rstrip() + "..."
