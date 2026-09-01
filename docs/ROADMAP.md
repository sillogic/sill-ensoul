# ROADMAP — 设计决策与已解决问题

> 这是一份**活文档**，记录 sill-ensoul 在落地"与 CLI、模型供应商解耦的长期记忆系统"过程中的设计决策、已解决问题与已知限制。
>
> 阅读顺序：§1（设计原则）→ §2（设计决策 D1-D12）→ §3（已解决问题清单）→ §4（当前状态）。

---

## 1. 设计原则

**目标**：一套与 CLI、模型供应商都解耦的多智能体系统。每个 agent 自带长期记忆（OKF Wiki），跨会话、跨项目累积经验——**一个 agent 处理的同类型项目越多，记忆越充分，能力越强**。

支撑这个目标的几条**设计原则**：

1. **记忆 = 文件（OKF），不是平台内部状态。** 可 git、可 diff、人可读、跨 CLI/模型通用。
2. **引擎 = 轻量 MCP server，只管数据/工具，不碰推理。** 自动满足"模型供应商无关"。
3. **记忆范围是"角色作用域"，不是"项目作用域"。** 这是相对现有 CLI（均以项目为单位、无跨项目记忆）的核心差异化——也是整个项目存在的理由。
4. **越用越强 = 规模红利。** 这条把成败压在"记忆增长"上，因此任何**随规模退化**的东西都是直接威胁（见问题 #1）。

> 多 agent 协作走**编排者模式**（D6）：任何 agent 都能用 `wiki_*` 工具操作其他 agent 的记忆，无需自治协商基础设施。

---

## 2. 设计决策（D1-D12）

### D1 — 服务形式：MCP 作主接口，核心保持 MCP 无关

- MCP 是当前最佳的"LLM 工具调用"主接口：各目标 CLI（Claude Code / Codex / Cursor / zcode / OpenCode）通吃，一次实现多处用，结构化参数优于文本解析。
- **但 MCP 不能是唯一通路。** 关键纪律：**逻辑只进 `okf.py`；`server.py` 永远只做透传，不塞逻辑。** 这样未来可加 `cli.py`（二进制，最大可移植）而不碰核心；`http.py`（远程 / 多 CLI 共享实例）已实现（D11，同样是新增适配器，核心未动）。
- 现状已符合：`okf.py` 头部声明 *"pure logic and has no MCP dependency"*，`server.py` 是薄 FastMCP 适配层。**保持即可，不要破坏。**
- 备选评估：HTTP/REST（CLI 不原生调，与 MCP 重复）、CLI 二进制（可移植但文本需解析）、纯文件（零依赖但写入易错）——均不如 MCP 适合本用途。

### D2 — 适配层三层分离（保证 CLI 可移植）

| 层 | 职责 | CLI 相关性 | 现状 |
|---|---|---|---|
| (a) 引擎 | 读写检索 OKF | CLI 无关 | ✅ 已做到 |
| (b) persona + workflow | "何时召回/沉淀"的工作流内容 | **CLI 无关，只写一次** | ✅ 已落地（`WORKFLOW.md`） |
| (c) 触发壳 | 怎么在某个 CLI 里触发 | 每 CLI 一份，薄 | ✅ 已落地（`AGENTS.md` / `CLAUDE.md`） |

- **可移植杠杆**：workflow 内容 (b) 写一次（纯 markdown），每个 CLI 的壳 (c) 只**引用**它，不内联。工具调用词（`agent_index`/`wiki_search`...）本来就跨 CLI 一致（同一 MCP server），真正每 CLI 不同的只有"怎么触发"。
- 落地方式：把 workflow 写在一个共享文档（`WORKFLOW.md`），zcode 的 `AGENTS.md` / Claude Code 的 `CLAUDE.md` / Codex 的 skill 都指向它，各自只改壳。

### D3 — 记忆范围：角色作用域，非项目作用域

- 一个 agent = 一个 OKF bundle = `knowledge/agents/<id>/`。记忆跨所有项目累积，不绑定任一项目仓库。
- 见问题 #4：KB 物理位置曾与此理念冲突，已通过全局 KB 修复。

### D4 — skill 调度：agent 是 skill 的推荐者，非拥有者（纯文档驱动）

