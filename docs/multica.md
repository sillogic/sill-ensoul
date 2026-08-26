# Sill-Ensoul × Multica 平台集成指南

> 面向对象：想把 sill-ensoul 长期记忆接到 Multica（AI 原生团队工作区）的人 —— 无论是
> 平台管理员、要绑分身的 Multica agent，还是从零搭建的「新人」。
>
> 本文是**公开、可版本化的集成知识**：唤醒块模板、降级规则、批量上架模式、踩坑记录全部
> 在这里，替代私有 KB 里的零散经验。核心结论一句话：**代码零分叉，集成 = 平台侧配置 +
> 一份薄壳**（详见下文「为什么不分叉」）。

---

## 1. 定位：记忆层 vs 编排层，互补不打架

ensoul 与 Multica **无结构性冲突，分层互补**：

| 层 | 职责 | 实例 |
|---|---|---|
| **记忆/身份层** | 角色作用域 OKF wiki，跨项目跨会话 | ensoul（本机 KB，私有） |
| **编排/执行层** | issue 分派 / 评论 / status / runtime / skill / 权限 / 调度 | Multica（团队共享） |

- ensoul 补 Multica 的「每 run 从零开始」短板；Multica 补 ensoul 的「无调度」短板。
- 两套记忆**物理隔离、写路径独立**：Multica 记忆（评论 + metadata + chat）在平台数据库、
  团队可见；ensoul 记忆（OKF 文件）在本机 KB、私有。唯一交互是 Multica run 里的 agent
  经 MCP 工具**单向调用** ensoul —— 不是共享状态，没有「打架」的物理基础。
- 分工纪律（非代码）：团队可见知识进评论；可复用经验蒸馏进 KB；评论带一句 concept_id
  告知。

## 2. 为什么不分叉（决策 1）

单分支（master）足够，**不建平台分叉**。依据：

- 整个仓库 0 行 multica 相关代码，依赖仅 `mcp` + `pyyaml`。multica 支持 = 平台侧配置
  （MCP 注册 + agent 分配，配置活在平台里不进仓库）+ 一份薄壳（`shells/multica/AGENTS.md`）。
  代码零分叉，专门分支里没有任何差异 → 纯维护负担。
- 单分支同时服务两类用户：无 multica 用户走自己 CLI 的 MCP 配置；multica 用户走平台
  MCP 库注册 / pi 扩展。运行时代码路径不分叉。
- **判断模板**：要不要为某平台/客户分叉？先 grep 仓库有没有该平台相关代码；集成若只是
  配置 + 薄壳，一律主分支 + 文档，不分叉。

## 3. MCP 接入路径（文档 = 现实，2026-08 对齐）

两条路径，**平台库路线 = 正式主路径（SIL-26 定案）**；pi 扩展路线 = Pi runtime 的当前交付通道 + CLI 本地兑底。双路径共存由构造保证兼容（见 §3.1）：

| 路径 | 状态 | 说明 |
|---|---|---|
| **平台 MCP 库路线**（主路径） | ✅ 设计定案 · ⏳ 待 owner 注册 | `multica workspace mcp add` + `multica agent mcp add`，任何 runtime CLI 可用。server 条目（`cmd /c sill-ensoul-mcp`）已实测握手通过（initialize + 8 工具 + 调用）；**`workspace mcp add` 是 admin/owner 操作，agent run 的 task-scoped token 会被拒** —— 注册需 workspace owner 执行（UI 或自己的 CLI），命令见下 |
| **pi 扩展路线**（兑底/当前交付） | ✅ 实装 | `~/.pi/agent/settings.json` → `cmd /c sill-ensoul-mcp`，经 `extensions/mcp-bridge.ts` 把 8 个 ensoul 工具暴露给 run 内 agent（Pi runtime 当前实际交付通道；pi 无原生 MCP） |

**注册命令（owner 执行一次；SIL-26 实测权限模型）**：

```bash
# 条目（已实测：initialize OK + 8 工具 + 调用）
# {"type":"stdio","command":"cmd","args":["/c","sill-ensoul-mcp"]}
multica workspace mcp add sill-ensoul --server-config-file ./entry.json
multica agent mcp add <agent-id> <server-id>   # server-id 取 workspace mcp list
```

版本对齐（SIL-26 复核）：pip 安装 `sill-ensoul` v0.3.0 == 仓库 v0.3.0，无漂移。

**新人注意**：SETUP.md 的「Multica adaptation」一节现按双路径写（平台注册 + pi 扩展
均已说明）；装好后用 `multica agent get` 确认 agent 能调 `list_agents` / `agent_index`。

