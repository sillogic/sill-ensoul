"""OKF (Open Knowledge Format) bundle read / write / search logic.

A knowledge base is a directory tree of markdown files, one OKF bundle per
agent under knowledge/agents/<agent_id>/. Each concept is one .md file with a
YAML frontmatter block; 'type' is the only required field (OKF SPEC 3.1/9).
Reserved filenames: index.md (directory map) and log.md (update history).

This module is pure logic and has no MCP dependency, so it can be unit-tested
on its own (see tests/test_smoke.py).

Storage model:
- OKF markdown files are the source of truth.
- A per-agent SQLite FTS5 index at <agent_dir>/.fts/index.db caches metadata
  and accelerates search/agent_index. It can be deleted and rebuilt at any time.
"""
from __future__ import annotations

import contextvars
import os
import re
import socket
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml

RESERVED = {"index.md", "log.md"}  # OKF SPEC 3.1 - never concept documents.
# OKF SPEC only reserves index.md/log.md. We additionally exclude AGENT.md: it
# is the agent's persona/identity file, not a retrievable knowledge concept.
# Keeping it out of search hits + concept listings prevents persona text (e.g.
# "推荐系统" written in the identity) from crowding out real experience entries
# (H7). Persona is still surfaced via agent_index() -> persona_preview.
EXTRA_NON_CONCEPT = {"agent.md"}
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _default_kb_root() -> Path:
    """Platform-appropriate default for the knowledge base, so the server is not
    bound to the repo dir (H4/H9). Precedence:
      ENSOUL_KB  ->  platform default:
        win32   ->  %LOCALAPPDATA%/ensoul/knowledge
        darwin  ->  ~/Library/Application Support/ensoul/knowledge
        else    ->  XDG_DATA_HOME/ensoul/knowledge  (default ~/.local/share/ensoul/knowledge)
      ->  ~/.ensoul/knowledge   (last-resort, works everywhere)."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "ensoul" / "knowledge"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ensoul" / "knowledge"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            return Path(xdg) / "ensoul" / "knowledge"
        return Path.home() / ".local" / "share" / "ensoul" / "knowledge"
    return Path.home() / ".ensoul" / "knowledge"


def base_kb_root() -> Path:
    """The BASE knowledge root (SIL-8: the single-tenant root). ENSOUL_KB
    overrides; else a global default (NOT the repo dir) so the package is
    location-independent once installed.

    Multi-tenant (SIL-8): the base root is the owner's root and the parent of
    every tenant root (`base/tenants/<user_id>/`). The user table lives here
    too (`base/users.json`) — intentionally OUTSIDE any tenant root, so no
    tenant can read or write it."""
    env = os.environ.get("ENSOUL_KB")
    if env:
        return Path(env).expanduser().resolve()
    return _default_kb_root()


# Per-request identity, injected by the HTTP auth middleware (ensoul/http.py)
# for the duration of one request. None outside a request => kb_root() resolves
# to the base root, so stdio (sill-ensoul-mcp), the admin CLI and tests are
# byte-for-byte unaffected. The only tool-layer change SIL-8 needs (D12).
_identity_ctx: contextvars.ContextVar[str | None] = \
    contextvars.ContextVar("ensoul_identity", default=None)

# Per-request MACHINE identity: the physical machine the CLIENT runs on,
# injected by the HTTP middleware from the `X-Machine-Id` request header. A
# shared remote KB is read/written by many machines; recording the writing
# machine lets a reader tell "which machine wrote this" apart from "which
# machine am I on" — otherwise words like "本机/this machine" inside old
# entries become ambiguous across machines. None outside HTTP => falls back to
# this host's hostname (stdio / admin CLI / tests are local by definition).
_machine_ctx: contextvars.ContextVar[str | None] = \
    contextvars.ContextVar("ensoul_machine", default=None)


def current_machine() -> str:
    """Physical machine bound to the current request, or this host's hostname.

    HTTP: the value of the client's `X-Machine-Id` header (never the server's
    own hostname — a remote client's machine is the thing we want). A remote
    client that did NOT send the header reports 'unknown'. stdio / admin CLI /
    tests run on the same machine as the KB, so the hostname is the correct
    machine there."""
    m = _machine_ctx.get()
    if m is not None:
        return m
    return socket.gethostname()


@contextmanager
def request_machine(machine: str | None):
    """Bind a machine identity for the duration of a request (HTTP middleware).
    Safe to nest; the previous value is restored on exit."""
    token = _machine_ctx.set(machine)
    try:
        yield
    finally:
        _machine_ctx.reset(token)


def current_identity() -> str | None:
    """Identity bound to the current request/thread (None outside HTTP)."""
    return _identity_ctx.get()


@contextmanager
def request_identity(identity: str | None):
    """Bind an identity for the duration of a request (HTTP auth middleware).
    Safe to nest; the previous value is restored on exit."""
    token = _identity_ctx.set(identity)
    try:
        yield
    finally:
        _identity_ctx.reset(token)


def tenant_root(identity: str | None) -> Path:
    """KB root for an identity: owner/None => base root; a tenant user_id =>
    `base/tenants/<user_id>/`. Every tenant gets its own isolated tree; two
    tenants may even own same-named agents (both `ensoul-dev`) without
    clashing, because the split happens at this root level (D12)."""
    base = base_kb_root()
    if not identity or identity == "owner":
        return base
    return base / "tenants" / identity


def kb_root() -> Path:
    """KB root for the CURRENT request identity (SIL-8 tenant-aware).
    Outside an HTTP request this equals base_kb_root() — unchanged behavior."""
    return tenant_root(_identity_ctx.get())


def _agents_dir() -> Path:
    return kb_root() / "agents"


def _agent_dir(agent_id: str) -> Path:
    return _agents_dir() / agent_id


def parse_markdown(text: str) -> tuple[dict, str]:
    """Split a concept file into (frontmatter dict, body string).

    If the file has no frontmatter, returns ({}, text). If frontmatter exists
    but is not valid YAML, raises yaml.YAMLError so the caller can surface the
    problem instead of silently working with an empty dict.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return ({}, text)
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        raise yaml.YAMLError("OKF frontmatter must be a YAML mapping")
    return (fm, m.group(2))