- **skill = 各 CLI 市场里那种可安装的能力包**（如 document-skills:pdf、frontend-design）。agent **不拥有 skill**，只积累**"使用 skill 的经验"**——用过、觉得好、记下来、下次推荐。存为普通 OKF concept（`type: Reference`，id 形如 `expertise/skill-<名字>`），记：这个 skill 是什么 / 何时推荐用 / 实操判断（非文档原文）。
- **调度规则**（见 WORKFLOW.md §3）：接到任务→检索 skill 经验→命中则推荐"用 X skill"→**判断当前环境有没有**：有用、没有就提醒用户自己装。**不代装、不探测、不猜**；只有真正用过且好用才沉淀。不记每个 CLI 怎么装（那是用户的事，各 CLI 自己引导）。
- **为什么这样设计**：① skill 是 CLI 的，"用 skill 的经验"是 agent 的记忆，两者解耦，契合"纯文档外挂"哲学（零代码）；② 去掉自动安装/探测 = 守住安全边界，也让规则极简。
- **状态**：✅ 已落地。规则在 WORKFLOW.md §3 + 各 CLI 薄壳。

### D5 — 不做模板继承（被否决的决策）

曾考虑引入"模板"概念：所有 agent 基于模板创建，模板含 persona + 技能列表（除记忆外所有内容），更新模板相当于更新所有基于其创建的 agent。**否决，不做。**

**否决理由**（4 条代价，前两条违背核心原则）：

1. **破坏 bundle 自包含性**。sill-ensoul 根基之一——"记忆 = 文件，可 git/diff/人可读"，Obsidian 打开 `agents/<id>/` 就懂这个 agent 的一切。继承模型下完整人格 = 模板 + agent 覆盖层，不再自包含。`git diff` 一个 agent 看不出模板变更的影响，但 agent 行为变了——审计断链。
2. **违背 D3 角色作用域核心原则**。D3 是项目存在的理由。共享人格的多 agent = "同角色多实例"，记忆隔离意义变弱，滑向项目作用域。更微妙：若模板只承载共性、agent 各有专长，那"更新模板更新所有 agent 人格"会覆盖 agent 自己演进出的人格微调——而"越用越个性化"正是原则 4"越用越强"的体现。模板"拉回基线"与此相悖。
3. **引入 OKF 没有的继承机制**。OKF 哲学是扁平、一个 concept 一个文件、文件路径 = 身份。继承是规范外扩展：要自定义模板格式、合并规则、覆盖优先级；搜索/索引要重新考虑；`agent_index` 要合并模板 + agent 暴露。
4. **与 D4 直接冲突**。D4 明确"skill 经验是 per-agent 记忆，不共享"。模板要"技能列表共享"，冲突。

**替代方案**：痛点"创建标准化/关注点分离"用**原型/拷贝语义**（create_agent 时从模板复制 persona，之后 agent 独立演进）即可解决，几乎不破坏哲学。默认 agent alter-ego 的"分裂"机制就是这个思路。只有"批量更新共性 persona"才真正需要继承，但当前 agent 规模下是假需求——等"十几个同族 agent、频繁改共性 persona"的痛点真实出现再上继承，届时设计有据。

**结论**：继承的全部代价换的是"批量更新共性"一个收益，而该收益现在还是假需求。继承违背 D3 这条核心原则，不值。

### D6 — 多 agent 协作：编排者模式，废弃自治协商（Phase 2 已废）

- **决策**：多 agent 协作走**编排者模式**——任何 agent 都能用现有 `wiki_*` 工具（`wiki_write_concept(agent_id=...)` / `wiki_read` / `wiki_search`）操作**其他** agent 的记忆。编排者（人或任一 agent）直接决定写谁的记忆、把结论分发给谁。
- **废弃的 Phase 2**：原设计的 `registry`（所有权声明）+ `boundary_scan`（冲突检测）+ `comm` 协商 + `boundary_record`（契约）全部删除。它们是为"agent 自治协商边界"设计的，但本项目是"编排者主导"模型，用不上——编排者知道在干什么，不用所有权声明防冲突。
- **为什么废弃**（三个场景触发反思）：
  1. "让 agent A 更新 agent B 的记忆" → 现有 `wiki_write_concept(agent_id=...)` 直接能做，不需任何 Phase 2 设施。
  2. "规划完分发给两个 agent" → 编排者直接 `wiki_write_concept` 到各方记忆即可，不需 comm 消息层。
  3. "唤醒新 agent 交流" → 通过记忆文件"留言"（写 concept 给它/读它的 concept）即可，不需实时对话——agent 本就不是常驻进程。
