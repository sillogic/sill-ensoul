# ROADMAP — 从"能跑"到"兑现核心承诺"的坎

> 这是一份**活文档**,记录 Sova 在落地"不依赖 CLI 的、带长期记忆的多智能体系统"过程中,技术与设计上的障碍、决策与下一步。慢慢完善。
>
> 阅读顺序:先看 §1(我们在赌什么)→ §2(已定的设计决策)→ §3(障碍清单)→ §4(下一步)。

---

## 1. 愿景与核心赌注

**目标**:一套与 CLI / 模型供应商都解耦的多智能体系统。每个 Agent 自带长期记忆(OKF Wiki),跨会话、跨项目累积经验——**一个 Agent 处理的同类型项目越多,记忆越充分,能力越强**。

支撑这个目标的几条赌注:

1. **记忆 = 文件(OKF),不是平台内部状态。** 可 git、可 diff、人可读、跨 CLI/模型通用。
2. **引擎 = 轻量 MCP server,只管数据/工具,不碰推理。** 自动满足"模型供应商无关"。
3. **记忆范围是"角色作用域",不是"项目作用域"。** 这是相对现有 CLI(均以项目为单位、无跨项目记忆)的核心差异化——也是整个项目存在的理由。
4. **越用越强 = 规模红利。** 这条把成败压在了"记忆增长"上,因此任何**随规模退化**的东西都是直接威胁(见 H1)。

> 近期聚焦:**孤立多 Agent**(一类项目一个 Agent;多类任务多个 Agent;另有跨项目 Agent 如 UI/UX、测试)。编排/通讯(Phase 2)暂缓。

---

## 2. 已定的设计决策(写在这里防漂移)

### D1 — 服务形式:MCP 作主接口,核心保持 MCP 无关
- MCP 是当前最佳的"LLM 工具调用"主接口:各目标 CLI(Claude Code / Codex / Cursor / zcode / OpenCode)通吃,一次实现多处用,结构化参数优于文本解析。
- **但 MCP 不能是唯一通路。** 关键纪律:**逻辑只进 `okf.py` / `registry.py` / `comm.py`;`server.py` 永远只做透传,不塞逻辑。** 这样未来可加 `cli.py`(二进制,最大可移植)、`http.py`(远程 / 多 CLI 共享实例)而不碰核心。
- 现状已符合:`okf.py` 头部声明 *"pure logic and has no MCP dependency"*,`server.py` 是薄 FastMCP 适配层。**保持即可,不要破坏。**
- 备选评估:HTTP/REST(CLI 不原生调,与 MCP 重复)、CLI 二进制(可移植但文本需解析)、纯文件(零依赖但写入易错)——均不如 MCP 适合本用途。

### D2 — 适配层三层分离(保证 CLI 可移植)
| 层 | 职责 | CLI 相关性 | 现状 |
|---|---|---|---|
| (a) 引擎 | 读写检索 OKF | CLI 无关 | ✅ 已做到 |
| (b) persona + workflow | "何时召回/沉淀"的工作流内容 | **CLI 无关,只写一次** | ❌ 待建(放 bundle 或 shared) |
| (c) 触发壳 | 怎么在某个 CLI 里触发 | 每 CLI 一份,薄 | ❌ 待建 |

- **可移植杠杆**:workflow 内容 (b) 写一次(纯 markdown),每个 CLI 的壳 (c) 只**引用**它,不内联。工具调用词(`agent_index`/`wiki_search`...)本来就跨 CLI 一致(同一 MCP server),真正每 CLI 不同的只有"怎么触发"。
- 落地方式:把 workflow 写在一个共享文档,zcode 的 AGENTS.md / Claude 的 CLAUDE.md / Codex 的 skill 都指向它,各自只改壳。

### D3 — 记忆范围:角色作用域,非项目作用域
- 一个 Agent = 一个 OKF bundle = `knowledge/agents/<id>/`。记忆跨所有项目累积,不绑定任一项目仓库。
- 见 H4:目前 KB 物理位置与此理念有冲突,待调整。

