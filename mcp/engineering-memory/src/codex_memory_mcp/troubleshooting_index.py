from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from contextlib import closing
from typing import Any

from .project_memory import DB_FILENAME
from .store import MemoryStore, MemoryStoreError


MAX_HINTS = 3
MAX_CONTEXT_CHARS = 6000


SEED_CASES: list[dict[str, Any]] = [
    {
        "case_id": "codex-hook-systemmessage-warning",
        "title": "Codex Stop hook output is displayed as warning",
        "applies_to": "codex-hooks",
        "keywords": [
            "stop hook",
            "systemmessage",
            "warning:",
            "\u672c\u8f6e\u603b\u7ed3",
            "\u663e\u793a\u6709\u70b9\u95ee\u9898",
            "\u50cf\u62a5\u9519",
        ],
        "symptom": "Stop hook prints a summary but Codex renders it as a warning line.",
        "cause": "Codex surfaces hook systemMessage as a warning-style UI line.",
        "reminder": "Do not use systemMessage for normal turn summaries. Keep the Stop hook silent by default and write summaries to memory instead.",
        "checks": [
            "Check CODEX_TURN_SUMMARY_DISPLAY; it should normally be unset.",
            "If a visible summary is needed, accept that systemMessage renders as warning in current Codex UI.",
        ],
    },
    {
        "case_id": "windows-powershell-utf8-mojibake",
        "title": "Chinese text becomes question marks or mojibake in hook tests",
        "applies_to": "windows-powershell-python-hooks",
        "keywords": [
            "mojibake",
            "????",
            "\u4e71\u7801",
            "\u95ee\u53f7",
            "powershell",
            "utf-8",
            "gbk",
            "\u4e2d\u6587",
        ],
        "symptom": "Chinese text is corrupted when passed through PowerShell pipes or command literals.",
        "cause": "Windows console and PowerShell may recode pipeline text before Python reads stdin.",
        "reminder": "Use UTF-8 files or byte streams for hook payload tests. In Python, read stdin bytes and try utf-8-sig, utf-8, then gb18030.",
        "checks": [
            "Avoid embedding Chinese test strings directly in PowerShell command text.",
            "Generate test payloads with Python Unicode escapes when verifying hook behavior.",
            "Keep hook stdout as ASCII JSON with escaped Unicode.",
        ],
    },
    {
        "case_id": "sqlite-windows-file-locked",
        "title": "SQLite database file is locked during Windows cleanup",
        "applies_to": "sqlite-windows-tests",
        "keywords": [
            "sqlite",
            "permissionerror",
            "winerror 32",
            "file locked",
            "\u88ab\u5360\u7528",
            "\u65e0\u6cd5\u8bbf\u95ee",
        ],
        "symptom": "Temporary directory cleanup fails because engineering_memory.sqlite is still in use.",
        "cause": "Using 'with sqlite3.connect(...) as conn' commits but does not close the connection. WAL files can also keep handles around on Windows.",
        "reminder": "Wrap SQLite connections with contextlib.closing(...) and use journal_mode=DELETE for small local test databases.",
        "checks": [
            "Search for 'with self._connect() as conn' and replace it with closing(self._connect()).",
            "Close any sqlite3 connection before deleting temp directories.",
            "Use short retry only as a fallback, not as the primary fix.",
        ],
    },
    {
        "case_id": "codex-mcp-not-loaded",
        "title": "Codex MCP tool is missing or not auto-starting",
        "applies_to": "codex-mcp",
        "keywords": [
            "mcp",
            "not loaded",
            "missing tool",
            "not auto",
            "\u6ca1\u6709\u542f\u52a8",
            "\u6ca1\u6709\u5de5\u5177",
            "\u81ea\u52a8\u62c9\u8d77",
            "required",
        ],
        "symptom": "Expected MCP tools are absent in Codex CLI/App.",
        "cause": "The server may not be registered in global config, may need Codex restart, or may not be marked required.",
        "reminder": "Check 'codex mcp list', global ~/.codex/config.toml, PYTHONPATH, and whether required=true is appropriate.",
        "checks": [
            "Run 'codex mcp list' and confirm engineering_memory is enabled.",
            "Verify command, args, CODEX_MEMORY_ROOT, and PYTHONPATH in config.toml.",
            "Restart Codex after changing MCP config.",
        ],
    },
    {
        "case_id": "codex-hook-trust-required",
        "title": "Codex hook does not run until trusted",
        "applies_to": "codex-hooks",
        "keywords": [
            "hook",
            "trust",
            "/hooks",
            "not running",
            "\u4e0d\u751f\u6548",
            "\u4fe1\u4efb",
        ],
        "symptom": "Configured hooks do not appear to run in CLI/App.",
        "cause": "Codex requires non-managed hooks to be trusted before execution.",
        "reminder": "Use /hooks in the CLI to trust the hook command after adding or changing hooks.json.",
        "checks": [
            "Validate ~/.codex/hooks.json with python -m json.tool.",
            "Open CLI and run /hooks if Codex prompts for hook trust.",
            "Check hook log files under memory-mcp-server/logs.",
        ],
    },
    {
        "case_id": "keil-build-log-verification",
        "title": "Keil build status is uncertain without build.log summary",
        "applies_to": "embedded-keil",
        "keywords": [
            "keil",
            "uv4",
            "build.log",
            "x error",
            "warning",
            "\u7f16\u8bd1",
            "\u6784\u5efa",
        ],
        "symptom": "Keil build output looks successful but the canonical error/warning line was not checked.",
        "cause": "Keil command status can be misleading; the reliable evidence is the build.log line with error and warning counts.",
        "reminder": "For Keil work, verify from build.log and report the 'X Error(s), Y Warning(s)' line.",
        "checks": [
            "Check %LOCALAPPDATA%\\Keil_v5\\UV4\\UV4.exe before saying UV4 is missing.",
            "Use the repo's actual .uvprojx target and inspect build.log after build.",
        ],
    },
    {
        "case_id": "mf-serial-hmi-crc-mismatch",
        "title": "M&F serial HMI CRC setting mismatch",
        "applies_to": "embedded-serial-hmi",
        "keywords": [
            "DeviceEnableCRC",
            "CRC16_ENABLE",
            "crc",
            "serial hmi",
            "mf",
            "dacai",
            "\u4e32\u53e3\u5c4f",
            "\u6821\u9a8c",
        ],
        "symptom": "Serial HMI frames are ignored, parsed incorrectly, or notify handling fails around CRC.",
        "cause": "Screen-side DeviceEnableCRC and MCU-side CRC16_ENABLE may not match.",
        "reminder": "Before deeper debugging, compare DeviceEnableCRC in VisualTFT/project settings against MCU CRC16_ENABLE.",
        "checks": [
            "Check the screen project setting DeviceEnableCRC.",
            "Check MCU compile-time CRC16_ENABLE.",
            "Only proceed to frame parsing after CRC settings agree.",
        ],
    },
]


