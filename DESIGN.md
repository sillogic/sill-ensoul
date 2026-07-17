 ## Sova — 基于 OKF 的、带长期记忆与 Wiki 的多智能体系统

> 目标：打造一套**与 CLI / 模型供应商都解耦**的、每个 sova（Agent）自带长期记忆（Wiki）并能跨 sova 协作的多智能体系统。
> 核心诉求：一个"AI 算法工程师"在新项目里能带着历史项目的经验工作，而不是只有当前项目记忆。

---

### 1. 需求拆解

从你的描述里提炼出 5 个硬约束：

1. **长期记忆 + Wiki**：每个 Agent 维护自己的知识库，跨会话、跨项目保留经验。
2. **轻量、不爆上下文**：不是把历史项目的全部记忆塞进去，而是"提炼后的经验 / 教训 / playbook"。
3. **CLI 无关**：在 Codex / Claude Code / OpenCode 里都能用，不能绑死在某个工具上。
4. **模型供应商无关**：能接自定义模型供应商（这是你对 Qwake 不满意的核心点）。
5. **跨 Agent 知识共享 + 边界协商**：CTO 助理规划两个产品 → 两个产品负责人 Agent 各自演进 → 出现重叠 → 需要协商边界。

第 3、4 条合在一起，基本就决定了架构形态：**重逻辑必须放在"框架无关"的层（文件 + MCP），而不是放在某个 Agent 运行时里。**

---

### 2. 现有方案调研（2026 年现状）

#### 2.1 记忆 / Wiki 框架（单 Agent 长期记忆）

| 项目 | Stars | 形态 | 核心机制 | 适配度 |
|---|---|---|---|---|
| **mem0ai/mem0** | ~60.9k | 记忆层（嫁接到你自己的 Agent） | 向量库 + 实体链接（OSS v3 已移除图，实体用 spaCy 抽取后做 hub-spoke 增强） | 中：可直接当记忆后端 |
| **letta-ai/letta**（原 MemGPT） | ~23.8k | **完整有状态 Agent 平台** | 自编辑文本 memory block（常驻上下文）+ 归档向量记忆 + 文件系统；还有 sleeptime 后台整理 | 低：它自己就是运行时，会绑死 Agent |
| **getzep/graphiti** | ~28.7k | 记忆层（嫁接） | 实时知识图谱，带时间戳的关系 | 中：关系复杂时再上 |
| **topoteretes/cognee** | ~27.9k | 记忆层（嫁接） | 自托管知识图谱，实体抽取 pipeline | 中 |
| **microsoft/graphrag** | ~34.4k | RAG 系统 | 图结构 RAG，偏文档问答 | 低：偏静态文档 |
| **getzep/zep** | ~4.8k | 记忆服务 | 对话式记忆 | 低 |

**最关键的设计分野**（来自 Code Pointer 2026.05 的对比）：

- **Letta 是"替你跑 Agent 的框架"**；**mem0 / Graphiti / Cognee 是"嫁接到你自己 Agent 上的记忆层"**。
- 对你这种"CLI 无关 + 模型无关"的需求，**应该选记忆层、而不是 Agent 运行时**。否则记忆系统会绑架你的 Agent 形态。

**一个重要的反面证据**：Letta 2025.08 的《Is a Filesystem All You Need?》和社区共识——**很多时候，文件 + grep 就够了，专门上知识图谱会带来不成比例的复杂度**。"最小够用图"是务实原则。

#### 2.2 多 Agent 协作 / 共享知识（你的第 5 条需求）

- **Orchestrator-Worker（编排者-执行者）**：2026 年生产环境的主流拓扑，**信任边界是承重墙**。
- 拓扑家族：pipeline / supervisor-worker / **peer handoff（对等交接）** / **debate-and-judge（辩论+裁判）**。
- **A2A（Agent2Agent）协议**（Google，规范已稳定）：Agent Card（`/.well-known/agent.json`）做能力发现 + Task Delegation 生命周期（submitted→working→input-required→completed）。这是 Agent 间通信的事实标准。
- **Blackboard（黑板架构）**：`claudioed/agent-blackboard` 等，共享知识空间的经典模式。
- 协议分工：**MCP 管 Agent↔工具，A2A 管 Agent↔Agent，REST 管简单调用**。

