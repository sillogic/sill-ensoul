# 任务：把 sill-ensoul MCP 从本地 stdio 切换到远程 HTTP 服务器

> ⚠️ **人类先读：别直接改这个文件！**
>
> 本文件在公开 git 仓库里。**不要在仓库内直接替换占位符**——填了真实 IP/端口/token 后，下次 `git add .` 提交就会把它带进历史并推送出去，等于公开泄露。
>
> 正确做法：**先把文件复制到仓库外，在副本上填值，粘贴完删除副本**：
> - Windows（PowerShell）：`Copy-Item deploy\cli-setup\switch-to-remote.md $HOME\switch-to-remote.md` → 改 `$HOME\switch-to-remote.md` → 用完 `Remove-Item $HOME\switch-to-remote.md`
> - Linux / macOS：`cp deploy/cli-setup/switch-to-remote.md ~/switch-to-remote.md` → 改 `~/switch-to-remote.md` → 用完 `rm ~/switch-to-remote.md`
>
> 副本在仓库目录之外，git 永远看不见它，物理上不可能被提交。下面这份文件里仍是占位符，供直接粘贴给 CLI。

你是本机 CLI。请帮我完成一次 sill-ensoul MCP 配置切换：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 目标服务器（已确认可连）

- MCP 端点：`http://<服务器公网IP>:<端口>/mcp`
- 鉴权头：`Authorization: Bearer <TOKEN>`（每个请求都带）

## 第一步：确认你是谁，只做对应那一节

下面 A–D 按 CLI 分节。先判断你自己属于哪一类，**只执行对应小节的步骤，其余小节直接忽略**；各节做完后再执行最后的「收尾」。

| 你是 | 走哪节 | 方式 |
|---|---|---|
| Claude Code | **A** | streamable-http 原生 |
| Codex（desktop） | **B** | `npx mcp-remote` stdio↔HTTP 桥 |
| zcode | **C** | `npx mcp-remote` stdio↔HTTP 桥 |
| 其他任何 CLI | **D** | `npx mcp-remote` stdio↔HTTP 桥（通用） |

> **mcp-remote 桥接公共参数（B/C/D 的 mcp-remote 命令都要带，缺了必踩坑，已实测）**：
> - `--allow-http`：mcp-remote 默认拒绝非 HTTPS 地址，裸 HTTP 端点必须显式加；
> - `--transport http-only`：默认 `http-first` 会先发一个假 initialize（`mcp-remote-fallback-test`）探测 SSE，再开第二个真 session，与 FastMCP 的 session 管理冲突 → 后续调用全部 `400 Bad Request: Missing session ID`；`http-only` 纯 POST 直连完全兼容。
> - 另外客户端握手必须串行：等 initialize 响应（session id 在响应头里）再发后续请求（自写测试脚本注意，正规 CLI 客户端如 pi 的 mcp-bridge 本身就是串行的）。

---

## A. Claude Code

1. 找到 sill-ensoul 的 MCP 注册。检查两处：① `~/.claude.json` 顶层 `mcpServers`（全局层）；② 当前项目 `.mcp.json` 顶层 `mcpServers`（项目层）。两处都可能存在 —— 告诉我你发现了几处、分别在哪个文件、现在的注册内容是什么。
2. 对每处现有注册，先把它**原样备份**（写到一个不会被 git 跟踪的位置，如 `~/.sill-ensoul-mcp-config.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册改成下面这个 streamable-http 形式（server 名保持 `sill-ensoul` 不变）：

```json
{ "mcpServers": { "sill-ensoul": {
  "type": "streamable-http",
  "url": "http://<服务器公网IP>:<端口>/mcp",
  "headers": { "Authorization": "Bearer <TOKEN>" }
} } }
```

如果你的版本较老不支持 `streamable-http`，告诉我并改用 `"type": "http"`（或提示我先升级 CLI）。

4. 校验：确认改动后文件是合法 JSON、结构正确；逐处说明改了什么、旧值备份在哪。
5. 不要动本地 `sill-ensoul-mcp` 的安装（stdio 本地 server 保留；以后想切回来用备份即可）。

---

## B. Codex（desktop）

1. 打开 `~/.codex/config.toml`，找到（或新增）`[mcp_servers.sill-ensoul]` 段。
2. 若已有旧注册，先把该段**原样备份**（如 `~/.codex/sill-ensoul-mcp.backup.toml`），告诉我备份路径。
3. 把该段改成用 `mcp-remote` 桥接远程 HTTP（Windows 用 `cmd /c` 包一层，Linux/macOS 直接写）：

Windows：

```toml
[mcp_servers.sill-ensoul]
command = "cmd"
args = ["/c", "npx", "--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>"]
startup_timeout_ms = 15000
```

Linux / macOS：

```toml
[mcp_servers.sill-ensoul]
command = "npx"
args = ["--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>"]
startup_timeout_ms = 15000
```

4. 校验：确认 config.toml 是合法 TOML、段结构正确；说明改了什么、备份在哪。
5. 不要动 `~/.codex/AGENTS.md` 里的规则引用（薄壳只管规则，不管 MCP server 注册）。

---

## C. zcode

1. 找到 sill-ensoul 的 MCP server 注册 —— 通常在 `~/.zcode/cli/config.json` 的 `servers.sill-ensoul` 键下（以你的实际配置文件为准），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**（如 `~/.zcode/sill-ensoul-mcp.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册改成「stdio 命令桥接远程 HTTP」：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --allow-http --transport http-only --header "Authorization: Bearer <TOKEN>"`，按你自己配置 schema 里注册一个 stdio server 的既有写法来放（Windows 下若命令名找不到，可加 `cmd /c` 包一层）。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件是合法 JSON、结构正确；说明改了什么、备份在哪。
5. 不要动你的 `AGENTS.md` 规则引用（薄壳只管规则，不管 MCP server 注册）。

---

## D. 其他 CLI（通用）

1. 找到本 CLI 里 sill-ensoul 的 MCP server 注册位置（你比任何人都清楚自己的配置放哪、什么格式），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**到不会被 git 跟踪的位置，告诉我备份路径。
3. 把 sill-ensoul 的注册改成「stdio 命令桥接远程 HTTP」—— 这是任何 CLI 都通用的方式（不依赖各家对 http 的原生支持）：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --allow-http --transport http-only --header "Authorization: Bearer <TOKEN>"`，按你既有 stdio server 注册的写法放。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件格式合法、结构正确；说明改了什么、备份在哪。

---

## 收尾（所有 CLI 都做）

- **必须完全退出本 CLI 再重新打开**，新会话才会用新配置（配置启动时加载，不热更新）。
- 重启后在会话里调 `agent_index` / `wiki_search` 能通 = 切换成功。
- 不要把 token / IP / 端口写进任何会被 git 提交的文件：填了真实值的提示词文件一律在**仓库外的副本**上改（见文件开头），用完删除。
- 顺序别反：先确认服务器服务在跑（`curl` 返回 401）、KB 已迁移，再切配置。
