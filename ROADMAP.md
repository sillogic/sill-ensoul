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

### 已修复的坎(摘要)

| 坎 | 问题 | 解法 | 教训 |
|---|---|---|---|
| H1 ✅ | 检索质量随规模退化(子串计数无分词) | `fts.py` SQLite FTS5 + BM25;CJK 索引端按字分词(`_segment_for_index`),查询端同步分词,零依赖 | 规模红利命门;FTS 表 title 被分词污染→`search` 用原始 concept title |
| H2 ✅ | 记忆"长"靠蒸馏,人会懒得记 | 提醒式半自动(纯文档):agent 主动判断时机+提炼,用户确认才写 | 全自动有质量风险(LLM 产垃圾稀释检索);半自动守质量门禁 |
| H3 ✅ | 适配层缺失,CLI 不可移植 | D2 三层分离落地:WORKFLOW.md(CLI 无关)+ 各 CLI 薄壳 | 工具调用词跨 CLI 一致,每 CLI 不同的只有"怎么触发" |
| H4 ✅ | KB 在项目仓库内,违背跨项目理念 | `_default_kb_root()` 平台感知全局默认(Win `%LOCALAPPDATA%/sova/knowledge`) | 跨项目 Agent 的记忆不该属于任一项目 |
| H6 ✅ | `wiki_read` 因 datetime 序列化崩溃 | `server.py` 的 `_dump` 加 `_json_default`,datetime→ISO 字符串 | D1 价值兑现:bug 定位在壳层,核心无辜,3 行修好 |
| H7 ✅ | persona(AGENT.md)污染搜索与 concept 清单 | `EXTRA_NON_CONCEPT = {"agent.md"}`,`_iter_concepts` 排除 | persona 不该进检索索引 |
| H8 ✅ | 缺 MCP 工具返回值契约测试 | `run_tests.py` 纳入 4 测试,自建临时 KB | 测试不依赖 repo 预存数据(H4) |
| H9 ✅ | server 绑死 cwd | `pyproject.toml` 定义 `sova-mcp` 控制台命令 + `pip install -e .` | 任意 cwd 直接 `sova-mcp` |
| H10 ✅ | 三场景规则(自我认知/项目查询/身份保持) | 写入 WORKFLOW.md §1.1/§2.1/§2.2 | 身份保持是"软身份"换"CLI 无关"的代价,缓解不完美 |

### 未完成的坎

#### H5 — 🟡 Phase 2 测试不可重复运行(registry 状态污染)
- **现状**:`tests/test_phase2.py` 修改真实 registry 且不回滚,第二次必挂。`comm` 有 `comm_clear()` 但 registry 无 reset 机制。
- **影响**:回归基线不可信;CI 不可重复。但当前聚焦孤立 Agent、Phase 2 deprioritize,可暂搁。
- **方案**:测试加 setup/teardown 或 fixture 快照;或给 registry 加 `reset_for_test()`。
- **状态**:已复现失败;属 Phase 2 范畴,`run_tests.py` 已跳过它。

#### H11 — 🟢 [已知限制,暂不修] 并发写同一 agent 的 expertise 会丢数据
- **风险**:`wiki_write_concept` 非原子覆盖写;`append_log` 是 read-modify-write。两进程同时写同一 concept → 后覆盖先,无报错。
- **实际量级**:窄。`projects/` 天然隔离(每项目独立文件),热点只在 `expertise/`(跨项目蒸馏共享区),而蒸馏本就是低频操作。
- **方案(按工作量)**:① 文件锁(`fcntl`/`msvcrt`)顺序化;② 原子写(临时文件 + `os.replace`);③ 版本号/冲突检测(过度工程)。
- **为什么暂不修**:还在验证核心闭环;文件锁 Windows 有坑;加锁是解决还没发生的问题。等真出现并发写再处理。

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
