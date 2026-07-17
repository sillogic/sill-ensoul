# Sova CLI Setup (machine-readable adaptation intent)

> **Who reads this**: the AI inside the user's CLI (Claude Code / Codex / zcode /
> any MCP-capable CLI). The user got this content to you in one of two ways:
> - they said *"set up sova from `<repo>`/SETUP.md"* and you read the file, or
> - they pasted this document's content directly into the chat.
>
> Either way, the intent is the same: **wire sova into THIS CLI so the user can
> start working. Do the adaptation yourself — don't just print steps for the user
> to run.** If anything is unclear, ask; otherwise proceed.
>
> **Why a single intent file (not per-CLI scripts)**: CLIs change their config
> formats over time. Rather than sova hardcoding each CLI's commands, this file
> states the *desired end state* and *constraints*. You (the CLI's AI) know best
> how your own CLI registers MCP servers and where its instruction file lives —
> use the current mechanism. sova stays CLI-agnostic.

## Prerequisites — you (the CLI AI) handle these, don't offload to the user

The user's goal is to say ONE sentence ("set up sova from `<repo>`/SETUP.md") and
have everything work. So before adapting the CLI, ensure these are true — do them
yourself if not:

### 1. sova package installed

Check if `sova-mcp` is on PATH (e.g. `sova-mcp --help` or `which sova-mcp`). If
not, install it. The user cloned the repo, so:

```bash
pip install -e <repo>
```

(or `pip install git+https://github.com/<user>/sova.git` if installing from GitHub
without a local clone). After install, `sova-mcp` and `sova-init` commands are on
PATH.

**Safety boundary**: before running pip install, TELL the user you're about to
install the sova package (from `<repo>` / GitHub) and get their OK. Don't install
silently. Show them the command. If they decline, stop and explain sova can't run
without the package.

### 2. Knowledge base initialized

Run `sova-init` yourself (it's now on PATH). This creates the global KB
(`%LOCALAPPDATA%/sova/knowledge` on Windows,
`~/Library/Application Support/sova/knowledge` on macOS,
`XDG_DATA_HOME/sova/knowledge` on Linux, `~/.sova/knowledge` fallback) and the
default agent `alter-ego` (digital
twin, empty memory). It's idempotent — safe to run if already initialized (it'll
skip). No user input needed.

If the user wants the KB somewhere specific, set `SOVA_KB=<path>` before running
`sova-init` — but only if they asked; the default global location is fine
otherwise.

### 3. Default agent `alter-ego` exists

`sova-init` creates it. Verify with `sova-init` output (it says "Created default
agent 'alter-ego'") or by checking the KB dir has `agents/alter-ego/`.

Only after all three are true, proceed to CLI adaptation below.

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

## After setup — you MUST report this to the user (they didn't read the README)

Once adaptation is done and verified, **do not just say "done"**. Output a short
report so the user knows exactly what to do next. Use this structure (adapt the
wording naturally, but cover all three points):

---

**✅ sova is set up.** Restart this CLI now (config/instruction files load at
startup, not hot-reloaded), then in a new session:

**👉 Say `唤醒 alter-ego`** (or `wake up alter-ego` / `唤醒分身`) to start.
`alter-ego` is your digital twin — empty memory, accumulate experience with it
first.

**Going further** (no need to read docs):
- Want your own agent name? Tell me "create an agent called <name>", then say
  `唤醒 <name>`.
- After a while I'll proactively remind you when something is worth saving to
  memory — you confirm, I write it.
- To read/edit your memory directly, open the KB in Obsidian:
  - Windows: `%LOCALAPPDATA%\sova\knowledge`
  - macOS: `~/Library/Application Support/sova/knowledge`
  - Linux: `~/.local/share/sova/knowledge`

---

That report is the user's whole onboarding — they pasted SETUP.md, you ran it,
you told them the wake word and the basics. They never need to open the README
for the common path. (README still exists for design background, full tool
reference, and troubleshooting — point them there only if they ask for depth.)
