# 任务：为远程 MCP 用户安装 sill-ensoul（CLI 接入）

> **你是哪种用户？先选对文件（SIL-8 文档拆分定案）：**
> - **本地直连 MCP**（本机 stdio，默认路径）→ 读 [`SETUP.md`](../../SETUP.md)。
> - **远程 MCP**（连服务器 / 接入卡用户）→ 读**本文件**（CLI 安装）。**连现成服务器不需要 clone 代码、不装本地包**——你手上只要有服务器地址 + token 就够了。
> - **原本地 → 切远程**（本机已用本地 stdio，改连现成服务器）→ 也读**本文件**：每节先备份旧注册再替换；本机旧本地 KB 会闲置（不删），或按 [`docs/deployment.md`](../../docs/deployment.md) KB 迁移节搬去服务器。
> - **远程 MCP 已装过，只缺机器身份头** → 读 [`update-machine-id.md`](update-machine-id.md)（给已有注册补 `X-Machine-Id`，SIL-9）。
> - **Multica 平台 agent**（前提：本机 CLI 已配好 MCP）→ 读 [`multica.md`](multica.md)。
> 五个文件各管一种场景，一份文件想写全反而难维护。

> ⚠️ **人类先读：别直接改这个文件！**
>
> 本文件在公开 git 仓库里。**不要在仓库内直接替换占位符**——填了真实 IP/端口/token 后，下次 `git add .` 提交就会把它带进历史并推送出去，等于公开泄露。
>
> 正确做法：**先把文件复制到仓库外，在副本上填值，粘贴完删除副本**：
> - Windows（PowerShell）：`Copy-Item deploy\cli-setup\cli-remote.md $HOME\cli-remote.md` → 改 `$HOME\cli-remote.md` → 用完 `Remove-Item $HOME\cli-remote.md`
> - Linux / macOS：`cp deploy/cli-setup/cli-remote.md ~/cli-remote.md` → 改 `~/cli-remote.md` → 用完 `rm ~/cli-remote.md`
>
> 副本在仓库目录之外，git 永远看不见它，物理上不可能被提交。下面这份文件里仍是占位符，供直接粘贴给 CLI。

你是本机 CLI。请帮我完成 sill-ensoul MCP 的**安装（远程接入）**：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 本文件做什么 / 不做什么

- **做**：把本 CLI 的 sill-ensoul MCP 注册指向远程服务器（8 个工具：list_agents / agent_index / wiki_* 等通过远程连接可用）。
- **不做**：不安装本地 Python 包、不建本地知识库（KB）、不创建 `alter-ego` 分身——**记忆和分身都在服务端 KB 里**，本机不产生本地副本。

## 目标服务器（已确认可连）

- MCP 端点：`http://<服务器公网IP>:<端口>/mcp`
- 鉴权头：`Authorization: Bearer <TOKEN>`（每个请求都带）

## 第一步：确认你是谁，只做对应那一节

下面 A–E 按 CLI 分节。先判断你自己属于哪一类，**只执行对应小节的步骤，其余小节直接忽略**；各节做完后再执行最后的「收尾」。

| 你是 | 走哪节 | 方式 |
|---|---|---|
| Claude Code | **A** | streamable-http 原生 |
| Codex（desktop） | **B** | `npx mcp-remote` stdio↔HTTP 桥 |
| zcode | **C** | `npx mcp-remote` stdio↔HTTP 桥 |
| pi | **E** | 扩展（pi 无原生 MCP；先看 E 节） |
| 其他任何 CLI | **D** | `npx mcp-remote` stdio↔HTTP 桥（通用） |

> **机器标识（所有节都要带）**：除 `Authorization` 外，每个请求还必须带
> `X-Machine-Id: <你的主机名>`（如 `X-Machine-Id: my-macbook`）。服务器靠它
> 在记忆里标注"这条是谁写的"（frontmatter `machine:` 字段），共享 KB 的读者
> 才能区分"谁写的"和"我在哪台机器"。不带则标 `unknown`。主机名获取：
> Windows `echo %COMPUTERNAME%`，macOS/Linux `hostname`。

