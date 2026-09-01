# 客户端接入提示词文件（deploy/cli-setup/）

本目录是 **sill-ensoul 客户端接入**的提示词文件集。**原则：不手敲命令** —— 把对应
文件整个丢给那个 CLI（或 Multica 对话），让它自己判断自己是哪类、自己读配置、自己改、
自己验证。

> 服务器端部署（跑 `sill-ensoul-http`）是另一条线，见 [`docs/deployment.md`](../../docs/deployment.md)；
> 本地单机安装（stdio 直连）是默认路径，见 [`SETUP.md`](../../SETUP.md)。

## 文件地图

| 文件 | 用途 | 谁读 | 前提 |
|---|---|---|---|
| [`cli-remote.md`](cli-remote.md) | **远程客户端首次接入**（连现成服务器 / 原本地切远程） | 目标 CLI 的 AI | 手上有服务器地址 + token |
| [`update-machine-id.md`](update-machine-id.md) | 已接入客户端**补 `X-Machine-Id` 机器头**（SIL-9 升级） | 目标 CLI 的 AI | 已用 cli-remote.md 装过 |
| [`multica.md`](multica.md) | **Multica 平台** agent 绑定 | Multica 对话 | 本机 CLI 已配好 MCP |
| [`README.md`](README.md) | 本索引（人读） | 人 | — |

## 场景路由（谁该拿哪个文件）

| 你的情况 | 拿哪个文件 |
|---|---|
| 没装过，连现成服务器（**不需要 clone 代码、不装本地包**） | `cli-remote.md` |
| 本机已用本地 stdio，想切到现成服务器 | `cli-remote.md`（旧注册自动备份替换；本机旧 KB 闲置或按 deployment.md 迁移） |
| 已装过远程，只缺机器身份头（记忆写入 `machine: unknown`） | `update-machine-id.md` |
| Multica 平台 agent（前提：MCP 已配好） | `multica.md` |

## 用法（三步）

> ⚠️ **先复制出仓库再填值**：这些文件在公开 git 仓库里，直接替换占位符后一旦
> `git add .` 提交就会泄露真实 IP/端口/token。**先复制一份到仓库外**：
>
> - Windows（PowerShell）：`Copy-Item deploy\cli-setup\cli-remote.md $HOME\cli-remote.md`
> - Linux / macOS：`cp deploy/cli-setup/cli-remote.md ~/cli-remote.md`
>
> 在副本上填值，用完删除副本。仓库内原文件始终保持占位符。
> （`update-machine-id.md` 是例外：它零秘密，只有主机名占位符，可直接丢。）

1. 打开目标 CLI 的聊天窗口（或 Multica 对话）。
2. 在**仓库外的副本**上把占位符替换成真实值（IP / 端口 / token，见文件内说明）。
3. 把整个文件内容粘贴给它，让它自己处理。

## 共同要点（各文件里已带，这里提醒）

- server 名保持 `sill-ensoul` 不变，只把注册指向远程端点；
- 每个请求带 `Authorization: Bearer <token>` **和** `X-Machine-Id: <你的主机名>`（机器身份，
  SIL-9，记忆自动打标 `machine:` 字段；不带则标 `unknown`）；
- **mcp-remote 桥接命令必带 `--allow-http --transport http-only`**（mcp-remote 默认拒绝非
  HTTPS 地址；默认 http-first 的 SSE 回退探测与 FastMCP session 管理冲突 → 400 Missing
  session ID，已实测）；
- 改之前先备份旧注册（备份路径会在对话里告诉你）；
- **改完必须完全退出该 CLI 再重开** —— 配置启动时加载，不热更新；
- 不要把填了真实值的提示词文件提交进任何 git 仓库（一律在仓库外副本上改）；
- 顺序别反：先确认服务器 KB 已迁移、服务已起（`curl` 返回 401），再切客户端。