class TroubleshootingIndex:
    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self.memory_store = memory_store or MemoryStore()
        self.root = self.memory_store.root
        self.db_path = self.root / DB_FILENAME

    def ensure_ready(self) -> None:
        self.memory_store.ensure_ready()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.executescript(
                    """
                    PRAGMA journal_mode = DELETE;
                    CREATE TABLE IF NOT EXISTS troubleshooting_cases (
                        case_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        applies_to TEXT NOT NULL,
                        keywords_json TEXT NOT NULL,
                        symptom TEXT NOT NULL,
                        cause TEXT NOT NULL,
                        reminder TEXT NOT NULL,
                        checks_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        source TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_troubleshooting_applies_to
                        ON troubleshooting_cases(applies_to);
                    """
                )
        self.seed_defaults()

    def seed_defaults(self) -> None:
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as conn:
            with conn:
                for case in SEED_CASES:
                    conn.execute(
                        """
                        INSERT INTO troubleshooting_cases(
                            case_id, title, applies_to, keywords_json, symptom, cause,
                            reminder, checks_json, created_at, updated_at, source
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(case_id) DO UPDATE SET
                            title = excluded.title,
                            applies_to = excluded.applies_to,
                            keywords_json = excluded.keywords_json,
                            symptom = excluded.symptom,
                            cause = excluded.cause,
                            reminder = excluded.reminder,
                            checks_json = excluded.checks_json,
                            updated_at = excluded.updated_at,
                            source = excluded.source
                        """,
                        (
                            case["case_id"],
                            case["title"],
                            case["applies_to"],
                            json.dumps(case["keywords"], ensure_ascii=False),
                            case["symptom"],
                            case["cause"],
                            case["reminder"],
                            json.dumps(case["checks"], ensure_ascii=False),
                            now,
                            now,
                            "seed",
                        ),
                    )

    def search(self, query: str, max_results: int = MAX_HINTS) -> list[dict[str, Any]]:
        self.ensure_ready()
        query = query.strip()
        if not query:
            return []
        max_results = positive_int(max_results, "max_results", maximum=MAX_HINTS)
        normalized = normalize(query)
        tokens = set(re.findall(r"[\w\-.\\:/]+", normalized))
        scored: list[dict[str, Any]] = []
        for case in self._all_cases():
            keywords = case["keywords"]
            score = 0
            matched: list[str] = []
            for keyword in keywords:
                keyword_norm = normalize(keyword)
                if not keyword_norm:
                    continue
                if keyword_norm in normalized:
                    score += 3 if " " in keyword_norm or "\\" in keyword_norm or ":" in keyword_norm else 2
                    matched.append(keyword)
                elif keyword_norm in tokens:
                    score += 1
                    matched.append(keyword)
            if score >= 4:
                item = {key: value for key, value in case.items() if key != "keywords"}
                item["matched_keywords"] = matched
                item["score"] = score
                scored.append(item)
        scored.sort(key=lambda item: (-int(item["score"]), item["title"]))
        return scored[:max_results]

    def context_for_prompt(self, prompt: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
        matches = self.search(prompt, MAX_HINTS)
        if not matches:
            return ""
        lines = [
            "<codex_troubleshooting_memory>",
            "The user's prompt resembles prior fault patterns. Consider only the top matching reminders before acting:",
            "",
        ]
        for match in matches:
            lines.extend(
                [
                    f"## {match['title']}",
                    f"- applies_to: {match['applies_to']}",
                    f"- symptom: {match['symptom']}",
                    f"- likely_cause: {match['cause']}",
                    f"- reminder: {match['reminder']}",
                    f"- matched_keywords: {', '.join(match['matched_keywords'])}",
                    "",
                ]
            )
            checks = match.get("checks") or []
            if checks:
                lines.append("Checks:")
                for check in checks:
                    lines.append(f"- {check}")
                lines.append("")
        lines.append("</codex_troubleshooting_memory>")
        context = "\n".join(lines).strip()
        return context[:max_chars]

    def list_cases(self, limit: int = 200) -> list[dict[str, Any]]:
        self.ensure_ready()
        limit = positive_int(limit, "limit", maximum=1000)
        return self._all_cases()[:limit]

    def _all_cases(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT case_id, title, applies_to, keywords_json, symptom, cause,
                       reminder, checks_json, created_at, updated_at, source
                FROM troubleshooting_cases
                ORDER BY title
                """
            ).fetchall()
        cases: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["keywords"] = json.loads(item.pop("keywords_json"))
            item["checks"] = json.loads(item.pop("checks_json"))
            cases.append(item)
        return cases

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


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