### D4 — skill 调度:agent 是 skill 的推荐者,非拥有者(纯文档驱动)
- **skill = 各 CLI 市场里那种可安装的能力包**(如 document-skills:pdf、frontend-design)。agent **不拥有 skill**,只积累**"使用 skill 的经验"**——用过、觉得好、记下来、下次推荐。存为普通 OKF concept(`type: Reference`,id 形如 `expertise/skill-<名字>`),记:这个 skill 是什么 / 何时推荐用 / 实操判断(非文档原文)。
- **调度规则**(见 WORKFLOW.md §3):接到任务→检索 skill 经验→命中则推荐"用 X skill"→**判断当前环境有没有**:有用、没就提醒用户自己装。**不代装、不探测、不猜**;只有真正用过且好用才沉淀。不记每个 CLI 怎么装(那是用户的事,各 CLI 自己引导)。
- **为什么这样设计**:① skill 是 CLI 的,"用 skill 的经验"是 agent 的记忆,两者解耦,契合"纯文档外挂"哲学(零代码);② 去掉自动安装/探测=守住安全边界,也让规则极简。
- **状态**:✅ 已落地。规则在 WORKFLOW.md §3 + zcode AGENTS.md 薄壳;demo 见 algo-engineer 的 `expertise/skill-pdf`(用真实 document-skills:pdf 沉淀)。

---

## 3. 障碍清单(坎)

> 状态图例:🔴 阻塞核心承诺 · 🟡 影响质量但不阻塞 · 🟢 低优先 / 已决策待执行
> 字段:现状(带 `file:line`)→ 为什么是问题 → 影响 → 方案 → 状态

### H1 — ✅ [已修] 检索质量随规模退化(最关键)
- **曾现**:`sova/okf.py` 的 `search()` 用 `hay.count(w)` 做关键词子串计数,无分词、无 TF-IDF、无语义。与赌注 4("越用越强")直接冲突——记忆越多噪声越大精度越降。
- **修复**:新建 `sova/fts.py`,SQLite FTS5 + BM25 排序。关键发现与解法:
  - **unicode61 把连续 CJK 当成单 token**("双塔模型"是一个 token),子串"双塔"永远搜不到 → 在**索引端**对 CJK 按字切分(`_segment_for_index`),查询端同步分词,零依赖实现中文子串检索(无需 jieba)。
  - 索引存 `<agent_dir>/.fts/index.db`(bundle 内、可 git);`search` 查询前做增量同步(按 mtime),保证索引与 bundle 一致,无需外部重建。
- **验收**:11 项检索回归(`tests/test_search.py`)全绿——中英混合查询精准命中,persona 不污染,写后立即可搜。
- **副作用(已修)**:索引端对 CJK 按字分词后,FTS 表里的 title 也被加了空格("机 器 学 习"),`search` 若从 FTS 表取 title 会返回污染文本。修复:`okf.search` 改用原始 concept 的 title(`by_cid`),不从 FTS 表取——分词只发生在索引内部,不污染返回值。
- **状态**:✅ 已修。规模再大时(关系/时序复杂)再考虑向量(mem0/Cognee)或 Graphiti。

### H10 — ✅ [已落地] 三个使用场景的规则(自我认知/项目查询/身份保持)
- **场景1 自我认知**(`WORKFLOW.md` §1.1):唤醒后用户问"你是谁/能做什么/做过什么",基于 persona + concept 清单回答。验证:`agent_index` 返回的 persona 在上下文即可支撑。
- **场景3 项目/经验查询**(`WORKFLOW.md` §2.1):问"做过哪些项目"→ 列 concept 清单里 `type: Project` 的;问"某项目经验"→ `wiki_read("projects/<名>")`。验证:读出 demo-project 的"负采样 1:4 AUC 最高"等细节。
- **场景2 身份保持**(`WORKFLOW.md` §2.2):会话深入后 persona "沉底"导致脱离 Agent——这是纯文档方案的固有张力。缓解规则:做专业判断前先想"记忆里有没有相关的"、话题回专业领域主动重检索、发现用通用知识冒充 Agent 经验时停下重检索。**诚实边界:缓解不完美,这是"软身份"换"CLI 无关"的代价。**
- **状态**:✅ 规则已写入 WORKFLOW.md + zcode AGENTS.md 薄壳。

