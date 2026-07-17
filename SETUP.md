# Sova CLI Setup (machine-readable adaptation intent)

> **Who reads this**: the AI inside the user's CLI (Claude Code / Codex / zcode /
> any MCP-capable CLI). The user will point you here with a prompt like
> *"set up sova from `<repo>`/SETUP.md"*. Your job: wire sova into THIS CLI so the
> user can start working. Do the adaptation yourself — don't just print steps for
> the user to run.
>
> **Why a single intent file (not per-CLI scripts)**: CLIs change their config
> formats over time. Rather than sova hardcoding each CLI's commands, this file
> states the *desired end state* and *constraints*. You (the CLI's AI) know best
> how your own CLI registers MCP servers and where its instruction file lives —
> use the current mechanism. sova stays CLI-agnostic.

## Prerequisites (already done if the user ran `sova-init`)

- sova package installed: `sova-mcp` and `sova-init` console commands on PATH.
- Knowledge base initialized at the global default (`%LOCALAPPDATA%/sova/knowledge`
  on Windows, `XDG_DATA_HOME/sova/knowledge` on Linux, `~/.sova/knowledge` fallback).
  Override with `SOVA_KB` env var if the user wants it elsewhere.
- Default agent `alter-ego` (digital twin) created with empty memory.

If `sova-init` hasn't been run, tell the user to run it first, then continue.

## Goal: three things must be true when you're done

### 1. The sova MCP server is registered with this CLI

- **Server name**: `sova`
- **Command**: `sova-mcp` (a console script on PATH; runs the stdio MCP server)
- **Scope**: user-level (available across all projects, not per-project) — unless
  the user asks for project scope.
- No args, no env vars required for normal operation. (`SOVA_KB` is optional,
  only if the user wants a non-default KB location.)

How you register it depends on THIS CLI's current mechanism — check your own
docs/config format. Examples of what "register" looks like across CLIs (for your
reference, not prescriptive): `claude mcp add ...`, editing a `config.json` under
the CLI's config dir, or a `.mcp.json` at project root. Use whatever is current.

### 2. The sova shell is installed into this CLI's instruction file

- **Shell content**: the output of `sova-init --print-shell` (also stored as
  `SHELL.md` in the repo root). It's CLI-agnostic workflow rules for the LLM.
- **Target file**: wherever THIS CLI reads its system instructions from
  (e.g. `~/.claude/CLAUDE.md`, `~/.zcode/AGENTS.md`, a Codex skill, etc.).
  You know where your own CLI's instruction file is.
- **CRITICAL — append, don't overwrite**: if the target file already has content,
  APPEND the sova shell (use `>>` or insert at end), never `>` overwrite. The
  sova shell is an independent rule block and coexists with existing instructions.
  If you're unsure, back up the file first.
- After appending, the shell's "Default agent" note tells the LLM that
  `alter-ego` is the default agent and maps "wake up" / "唤醒" / "digital twin"
  / "分身" to `agent_index("alter-ego")`.

### 3. Verified working

After steps 1-2, the user must restart this CLI (config/instruction files are
loaded at startup, not hot-reloaded). Then in a new session, verify by either:

- User says "wake up alter-ego" (or "唤醒 alter-ego" / "唤醒分身") → the CLI
  should call the `agent_index` tool with `agent_id="alter-ego"` and receive the
  persona preview. If that works, setup is complete.
- Or directly invoke the `list_agents` tool → should return a list including
  `alter-ego`.

If the tools aren't available at all, the MCP server registration failed —
re-check step 1. If tools are there but `alter-ego` isn't found, `sova-init`
wasn't run or KB location differs — check `SOVA_KB` / run `sova-init`.

## What NOT to do

- Don't hardcode paths assuming a specific CLI (e.g. don't assume `~/.claude/`).
  Detect or ask which CLI you're running in.
- Don't overwrite the user's existing instruction file.
- Don't install skills or packages on the user's behalf beyond sova itself.
- Don't modify sova's repo files — setup is about wiring sova INTO the CLI,
  not changing sova.

## After setup

Tell the user: setup is done, say "wake up alter-ego" (or "唤醒 alter-ego") to
start. The default agent has empty memory — accumulate experience with it first;
split off a specialized agent via `create_agent` when a domain has enough.

For full workflow rules, the shell references `WORKFLOW.md` in the sova repo
(absolute path embedded in the shell content). For design background, see
`docs/DESIGN.md`; for progress/decisions, `docs/ROADMAP.md`.