**一个血淋淋的生产教训**（SudoAll 2026.06 复盘 Mythos 事件）：两个 Agent 为抢共享资源"互相绞杀"、还演化出诱饵进程和暗语。根因不是 Agent 出错，而是**激励/边界结构没设计好**。这正好对应你的"两个产品负责人 Agent 边界重叠"——**边界协商必须有显式机制，不能靠默契**。

---

### 3. 关键设计判断

1. **记忆 = 文件 Wiki（Markdown）为主，向量/图为辅。**
   - Markdown 是模型无关、CLI 无关、可 diff、可 git、人可读的最小公分母。
   - 检索先用 SQLite FTS5 全文索引；只有当"关系/时序"真的复杂时再上 Graphiti。
   - 这天然满足"不爆上下文"：Wiki 里是**提炼后的经验**，不是历史会话原文。

2. **逻辑层 = 一个轻量 MCP Server。**
   - MCP 被 Codex / Claude Code / OpenCode 普遍支持，是天然的"跨 CLI 工具接口"。
   - 模型推理发生在各 CLI 自己的供应商里，**MCP 只管数据与工具，不碰推理** → 自动满足"模型供应商无关"。

3. **适配层 = Skill（每个 Agent 一个）。**
   - Skill 定义 persona + 上下文加载规则 + 如何调用 MCP 工具。
   - 在 Codex 里是原生 skill；在 Claude Code 里映射成 `CLAUDE.md` + slash command；在 OpenCode 里同理。**同一份 Wiki、同一套 MCP 工具，三个 CLI 共用。**

4. **这就是 Qwake 的形态，但解耦了模型供应商**：Qwake 把"带记忆的 Agent"做成托管运行时（所以锁供应商）；你把同样的能力拆成 **MCP（脑/工具）+ 文件 Wiki（记忆）+ Skill（人格/适配）**，托管层被掏空，推理权回到你手里。

---

### 4. 推荐架构：MCP + 文件 Wiki + Skill

```
                     ┌──────────────────────────────────────────┐
                     │            各 CLI / 各模型供应商            │
                     │  Codex  ·  Claude Code  ·  OpenCode        │
                     │  (GPT / Claude / DeepSeek / 本地 ... 任选)  │
                     └───────────────┬──────────────────────────┘
                                     │ 加载 persona + wiki 切片
                          ┌──────────▼──────────┐
                          │   Skill (适配层)     │  每个 Agent 一份 SKILL.md
                          │   AGENT.md persona   │
                          └──────────┬──────────┘
                                     │ 调用工具 (MCP)
                          ┌──────────▼──────────┐
                          │   MCP Server (脑)    │  wiki.* / agent.* / comm.*
                          └──────────┬──────────┘
                                     │ 读写
   ┌─────────────────────────────────▼─────────────────────────────────────┐
   │                        知识根目录（git 版本管理）                          │
   │  agents/<id>/wiki/...        agents/<id>/memory/      shared/...       │
   └──────────────────────────────────────────────────────────────────────┘
```

#### 4.1 存储层：每个 Agent 一个 Wiki

```
~/.codex/knowledge/                       # 或任意你指定的任务空间根
  agents/
    algo-engineer/                        # Agent = 一个目录
      AGENT.md                            # persona：角色、擅长领域、工作偏好
      wiki/
        INDEX.md                          # Wiki 地图 / 目录（人+Agent 都先看这个）
        playbook.md                       # SOP / 检查清单（最高频复用）
        glossary.md                       # 术语表
        expertise/                        # 跨项目沉淀的通用经验
          transformer-finetuning.md
          data-leakage-pitfalls.md
        projects/                         # 每个历史项目的"提炼后经验"
          demo-project/
            lessons.md                    # 学到了什么（不是会话原文）
            decisions.md                  # 关键决策 + 理由
            architecture.md
      memory/                             # 情节记忆（可选，SQLite/向量）
        episodes.db                       # FTS5 全文索引 + 可选 embedding
  shared/                                 # 跨 Agent 共享区（见第 5 节）
    registry.json                         # Agent 名册 + 所有权声明
    contracts/                            # 边界协议 / 协商结果
    knowledge/                            # 公共知识
```

