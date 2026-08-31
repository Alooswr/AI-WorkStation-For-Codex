# 嘉立创 EDA 接入与连接

Read this reference only when installing, reconnecting, or diagnosing the official EasyEDA bridge.

## Supported topology

`Codex -> easyeda-api skill -> 127.0.0.1:49620-49629 bridge -> Run API Gateway -> 嘉立创EDA专业版 eda.* API`

This workflow targets 嘉立创EDA专业版 V3. The installed Gateway release must declare compatibility with the user's editor version. It does not apply to 嘉立创EDA标准版.

Official components:

- API skill: <https://github.com/easyeda/easyeda-api-skill>
- Gateway extension: <https://github.com/easyeda/eext-run-api-gateway>
- Extension page: <https://jlc-ext.com/item/oshwhub/run-api-gateway>
- Extension API reference: <https://prodocs.lceda.cn/cn/api/reference/pro-api.html>

## Setup

1. Confirm `../easyeda-api/SKILL.md`, `scripts/bridge-server.mjs`, and `node_modules/ws` exist.
2. Run `scripts/bridge.ps1 -Action start` from this skill. The script starts the official server as a hidden Windows process and scans only ports 49620-49629.
3. In 嘉立创EDA专业版, open `高级 -> 扩展管理器` and install or import `Run API Gateway` from the official release.
4. When 嘉立创EDA asks for external-interaction permission, hand control to the user. Do not approve it automatically.
5. If the Gateway is installed but disconnected, use its own `重新连接` action, then recheck health.

Installing or updating an extension changes the EDA application. Follow the active Computer Use confirmation rules immediately before the install action.

## Read-only validation

Run `scripts/bridge.ps1 -Action status` and require a response shaped like:

```json
{
  "found": true,
  "port": 49620,
  "health": {
    "service": "easyeda-bridge",
    "edaConnected": true
  }
}
```

Then query:

```powershell
$port = 49620
Invoke-RestMethod "http://127.0.0.1:$port/eda-windows"
```

Use a read-only execute call before any design change:

```powershell
$body = @{ code = 'return { project: await eda.dmt_Project.getCurrentProjectInfo(), document: await eda.dmt_SelectControl.getCurrentDocumentInfo() };' } | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:$port/execute" -Method Post -ContentType 'application/json' -Body $body
```

The result must identify the expected EDA window, project, and document type. A healthy bridge with `edaConnected: false` proves only that the local server is running, not that Codex can control 嘉立创EDA.

## Troubleshooting boundaries

- No bridge found: verify Node.js, the sibling skill path, dependency install, and bridge error log returned by `bridge.ps1 -Action start`.
- Bridge found but no EDA window: verify the Gateway is installed, enabled, permitted for external interaction, and connected.
- Multiple windows: list them and ask the user to choose; do not guess from recency.
- An API returns null or times out: verify project/document state and the exact API signature before blaming permissions or retrying.
- Stop the bridge at the end of the active EDA task with `scripts/bridge.ps1 -Action stop`, unless the user explicitly asks to keep it available.

The bridge has no authentication token. It must remain loopback-only and should not be exposed through port forwarding, LAN binding, tunnels, or firewall publication.
