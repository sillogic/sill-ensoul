# Sill-Ensoul 设计文档

> ⚠ **本文是设计阶段的探索性文档**，记录了设计过程中的思考与权衡（含被否决的方案）。
> - §3.3 / §4.1 / §4.3 是早期草案（skill 形态、目录结构、whoami 绑定），实际实现以代码（`ensoul/`）为准；
> - §7 Phase 3 提到的"sleeptime 全自动蒸馏"**经评估已否决**，提醒式半自动是终态设计（见 ROADMAP H2）；
> - §8 的开放问题已全部决策（见 ROADMAP D1-D6）。
>
> **当前权威设计决策以 [ROADMAP.md](ROADMAP.md) §2（D1-D6）为准。** 本文保留是因为 §2 的竞品调研和 §9 的 OKF 论证仍有参考价值。

---

## 1. 目标与约束

**目标**：一套与 CLI、模型供应商都解耦的多智能体系统，每个 agent 自带长期记忆（Wiki），能跨 ensouler 协作。

**核心诉求**：让一个专业角色（如算法工程师）在新项目里能带着历史项目的经验工作，而不是只有当前项目记忆。

### 1.1 五条硬约束

1. **长期记忆 + Wiki**：每个 agent 维护自己的知识库，跨会话、跨项目保留经验。
2. **轻量、不爆上下文**：进上下文的是"提炼后的经验 / 教训 / playbook"，不是历史项目的全部记忆。
3. **CLI 无关**：在 Codex / Claude Code / OpenCode 等里都能用，不绑死某个工具。
4. **模型供应商无关**：能接任意模型供应商（这是项目要解决的核心痛点之一——现有托管方案往往锁定供应商）。
5. **跨 agent 知识共享**：多个角色 agent 各自演进时，需要能分发结论、共享信息。

约束 3、4 合在一起基本决定了架构形态：**核心逻辑必须放在"框架无关"的层（文件 + MCP），而不是某个 agent 运行时里。**

---

## 2. 现有方案调研

### 2.1 记忆 / Wiki 框架（单 agent 长期记忆）

| 项目 | 形态 | 核心机制 | 适配度 |
|---|---|---|---|
| **mem0ai/mem0** | 记忆层（嫁接到自己的 agent） | 向量库 + 实体链接 | 中：可当记忆后端 |
| **letta-ai/letta**（原 MemGPT） | 完整有状态 agent 平台 | 自编辑文本 memory block（常驻上下文）+ 归档向量记忆 + 文件系统；含 sleeptime 后台整理 | 低：本身是运行时，会绑死 agent 形态 |
| **getzep/graphiti** | 记忆层（嫁接） | 实时知识图谱，带时间戳的关系 | 中：关系复杂时再上 |
| **topoteretes/cognee** | 记忆层（嫁接） | 自托管知识图谱，实体抽取 pipeline | 中 |
| **microsoft/graphrag** | RAG 系统 | 图结构 RAG，偏文档问答 | 低：偏静态文档 |
| **getzep/zep** | 记忆服务 | 对话式记忆 | 低 |

> Star 数变化快，上表不再列具体数字；调研时（2026 中）mem0 与 graphiti 在万星级，letta/cognee/graphrag 同梯队。

**关键设计分野**：

- **letta 是"替你跑 agent 的框架"**；**mem0 / graphiti / cognee 是"嫁接到自己 agent 上的记忆层"**。
- 对于"CLI 无关 + 模型无关"的需求，**应该选记忆层、而不是 agent 运行时**，否则记忆系统会绑架 agent 形态。

**一个重要的反面证据**：letta 2025.08 的《Is a Filesystem All You Need?》与社区共识——**很多时候文件 + grep 就够了，专门上知识图谱会带来不成比例的复杂度**。"最小够用图"是务实原则。

### 2.2 多 agent 协作 / 共享知识

