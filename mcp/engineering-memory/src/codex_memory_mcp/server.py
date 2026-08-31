from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .project_memory import ProjectMemoryStore
from .store import MemoryStore, MemoryStoreError
from .troubleshooting_index import MAX_HINTS, TroubleshootingIndex


SERVER_INSTRUCTIONS = (
    "Use this local server for long-term engineering memory. "
    "Search memory before non-trivial repo or workstation tasks when prior context may matter. "
    "Call add_engineering_memory_note only when the user explicitly asks to save or update memory. "
    "Automatic turn summaries are handled by the local Stop hook, not by MCP tool calls; "
    "global infrastructure turns stay in global memory, while project_engineering turns are also "
    "indexed under the current project. "
    "Project facts, progress, interfaces, pin maps, and baud rates should be recorded as structured "
    "project memory only when observed in code/docs/logs or explicitly confirmed by the user."
)


server = Server("codex-engineering-memory", instructions=SERVER_INSTRUCTIONS)
store = MemoryStore()
project_store = ProjectMemoryStore(store)
troubleshooting_index = TroubleshootingIndex(store)


SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    "required": ["query"],
    "additionalProperties": False,
}

READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "max_chars": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 12000},
    },
    "required": ["path"],
    "additionalProperties": False,
}

LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
    },
    "additionalProperties": False,
}

ADD_NOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}, "default": []},
    },
    "required": ["title", "content"],
    "additionalProperties": False,
}

PROJECT_CONTEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "max_chars": {"type": "integer", "minimum": 1, "maximum": 50000, "default": 8000},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "query": {"type": "string"},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    "required": ["cwd", "query"],
    "additionalProperties": False,
}

PROJECT_RESOURCE_REFRESH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "force": {"type": "boolean", "default": False},
        "max_files": {"type": "integer", "minimum": 1, "maximum": 200000, "default": 20000},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_RESOURCE_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "query": {"type": "string", "default": ""},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_FACT_UPSERT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "category": {"type": "string"},
        "key": {"type": "string"},
        "value": {"type": "string"},
        "source": {"type": "string", "default": "manual"},
        "confidence": {"type": "string", "default": "manual"},
        "notes": {"type": "string", "default": ""},
        "source_path": {"type": "string", "default": ""},
        "verified": {"type": "boolean", "default": False},
    },
    "required": ["cwd", "category", "key", "value"],
    "additionalProperties": False,
}

PROJECT_FACT_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "category": {"type": "string", "default": ""},
        "query": {"type": "string", "default": ""},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_PROGRESS_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "status": {"type": "string"},
        "summary": {"type": "string"},
        "completed": {"type": "string", "default": ""},
        "blockers": {"type": "string", "default": ""},
        "next_steps": {"type": "string", "default": ""},
        "verification": {"type": "string", "default": ""},
    },
    "required": ["cwd", "status", "summary"],
    "additionalProperties": False,
}

PROJECT_PROGRESS_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 20},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_ACTION_CONFIG_UPSERT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "action": {"type": "string", "enum": ["build", "flash", "monitor", "clean", "test", "reset"]},
        "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "action_cwd": {"type": "string", "default": ""},
        "device_id": {"type": "string", "default": ""},
        "framework": {"type": "string", "default": ""},
        "config_path": {"type": "string", "default": ""},
        "timeout_ms": {"type": "integer", "minimum": 1},
        "risk": {"type": "string", "default": ""},
        "source": {"type": "string", "default": "manual"},
        "confidence": {"type": "string", "default": "manual"},
        "verified": {"type": "boolean", "default": False},
        "notes": {"type": "string", "default": ""},
    },
    "required": ["cwd", "action", "command"],
    "additionalProperties": False,
}

