from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any

from .project_memory import ProjectMemoryStore
from .store import MemoryStore


DEFAULT_CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
LOG_PATH = Path(
    os.environ.get("CODEX_MEMORY_LOG_PATH")
    or (DEFAULT_CODEX_HOME / "log" / "turn-summary-hook.log")
)
CLIENT_LABEL_ENV = "CODEX_MEMORY_CLIENT_LABEL"
DEFAULT_CLIENT_LABEL = "Codex"
MAX_SUMMARY_CHARS = 5000
MAX_DISPLAY_CHARS = 260
MAX_TOOL_CALLS = 20
MAX_ARGUMENT_CHARS = 300
DISPLAY_ENV = "CODEX_TURN_SUMMARY_DISPLAY"
DISPLAY_SYSTEM_MESSAGE = "systemMessage"
DEFAULT_DISPLAY = "\u5df2\u5b8c\u6210\u672c\u8f6e\u5de5\u4f5c\u5e76\u5199\u5165\u957f\u671f\u8bb0\u5fc6\u3002"
SYSTEM_MESSAGE_PREFIX = "/* \u672c\u8f6e\u603b\u7ed3\uff1a"
SCOPE_PROJECT_ENGINEERING = "project_engineering"
SCOPE_GLOBAL_INFRASTRUCTURE = "global_infrastructure"
GLOBAL_INFRASTRUCTURE_PATTERNS = [
    r"\bcodex\b",
    r"\bmcp\b",
    r"memory-mcp",
    r"engineering_memory",
    r"long[- ]term memory",
    r"turn summary",
    r"stop hook",
    r"userpromptsubmit",
    r"hooks\.json",
    r"config\.toml",
    r"\.codex",
    r"codex_memory_mcp",
    r"\u957f\u671f\u8bb0\u5fc6",
    r"\u5de5\u7a0b\u8bb0\u5fc6",
    r"\u9879\u76ee\u8bb0\u5fc6",
    r"\u81ea\u52a8\u603b\u7ed3",
    r"\u6545\u969c\u6392\u67e5\u7d22\u5f15",
]
PROJECT_ENGINEERING_PATTERNS = [
    r"\bfirmware\b",
    r"\bkeil\b",
    r"\besp32\b",
    r"\blvgl\b",
    r"\buart\b",
    r"\bcrc\b",
    r"\bmodbus\b",
    r"\bschematic\b",
    r"\bnetlist\b",
    r"\bpcb\b",
    r"\beda\b",
    r"\bbuild\.log\b",
    r"\.uvprojx",
    r"\u539f\u7406\u56fe",
    r"\u7f51\u8868",
    r"\u56fa\u4ef6",
    r"\u7f16\u8bd1",
    r"\u4e32\u53e3",
    r"\u63a5\u7ebf",
]