- **Orchestrator-Worker（编排者-执行者）**：生产环境主流拓扑，**信任边界是承重墙**。
- 拓扑家族：pipeline / supervisor-worker / peer handoff（对等交接）/ debate-and-judge（辩论+裁判）。
- **A2A（Agent2Agent）协议**（Google）：Agent Card（`/.well-known/agent.json`）做能力发现 + Task Delegation 生命周期。是 agent 间通信的事实标准。
- **Blackboard（黑板架构）**：共享知识空间的经典模式。
- 协议分工：**MCP 管 agent↔工具，A2A 管 agent↔agent，REST 管简单调用**。

**一个生产教训**：业界多次出现"多个自治 agent 为抢共享资源互相干扰"的事故。根因往往不是 agent 出错，而是**激励/边界结构没设计好**。这印证了"边界协调需要显式机制，不能靠默契"。

---

## 3. 关键设计判断

1. **记忆 = 文件 Wiki（Markdown）为主，向量/图为辅。**
   - Markdown 是模型无关、CLI 无关、可 diff、可 git、人可读的最小公分母。
   - 检索先用 SQLite FTS5 全文索引；只有当"关系/时序"真的复杂时再上 graphiti。
   - 这天然满足"不爆上下文"：Wiki 里是**提炼后的经验**，不是历史会话原文。

2. **逻辑层 = 一个轻量 MCP server。**
   - MCP 被 Codex / Claude Code / OpenCode 普遍支持，是天然的"跨 CLI 工具接口"。
   - 模型推理发生在各 CLI 自己的供应商里，**MCP 只管数据与工具，不碰推理** → 自动满足"模型供应商无关"。

3. **适配层 = 薄壳（每个 CLI 一份）+ 共享工作流文档。**
   - 早期草案设想"每个 agent 一个 skill"，落地后简化为：**CLI 无关的工作流规则写一次**（`WORKFLOW.md`），**每个 CLI 放一份薄壳**（`AGENTS.md`/`CLAUDE.md`）只引用它、补"怎么触发"。这是 D2 三层分离的 (b)+(c) 层（详见 ROADMAP）。
   - 在 Codex 里是原生 skill；在 Claude Code 里映射成 `CLAUDE.md`；在 zcode 里是 `AGENTS.md`。**同一份 OKF Wiki、同一套 MCP 工具，多个 CLI 共用。**

4. **与托管方案的差异**：托管方案（如 Qwake）把"带记忆的 agent"做成运行时（因此锁供应商）；本项目把同样的能力拆成 **MCP（工具）+ 文件 Wiki（记忆）+ 薄壳（人格/适配）**，托管层被掏空，推理权回到用户手里。

---

## 4. 架构：MCP + 文件 Wiki + 薄壳

```
  Claude Code / Codex / zcode / Cursor   ← 推理在各自 CLI 的模型供应商，不锁死
           |  加载 persona + wiki 切片（薄壳：AGENTS.md / CLAUDE.md）
        sill-ensoul-mcp (MCP server, 8 工具, 读写检索)
           |  读写
  knowledge/agents/<id>/   ← 每个 ensouler 一个 OKF bundle（markdown 文件）
```

### 4.1 存储层

> 下面的目录结构是早期草案。**实际落地形态以代码为准**（见 `ensoul/okf.py` 的 `_default_kb_root` / `agent_index` 等），主要差异：没有独立的 `wiki/` 子目录和 `memory/` 向量层、`shared/` 已随 D6 废弃、persona 是 `AGENT.md`。

```
<kb_root>/                                 # 全局 KB（平台感知，不在任何项目仓库内）
  agents/
    <agent_id>/                            # 一个 agent = 一个目录（OKF bundle）
      AGENT.md                             # persona：角色、强项、工作方式
      index.md                             # 知识地图（progressive disclosure）
      log.md                               # 更新历史（按日期分组）
      playbook.md                          # SOP / 检查清单（type: Playbook）
      expertise/                           # 跨项目沉淀的通用经验（type: Reference）
        <topic>.md
      projects/                            # 每个历史项目的"提炼后经验"（type: Project）
        <project>.md
```

**写作规则（保证不爆上下文）**：Wiki 只写"教训 / 决策 / 模式 / 检查清单"，不存会话原文。项目结束/里程碑时，把值得留的东西提炼成 `projects/<id>.md` 或更新 `expertise/<topic>.md`，并在 `log.md` 记一笔。

### 4.2 引擎层：MCP server 工具集