- **与项目哲学一致**：agent 是"被唤醒才活、记忆跨项目累积"的角色，不是自主运行实体。"agent 自治协商"和这个模型有张力（没常驻进程怎么协商？）。编排者模式反而贴合："编排者用工具操作多 agent 记忆"。
- **状态**：✅ 已落地。`registry.py`/`comm.py`/`test_phase2.py` 已删，server.py 的 6 个 Phase 2 工具已移除。工具数 14→8。

### D7 — 无 per-agent `workflow/` 文件夹；全局 `WORKFLOW.md` 是唯一工作流权威源

- **决策**：**不在每个 agent bundle 内建 `workflow/` 文件夹**。所有 agent 共享一份全局 `WORKFLOW.md`，定义"何时唤醒/检索/引用/沉淀/skill 调度"等 CLI 无关规则。各 CLI 的薄壳（`AGENTS.md` / `CLAUDE.md`）只引用它，不内联。
- **为什么否决 per-agent workflow**：
  1. **违反单一真相源**。工作流是"所有 ensouler 通用的协作协议"，不是某个 agent 的私有记忆。一旦每个 agent 都有 workflow 副本，改一条通用规则要改 N 处，必然漂移。
  2. **与 D2 三层分离冲突**。workflow 属于 (b) 层（CLI 无关、只写一次），把它拆进每个 agent bundle 等于把 (b) 层混进 (c)/记忆层。
  3. **与 OKF  bundle 自包含哲学冲突**。agent bundle 应该只装"这个角色知道什么"（经验、项目、playbook），不该装"系统怎么运转"的元规则。
- **如果某个 agent 真的需要专属流程怎么办**：把它写成普通 OKF concept，type 用 `Playbook`（OKF SPEC 4.1 示例类型之一），放在 `playbooks/<name>.md`。这既是 agent 的私有经验，又完全合规，还能被检索。例如 `playbooks/code-review.md`。
- **状态**：✅ 已决策，不添加 per-agent workflow 文件夹。

### D8 — OKF 合规性：bundle 内 extra markdown 文件是否可接受

经对照 [OKF SPEC](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) 审查：

| 文件 | OKF 定位 | 我们的处理 | 结论 |
|---|---|---|---|
| `index.md` | 保留文件名（SPEC 3.1），目录清单 | 每个 agent 创建，无 frontmatter，用于知识地图 | ✅ 完全合规 |
| `log.md` | 保留文件名（SPEC 3.1），变更历史 | 每个 agent 创建，按日期分组追加 | ✅ 完全合规 |
| `AGENT.md` | 非保留文件名 → SPEC 3.1 规定"其余 `.md` 都是 concept 文档" | 我们把它作为 `type: Profile` 的 concept，但引擎额外按文件名排除在搜索/concept 清单外（H7），只通过 `agent_index()` 暴露 persona | ✅ 合规：OKF 允许 producer-defined type 与扩展 key；`Profile` 是有效的自定义类型。排除它是引擎实现细节，不影响文件格式合规。 |
| `.fts/index.db` | 非 markdown，OKF 未涉及 | SQLite FTS5 派生索引，`.md` 是唯一权威源 | ✅ 不影响 OKF 合规 |

- **关键引述**：OKF SPEC 3.1 只保留 `index.md` / `log.md`；4.1 明确"Producers MAY include any additional keys"，消费者"MUST tolerate unknown types gracefully"。因此 `AGENT.md` 作为带 `type: Profile` 的 concept 是合法扩展。
- **状态**：✅ 已确认合规，无需重构文件结构。

### D9 — 并发写锁：SQLite 互斥量（三平台同一份代码）

### D10 — 升级方式：意图文件 + pip + 标记同步，KB 永不触碰

- **问题**（SIL-28）：没有标准升级路径。只有首次安装（GitHub 下载源码 → 把 SETUP.md 拖进 AI 对话框 → 按文档装）。发新版后用户只能重来一遍，且重跑 SETUP.md 会**重复追加薄壳块**（它教的是"append, don't overwrite"）。
- **决策**：升级 = 两个独立部分，各走已有的成熟机制：
  1. **包代码** → pip（GitHub 路由：`pip install -U git+...`；editable clone 路由：`git pull` + 重跑 `pip install -e`）。
  2. **薄壳规则** → 复用既有 `--sync-shell`（定界标记**原位替换**，不重复、自动备份）——这是 `SHELL.md` 改版后让各 CLI 指令文件跟上来的唯一机制。
  3. **KB 是用户数据，永不触碰**；FTS schema 变更由运行时 `PRAGMA user_version` 自动迁移（已有机制）。MCP server 注册指向 `sill-ensoul-mcp` 命令，跨版本存活，只在验证失败时才重注册。