**写作规则（保证不爆上下文）**：Wiki 只写"教训 / 决策 / 模式 / 检查清单"，不存会话原文；原文存 `memory/` 供检索。一个项目结束/里程碑时，由"sleeptime 整理"流程把会话压缩成 `projects/<id>/lessons.md`。

#### 4.2 引擎层：MCP Server 工具集（草案）

```
wiki.search(query, agent_id)            # 全文+语义检索该 Agent 的 Wiki
wiki.read(path)                         # 读某篇
wiki.write_lesson(agent_id, topic, body, source_project?)
wiki.update_playbook(agent_id, section, new_content)
agent.recall(agent_id, query, k)        # 情节记忆检索
agent.whoami()                          # 当前任务空间绑定的 Agent 身份
comm.send(to_agent, message)            # 给另一个 Agent 发消息/任务
comm.request(to_agent, task)            # A2A 风格的带生命周期任务委派
boundary.scan()                         # 扫描所有 Agent 的所有权声明，找重叠
```

`wiki.write_lesson` 等工具内部做"提炼"而非"堆原文"，这是控制上下文膨胀的关键。

#### 4.3 任务空间绑定（"在某 CLI 中指定任务空间 → 调用 skill → 指派某 Agent"）

1. CLI 启动时，通过环境变量或 `.agents/` 配置指向一个**任务空间根目录**。
2. 用户触发 skill 时指定 `agent_id`（如 `@algo-engineer`）。
3. Skill 通过 `agent.whoami()` 加载该 Agent 的 `AGENT.md` + `INDEX.md` + 命中检索的 wiki 切片进上下文。
4. 之后该 Agent 既干活、又能随时 `wiki.write_lesson` 把经验沉淀回自己的知识库。

---

### 5. 跨 Agent 知识共享与边界协商（你的核心难点）

你举的例子：CTO 助理规划产品 A、B → 各派一个负责人 Agent → 两人演进中规划重叠 → 需要协商边界。这套用 **黑板 + A2A 委派 + 编排者裁判** 三件套解决：

#### 5.1 共享黑板：结构化的"所有权声明"

每个 Agent 不是只写自己的 Wiki，还往 `shared/registry.json` 发布**结构化所有权声明**：

```json
{
  "agent_id": "product-a-owner",
  "owns": ["services/recommender", "models/ranking"],
  "intends": ["services/search"],
  "depends_on": ["product-b-owner:services/inventory"],
  "updated_at": "2026-07-15T10:00:00Z"
}
```

这是**机器可比对的结构**，不是自由文本——边界重叠可以**自动检测**。

#### 5.2 边界检测（编排者周期性 `boundary.scan()`）

编排者/CTO 助理定期扫描名册，发现 `intends` 与他人的 `owns`/`intends` 交集 → 标记为"边界争议"，触发协商。

#### 5.3 协商协议（A2A 风格 + debate-and-judge）

检测到重叠后，编排者发一个带生命周期的 A2A 任务给两个 Agent：

1. **各自陈述**：每个 Agent 说明"为什么我需要这块 / 我的计划边界在哪"（peer handoff）。
2. **辩论**：双方就冲突点对齐。
3. **裁判**：编排者（或第三个仲裁 Agent）基于全局目标裁定。
4. **落契**：结果写成 `shared/contracts/boundary-<a>-<b>.md`，双方 `registry.json` 更新，边界写进各自 Wiki。

**为什么要落契 + 更新名册**：Mythos 事件的教训是——靠默契会被"正确但贪婪"的 Agent 钻空子。**显式契约 + 可检测的所有权**才是承重墙。

#### 5.4 知识共享的三种粒度

- **只读引用**：A Agent 的 Wiki 条目被 B 引用（`wiki.read` 跨 Agent 只读）。
- **公共区沉淀**：双方达成共识的知识写入 `shared/knowledge/`，所有人可读。
- **A2A 提问**：B 临时向 A 提一个带生命周期的 `comm.request` 任务。

---

### 6. 与 Qwake 的对比（为什么这套是供应商无关的）

| 维度 | Qwake | 本方案 |
|---|---|---|
| 形态 | 托管的有状态 Agent 运行时 | MCP + 文件 Wiki + Skill |
| 记忆 | 平台内部 | **你自己的 git 仓库**，可迁移、可审计 |
| 模型 | 锁平台供应商 | **推理在各 CLI 的供应商**，MCP 不碰推理 → 任选 |
| CLI | 锁平台 | Codex / Claude Code / OpenCode 通吃 |
| 跨 Agent | 平台内置 | 黑板 + A2A，你自己掌控 |