> 落地后的实际工具集（8 个，见 `ensoul/server.py`）。早期草案曾列 `comm.*`/`boundary.*` 等 Phase 2 工具，**这些已随 D6 废弃自治协商而删除**——多 agent 协作改走编排者模式（任何 agent 用 `wiki_write_concept(agent_id=...)` 直接操作他人记忆），不需要专门工具。

```
list_agents()                              # 列出所有 ensouler
create_agent(agent_id, name, persona)      # 新建 ensouler（目录 + persona + index + log）
delete_agent(agent_id)                     # 删除（不可逆）
agent_index(agent_id)                      # 唤醒/切换：persona 预览 + 知识地图 + concept 清单
wiki_search(agent_id, query, limit)        # FTS5 + BM25 全文检索（CJK 按字分词）
wiki_read(agent_id, concept_id)            # 读一条 concept
wiki_write_concept(agent_id, ...)          # 沉淀新经验（type 必填）
wiki_append_log(agent_id, action, detail)  # 记一笔变更到 log.md
```

`wiki_write_concept` 内部存"提炼后内容"而非"堆原文"——body 只写教训/决策/模式，这是控制上下文膨胀的关键（见 §9.4 防膨胀硬约束）。

### 4.3 agent 唤醒流程

1. MCP server 启动时读 `ENSOUL_KB`（或平台默认路径）定位全局 KB。
2. CLI 触发时指定 `agent_id`（如对 CLI 说"唤醒 algo-engineer"）。
3. `agent_index(agent_id)` 加载该 agent 的 `AGENT.md`（persona）+ `index.md`（地图）+ concept 清单进上下文。
4. 之后该 agent 既干活、又能随时 `wiki_search`/`wiki_write_concept` 把经验沉淀回自己的知识库。

---

## 5. 跨 agent 知识共享（编排者模式，原 Phase 2 已废弃）

> **历史**：本节原设计"黑板 + A2A 协商 + 边界契约"的自治多 agent 方案（registry 所有权声明 / boundary_scan 冲突检测 / comm 谈判 / boundary_record 落契）。**该方案已废弃**，代码（`registry.py`/`comm.py`）和 6 个 MCP 工具已删除。废弃理由见 ROADMAP.md 的 **D6 决策**。

**现在的方案——编排者模式**：多 agent 协作走"编排者用工具直接操作"模型，不走"agent 自治协商"：

- **任何 agent 都能操作其他 agent 的记忆**：`wiki_write_concept(agent_id="B", ...)` / `wiki_read(agent_id="B", ...)` / `wiki_search(agent_id="B", ...)` 的 `agent_id` 参数可指向任意 agent。唤醒 A 时，可直接写 B 的记忆。
- **分发结论 = 写各方记忆**：编排者规划完，调 `wiki_write_concept` 把结论写进相关 agent 各自的记忆，它们下次唤醒即带着该结论。
- **agent 间"交流" = 通过记忆文件留言**：写一个 concept 给对方 / 读对方的 concept。agent 不是常驻进程，没有"实时对话"——"留言 + 下次唤醒读"就是模型里的交流方式。

**为什么废弃自治协商**：sill-ensoul 是"被唤醒才活、记忆跨项目累积"的角色，不是自主运行实体。"agent 自治协商边界"和这个模型有张力（没常驻进程怎么协商？）。编排者模式反而贴合：编排者（人或任一 agent）用现有工具操作多 agent 记忆，不需要 registry 防冲突（编排者知道在干什么）、不需要 boundary_scan（没自治抢资源）、不需要 comm 谈判（直接写结论）。

---

## 6. 与托管方案对比

| 维度 | 托管方案（如 Qwake） | 本项目 |
|---|---|---|
| 形态 | 托管的有状态 agent 运行时 | MCP + 文件 Wiki + 薄壳 |
| 记忆 | 平台内部 | **用户自己的 git 仓库**，可迁移、可审计 |
| 模型 | 锁平台供应商 | **推理在各 CLI 的供应商**，MCP 不碰推理 → 任选 |
| CLI | 锁平台 | Codex / Claude Code / zcode / OpenCode 通吃 |
| 跨 agent | 平台内置 | 编排者模式，用户自己掌控 |