- **落地物**：新增 `UPGRADE.md`（与 SETUP.md 同模式的机器可读意图文件：两步升级 + 验证 + 注意事项 + 事后报告模板）；`sill-ensoul-init --version`（比对已装 vs 仓库版本的原语）；SETUP.md 补"已装过就进 UPGRADE.md"指针 + 定界标记重复追加防护；README 升级一节。
- **为什么不做 `sill-ensoul-upgrade` 自动升级脚本**：① pip 自我升级脆弱（进程内升级正在跑的包，Windows 上容易踩文件锁）；② 与项目哲学冲突——SETUP.md 已确立"CLI 的 AI 用自己当前的配置机制自理环境"，升级同样交给它；③ 版本检查需要网络（GitHub API），与项目离线友好的定位不符。用户那句"从 UPGRADE.md 升级"与"从 SETUP.md 安装"摩擦等价，但升级内容明确、安全边界清楚。
- **状态**：✅ 已落地（SIL-28，v0.2.3+）。

- **决策**：`okf.py` 加 `_agent_lock` context manager，用 SQLite 的 single-writer 事务（`BEGIN IMMEDIATE`）做 per-agent 跨进程互斥量，包住 `append_log` 读改写 / `write_concept` / `_sync_agent_index`。锁文件是**专用**的 `<agent_dir>/.lock.db`，永不被 `os.replace`。
- **为什么 SQLite 而不是 fcntl/msvcrt**：项目承诺平台无关（win/linux/mac）。`fcntl.flock` + `msvcrt.locking` 双路径是两套代码、两套测试，且 msvcrt 有"锁已存在字节/打开模式/10 次重试"的坑（ROADMAP #12 旧注记）。`sqlite3` 是 stdlib、项目已在用（FTS5），`BEGIN IMMEDIATE` 的 RESERVED 锁在三平台天然就是跨进程互斥量，进程崩溃由事务恢复 + OS 文件锁释放兜底，锁不会残留。锁的代码不需要知道平台是谁 —— 这才叫平台无关。
- **锁必须加在专用文件上（坑）**：`append_log`/`write_concept` 用 `os.replace` 换目标 inode —— 如果锁加在被写的文件上，第二个进程会锁新 inode，与第一个进程的旧 inode 锁互不相斥，两个进程同时进临界区，锁白加。
- **两层各管一件事**：锁管**串行**（不丢更新），`_atomic_write_text` 管**崩溃**（不留半截文件）。`_sync_agent_index` 也要包：SQLite busy_timeout 默认 0，两进程同时 sync 同一 `index.db` 会报 `database is locked`。
- **状态**：✅ 已落地。确定性语义测试（`tests/test_concurrent.py` A1/A2：持锁期间争抢必须 OperationalError、释放后立即成功）+ 并发压力测试（B3：N 进程并发 append 断言日志条数 = N；B4：并发写同一 concept 不撕裂）。

### D11 — 远程部署：HTTP transport + Bearer token 鉴权（SIL-7，单租户先行）

- **问题**（SIL-7）：要在云服务器上部署 MCP，先要解决「谁能连」——鉴权。stdio 只走本机
  管道，天然私密；HTTP 一上公网/tailnet，谁拿到地址谁读全部记忆就不成立。多租户
  （SIL-8，数据层「连上来后看哪份记忆」）与鉴权正交，另卡跟踪，不在本次范围。
- **决策**：新增 `ensoul/http.py` = Streamable HTTP 适配器，复用 `server.py` 的同一批
  工具 callable（8 工具定义一次，D1 保持：transport 是适配器不是重构）。外层包 Bearer
  鉴权中间件，先于路由执行：
  - 静态 token 来自 env `ENSOUL_MCP_TOKEN`；未配置 → 拒绝启动（fail-closed：无鉴权的
    远程 server 正是 SIL-7 要消灭的）。
  - 每个请求必须带 `Authorization: Bearer <token>`，否则 401（未知路径同样 401，不泄露
    端点）；常量时间比较（`hmac.compare_digest`）防时序侧信道。
  - FastMCP 默认的 DNS rebinding 防护只放行 localhost Host，远程 IP/域名会被 421 ——
    显式关闭：Bearer 门禁先于路由对每个请求执行，rebinding 攻击者拿不到 token 也
    没用；传输层安全交给部署形态（Tailscale/防火墙）。
  - **单租户先行**：一个 token = 一个身份（owner）→ 一个 KB 根（`ENSOUL_KB`/平台默认，
    `okf.kb_root()` 已可注入）。留「身份 → KB 根」映射口子（`_identity_for_token` /
    `_kb_root_for_identity`）：SIL-8 只是加映射表，鉴权协议与工具层零改动 —— 构造覆盖，
    不提前写代码。
  - stdio（`sill-ensoul-mcp`）不加鉴权：本机管道天然私密，加了反而破坏现有注册。