def serialize(frontmatter: dict, body: str) -> str:
    fm = {k: v for k, v in frontmatter.items() if v is not None}
    head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{head}\n---\n\n{body.strip()}\n"


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text to path atomically: create a temp file in the same directory,
    then os.replace() it into place. This prevents half-written files on crash.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.tmp_", suffix=".md"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


@contextmanager
def _agent_lock(agent_id: str, timeout: float = 10.0):
    """Per-agent cross-process mutex via SQLite's single-writer semantics.

    Same code runs on win/linux/mac: sqlite3 is stdlib everywhere, so there is
    no fcntl/msvcrt platform branch (ROADMAP #12 / D9). BEGIN IMMEDIATE takes
    SQLite's RESERVED lock, which is a cross-process mutex on all platforms;
    `timeout` makes contending writers wait instead of failing immediately. A
    crash inside the critical section is rolled back by SQLite and the file
    lock released by the OS, so the mutex can never go stale.

    The lock file <agent_dir>/.lock.db is DEDICATED and never os.replace'd.
    Locking the file being written would be broken: append_log/write_concept
    replace the target inode, so a second process would lock the NEW inode
    while the first still holds the OLD one — two locks, no exclusion.

    NOT reentrant: acquiring the same agent's lock from inside its own critical
    section would self-deadlock (2nd BEGIN IMMEDIATE blocks until the 10s
    timeout). No okf code path nests, and the MCP shell calls tools
    sequentially — keep it that way.
    """
    agent_dir = _agent_dir(agent_id)
    agent_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(agent_dir / ".lock.db"), timeout=timeout)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_agents() -> list[dict]:
    d = _agents_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if p.is_dir():
            out.append({"agent_id": p.name, "has_persona": (p / "AGENT.md").exists()})
    return out