代价：用户要自己装这个 MCP server 和薄壳。换来的是**没有供应商锁定 + 记忆完全归用户**。

---

## 7. 落地路线图

- **Phase 0 — 单 agent 文件 Wiki**：定一个 `algo-engineer` 的目录结构 + `AGENT.md`，用纯 Markdown + grep 验证"带经验进新项目"跑得通。先不上 MCP，证明价值。✅ 已完成
- **Phase 1 — MCP server（核心）**：实现 `wiki_search/read/write_concept` + `agent_index`（SQLite FTS5）。在各 CLI 里挂上这个 MCP，把薄壳放进各自的指令文件。✅ 已完成（8 个工具，见 `ensoul/server.py`）
- ~~**Phase 2 — 多 agent + 黑板**~~：~~加 `shared/registry.json` + `boundary.scan()` + `comm.*`~~ **已废弃**，改走编排者模式（D6），不需要自治协商基础设施。
- **Phase 3 — 按需升级**：关系/时序真的复杂了再上 graphiti 做知识图谱。~~加 sleeptime 后台整理流程~~ → **sleeptime 全自动蒸馏经评估否决**（见下）。

> **关于 sleeptime 全自动蒸馏（原 Phase 3 一部分，已否决）**：曾设想参考 letta 的 sleeptime agent 做"后台自动压缩会话、自动写入 wiki"。**经评估否决，不做。** 理由：① LLM 自动判断"什么值得记"容易产出垃圾条目，稀释检索质量（与 H1 刚修好的规模红利冲突）；② 是个有状态的后台子系统，与"CLI 解耦、被唤醒才活"的哲学有张力。**终态设计是"自动 + 事后告知"**——agent 主动判断时机 + 提炼 + 直接写入，写后告知用户（用户保留事后否决）。质量门禁靠触发条件明确可判定 + body 只写蒸馏纪律 + 事后否决，不靠写前确认。详见 ROADMAP H2。

**原则：先用文件证明价值，再用 MCP 解耦 CLI，最后再考虑图谱。** 不要一上来就 mem0 + graphiti + 多 agent 全家桶。

---

## 8. 已决策的开放问题

> 设计阶段列出的开放问题，现已全部决策。记录于此供追溯。

1. **知识根放哪** → **全局 KB**（`%LOCALAPPDATA%/ensoul/knowledge` 等，平台感知；`ENSOUL_KB` 可覆盖）。不绑定任一项目仓库（H4）。
2. **检索技术选型** → **先 FTS5**（SQLite FTS5 + BM25 + CJK 按字分词，零依赖）。向量/图谱留作"关系时序复杂时"的未来选项，目前不需要。
3. **整理流程谁来做** → **自动 + 事后告知**（agent 判断时机 + 提炼 + 直接写入，写后告知用户）。全自动 sleeptime 已否决（见 §7）；写前确认已改为写后告知（触发条件已明确到 agent 能判定，写前问大概率走形式）。
4. **边界协调** → **编排者模式**（D6）：任何 agent 用 `wiki_write_concept(agent_id=...)` 直接操作他人记忆，不需要自治协商。协调者是编排者（人或任一 agent）。
5. **MCP server 语言** → **Python**（`mcp` + `pyyaml`，两个依赖）。

---

## 9. 记忆格式定案：采用 Google OKF（Open Knowledge Format）

> Karpathy 推荐的 OKF（Google Cloud 2026.06，`GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`）把"LLM-wiki"模式标准化了。它正好就是想要的"存在形式就是 md 文件"。

### 9.1 为什么 OKF 是这个项目记忆层的正确答案

OKF 把记忆定义为**一个目录的 markdown + YAML frontmatter**，核心规约就三句话：

- **一个 concept 一个 .md 文件**，文件路径 = concept 的身份（如 `projects/demo-project.md`）。
- **frontmatter 只强制一个字段 `type`**，其余（`title/description/resource/tags/timestamp`）可选；可以自由加任何扩展 key。
- **只有两个保留文件名**：`index.md`（目录索引，支持 progressive disclosure，无 frontmatter）和 `log.md`（按日期分组的更新历史，最新在前）。

