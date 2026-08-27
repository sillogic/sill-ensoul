# Sill-Ensoul

English | [简体中文](README.zh-CN.md)

**Long-term memory that follows your agents across CLIs, projects, and sessions.**

Give your CLI agents experience that doesn't vanish when you switch projects, switch tools, or start a new session — it doesn't touch your workflow, just adds memory to the agents you already use.

> *ensoul* /ɪnˈsoʊl/ — verb. To give a CLI agent memory that carries across sessions, so it's more than a blank slate each time. An agent that's been ensouled is called an **ensouler**.

---

## What it does

- **Cross-CLI**: one memory, shared across Claude Code / Codex / zcode / Cursor / OpenCode. Use Claude today, switch to Codex tomorrow — your agents' memory follows.
- **Cross-project**: memory lives in a global KB, not bound to any project repo. The bug your algo agent hit in project A is recalled in project B.
- **Cross-session**: every new conversation, the agent `wiki_search`es its own past experience first and starts with memory, not from scratch.
- **Agent isolation**: spin up multiple ensoulers (algorithm engineer, backend, testing, UI...) — each has its own memory bundle, no cross-contamination. Wake one, work with its experience.
- **Memory is files**: plain markdown (following [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)) — git-able, diff-able, editable in Obsidian. Vector stores are just an index; md is always source of truth.
- **Zero external deps**: SQLite FTS5 full-text search (CJK char segmentation + BM25) — no OpenAI key, no Docker, no cloud service. Model-vendor-agnostic: inference always stays in your CLI.
- **Proactive distillation**: when an agent hits a non-trivial pitfall or makes a reusable decision, it **distills and writes it directly, then tells you what it wrote** (concept_id + one-line gist). You don't have to remember to write things down, and you keep after-the-fact veto (ask it to delete/edit).

---

## Quick Start

After cloning, do **one** of these in your CLI (Claude Code / Codex / zcode / OpenCode, etc.):

```text
# Option A: let the CLI's AI set it up (recommended — you send one message)
say: set up sill-ensoul from <repo>/SETUP.md

# Option B: more direct — paste SETUP.md contents into the chat, hit enter
```

The CLI's AI follows [SETUP.md](SETUP.md): installs the package → builds the KB → creates the default agent `alter-ego` → registers the MCP server → installs the shell. Restart the CLI, then say:

```text
wake up alter-ego      # or 唤醒 alter-ego / 唤醒分身
```

`alter-ego` is your digital twin (default agent, empty memory). Accumulate experience with it first; once a domain (algorithm/backend/ ...) has enough, tell the CLI "create an agent called algo-engineer" for a specialized role.

<details>
<summary>Don't want the AI to install? Manual 3 steps</summary>

```bash
pip install -e <repo>          # or, once published: pip install sill-ensoul
sill-ensoul-init               # builds the global KB + default agent alter-ego
# then have the CLI's AI read SETUP.md to finish MCP registration + shell install
```

Requires **Python >= 3.10**.
</details>

<details>
<summary>Where is memory stored? Can I sync it via cloud?</summary>

Global KB, not inside any project repo (private memory never enters git):

| Platform | Default path |
|---|---|
| Windows | `%LOCALAPPDATA%\ensoul\knowledge` |
| macOS | `~/Library/Application Support/ensoul/knowledge` |
| Linux | `$XDG_DATA_HOME/ensoul/knowledge` (default `~/.local/share/ensoul/knowledge`) |

Set `ENSOUL_KB=<path>` to put it anywhere (e.g. a Dropbox / iCloud folder for multi-device sync). Open that folder in Obsidian — each agent is a subfolder, the `.md` files inside are the memory.
</details>

<details>
<summary>CLI maintenance commands</summary>

After install, `sill-ensoul-init` provides a few maintenance commands:

| Command | Purpose |
|---|---|
| `sill-ensoul-init` | Initialize the global KB + default `alter-ego` agent (idempotent). |
| `sill-ensoul-init --print-shell` | Print the CLI-agnostic shell for manual append to a CLI instruction file. |
| `sill-ensoul-init --sync-shell` | Auto-update sill-ensoul shell segments in supported CLI instruction files (Claude Code, Zcode, Codex, OpenCode). |
| `sill-ensoul-init --rebuild-index` | Rebuild the SQLite FTS index for every agent from the `.md` source of truth. |
| `sill-ensoul-init --version` | Print the installed package version (for upgrade checks). |

Supported CLI instruction files are detected automatically; only the ones that exist and already contain sill-ensoul markers are updated.
</details>

---

## Upgrade

Upgrading an existing install is two parts, three commands — and your KB is
**never touched** (upgrades update the package code and re-sync the shell rules
only; your agents' memory stays put):

```bash
sill-ensoul-init --version                                   # what's installed now
pip install -U "git+https://github.com/sillogic/sill-ensoul.git"   # or: git pull && pip install -e <repo>
sill-ensoul-init --sync-shell                                # refresh shell rules in CLI instruction files
```

Restart your CLI. The full machine-readable intent for the CLI's AI (route
detection, verification, what-not-to-do) is [UPGRADE.md](UPGRADE.md) — say
*"upgrade sill-ensoul from `<repo>`/UPGRADE.md"* and the CLI handles it.

---

## How it works

```
  Claude Code / Codex / zcode / Cursor   ← inference runs in each CLI's model vendor, not locked
           |  load persona + wiki slice (thin shell: AGENTS.md / CLAUDE.md)
        sill-ensoul-mcp (MCP server, 8 tools, read/write/search)
           |  read/write
  knowledge/agents/<id>/   ← one OKF bundle per ensouler (markdown files)
  knowledge/agents/<id>/.fts/index.db   ← local SQLite FTS5 index, derived from the .md files
```

