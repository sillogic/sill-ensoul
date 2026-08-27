# 任务：把 sill-ensoul 分身接入 Multica（平台 agent 绑定）

> ⚠️ **人类先读**：本文件不含任何密钥，可放心粘贴 / 转发。它是一份**机器可读适配意图**——
> 在 Multica 对话里把本文件内容丢给目标 agent（或说“按 `<repo>/deploy/cli-setup/multica.md`
> 接入 sill-ensoul”），让接收 agent 自己完成：确认工具 → 建平台 agent → 绑分身 → 验证。
>
> **前提（重要，SIL-8 定案）**：本文件**不做 MCP 安装**。使用前，用户必须已经在 CLI 里
> 配好了 sill-ensoul MCP（8 个工具可用）：
> - 本地 stdio：按 `<repo>/SETUP.md`；
> - 远程 HTTP：按 `<repo>/deploy/cli-setup/switch-to-remote.md`（或管理员发的接入卡）。
>
> 如果工具还没配好，先走上面任一文件，再回来用本文件。

你是本机 Multica 平台 agent。请帮我完成 sill-ensoul 分身接入：**自己动手建 agent、绑分身、
验证，不要只给我命令让我执行。**

## 第 0 步：确认工具已可用（前提检查）

调一次 `list_agents`：

- **能调通**（返回 agent 列表，哪怕为空）→ 前提成立，继续第 1 步。
- **调不通**（工具不存在 / 报错）→ 前提没满足。停下来告诉用户：先按 `<repo>/SETUP.md`
  （本地）或 `<repo>/deploy/cli-setup/switch-to-remote.md`（远程）配好 MCP，再回来跑本文件。
  注意 MCP 配置不热加载——刚装完的当前 run 可能还拿不到工具：按降级规则先干别的，下个
  run 验证工具后再补绑定。

## 第 1 步：确认 / 创建平台 agent

Multica agent 是平台实体（看板上跑 issue 的执行者），ensoul 分身是记忆实体（OKF wiki），
两者 1:1 绑定。平台 agent 的创建是平台动作（UI 或 `multica agent create`），md 装不了也
**不该**由 md 创建：

- 已有要绑的平台 agent → 直接用它，跳到第 2 步。
- 没有 → 建一个（UI 建，或让当前 agent 执行）：

```bash
multica agent create \
  --name "alter-ego" \
  --description "<分身 AGENT.md 的 title/description>" \
  --instructions "<平台基础 instructions + 唤醒块>" \
  --runtime-id <能调到 ensoul MCP 工具的 runtime> \
  --model <同现有 agent> \
  --permission-mode public_to --public-to-workspace
```

## 第 2 步：绑定分身（唤醒块）

1. `list_agents` 按领域匹配已有分身：有匹配 → 绑它；没有 → `create_agent` 新建分身再绑
   （匹配规则见 `ensoul-multica-binding` skill，由匹配结果自动决定，用户不用二选一）。
2. 生成唤醒块：复制 `<repo>/shells/multica/AGENTS.md` 的 `## 分身绑定(1:1)` 整块，替换
   `<分身id>` 与 `<角色一句话描述>`；**必带身份优先级行**（平台行为契约优先；分身用于
   专业判断与记忆）。
3. **append 不覆盖**：读目标 agent 当前 instructions，唤醒块追加在末尾（create 时可直接
   带上），`multica agent update <id> --instructions "<原文 + 唤醒块>"` 写入。
4. name/description 同步：`multica agent update <id> --name "<分身id>@<机器>"
   --description "<分身 title/description>"`。
5. 挂绑定 skill（若 workspace 已存在）：`multica agent skills add <id>
   --skill-ids ensoul-multica-binding`——唤醒块本身即是绑定；skill 只提供“以后还能绑别的
   分身”的能力，首次安装时 skill 可能还不存在，不影响绑定。

## 第 3 步：验证 + 收尾

- `multica agent get <id> --output json`：name 是 `<分身id>@<机器>`、instructions 含唤醒块；
- 该 agent 能调 `list_agents` / `agent_index`（`list_agents` 返回里含该分身）。
- 完成后按下方「事后报告」模板向用户汇报。

## 事后报告（必做）

告诉用户：✅ 已接入。绑定了分身 `<分身id>`（agent：`<name>`）。在这个 agent 的对话里说
「唤醒 `<分身id>`」（或“唤醒分身”）开始使用。记忆在 `<KB 路径>`（Windows：
`%LOCALAPPDATA%\ensoul\knowledge`）。
