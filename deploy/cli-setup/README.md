# 客户端接入提示词文件

本目录 = sill-ensoul **客户端接入**的提示词文件：把对应文件整个丢给那个 CLI（或
Multica 对话），让它自己判断自己是哪类、自己读配置、自己改、自己验证——**不手敲命令**。

| 文件 | 用途 |
|---|---|
| [`cli-remote.md`](cli-remote.md) | 远程客户端首次接入（连现成服务器 / 原本地切远程） |
| [`update-machine-id.md`](update-machine-id.md) | 已接入客户端补 `X-Machine-Id` 机器头（SIL-9） |
| [`multica.md`](multica.md) | Multica 平台 agent 绑定（前提：本机 CLI 已配好 MCP） |
| `README.md` | 本目录导航（就是这份） |

**场景路由**（谁该拿哪个文件）和**用法**（副本填值 → 粘贴）见根
[`README.md`](../../README.md) 的「部署场景决策表」，本目录不重复。

其他部署线：
- **服务器端**（跑 `sill-ensoul-http`，含 `deploy/sill-ensoul-http.service` 模板）→ [`docs/deployment.md`](../../docs/deployment.md)
- **本地单机**（stdio 直连，默认路径）→ [`SETUP.md`](../../SETUP.md)