> **mcp-remote 桥接公共参数（B/C/D 的 mcp-remote 命令都要带，缺了必踩坑，已实测）**：
> - `--allow-http`：mcp-remote 默认拒绝非 HTTPS 地址，裸 HTTP 端点必须显式加；
> - `--transport http-only`：默认 `http-first` 会先发一个假 initialize（`mcp-remote-fallback-test`）探测 SSE，再开第二个真 session，与 FastMCP 的 session 管理冲突 → 后续调用全部 `400 Bad Request: Missing session ID`；`http-only` 纯 POST 直连完全兼容。
> - `--header "X-Machine-Id: <你的主机名>"`：机器标识（见上面公共说明），每个 `--header` 一项，Authorization 和 X-Machine-Id 各自单独一个 `--header`。
> - 另外客户端握手必须串行：等 initialize 响应（session id 在响应头里）再发后续请求（自写测试脚本注意，正规 CLI 客户端如 pi 的 mcp-bridge 本身就是串行的）。

---

## A. Claude Code

1. 找到 sill-ensoul 的 MCP 注册。检查两处：① `~/.claude.json` 顶层 `mcpServers`（全局层）；② 当前项目 `.mcp.json` 顶层 `mcpServers`（项目层）。两处都可能存在 —— 告诉我你发现了几处、分别在哪个文件、现在的注册内容是什么。
2. 对每处**已有**注册，先把它**原样备份**（写到一个不会被 git 跟踪的位置，如 `~/.sill-ensoul-mcp-config.backup.json`），告诉我备份路径。没有旧注册则跳过本步。
3. 把 sill-ensoul 的注册设置成下面这个 streamable-http 形式（server 名保持 `sill-ensoul` 不变）：

```json
{ "mcpServers": { "sill-ensoul": {
  "type": "streamable-http",
  "url": "http://<服务器公网IP>:<端口>/mcp",
  "headers": {
    "Authorization": "Bearer <TOKEN>",
    "X-Machine-Id": "<你的主机名>"
  }
} } }
```

如果你的版本较老不支持 `streamable-http`，告诉我并改用 `"type": "http"`（或提示我先升级 CLI）。

4. 校验：确认改动后文件是合法 JSON、结构正确；逐处说明改了什么、旧值备份在哪。

---

## B. Codex（desktop）

1. 打开 `~/.codex/config.toml`，找到（或新增）`[mcp_servers.sill-ensoul]` 段。
2. 若已有旧注册，先把该段**原样备份**（如 `~/.codex/sill-ensoul-mcp.backup.toml`），告诉我备份路径。
3. 把该段设置成用 `mcp-remote` 桥接远程 HTTP（Windows 用 `cmd /c` 包一层，Linux/macOS 直接写）：

Windows：

```toml
[mcp_servers.sill-ensoul]
command = "cmd"
args = ["/c", "npx", "--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>", "--header", "X-Machine-Id: <你的主机名>"]
startup_timeout_ms = 15000
```

Linux / macOS：

```toml
[mcp_servers.sill-ensoul]
command = "npx"
args = ["--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>", "--header", "X-Machine-Id: <你的主机名>"]
startup_timeout_ms = 15000
```

4. 校验：确认 config.toml 是合法 TOML、段结构正确；说明改了什么、备份在哪。

---

## C. zcode

1. 找到 sill-ensoul 的 MCP server 注册 —— 通常在 `~/.zcode/cli/config.json` 的 `servers.sill-ensoul` 键下（以你的实际配置文件为准），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**（如 `~/.zcode/sill-ensoul-mcp.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册设置成「stdio 命令桥接远程 HTTP」：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --allow-http --transport http-only --header "Authorization: Bearer <TOKEN>" --header "X-Machine-Id: <你的主机名>"`，按你自己配置 schema 里注册一个 stdio server 的既有写法来放（Windows 下若命令名找不到，可加 `cmd /c` 包一层）。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件是合法 JSON、结构正确；说明改了什么、备份在哪。

---

## D. 其他 CLI（通用）

