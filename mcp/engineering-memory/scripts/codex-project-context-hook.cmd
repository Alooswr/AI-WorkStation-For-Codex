@echo off
if not defined CODEX_MEMORY_ROOT set "CODEX_MEMORY_ROOT=%USERPROFILE%\.codex\memories"
if not defined CODEX_PROJECT_RESOURCE_MAX_SCAN_FILES set "CODEX_PROJECT_RESOURCE_MAX_SCAN_FILES=50000"
if not defined CODEX_PROJECT_CONTEXT_HOOK_MODE set "CODEX_PROJECT_CONTEXT_HOOK_MODE=silent"
set "PYTHONUTF8=1"
for %%I in ("%~dp0..") do set "CODEX_MEMORY_MCP_ROOT=%%~fI"
set "PYTHONPATH=%CODEX_MEMORY_MCP_ROOT%\src;%PYTHONPATH%"
python -m codex_memory_mcp.project_context_hook