### H2 — 🟢 [半自动已落地] 记忆"长"靠蒸馏机制
- **曾现**:`write_concept`/`append_log` 只"被调才写";纯手动蒸馏的问题是人会"懒得记"——任务结束时最不想干的就是复盘,记忆会停在初始几条不长了,"越用越强"承诺不兑现。
- **已落地(半自动,纯文档驱动)**:`WORKFLOW.md` §3 升级为**提醒式半自动**——agent 主动判断时机(踩了非平凡的坑/可复用决策/总结出模式/纠正旧认知)、做提炼,但**写入由用户确认**守住质量门禁。规则写在文档里(明确可判定的触发条件),无后台代码。zcode `AGENTS.md` 薄壳已同步。
- **为什么是半自动而非全自动**:全自动蒸馏(sleeptime agent)有质量风险——LLM 自动判断"什么值得记"容易产出垃圾条目,反而稀释检索质量(H1 刚修好);且是个有状态的后台子系统,与"CLI 解耦"原则有张力。半自动:解决"懒得记"(趁热提醒)、保留"人过滤质量"(确认才写)、零额外子系统。
- **未来升级条件**:① 手动/半自动已跟不上(几十个项目后);② 积累了足够多样本,能定义"什么算好经验"作为自动蒸馏的提炼标准;③ 能接受记忆里有部分噪声。届时再上 sleeptime agent,可模仿已有 concept 风格。**现在样本太少,无质量基准,不宜全自动。**
- **状态**:🟢 半自动已落地。全自动(进阶)待未来。

### H3 — ✅ [已修] 适配层缺失,且必须 CLI 可移植
- **曾现**:无任何机制在新会话/进项目时自动 `agent_index` + 按需 `wiki_search`,调不调全靠提示词,不稳定。
- **修复**(遵循 D2 三层分离):
  - **(b) 层** —— 新建 `WORKFLOW.md`(repo 根),CLI 无关的权威工作流:唤醒→召回→引用→沉淀四步 + 12 工具速查 + 反模式。各 CLI 共用这一份,不重复。
  - **(c) 层 zcode 壳** —— 新建 `~/.zcode/AGENTS.md`(用户级,所有工作区生效),内含压缩版触发规则(自包含、条件触发:仅任务涉及专业角色时激活),并指向 WORKFLOW.md 完整版。壳很薄,不内联逻辑。
- **可移植性**:迁 Claude Code → 把 AGENTS.md 那段压缩规则放进 `CLAUDE.md`;迁 Codex → 放进其 skill。工具调用词(`agent_index` 等)本来就跨 CLI 一致,真正每 CLI 不同的只有"怎么触发"这一件事。
- **状态**:✅ 已修(zcode 接入完成)。Claude/Codex 接入是机械复制,待用户需要时做。

### H4 — ✅ [已修] KB 物理位置在项目仓库内,与跨项目理念冲突
- **曾现**:`kb_root()` 默认 `<repo>/knowledge`——KB 物理上躺在某个具体项目目录里,跨项目 Agent 的记忆不该属于任一项目。
- **修复**:`okf.py` 新增 `_default_kb_root()`,平台感知全局默认(Windows `%LOCALAPPDATA%/sova/knowledge`、Linux `%XDG_DATA_HOME%/sova/knowledge`、兜底 `~/.sova/knowledge`),`SOVA_KB` 仍可覆盖。
- **状态**:✅ 已修。repo/knowledge 保留为开发期副本。

### H6 — ✅ [已修] wiki_read 因 datetime 序列化崩溃
- **曾现**:`server.py` 的 `_dump` 用 `json.dumps` 序列化 `okf.read_concept` 返回值,而 frontmatter 里无引号的 `timestamp: 2026-03-10T08:00:00Z` 被 YAML 解析成 `datetime` 对象 → `datetime is not JSON serializable` → FastMCP 包成 tool error。
- **影响范围**:这是**核心路径 bug**。任何带 `timestamp` 的 concept(几乎所有项目经验)一经 `wiki_read` 即崩——"带历史经验进项目"根本跑不通。`list_agents`/`agent_index` 因不返回完整 frontmatter 而幸免。
- **修复**:`server.py` 增加 `_json_default`,`datetime/date` → ISO 字符串。已验证三层测试全绿(OKF 冒烟 + MCP live + 12 工具可用)。
- **教训**:三层分离(D1)的价值在此兑现——bug 精确定位在壳层 `server.py`,核心 `okf.py` 无辜。同时暴露**缺一层"MCP 工具返回值契约"测试**(见 H7)。

