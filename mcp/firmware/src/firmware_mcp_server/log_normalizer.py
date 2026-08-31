from __future__ import annotations

import re
from typing import Any


LOG_LEVELS = ("Error", "Warning", "Info")
MAX_LOG_ENTRIES = 500


def classify_log_line(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return "Info"

    lower = text.casefold()
    without_zero_error_counts = re.sub(r"\b0\s+error\(s\)", "", lower)
    without_zero_counts = re.sub(r"\b0\s+warning\(s\)", "", without_zero_error_counts)

    if re.search(r"\b[1-9]\d*\s+error\(s\)", lower):
        return "Error"
    if re.search(r"\b(error|fatal|exception|traceback|failed|failure|panic|hardfault|assert)\b", without_zero_counts):
        return "Error"
    if re.search(r"\b[1-9]\d*\s+warning\(s\)", lower):
        return "Warning"
    if re.search(r"\b(warning|warn|deprecated)\b", without_zero_counts):
        return "Warning"
    return "Info"


def normalize_command_logs(stdout: str, stderr: str, max_entries: int = MAX_LOG_ENTRIES) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    counts = new_counts()
    total = 0

    for stream, text in (("stdout", stdout), ("stderr", stderr)):
        for raw_line in str(text or "").splitlines():
            line = raw_line.rstrip()
            level = classify_log_line(line)
            counts[level] += 1
            total += 1
            if len(entries) < max_entries:
                entries.append({"level": level, "stream": stream, "line": line})

    return {
        "levels": list(LOG_LEVELS),
        "counts": counts,
        "entries": entries,
        "total": total,
        "truncated": total > len(entries),
    }


def normalize_serial_logs(lines: list[dict[str, Any]], max_entries: int = MAX_LOG_ENTRIES) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    counts = new_counts()
    total = 0

    for item in lines:
        line = str(item.get("line") or "")
        level = classify_log_line(line)
        counts[level] += 1
        total += 1
        if len(entries) < max_entries:
            entries.append({"level": level, "stream": "serial", "line": line})

    return {
        "levels": list(LOG_LEVELS),
        "counts": counts,
        "entries": entries,
        "total": total,
        "truncated": total > len(entries),
    }


def new_counts() -> dict[str, int]:
    return {level: 0 for level in LOG_LEVELS}