- **命令**：`sill-ensoul-http [--host H] [--port P]`（env 覆盖 `ENSOUL_MCP_HOST` /
  `ENSOUL_MCP_PORT`，默认 0.0.0.0:8930）。uvicorn 是可选 extra（`pip install
  "sill-ensoul[http]"`），stdio 安装保持零额外依赖。
- **测试**：`tests/test_http_live.py`（fail-closed + 401 门禁 + 真实 uvicorn/官方 MCP
  client 端到端），已纳入 `run_tests.py`。
- **依赖约束**：`pyproject.toml` 钉 `mcp>=1.2,<2`。mcp 2.x 把 `FastMCP` 改名 `MCPServer`、
  删掉 `mcp.server.fastmcp` 模块，http.py/server.py 都按 1.x API 写（SIL-7 部署现场踩到：
  新装拉到 mcp 2.x，`sill-ensoul-http --help` 直接 ModuleNotFoundError）。迁移到 mcp 2.x 是
  后续任务：改用 `mcp.server.mcpserver.MCPServer` + 核对 streamable HTTP/鉴权中间件 API
  差异，迁移完再放开上界。
- **状态**：✅ 已落地（SIL-7，v0.4.0）。

### D12 — 多租户用户管理：一个 token = 一个用户 = 一个隔离 KB 根（SIL-8，方案 A）

- **问题**（SIL-8）：多用户共用同一个服务器的 MCP 服务时，需要用户隔离（数据层「连上来后看哪份记忆」）+ 用户管理。鉴权（SIL-7/D11）是连接层「谁能连」，多租户是数据层，正交但依赖前者的 token 协议。用户明确要求：**不做开放注册**（私有/小团队定位），admin 创建用户并**分发 md 接入卡**，用户拿到丢给 CLI 即完成接入。
- **决策**：
  - **用户模型**：一个用户 = 一个 Bearer token → 一个身份 → 一个隔离 KB 根（`base/tenants/<user_id>/`）。MCP 客户端只认 `Authorization: Bearer` 头，无登录/密码概念 → 不做注册流/密码体系；用户管理本质 = 映射表 `token → 身份 → KB 根`。
  - **用户表**：`base/users.json`（base 根上，故意不在任何 tenant 根内 —— tenant 读不到也写不到它）。存 `user_id → name + token_hash(sha256) + enabled + created_at + note`；**token 只存哈希**，明文只在 create/reset 时展示一次（文件泄漏 ≠ 凭据泄漏；支持吊销/重置）。
  - **admin 形态（用户拍板：方案 A）**：零 UI 的 `sill-ensoul-admin` CLI（`user create/list/revoke/enable/reset`），在服务器上跑；B（`/admin/*` 端点 + 静态页）作为 A 的薄壳包装，随时可加。create/reset 同时生成**md 接入卡**（见下）。
  - **鉴权两路**：owner token（env `ENSOUL_MCP_TOKEN`，SIL-7）→ 身份 `owner` → base 根（**向后兼容**，存量部署零改动）；用户 token → 查表 → `user_id` → `base/tenants/<user_id>/`。吊销即时生效（每次请求现查表，无进程内缓存，无需重启）。
  - **工具层唯一改动**：`okf.kb_root()` 从进程级全局解析改为按请求身份解析 —— HTTP 中间件鉴权通过后把身份注入 contextvar（`okf.request_identity`），请求结束还原；stdio（`sill-ensoul-mcp`）/admin CLI/测试无身份 → 解析到 base 根，行为逐字节不变。8 个工具零改动（D1 继续成立：transport 是适配器）。anyio 的 `to_thread` 会拷贝当前 context，同步工具 handler 也能看到身份。
  - **接入卡 = SIL-35 自识别分节模式的复用与扩展**：单文件，A Claude Code / B Codex / C zcode / D 其他 CLI + **E Multica**（平台 agent：先按 A–D 装工具，再按 `ensoul-multica-binding` 规则 `list_agents` 匹配绑/建分身，工具不热加载的当前 run 按降级规则先干活）。真实 URL+token 在生成时填入；**卡含活 token，必须留在仓库外**（CLI 默认写到 cwd 并打印警告；不入 git、不走公开渠道，公网必须 TLS）。