### H7 — ✅ [已修] persona(AGENT.md)污染搜索与 concept 清单
- **曾现**:`AGENT.md`(persona)未列入 OKF 保留名,被当成普通 concept 进了 `agent_index` 清单和搜索索引。实测 `wiki_search("推荐系统")` 时 persona(score 1)抢占真正经验条目位置。
- **修复**:`okf.py` 新增 `EXTRA_NON_CONCEPT = {"agent.md"}`,`_iter_concepts` 同时排除 `RESERVED`(index/log)和 `EXTRA_NON_CONCEPT`(persona);`write_concept` 也禁止写 persona 文件名。persona 仍经 `agent_index()` 的 `persona_preview` 暴露。
- **验收**:concept 清单不再含 AGENT;搜索结果不再被 persona 文本污染。已纳入 `tests/test_search.py`。
- **状态**:✅ 已修。

### H9 — ✅ [已修] server 依赖 cwd 才能启动,跨项目使用会踩坑
- **曾现**:`command = python -m sova.server` + `cwd` 写死在 repo 根。`python -m` 只有 cwd 在 repo 根才能 import 到包;从其他目录启动 → `ModuleNotFoundError: No module 'sova'` → 进程秒退 → CLI 端 `Connection closed` / 工具不出现。与"任意项目唤醒全局 Agent"核心场景直接冲突。
- **修复**:① 新增 `pyproject.toml`,`[project.scripts]` 定义 `sova-mcp = sova.server:main` 控制台命令;② `server.py` 增加 `main()` 入口;③ `pip install -e .` 装成可编辑包。装完后**任意 cwd 直接 `sova-mcp`** 即启动 server,无需 cwd/PYTHONPATH。
- **验收**:从临时目录用 `command=sova-mcp` 启动 → 12 工具可用 → 全局 KB 读到 algo-engineer 历史经验。全绿。
- **各 CLI 配置现在统一简化为**:`{"command": "sova-mcp"}`(zcode 用户级已更新为此形式)。
- **状态**:✅ 已修。**进阶(公开分享)**:`pip install -e .` 是本地;要给别人/别的机器用,发 PyPI 后对方一行 `pip install sova` 即可,配置完全相同。或 `uvx sova`(隔离运行)。这些只需在现有 `pyproject.toml` 上加发版动作,无需改代码。

### H8 — ✅ [已修] 缺 MCP 工具返回值契约测试
- **曾现**:无"MCP 工具返回值可被 JSON 解析、字段齐全"的回归测试。`test_mcp_live` 抓出 H6 证明了价值。
- **修复**:`run_tests.py` 现纳入 4 个测试(smoke / search / mcp_live / cross_project),跳过会红的 phase2(H5)。`test_search`(11 项检索回归)、`test_mcp_live`(12 工具壳层)、`test_cross_project`(跨项目端到端)均已入库。
- **状态**:✅ 已修。`python run_tests.py` → ALL TESTS PASSED。

### H5 — 🟡 Phase 2 测试不可重复运行(registry 状态污染)
- **现状**:`tests/test_phase2.py:60-66` 第 6/7 步**修改了真实 registry 且不回滚**。`comm` 有 `comm_clear()`(`comm.py:94`)清理 mailbox,但 **registry 没有任何 reset/快照机制**。第一次跑 OK,第二次必挂(已实测 `run_tests.py` 失败:期望冲突却 clean)。
- **为什么是问题**:回归基线不可信;CI 不可重复。
- **影响**:目前聚焦孤立 Agent、暂缓 Phase 2,故此问题可暂搁;但 `run_tests.py` 一跑就红,易误导。
- **方案**:测试加 setup/teardown(每次重置成"冲突初始态")或 fixture 快照;或给 registry 加 `reset_for_test()`。
- **状态**:已复现失败;属 Phase 2 范畴,当前 deprioritize。临时可单独跑 `python -m tests.test_smoke` 看 OKF 层。

