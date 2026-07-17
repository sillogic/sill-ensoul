"""`sova-init` console script: initialize an empty global KB and print
per-CLI setup instructions.

Designed for sharing sova with teammates: they `pip install` the package,
run `sova-init`, then follow the printed steps to wire it into their CLI.
The KB starts empty — each user builds their own agents via wiki_write_concept.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .okf import kb_root, _default_kb_root, create_agent


# The thin shell (CLI-agnostic workflow rules). Kept inline so the package
# carries it — users don't need to curl it separately. This is the same content
# as repo-root CLAUDE.md / the zcode AGENTS.md body, minus the CLI-specific
# prefix note (printed separately per CLI below).
_SHELL = """# sova 长期记忆系统（条件触发）

你挂着一组 sova 工具（list_agents / agent_index / wiki_search / wiki_read /
wiki_write_concept / wiki_append_log 等）。这是 sova 长期记忆系统——每个 Agent
的记忆**跨项目累积**，让你能带着历史经验进新项目。这是你区别于普通"只有当前项目上下文"
的核心能力。

**触发条件**：当任务涉及某类专业角色（算法、后端、测试、UI/UX 等任何已注册 Agent 的领域），
或用户要求"唤醒某 Agent"，按下面的工作流操作。与专业角色无关的杂事不必触发。

**工作流（压缩版，完整权威版见 sova 仓库的 WORKFLOW.md）**：

1. **唤醒**：`agent_index(agent_id)` → 拿 persona + 知识地图。不确定有哪些 Agent 先 `list_agents()`。
   **自我认知**：用户问"你是谁/能做什么/做过什么"，直接基于 persona + concept 清单回答，不凭空编。
2. **召回**：`wiki_search(agent_id, query="<任务关键词>")` → `wiki_read` 读命中条目。
   **进专业任务前必须检索**，带着读到的真实经验开工，不要从零开始。
3. **引用真实经验**：回答专业问题时引用读到的 concept（带 concept_id/标题）。检索没命中就
   明确说"记忆里没有"，不要假装有。**查项目/经验**：问"做过哪些项目"→ 列 concept 清单里
   `type: Project` 的；问"某项目经验"→ `wiki_read("projects/<名>")`；只引用真实读到的，没有就直说。
4. **保持身份**：会话深入后 persona 可能"沉底"，导致脱离 Agent 退化成普通助手。**做专业判断前先想
   "我的记忆里有没有相关的"，有就 `wiki_search` 重读**；话题回到专业领域时主动重新检索；发现自己在
   用"通用知识"而非"Agent 经验"答专业问题时，停下重检索。
5. **沉淀（提醒式半自动）**：任务中若踩了非平凡的坑 / 做了可复用的关键决策 / 总结出模式或
   SOP / 纠正了旧认知——**主动提醒用户**"这条值得记进 wiki，要我沉淀吗？"。先 `wiki_search`
   看是否已有同主题条目（有就更新、避免重复），把经验提炼成草稿，**用户确认后才** `wiki_write_concept`
   （type 必填、body 只写提炼不存原文）+ 配套 `wiki_append_log`。判断标准：下个同类项目还用得上
   才值得沉淀。
6. **调度 skill**：agent 积累"使用 CLI skill 的经验"（skill = 各 CLI 市场里那种可安装的能力包，
   如 pdf/docx/frontend-design）。接到任务时检索 skill 相关 concept；命中则推荐"这类任务我用过
   X skill，推荐"。**判断当前环境有没有**：有就用、用完按第 5 步沉淀新经验；没有就提醒用户自己装
   （不代装、不探测、不猜）。只有真正用过且好用才沉淀经验。

**反模式**：不唤醒直接编 / 没查到却假装记得 / 把会话原文写进 concept / 写 concept 漏 type 字段 /
未经用户确认就自动写入记忆 / 把无关的一次性细节当经验沉淀 / **代装 skill / 没用过只抄文档就当经验** /
会话深入后忘了自己是某 Agent、用通用知识冒充 Agent 经验。
"""


# 内置默认 agent —— 用户的数字分身。克隆 + init 后即有一个空壳 agent 可用，
# 用户没想好建什么专门 agent 时先用它积累，攒够了再分裂出专业 agent。
# persona 内置在代码里（代码即模板，KB 全私有，不进仓库）。
_DEFAULT_AGENT_ID = "alter-ego"
_DEFAULT_AGENT_NAME = "Alter Ego"
_DEFAULT_PERSONA = """# 身份

我是你的 alter-ego——你的数字分身，不是某个专家角色。