def create_agent(agent_id: str, name: str | None = None,
                 persona: str | None = None) -> dict:
    """Create a new agent bundle: directory + AGENT.md (persona) + index.md +
    log.md. Fails if the agent already exists (avoid clobbering).
    `name` is the display name; `persona` is free-text identity/strengths."""
    if not agent_id or "/" in agent_id or ".." in agent_id:
        raise ValueError("invalid agent_id (must be a simple directory name)")
    d = _agent_dir(agent_id)
    if d.exists():
        raise FileExistsError(f"agent '{agent_id}' already exists")
    d.mkdir(parents=True, exist_ok=False)

    # AGENT.md — persona (type: Profile). The body is user-provided identity,
    # or a template they fill in later.
    display = name or agent_id
    persona_body = persona or (
        f"# 身份\n\n我是 {display}。强项：\n\n- （待补充）\n\n# 工作方式\n\n"
        "进新项目时，先读自己的 index.md 和最相关的经验条目，带着历史项目的"
        "教训开工。任务中遇到非平凡的坑、关键决策、可复用模式或纠正了旧认知时，"
        "自动提炼并写入 wiki，写完后告诉你。原文不进记忆。")
    agent_md = serialize(
        {"type": "Profile", "title": display,
         "description": f"{display} Agent"},
        persona_body)
    _atomic_write_text(d / "AGENT.md", agent_md)

    # index.md — knowledge map (OKF reserved file, no frontmatter)
    _atomic_write_text(
        d / "index.md",
        f"# {display} · 知识地图\n\n"
        "# 核心文件\n* [Playbook](playbook.md) - SOP 和检查清单（最高频复用）\n\n"
        "# 通用经验\n* [expertise](expertise/) - 跨项目沉淀的方法论\n\n"
        "# 项目经验\n* [projects](projects/) - 每个历史项目的提炼后经验\n")

    # log.md — update history (OKF reserved file)
    _atomic_write_text(d / "log.md", "# Directory Update Log\n")

    return {"agent_id": agent_id, "name": display,
            "created": [str(p.name) for p in sorted(d.iterdir())]}


def delete_agent(agent_id: str) -> dict:
    """Delete an agent's entire bundle. Irreversible — caller must confirm.
    Refuses to delete paths that escape the agents dir (safety)."""
    if not agent_id or ".." in agent_id:
        raise ValueError("invalid agent_id")
    d = _agent_dir(agent_id)
    if not d.exists():
        raise FileNotFoundError(f"agent '{agent_id}' not found")
    # Safety: only delete if it's actually under the agents dir.
    agents_root = _agents_dir().resolve()
    if not d.resolve().is_relative_to(agents_root):
        raise ValueError("refusing to delete: path escapes agents dir")
    import shutil
    shutil.rmtree(d)
    return {"agent_id": agent_id, "deleted": True}


def _read_persona(agent_id: str) -> dict | None:
    f = _agent_dir(agent_id) / "AGENT.md"
    if not f.exists():
        return None
    fm, body = parse_markdown(f.read_text(encoding="utf-8"))
    return {"frontmatter": fm, "preview": body[:600]}


def _iter_concepts(agent_id: str):
    base = _agent_dir(agent_id)
    if not base.exists():
        return
    for p in sorted(base.rglob("*.md")):
        # RESERVED (index.md/log.md) are OKF-internal; EXTRA_NON_CONCEPT
        # (agent.md) is persona. Neither is a retrievable knowledge concept.
        if p.name.lower() in RESERVED or p.name.lower() in EXTRA_NON_CONCEPT:
            continue
        yield p


def _concept_id_from_path(base: Path, path: Path) -> str:
    return path.relative_to(base).with_suffix("").as_posix()


def read_concept(agent_id: str, concept_id: str) -> dict:
    """concept_id uses '/' separators, no .md suffix (e.g. 'projects/recsys')."""
    if ".." in concept_id.split("/"):
        raise ValueError("invalid concept id")
    f = _agent_dir(agent_id) / f"{concept_id}.md"
    if not f.exists():
        raise FileNotFoundError(f"{agent_id}/{concept_id}")
    fm, body = parse_markdown(f.read_text(encoding="utf-8"))
    return {"agent_id": agent_id, "concept_id": concept_id,
            "frontmatter": fm, "body": body}