### 3.1 三类用户兼容性 + 嵌套 CLI 约定（SIL-26 设计输入，2026-08）

用户追问「只用 multica / 只用 CLI / 两者都用」三类用户怎么兼容，接受两处都装 ensoul
MCP，但担心「装了 ensoul 的 multica 调装了 ensoul 的 CLI」出问题。**结论：兼容性由
构造保证，无需为任何一类做专门分支或新代码**：

- **数据完整性层 = 已解决（非风险）**：server.py 完全无状态（8 工具全部显式传
  agent_id，无全局 session/active-agent，stdio 不占端口）—— N 个 MCP 客户端 = N 个
  独立进程读写同一文件库。写路径全部在 D9 锁 + 原子写内（每 agent 目录 `.lock.db` +
  `BEGIN IMMEDIATE` 跨进程互斥 + `_atomic_write_text` os.replace），并发写被串行化，
  不会半截/丢更新/坏索引；search 前先同步索引且索引维护在锁内；init 幂等（已存在
  skip）。
- **纪律层 = 真正的剩余摩擦点**（锁防损坏、防不了两个「心智」以同一 agent_id 同时
  写作），两条约定：
  1. **嵌套一层写**：multica runtime 内嵌套的 CLI 只当执行工具，记忆层归外层 agent
     管（已持 8 工具）；嵌套会话按各 CLI 机制禁用 ensoul（配置动作，非代码分叉）。嵌
     套确实要用 → 换不同 agent_id，或接受去重（蒸馏规则先 search 再写天然防重）；
     `ENSOUL_KB` 可整体切库做完全隔离，但那是隔离非共享，一般不要。
  2. **同一命令注册**：平台侧与 CLI 侧用同一注册命令（`cmd /c sill-ensoul-mcp`），
     一台机器一个 server 版本一个 KB，消灭版本漂移。
- **三类用户落法**：只用 multica = 平台库注册 + agent 分配（工具直调）；只用 CLI =
  各 CLI 自配（现状）；两者都用 = 同一二进制同一 KB 两处配置共存，错开使用零冲突、
  同时跑（autopilot + 本地 CLI）有锁兑底，守「嵌套一层写」约定即可。

## 4. 分身绑定（决策 4/5/6）

### 4.1 绑定机制 = instructions 唤醒块

Multica 与 ensoul 之间**不存在平台级绑定字段**；1:1 靠 agent 的 `instructions` 里的
**唤醒块**实现。模板见 [shells/multica/AGENTS.md](../shells/multica/AGENTS.md) ——
append 进 instructions、替换 `<分身id>` 占位符即可，一次 `multica agent update` 写入
即生效（该 agent 此后每个 run 都加载）。

唤醒块四要素：

1. **绑定声明**：本 agent ↔ 分身 `<id>` 一对一，run 开始先切换到该分身。
2. **强制步骤**：`agent_index` → `wiki_search`（命中 `wiki_read`，无记忆明说）→ 保持
   分身身份引用真实 concept_id → 按沉淀规则自动蒸馏 + 事后告知。
3. **降级规则**（软约束，必带）：ensoul MCP 工具不可用 → 退回平台普通身份继续工作，
   最终评论说明「本次未切换到分身」；**不允许因工具缺失阻塞任务**。
4. **身份优先级**：平台行为契约（issue 工作流/评论纪律）优先；分身用于专业判断与记忆，
   不争抢 persona。

### 4.2 绑定流程固化为 skill：`ensoul-multica-binding`

绑定是高频重复流程（每次新建 agent 都走一遍），固化为 workspace 级 skill：

1. 读目标 agent 当前 instructions（**合并不覆盖**）；
2. `list_agents` 按领域匹配分身，无则 `create_agent`；
3. 生成唤醒块并入 instructions，`multica agent update` 写入；
4. `multica agent skills add <agent-id> --skill-ids <ensoul-multica-binding>` —— **新建
   agent 必做**，否则新 agent 在自己的创建对话里读不到 skill 不知道怎么绑；
5. 验证 + 告知。

### 4.3 name/description 同步（决策 6）

绑定收尾：`multica agent update <agent-id> --name "<分身id>" --description "<分身
AGENT.md 的 title/description>"` —— 让平台侧「看起来就是」那个分身（成员在 UI 里一眼
认出）。分身后续 persona 更新时按需再同步。

### 4.4 通过 SETUP.md 初始化（决策 7 + SIL-29 细化）