- **附带收益**：隔离在 KB 根层 → 两个租户可各有同名 agent（都是 `ensoul-dev`）不冲突；多机命名规则（分身id@机器）在租户内部照旧。
- **边界**：用户表是 admin 单写者（服务器上一个管理员操作），读改写 + 原子写足够，不复用 D9 per-agent 锁；并发 admin 操作最后写者胜，小团队可接受。
- **状态**：✅ Phase 1 已落地（用户表 + admin CLI + md 接入卡 + http 口子打通 + tenant 隔离端到端测试）。Phase 2 待办：B 形态薄页面、租户 onboarding/迁移工具、`user delete`（当前 revoke 即等效禁用，不删数据）。

---

### D13 — 机器身份：连接的固有属性，记忆自动打标（SIL-9）

- **问题**（SIL-9，mac 冷启动接入 pi 后暴露）：多台机器通过远程 MCP 共享**同一份** KB 后，记忆正文里的「本机/这台机器」成了悬空相对词——写入时指写机器，跨机读取时模型会误当成读机器（在 Windows 上读到 mac 写的「本机 macOS 实装」会拿 mac 的状态冒充当前机器）。根因是双重的：① 会话里「我在哪台机器」这个环境事实不可见；② 记忆没有「写机器」元数据。修文档、修规范都是打地鼠，根治 = 让读机器和写机器都成为运行时事实。
- **决策（连接级机器身份，一次落地永久受益）**：
  - **协议**：客户端每个请求带 `X-Machine-Id: <hostname>` 头（与 `Authorization` 并列）。服务器中间件解析 → contextvar `okf.request_machine`（与 SIL-8 的 `request_identity` 同款口子，零重构）。**缺失 → `unknown`，绝不 fallback 服务器自身 hostname**（那会标成错的机器）；stdio（本机 sill-ensoul-mcp）无 HTTP → fallback `socket.gethostname()`（本地写即本机写，语义正确）。
  - **写入自动打标**：`wiki_write_concept` 自动在 frontmatter 加 `machine:` 字段（在 extra 之后写入，**权威、不可伪造/覆盖**）；`wiki_append_log` 的 entry 也带 `(machine: <m>)`。写作者零负担，不需要自觉。
  - **读机器常驻可见**：机器名是客户端本地事实，由本地注入最可靠——薄壳生成器（`--print-shell` / `--sync-shell`）在 SHELL 顶部注入 `<!-- SILL-ENSOUL-MACHINE -->` banner（`**Current machine**: <hostname>` + 语义解释），模型每会话必读薄壳 → 永远知道自己在哪台。SHELL.md 加 Machine awareness 规则（「本机」= 写机器 frontmatter.machine，不等于当前机器）。
  - **闭环**：`frontmatter.machine (@mac)` ≠ `current machine (@zzj-hj-lp)` → 记忆里的「本机」指 mac，不是当前这台的。歧义在机制层消解，不靠模型聪明。
- **落点**：`okf.py`（machine ctx + 打标）/ `http.py`（X-Machine-Id 解析 + unknown fallback）/ `init_cmd.py`（banner + print/sync 注入）/ `SHELL.md`（规则）/ `cli-remote.md`（全节 X-Machine-Id + 新 E 节 pi）+ 各 CLI 客户端配置加一个 header。
- **迁移**：已接入机器各补一个 header（本机 settings.json 已加，重启生效；mac 自包含扩展待补）；新接入靠 cli-remote.md 自动带。旧记忆无 machine 字段 → 靠 banner 当前机器 + 记忆上下文推断，可接受，不重写。
- **关联**：与 SIL-7/8 同构（身份=连接属性，机器=连接属性）；补上 remote-mcp-tailscale-plan 多机命名规则只覆盖「实例名」没覆盖「记忆正文」的空缺。
- **状态**：✅ 已落地并测试（stdio→hostname / HTTP header→frontmatter / 缺失→unknown 三路断言全绿）。

---

## 3. 问题清单

