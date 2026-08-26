# Sill-Ensoul CLI Setup (machine-readable adaptation intent)

> **Who reads this**: the AI inside the user's CLI (Claude Code / Codex / zcode / OpenCode /
> any MCP-capable CLI). The user got this content to you in one of two ways:
> - they said *"set up sill-ensoul from `<repo>`/SETUP.md"* and you read the file, or
> - they pasted this document's content directly into the chat.
>
> Either way, the intent is the same: **wire sill-ensoul into THIS CLI so the user can
> start working. Do the adaptation yourself — don't just print steps for the user
> to run.** If anything is unclear, ask; otherwise proceed.
>
> **Why a single intent file (not per-CLI scripts)**: CLIs change their config
> formats over time. Rather than sill-ensoul hardcoding each CLI's commands, this file
> states the *desired end state* and *constraints*. You (the CLI's AI) know best
> how your own CLI registers MCP servers and where its instruction file lives —
> use the current mechanism. sill-ensoul stays CLI-agnostic.
>
> **Already set up?** This file is for *first-time installation*. If the user says
> "upgrade" (or re-drops this file on a machine that already has sill-ensoul),
> read [UPGRADE.md](UPGRADE.md) instead — it upgrades the package and re-syncs
> the shell without re-running first-time steps.

## Prerequisites — you (the CLI AI) handle these, don't offload to the user

The user's goal is to say ONE sentence ("set up sill-ensoul from `<repo>`/SETUP.md") and
have everything work. So before adapting the CLI, ensure these are true — do them
yourself if not:

### 1. sill-ensoul package installed

Check if `sill-ensoul-mcp` is on PATH (e.g. `sill-ensoul-mcp --help` or `which sill-ensoul-mcp`). If
not, install it. The user cloned the repo, so:

```bash
pip install -e <repo>
```

(or `pip install git+https://github.com/<user>/sill-ensoul.git` if installing from GitHub
without a local clone). After install, `sill-ensoul-mcp` and `sill-ensoul-init` commands are on
PATH.

**Safety boundary**: before running pip install, TELL the user you're about to
install the sill-ensoul package (from `<repo>` / GitHub) and get their OK. Don't install
silently. Show them the command. If they decline, stop and explain sill-ensoul can't run
without the package.

### 2. Knowledge base initialized

Run `sill-ensoul-init` yourself (it's now on PATH). This creates the global KB
(`%LOCALAPPDATA%/ensoul/knowledge` on Windows,
`~/Library/Application Support/ensoul/knowledge` on macOS,
`XDG_DATA_HOME/ensoul/knowledge` on Linux, `~/.ensoul/knowledge` fallback) and the
default agent `alter-ego` (digital
twin, empty memory). It's idempotent — safe to run if already initialized (it'll
skip). No user input needed.

If the user wants the KB somewhere specific, set `ENSOUL_KB=<path>` before running
`sill-ensoul-init` — but only if they asked; the default global location is fine
otherwise.

### 3. Default agent `alter-ego` exists

`sill-ensoul-init` creates it. Verify with `sill-ensoul-init` output (it says "Created default
agent 'alter-ego'") or by checking the KB dir has `agents/alter-ego/`.

Only after all three are true, proceed to CLI adaptation below.

## Goal: three things must be true when you're done

### 1. The sill-ensoul MCP server is registered with this CLI

- **Server name**: `sill-ensoul`
- **Command**: `sill-ensoul-mcp` (a console script on PATH; runs the stdio MCP server)
- **Scope**: user-level (available across all projects, not per-project) — unless
  the user asks for project scope.
- No args, no env vars required for normal operation. (`ENSOUL_KB` is optional,
  only if the user wants a non-default KB location.)

How you register it depends on THIS CLI's current mechanism — check your own
docs/config format. Examples of what "register" looks like across CLIs (for your
reference, not prescriptive): `claude mcp add ...`, editing a `config.json` under
the CLI's config dir, or a `.mcp.json` at project root. Use whatever is current.

### 2. The sill-ensoul shell is installed into this CLI's instruction file

- **Shell content**: the output of `sill-ensoul-init --print-shell` (also stored as
  `ensoul/SHELL.md` in the package). It's CLI-agnostic workflow rules for the LLM.
- **Target file**: wherever THIS CLI reads its system instructions from
  (e.g. `~/.claude/CLAUDE.md`, `~/.zcode/AGENTS.md`, `~/.codex/AGENTS.md`,
  `~/.config/opencode/AGENTS.md`). You know where your own CLI's instruction file is.
- **CRITICAL — append, don't overwrite**: if the target file already has content,
  APPEND the ensouler shell (use `>>` or insert at end), never `>` overwrite. The
  sill-ensoul shell is an independent rule block and coexists with existing instructions.
  If you're unsure, back up the file first.
- **If the file already contains `<!-- SILL-ENSOUL-SHELL-START -->`** (from a
  previous setup or upgrade), do NOT append again — that would create a duplicate
  block. Run `sill-ensoul-init --sync-shell` to replace the marked block in place.
- **To check the installed version** (e.g. before deciding whether an upgrade is
  needed): `sill-ensoul-init --version`.
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
re-check step 1. If tools are there but `alter-ego` isn't found, `sill-ensoul-init`
wasn't run or KB location differs — check `ENSOUL_KB` / run `sill-ensoul-init`.

If search feels slow or returns stale results after the user manually edits `.md`
files outside the tools, run `sill-ensoul-init --rebuild-index` to rebuild the
local SQLite FTS index from the markdown source of truth.

## Multica adaptation (this file arrived via a Multica conversation)

The user may have dropped this file into a **Multica conversation** instead of a
CLI. The intent is the same — wire sill-ensoul into THIS workspace — but the
adaptation targets are Multica's own, not a per-CLI config. The receiving agent
(this one) performs the setup; the user's ensoul interface is a **new dedicated
agent** created for the default 分身 `alter-ego` (the digital twin
`sill-ensoul-init` creates) and bound to it 1:1. Do NOT rename this receiving
agent — it keeps its own identity.

1. **Install ensoul into every CLI Multica recognizes on this machine — the
   platform MCP library is NOT registered** (SIL-26 final decision 2026-08-26:
   Multica doesn't host ensoul; the CLIs that Multica runs get ensoul). Result:
   any runtime Multica uses has the tools, zero per-agent config, no
   double-wiring. Idempotent — safe to re-run any time:

   a. **Package + KB, machine-level, once** (idempotent):
      - `sill-ensoul-mcp` on PATH? If not, `pip install sill-ensoul` (or
        `pip install -e <repo>`) — same safety boundary: tell the user first,
        show the command, get their OK. If yes, check the version with
        `sill-ensoul-init --version` against the repo/release version — if the
        installed one is older, run the UPGRADE.md flow (upgrade package +
        `sill-ensoul-init --sync-shell`).
      - Run `sill-ensoul-init` (idempotent — creates the global KB + default
        分身 `alter-ego`, skips if already there).
   b. **Detect the CLIs** — the set Multica recognizes on this machine:
      - `multica runtime list --output json` → the runtimes registered for this
        machine (provider field), AND
      - scan PATH for the known agent CLI commands (`claude` / `codex` /
        `opencode` / `pi` / `cursor-agent` / `kimi` / `qodercli` / `qwen` / …
        — the same known-command list the Multica daemon probes; inside a task
        `multica daemon probe-runtimes` is unavailable, so use runtime list +
        PATH scan and take the union).
      - Each unique CLI in the union gets step c.
   c. **Per CLI, idempotent**:
      - Already has the sill-ensoul MCP server registered (its own config)?
        Skip registration. Not registered → register using THAT CLI's current
        mechanism (the per-CLI steps earlier in this file are the reference:
        `claude mcp add --scope user`, a config-file entry, `.mcp.json`, or the
        pi extension `~/.pi/agent/settings.json` + `mcp-bridge.ts` — each CLI
        has its own).
      - Instruction file already contains `<!-- SILL-ENSOUL-SHELL-START -->`?
        Skip. Not present → append `sill-ensoul-init --print-shell` output once
        (never append twice; if unsure, ask).
      - No per-CLI version step needed: one machine = one server version = one
        KB, and step a already aligned the package.
   d. **Do NOT register the platform MCP library** (`multica workspace mcp add`
      / `multica agent mcp add`). It's a future option (remote server / several
      runtimes coexisting / multi-machine) — not part of this setup.
2. **Create the Multica agent for the default 分身 `alter-ego` and bind it**:
   Multica agents and ensoul 分身 are bound 1:1 — the binding is a wake-up block
   in the agent's `instructions` (there is no platform-level link). Create a new
   agent that IS the digital twin on the board:
   ```bash
   multica agent create \
     --name "alter-ego" \
     --description "<alter-ego AGENT.md title/description>" \
     --instructions "<platform base + 分身绑定 wake-up block>" \
     --runtime-id <runtime that can reach the ensoul MCP tools> \
     --model <same model as this agent> \
     --permission-mode public_to --public-to-workspace
   ```
   - **Base instructions**: copy THIS agent's current platform instructions as
     the starting point (so the new agent is a full Multica citizen), then
     APPEND the `## 分身绑定(1:1)` wake-up block from `shells/multica/AGENTS.md`
     in the repo — replacing `<分身id>` with `alter-ego` and the persona line
     with the alter-ego persona (数字分身). **Append, don't overwrite.**
   - **Identity-priority line** — the wake-up block must carry
     `**身份优先级**:平台行为契约(issue 工作流/评论纪律)优先;分身用于专业判断与记忆。`
     The `ensoul-multica-binding` skill template already has it; if you hand-write
     the block, add it — new bindings are born with it, not patched later.
   - **Runtime/model**: pick any local runtime on this machine — after step 1
     every CLI Multica recognizes here has ensoul, so every runtime has the
     tools. Use the same model this agent uses.
   - **Attach the binding skill (if present)**: `multica skill list` — if
     `ensoul-multica-binding` exists, attach it so the new agent can bind further
     agents/分身 later: `multica agent skills add <new-agent-id> --skill-ids
     <skill-id>`. On a very first install the skill may not exist yet — the
     wake-up block alone IS the binding; the skill only adds future-binding
     capability.
3. **Verify**: `multica agent get <new-agent-id> --output json` shows name
   `alter-ego`, instructions contain the wake-up block, and the agent can call
   the `list_agents` / `agent_index` tools (e.g. `list_agents` must include
   `alter-ego`).

## What NOT to do

- Don't hardcode paths assuming a specific CLI (e.g. don't assume `~/.claude/`).
  Detect or ask which CLI you're running in.
- Don't overwrite the user's existing instruction file.
- Don't install skills or packages on the user's behalf beyond sill-ensoul itself.
- Don't modify ensouler's repo files — setup is about wiring sill-ensoul INTO the CLI,
  not changing sill-ensoul.

## After setup — you MUST report this to the user (they didn't read the README)

Once adaptation is done and verified, **do not just say "done"**. Output a short
report so the user knows exactly what to do next. Use this structure (adapt the
wording naturally, but cover all three points):

---

**✅ sill-ensoul is set up.**

- **In Multica**: open the new **`alter-ego`** agent and start a chat there — it
  is your digital twin. Say `唤醒 alter-ego` (or `wake up alter-ego` / `唤醒分身`)
  in that conversation to start.
- **In a CLI you use directly**: every detected CLI was wired in step 1 —
  restart that CLI (config/instruction files load at startup, not
  hot-reloaded), then in a new session:

**👉 Say `唤醒 alter-ego`** (or `wake up alter-ego` / `唤醒分身`) to start.
`alter-ego` is your digital twin — empty memory, accumulate experience with it
first.

**Going further** (no need to read docs):
- Want your own agent name? Tell me "create an agent called <name>", then say
  `唤醒 <name>`.
- After a while I'll automatically distill reusable experience into your wiki
  and tell you what I wrote (concept_id + one-line gist). You can always ask me
  to delete or edit it afterward.
- To read/edit your memory directly, open the KB in Obsidian:
  - Windows: `%LOCALAPPDATA%\ensoul\knowledge`
  - macOS: `~/Library/Application Support/ensoul/knowledge`
  - Linux: `~/.local/share/ensoul/knowledge`

---

That report is the user's whole onboarding — they pasted SETUP.md, you ran it,
you told them the wake word and the basics. They never need to open the README
for the common path. (README still exists for design background, full tool
reference, and troubleshooting — point them there only if they ask for depth.)
