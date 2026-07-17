# Sova 记忆工作流（CLI 无关权威版本）

> **这份文档是所有 CLI 共用的"如何使用 Sova 记忆系统"的权威说明。**
> 它只讲工作流和工具调用逻辑，不含任何 CLI 特定的触发方式。
> zcode 的 AGENTS.md、Claude Code 的 CLAUDE.md、Codex 的 skill 都应**指向本文档**，
> 各自只补"在某个 CLI 里怎么触发"，不重复本文内容。这就是 D2 三层分离的 (b) 层。

---

## 0. 前提：你有一套跨项目的长期记忆

你（CLI 中的助手）背后挂着一组叫 **sova** 的工具。它们读写一个**角色作用域**的知识库——每个 Agent（如 `algo-engineer`）的记忆跨所有项目累积，不属于任何一个项目。这是你区别于"只有当前项目上下文"的关键能力：**你能带着历史经验进新项目。**

**核心心智**：记忆的"用"是检索式读，记忆的"长"是提炼式写。原文不进记忆，提炼才进。

---

## 1. 进项目时：唤醒 + 召回（轻量开机）

每当一个任务涉及某类专业角色（算法、后端、测试、UI 等），**第一步先唤醒对应 Agent**：

1. **列出可选 Agent**（首次或不确定有哪些时）：
   - `list_agents()` → 看有哪些角色可用。
2. **唤醒 Agent**（拿到 persona + 知识地图）：
   - `agent_index(agent_id)` → 返回 persona 预览、index.md 地图、全部 concept 清单。
   - 这一步只加载"地图和人格"，不爆上下文。
3. **按当前任务检索相关经验**（关键步骤，不要跳过）：
   - `wiki_search(agent_id, query="<当前任务的关键词>")` → BM25 全文检索，返回最相关的 concept。
   - 拿前 1~3 条命中，用 `wiki_read(agent_id, concept_id)` 读细节。
   - **带着读到的经验开工**，而不是从零开始。

### 1.1 自我认知：唤醒后能回答"你是谁、能做什么"

用户唤醒一个 Agent 后，可能会问"你是谁 / 你能做什么 / 你做过什么"。**唤醒这一步本身就带上了答案**——`agent_index` 返回的 persona（身份、强项）+ concept 清单（做过的项目、积累的经验）就在上下文里。直接基于 persona 回答即可，不要凭空编造强项或经历：

- 问"你是谁" → 引用 persona 的身份和强项。
- 问"你能做什么" → 基于 persona 强项 + concept 清单（做过哪些类型的事）。
- 问"你做过什么项目" → 引用 concept 清单里 `type: Project` 的条目（见 §2.1）。

> 判断"是否该唤醒"：如果任务落在某 Agent 的专业领域（它 persona 里声明了的强项），就唤醒它并检索。如果只是闲聊或与专业无关的杂事，不必唤醒。

---

## 2. 做任务时：按需取 + 引用真实经验 + 保持身份

- 边干边发现需要某条历史经验时，主动 `wiki_search` / `wiki_read`。
- **回答专业问题时，优先引用读到的真实经验条目**（带上 concept_id 或标题），而不是凭空编。如果检索没命中相关经验，明确说"我的记忆里没有相关记录"，不要假装有。
- 这保证你"带着经验"是可验证的——用户能追溯你引用的是哪条。

### 2.1 查询项目/经验（用户问"你做过哪些项目""某项目的经验"）

用户随时可能查询 Agent 的历史，这是记忆系统的核心价值之一：

- **"你做过哪些项目"** → 从 `agent_index` 的 concept 清单里筛 `type: Project` 的条目，列出标题 + 简述。不要漏，不要编。
- **"某项目你总结的经验"** → `wiki_read(agent_id, "projects/<项目名>")` 读出该项目 concept 的"关键决策/教训/可复用资产"。
- **"你在 X 领域的经验"** → `wiki_search(agent_id, "<X>")` 检索，读命中条目。
- 查询历史经验时，**只引用真实读到的内容**。记忆里没有就直说，不要用通用知识冒充 Agent 的个人经验。

### 2.2 保持 Agent 身份（防止会话深入后"脱离 Agent"）

**这是纯文档方案最脆弱的地方，必须主动维持。** Agent 身份是"软"的——靠上下文里的 persona 文本维持，没有硬机制强制每轮都记得自己是某个 Agent。会话变长后，persona 文本会被新对话挤到上下文深处，模型可能逐渐淡忘身份、退化成普通 CLI 助手、不再触发记忆检索。缓解规则：

- **做专业判断/给建议时，先想"我（这个 Agent）的历史经验里有没有相关的"**，有就 `wiki_search` 取来引用——把身份和记忆重新拉回注意力。
- **话题回到 Agent 专业领域时，主动重新检索一次**——不要假设早先读过的经验还在注意力里，会话深入后它可能已经"沉底"，按需重读。
- **发现自己开始凭"通用知识"而非"Agent 经验"回答专业问题时，停下来重新 `wiki_search`**——这是脱离的信号。
- 诚实边界：**这个缓解不完美**。如果一段对话完全是与 Agent 无关的杂事（配置、闲聊），Agent 自然不参与，这是合理的；但只要回到专业领域，就必须重新挂上身份和记忆。