老用户把 SETUP.md 直接丢给 multica agent 对话即可初始化，无需专门 md（SIL-27 确认）。
SETUP.md 内「Multica adaptation」一节覆盖：平台 MCP 注册 / **创建默认分身 `alter-ego` 的
agent 并绑定**（唤醒块 + skill，SIL-29 起取代「改名接收 agent」）/ 验证。

- **首次安装（SIL-29）**：接收 SETUP.md 的 agent **不改名**、保持自己的 Helper 身份，负责
  **创建**一个名为 `alter-ego` 的新 agent —— instructions = 平台基础（复制接收 agent 的
  instructions）+ 唤醒块（`<分身id>` = `alter-ego`，模板见
  [shells/multica/AGENTS.md](../shells/multica/AGENTS.md)），runtime 选能调 ensoul MCP 工具
  的那个（Route A 任意 / Route B pi runtime），挂 `ensoul-multica-binding` skill（若
  workspace 已存在）。用户在 workspace 里直接与 `alter-ego` agent 对话即开始使用。
- **老用户**：更贴合 4.2 的绑定 skill（按领域匹配已有分身 1:1 绑定 + name/description
  同步），非一律 alter-ego。

## 5. 批量上架模式（决策 8）：分身 → agent + 项目

把本机已有分身系统搬进 Multica 的第一批上架，按四步：

1. **分身枚举**：`list_agents` 列出所有 OKF agent（本机 `%LOCALAPPDATA%/ensoul/knowledge/
   agents/`，每个子目录一个分身）；排除 `.obsidian` 等非 agent 目录。
2. **agent 创建**：每个分身
   `multica agent create --name <分身id> --description <AGENT.md title/description>
   --instructions <唤醒块> --runtime-id <装了 pi mcp-bridge 的 runtime> --model <同现有>
   --permission-mode public_to --public-to-workspace`，然后
   `multica agent skills add <id> --skill-ids <ensoul-multica-binding>`（4.2 步骤 ④ 必做）。
3. **项目扫描 = 分身记忆的 `projects/` 概念**：每个 `agents/<id>/projects/*.md`
   （type: Project）就是一个项目。合并口径：同一代码仓的多个 Project concept 合并成一个
   平台项目；纯状态/协作接口型 concept 不单开项目。
4. **绑定 + 本地文件夹**：`multica project create --title <项目名> --lead <分身 agent 名>`
   把 agent 设为 lead；`multica project resource add <project-id> --type local_directory
   --daemon-id <本机 daemon> --local-path <绝对路径> --execution-mode worktree|in_place`
   关联本地文件夹（git 仓用 worktree，非 git 目录用 in_place）。

之后新分身/新项目按同一模式增量创建。

## 6. 已知摩擦点与对策（SIL-20 二次评估，2026-08）

实测运行态验证：核心模型无问题，**保持现状（P0）**。4 个非致命摩擦点：

1. **MCP 接入路径文档 vs 实际分叉** → 已对齐（见 §3，SIL-24）。
2. **身份双壳优先级文字模糊** → 唤醒块加「平台行为契约优先」一句话（见 §4.1 要素 4，
   SIL-25 落地到 10 个 agent）。
3. **单 runtime 单点**：10 个 agent 全钉 Pi runtime，该 runtime 掉线 → 全部降级「无分身」。
   远程 MCP/Tailscale（方案 B）已选但**暂缓** —— 已知约束，非新回归。
4. **记忆厚度不均**：分身绑定只给身份，记忆靠使用累积；空分身需预期管理（用户以为绑了
   分身就「很懂」其实是空记忆）。

## 7. 踩坑记录（Windows）

- **中文 instructions 传输**：`--instructions` 是 inline 参数，PowerShell 5.1 可能把非
  ASCII 打成 `?`。最稳路径 = **python subprocess 传 UTF-8 argv**（`subprocess.run([...],
  encoding='utf-8')`，python 内部用 UTF-16 调 Windows API，中文零损耗）；打印时
  `sys.stdout = TextIOWrapper(..., encoding='utf-8')` 防炸。git-bash `$(cat file)` 直传
  Go CLI 会被 GBK 控制台吞坏（显示乱码，存进去可能其实是好的）。
- **append 不覆盖**：写回 instructions 必须读原文合并，绝不 `>` 覆盖。
- **锁文件与并发**：多 agent 并发写 KB 已有代码级方案（SQLite 互斥锁，ROADMAP D9），
  平台侧无需收敛单一 scribe。

## 8. 边界

- ensoul KB 是本机私有（团队不可见），平台 workspace 是团队共享 —— **团队该知道的不能
  只写进 KB**（评论才是团队通道）。
- 远程 MCP（Tailscale）、鉴权、多租户、本地部署：划在集成边界外，另卡跟踪。
