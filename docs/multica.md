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
- 单分支同时服务两类用户：无 multica 用户走自己 CLI 的 MCP 配置；multica 用户走 CLI 级安装（SETUP.md setupmd 流程，见 §3.3）。运行时代码路径不分叉。
- **判断模板**：要不要为某平台/客户分叉？先 grep 仓库有没有该平台相关代码；集成若只是
  配置 + 薄壳，一律主分支 + 文档，不分叉。

## 3. MCP 接入路径（文档 = 现实，2026-08-26 最终定案）

**一条主路径：CLI/runtime 级安装** —— setup 时把 ensoul 装进本机所有被 Multica 识别到的 CLI；任何 runtime 都有工具，零 per-agent 配置，无双写。**平台 MCP 库 = 未来选项**（远程 server / 多 runtime 并存 / 多机时再上），现在不注册（SIL-26 最终定案，2026-08-26 用户确认）：

| 路径 | 状态 | 说明 |
|---|---|---|
| **CLI/runtime 级安装**（主路径） | ✅ 定案 + 本机已实装 | 把 sill-ensoul 装进每个被 Multica 识别到的 CLI（pi 扩展 bridge / `claude mcp add` / opencode mcp / …）；per-runtime 注入 → 该 runtime 上所有 agent 自动有工具。幂等（已装跳过）+ 版本检查（旧了升级，UPGRADE.md） |
| **平台 MCP 库**（未来选项） | ⏸ 暂缓 | `multica workspace mcp add` + `agent mcp add`（admin/owner 操作，agent 被服务端硬拒）；价值场景（远程/多 runtime 并存/多机）全在暂缓边界内，不提前做 |

版本对齐（SIL-26 复核）：一台机器一个 server 版本一个 KB —— pip 安装 `sill-ensoul` v0.3.0 == 仓库 v0.3.0，无漂移。

**新人安装流程（setupmd）**见 §3.3；[`deploy/cli-setup/multica.md`](../deploy/cli-setup/multica.md) 是可执行版本（前提：本机 CLI 已配好 MCP）。装好后用 `multica agent get` 确认 agent 能调 `list_agents` / `agent_index`。

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
  2. **同一机器一个 server 版本一个 KB**：一台机器所有 CLI 注册同一个命令（`cmd /c
     sill-ensoul-mcp`）、同一个包版本，消灭版本漂移（平台库不注册，注册命令单一性自动
     满足，剩余纪律 = 版本对齐）。
- **三类用户落法**：只用 multica = setupmd 装齐所有识别到的 CLI → 任何 runtime 有工具
  （天然零 per-agent 配置）；只用 CLI = 各 CLI 自配（现状）；两者都用 = 同一二进制同一 KB
  多处配置共存，错开使用零冲突、同时跑（autopilot + 本地 CLI）有锁兑底，守「嵌套一层写」
  约定即可。
- **「嵌套 CLI 没装 ensoul 要不要唤醒时自动装？」—— 不需要，也不建议（2026-08 追加）**：
  分工的前提**不是**「嵌套的每个 CLI 都装了 ensoul」，而是「外层 agent 有工具」—— 那由
  setup 时一次性装齐保证（§3.3 setupmd，SIL-26 定案），不是每次唤醒的前提。嵌套 CLI 本来
  就不承担记忆层（约定 1），唤醒时发现缺 ensoul → 按降级规则继续干活 + 报告一句即可；每次
  唤醒自动装 = 无需求也装，反而把「两个心智写同一分身」的风险重新引入，还欠版本钉死
  （pip v0.3.0 == 仓库 v0.3.0）、幂等、静默改用户机器三笔账。嵌套确实要用 ensoul 的
  场景（换 agent_id 的会话）走一次性安装（`pip install sill-ensoul`）；自动化的正确形态
  是 bootstrap —— §3.3 setupmd 就是它（setup 时一步装齐 + 幂等 + 版本检查），不是运行时
  magic。

### 3.2 未来演进：远程 server / 多租户 —— 鉴权已落地，其余只留边界（2026-08）

用户计划：以后 MCP 上服务器（远程，使用会简单很多）、多租户后面再做；远程（Tailscale
方案 B 暂缓）、鉴权（SIL-7）、多租户（SIL-8）各已有卡片。**SIL-7 鉴权已按指令落地
（2026-08-27，见 D11）；其余仍不写代码，边界由构造覆盖**：