它有两条设计原则，直接命中需求：

1. **Producer/Consumer 独立**：谁写知识、谁读知识可以完全分开。一个人手写的 bundle 能被 agent 读；一个 LLM 生成的 bundle 能被另一个 LLM 查询。**格式就是契约，两端工具各自可换。** ← 这正是"CLI 无关 + 模型无关"的官方背书。
2. **Format, not platform**：不绑定任何云、数据库、模型供应商、agent 框架；永远不需要私有账号或 SDK 就能读写。"If you can cat a file, you can read OKF."

换句话说，"文件 Wiki"这个设想，**现在有一个有官方规范、有参考实现、有人在做可视化器的标准格式**。直接用，不用自己发明目录约定。

### 9.2 一个 agent 的 OKF bundle 长这样

每个 agent 的知识库 = 一个 OKF bundle（一个目录）：

```
agents/algo-engineer/                 # 一个 agent = 一个 OKF bundle
  index.md                            # ★ Wiki 地图：progressive disclosure，先看这个
  log.md                              # ★ 按日期的更新历史（记忆怎么变的）
  AGENT.md                            # persona（type: Profile，约定扩展用）
  playbook.md                         # type: Playbook —— SOP / 检查清单（最高频复用）
  expertise/                          # type: Reference —— 跨项目沉淀的通用经验
    transformer-finetuning.md
    data-leakage-pitfalls.md
  projects/                           # type: Project —— 每个历史项目的"提炼后经验"
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
---

# 关键决策
- 召回用双塔，精排用 GBDT+DNN 串联，理由是……

# 教训（不是会话原文，是提炼）
- 负采样比例 1:4 时 AUC 最高，1:10 反而过拟合
- 见 [data-leakage-pitfalls](/expertise/data-leakage-pitfalls.md)
```

文件之间用**普通 markdown 链接**互相关联，整个 bundle 就是一张"比目录树更丰富的知识图"（OKF §5 cross-linking）。

### 9.3 在 CLI 对话里"怎么用"记忆（使用模式）

核心思路：**把 OKF bundle 当成 agent 的外部硬盘。对话里不靠"记得"，靠"读得到"。** 分三个时机：

**① 进项目时（唤醒 / 召回）**
在 CLI 里触发、指定 agent（如 `@algo-engineer`）。薄壳做两件事：
- 读该 agent 的 `index.md` + `AGENT.md`（persona）进上下文 —— 这是"轻量开机"，只有地图和人格，不爆上下文。
- 按当前任务，检索命中 1～3 篇最相关 concept（如 `playbook.md` + 某个 `projects/*.md`）切片进上下文。
等价于"工程师来新项目前，先翻一眼自己的经验笔记"。**进上下文的永远是"提炼后的切片"，不是历史会话原文。**

**② 做任务时（按需取）**
Agent 边干边发现需要某条经验时，主动 `wiki_read` 某篇 concept；或发现一个反复出现的坑时，把它沉淀进 wiki（见下）。对话本身不存进记忆，记忆里只留"被显式提炼的条目"。

**③ 出项目/里程碑时（沉淀 / 压缩）**
项目告一段落，agent 会**主动提醒**"这次有值得记的东西"，确认后它把值得留的内容**新写或更新一个 concept 文件**，并在 `log.md` 记一笔。下次这个 agent 进新项目，`index.md` 和检索就能带上这次的经验。

> 这是"提醒式半自动"——agent 负责判断时机和提炼，用户负责拍板写不写。曾设想的"sleeptime 后台自动压缩"经评估否决（理由见 §7），半自动是终态设计。

> 一句话：**记忆的"用"是检索式读，记忆的"长"是提炼式写。原文不进记忆，提炼才进。** 这就是控制上下文膨胀的根本机制。

### 9.4 记忆怎么更新（写入协议）

OKF 的 `log.md` 天生就是为"记忆更新历史"设计的。更新分两类操作：