1. 找到本 CLI 里 sill-ensoul 的 MCP server 注册位置（你比任何人都清楚自己的配置放哪、什么格式），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**到不会被 git 跟踪的位置，告诉我备份路径。
3. 把 sill-ensoul 的注册设置成「stdio 命令桥接远程 HTTP」—— 这是任何 CLI 都通用的方式（不依赖各家对 http 的原生支持）：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --allow-http --transport http-only --header "Authorization: Bearer <TOKEN>" --header "X-Machine-Id: <你的主机名>"`，按你既有 stdio server 注册的写法放。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件格式合法、结构正确；说明改了什么、备份在哪。

---

## E. pi

**pi 没有原生 MCP 支持**（官方 README 明说 "No MCP"）——不读 `mcpServers` 配置，
A–D 全部不适用。pi 的自定义工具只能靠**扩展**（`pi.registerTool()`）。

1. 先检查本机有没有 sill-ensoul 扩展：`ls ~/.pi/agent/extensions/`，找 `mcp-bridge.ts`
   或 `sill-ensoul.ts`。**扩展文件不在本仓库**（仓库 CLI-agnostic，不发布 per-CLI 扩展）——
   如果本机没有，向你的 sill-ensoul owner 索取（从他已配置好的机器上复制），或按
   `expertise/pi-mcp-config-landing` 现写一个自包含 streamable-http 客户端扩展。
2. 扩展读 `~/.pi/agent/settings.json` 的 `mcpServers`。把 sill-ensoul 配成
   mcp-remote 桥（与 D 节相同，Windows 用 `cmd /c` 包一层）：

```json
{ "mcpServers": { "sill-ensoul": {
  "command": "cmd",
  "args": ["/c", "npx", "--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>", "--header", "X-Machine-Id: <你的主机名>"],
  "startupTimeoutMs": 60000
} } }
```

   （macOS/Linux 去掉 `cmd` `/c` 两层即可。若扩展是自包含 HTTP 客户端而非 stdio 桥，
   改在扩展自己的配置里加 `X-Machine-Id` header。）
3. 扩展装好 + 配置写好后，**完全退出 pi 再重开**（扩展在 session_start 加载）。
4. 校验：会话里调 `list_agents` 能返回服务端 KB 的 agent 列表 = 成功。

---

## 薄壳（可选但推荐）

上面只装了工具；要让本 CLI 学会 ensoul 工作流（唤醒分身 / 检索记忆 / 蒸馏沉淀），把
[`ensoul/SHELL.md`](../../ensoul/SHELL.md) 的规则内容 **append**（不覆盖）进本 CLI 的
指令文件（Claude Code 的 `~/.claude/CLAUDE.md`、zcode 的 `~/.zcode/AGENTS.md`、pi 的
`~/.pi/agent/AGENTS.md` 等，按你自己的机制）。已有 `<!-- SILL-ENSOUL-SHELL-START -->`
定界标记则说明已装过，跳过。
> 远程接入不装本地包，所以**不用** `sill-ensoul-init --print-shell`——直接从
> `ensoul/SHELL.md` 取内容即可。
> **没有仓库访问权？** 把 `ensoul/SHELL.md` 的完整内容也粘贴给我（或让文件提供方
> 发你一份），我把它 append 进指令文件——引用路径 `../../ensoul/SHELL.md` 是仓库内
> 相对路径，我这边解析不到，必须有正文。

---

## 收尾（所有 CLI 都做）

- **必须完全退出本 CLI 再重新打开**，新会话才会用新配置（配置启动时加载，不热更新）。
- 重启后在会话里调 `agent_index` / `wiki_search` 能通 = 接入成功。验证以**当前注册指向的
  服务端**实际返回为准——`list_agents` 返回的是服务端 KB 里的现成分身（alter-ego /
  ensoul-dev 等），不要期待本机有 alter-ego（本机不建本地 KB）。
- 不要把 token / IP / 端口写进任何会被 git 提交的文件：填了真实值的提示词文件一律在**仓库外的副本**上改（见文件开头），用完删除。
- 顺序别反：先确认服务器服务在跑（`curl` 返回 401）、KB 已迁移，再配客户端。
- 配好 CLI 后，如果还要接入 Multica 平台，用你手里的另一份文件（`multica.md`，Multica 初始化）。