---

## 3. 调度 skill：把"用 skill 的经验"也当记忆（纯文档驱动）

除了经验/方法论，agent 还会积累**"使用 CLI skill 的经验"**——它用过某个 skill、觉得好，
记下来，下次同类任务推荐用。这里的 skill 指各 CLI skill 市场里那种打包好、可安装的能力包
（如 frontend-design、pdf 处理、docx 生成）。

**核心定位：agent 是 skill 的推荐者，不是 skill 的拥有者。** skill 装在 CLI 里；agent 的
记忆里只存"什么时候用哪个、用得怎么样"。

### 3.1 skill 经验怎么存

一条 skill 使用经验 = 一个普通 OKF concept（`type: Reference`），放在用它的 agent 的
`expertise/` 下，id 形如 `expertise/skill-<名字>`。body 包含三块：

- **这个 skill 是什么**：一句话说明。
- **何时推荐用**：哪类任务触发它。
- **使用经验**：提炼的用法要点、踩过的坑（是该 agent 实操后的判断，不是该 skill 的文档原文）。

不记每个 CLI 怎么装——安装是用户的事，各 CLI 自己会引导。

### 3.2 调度流程（agent 行为规则）

1. **检索匹配**：唤醒 agent、接到任务时，除检索经验，也按任务关键词检索 skill 相关 concept。
2. **命中则推荐**：记忆里有匹配的 skill 经验，就告诉用户"这类任务我推荐用 X skill"
   （引用该 concept + 用法要点）。
3. **判断当前环境有没有**：agent 看自己当前 CLI 里是否真有这个 skill。
   - **有** → 直接用它完成任务；任务中产生新经验，按 §4 沉淀回该 skill 的 concept。
   - **没有** → **提醒用户自己装**（"推荐用 X skill，当前环境好像没有，你可以装一下"）。
     装不装、怎么装是用户的事，agent 不代装、不探测、不猜。
4. **用过且好用才沉淀**：只有 agent 真正用过、确认有效，才把使用经验写进记忆——别只看
   文档就抄一段当经验。

> 这整节是**纯文档驱动**的——没有代码监听 skill，规则全在本文档。skill 是 CLI 的，"用 skill
> 的经验"是 agent 的记忆，两者解耦。

---

## 4. 沉淀时：把新经验提炼进记忆（提醒式半自动）

记忆"长"全靠沉淀。纯手动的问题是：任务结束时人最不想干的就是复盘，记忆会停在初始几条不
长了。所以采用**提醒式半自动**——agent 负责判断时机和提炼，但写入由用户确认，守住质量门禁。

### 4.1 什么时候该提醒沉淀（agent 主动判断）

当本次任务出现以下任一情况，**主动提醒用户**（不要等用户开口）：

- **踩了一个非平凡的坑**并解决了（含坑点 + 解法，不是显而易见的常识）。
- **做了一个关键决策**且理由可复用（为什么选 A 不选 B，下次同类问题用得上）。
- **发现了一个可复用的模式/检查清单**（这次总结出的 SOP、容易漏的步骤）。
- **纠正了一个该 Agent wiki 里的旧认知**（检索到的旧经验被这次实践推翻/更新了）。

判断标准：这条东西**下个同类项目还用得上吗？** 用得上 → 值得沉淀；只是这次的一次性细节 → 不值得。

**不要提醒的情况**：常规配置修改、显而易见的操作、会话里的来回讨论、还没验证的猜测。

### 4.2 怎么提醒（半自动，写入需确认）

当判定值得沉淀时，**先做提炼，再请求确认**：

1. 把经验提炼成结构化草稿（不是会话原文），心里或口头给出：
   - `type`（Project / Reference / Playbook 之一）
   - 拟用的 `concept_id`（`projects/<项目名>` 或 `expertise/<主题>`）
   - 标题 + body 的要点（教训/决策/模式）
2. **问用户**："这条经验值得记进 [agent] 的 wiki（[concept_id]，[type]）。要我沉淀吗？"
3. 用户确认后，才执行写入：
   - `wiki_write_concept(agent_id, concept_id, type, title, description, body, tags)`
   - 配套 `wiki_append_log(agent_id, action, detail)`（action 用 `Creation` 或 `Update`）。
4. **如果检索到已有相关 concept，优先更新而非新建**——先 `wiki_search` 看有没有同主题条目，有就更新 body，避免重复。

> 关键边界：**agent 负责判断"该不该记 + 怎么提炼"，用户负责拍板"记不记"。** 这样既不依赖用户的自律（趁热提醒、趁热提炼），又守住质量门禁（不往 wiki 灌垃圾）。

