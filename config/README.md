# MCP configuration template

`mcp.example.toml` is intentionally not a drop-in file. Render a private copy outside the repository and replace:

- `__PYTHON_EXE__`: absolute Python interpreter path.
- `__REPO_ROOT__`: this checkout's absolute path.
- `__LOCAL_CONFIG_DIR__`: ignored local configuration directory.
- `__LOCAL_MEMORY_ROOT__`: private long-term memory data directory.
- `__PROJECT_RESOURCE_ROOTS_JSON__`: machine-local project roots in the format expected by the memory MCP.
- `__MOTIONSITES_MCP_URL__`: remote endpoint; perform OAuth again on the target machine.

Do not paste shell tokens, API keys or OAuth data into a tracked TOML file. Codex-managed `node_repl`/`cua_repl` entries are omitted because their paths and native-pipe values are generated per installation.