def main() -> int:
    try:
        raw = read_stdin_text()
        payload = json.loads(raw) if raw.strip() else {}
        note = build_turn_note(payload)
        if not note:
            return 0
        store = MemoryStore()
        cwd = str(payload.get("cwd") or "")
        project_store = ProjectMemoryStore(store)
        intent = project_store.take_user_intent(str(payload.get("session_id") or ""), cwd)
        if intent:
            note["user_intent"] = intent
            note["content"] = f"## User Intent\n{intent}\n\n{note['content']}"
        store.add_note(
            title=note["title"],
            content=note["content"],
            tags=[client_tag(), "auto", "stop-hook", note.get("memory_scope", SCOPE_PROJECT_ENGINEERING)],
        )
        if cwd and note.get("memory_scope") == SCOPE_PROJECT_ENGINEERING:
            project_store.add_turn_summary(cwd, note, payload)
        output = build_hook_output(note)
        if output:
            sys.stdout.write(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
        return 0
    except Exception:
        log_error()
        return 0


def client_label() -> str:
    return os.environ.get(CLIENT_LABEL_ENV) or DEFAULT_CLIENT_LABEL


def client_tag() -> str:
    return client_label().casefold().replace(" ", "-") + "-turn-summary"


def read_stdin_text() -> str:
    raw = sys.stdin.buffer.read()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def build_turn_note(payload: dict[str, Any]) -> dict[str, str] | None:
    last_message = clean_text(str(payload.get("last_assistant_message") or ""))
    if not last_message:
        return None

    transcript_path = str(payload.get("transcript_path") or "")
    turn_id = str(payload.get("turn_id") or payload.get("prompt_id") or "")
    session_id = str(payload.get("session_id") or "")
    cwd = str(payload.get("cwd") or "")
    event_name = str(payload.get("hook_event_name") or "Stop")

    turn_events = load_turn_events(transcript_path, turn_id)
    tool_calls = extract_tool_calls(turn_events)
    files = extract_file_mentions(last_message, tool_calls)
    memory_scope = classify_turn_scope(last_message, tool_calls, files, cwd)

    title_bits = [f"{client_label()} turn summary"]
    if cwd:
        title_bits.append(Path(cwd).name or cwd)
    if turn_id:
        title_bits.append(turn_id[:8])

    lines = [
        f"- hook_event: {event_name}",
        f"- session_id: {session_id or 'unknown'}",
        f"- turn_id: {turn_id or 'unknown'}",
        f"- cwd: {cwd or 'unknown'}",
        f"- transcript_path: {transcript_path or 'unknown'}",
        f"- memory_scope: {memory_scope}",
        "",
        "## Assistant Summary",
        limit_text(last_message, MAX_SUMMARY_CHARS),
    ]

    if tool_calls:
        lines.extend(["", "## Tool Calls"])
        for call in tool_calls[:MAX_TOOL_CALLS]:
            lines.append(f"- {call}")

    if files:
        lines.extend(["", "## Files Mentioned"])
        for file_path in files[:50]:
            lines.append(f"- {file_path}")

    return {
        "title": " - ".join(title_bits),
        "content": "\n".join(lines).strip(),
        "display": build_display_summary(last_message, tool_calls, files),
        "memory_scope": memory_scope,
    }


def build_hook_output(note: dict[str, str]) -> dict[str, Any]:
    if os.environ.get(DISPLAY_ENV) != DISPLAY_SYSTEM_MESSAGE:
        return {}
    display = note.get("display") or note.get("title") or DEFAULT_DISPLAY
    return {
        "continue": True,
        "systemMessage": f"{SYSTEM_MESSAGE_PREFIX}{display} */",
        "suppressOutput": False,
    }


def build_display_summary(last_message: str, tool_calls: list[str], files: list[str]) -> str:
    summary = first_meaningful_line(last_message)
    suffixes: list[str] = []
    if tool_calls:
        suffixes.append(f"\u5de5\u5177 {len(tool_calls)} \u6b21")
    if files:
        suffixes.append(f"\u6587\u4ef6 {min(len(files), 50)} \u4e2a")
    if suffixes:
        summary = f"{summary} ({', '.join(suffixes)})"
    return limit_single_line(summary, MAX_DISPLAY_CHARS)


def load_turn_events(transcript_path: str, turn_id: str) -> list[dict[str, Any]]:
    if not transcript_path or not turn_id:
        return []
    path = Path(transcript_path)
    if not path.is_file():
        return []

    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                metadata = payload.get("metadata")
                if isinstance(metadata, dict) and metadata.get("turn_id") == turn_id:
                    events.append(payload)
    except OSError:
        return []
    return events


def extract_tool_calls(events: list[dict[str, Any]]) -> list[str]:
    calls: list[str] = []
    for payload in events:
        if payload.get("type") != "function_call":
            continue
        name = str(payload.get("name") or "tool")
        arguments = payload.get("arguments")
        summary = summarize_arguments(arguments)
        calls.append(f"{name}: {summary}" if summary else name)
    return calls


def summarize_arguments(arguments: Any) -> str:
    if not arguments:
        return ""
    if isinstance(arguments, str):
        try:
            decoded = json.loads(arguments)
        except json.JSONDecodeError:
            return limit_text(clean_text(arguments), MAX_ARGUMENT_CHARS)
    else:
        decoded = arguments

    if isinstance(decoded, dict):
        for key in ("cmd", "path", "file", "query", "q", "name"):
            value = decoded.get(key)
            if value:
                return f"{key}={limit_text(clean_text(str(value)), MAX_ARGUMENT_CHARS)}"
        return limit_text(json.dumps(decoded, ensure_ascii=False, separators=(",", ":")), MAX_ARGUMENT_CHARS)
    return limit_text(clean_text(str(decoded)), MAX_ARGUMENT_CHARS)


def extract_file_mentions(last_message: str, tool_calls: list[str]) -> list[str]:
    text = "\n".join([last_message, *tool_calls])
    patterns = [
        r"[A-Za-z]:\\[^\s`\"<>|]+",
        r"(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+",
    ]
    seen: set[str] = set()
    files: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            cleaned = match.rstrip(").,;:]")
            if cleaned not in seen:
                seen.add(cleaned)
                files.append(cleaned)
    return files


def classify_turn_scope(
    last_message: str,
    tool_calls: list[str],
    files: list[str],
    cwd: str,
) -> str:
    text = "\n".join([last_message, *tool_calls, *files, cwd]).casefold()
    global_score = score_patterns(text, GLOBAL_INFRASTRUCTURE_PATTERNS)
    project_score = score_patterns(text, PROJECT_ENGINEERING_PATTERNS)
    if r"\.codex" in text or "memory-mcp-server" in text or "codex_memory_mcp" in text:
        global_score += 4
    if "\\work\\" in text or "/work/" in text:
        project_score += 1
    if global_score >= 2 and global_score >= project_score:
        return SCOPE_GLOBAL_INFRASTRUCTURE
    return SCOPE_PROJECT_ENGINEERING


def score_patterns(text: str, patterns: list[str]) -> int:
    score = 0
    for pattern in patterns:
        if re.search(pattern, text):
            score += 1
    return score


def clean_text(text: str) -> str:
    text = re.sub(r"<oai-mem-citation>.*?</oai-mem-citation>", "", text, flags=re.DOTALL)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        stripped = re.sub(r"^[\-*#>\s]+", "", line).strip()
        if stripped:
            return stripped
    return DEFAULT_DISPLAY


def limit_single_line(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("*/", "* /")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n...[truncated]"


def log_error() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(traceback.format_exc())
        handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