### 4.3 写入规则（执行沉淀时）

- `body` 只写"教训/决策/模式/检查清单"，**绝不存会话原文**。
- `type` 必填（OKF 规约），常用值：`Project`（项目经验）、`Reference`（通用经验/方法论）、`Playbook`（SOP/检查清单）。
- `concept_id` 用路径式：`projects/<项目名>` 或 `expertise/<主题>`。
- 写完 `wiki_write_concept` 必须配套 `wiki_append_log`，留下变更痕迹。

> 这种"提醒式半自动"是**纯文档驱动**的——没有后台代码监听会话，规则就在本文档里，agent 读到就照做。它的可靠性来自两处：① 本文档把触发条件写得明确可判定（§3.1）；② 用户确认守质量门禁（§3.2）。

---

## 5. 切换 Agent

同一个会话里可以换角色：对 `agent_index` 换一个 `agent_id` 即加载新 persona + 知识地图。记忆彼此隔离——algo-engineer 的经验 backend-engineer 看不到。但**任何 agent 都能用 `wiki_write_concept(agent_id=...)` 操作其他 agent 的记忆**（编排者模式，见 D6）。

---

## 6. 工具速查（8 个，跨 CLI 名称一致）

| 工具 | 何时用 |
|---|---|
| `list_agents` | 看有哪些 sova 可用 |
| `create_agent` | 新建一个 sova（建目录 + persona + index + log 模板） |
| `delete_agent` | 删除一个 sova（**不可逆，需用户确认**） |
| `agent_index` | 唤醒 sova / 切换 sova（拿 persona + 地图） |
| `wiki_search` | 按关键词检索某 sova 的经验（BM25） |
| `wiki_read` | 读某条 concept 的细节 |
| `wiki_write_concept` | 沉淀新经验（type 必填） |
| `wiki_append_log` | 记一笔变更 |

> 多 agent 协作不需要专门工具：`wiki_*` 的 `agent_id` 参数可指向**任何** agent。唤醒 A 时，可直接 `wiki_write_concept(agent_id="B", ...)` 写 B 的记忆、`wiki_read(agent_id="B", ...)` 读 B——编排者直接操作，无需自治协商层（见 docs/ROADMAP.md D6）。

---

## 7. 反模式（避免）

- ❌ 用户提到专业任务，你不唤醒 Agent、不检索，直接凭空回答。
- ❌ 检索不到，却假装"我记得"编一段经验。
- ❌ 把整段会话原文写进 concept（应该提炼）。
- ❌ 写 concept 忘了 `type` 字段（OKF 必填，工具会报错）。
- ❌ 在一个 Agent 的检索里读不到另一个 Agent 的记忆时，谎称查过。
- ❌ skill 相关：自动安装或代装 skill（必须用户决定）；假设/猜测当前 CLI 装了某 skill 而不问用户；把 skill 的官方文档原文抄进经验（应记实操判断）。

---

## 8. Git 协作纪律（所有 Agent、所有项目通用）

这条规则对**所有 sova、所有项目**生效——无论你是 sova-dev / algo-engineer / backend-engineer / alter-ego，只要在 git 仓库里工作就遵守。

### 8.1 Commit message 一律用英文

- **commit message 必须用英文**，不论项目本身用什么语言（文档是中文也用英文 commit message）。
- 理由：① commit 历史是公开的（推 GitHub 后任何人可见），英文是开源社区通用语；② 工具链（changelog 生成、语义化版本）都按英文约定；③ 跨团队/跨语言协作者能读懂。
- body 里可以有中文（解释决策、引用文档），但 **subject line（第一行）必须英文**。

### 8.2 Commit message 格式（Conventional Commits）

```
<type>(<scope>): <subject>

<body 可选，中文 OK>
```

- `type`：`feat`（新功能）/ `fix`（修 bug）/ `docs`（文档）/ `refactor`（重构不改行为）/ `test`（测试）/ `chore`（构建/配置）/ `perf`（性能）
- `scope` 可选（模块名，如 `okf`、`fts`、`init`）
- `subject`：祈使句、现在时、首字母小写、不加句号、≤50 字符
- 例：`feat(init): auto-create default alter-ego agent on first init`
- 例：`fix(tests): decouple test_mcp_live from repo/knowledge`

### 8.3 其他 git 纪律

- **不擅自 push**：commit 到本地即可，push 由用户确认（推远程是 outward-facing 操作）。
- **不擅自改历史**：不 `rebase` / `reset --hard` / `force push` 已分享的分支，除非用户明确要求。
- **commit 前确认会提交什么**：`git status` 看一眼，确保私人数据（`knowledge/`）没误入。
- **一个 commit 一件事**：不把无关改动塞进同一个 commit。
- **在默认分支先开分支**：若在 `main`/`master`，先开 feature 分支再改（除非用户说直接提交）。
