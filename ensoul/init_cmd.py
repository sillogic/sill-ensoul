"""`sill-ensoul-init` console script: initialize an empty global KB and manage
per-CLI shell integration.

Designed for sharing sill-ensoul with teammates: they `pip install` the package,
run `sill-ensoul-init`, then follow the printed steps to wire it into their CLI.
The KB starts empty — each user builds their own agents via wiki_write_concept.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import TypedDict

from .okf import kb_root, create_agent, list_agents, rebuild_index


# The thin shell (CLI-agnostic workflow rules). Kept inline so the package
# carries it — users don't need to curl it separately. This is the same content
# as repo-root SHELL.md / the zcode AGENTS.md body, minus the CLI-specific
# prefix note (printed separately per CLI below).
_SHELL = """# Sill-Ensoul Long-Term Memory System (conditionally triggered)

You have a set of sill-ensoul tools (list_agents / agent_index / wiki_search / wiki_read /
wiki_write_concept / wiki_append_log, etc.). This is the ensouler long-term memory
system — each Agent's memory **accumulates across projects**, letting you carry
historical experience into new projects. This is your core advantage over a plain
"current-project-context-only" assistant.

**Default agent**: after `sill-ensoul-init`, a default agent `alter-ego` (your digital
twin) is available. If the user says "wake up" / "唤醒" without naming an agent,
or mentions "default agent" / "digital twin" / "分身", call `agent_index("alter-ego")`.
Users build specialized agents later via `create_agent`.