def _sync_agent_index(agent_id: str) -> None:
    """Scan the agent's OKF files and update the SQLite index incrementally.

    Only reads files that are new or changed (by mtime + size). Files with
    malformed frontmatter are skipped with a warning. Serialized by
    _agent_lock: two processes syncing the same index.db concurrently would
    otherwise hit SQLite's default busy_timeout=0 and raise
    "database is locked" (ROADMAP #12).
    """
    from . import fts

    base = _agent_dir(agent_id)
    if not base.exists():
        return

    with _agent_lock(agent_id):
        concepts: list[dict] = []
        for p in _iter_concepts(agent_id):
            rel = _concept_id_from_path(base, p)
            stat = p.stat()
            # Try the lightweight cache first; only read+parse if changed.
            cached = fts.get_meta(base, rel)
            if (cached and
                abs(cached.get("mtime", 0) - stat.st_mtime) < 0.001 and
                cached.get("size", -1) == stat.st_size):
                concepts.append({
                    "concept_id": rel,
                    "title": cached["title"],
                    "description": cached["description"],
                    "tags": cached["tags"],
                    "type": cached["type"],
                    "body": cached.get("body_preview", ""),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                })
                continue

            try:
                text = p.read_text(encoding="utf-8")
                fm, body = parse_markdown(text)
            except yaml.YAMLError as e:
                import warnings
                warnings.warn(f"skipping malformed OKF frontmatter in {p}: {e}")
                continue
            tags = fm.get("tags") or []
            concepts.append({
                "concept_id": rel,
                "title": str(fm.get("title", "")),
                "description": str(fm.get("description", "")),
                "tags": " ".join(str(t) for t in tags),
                "body": body,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "type": str(fm.get("type", "")),
            })

        fts.sync_index(base, concepts)


def search(agent_id: str, query: str, limit: int = 5) -> list[dict]:
    """Full-text search over an agent's wiki, BM25-ranked via SQLite FTS5 (H1).

    The index at <agent_dir>/.fts/index.db is synced incrementally before each
    query, so it is always consistent with the OKF bundle. Only new or changed
    concept files are read from disk. Persona (AGENT.md) and OKF reserved files
    are excluded (H7).
    """
    base = _agent_dir(agent_id)
    if not base.exists():
        return []

    _sync_agent_index(agent_id)

    from . import fts
    hits = fts.search(base, query, limit=limit)
    out = []
    for h in hits:
        cid = h["concept_id"]
        out.append({
            "agent_id": agent_id,
            "concept_id": cid,
            "title": h.get("title") or cid,
            "type": h.get("type", ""),
            "score": round(h["score"], 4),
            "snippet": _snippet(h.get("body_preview", ""), query.split()),
        })
    return out