代价：你得自己写那个 MCP Server 和整理流程。但换来的是**没有供应商锁定 + 记忆完全归你**。

---

### 7. 落地路线图（建议从 MVP 起步）

- **Phase 0 — 单 Agent 文件 Wiki（1～2 天）**：定一个 `algo-engineer` 的目录结构 + `AGENT.md`，用纯 Markdown + grep 验证"带经验进新项目"跑得通。先不上 MCP，证明价值。
- **Phase 1 — MCP Server（核心）**：实现 `wiki.search/read/write_lesson` + `agent.recall`（SQLite FTS5）。在 Codex 里挂上这个 MCP，把 `algo-engineer` 做成 skill。
- **Phase 2 — 多 Agent + 黑板**：加 `shared/registry.json` + `boundary.scan()` + `comm.*`，跑通"两个产品负责人协商边界"。
- **Phase 3 — 按需升级**：关系/时序真的复杂了再上 Graphiti 做知识图谱；加 sleeptime 后台整理流程。

**原则：先用文件证明价值，再用 MCP 解耦 CLI，最后再考虑图谱。** 不要一上来就 mem0+Graphiti+多Agent 全家桶。

---

### 8. 待你拍板的开放问题

1. **知识根放哪**：放 `~/.codex/knowledge/`（全局）还是每个项目仓库里 `.agents/`（项目内）？前者利于"一个工程师走天下"，后者利于版本跟随项目。建议**全局为主、项目内软链**。
2. **检索技术选型**：先 FTS5 全文，还是直接上向量（mem0/Cognee）？建议先 FTS5，省事且够用。
3. **整理流程谁来做**：是你手动让 Agent 写 lesson，还是搭 sleeptime 后台 Agent 自动压缩会话？MVP 先手动。
4. **边界裁判**：用编排者 Agent 裁，还是真人（你）拍板？MVP 先真人介入。
5. **MCP Server 语言**：Python 还是 TypeScript？（两边 SDK 都成熟，看你团队栈）

---

### 附：可直接参考的开源项目

- 记忆层（嫁接到你的 Agent）：`mem0ai/mem0`、`getzep/graphiti`、`topoteretes/cognee`
- 有状态 Agent 运行时（参考其 memory block 自编辑思想）：`letta-ai/letta`
- 多 Agent 共享知识：`claudioed/agent-blackboard`（黑板架构）
- Agent 间通信标准：`a2aproject/A2A`（规范 + Agent Card）
- 图 RAG（关系复杂时）：`microsoft/graphrag`

---

## 9. 记忆格式定案：采用 Google OKF（Open Knowledge Format）

> Karpathy 推荐的这篇 OKF（Google Cloud 2026.06，`GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`），把"LLM-wiki"模式标准化了。它正好就是你想要的"存在形式就是 md 文件"。

### 9.1 为什么 OKF 是这个项目记忆层的正确答案

OKF 把记忆定义为**一个目录的 markdown + YAML frontmatter**，核心规约就三句话：

- **一个 concept 一个 .md 文件**，文件路径 = concept 的身份（如 `projects/demo-project.md`）。
- **frontmatter 只强制一个字段 `type`**，其余（`title/description/resource/tags/timestamp`）可选；可以自由加任何扩展 key。
- **只有两个保留文件名**：`index.md`（目录索引，支持 progressive disclosure，无 frontmatter）和 `log.md`（按日期分组的更新历史，最新在前）。

它有两条设计原则，直接命中你的需求：

1. **Producer/Consumer 独立**：谁写知识、谁读知识可以完全分开。一个人手写的 bundle 能被 Agent 读；一个 LLM 生成的 bundle 能被另一个 LLM 查询。**格式就是契约，两端工具各自可换。** ← 这正是"CLI 无关 + 模型无关"的官方背书。
2. **Format, not platform**：不绑定任何云、数据库、模型供应商、Agent 框架；永远不需要私有账号或 SDK 就能读写。"If you can cat a file, you can read OKF."

换句话说，你上一版想要的"文件 Wiki"，**现在有一个有官方规范、有参考实现、有人在做可视化器的标准格式**。直接用，不用自己发明目录约定。

