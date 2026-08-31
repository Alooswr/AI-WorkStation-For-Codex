# Codex Workstation Kit

这是一个面向私有仓库的、经过脱敏的 Codex 本机工作环境快照。它保留可复用的 MCP 源码、个人/本地 Skill、工程协作规则与精选长期记忆，但不是 `.codex` 目录的逐字备份，也不能直接覆盖到另一台机器。

## 包含内容

- `AGENTS.md`：已模板化的工程协作规则，个人称呼和本机用户目录已泛化。
- `MEMORY.md`：从原始长期记忆中人工提炼的通用偏好、验证门槛和故障护栏；不含项目细节和会话来源元数据。
- `mcp/`：当前本地 engineering-memory、firmware、serial-port MCP 的脱敏源码快照。
- `skills/`：18 个自建或本地授权信息明确的 Skill；链接目录已物化并去重。
- `config/mcp.example.toml`：从零编写的 MCP 占位配置，不含任何本机令牌、OAuth 状态或真实项目路径。
- `inventory/`：已复制与仅登记项目的边界说明。
- `scripts/audit_redaction.py`：提交前敏感信息审计。

## 恢复思路

1. 审阅 `inventory/` 和各目录许可证，再选择需要恢复的组件。
2. 将选定 Skill 复制到本机个人 Skill 目录；不要重建旧机器上的 Junction/SymbolicLink 拓扑。
3. 分别在 `mcp/engineering-memory` 和 `mcp/firmware` 中执行可编辑安装，再按需要安装 serial-port 依赖。
4. 复制 `config/mcp.example.toml` 到仓库外，替换双下划线占位符，追加到本机 Codex 配置。
5. 在本机私有位置创建 firmware 设备配置、memory 数据根目录，并重新完成远程 MCP OAuth。
6. 导入 `AGENTS.md` 和 `MEMORY.md` 前先检查是否适合新机器/新项目。

示例命令：

```powershell
python -m pip install -e .\mcp\engineering-memory
python -m pip install -e .\mcp\firmware
python -m pip install mcp pyserial
python .\scripts\audit_redaction.py .
```

第三方 Skill 的版权仍归原作者；保留其已有许可证/NOTICE，本仓库不提供统一再授权。