**A. 新增/深化一条经验 → 写或更新某个 concept 文件**
- 写入时必须带 frontmatter（至少 `type` + `timestamp`），body 用结构化 markdown（标题/列表/表格，便于 agent 检索）。
- 遵守 OKF §9 conformance：`type` 必填；consumer 对未知字段要容忍保留（所以可以放心加 `project_status` 这类扩展 key）。

**B. 记一笔变更 → 追加 `log.md`**（最新在前，按 ISO 日期分组）：
```markdown
# Directory Update Log

## 2026-07-15
* **Update**: 把 demo-project 的负采样教训补进 [data-leakage-pitfalls](/expertise/data-leakage-pitfalls.md)。
* **Creation**: 新建项目经验 [demo-project](/projects/demo-project.md)。
```

**两种更新策略**：
- **自动 + 事后告知（终态设计，已落地）**：agent 在任务中踩了非平凡的坑/做了可复用决策时，**直接提炼并写入** wiki，写后告知用户写了什么（concept_id + 标题 + 一句话要点）。既不靠用户自律去记（趁热自动沉淀），又保留事后否决（用户可让删/改）——质量门禁靠触发条件明确可判定 + body 只写蒸馏纪律 + 事后否决，不靠写前确认。
- ~~**进阶：sleeptime 后台压缩**~~ → **经评估否决**。理由见 §7：LLM 自动判断"什么值得记"易产垃圾稀释检索（撞 H1），且有状态后台子系统与"CLI 解耦、被唤醒才活"哲学有张力。半自动已足够。

**防膨胀的硬约束**：concept 文件只放"教训/决策/模式/检查清单"；会话原文绝不进 OKF bundle。OKF bundle 保持精炼，是"工程师脑子里的笔记"，不是"聊天记录"。

### 9.5 MCP 与薄壳的职责分工

**把"记忆引擎"做成 MCP server，薄壳只做适配/人格层。** 理由：

| 维度 | 纯薄壳（提示词） | MCP server（主体） |
|---|---|---|
| 跨 CLI 一致性 | 每个 CLI 的语法不同（Codex skill ≠ Claude 的 CLAUDE.md），逻辑要各写一遍 | **MCP 工具在各 CLI 里调用方式一致**，写一次多处用 |
| 模型供应商 | OK（薄壳只是提示词） | OK（MCP 不碰推理） |
| 状态/检索逻辑 | 塞在提示词里很别扭，难维护 | 代码实现 `wiki_search/read/write`，干净 |
| OKF 解析 | 提示词里解析 YAML 易出错 | 代码里用现成 YAML/MD 库解析 frontmatter，可靠 |
| 记忆更新原子性 | 难保证 | 代码里做"写 concept + 更 log"事务化 |

**职责分工**：
- **MCP server = 记忆引擎**：工具如 `wiki_search / wiki_read / wiki_write_concept / wiki_append_log / agent_index`。负责读写 OKF bundle、解析 frontmatter、维护索引。跨 CLI 共用的后端。
- **薄壳 = 人格 + 触发**：内容只有三样：① persona（`AGENT.md` 的角色定义）② "进项目/出项目"时该怎么调 MCP 工具的工作流提示 ③ 把不同 CLI 的触发方式做适配。

> 一句话记忆点：**MCP 管"怎么读写知识"，薄壳 管"这个 agent 是谁、何时读写"。** 知识本体是 OKF 文件，三者各司其职，都和具体 CLI / 模型解耦。

### 9.6 这套怎么呼应原始诉求

- "存在形式就是 md 文件" → OKF 就是标准化的 md bundle，连目录约定都不用自己想。
- "CLI 对话里怎么用" → §9.3 的三时机：唤醒读 index、按需读 concept、沉淀写 concept+log。
- "记忆怎么更新" → §9.4：写 concept 必须带 frontmatter + 追加 log.md；提醒式半自动。
- "MCP 和薄壳 推荐哪个" → §9.5：MCP 做记忆引擎主体，薄壳做人格/触发层。
- "不爆上下文" → 记忆只存提炼后内容；进上下文的是检索切片。

> OKF 官方那句话适合收尾：**"If you can cat a file, you can read OKF; if you can git clone a repo, you can ship it."** 多 agent 记忆，就是一个个可 git、可 diff、可跨 CLI 跨模型读写的 OKF bundle。
