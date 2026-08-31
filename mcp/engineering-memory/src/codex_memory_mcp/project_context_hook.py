from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

from .project_memory import ProjectMemoryStore
from .troubleshooting_index import TroubleshootingIndex
from .turn_summary_hook import read_stdin_text


DEFAULT_CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
LOG_PATH = Path(
    os.environ.get("CODEX_MEMORY_LOG_PATH")
    or (DEFAULT_CODEX_HOME / "log" / "project-context-hook.log")
)
HOOK_MODE_ENV = "CODEX_PROJECT_CONTEXT_HOOK_MODE"
MODE_SILENT = "silent"
MODE_ALERTS = "alerts"
MODE_FULL = "full"


def main() -> int:
    try:
        raw = read_stdin_text()
        payload = json.loads(raw) if raw.strip() else {}
        cwd = str(payload.get("cwd") or "")
        prompt = str(payload.get("prompt") or payload.get("user_prompt") or payload.get("message") or "")
        mode = hook_mode()
        if cwd:
            store = ProjectMemoryStore()
            # The Stop hook has no model available, so hand it the user's own wording
            # rather than making it infer intent from the assistant's reply.
            store.stash_user_intent(str(payload.get("session_id") or ""), cwd, prompt)
            if mode == MODE_FULL:
                context = store.project_engineering_context(cwd)
                project_context = str(context.get("context") or "")
            else:
                store.refresh_project_resources(cwd)
                project_context = ""
        else:
            project_context = ""

        troubleshooting_context = ""
        if mode in {MODE_ALERTS, MODE_FULL}:
            troubleshooting_context = TroubleshootingIndex().context_for_prompt(" ".join([prompt, cwd]).strip())

        if mode == MODE_SILENT:
            return 0

        combined_context = "\n\n".join(part for part in [project_context, troubleshooting_context] if part)
        if not combined_context:
            return 0
        output = {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": combined_context,
            },
            "suppressOutput": True,
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
        return 0
    except Exception:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
            handle.write("\n")
        return 0

def hook_mode() -> str:
    value = str(os.environ.get(HOOK_MODE_ENV) or MODE_SILENT).strip().casefold()
    if value in {MODE_SILENT, MODE_ALERTS, MODE_FULL}:
        return value
    return MODE_SILENT


if __name__ == "__main__":
    raise SystemExit(main())