> 状态图例：🔴 曾阻塞核心承诺 · 🟡 曾影响质量但不阻塞 · 🟢 已知限制 / 已决策
> 字段：问题 → 解法 → 教训

### 已解决的问题

| # | 问题 | 解法 | 教训 |
|---|---|---|---|
| #1 ✅ | 检索质量随规模退化（子串计数无分词） | `fts.py` SQLite FTS5 + BM25；CJK 索引端按字分词（`_segment_for_index`），查询端同步分词，零依赖 | 规模红利命门；FTS 表 title 被分词污染 → `search` 用原始 concept title |
| #2 ✅ | 记忆"长"靠蒸馏，人会懒得记 | 自动 + 事后告知（纯文档）：agent 主动判断时机 + 提炼 + 直接写入，写后告知用户（保留事后否决） | **自动 + 告知是终态设计，非待办**——写前确认经评估改为写后告知（触发条件已明确到 agent 能判定，写前问大概率走形式）；全自动 sleeptime 经评估否决（LLM 产垃圾稀释检索，撞 #1；有状态后台子系统与"被唤醒才活"哲学冲突） |
| #3 ✅ | 适配层缺失，CLI 不可移植 | D2 三层分离落地：WORKFLOW.md（CLI 无关）+ 各 CLI 薄壳 | 工具调用词跨 CLI 一致，每 CLI 不同的只有"怎么触发" |
| #4 ✅ | KB 在项目仓库内，违背跨项目理念 | `_default_kb_root()` 平台感知全局默认（Win `%LOCALAPPDATA%/ensoul/knowledge`） | 跨项目 agent 的记忆不该属于任一项目 |
| #5 ✅ | Phase 2 测试不可重复运行（registry 状态污染） | Phase 2 整体废弃（D6），相关测试随之删除 | 自治协商模型与项目哲学不符，测试问题随之消失 |
| #6 ✅ | `wiki_read` 因 datetime 序列化崩溃 | `server.py` 的 `_dump` 加 `_json_default`，datetime→ISO 字符串 | D1 价值兑现：bug 定位在壳层，核心无辜，3 行修好 |
| #7 ✅ | persona（AGENT.md）污染搜索与 concept 清单 | `EXTRA_NON_CONCEPT = {"agent.md"}`，`_iter_concepts` 排除 | persona 不该进检索索引 |
| #8 ✅ | 缺 MCP 工具返回值契约测试 | `run_tests.py` 纳入测试，自建临时 KB | 测试不依赖 repo 预存数据（#4） |
| #9 ✅ | server 绑死 cwd | `pyproject.toml` 定义 `sill-ensoul-mcp` 控制台命令 + `pip install -e .` | 任意 cwd 直接 `sill-ensoul-mcp` |
| #10 ✅ | 三场景规则（自我认知/项目查询/身份保持） | 写入 WORKFLOW.md §1.1/§2.1/§2.2 | 身份保持是"软身份"换"CLI 无关"的代价，缓解不完美 |
| #11 ✅ | search/agent_index 每次查询全量读文件 | 扩展 FTS `meta` 表缓存 title/desc/tags/type/body_preview；查询走索引，未变更文件不读 | 保持 OKF 文件为唯一权威源；`.fts/index.db` 是派生索引 |
| #12 ✅ | 并发写同一 agent 丢数据（append_log 读改写丢失 / 同 concept 后覆盖先） | D9 `_agent_lock`：SQLite 互斥量（per-agent `.lock.db`，`BEGIN IMMEDIATE`，三平台同一份代码）串行化 append_log/write_concept/_sync_agent_index；原子写保留（锁管串行、原子写管崩溃）；`tests/test_concurrent.py`（确定性互斥语义测试 + N 进程并发 append 断言条数=N） | 锁必须加在永不被 replace 的专用文件上；SQLite single-writer 天然是跨平台互斥量，无 fcntl/msvcrt 分支 |

### 已知限制（不修，已决策）

#### #13 — 🟢 server.py 工具数增长后应按职责拆分

- **现状**：`server.py` 8 个 `@mcp.tool` 平铺，Phase 1（8 个 wiki/agent 工具）都在。
- **何时该拆**：工具数超过 ~15，或出现新的工具组（如未来加记忆压缩、向量化等）。
- **怎么拆**：`server.py` 留 FastMCP 实例 + main() + 共享 `_dump`；工具按组进 `tools_wiki.py` 等，通过 FastMCP 的跨模块注册机制挂到 mcp。
- **为什么不修**：8 个工具 119 行，没到痛；拆要验证 FastMCP 跨模块注册机制，有不确定性；现在拆是过早优化。

