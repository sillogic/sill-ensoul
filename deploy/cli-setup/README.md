# 各 CLI 指向远程 sill-ensoul MCP —— 提示词文件

把本机 CLI（Claude Code / Codex / zcode 等）的 sill-ensoul MCP 从「本地 stdio」切换到「服务器 HTTP」。
**原则：不手敲命令** —— 把对应文件整个丢给那个 CLI，让它自己读配置、自己改、自己验证。

## 用法（三步）

1. 打开目标 CLI 的聊天窗口。
2. 把文件里的三个占位符替换成真实值：
   - `<服务器公网IP>` → 你的 ECS 公网 IP
   - `<端口>` → `ENSOUL_MCP_PORT`（默认 `8930`，没改就是它）
   - `<TOKEN>` → 服务器 `/etc/sill-ensoul/env` 里 `ENSOUL_MCP_TOKEN` 的值
3. 把整个文件内容粘贴给该 CLI，让它自己处理（改配置、备份、验证一条龙）。

## 文件对应

| CLI | 文件 | 方式 |
|---|---|---|
| Claude Code | `claude-code.md` | streamable-http 原生 |
| Codex desktop | `codex.md` | `npx mcp-remote` 桥 |
| zcode | `zcode.md` | `npx mcp-remote` 桥 |
| 其他任何 CLI | `other.md` | `npx mcp-remote` 桥 |

## 共同要点（提示词里已带，这里提醒）

- server 名保持 `sill-ensoul` 不变，只把注册从 stdio 换成 HTTP；
- 改之前先备份旧注册（备份路径会在对话里告诉你）；
- **改完必须完全退出该 CLI 再重开** —— 配置启动时加载，不热更新；
- 不要把 token 提交进任何 git 仓库；
- 顺序别反：先确认服务器 KB 已迁移、服务已起（`curl` 返回 401），再切客户端。
