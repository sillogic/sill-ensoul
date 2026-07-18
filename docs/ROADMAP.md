# ROADMAP — 设计决策与已解决问题

> 这是一份**活文档**，记录 sill-ensoul 在落地"与 CLI、模型供应商解耦的长期记忆系统"过程中的设计决策、已解决问题与已知限制。
>
> 阅读顺序：§1（设计原则）→ §2（设计决策 D1-D6）→ §3（已解决问题清单）→ §4（当前状态）。

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

## 2. 设计决策（D1-D6）

### D1 — 服务形式：MCP 作主接口，核心保持 MCP 无关

- MCP 是当前最佳的"LLM 工具调用"主接口：各目标 CLI（Claude Code / Codex / Cursor / zcode / OpenCode）通吃，一次实现多处用，结构化参数优于文本解析。
- **但 MCP 不能是唯一通路。** 关键纪律：**逻辑只进 `okf.py`；`server.py` 永远只做透传，不塞逻辑。** 这样未来可加 `cli.py`（二进制，最大可移植）、`http.py`（远程 / 多 CLI 共享实例）而不碰核心。
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

### 已知限制（不修，已决策）

#### #11 — 🟢 并发写同一 agent 的 expertise 会丢数据

- **风险**：`wiki_write_concept` 非原子覆盖写；`append_log` 是 read-modify-write。两进程同时写同一 concept → 后覆盖先，无报错。
- **实际量级**：窄。`projects/` 天然隔离（每项目独立文件），热点只在 `expertise/`（跨项目蒸馏共享区），而蒸馏本就是低频操作。
- **方案（按工作量）**：① 文件锁（`fcntl`/`msvcrt`）顺序化；② 原子写（临时文件 + `os.replace`）；③ 版本号/冲突检测（过度工程）。
- **为什么不修**：核心闭环已验证；文件锁 Windows 有坑；加锁是解决还没发生的问题。等真出现并发写再处理。

#### #12 — 🟢 server.py 工具数增长后应按职责拆分

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
| — | **新 CLI 接入** | Claude/Codex 复制 (c) 薄壳 | 机械工作，需要时做 |
| — | PyPI 发布（可选） | `pip install sill-ensoul` 一行装 | 目前从 GitHub 装；发 PyPI 只加发版动作，不改代码，有需要再做 |

> **当前状态：核心闭环（唤醒→检索→引用→沉淀）已全部打通，已发布到 GitHub（v0.1.0）。** 项目已达设计终态——自动沉淀（auto + notify-after）、编排者模式多 agent 协作都是定案，没有待办路线图。剩余的"新 CLI 接入""PyPI 发布"是按需的机械工作，非核心承诺缺口。

> 原则延续 DESIGN.md（同目录）：**先用文件证明价值，再用 MCP 解耦 CLI，最后再考虑图谱。** 本文档跟踪的是"兑现承诺路上"的具体问题，一条条来。
