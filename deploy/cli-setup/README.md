# 各 CLI 安装 sill-ensoul（远程 MCP）—— 提示词文件

把本机 CLI（Claude Code / Codex / zcode 等）接入远程 sill-ensoul MCP 服务器。
**原则：不手敲命令** —— 把 [`cli-remote.md`](cli-remote.md) 整个丢给那个 CLI，让它自己判断自己是哪类 CLI、自己读配置、自己改、自己验证。

> **文件分工（SIL-8 文档拆分定案 2026-08-27）**：本地直连 MCP → 仓库根 [`SETUP.md`](../../SETUP.md)；
> 远程 MCP → 本目录 [`cli-remote.md`](cli-remote.md)（CLI 安装）；Multica 平台 agent（前提：本机 CLI 已配好 MCP）
> → 本目录 [`multica.md`](multica.md)（Multica 初始化）。三个文件各管一种场景。
> 远程用户到手的是两份文件：`cli-remote.md`（CLI 安装）+ `multica.md`（Multica 初始化），
> 分别丢给 CLI 和 Multica 对话即可。

## 用法（三步）

> ⚠️ **先复制出仓库再填值**：`cli-remote.md` 在公开 git 仓库里，直接替换占位符后一旦 `git add .` 提交就会泄露真实 IP/端口/token。**先复制一份到仓库外**：
>
> - Windows（PowerShell）：`Copy-Item deploy\cli-setup\cli-remote.md $HOME\cli-remote.md`
> - Linux / macOS：`cp deploy/cli-setup/cli-remote.md ~/cli-remote.md`
>
> 在副本上填值，用完删除副本（`Remove-Item $HOME\cli-remote.md` / `rm ~/cli-remote.md`）。仓库内原文件始终保持占位符。

1. 打开目标 CLI 的聊天窗口。
2. 在**仓库外的副本**上把三个占位符替换成真实值：
   - `<服务器公网IP>` → 你的 ECS 公网 IP
   - `<端口>` → `ENSOUL_MCP_PORT`（默认 `8930`，没改就是它）
   - `<TOKEN>` → 你接入卡上的 Bearer token（管理员分发；服务器 `/etc/sill-ensoul/env` 里是 `ENSOUL_MCP_TOKEN`）
3. 把整个文件内容粘贴给该 CLI，让它自己处理。

**一个文件适用所有 CLI**，不用再按 CLI 挑文件：文件里 A–D 按 CLI 分节（A Claude Code streamable-http 原生；B Codex desktop / C zcode / D 其他 CLI 用 `npx mcp-remote` 桥），粘贴后它会只做自己那一节。

## 共同要点（提示词里已带，这里提醒）

- server 名保持 `sill-ensoul` 不变，只把注册指向远程端点（HTTP 直连或 mcp-remote 桥）；
- **mcp-remote 桥接命令必带 `--allow-http --transport http-only`**（mcp-remote 默认拒绝非 HTTPS 地址；默认 http-first 的 SSE 回退探测与 FastMCP session 管理冲突 → 400 Missing session ID，已实测）；
- 改之前先备份旧注册（备份路径会在对话里告诉你）；
- **改完必须完全退出该 CLI 再重开** —— 配置启动时加载，不热更新；
- 不要把填了真实值的提示词文件提交进任何 git 仓库（一律在仓库外副本上改）；
- 顺序别反：先确认服务器 KB 已迁移、服务已起（`curl` 返回 401），再切客户端。
