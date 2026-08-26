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

两条路径，**当前实装验证的是 pi 扩展路线**；平台 MCP 库路线是规划目标（SIL-26 落地）：

| 路径 | 状态 | 说明 |
|---|---|---|
| **pi 扩展路线**（已验证） | ✅ 实装 | `~/.pi/agent/settings.json` → `cmd /c sill-ensoul-mcp`，经 `extensions/mcp-bridge.ts` 把 8 个 ensoul 工具暴露给 run 内 agent |
| **平台 MCP 库路线**（规划） | ⏳ 目标 | `multica workspace mcp add` + `multica agent mcp add`，任何 runtime CLI 可用；2026-08-26 复核 `multica workspace mcp list` 仍为 `[]`，且本机 pip 安装版本（v0.2.1）滞后于仓库（v0.2.3）—— 实装前需先升级 |

**新人注意**：SETUP.md 的「Multica adaptation」一节现按双路径写（平台注册 + pi 扩展
均已说明）；装好后用 `multica agent get` 确认 agent 能调 `list_agents` / `agent_index`。

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

### 4.4 通过 SETUP.md 初始化（决策 7）

老用户把 SETUP.md 直接丢给 multica agent 对话即可初始化，无需专门 md（SIL-27 确认）。
SETUP.md 内「Multica adaptation」一节覆盖：平台 MCP 注册 / shell append 进 instructions /
改名默认分身 `alter-ego` / 验证。老用户更贴合 4.2 的绑定 skill（按领域匹配已有分身），
非一律 alter-ego。

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
