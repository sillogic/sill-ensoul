# 任务：把 sill-ensoul 分身接入 Multica（平台 agent 绑定）

> ⚠️ **人类先读**：本文件**不含任何密钥、不做任何 MCP 安装**，可放心粘贴 / 转发。它是一份
> **机器可读适配意图**——在 Multica 对话里把本文件内容丢给目标 agent（或说「按 multica.md
> 接入 sill-ensoul」），让接收 agent 自己完成：确认工具 → 确认平台 agent → 绑分身 → 验证。
>
> **前提（SIL-8 定案）**：你的 CLI 已经配好 sill-ensoul MCP（8 个工具可用）——这由你手里的
> **另一份文件（CLI 安装，远程 MCP 接入）** 完成。本文件只做 Multica 平台侧：不含安装步骤、
> 不含密钥，MCP 没配好时无法用它（见第 0 步）。

你是本机 Multica 平台 agent。请帮我完成 sill-ensoul 分身接入：**自己动手确认 agent、绑分身、
验证，不要只给我命令让我执行。**

## 第 0 步：确认工具已可用（前提检查）

调一次 `list_agents`：

- **能调通**（返回 agent 列表，哪怕为空）→ 前提成立，继续第 1 步。
- **调不通**（工具不存在 / 报错）→ 前提没满足。停下来告诉用户：先完成你手里的
  「CLI 安装」文件（远程 MCP 接入），再回来跑本文件。注意 MCP 配置不热加载——刚装完的
  当前 run 可能还拿不到工具：按降级规则先干别的，下个 run 验证工具后再补绑定。

## 第 1 步：确认平台 agent（只用一个，不为每个分身都建）

Multica agent 是平台实体（看板上跑 issue 的执行者），ensoul 分身是记忆实体（OKF wiki），
两者 1:1 绑定。平台 agent 的创建是平台动作（UI 或 `multica agent create`），md 装不了也
**不该**由 md 创建：

- 已有要绑的平台 agent → 直接用它，跳到第 2 步。
- 没有 → 建**一个**（UI 建，或让当前 agent 执行 `multica agent create`）。名字先用占位
  （**不要默认 `alter-ego`**），第 2 步绑定后统一同步为 `<分身id>@<机器>`。

**只建一个 agent、绑一个分身**：不要为每个分身都创建一个平台 agent。

## 第 2 步：绑定分身（唤醒块）

1. `list_agents` 按领域匹配**已有**分身：有匹配 → 绑它；拿不准 → 把 `list_agents` 结果
   列给用户，让他选绑哪个。
2. **过渡阶段规则（SIL-8 定案，2026-08-27）**：**不新建分身，也不默认创建 `alter-ego`
   分身**——服务端 ensoul 列表已有现成分身（如 alter-ego / ensoul-dev 等），直接绑最贴近
   的一个即可。即使绑定的 skill 里有「无匹配就 `create_agent` 新建」的规则，过渡阶段一律
   按本文件执行：**不新建**。等 SIL-8 多租户完成后，每个用户有自己独立的 KB，再谈按需
   新建分身。
3. 生成唤醒块：复制 `<repo>/shells/multica/AGENTS.md` 的 `## 分身绑定(1:1)` 整块，替换
   `<分身id>` 与 `<角色一句话描述>`；拿不到仓库文件就按下面四要素自己生成：
   ① 绑定声明（本 agent ↔ 分身 `<id>` 一对一，run 开始先切换到该分身）；② 强制步骤
   （`agent_index` → `wiki_search`，命中 `wiki_read`，无记忆明说 → 保持分身身份引用真实
   concept_id → 按沉淀规则自动蒸馏 + 事后告知）；③ 降级规则（工具不可用 → 退回平台身份
   继续工作，最终评论说明「本次未切换到分身」）；④ **身份优先级行**（平台行为契约优先；
   分身用于专业判断与记忆）。
4. **append 不覆盖**：读目标 agent 当前 instructions，唤醒块追加在末尾（create 时可直接
   带上），`multica agent update <id> --instructions "<原文 + 唤醒块>"` 写入。
5. name/description 同步：`multica agent update <id> --name "<分身id>@<机器>"
   --description "<分身 title/description>"`。
6. 挂绑定 skill（若 workspace 已存在）：`multica agent skills add <id>
   --skill-ids ensoul-multica-binding`——唤醒块本身即是绑定；skill 只提供「以后还能绑别的
   分身」的能力，首次安装时 skill 可能还不存在，不影响绑定。

## 第 3 步：验证 + 收尾

- `multica agent get <id> --output json`：name 是 `<分身id>@<机器>`、instructions 含唤醒块；
- 该 agent 能调 `list_agents` / `agent_index`（`list_agents` 返回里含该分身）。
- 完成后按下方「事后报告」模板向用户汇报。

## 事后报告（必做）

告诉用户：✅ 已接入。绑定了分身 `<分身id>`（agent：`<name>`）。在这个 agent 的对话里说
「唤醒 `<分身id>`」（或“唤醒分身”）开始使用。记忆在**服务端 KB**（远程 MCP 接入时本机
没有本地副本，读写都走远程连接）。
