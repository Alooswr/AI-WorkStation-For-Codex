@echo off
if not defined CODEX_MEMORY_ROOT set "CODEX_MEMORY_ROOT=%USERPROFILE%\.codex\memories"
set "PYTHONUTF8=1"
for %%I in ("%~dp0..") do set "CODEX_MEMORY_MCP_ROOT=%%~fI"
set "PYTHONPATH=%CODEX_MEMORY_MCP_ROOT%\src;%PYTHONPATH%"
python -m codex_memory_mcp.turn_summary_hook