PROJECT_ACTION_CONFIG_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "action": {"type": "string", "default": "", "enum": ["", "build", "flash", "monitor", "clean", "test", "reset"]},
        "query": {"type": "string", "default": ""},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_INTERFACE_UPSERT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "name": {"type": "string"},
        "interface_type": {"type": "string", "default": ""},
        "uart_no": {"type": "string", "default": ""},
        "baud_rate": {"type": "string", "default": ""},
        "tx_pin": {"type": "string", "default": ""},
        "rx_pin": {"type": "string", "default": ""},
        "protocol": {"type": "string", "default": ""},
        "settings": {"type": "object", "default": {}},
        "source": {"type": "string", "default": "manual"},
        "confidence": {"type": "string", "default": "manual"},
        "notes": {"type": "string", "default": ""},
    },
    "required": ["cwd", "name"],
    "additionalProperties": False,
}

PROJECT_INTERFACE_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "query": {"type": "string", "default": ""},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

PROJECT_PIN_UPSERT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "peripheral": {"type": "string"},
        "signal": {"type": "string"},
        "gpio": {"type": "string", "default": ""},
        "board": {"type": "string", "default": ""},
        "net_name": {"type": "string", "default": ""},
        "connector": {"type": "string", "default": ""},
        "direction": {"type": "string", "default": ""},
        "level": {"type": "string", "default": ""},
        "pull": {"type": "string", "default": ""},
        "source": {"type": "string", "default": "manual"},
        "confidence": {"type": "string", "default": "manual"},
        "verified": {"type": "boolean", "default": False},
        "notes": {"type": "string", "default": ""},
    },
    "required": ["cwd", "peripheral", "signal"],
    "additionalProperties": False,
}

PROJECT_PIN_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cwd": {"type": "string"},
        "query": {"type": "string", "default": ""},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
    },
    "required": ["cwd"],
    "additionalProperties": False,
}

