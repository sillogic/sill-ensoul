# Sill-Ensoul

English | [简体中文](README.zh-CN.md)

**Long-term memory that follows your agents across CLIs, projects, and sessions.**

Give your CLI agents experience that doesn't vanish when you switch projects, switch tools, or start a new session — it doesn't touch your workflow, just adds memory to the agents you already use.

> *ensoul* /ɪnˈsoʊl/ — verb. To give a CLI agent memory that carries across sessions, so it's more than a blank slate each time. An agent that's been ensouled is called an **ensouler**.

---

## What it does

- **Cross-CLI**: one memory, shared across Claude Code / Codex / zcode / Cursor. Use Claude today, switch to Codex tomorrow — your agents' memory follows.
- **Cross-project**: memory lives in a global KB, not bound to any project repo. The bug your algo agent hit in project A is recalled in project B.
- **Cross-session**: every new conversation, the agent `wiki_search`es its own past experience first and starts with memory, not from scratch.
- **Agent isolation**: spin up multiple ensoulers (algorithm engineer, backend, testing, UI...) — each has its own memory bundle, no cross-contamination. Wake one, work with its experience.
- **Memory is files**: plain markdown (following [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)) — git-able, diff-able, editable in Obsidian. Vector stores are just an index; md is always source of truth.
- **Zero external deps**: SQLite FTS5 full-text search (CJK char segmentation + BM25) — no OpenAI key, no Docker, no cloud service. Model-vendor-agnostic: inference always stays in your CLI.
- **Proactive distillation**: when an agent hits a non-trivial pitfall or makes a reusable decision, it **proactively reminds you** "this is worth saving to the wiki" — you confirm before it writes. So you don't have to remember to write things down, and nothing lands in memory without your say-so.

---

## Quick Start

After cloning, do **one** of these in your CLI (Claude Code / Codex / zcode, etc.):

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

---

## How it works

```
  Claude Code / Codex / zcode / Cursor   ← inference runs in each CLI's model vendor, not locked
           |  load persona + wiki slice (thin shell: AGENTS.md / CLAUDE.md)
        sill-ensoul-mcp (MCP server, 8 tools, read/write/search)
           |  read/write
  knowledge/agents/<id>/   ← one OKF bundle per ensouler (markdown files)
```

**Three-layer separation** (design decisions D1/D2, see [docs/ROADMAP.md](docs/ROADMAP.md)):

- **Engine** (`ensoul/`) — CLI-agnostic, handles data/tools only, no inference. `server.py` is a thin MCP shell, pass-through only.
- **Shell** (`AGENTS.md` / `CLAUDE.md`) — one per CLI, defines "when to wake/search/distill", references the shared [WORKFLOW.md](WORKFLOW.md).
- **Memory** (`knowledge/agents/<id>/`) — OKF markdown files, git-able, diff-able, human-readable.

Core loop: **wake** (load persona + knowledge map) → **recall** (search relevant experience) → **cite** (reference real memory with concept_id) → **distill** (new experience, written only after you confirm). Memory persists across projects and sessions.

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

## Tests

```bash
pip install -e .
python -m tests.run_tests
```

Three release tests, all green = core loop works (each builds its own temp KB, runs straight after clone):

| Test | Verifies |
|---|---|
| `test_search` | FTS5 search + persona exclusion (11 regressions) |
| `test_mcp_live` | MCP shell layer (8 tools, real stdio) |
| `test_cross_project` | Cross-project memory retention (end-to-end) |

---

## Status

- ✅ Core loop works: wake → recall → cite → distill → cross-project retention
- ✅ Installable: `pip install` + `sill-ensoul-init` self-boots CLI setup
- ✅ Cross-CLI verified: zcode + Claude Code both adapted
- ✅ Design final: reminder-style semi-auto distillation is the intended design (not a placeholder for full-auto). Multi-agent collaboration via orchestrator model (D6).
- See [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Dig deeper

- [docs/DESIGN.md](docs/DESIGN.md) — design background: why OKF, why MCP, comparison with mem0/letta/graphiti
- [docs/ROADMAP.md](docs/ROADMAP.md) — progress + design decisions D1-D6 + historical pitfalls H1-H12
- [WORKFLOW.md](WORKFLOW.md) — CLI-agnostic workflow (wake/recall/distill/skill dispatch)
- [SETUP.md](SETUP.md) — machine-readable adaptation intent for the CLI's AI

## License

[MIT](LICENSE) © sillogic