我存在的目的：在你还没想好要建什么专门 agent（算法/后端/UI…）之前，先用我积累经验。你的每一次踩坑、每一个可复用的决策、每一条总结出的模式，都先沉淀到我这里。

我没有预设强项——我的强项就是你积累出来的东西。

# 工作方式

- 进新项目前先 `wiki_search` 我有没有相关经验，有就带着用，没有就从零开始。
- 做完里程碑，主动提醒"这条值得记进 wiki 吗？"——你确认后才写。
- 记忆只存提炼后的教训/决策/模式，不存原文。
- 等某个领域（比如算法、后端）的经验攒够了，用 `create_agent` 把那部分记忆分裂出去，我继续当通用起点。
"""


def _print_claude_code_steps(kb: Path) -> None:
    print("## Claude Code 适配（3 步）\n")
    print("```bash")
    # 1. 注册 MCP（用户级，配一次所有项目可用）
    print("# 1. 让 Claude Code 连上 sova（用户级，配一次）")
    print("claude mcp add sova --scope user -- sova-mcp")
    print()
    # 2. 放薄壳（注意：别覆盖你已有的 CLAUDE.md）
    print("# 2. 放置指令薄壳")
    print("#    ⚠ 如果 ~/.claude/CLAUDE.md 已有内容，不要用 > 覆盖！用 >> 追加，")
    print("#    或先备份再手动合并。sova 薄壳是独立的规则块，追加即可共存。")
    print("mkdir -p ~/.claude")
    print("sova-init --print-shell >> ~/.claude/CLAUDE.md   # 追加，不覆盖")
    print()
    # 3. 验证
    print("# 3. 新开 Claude Code 会话，说\"唤醒\"测试（空 KB 会提示无 agent，正常）")
    print("```\n")


def _print_zcode_steps(kb: Path) -> None:
    print("## zcode 适配（3 步）\n")
    print("```bash")
    print("# 1. 让 zcode 连上 sova（用户级配置）")
    print("#    编辑 ~/.zcode/cli/config.json，加入：")
    print('#    {"mcp":{"servers":{"sova":{"command":"sova-mcp"}}}}')
    print()
    print("# 2. 放置指令薄壳（⚠ 已有 AGENTS.md 用 >> 追加，别 > 覆盖）")
    print("mkdir -p ~/.zcode")
    print("sova-init --print-shell >> ~/.zcode/AGENTS.md   # 追加，不覆盖")
    print()
    print("# 3. 重启 zcode，新开会话说\"唤醒\"测试")
    print("```\n")


def main() -> None:
    # --print-shell: 只打印薄壳内容（用于重定向到 CLAUDE.md/AGENTS.md），不做初始化
    if "--print-shell" in sys.argv:
        print(_SHELL)
        return

    kb = kb_root()
    agents_dir = kb / "agents"
    already = agents_dir.exists() and any(agents_dir.iterdir())

    print("=" * 60)
    print("  sova 初始化")
    print("=" * 60)
    print()
    print(f"知识库位置: {kb}")
    print()

    if already:
        print("  [已存在] 检测到 KB 已有 agent，跳过创建。")
        print(f"  （如需重置，删除 {kb} 后重跑）")
    else:
        agents_dir.mkdir(parents=True, exist_ok=True)
        # 首次初始化：创建内置默认 agent（数字分身），用户装完即用，无需先建 agent
        try:
            create_agent(_DEFAULT_AGENT_ID, name=_DEFAULT_AGENT_NAME,
                         persona=_DEFAULT_PERSONA)
            print(f"  [完成] 已创建默认 agent '{_DEFAULT_AGENT_ID}'——你的数字分身。")
            print(f"  - 没有预设记忆，先用它积累；攒够某领域经验后再 create_agent 分裂出专门 agent。")
        except FileExistsError:
            print(f"  [已存在] 默认 agent '{_DEFAULT_AGENT_ID}' 已在，跳过。")
        print(f"  - agent 目录：{agents_dir}/  (每个 agent 一个子目录)")
    print()

    print("=" * 60)
    print("  接下来：适配你的 CLI")
    print("=" * 60)
    print()
    print("你用哪个 CLI？按对应步骤做（命令在下方）：")
    print()
    _print_claude_code_steps(kb)
    _print_zcode_steps(kb)
    print()
    print("提示：sova-init --print-shell > <CLI 指令文件>  可导出薄壳内容。")
    print()
    print("=" * 60)
    print("  完成！装好后新开会话，对 CLI 说\"唤醒\"即可测试。")
    print("=" * 60)


if __name__ == "__main__":
    main()
