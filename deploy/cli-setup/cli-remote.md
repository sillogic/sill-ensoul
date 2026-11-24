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
| Codex（desktop） | **B** | streamable-http 原生（config.toml `url`） |
| zcode | **C** | 原生优先，否则 `npx mcp-remote` 桥 |
| pi（1.x） | **E** | streamable-http 原生（`mcp.json`） |
| 其他任何 CLI | **D** | 原生 streamable-http 优先；不支持才用 `npx mcp-remote` 桥 |

> **口径（2026-11 修订）**：主力 CLI 现在都原生支持 streamable HTTP，**桥接不再是默认方案**——
> 桥多一层 node 进程、多一个失败点（见下面 `mcp-remote` 的三个已实测坑）。只有 CLI 确实
> 不支持 http 时才退回桥。
>
> 本节写法已在下列版本实测（2026-11-24）：Claude Code 2.1.292、Codex 0.153.4、pi 1.0.4、
> OpenCode 1.18.26、npx 11.6.2。版本低于这些的按「旧版回退」小节处理。

> **机器标识（所有节都要带）**：除 `Authorization` 外，每个请求还必须带
> `X-Machine-Id: <你的主机名>`（如 `X-Machine-Id: my-macbook`）。服务器靠它
> 在记忆里标注"这条是谁写的"（frontmatter `machine:` 字段），共享 KB 的读者
> 才能区分"谁写的"和"我在哪台机器"。不带则标 `unknown`。主机名获取：
> Windows `echo %COMPUTERNAME%`，macOS/Linux `hostname`。

> **mcp-remote 桥接公共参数（只有走桥的 C/D 与 B 的旧版回退才需要，缺了必踩坑，已实测）**：
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

## B. Codex（desktop）——原生 streamable HTTP

Codex 的 `[mcp_servers.*]` 支持直接写 `url`（streamable HTTP），**不要再用 mcp-remote 桥**。

1. 打开 `~/.codex/config.toml`，找到 `[mcp_servers.sill-ensoul]` 段，告诉我现在的内容。
   若已有旧注册（`command = "cmd"` / `npx mcp-remote ...`），先把整段**原样备份**
   （如 `~/.codex/sill-ensoul-mcp.backup.toml`），告诉我备份路径。
2. 把它改成原生形式 —— 注意 `url`、`startup_timeout_sec`（**秒**，不是旧桥写法里的 `_ms`）、
   以及 `http_headers` **子表**（两个头都在这里，不是 TOML 内联字符串）：

```toml
[mcp_servers.sill-ensoul]
url = "http://<服务器公网IP>:<端口>/mcp"
startup_timeout_sec = 60

[mcp_servers.sill-ensoul.http_headers]
Authorization = "Bearer <TOKEN>"
X-Machine-Id = "<你的主机名>"
```

   等价 CLI 写法（只解决 Authorization；自定义头仍需按上面补 `http_headers`）：
   `codex mcp add sill-ensoul --url http://<服务器公网IP>:<端口>/mcp`，
   或把 token 放环境变量、用 `bearer_token_env_var = "ENSOUL_MCP_TOKEN"` 代替明文头。
3. 校验：`codex mcp list` —— `sill-ensoul` 那行 `Url` 列是对的地址、`Status` 是 enabled、
   `Auth` 是 `Bearer token`；再确认 config.toml 是合法 TOML。

**已实测的四个坑**：
- **改完必须完全退出 Codex 再重开**（`config.toml` 只在启动时加载，不热更新）。
- **`codex mcp list` 里出现一个 `sill-ensoul` 子进程 ≠ 会话里能用**：判断标准只有「新会话里调 `list_agents` 是否返回服务端 KB 的 agent」。调不通就是没生效。
- **同一 name 不能同时存在 `command` 与 `url` 两种写法**：改造时把旧的 `command`/`args` 行整段删掉（备份留着），否则 TOML 解析或启动会出问题。
- **Windows 的 `cmd /c` 只是 stdio 旧写法需要的 PATH 兜底**，原生 `url` 用不到；别照抄进新配置。

<details>
<summary>旧版 Codex（不支持 <code>url</code>）的回退写法：mcp-remote 桥</summary>

