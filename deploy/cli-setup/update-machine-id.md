# 任务：为已接入的 sill-ensoul 客户端补机器身份（X-Machine-Id）

> **人类先读：别直接改这个文件！**
>
> 本文件在公开 git 仓库里，填了真实值后提交就会泄露。本文件**不需要填任何秘密**
> （你的 IP / token 在你现有注册里已经有了），唯一要填的是你的**主机名**（非秘密）。
> 所以可以直接把本文件丢给 AI 使用；如果要存副本，放仓库外即可。
>
> **你是哪种用户？**
> - **已经用 cli-remote.md / SETUP.md 装过 sill-ensoul 远程 MCP** → 读本文件（升级）。
> - **还没装过** → 去读 [`cli-remote.md`](cli-remote.md)（首次安装，那里已经包含 X-Machine-Id）。
> - 本机 sill-ensoul 走的是**本地 stdio**（`sill-ensoul-mcp`，不连服务器）→ 不用改，跳过本文件。

你是本机 CLI。请帮我给 sill-ensoul 的 MCP 注册**补一个 `X-Machine-Id` 请求头**：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 为什么要加

sill-ensoul 的服务器现在给每条记忆自动打标 `machine:` 字段（记录"这条是谁写的"），
靠客户端在每个请求带 `X-Machine-Id: <你的主机名>` 头。共享 KB 的读者（包括其他机器上
的 AI）靠它区分「谁写的」和「我在哪台机器」——**不带的机器写入的记忆会标成 `unknown`**。

## 目标

- 在你现有的 sill-ensoul MCP 注册上，给每个请求**追加**一个请求头：
  `X-Machine-Id: <你的主机名>`
- 主机名获取：Windows 运行 `echo %COMPUTERNAME%`；macOS / Linux 运行 `hostname`。
- server 名保持 `sill-ensoul` 不变；**只加头，别的什么都不动**。

## 第一步：确认你是谁，只做对应那一节

| 你是 | 走哪节 | 你的注册长什么样 |
|---|---|---|
| Claude Code | **A** | `~/.claude.json` 或项目 `.mcp.json` 里 `type: streamable-http` |
| Codex（desktop） | **B** | `~/.codex/config.toml` 里 `[mcp_servers.sill-ensoul]` |
| zcode | **C** | `~/.zcode/cli/config.json` 里 `servers.sill-ensoul` |
| pi | **E** | `~/.pi/agent/settings.json` 里 `mcpServers.sill-ensoul` |
| 其他任何 CLI | **D** | 你的 CLI 的 stdio server 注册（命令是 `npx mcp-remote ...`） |

先**核对**（所有节通用）：找到 sill-ensoul 注册后，如果它的配置里**已经有**
`X-Machine-Id` 头（mcp-remote 命令里已有 `--header "X-Machine-Id: ..."`，或 headers 里
已有该键）→ 说明已升级过，**直接跳过本文件，什么都不用做**。没有 → 按下面对应节改。

---

## A. Claude Code（streamable-http 原生）

1. 找到 sill-ensoul 的注册（`~/.claude.json` 顶层 `mcpServers`，或项目 `.mcp.json`
   顶层 `mcpServers`）。把现在的注册内容告诉我。
2. 在它的 `headers` 里加 `"X-Machine-Id": "<你的主机名>"`，得到类似：

```json
{ "mcpServers": { "sill-ensoul": {
  "type": "streamable-http",
  "url": "http://<你现有的服务器地址>/mcp",
  "headers": {
    "Authorization": "Bearer <你现有的TOKEN>",
    "X-Machine-Id": "<你的主机名>"
  }
} } }
```

3. 校验：改动后文件是合法 JSON，`url` / `Authorization` 保持原值不变，只多了
   `X-Machine-Id` 一个键。改前先备份原配置（如 `~/.claude.json.bak`），告诉我备份路径。

---

## B. Codex（desktop）

