# Codex Memory MCP Server

Local stdio MCP server for long-term engineering memory.

The server is intentionally file-backed. It reads the existing Codex memory
workspace and writes new ad-hoc notes only under:

`%USERPROFILE%\.codex\memories\extensions\ad_hoc\notes`

Tools:

- `search_engineering_memory`: search Markdown and JSONL memory files.
- `read_engineering_memory`: read a memory file by relative path.
- `list_engineering_memory_files`: list readable memory files.
- `add_engineering_memory_note`: append a timestamped note when the user has
  explicitly asked to save or update long-term memory.
- `get_project_memory_context`: build the project memory context for a cwd.
- `get_project_engineering_context`: build compact structured project context,
  including recent progress, project facts, interfaces, pin map, baud rates,
  and resource paths.
- `search_project_memory`: search memory scoped to a project cwd.
- `list_memory_projects`: list indexed project memory roots.
- `refresh_project_resources`: index matching file paths from shared project-resource folders.
- `list_project_resources`: list indexed project resource file locations.
- `upsert_project_fact`: record or update one observed project fact.
- `list_project_facts`: list structured project facts.
- `update_project_progress`: append a structured project progress entry.
- `list_project_progress`: list recent project progress entries.
- `upsert_project_action_config`: record one standard project action command
  for build, flash, monitor, clean, test, or reset.
- `list_project_action_configs`: list stored standard action commands.
- `upsert_project_interface`: record UART/interface details such as baud rate,
  TX/RX pins, protocol, and settings.
- `list_project_interfaces`: list structured project interfaces.
- `upsert_project_pin`: record one pin-map row for wiring cross-checks.
- `list_project_pin_map`: list structured pin mappings.
- `search_troubleshooting_memory`: search indexed fault patterns and reminders.
- `list_troubleshooting_memory_cases`: list troubleshooting cases in SQLite.

Tool responses are compact JSON. Successful calls include `"ok": true`; invalid
arguments or blocked paths return `"ok": false` with an `error` string.

Codex starts this server through `%USERPROFILE%\.codex\config.toml`.

## Automatic turn summaries

Codex also runs `scripts\codex-turn-summary-hook.cmd` from the global
`%USERPROFILE%\.codex\hooks.json` Stop hook. The hook records each completed
turn as a new global note under the same ad-hoc notes directory. It records a
copy under the project memory folder only when the turn is classified as
`project_engineering`; Codex/MCP/hook/config work is classified as
`global_infrastructure` and stays global-only. It reads the hook payload from
stdin and never modifies existing memory files.

The `add_engineering_memory_note` MCP tool is still explicit-only. Automatic
turn summaries are written by the Stop hook, not by MCP tool calls.

Codex renders hook `systemMessage` output as a warning line in the CLI, so
display output is disabled by default. To test the optional display path, set
`CODEX_TURN_SUMMARY_DISPLAY=systemMessage`; the hook will then return a compact
message like `/* 本轮总结：... */`.

## Troubleshooting index

Fault-pattern reminders are stored in the same SQLite database under the
`troubleshooting_cases` table. The search tool can return at most the top 3
matching reminders. `UserPromptSubmit` runs in `silent` mode by default so the
Codex CLI does not print `hook context` blocks on every prompt. Set
`CODEX_PROJECT_CONTEXT_HOOK_MODE=alerts` to inject only troubleshooting
reminders, or `CODEX_PROJECT_CONTEXT_HOOK_MODE=full` to inject full project
memory context.

## Project memory

Project-scoped memory is stored under:

`%USERPROFILE%\.codex\memories\projects\<project-slug>`

Project metadata and turn summaries are indexed in SQLite at:

`%USERPROFILE%\.codex\memories\engineering_memory.sqlite`

The project root is the nearest parent containing `.git`; if no git repository
exists, the current working directory is used. In default `silent` mode,
`UserPromptSubmit` refreshes project resource indexes but does not return
`additionalContext`, avoiding noisy CLI output. Project memory remains available
through `get_project_memory_context`, `search_project_memory`, and
`list_project_resources`. Global infrastructure work, such as changing this MCP
server, Codex hooks, or Codex config, is retained in global long-term memory
instead of being added to an unrelated engineering project.

## First project scan

When a project is first resolved, the MCP creates or updates the project
`profile.md` with a deterministic first-pass scan. The scan records:

- project type
- build system
- entry files
- main modules
- driver directories
- config files
- flash method
- test method
- potential risks

The scanner is intentionally conservative. It reads only small text snippets
needed to detect entry points and build/test targets, ignores generated/vendor
directories such as `build`, `dist`, `.git`, and `node_modules`, and stores
paths plus summaries instead of copying source contents. If an existing profile
already has `## First Scan`, it is left unchanged. If a profile exists without
that section, the scan section is inserted before `## Stable Notes` so manual
notes are preserved.

## Structured project engineering memory

Project memory now has structured SQLite tables for data that should be
retrieved precisely instead of only searched as prose:

- `project_facts`: project code/name, chip model, hardware revision, build and
  flash commands, default baud rate, source path, confidence, and verification
  flag.
- `project_progress`: compact work progress entries from the Stop hook or the
  `update_project_progress` tool, including status, completed work, blockers,
  next steps, and verification notes.
- `project_actions`: standard build/flash/monitor/clean/test/reset action
  commands, device IDs, framework type, config file path, timeout, risk, and
  verification flag.
- `project_interfaces`: UART/I2C/SPI/CAN/network/debug interfaces, including
  UART number, baud rate, TX/RX pins, protocol, and JSON settings.
- `project_pin_map`: board/peripheral/signal/GPIO/net/connector/direction rows
  for schematic, EDA netlist, and firmware wiring cross-checks.

`resolve_project()` automatically records identity facts for each project:
`project.code`, `project.root`, and `project.memory_slug`. Turn summaries from
project engineering work are also inserted into `project_progress` so the
latest work state can be queried without reading every Markdown turn file.

The structured upsert tools should store only observed or explicitly confirmed
facts. For engineering documents, schematic PDFs, and EDA netlists, store the
file location and extracted fact rows; do not copy whole document contents into
long-term memory.

## Project resource path index

The project memory layer can also index file locations from shared engineering
resource folders. This is configured with:

`CODEX_PROJECT_RESOURCE_ROOTS=<PROJECT_RESOURCE_ROOTS_JSON>`

The scanner matches files by project aliases such as repository name, nearby path
segments, and git remote repository name. It indexes likely resource files only:
documents, PDFs, spreadsheets, text/Markdown notes, archives, EDA netlists, and
files whose names clearly look like netlists or schematics. It stores only file
paths and metadata in SQLite, not file contents. Indexed metadata includes path,
root, file name, extension, type, size, modified time, matched alias, and match
score.

Resource paths are stored in the `project_resources` SQLite table and are
included in auto-mounted project context under `Project Resource Paths`. EDA
netlists and schematic PDFs are classified as `eda_netlist` and `schematic_pdf`
so they appear near the top for wiring cross-check tasks.

If a turn summary mentions a file path inside the configured resource folders,
the Stop hook also binds that path to the current project with
`matched_alias=mentioned_in_turn`. This handles ambiguous files such as a generic
`Netlist_Schematic2_2026-03-19.tel` whose name does not contain the project
identifier.
