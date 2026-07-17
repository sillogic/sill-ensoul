# Sova

English | [简体中文](README.md)

A multi-agent system with long-term memory (OKF Wiki), decoupled from CLI and model vendors. Each sova (Agent) owns an OKF knowledge bundle; a lightweight MCP server exposes these bundles as tools, letting you read/write sova's memory directly from CLIs like zcode / Claude Code / Codex.

> **Sova** — cross-project long-term memory for CLI agents. Each woken agent is also a **sova** (plural: sovas).

**Core differentiator**: Memory is **role-scoped** — a sova's experience accumulates across all projects, unlike existing CLIs that only have project-level memory. Lessons the algo-engineer sova learned in project A carry over to project B.

> For the full README (in Chinese), see [README.md](README.md). Design background: [docs/DESIGN.md](docs/DESIGN.md). Progress: [docs/ROADMAP.md](docs/ROADMAP.md). Memory format follows Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (OKF v0.1).

---

## Quick Start

```bash
pip install git+https://github.com/<your-username>/sova.git
sova-init              # Initialize KB + create default agent `alter-ego`
```

`sova-init` only does CLI-agnostic init (build KB + alter-ego). **CLI adaptation** is done by your CLI's own AI — in the CLI, say `set up sova from <repo>/SETUP.md`, and the CLI reads `SETUP.md` and registers the MCP server + installs the shell itself. See [SETUP.md](SETUP.md).

> **First use**: after wiring up your CLI, open a new session and say **`wake up alter-ego`** — this is your digital twin (the default agent), with empty memory. Accumulate experience with it first; split off a specialized agent via `create_agent` when a domain has enough. Saying "wake up" / "digital twin" / "唤醒分身" also works — the shell recognizes them.

> **Want your own agent name?** Just tell the CLI "create an agent called nova" — it calls `create_agent(agent_id="nova", ...)`. Then say **`wake up nova`** to use it. The agent_id is the name you choose; no shell edit, no CLI restart needed. alter-ego is just the out-of-the-box default, not the only option.

### Share with a teammate (any MCP-capable CLI)

```bash
pip install git+https://github.com/<you>/sova.git
sova-init                          # Initialize KB + create alter-ego
```

Then let their CLI adapt itself — in the CLI, say:

```
set up sova from <repo>/SETUP.md
```

The CLI's AI reads `SETUP.md` (the adaptation intent) and registers the MCP server + installs the shell itself. sova never hardcodes any CLI's config format — when CLIs change, the AI adapts, sova doesn't. After setup, restart the CLI and say "wake up alter-ego" to start.

After installing, open a new Claude Code session — a default agent `alter-ego` (your digital twin) is ready. Say "wake up alter-ego" to start accumulating experience.

> **Privacy**: `knowledge/` is in `.gitignore` — your private memory never enters the repo. Teammates get an empty KB; each person's sova memory is independent.

---

## Architecture

```
  zcode / Claude Code / Codex   (inference runs in each CLI's model vendor, not locked)
           |  load persona + wiki slice (thin shell: AGENTS.md / CLAUDE.md)
        MCP server (sova/, memory engine, 8 tools)
           |  read/write
  knowledge/agents/<id>/  ← one OKF bundle per agent (md files, global KB)
```

Three-layer separation (design decisions D1/D2, see docs/ROADMAP.md):

- **Engine** (`sova/`) — CLI-agnostic, handles data/tools only, no inference.
- **Shell** (`AGENTS.md` / `CLAUDE.md`) — one per CLI, defines "when to wake/search/distill", references the shared [WORKFLOW.md](WORKFLOW.md).
- **Memory** (`knowledge/agents/<id>/`) — OKF markdown files, git-able, diff-able, human-readable (view in Obsidian).

---

## 8 Tools

| Tool | Purpose |
|---|---|
| `list_agents` | List all sovas |
| `create_agent` | Create a sova (dir + persona + index + log template) |
| `delete_agent` | Delete a sova (irreversible, confirm first) |
| `agent_index` | Wake/switch sova (persona + knowledge map) |
| `wiki_search` | Full-text search a sova's experience (FTS5 + BM25) |
| `wiki_read` | Read a concept's details |
| `wiki_write_concept` | Distill new experience (type required) |
| `wiki_append_log` | Log a change |

> Multi-agent collaboration needs no dedicated tools: `wiki_*` tools take an `agent_id` param pointing to **any** agent. Any agent can read/write other agents' memories directly — the orchestrator model (see docs/ROADMAP.md D6).

---

## Key Features

- **Role-scoped memory**: sova experience accumulates across projects, not project-level.
- **OKF file-based**: memory is markdown, git-able/diff-able, editable in Obsidian. md is always source of truth.
- **FTS5 Chinese search**: SQLite FTS5 + CJK char segmentation + BM25, zero dependencies.
- **Cross-CLI/cross-model**: MCP is the interface, inference in each CLI's vendor, not locked.
- **Reminder-style semi-auto distillation**: agent proactively judges timing + distills, user confirms before writing (quality gate).

---

## Status

- ✅ Core loop works: wake → recall → cite → distill → cross-project retention.
- ✅ Installable: `pip install` one-liner, `sova-init` self-boots CLI setup.
- ✅ Cross-CLI verified: zcode + Claude Code both adapted.
- 🟡 Not done: sleeptime fully-auto distillation.
- See [docs/ROADMAP.md](docs/ROADMAP.md).