**Three-layer separation** (design decisions D1/D2, see [docs/ROADMAP.md](docs/ROADMAP.md)):

- **Engine** (`ensoul/`) — CLI-agnostic, handles data/tools only, no inference. `server.py` is a thin MCP shell, pass-through only.
- **Shell** (`AGENTS.md` / `CLAUDE.md`) — one per CLI, defines "when to wake/search/distill", references the shared [WORKFLOW.md](WORKFLOW.md).
- **Memory** (`knowledge/agents/<id>/`) — OKF markdown files, git-able, diff-able, human-readable.

**About the `.fts/index.db` file**: Each agent bundle has a local SQLite FTS5 index that caches metadata and accelerates search. It is derived data — the `.md` files are always the source of truth. You can delete `.fts/` at any time; it will be rebuilt on demand. SQLite is part of Python's standard library, so there is no extra install and no separate database process.

Core loop: **wake** (load persona + knowledge map) → **recall** (search relevant experience) → **cite** (reference real memory with concept_id) → **distill** (new experience, written directly with a heads-up). Memory persists across projects and sessions.

---

## 8 Tools

| Tool | Purpose |
|---|---|
| `list_agents` | List all ensoulers |
| `create_agent` | Create an ensouler (dir + persona + index + log template) |
| `delete_agent` | Delete an ensouler (irreversible, confirm first) |
| `agent_index` | Wake/switch ensouler (persona + knowledge map) |
| `wiki_search` | Full-text search an ensouler's experience (FTS5 + BM25, with CJK segmentation) |
| `wiki_read` | Read a concept's details |
| `wiki_write_concept` | Distill new experience (type required) |
| `wiki_append_log` | Log a change |

> Multi-ensouler collaboration needs no dedicated tools: any agent can use `wiki_write_concept(agent_id=...)` to operate on **another** agent's memory — orchestrator reads/writes directly (see [docs/ROADMAP.md](docs/ROADMAP.md) D6).

---

## Remote deployment (HTTP server)

Run the **same 8 tools** as a Streamable HTTP MCP server on any machine (VPS / home server / tailnet) so multiple machines share **one** knowledge base. Every request is gated by a static **Bearer token** (SIL-7 / D11) — single-tenant today, with an identity→KB-root seam for future multi-tenancy.

```bash
pip install "sill-ensoul[http]"            # stdio installs stay zero-extra-dep
ENSOUL_MCP_TOKEN=$(openssl rand -hex 32)   # or: python -c "import secrets;print(secrets.token_hex(32))"
ENSOUL_MCP_TOKEN=... sill-ensoul-http      # default bind 0.0.0.0:8930
```

- **Fail-closed**: the server **refuses to start without `ENSOUL_MCP_TOKEN`** — an unauthenticated remote server is exactly what this is for.
- Optional: `ENSOUL_MCP_HOST` / `ENSOUL_MCP_PORT` env overrides (or `--host` / `--port`). The KB root is still `ENSOUL_KB` / the platform default.

Point a CLI's MCP config at it (streamable-http clients send the header on every request):

```jsonc
{ "type": "streamable-http", "url": "http://<server>:8930/mcp",
  "headers": { "Authorization": "Bearer <token>" } }
```

or via a stdio↔HTTP bridge: `npx mcp-remote http://<server>:8930/mcp --header "Authorization: Bearer <token>"`.

> **Security notes**: the token is the auth boundary — never commit it; prefer a private network (Tailscale / VPN / firewall) for transport security; the stdio server (`sill-ensoul-mcp`) stays local-only and needs no token.

---

## Tests

```bash
pip install -e .
python -m tests.run_tests
```

Four release tests, all green = core loop works (each builds its own temp KB, runs straight after clone):

| Test | Verifies |
|---|---|
| `test_search` | FTS5 search + persona exclusion (11 regressions) |
| `test_mcp_live` | MCP shell layer (8 tools, real stdio) |
| `test_http_live` | HTTP transport + Bearer auth (fail-closed, 401 gate, real uvicorn e2e) |
| `test_cross_project` | Cross-project memory retention (end-to-end) |

---

## Status

- ✅ Core loop works: wake → recall → cite → distill → cross-project retention
- ✅ Installable: `pip install` + `sill-ensoul-init` self-boots CLI setup
- ✅ Cross-CLI verified: zcode + Claude Code both adapted
- ✅ Design final: auto-distill + notify-after (not pre-write confirmation, not full-auto). Multi-agent collaboration via orchestrator model (D6).
- See [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Dig deeper

- [docs/DESIGN.md](docs/DESIGN.md) — design background: why OKF, why MCP, comparison with mem0/letta/graphiti
- [docs/ROADMAP.md](docs/ROADMAP.md) — progress + design decisions D1-D11 + historical pitfalls H1-H12
- [docs/multica.md](docs/multica.md) — platform integration guide (Multica): wake-up block template, degradation rules, batch onboarding
- [WORKFLOW.md](WORKFLOW.md) — CLI-agnostic workflow (wake/recall/distill/skill dispatch)
- [SETUP.md](SETUP.md) — machine-readable adaptation intent for the CLI's AI
- [UPGRADE.md](UPGRADE.md) — machine-readable upgrade intent for the CLI's AI

## License

Released under the [MIT License](LICENSE) © 2026 sillogic.
