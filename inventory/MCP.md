# MCP inventory

| Entry | Kind | Repository handling |
|---|---|---|
| `engineering_memory` | Local Python STDIO | Current active source snapshot copied; memory data, databases, logs and live hook config excluded. |
| `firmware` | Local Python STDIO | Current working-tree snapshot copied, including local uncommitted source changes; real device config excluded. |
| `serial-port` | Local Python STDIO | Script copied; runtime enumeration data is not stored. |
| `openaiDeveloperDocs` | Public HTTPS | Public endpoint retained in template. |
| `motionsites` | Remote HTTPS/OAuth | Source is not local; only a placeholder entry is retained. OAuth must be repeated. |
| `node_repl` | Codex-managed STDIO | Inventory only; generated runtime paths and pipe metadata excluded. |
| `cua_repl` | Codex-managed STDIO | Inventory only; generated binary/runtime metadata excluded. |

The live Codex configuration and all backups are excluded by design. The template in `config/` was written from scratch and does not share Git history with the local configuration.