### H11 — 🟢 [已知限制,暂不修] 并发写同一 agent 的 expertise 会丢数据
- **风险**:`wiki_write_concept`(`okf.py`)用 `Path.write_text` 非原子覆盖写;`append_log` 是 read-modify-write。两个会话**同时**写同一个 agent 的**同一个 concept** 文件时,后写覆盖先写,数据丢失且无报错;同时追加 log 会丢一条。
- **实际量级**:窄。① 顺序写(项目A写完→项目B写)完全安全;② "两个项目同时沉淀到**同一个** concept"概率低——项目过程记忆写在 `projects/<本项目>.md`,各项目天然隔离不冲突;真正的并发热点只在 `expertise/`(跨项目蒸馏的共享区),而蒸馏本就是"项目结束、低频提炼"的操作。
- **相关洞察(已体现在结构里)**:项目过程记忆(每项目独立文件,天然隔离)和蒸馏的专业意见(跨项目共享,并发热点)是两种生命周期的东西。**现有目录结构已正确分层**——`projects/` 隔离、`expertise/` 共享——不用大改,缺的只是对 expertise/ 的并发保护。
- **方案(按工作量排,暂不动)**:① 最轻——写 expertise 时加文件锁(`fcntl`/`msvcrt`),顺序化并发写;② 中等——`write_concept` 改原子写(临时文件 + `os.replace`),防"写到一半被覆盖",但解不了 read-modify-write 竞态;③ 重——版本号/冲突检测,过度工程。
- **为什么暂不修**:① 还在验证核心闭环,并发是"真并行、规模上来"才迫切的问题;② 文件锁在 Windows 上有坑;③ 加锁是解决还没发生的问题。等真出现"两项目同时沉淀到同一 expertise"再处理。
- **状态**:🟢 已知限制,记下来。当前 ROADMAP 优先级低于核心闭环测试。

---

## 4. 下一步(按"兑现核心承诺"排序)

| 序 | 坎 | 动作 | 为什么这个序 |
|---|---|---|---|
| ~~0~~ | ~~H6/H9/H4~~ | ✅ 已修 datetime / cwd / KB 位置 | 三轮测试逐个修复,server 可发布 |
| ~~1~~ | ~~H3~~ | ✅ 已修 适配层(WORKFLOW.md + zcode AGENTS.md) | 唤醒/检索自动触发,可移植架构立住 |
| ~~2~~ | ~~H1+H7~~ | ✅ 已修 FTS5 检索 + persona 排除 | 规模红利命门解决,11 项回归锁定 |
| ~~3~~ | ~~H8~~ | ✅ 已修 测试套纳入 run_tests.py | 防壳层 bug 回归 |
| 4 | ~~H2~~ | ✅ 半自动蒸馏已落地(纯文档驱动) | 解决"懒得记",守住质量门禁;全自动待未来 |
| ~~—~~ | ~~**改名**~~ | ✅ 已完成 代码层统一为 sova:包名 `sova`、命令 `sova-mcp`/`sova-init`、目录 `sova/`、环境变量 `SOVA_KB`/`SOVA_SHARED`、KB 路径 `sova/knowledge` | 对外品牌名 Sova 与代码内部命名一致;现有记忆已迁移 |
| — | H5 | Phase 2 测试隔离 | 暂搁;做编排/通讯时一并修 |
| — | **新 CLI 接入** | Claude/Codex 复制 (c) 薄壳 | 机械工作,需要时做 |
| — | 发布 | PyPI / `uvx` 公开分享 | 本机已解绑;分享只加发版动作,不改代码 |

> **当前状态:核心闭环(唤醒→检索→引用→沉淀)已全部打通且可发布。** 剩余 H2(自动蒸馏)是增强,Phase 2(编排)是另一条线。

> 原则延续 DESIGN.md:**先用文件证明价值,再用 MCP 解耦 CLI,最后再考虑图谱。** 这份文档跟踪的是"兑现承诺路上"的具体坎,一条条来。