```toml
# Windows（cmd /c 让 cmd.exe 解析 PATH —— Codex spawn 子进程时不保证走 shell）
[mcp_servers.sill-ensoul]
command = "cmd"
args = ["/c", "npx", "--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>", "--header", "X-Machine-Id: <你的主机名>"]
startup_timeout_ms = 15000
```

```toml
# Linux / macOS：去掉 cmd /c 两层
[mcp_servers.sill-ensoul]
command = "npx"
args = ["--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer <TOKEN>", "--header", "X-Machine-Id: <你的主机名>"]
startup_timeout_ms = 15000
```
</details>

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
3. **先判断你的 CLI 支不支持原生 streamable HTTP**（配置里能写 `url` / `type: http` / `--transport http`）：
   - **支持** → 直接写 `url: http://<服务器公网IP>:<端口>/mcp` + 两个 header（`Authorization: Bearer <TOKEN>`、`X-Machine-Id: <你的主机名>`）。这是首选。
   - **不支持** → 退回 stdio 桥：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --allow-http --transport http-only --header "Authorization: Bearer <TOKEN>" --header "X-Machine-Id: <你的主机名>"`，按你既有 stdio server 注册的写法放。
   server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件格式合法、结构正确；说明改了什么、备份在哪、走的是原生还是桥。

---

## E. pi（1.x 起原生支持 MCP）

**2026-10 起 pi 原生支持 MCP**（stdio + streamable HTTP），配置在 `~/.pi/agent/mcp.json`
（项目级 `.pi/mcp.json`，需 project trust）。**不需要写扩展、不需要 mcp-remote 桥。**

> 历史说明：pi 1.0 之前官方明说 "No MCP"，那时只能靠 `~/.pi/agent/extensions/mcp-bridge.ts`
> 这类扩展读 `settings.json.mcpServers`。本仓库旧版本各节写的就是那条路 —— 已过时。
> 若本机还装着旧扩展，**先移除/停用它**，避免和原生注册双开。

1. 看现状：`pi mcp list`（或会话内 `/mcp`）。告诉我现在已经注册了什么。
   有旧的 `mcp-remote` 桥注册就先记下来，改完要删掉。
2. 注册。CLI 写法（token 走环境变量，别写进配置）：

```bash
pi mcp add sill-ensoul --url http://<服务器公网IP>:<端口>/mcp \
  --bearer-token-env-var ENSOUL_MCP_TOKEN
```

   或直接写 `~/.pi/agent/mcp.json`（`headers` 支持 `${VAR}` 插值）：

```json
{ "mcpServers": { "sill-ensoul": {
  "url": "http://<服务器公网IP>:<端口>/mcp",
  "headers": {
    "Authorization": "Bearer ${ENSOUL_MCP_TOKEN}",
    "X-Machine-Id": "<你的主机名>"
  },
  "exposure": "direct"
} } }
```

   `exposure: "direct"` = 工具直接进模型上下文（和别的 CLI 里一样用）；不写则按 pi 默认策略。
3. 生效：会话内 `/reload`，或**完全退出 pi 再重开**（新服务器在启动/reload 时连接）。
4. 校验：`pi mcp list` 显示 `sill-ensoul` 已连接；会话里调 `list_agents` 能返回服务端 KB
   的 agent 列表。**注意**：`list_agents` 返回的是**服务端** KB 里的分身，本机不建本地 KB，
   不要期待本机有「默认分身」。

**已实测的坑**：
- 配置位置只在 `~/.pi/agent/mcp.json` 与 `.pi/mcp.json`（project trust 之后才读）——
  **不是** `settings.json`。往 `settings.json` 里写 `mcpServers` 不会生效。
- 手写 streamable-http 客户端（不给 pi 用、自己用 curl 验证）时握手必须串行：`initialize` →
  从响应头拿 `mcp-session-id` → `notifications/initialized` → 之后每个请求带 `Mcp-Session-Id`；
  响应体是 SSE（`event: message` + `data: {...}`），`Accept` 要带 `application/json, text/event-stream`。
- 旧扩展 + 新原生注册同时存在时，同名 server 会出现两套工具，模型会重复调用。

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