---

## 4. 当前状态

| 序 | 项 | 动作 | 结果 |
|---|---|---|---|
| ~~1~~ | ~~#6/#9/#4~~ | ✅ 已修 datetime / cwd / KB 位置 | 三轮测试逐个修复，server 可发布 |
| ~~2~~ | ~~#3~~ | ✅ 已修 适配层（WORKFLOW.md + 各 CLI 薄壳） | 唤醒/检索自动触发，可移植架构立住 |
| ~~3~~ | ~~#1+#7~~ | ✅ 已修 FTS5 检索 + persona 排除 | 规模红利命门解决，11 项回归锁定 |
| ~~4~~ | ~~#8~~ | ✅ 已修 测试套纳入 run_tests.py | 防壳层 bug 回归 |
| ~~5~~ | ~~#2~~ | ✅ 自动沉淀已落地（auto + notify-after，纯文档驱动） | 解决"懒得记"，守住质量门禁；**全自动 sleeptime 已否决，auto + notify-after 是终态设计** |
| ~~6~~ | ~~**改名**~~ | ✅ 代码层统一为 sill-ensoul | 包名 `sill-ensoul`、命令 `sill-ensoul-mcp`/`sill-ensoul-init`、目录 `ensoul/`、环境变量 `ENSOUL_KB`、KB 路径 `ensoul/knowledge` |
| ~~7~~ | ~~**GitHub 发布**~~ | ✅ 已推 github.com/sillogic/sill-ensoul | v0.1.0 tag 已打，首个公开版本上线 |
| ~~8~~ | ~~**#12**~~ | ✅ 已修 并发写（okf.py SQLite 互斥锁 D9 + tests/test_concurrent.py） | 跨进程写同一 agent 不再丢更新；三平台同一份代码；确定性语义测试防回归 |
| ~~9~~ | ~~**SIL-28 升级方式**~~ | ✅ 已落地 标准升级路径（UPGRADE.md + `--version` + `--sync-shell` 复用） | 升级 = 包 + 薄壳两部分；KB 永不触碰；不做自升级脚本（D10） |
| ~~10~~ | ~~**SIL-7 MCP 鉴权**~~ | ✅ 已落地 远程 HTTP 部署（`ensoul/http.py`：Streamable HTTP + Bearer token，单租户 fail-closed，多租户留「身份→KB 根」映射口子） | 鉴权 = 连接层「谁能连」，与多租户正交；多机实例命名改为「分身id@机器」；D11 |
| ~~11~~ | ~~**SIL-8 多租户 Phase 1**~~ | ✅ 已落地 用户表 + admin CLI + md 接入卡（`ensoul/users.py` + `sill-ensoul-admin`，token 只存哈希；owner token 向后兼容；http 口子打通；tenant KB 根隔离端到端测试） | 工具层仅 `okf.kb_root()` 按 contextvar 身份解析一处改动；接入卡复用 SIL-35 A–D 分节 + Multica 分节；D12 |
| ~~12~~ | ~~**SIL-9 机器身份（多机记忆「本机」歧义根治）**~~ | ✅ 已落地 `X-Machine-Id` header → contextvar → 写入自动打标 frontmatter `machine:` + 薄壳注入 `current machine` banner + SHELL.md 规则 + cli-remote.md 全节/pi 节（D13） | 三路断言全绿（stdio→hostname / header→frontmatter / 缺失→unknown）；已接入机器补一个 header，新接入自动带 |
| — | **新 CLI 接入** | Claude/Codex 复制 (c) 薄壳 | 机械工作，需要时做 |
| — | PyPI 发布（可选） | `pip install sill-ensoul` 一行装 | 目前从 GitHub 装；发 PyPI 只加发版动作，不改代码，有需要再做 |

> **当前状态：核心闭环（唤醒→检索→引用→沉淀）已全部打通，已发布到 GitHub（v0.1.0）。** 项目已达设计终态——自动沉淀（auto + notify-after）、编排者模式多 agent 协作都是定案，没有待办路线图。剩余的"新 CLI 接入""PyPI 发布"是按需的机械工作，非核心承诺缺口。

> 原则延续 DESIGN.md（同目录）：**先用文件证明价值，再用 MCP 解耦 CLI，最后再考虑图谱。** 本文档跟踪的是"兑现承诺路上"的具体问题，一条条来。
