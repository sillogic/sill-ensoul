"""`sill-ensoul-init` console script: initialize an empty global KB and manage
per-CLI shell integration.

Designed for sharing sill-ensoul with teammates: they `pip install` the package,
run `sill-ensoul-init`, then follow the printed steps to wire it into their CLI.
The KB starts empty — each user builds their own agents via wiki_write_concept.
"""
from __future__ import annotations

import argparse
import functools
import importlib.resources as resources
import shutil
import sys
from pathlib import Path
from typing import TypedDict

from .okf import kb_root, create_agent, list_agents, rebuild_index


# The thin shell (CLI-agnostic workflow rules) lives in ensoul/SHELL.md so there
# is a single source of truth. init_cmd.py reads it from the package at runtime,
# which works both for editable installs (repo) and for wheels (package data).
@functools.lru_cache(maxsize=1)
def _load_shell() -> str:
    """Return the CLI-agnostic shell content shipped inside the package."""
    return resources.files("ensoul").joinpath("SHELL.md").read_text(encoding="utf-8")


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
    {
        "name": "Codex",
        "path": Path.home() / ".codex" / "AGENTS.md",
    },
]

# OpenCode uses a skill directory rather than a single marked markdown file.
_OPENCODE_SKILL_DIR = Path.home() / ".config" / "opencode" / "skills" / "sill-ensoul"


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
- **每个任务或里程碑结束时，主动回顾本轮是否有应该沉淀但漏掉的东西，有则立即补上。**
- 等某个领域（比如算法、后端）的经验攒够了，用 `create_agent` 把那部分记忆分裂出去，我继续当通用起点。
"""


def _marked_shell() -> str:
    shell = _load_shell().strip()
    return f"{_SHELL_START_MARKER}\n{shell}\n{_SHELL_END_MARKER}"


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


def _update_opencode_skill() -> str:
    """Update the OpenCode skill directory for sill-ensoul.

    OpenCode uses a skill system: each skill is a directory under
    ~/.config/opencode/skills/<name>/ containing a SKILL.md file. We create or
    overwrite the sill-ensoul skill with the current shell content.
    """
    skill_dir = _OPENCODE_SKILL_DIR
    skill_file = skill_dir / "SKILL.md"

    # Check whether OpenCode is installed at all.
    opencode_dir = skill_dir.parent.parent
    if not opencode_dir.exists():
        return "missing"

    skill_dir.mkdir(parents=True, exist_ok=True)

    # OpenCode SKILL.md uses YAML frontmatter with name/description.
    content = f"""---
name: sill-ensoul
description: Long-term memory system for agents across projects and sessions. Wake an agent with "wake up <agent_id>" and recall past experience via wiki_search/wiki_read.
---

{_load_shell().strip()}
"""
    skill_file.write_text(content, encoding="utf-8")
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

    # OpenCode is a skill-based CLI, handled separately.
    opencode_status = _update_opencode_skill()
    opencode_labels = {
        "updated": "updated skill",
        "missing": "missing (OpenCode not installed)",
    }
    print(f"  [{opencode_labels[opencode_status]}] OpenCode: {_OPENCODE_SKILL_DIR}/SKILL.md")
    if opencode_status == "updated":
        any_updated = True

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
        print(_load_shell())
        return 0

    if args.sync_shell:
        return sync_shell()

    if args.rebuild_index:
        return rebuild_indices()

    return init_kb()


if __name__ == "__main__":
    sys.exit(main())
