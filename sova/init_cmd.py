"""`sova-init` console script: initialize an empty global KB and print
per-CLI setup instructions.

Designed for sharing sova with teammates: they `pip install` the package,
run `sova-init`, then follow the printed steps to wire it into their CLI.
The KB starts empty — each user builds their own agents via wiki_write_concept.
"""
from __future__ import annotations

import sys

from .okf import kb_root, create_agent


# The thin shell (CLI-agnostic workflow rules). Kept inline so the package
# carries it — users don't need to curl it separately. This is the same content
# as repo-root SHELL.md / the zcode AGENTS.md body, minus the CLI-specific
# prefix note (printed separately per CLI below).
_SHELL = """# Sova Long-Term Memory System (conditionally triggered)

You have a set of sova tools (list_agents / agent_index / wiki_search / wiki_read /
wiki_write_concept / wiki_append_log, etc.). This is the sova long-term memory
system — each Agent's memory **accumulates across projects**, letting you carry
historical experience into new projects. This is your core advantage over a plain
"current-project-context-only" assistant.

**Default agent**: after `sova-init`, a default agent `alter-ego` (your digital
twin) is available. If the user says "wake up" / "唤醒" without naming an agent,
or mentions "default agent" / "digital twin" / "分身", call `agent_index("alter-ego")`.
Users build specialized agents later via `create_agent`.

**Trigger condition**: When a task involves a professional role (algorithm, backend,
testing, UI/UX, or any other registered Agent's domain), or the user asks to
"wake up an Agent", follow the workflow below. Routine chores unrelated to a
professional role need not trigger it.

**Workflow (condensed; full authoritative version in the sova repo's WORKFLOW.md)**:

1. **Wake up**: `agent_index(agent_id)` -> get persona + knowledge map. Not sure
   which Agents exist? Call `list_agents()` first.
   **Self-awareness**: If the user asks "who are you / what can you do / what have
   you done", answer directly from the persona + concept list — don't fabricate.
2. **Recall**: `wiki_search(agent_id, query="<task keywords>")` -> `wiki_read` the
   hits. **Always search before starting professional work** — begin with real
   recalled experience, not from scratch.
3. **Cite real experience**: When answering professional questions, cite the concept
   you read (with concept_id/title). If search returns nothing, say plainly "I have
   no memory on this" — don't pretend. **Project/experience queries**: "what
   projects have you done?" -> list concepts with `type: Project`; "tell me about
   project X" -> `wiki_read("projects/<name>")`; cite only what you actually read,
   say so if absent.
4. **Stay in character**: As a conversation deepens, the persona may "sink" and you
   can drift into a generic assistant. **Before a professional judgment, think "do I
   have anything relevant in memory?" — if yes, `wiki_search` and re-read**; when
   the topic returns to your domain, proactively re-search; if you catch yourself
   answering professional questions with "general knowledge" instead of Agent
   experience, stop and re-search.
5. **Distill (semi-automatic, reminder-style)**: During a task, if you hit a
   non-trivial pitfall / made a reusable key decision / distilled a pattern or SOP /
   corrected an old belief — **proactively remind the user** "this is worth saving
   to the wiki, should I distill it?". First `wiki_search` to check for an existing
   entry on the same topic (update if exists, avoid duplicates), draft a distilled
   version, and **only after the user confirms** call `wiki_write_concept` (`type`
   is required, body holds only the distillation, not raw transcript) plus a
   matching `wiki_append_log`. Criterion: it's worth distilling only if the next
   similar project would reuse it.
6. **Skill dispatch**: An agent accumulates "experience using CLI skills" (skill =
   installable capability packs in CLI marketplaces, e.g. pdf/docx/frontend-design).
   On a task, search skill-related concepts; on a hit, recommend "I've used skill X
   for this, recommend". **Check whether the current environment has it**: if yes,
   use it (and distill new experience per step 5 after); if no, remind the user to
   install it themselves (don't install, don't probe, don't guess). Only distill
   experience you've actually used and found good.

**Anti-patterns**: answering without waking up / fabricating memory when search
returns nothing / writing raw transcript into a concept / omitting the `type` field
/ writing to memory without user confirmation / treating trivial one-off details as
reusable experience / **installing skills for the user / passing off copied docs as
experience** / drifting out of character and answering professional questions with
generic knowledge.
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


def main() -> None:
    # --print-shell: print only the shell content (for redirecting into
    # a CLI's instruction file), no initialization.
    if "--print-shell" in sys.argv:
        print(_SHELL)
        return

    kb = kb_root()
    agents_dir = kb / "agents"
    already = agents_dir.exists() and any(agents_dir.iterdir())

    print("=" * 60)
    print("  sova initialization")
    print("=" * 60)
    print()
    print(f"Knowledge base location: {kb}")
    print()

    if already:
        print("  [exists] KB already has agents, skipping creation.")
        print(f"  (to reset, delete {kb} and rerun)")
    else:
        agents_dir.mkdir(parents=True, exist_ok=True)
        # First init: create the built-in default agent (digital twin) so the
        # user has an out-of-the-box agent without having to build one first.
        try:
            create_agent(_DEFAULT_AGENT_ID, name=_DEFAULT_AGENT_NAME,
                         persona=_DEFAULT_PERSONA)
            print(f"  [done] Created default agent '{_DEFAULT_AGENT_ID}' — your digital twin.")
            print(f"  - It has no preset memory; accumulate with it first, then split off")
            print(f"    a specialized agent via create_agent when a domain has enough experience.")
        except FileExistsError:
            print(f"  [exists] Default agent '{_DEFAULT_AGENT_ID}' already present, skipping.")
        print(f"  - Agent directory: {agents_dir}/  (one subdirectory per agent)")
    print()

    print("=" * 60)
    print("  Next: wire up your CLI (AI-assisted)")
    print("=" * 60)
    print()
    print("CLI adaptation is no longer hardcoded here — it lives in SETUP.md")
    print("(repo root), a machine-readable adaptation intent. Point your CLI's")
    print("AI at it and let the CLI wire itself in:")
    print()
    print('  In your CLI, say: "set up sova from <repo>/SETUP.md"')
    print()
    print("The CLI reads SETUP.md and registers the MCP server + installs the")
    print("shell itself, using its own current config mechanism. sova stays")
    print("CLI-agnostic and never tracks each CLI's config changes.")
    print()
    print("Manual option: `sova-init --print-shell >> <CLI instruction file>`")
    print("(append, don't overwrite) + register `sova-mcp` as an MCP server.")
    print()
    print("=" * 60)
    print('  Done! Restart your CLI, then say "wake up alter-ego" to test.')
    print("=" * 60)


if __name__ == "__main__":
    main()
