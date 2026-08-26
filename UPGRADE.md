# Sill-Ensoul Upgrade (machine-readable upgrade intent)

> **Who reads this**: the AI inside the user's CLI (Claude Code / Codex / zcode /
> OpenCode / any MCP-capable CLI). The user got this content to you in one of two
> ways:
> - they said *"upgrade sill-ensoul from `<repo>`/UPGRADE.md"* and you read the file, or
> - they pasted this document's content directly into the chat.
>
> Either way, the intent is the same: **bring the installed sill-ensoul up to the
> version of THIS repo, without touching the user's knowledge base and without
> breaking their existing CLI wiring.** Do the upgrade yourself — don't just print
> steps for the user to run. If anything is unclear, ask; otherwise proceed.
>
> **Relation to SETUP.md**: SETUP.md is for *first-time installation*. This file
> is for *everything after* — when the user says "upgrade", or when you discover
> the installed version is older than the repo version.

## Mental model: an upgrade has exactly 2 parts

sill-ensoul has two upgradeable things, and only two:

| Part | What it is | Where it lives | Who updates it |
|---|---|---|---|
| **Package (code)** | `sill-ensoul` Python package — `sill-ensoul-mcp` server, `sill-ensoul-init`, engine logic | Python site-packages (or an editable clone) | pip |
| **Shell (rules)** | CLI-agnostic workflow rules the LLM loads each session (`ensoul/SHELL.md`) | each CLI's instruction file, in a block marked `<!-- SILL-ENSOUL-SHELL-START --> ... <!-- SILL-ENSOUL-SHELL-END -->` | `sill-ensoul-init --sync-shell` |

The **knowledge base** (the user's actual accumulated memory, e.g.
`%LOCALAPPDATA%/ensoul/knowledge` on Windows, `ENSOUL_KB` if set) is **user data,
never part of an upgrade** — no version of sill-ensoul touches it. FTS index
schema changes are migrated automatically at runtime (schema version detection +
rebuild); the user does nothing.

**MCP server registration** (per-CLI config: `claude mcp add`, a config file, a
`.mcp.json`, platform MCP library, ...) points at the `sill-ensoul-mcp` command
and **survives package upgrades** — do not re-register unless verification fails.

## Step 0 — check what's installed

```bash
sill-ensoul-init --version     # installed package version
pip show sill-ensoul           # same thing, more detail
```

The version of THIS repo is what the user wants to reach. If they match, there is
nothing to upgrade — say so and stop.

## Step 1 — upgrade the package

**Safety boundary**: before running pip, TELL the user you're about to upgrade the
sill-ensoul package, show the command, and get their OK — same boundary as
SETUP.md. Don't upgrade silently.

There are two install routes; detect which one the user used:

- **Installed from GitHub** (`pip install git+https://github.com/sillogic/sill-ensoul.git`):
  ```bash
  pip install -U "git+https://github.com/sillogic/sill-ensoul.git"
  ```
- **Editable install from a local clone** (`pip install -e <repo>`): update the
  clone, then re-run the editable install so new entry points / package data take
  effect (code-only changes are already live in editable mode, but re-running is
  cheap and idempotent):
  ```bash
  git -C <repo> pull
  pip install -e <repo>
  ```

How to tell the routes apart: `pip show sill-ensoul` → `Location`. An editable
install points *inside* the clone directory (and shows `Editable project
location`); a GitHub install points into site-packages.

## Step 2 — sync the shell (rules update)

The package upgrade ships a new `SHELL.md`. The copies already pasted into the
user's CLI instruction files are now stale. Bring them up to date:

```bash
sill-ensoul-init --sync-shell
```

What it does: for each supported CLI instruction file (Claude Code
`~/.claude/CLAUDE.md`, Zcode `~/.zcode/AGENTS.md`, Codex `~/.codex/AGENTS.md`,
OpenCode `~/.config/opencode/AGENTS.md` — the built-in list) that **already
contains** the sill-ensoul markers, it replaces the marked block with the new
shell **in place** (no duplication) and writes a backup next to the file
(`.sill-ensoul.bak`). Files without markers are left untouched and reported as
"unmarked".

For a CLI whose instruction file has **no markers** yet (shell was appended
without markers, or the CLI isn't in the built-in list): check whether the shell
is already present (search for a known phrase like `wiki_write_concept` or
`sill-ensoul`). If absent, append once:

```bash
sill-ensoul-init --print-shell >> <CLI instruction file>
```

**Never append twice** — duplicate rule blocks are worse than stale ones. When in
doubt, ask the user whether that CLI was set up before.

## Step 3 — verify

```bash
sill-ensoul-init --version       # now shows the new version
sill-ensoul-init --sync-shell    # re-run: everything "updated" or "missing", no errors
```

Then have the user **restart their CLI** (instruction files load at startup, not
hot-reloaded). In the new session, wake an agent (`唤醒 alter-ego` / `wake up
alter-ego`) or call `list_agents` — if the tools answer, the upgrade is complete.
If the MCP tools are missing, re-check the server registration (SETUP.md step 1)
and re-register only then.

## What NOT to do (an upgrade is not a reinstall)

- **Don't touch the KB.** Never delete / reset / re-create
  `%LOCALAPPDATA%/ensoul/knowledge` (or the `ENSOUL_KB` target) — that is the
  user's accumulated memory. An upgrade never needs it.
- **Don't rely on `sill-ensoul-init` (no flags) to "apply" the upgrade.** It is
  first-time initialization and idempotent — it will just report the KB already
  exists. It won't refresh a stale shell; that's `--sync-shell`'s job.
- **Don't re-register the MCP server unless verification fails.**
- **Don't overwrite the user's CLI instruction files.** `--sync-shell` replaces
  only the marked block; anything else is append-once or hands-on.
- **Don't modify this repo's files.** The upgrade updates the *installed* copy
  and the CLI wiring, not the source.
- **Don't upgrade silently.** pip runs need the user's OK first.

## After upgrade — you MUST report this to the user

Once done, do not just say "done". Say something like (adapt wording naturally,
but cover the points):

---

**✅ sill-ensoul upgraded to <version>.** Restart your CLI now, then wake an agent
(`唤醒 alter-ego`) to confirm everything works.

- Your memory was **not touched** — all agents and their experience are intact.
- CLI shells were re-synced to the new rules (`sill-ensoul-init --sync-shell`).
- Later version check: `sill-ensoul-init --version`

---