- **transport 可换 = 配置不是代码，且 HTTP 适配器已实现**：MCP 客户端注册本就是配置驱动
  （今天 `{"type":"stdio",...}`，远程 `{"type":"streamable-http","url":...}`），换远程 =
  换注册条目，server 工具面（8 工具）与数据层一行不动。HTTP transport = 新增适配器
  （`ensoul/http.py`，复用 server.py 的同一批工具 callable），不是重构 —— D1 承诺兑现。
- **多租户 = KB 根注入，数据模型不用改**：`ENSOUL_KB` 环境变量已让 KB 根可注入，租户 =
  每租户一个 KB 根（或路径前缀），agent_id 仍是数据层唯一身份键；SIL-8 开工时直接加
  「租户 → KB 根」映射即可（http.py 已留 `_identity_for_token` / `_kb_root_for_identity`
  口子，只加映射，鉴权协议与工具层零改动）。
- **远程的真正门槛是鉴权（SIL-7），不是技术 —— 已落地**：`sill-ensoul-http`（Streamable
  HTTP + Bearer token，`ENSOUL_MCP_TOKEN` 必设，缺 token 拒绝启动 fail-closed；单租户，
  一个 token = 一个身份 → 一个 KB 根）。远程 = 单 server 进程管一个 KB，并发由进程内
  串行天然保证；跨机共享同一 KB 才需要分布式锁，但那不是目标形态。
- **剩下不动的原因**：SIL-8（多租户）与远程部署形态（Tailscale 方案 B 等）无真实负载
  验证需求，提前实现违反「能不动就不动」；留边界 = 这两张卡开工时拿到的是
  「不需要重构的地基」。

### 3.3 新人安装流程（setupmd，SIL-26 最终定案 2026-08-26）

用户通过 Multica 走 SETUP.md 安装（「setupmd」）：**Multica 平台不装 ensoul，把 ensoul
装进本机所有被 Multica 识别到的 CLI**（幂等：已装跳过；已装则比版本，旧了升级）。可执行
版本在 [`deploy/cli-setup/multica.md`](../deploy/cli-setup/multica.md)（SIL-8 文档拆分后：
multica.md 只做平台侧，MCP 安装由 SETUP.md / cli-remote.md 负责）步骤 1 之前的前提
检查，要点：

1. **机器级一次（幂等）**：`sill-ensoul-mcp` 在 PATH 上？没有 → `pip install sill-ensoul`
   （先告知用户拿 OK）；有 → `sill-ensoul-init --version` 对比仓库/最新，旧了走 UPGRADE.md。
   `sill-ensoul-init` 跑一遍（建全局 KB + 默认分身 alter-ego，幂等）。
2. **探测被识别的 CLI**：`multica runtime list --output json`（本机 runtime 的 provider）∪
   PATH 扫描已知 agent CLI 命令（claude / codex / opencode / pi / cursor-agent / kimi /
   qodercli / qwen / …，与 daemon probe-runtimes 同一套已知清单；task 内 probe-runtimes
   不可用，所以用 runtime list + PATH 扫描）。取并集逐个处理。
3. **逐个 CLI 幂等安装**：已注册 sill-ensoul MCP → 跳过；没注册 → 按该 CLI 自己的机制注册
   （pi 扩展 bridge / `claude mcp add` / 各 CLI config）。指令文件已含 shell 标记 → 跳过；
   没有 → `sill-ensoul-init --print-shell` append 一次。版本/升级在机器级已覆盖（一台机器
   一个 server 版本一个 KB）。
4. **不注册平台 MCP 库**（未来选项，暂缓）。

**为什么这个形态**：per-runtime 注入 → 该 runtime 上所有 agent 自动有工具，零 per-agent
配置；setup 时一次性装齐 = 运行时永远不缺（「唤醒时自动装」的否决保持成立，见 §3.1）；
已装跳过 + 版本检查 = 可重跑、不静默改机器。

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

### 4.3 name/description 同步（决策 6 + SIL-7 修正 2026-08-27）

绑定收尾：`multica agent update <agent-id> --name "<分身id>@<机器>" --description "<分身
AGENT.md 的 title/description>"` —— 让平台侧「看起来就是」那个分身（成员在 UI 里一眼
认出）。分身后续 persona 更新时按需再同步。