TROUBLESHOOTING_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "max_results": {"type": "integer", "minimum": 1, "maximum": MAX_HINTS, "default": MAX_HINTS},
    },
    "required": ["query"],
    "additionalProperties": False,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_engineering_memory",
            description="Search long-term Codex engineering memory files and return matching line snippets.",
            inputSchema=SEARCH_SCHEMA,
        ),
        Tool(
            name="read_engineering_memory",
            description="Read a long-term engineering memory file by relative path.",
            inputSchema=READ_SCHEMA,
        ),
        Tool(
            name="list_engineering_memory_files",
            description="List available long-term engineering memory files.",
            inputSchema=LIST_SCHEMA,
        ),
        Tool(
            name="add_engineering_memory_note",
            description=(
                "Write a timestamped long-term engineering memory note. "
                "Use only after the user explicitly asks to save or update memory."
            ),
            inputSchema=ADD_NOTE_SCHEMA,
        ),
        Tool(
            name="get_project_memory_context",
            description="Build the auto-mounted long-term memory context for a project or repository cwd.",
            inputSchema=PROJECT_CONTEXT_SCHEMA,
        ),
        Tool(
            name="get_project_engineering_context",
            description=(
                "Build compact structured project context: recent progress, project facts, "
                "interfaces, pin map, baud rates, and indexed resource paths."
            ),
            inputSchema=PROJECT_CONTEXT_SCHEMA,
        ),
        Tool(
            name="search_project_memory",
            description="Search long-term memory files scoped to the project or repository containing cwd.",
            inputSchema=PROJECT_SEARCH_SCHEMA,
        ),
        Tool(
            name="list_memory_projects",
            description="List projects with indexed long-term engineering memory.",
            inputSchema=LIST_SCHEMA,
        ),
        Tool(
            name="refresh_project_resources",
            description=(
                "Scan configured shared project-resource folders and index only matching file paths "
                "for the project containing cwd. Does not copy or read file contents."
            ),
            inputSchema=PROJECT_RESOURCE_REFRESH_SCHEMA,
        ),
        Tool(
            name="list_project_resources",
            description=(
                "List indexed resource file locations for the project containing cwd, including "
                "EDA netlists and schematic PDFs when matched."
            ),
            inputSchema=PROJECT_RESOURCE_LIST_SCHEMA,
        ),
        Tool(
            name="upsert_project_fact",
            description=(
                "Record or update one project-scoped engineering fact, such as project code, "
                "chip model, build command, hardware revision, or default baud rate. "
                "Use only for observed or explicitly confirmed facts, not guesses."
            ),
            inputSchema=PROJECT_FACT_UPSERT_SCHEMA,
        ),
        Tool(
            name="list_project_facts",
            description="List structured project facts for the project containing cwd.",
            inputSchema=PROJECT_FACT_LIST_SCHEMA,
        ),
        Tool(
            name="update_project_progress",
            description=(
                "Append a structured project progress entry with completed work, blockers, "
                "next steps, and verification status."
            ),
            inputSchema=PROJECT_PROGRESS_UPDATE_SCHEMA,
        ),
        Tool(
            name="list_project_progress",
            description="List recent structured progress entries for the project containing cwd.",
            inputSchema=PROJECT_PROGRESS_LIST_SCHEMA,
        ),
        Tool(
            name="upsert_project_action_config",
            description=(
                "Record or update one project standard action configuration for build, flash, "
                "monitor, clean, test, or reset. Stores command arrays and config locations, "
                "not execution logs."
            ),
            inputSchema=PROJECT_ACTION_CONFIG_UPSERT_SCHEMA,
        ),
        Tool(
            name="list_project_action_configs",
            description="List stored standard action configurations for the project containing cwd.",
            inputSchema=PROJECT_ACTION_CONFIG_LIST_SCHEMA,
        ),
        Tool(
            name="upsert_project_interface",
            description=(
                "Record or update a hardware/software interface, including UART number, baud rate, "
                "TX/RX pins, protocol, and settings."
            ),
            inputSchema=PROJECT_INTERFACE_UPSERT_SCHEMA,
        ),
        Tool(
            name="list_project_interfaces",
            description="List structured interfaces, UARTs, baud rates, and protocol settings for the project.",
            inputSchema=PROJECT_INTERFACE_LIST_SCHEMA,
        ),
        Tool(
            name="upsert_project_pin",
            description=(
                "Record or update one project pin-map row from code, schematic PDF, EDA netlist, "
                "board notes, or user confirmation."
            ),
            inputSchema=PROJECT_PIN_UPSERT_SCHEMA,
        ),
        Tool(
            name="list_project_pin_map",
            description="List structured project pin mappings for wiring cross-checks.",
            inputSchema=PROJECT_PIN_LIST_SCHEMA,
        ),
        Tool(
            name="search_troubleshooting_memory",
            description="Search indexed troubleshooting cases by fault symptom and return proactive reminders.",
            inputSchema=TROUBLESHOOTING_SEARCH_SCHEMA,
        ),
        Tool(
            name="list_troubleshooting_memory_cases",
            description="List troubleshooting memory cases indexed in the local SQLite memory database.",
            inputSchema=LIST_SCHEMA,
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = arguments or {}
    try:
        if name == "search_engineering_memory":
            result = {"ok": True, "hits": store.search(args["query"], args.get("max_results", 20))}
        elif name == "read_engineering_memory":
            result = {"ok": True, **store.read(args["path"], args.get("max_chars", 12000))}
        elif name == "list_engineering_memory_files":
            result = {"ok": True, "files": store.list_files(args.get("limit", 200))}
        elif name == "add_engineering_memory_note":
            result = {"ok": True, **store.add_note(args["title"], args["content"], args.get("tags"))}
        elif name == "get_project_memory_context":
            result = {"ok": True, **project_store.project_context(args["cwd"], args.get("max_chars", 8000))}
        elif name == "get_project_engineering_context":
            result = {"ok": True, **project_store.project_engineering_context(args["cwd"], args.get("max_chars", 8000))}
        elif name == "search_project_memory":
            result = {
                "ok": True,
                **project_store.search_project(args["cwd"], args["query"], args.get("max_results", 20)),
            }
        elif name == "list_memory_projects":
            result = {"ok": True, "projects": project_store.list_projects(args.get("limit", 200))}
        elif name == "refresh_project_resources":
            result = {
                "ok": True,
                **project_store.refresh_project_resources(
                    args["cwd"],
                    bool(args.get("force", False)),
                    args.get("max_files", 20000),
                ),
            }
        elif name == "list_project_resources":
            result = {
                "ok": True,
                **project_store.list_project_resources(
                    args["cwd"],
                    args.get("query", ""),
                    args.get("limit", 50),
                ),
            }
        elif name == "upsert_project_fact":
            result = {
                "ok": True,
                **project_store.upsert_project_fact(
                    args["cwd"],
                    args["category"],
                    args["key"],
                    args["value"],
                    args.get("source", "manual"),
                    args.get("confidence", "manual"),
                    args.get("notes", ""),
                    args.get("source_path", ""),
                    bool(args.get("verified", False)),
                ),
            }
        elif name == "list_project_facts":
            result = {
                "ok": True,
                **project_store.list_project_facts(
                    args["cwd"],
                    args.get("category", ""),
                    args.get("query", ""),
                    args.get("limit", 100),
                ),
            }
        elif name == "update_project_progress":
            result = {
                "ok": True,
                **project_store.update_project_progress(
                    args["cwd"],
                    args["status"],
                    args["summary"],
                    args.get("completed", ""),
                    args.get("blockers", ""),
                    args.get("next_steps", ""),
                    args.get("verification", ""),
                ),
            }
        elif name == "list_project_progress":
            result = {"ok": True, **project_store.list_project_progress(args["cwd"], args.get("limit", 20))}
        elif name == "upsert_project_action_config":
            result = {
                "ok": True,
                **project_store.upsert_project_action_config(
                    args["cwd"],
                    args["action"],
                    args["command"],
                    args.get("action_cwd", ""),
                    args.get("device_id", ""),
                    args.get("framework", ""),
                    args.get("config_path", ""),
                    args.get("timeout_ms"),
                    args.get("risk", ""),
                    args.get("source", "manual"),
                    args.get("confidence", "manual"),
                    bool(args.get("verified", False)),
                    args.get("notes", ""),
                ),
            }
        elif name == "list_project_action_configs":
            result = {
                "ok": True,
                **project_store.list_project_action_configs(
                    args["cwd"],
                    args.get("action", ""),
                    args.get("query", ""),
                    args.get("limit", 100),
                ),
            }
        elif name == "upsert_project_interface":
            result = {
                "ok": True,
                **project_store.upsert_project_interface(
                    args["cwd"],
                    args["name"],
                    args.get("interface_type", ""),
                    args.get("uart_no", ""),
                    args.get("baud_rate", ""),
                    args.get("tx_pin", ""),
                    args.get("rx_pin", ""),
                    args.get("protocol", ""),
                    args.get("settings", {}),
                    args.get("source", "manual"),
                    args.get("confidence", "manual"),
                    args.get("notes", ""),
                ),
            }
        elif name == "list_project_interfaces":
            result = {
                "ok": True,
                **project_store.list_project_interfaces(args["cwd"], args.get("query", ""), args.get("limit", 100)),
            }
        elif name == "upsert_project_pin":
            result = {
                "ok": True,
                **project_store.upsert_project_pin(
                    args["cwd"],
                    args["peripheral"],
                    args["signal"],
                    args.get("gpio", ""),
                    args.get("board", ""),
                    args.get("net_name", ""),
                    args.get("connector", ""),
                    args.get("direction", ""),
                    args.get("level", ""),
                    args.get("pull", ""),
                    args.get("source", "manual"),
                    args.get("confidence", "manual"),
                    bool(args.get("verified", False)),
                    args.get("notes", ""),
                ),
            }
        elif name == "list_project_pin_map":
            result = {
                "ok": True,
                **project_store.list_project_pin_map(args["cwd"], args.get("query", ""), args.get("limit", 200)),
            }
        elif name == "search_troubleshooting_memory":
            result = {
                "ok": True,
                "matches": troubleshooting_index.search(args["query"], args.get("max_results", MAX_HINTS)),
            }
        elif name == "list_troubleshooting_memory_cases":
            result = {"ok": True, "cases": troubleshooting_index.list_cases(args.get("limit", 200))}
        else:
            raise MemoryStoreError(f"unknown tool: {name}")
    except (KeyError, TypeError, ValueError, MemoryStoreError) as exc:
        result = {"ok": False, "error": str(exc)}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":")))]


async def main() -> None:
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())