**Trigger condition**: When a task involves a professional role (algorithm, backend,
testing, UI/UX, or any other registered Agent's domain), or the user asks to
"wake up an Agent", follow the workflow below. Routine chores unrelated to a
professional role need not trigger it.

**Workflow (condensed; full authoritative version in the ensouler repo's WORKFLOW.md)**:

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
5. **Distill (auto + notify-after)**: During a task, if you hit a non-trivial
   pitfall / made a reusable key decision / distilled a pattern or SOP /
   corrected an old belief — **distill it and write it directly, without asking first**.
   First `wiki_search` to check for an existing entry on the same topic (update if
   exists, avoid duplicates), draft a distilled version, call `wiki_write_concept`
   (`type` is required, body holds only the distillation, not raw transcript) plus
   a matching `wiki_append_log`, **then briefly tell the user** what you wrote
   (concept_id + title + one-line gist). Criterion: it's worth distilling only if
   the next similar project would reuse it. The user retains after-the-fact veto
   (delete/edit on request) — that's the quality gate, not pre-write confirmation.
   **Irreversible ops still need pre-confirmation** (e.g. `delete_agent`).
6. **Skill dispatch**: An agent accumulates "experience using CLI skills" (skill =
   installable capability packs in CLI marketplaces, e.g. pdf/docx/frontend-design).
   On a task, search skill-related concepts; on a hit, recommend "I've used skill X
   for this, recommend". **Check whether the current environment has it**: if yes,
   use it (and distill new experience per step 5 after); if no, remind the user to
   install it themselves (don't install, don't probe, don't guess). Only distill
   experience you've actually used and found good.

**Anti-patterns**: answering without waking up / fabricating memory when search
returns nothing / writing raw transcript into a concept / omitting the `type` field
/ writing to memory without notifying the user afterward / distilling trivial
one-off details as if they were reusable experience / **installing skills for the
user / passing off copied docs as experience** / drifting out of character and
answering professional questions with generic knowledge.
"""

_SHELL_START_MARKER = "<!-- SILL-ENSOUL-SHELL-START -->"
_SHELL_END_MARKER = "<!-- SILL-ENSOUL-SHELL-END -->"


class _CLITarget(TypedDict):
    name: str
    path: Path


# Supported CLI instruction files. Paths are inside the user's home directory and
# are therefore outside the repo — git cannot sync them. --sync-shell exists to
# bridge this gap.
_CLI_TARGETS: list[_CLITarget] = [
    {
        "name": "Claude Code",
        "path": Path.home() / ".claude" / "CLAUDE.md",
    },
    {
        "name": "Zcode",
        "path": Path.home() / ".zcode" / "AGENTS.md",
    },
]


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
- 任务中遇到非平凡的坑、关键决策、可复用模式或纠正了旧认知时，自动提炼并写入 wiki，写完后告诉你。记忆只存提炼后的教训/决策/模式，不存原文。
- 等某个领域（比如算法、后端）的经验攒够了，用 `create_agent` 把那部分记忆分裂出去，我继续当通用起点。
"""


def _marked_shell() -> str:
    return f"{_SHELL_START_MARKER}\n{_SHELL.strip()}\n{_SHELL_END_MARKER}"


def _update_shell_file(path: Path, name: str) -> str:
    if not path.exists():
        return "missing"

    content = path.read_text(encoding="utf-8")
    has_start = _SHELL_START_MARKER in content
    has_end = _SHELL_END_MARKER in content
    if not has_start and not has_end:
        return "unmarked"
    if has_start != has_end:
        return "malformed"

    start_idx = content.find(_SHELL_START_MARKER)
    end_idx = content.find(_SHELL_END_MARKER)
    if start_idx > end_idx:
        return "malformed"
    end_idx += len(_SHELL_END_MARKER)

    backup = path.parent / (path.name + ".sill-ensoul.bak")
    shutil.copy2(path, backup)

    new_content = content[:start_idx] + _marked_shell() + content[end_idx:]
    path.write_text(new_content, encoding="utf-8")
    return "updated"


def sync_shell() -> int:
    print("=" * 60)
    print("  sill-ensoul sync-shell")
    print("=" * 60)
    print()

    any_updated = False
    any_attention = False
    for target in _CLI_TARGETS:
        path = target["path"]
        status = _update_shell_file(path, target["name"])
        labels = {
            "updated": "updated",
            "missing": "missing",
            "unmarked": "unmarked (no markers; append manually or re-init)",
            "malformed": "malformed markers (manual fix needed)",
        }
        print(f"  [{labels[status]}] {target['name']}: {path}")
        if status == "updated":
            any_updated = True
        if status in ("unmarked", "malformed"):
            any_attention = True

    print()
    if any_updated:
        print("Restart your CLI for the updated shell to take effect.")
        print("Backups were written next to each updated file with suffix")
        print("`.sill-ensoul.bak`.")
    elif any_attention:
        print("Some files need manual attention (see statuses above).")
        print("Bootstrap a fresh shell with: sill-ensoul-init --print-shell >> <file>")
    else:
        print("No supported CLI instruction files were found.")
        print("Bootstrap manually with: sill-ensoul-init --print-shell >> <file>")
    print()
    return 0


def rebuild_indices() -> int:
    print("=" * 60)
    print("  sill-ensoul rebuild-index")
    print("=" * 60)
    print()

    agents = list_agents()
    if not agents:
        print("  No agents found. Run `sill-ensoul-init` first.")
        print()
        return 1

    for a in agents:
        agent_id = a["agent_id"]
        try:
            result = rebuild_index(agent_id)
            print(f"  [done] {agent_id}: {result['indexed_concepts']} concepts indexed")
        except FileNotFoundError as e:
            print(f"  [skip] {agent_id}: {e}")

    print()
    print("Index rebuild complete. The .fts/ directories are derived data and")
    print("can be deleted; they will be rebuilt on demand.")
    print()
    return 0


def init_kb() -> int:
    kb = kb_root()
    agents_dir = kb / "agents"
    already = agents_dir.exists() and any(agents_dir.iterdir())

    print("=" * 60)
    print("  sill-ensoul initialization")
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
    print('  In your CLI, say: "set up sill-ensoul from <repo>/SETUP.md"')
    print()
    print("The CLI reads SETUP.md and registers the MCP server + installs the")
    print("shell itself, using its own current config mechanism. sill-ensoul stays")
    print("CLI-agnostic and never tracks each CLI's config changes.")
    print()
    print("Manual options:")
    print("  sill-ensoul-init --print-shell >> <CLI instruction file>")
    print("  sill-ensoul-init --sync-shell          (update existing marked shells)")
    print("  sill-ensoul-init --rebuild-index       (rebuild FTS index for all agents)")
    print("(append, don't overwrite) + register `sill-ensoul-mcp` as an MCP server.")
    print()
    print("=" * 60)
    print('  Done! Restart your CLI, then say "wake up alter-ego" to test.')
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize sill-ensoul global KB and manage CLI shell integration."
    )
    parser.add_argument(
        "--print-shell",
        action="store_true",
        help="Print only the shell content (for redirecting into a CLI's instruction file).",
    )
    parser.add_argument(
        "--sync-shell",
        action="store_true",
        help="Sync the shell into supported CLI instruction files (Claude Code, Zcode).",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild the FTS index for all agents.",
    )
    args = parser.parse_args()

    if args.print_shell:
        print(_SHELL)
        return 0

    if args.sync_shell:
        return sync_shell()

    if args.rebuild_index:
        return rebuild_indices()

    return init_kb()


if __name__ == "__main__":
    sys.exit(main())