def write_concept(agent_id: str, concept_id: str, type: str,
                  title: str | None = None, description: str | None = None,
                  body: str = "", tags: list[str] | None = None,
                  extra: dict | None = None) -> dict:
    """Create or update a concept file. 'type' is required by OKF.
    Writes atomically so a crash mid-write never leaves a half-written file."""
    if not type:
        raise ValueError("OKF requires a 'type' field")
    if ".." in concept_id.split("/"):
        raise ValueError("invalid concept id")
    name = concept_id.rsplit("/", 1)[-1] + ".md"
    if name.lower() in RESERVED:
        raise ValueError(f"{name} is a reserved OKF filename")
    if name.lower() in EXTRA_NON_CONCEPT:
        raise ValueError(f"{name} is the persona file; write concepts, not persona, via this tool")

    fm = {
        "type": type, "title": title, "description": description,
        "tags": tags or [],
        "timestamp": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if extra:
        fm.update(extra)
    # The writing machine is auto-stamped and authoritative (after extra, so a
    # caller can never forge/override it). Readers of a shared remote KB use
    # this to tell "which machine wrote this" from "which machine am I on".
    fm["machine"] = current_machine()

    f = _agent_dir(agent_id) / f"{concept_id}.md"
    # Lock serializes concurrent writers to the same concept (last-writer-wins
    # deterministically); the atomic write below still guards against torn
    # files on crash. Two layers, two jobs (ROADMAP #12/D9).
    with _agent_lock(agent_id):
        _atomic_write_text(f, serialize(fm, body))
        return read_concept(agent_id, concept_id)


def append_log(agent_id: str, action: str, detail: str) -> dict:
    """Append one entry to the agent's log.md under today's ISO date group.
    The read-modify-write runs under _agent_lock so concurrent callers cannot
    lose an entry (ROADMAP #12); the atomic write still guards torn files on
    crash. Two layers, two jobs."""
    f = _agent_dir(agent_id) / "log.md"
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    entry = f"* **{action}**: {detail} (machine: {current_machine()})"
    with _agent_lock(agent_id):
        text = f.read_text(encoding="utf-8") if f.exists() else "# Directory Update Log\n"
        if "# Directory Update Log" not in text:
            text = "# Directory Update Log\n\n" + text
        marker = f"## {today}"
        if marker in text:
            text = text.replace(marker, f"{marker}\n{entry}", 1)
        else:
            text = text.replace("# Directory Update Log\n",
                                f"# Directory Update Log\n\n{marker}\n{entry}\n", 1)
        _atomic_write_text(f, text)
    return {"agent_id": agent_id, "date": today, "entry": entry}


def agent_index(agent_id: str) -> dict:
    """Progressive-disclosure entry: persona preview + index.md + concept list.

    Raises FileNotFoundError if the agent bundle does not exist, so callers
    can distinguish "empty agent" from "missing agent" (bug fix).
    """
    base = _agent_dir(agent_id)
    if not base.exists():
        raise FileNotFoundError(f"agent '{agent_id}' not found")
    persona = _read_persona(agent_id)
    idx_file = _agent_dir(agent_id) / "index.md"
    index_text = idx_file.read_text(encoding="utf-8") if idx_file.exists() else ""

    _sync_agent_index(agent_id)

    from . import fts
    concepts = [
        {"concept_id": c["concept_id"],
         "title": c["title"] or c["concept_id"],
         "type": c["type"]}
        for c in fts.list_meta(base)
    ]

    return {"agent_id": agent_id,
            "persona_preview": persona["preview"] if persona else None,
            "index_md": index_text, "concepts": concepts}


def rebuild_index(agent_id: str) -> dict:
    """Force a full rebuild of the SQLite index for an agent.

    Reads every concept file and re-indexes it. Use when the index is suspected
    to be out of sync (e.g. after manual bulk edits outside the MCP tools).
    """
    base = _agent_dir(agent_id)
    if not base.exists():
        raise FileNotFoundError(f"agent '{agent_id}' not found")

    from . import fts
    fts.clear_index(base)

    concepts: list[dict] = []
    for p in _iter_concepts(agent_id):
        rel = _concept_id_from_path(base, p)
        stat = p.stat()
        try:
            text = p.read_text(encoding="utf-8")
            fm, body = parse_markdown(text)
        except yaml.YAMLError:
            continue
        tags = fm.get("tags") or []
        concepts.append({
            "concept_id": rel,
            "title": str(fm.get("title", "")),
            "description": str(fm.get("description", "")),
            "tags": " ".join(str(t) for t in tags),
            "body": body,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "type": str(fm.get("type", "")),
        })

    fts.sync_index(base, concepts)
    return {"agent_id": agent_id, "indexed_concepts": len(concepts)}


def _snippet(body: str, words: list[str], width: int = 160) -> str:
    low = body.lower()
    pos = min((low.find(w) for w in words if low.find(w) >= 0), default=0)
    start = max(0, pos - 40)
    s = body[start:start + width].replace("\n", " ").strip()
    return ("..." + s + "...") if start > 0 else (s + "...")
