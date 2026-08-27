# 各 CLI 指向远程 sill-ensoul MCP —— 提示词文件

把本机 CLI（Claude Code / Codex / zcode 等）的 sill-ensoul MCP 从「本地 stdio」切换到「服务器 HTTP」。
**原则：不手敲命令** —— 把 `switch-to-remote.md` 整个丢给那个 CLI，让它自己判断自己是哪类 CLI、自己读配置、自己改、自己验证。

## 用法（三步）

> ⚠️ **先复制出仓库再填值**：`switch-to-remote.md` 在公开 git 仓库里，直接替换占位符后一旦 `git add .` 提交就会泄露真实 IP/端口/token。**先复制一份到仓库外**：
>
> - Windows（PowerShell）：`Copy-Item deploy\cli-setup\switch-to-remote.md $HOME\switch-to-remote.md`
> - Linux / macOS：`cp deploy/cli-setup/switch-to-remote.md ~/switch-to-remote.md`
>
> 在副本上填值，用完删除副本（`Remove-Item $HOME\switch-to-remote.md` / `rm ~/switch-to-remote.md`）。仓库内原文件始终保持占位符。

1. 打开目标 CLI 的聊天窗口。
2. 在**仓库外的副本**上把三个占位符替换成真实值：
   - `<服务器公网IP>` → 你的 ECS 公网 IP
   - `<端口>` → `ENSOUL_MCP_PORT`（默认 `8930`，没改就是它）
   - `<TOKEN>` → 服务器 `/etc/sill-ensoul/env` 里 `ENSOUL_MCP_TOKEN` 的值
3. 把整个文件内容粘贴给该 CLI，让它自己处理。

**一个文件适用所有 CLI**，不用再按 CLI 挑文件：文件里 A–D 按 CLI 分节（A Claude Code streamable-http 原生；B Codex desktop / C zcode / D 其他 CLI 用 `npx mcp-remote` 桥），粘贴后它会只做自己那一节。

## 共同要点（提示词里已带，这里提醒）

- server 名保持 `sill-ensoul` 不变，只把注册从 stdio 换成 HTTP；
- 改之前先备份旧注册（备份路径会在对话里告诉你）；
- **改完必须完全退出该 CLI 再重开** —— 配置启动时加载，不热更新；
- 不要把填了真实值的提示词文件提交进任何 git 仓库（一律在仓库外副本上改）；
- 顺序别反：先确认服务器 KB 已迁移、服务已起（`curl` 返回 401），再切客户端。