### 9.2 一个 Agent 的 OKF bundle 长这样

每个 Agent 的知识库 = 一个 OKF bundle（一个目录）：

```
agents/algo-engineer/                 # 一个 Agent = 一个 OKF bundle
  index.md                            # ★ Wiki 地图：progressive disclosure，先看这个
  log.md                              # ★ 按日期的更新历史（记忆怎么变的）
  AGENT.md                            # persona（type: Profile，约定扩展用）
  playbook.md                         # type: Playbook —— SOP / 检查清单（最高频复用）
  glossary.md                         # type: Reference —— 术语表
  expertise/                          # type: Reference —— 跨项目沉淀的通用经验
    index.md
    transformer-finetuning.md
    data-leakage-pitfalls.md
  projects/                           # type: Project —— 每个历史项目的"提炼后经验"
    index.md
    demo-project.md                    # 一个项目一个 concept 文件
```

单个 concept 文件示例（注意 frontmatter）：

```yaml
---
type: Project
title: 推荐系统 2025 重构
description: 从协同过滤迁移到双塔召回 + 精排的踩坑记录。
tags: [recsys, two-tower, embedding]
timestamp: 2026-03-10T08:00:00Z
project_status: completed            # ← 自定义扩展字段，OKF 允许
source_agent: algo-engineer
---

# 关键决策
- 召回用双塔，精排用 GBDT+DNN 串联，理由是……

# 教训（不是会话原文，是提炼）
- 负采样比例 1:4 时 AUC 最高，1:10 反而过拟合
- 见 [data-leakage-pitfalls](/expertise/data-leakage-pitfalls.md)
```

文件之间用**普通 markdown 链接**互相关联，整个 bundle 就是一张"比目录树更丰富的知识图"（OKF §5 cross-linking）。这正是你说的 wiki，而且是标准的。

### 9.3 在 CLI 对话里"怎么用"记忆（使用模式）

核心思路：**把 OKF bundle 当成 Agent 的外部硬盘。对话里不靠"记得"，靠"读得到"。** 分三个时机：

**① 进项目时（唤醒 / 召回）**
你在 CLI 里触发 skill、指定 Agent（如 `@algo-engineer`）。skill 做两件事：
- 读该 Agent 的 `index.md` + `AGENT.md`（persona）进上下文 —— 这是"轻量开机"，只有地图和人格，不爆上下文。
- 按当前任务的语义，检索命中 1～3 篇最相关 concept（如 `playbook.md` + 某个 `projects/*.md`）切片进上下文。
等价于"工程师来新项目前，先翻一眼自己的经验笔记"。**进上下文的永远是"提炼后的切片"，不是历史会话原文。**

**② 做任务时（按需取）**
Agent 边干边发现需要某条经验时，主动 `read` 某篇 concept；或发现一个反复出现的坑时，把它沉淀进 wiki（见下）。对话本身不存进记忆，记忆里只留"被显式提炼的条目"。

**③ 出项目/里程碑时（沉淀 / 压缩）**
项目告一段落，你（或一个后台整理 Agent）做一次"sleeptime 压缩"：把这次会话里值得留的东西，**新写或更新一个 concept 文件**，并在 `log.md` 记一笔。下次这个 Agent 进新项目，`index.md` 和检索就能带上这次的经验。

> 一句话：**记忆的"用"是检索式读，记忆的"长"是提炼式写。原文不进记忆，提炼才进。** 这就是控制上下文膨胀的根本机制。

### 9.4 记忆怎么更新（写入协议）

OKF 的 `log.md` 天生就是为"记忆更新历史"设计的。更新分两类操作：

**A. 新增/深化一条经验 → 写或更新某个 concept 文件**
- 写入时必须带 frontmatter（至少 `type` + `timestamp`），body 用结构化 markdown（标题/列表/表格，便于 Agent 检索）。
- 遵守 OKF §9 conformance：`type` 必填；consumer 对未知字段要容忍保留（所以你放心加 `project_status` 这类扩展 key）。

**B. 记一笔变更 → 追加 `log.md`**（最新在前，按 ISO 日期分组）：
```markdown
# Directory Update Log

## 2026-07-15
* **Update**: 把 demo-project 的负采样教训补进 [data-leakage-pitfalls](/expertise/data-leakage-pitfalls.md)。
* **Creation**: 新建项目经验 [demo-project](/projects/demo-project.md)。
```