**实例名命名规则（SIL-7 讨论定案，2026-08-27）**：平台 agent 实例名一律
`<分身id>@<机器>`（如 `ensoul-dev@home`、`ensoul-dev@mac`），**单机也加后缀** —— 因为
后面增加多机时，裸名看不出是哪台机器；从第一天就带后缀，避免日后批量改名迁移。要点：

- 实例名带机器后缀 ≠ 记忆键：唤醒块 `agent_index("<裸分身id>")` 不变，记忆仍读写同一份
  KB（多机共享同一分身 = 读写同一份记忆，这正是远程 MCP 单一权威源的目的，记忆不分裂）。
- 旧约定「单机 1:1 用裸名」作废，一律加后缀（代码零改动，后缀只活在平台 agent 实例名）。

### 4.4 通过 multica.md 初始化（决策 7 + SIL-29 细化 + SIL-8 文档拆分）

SIL-8（2026-08-27）文档拆分定案后：接入引导按场景分成三个文件 —— 本地 MCP 用 SETUP.md、
远程 MCP 用 [`deploy/cli-setup/cli-remote.md`](../deploy/cli-setup/cli-remote.md)（CLI 安装）、**Multica 用
[`deploy/cli-setup/multica.md`](../deploy/cli-setup/multica.md)**。
multica.md 的前提是**本机 CLI 已配好 MCP**（所以它不含安装步骤、不含密钥，只含：前提检查
→ 确认平台 agent → 绑分身 → 验证）。老用户把 multica.md 直接丢给 multica agent 对话即可初始化。

multica.md 覆盖：前提检查（`list_agents` 验证工具可用）/ 确认或创建**一个**平台 agent /
绑定**已有**分身（唤醒块 + skill）/ 验证。

- **过渡阶段规则（2026-08-27，SIL-8）**：绑定只匹配**已有**分身，**不新建分身、不默认创建
  `alter-ego` 分身** —— 服务端 ensoul 列表已有现成分身（alter-ego / ensoul-dev 等），直接绑
  最贴近的一个即可。绑定 skill（§4.2）里「无匹配就 `create_agent` 新建」的规则在过渡阶段
  暂停执行，由 multica.md 的显式规则覆盖（remote 用户拿到的是两份文件：CLI 安装
  cli-remote.md + Multica 初始化 multica.md，multica.md 不再承担任何安装职责）。等 SIL-8
  多租户完成后，每个用户有自己独立的 KB（tenants/&lt;user_id&gt;/），届时再谈按需新建分身。
- **首次安装（SIL-29 修正）**：接收 multica.md 的 agent **不改名**、保持自己的 Helper 身份，
  按上述规则确认/创建一个平台 agent 并绑定**已有**分身（不再创建 alter-ego 分身），唤醒块
  模板见 [shells/multica/AGENTS.md](../shells/multica/AGENTS.md)。
- **老用户**：更贴合 4.2 的绑定 skill（按领域匹配已有分身 1:1 绑定 + name/description
  同步），非一律 alter-ego。

## 5. 批量上架模式（决策 8）：分身 → agent + 项目

把本机已有分身系统搬进 Multica 的第一批上架，按四步：

1. **分身枚举**：`list_agents` 列出所有 OKF agent（本机 `%LOCALAPPDATA%/ensoul/knowledge/
   agents/`，每个子目录一个分身）；排除 `.obsidian` 等非 agent 目录。
2. **agent 创建**：每个分身
   `multica agent create --name <分身id>@<机器> --description <AGENT.md title/description>
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

1. **MCP 接入路径文档 vs 实际分叉** → 已对齐（见 §3，SIL-24 + SIL-26 最终定案：单主路径 = CLI 级安装）。
2. **身份双壳优先级文字模糊** → 唤醒块加「平台行为契约优先」一句话（见 §4.1 要素 4，
   SIL-25 落地到 10 个 agent）。
3. **单 runtime 单点**：CLI 级安装后（§3.3），同机换 runtime 不再丢工具（该机所有被识别 CLI 都有 ensoul）；跨机仍取决于那台机装没装。远程 MCP/Tailscale（方案 B）已选但**暂缓** —— 已知约束，非新回归。
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