1. 打开 `~/.codex/config.toml`，找到 `[mcp_servers.sill-ensoul]` 段，告诉我现在的样子。
2. 在 args 里**追加**两个元素：`"--header"` 和 `"X-Machine-Id: <你的主机名>"`
   （注意：`Authorization` 的 `--header` 保持不动，X-Machine-Id 是新增的一组），得到类似：

```toml
[mcp_servers.sill-ensoul]
command = "cmd"
args = ["/c", "npx", "--yes", "mcp-remote", "http://<你现有的服务器地址>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <你现有的TOKEN>", "--header", "X-Machine-Id: <你的主机名>"]
startup_timeout_ms = 15000
```

   （macOS / Linux 去掉 `cmd`、`/c` 两层即可，结构一样。）
3. 校验：config.toml 是合法 TOML，原来的参数原样保留，只多了 `X-Machine-Id` 一组
   `--header`。改前备份（如 `~/.codex/sill-ensoul-mcp.backup.toml`），告诉我备份路径。

---

## C. zcode

1. 找到 sill-ensoul 的注册（通常在 `~/.zcode/cli/config.json` 的 `servers.sill-ensoul`），
   告诉我现在的注册内容。
2. 把它设置成「stdio 命令桥接远程 HTTP」并带机器头（若已是 mcp-remote 桥，只追加
   `--header "X-Machine-Id: <你的主机名>"` 一组参数即可；`Authorization` 那组保留）：

   `npx --yes mcp-remote http://<你现有的服务器地址>/mcp --allow-http --transport http-only --header "Authorization: Bearer <你现有的TOKEN>" --header "X-Machine-Id: <你的主机名>"`

   按你自己配置 schema 里既有 stdio server 的写法放。server 名保持 `sill-ensoul` 不变。
3. 校验：配置文件是合法 JSON、结构正确，只多了 X-Machine-Id 一组参数。改前备份，告诉我路径。

---

## D. 其他 CLI（mcp-remote 通用桥）

1. 找到本 CLI 里 sill-ensoul 的 MCP server 注册（你比任何人都清楚自己的配置放哪、
   什么格式），把现在的注册内容告诉我。
2. 如果注册的命令是 `npx ... mcp-remote ...`，在参数里**追加**一组
   `--header "X-Machine-Id: <你的主机名>"`（`Authorization` 那组 `--header` 保留不动）。
3. 校验：配置文件格式合法、结构正确。改前备份，告诉我备份路径。

---

## E. pi（settings.json 的 mcpServers）

1. 打开 `~/.pi/agent/settings.json`，找到 `mcpServers.sill-ensoul`，告诉我现在的样子。
2. 在 `args` 里**追加**两个字符串：`"--header"`、`"X-Machine-Id: <你的主机名>"`
   （紧跟 `Authorization` 那组之后），得到类似：

```json
{ "mcpServers": { "sill-ensoul": {
  "command": "cmd",
  "args": ["/c", "npx", "--yes", "mcp-remote", "http://<你现有的服务器地址>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <你现有的TOKEN>", "--header", "X-Machine-Id: <你的主机名>"],
  "startupTimeoutMs": 60000
} } }
```

   （macOS / Linux 去掉 `cmd`、`/c` 两层即可。若你的 pi 用的是自包含 HTTP 客户端扩展
   而非 mcp-remote 桥，在扩展自己的配置里加 `X-Machine-Id` header。）
3. 校验：settings.json 是合法 JSON，原有配置不动，只多了 X-Machine-Id 一组。改前备份，告诉我路径。

---

## 收尾（所有 CLI 都做）

- **必须完全退出本 CLI 再重新打开**，新会话才会用新配置（配置启动时加载，不热更新）。
- 重启后在会话里让 AI **写一条记忆再读回**（如"写一条概念到 projects/machine-verify，
  读回 frontmatter.machine 值"）——`machine` 等于你的主机名 = 成功；`unknown` = 头没带上，
  回查配置。或者简单调一次 `list_agents` 正常返回也行（连接通了，但看不到 machine 值）。
- 升级后如果 AI 提到"记忆没有 machine 字段"，说明用的还是旧注册，回来复查。