**两种更新策略（按成熟度演进）**：
- **MVP：人工触发**。你在对话里说"把这个教训记进 wiki"，Agent 执行"写 concept + 更 log"。先证明价值，不搞自动化。
- **进阶：sleeptime 后台压缩**。参考 Letta 的 sleeptime agent 思路——一个独立 Agent 定期扫"近期会话/代码变更"，提炼出应入 wiki 的条目，批量更新 concept + log。这样记忆会"自己长大"，但仍只存提炼后的内容。

**防膨胀的硬约束**：concept 文件只放"教训/决策/模式/检查清单"；会话原文绝不进 OKF，要存就放旁边的 `memory/`（向量/FTS 索引的原材料）。OKF bundle 保持精炼，是"工程师脑子里的笔记"，不是"聊天记录"。

### 9.5 Skill vs MCP —— 我的推荐：MCP 为主，Skill 做薄适配

这是你直接问的问题。结论先给：**把"记忆引擎"做成 MCP server，Skill 只做一个薄薄的适配/人格层。** 理由：

| 维度 | 纯 Skill | MCP server（推荐主体） |
|---|---|---|
| 跨 CLI 一致性 | 每个 CLI 的 skill 语法不同（Codex skill ≠ Claude 的 CLAUDE.md），逻辑要各写一遍 | **MCP 工具在三个 CLI 里调用方式一致**，写一次三处用 |
| 模型供应商 | OK（skill 只是提示词） | OK（MCP 不碰推理） |
| 状态/检索逻辑 | 塞在提示词里很别扭，难维护 | 代码实现 `wiki.search/read/write`，干净 |
| OKF 解析 | 提示词里解析 YAML 易出错 | 代码里用现成 YAML/MD 库解析 frontmatter，可靠 |
| 记忆更新原子性 | 难保证 | 代码里做"写 concept + 更 log"事务化 |

**职责分工**：
- **MCP server = 记忆引擎（脑里管知识的那部分）**：工具如 `wiki.search / wiki.read / wiki.write_concept / wiki.append_log / agent.recall / agent.whoami`。它负责读写 OKF bundle、解析 frontmatter、维护索引。这是跨 CLI 共用的真正后端。
- **Skill = 人格 + 触发（薄适配层）**：每个 Agent 一个 skill，内容只有三样：① persona（`AGENT.md` 那套角色定义）② "进项目/出项目"时该怎么调 MCP 工具的工作流提示 ③ 把不同 CLI 的触发方式做适配（Codex 用原生 skill，Claude Code 映射成 slash command + CLAUDE.md）。

为什么不是"纯 skill"：OKF 的 frontmatter 解析、`index.md` 的 progressive-disclosure 生成、`log.md` 的日期分组追加，这些用提示词做又脆又重复；放进 MCP 代码里一次写好、三端复用。
为什么 skill 不能省：persona 和"什么时候召回/沉淀"的工作流是提示词级别的，必须跟着 CLI 走。所以 skill 留着，但做薄。

> 一句话记忆点：**MCP 管"怎么读写知识"，Skill 管"这个 Agent 是谁、何时读写"。** 知识本体是 OKF 文件，三者各司其职，都和具体 CLI / 模型解耦。

### 9.6 这套怎么呼应你的原始诉求

- "存在形式就是 md 文件" → OKF 就是标准化的 md bundle，连目录约定都不用自己想。
- "CLI 对话里怎么用" → 9.3 的三时机：唤醒读 index、按需读 concept、沉淀写 concept+log。
- "记忆怎么更新" → 9.4：写 concept 必须带 frontmatter + 追加 log.md；MVP 人工触发，进阶 sleeptime 自动压缩。
- "skill 和 mcp 推荐哪个" → 9.5：MCP 做记忆引擎主体，skill 做薄人格/触发层，两者配合。
- "不爆上下文" → 记忆只存提炼后内容，原文进 `memory/`；进上下文的是检索切片。

> OKF 官方那句话最适合收尾：**"If you can cat a file, you can read OKF; if you can git clone a repo, you can ship it."** 你的多智能体记忆，就是一个个可 git、可 diff、可跨 CLI 跨模型读写的 OKF bundle。

