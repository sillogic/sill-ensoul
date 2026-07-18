"""SQLite FTS5 full-text index for an OKF bundle (H1).

Replaces okf.search()'s str.count() scoring with a proper inverted index.
Design:
- One index.db per agent, at <agent_dir>/.fts/index.db (inside the bundle,
  git-trackable, not a concept dir so it never shows up as knowledge).
- Tokenizer: unicode61 with remove_diacritics 2. For CJK this is "per-character"
  tokenization (each Han char is its own token) — zero-dependency, good enough
  for mixed zh/en retrieval (DESIGN: "先 FTS5 省事").
- Ranking: bm25(). Lower (more negative) = more relevant; we negate so higher
  score = better, matching the old str.count() contract.
- Freshness: indexed by concept_id (relative path). sync_index() does an
  incremental sync (upsert/delete to match current files), so the index is
  always consistent with the bundle without a separate rebuild step.
- Metadata cache: the `meta` table also caches title/description/tags/type and
  a body preview. This lets okf.search() and agent_index() serve results without
  reading every .md file on every query.

Pure logic, no MCP dependency — unit-testable on its own (like okf.py).
"""
from __future__ import annotations

import sqlite3
import re
import threading
from pathlib import Path

# Schema version for the index.db file. Increment when the FTS or meta schema
# changes. _connect() checks PRAGMA user_version and rebuilds tables when stale,
# so upgrades don't leave old indexes with missing columns.
_SCHEMA_VERSION = 1

# FTS5 virtual table. unicode61: splits on non-alphanumeric; for CJK each char
# becomes a token (no word segmenter needed). remove_diacritics=2 normalizes
# accents. We index title/desc/tags/body as separate columns so bm25 can weight
# them (title hit counts more than body hit).
_FTS_SCHEMA = """CREATE VIRTUAL TABLE IF NOT EXISTS concepts USING fts5(
    concept_id UNINDEXED,
    title,
    description,
    tags,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
)"""

# Metadata cache: one row per concept. Caches lightweight fields so search and
# agent_index can avoid reading every .md file on every query. body_preview is
# the first 500 chars of the body, used for snippets.
_META_SCHEMA = """CREATE TABLE IF NOT EXISTS meta(
    concept_id TEXT PRIMARY KEY,
    mtime REAL,
    size INTEGER,
    title TEXT,
    description TEXT,
    tags TEXT,
    type TEXT,
    body_preview TEXT
)"""

# unicode61 treats a contiguous CJK run as ONE token (e.g. "双塔模型" is a
# single token), so substring search like "双塔" never matches. To make CJK
# retrievable at sub-word granularity with zero dependencies (no jieba), we
# space-separate every Han character before indexing. Then "双塔模型" is stored
# as tokens [双, 塔, 模, 型], and the phrase "双塔" matches the adjacent pair.
# ASCII/Latin runs are left intact so English word matching still works.
_CJK = re.compile(r"[一-鿿]")

_PREVIEW_LEN = 500


def _segment_for_index(text: str) -> str:
    """Space-separate CJK chars (per-char tokens) while keeping Latin whole.
    Applied to indexed text only, never stored back to the .md files."""
    if not text:
        return ""
    out = []
    for tok in re.findall(r"[一-鿿]+|[^一-鿿]+", text):
        if _CJK.match(tok[0]):
            out.append(" ".join(tok))  # CJK run -> per-char tokens
        else:
            out.append(tok)
    return "".join(out)


# Per-process connection cache keyed by agent_dir. sqlite3 connections are not
# shareable across threads by default; we keep one per (agent_dir, thread).
_conn_cache: dict[tuple[str, int], sqlite3.Connection] = {}
_cache_lock = threading.Lock()


class FTSQueryError(Exception):
    """Raised when a query cannot be executed by FTS5 (e.g. malformed MATCH)."""


def _db_path(agent_dir: Path) -> Path:
    return agent_dir / ".fts" / "index.db"


def _connect(agent_dir: Path) -> sqlite3.Connection:
    key = (str(agent_dir), threading.get_ident())
    with _cache_lock:
        conn = _conn_cache.get(key)
        if conn is not None:
            return conn
    dbp = _db_path(agent_dir)
    dbp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbp))
    conn.row_factory = sqlite3.Row
    conn.executescript(_FTS_SCHEMA)
    conn.executescript(_META_SCHEMA)
    conn.commit()

    # Schema migration: if the on-disk schema version is older than the code's,
    # drop and recreate tables. The index will be rebuilt from .md files on the
    # next sync. This avoids "no such column" errors after upgrading.
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != _SCHEMA_VERSION:
        conn.execute("DROP TABLE IF EXISTS meta")
        conn.execute("DROP TABLE IF EXISTS concepts")
        conn.executescript(_FTS_SCHEMA)
        conn.executescript(_META_SCHEMA)
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        conn.commit()

    with _cache_lock:
        _conn_cache[key] = conn
    return conn


def reset_cache_for_tests() -> None:
    """Close + forget all cached connections (test isolation)."""
    with _cache_lock:
        for conn in _conn_cache.values():
            try:
                conn.close()
            except Exception:
                pass
        _conn_cache.clear()


def _index_document(conn: sqlite3.Connection, concept_id: str, title: str,
                    description: str, tags: str, body: str, mtime: float,
                    size: int, type: str) -> None:
    """Upsert both the FTS row and the metadata cache for one concept."""
    preview = (body or "")[:_PREVIEW_LEN]
    # Segment CJK per-char at index time so sub-word CJK search works.
    conn.execute("DELETE FROM concepts WHERE concept_id = ?", (concept_id,))
    conn.execute(
        "INSERT INTO concepts(concept_id, title, description, tags, body) "
        "VALUES (?,?,?,?,?)",
        (concept_id, _segment_for_index(title or ""),
         _segment_for_index(description or ""),
         _segment_for_index(tags or ""),
         _segment_for_index(body or "")))
    conn.execute(
        "INSERT OR REPLACE INTO meta "
        "(concept_id, mtime, size, title, description, tags, type, body_preview) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (concept_id, mtime, size, title or "", description or "",
         tags or "", type or "", preview))


def sync_index(agent_dir: Path, concepts: list[dict]) -> None:
    """Bring the index in sync with the given concepts.

    `concepts` is a list of dicts with keys:
      concept_id, title, description, tags, body, type, mtime, size.
    Upserts changed docs and removes docs no longer present.
    """
    conn = _connect(agent_dir)
    seen = set()
    for c in concepts:
        cid = c["concept_id"]
        seen.add(cid)
        row = conn.execute(
            "SELECT mtime, size FROM meta WHERE concept_id=?", (cid,)).fetchone()
        if (row and
            abs(row["mtime"] - c["mtime"]) < 0.001 and
            row["size"] == c.get("size", -1)):
            continue  # unchanged
        _index_document(
            conn, cid, c.get("title", ""), c.get("description", ""),
            c.get("tags", ""), c.get("body", ""), c["mtime"],
            c.get("size", 0), c.get("type", ""))
    # delete dropped concepts
    rows = conn.execute("SELECT concept_id FROM meta").fetchall()
    for r in rows:
        if r["concept_id"] not in seen:
            conn.execute("DELETE FROM concepts WHERE concept_id = ?",
                         (r["concept_id"],))
            conn.execute("DELETE FROM meta WHERE concept_id = ?",
                         (r["concept_id"],))
    conn.commit()


def clear_index(agent_dir: Path) -> None:
    """Drop all indexed data for an agent. Used by --rebuild-index."""
    conn = _connect(agent_dir)
    conn.execute("DELETE FROM concepts")
    conn.execute("DELETE FROM meta")
    conn.commit()


def get_meta(agent_dir: Path, concept_id: str) -> dict | None:
    """Return cached metadata for a single concept, or None if not indexed."""
    conn = _connect(agent_dir)
    row = conn.execute(
        "SELECT concept_id, title, description, tags, type, body_preview "
        "FROM meta WHERE concept_id=?", (concept_id,)).fetchone()
    if not row:
        return None
    return {
        "concept_id": row["concept_id"],
        "title": row["title"],
        "description": row["description"],
        "tags": row["tags"],
        "type": row["type"],
        "body_preview": row["body_preview"],
    }


def list_meta(agent_dir: Path) -> list[dict]:
    """Return cached metadata for all indexed concepts."""
    conn = _connect(agent_dir)
    rows = conn.execute(
        "SELECT concept_id, title, description, tags, type, body_preview "
        "FROM meta ORDER BY concept_id").fetchall()
    return [
        {
            "concept_id": r["concept_id"],
            "title": r["title"],
            "description": r["description"],
            "tags": r["tags"],
            "type": r["type"],
            "body_preview": r["body_preview"],
        }
        for r in rows
    ]


def _phrase_terms(query: str) -> list[str]:
    """Build FTS5 phrase-prefix terms, applying the SAME CJK per-char
    segmentation used at index time (see _segment_for_index). So query "双塔"
    becomes the phrase '"双 塔"'*', matching the adjacent index tokens 双,塔.
    Latin tokens stay whole with prefix matching ('rank'* -> 'ranking')."""
    query = query.replace('"', "").replace("*", "")
    terms = []
    for tok in query.strip().split():
        seg = _segment_for_index(tok).strip()
        if seg:
            # collapse internal whitespace into a phrase of per-char tokens
            phrase = " ".join(seg.split())
            terms.append(f'"{phrase}"*')
    return terms


def _run(conn: sqlite3.Connection, match_expr: str, limit: int) -> list[sqlite3.Row]:
    sql = ("SELECT concept_id, bm25(concepts) AS rank "
           "FROM concepts WHERE concepts MATCH ? ORDER BY rank LIMIT ?")
    try:
        return conn.execute(sql, (match_expr, limit)).fetchall()
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        # Common benign case: pure punctuation or otherwise unparseable query.
        if "malformed" in msg or "syntax" in msg:
            raise FTSQueryError(str(e)) from e
        raise


def search(agent_dir: Path, query: str, limit: int = 5) -> list[dict]:
    """BM25-ranked FTS5 search. Each whitespace token becomes a phrase-prefix
    term (CJK segmented per-char to match index time). Multi-token queries OR
    the phrases. Higher score = more relevant (bm25 negated).

    Returns an empty list for malformed queries instead of crashing."""
    terms = _phrase_terms(query)
    if not terms:
        return []
    conn = _connect(agent_dir)
    out = []
    try:
        rows = _run(conn, " OR ".join(terms), limit)
    except FTSQueryError:
        return []
    for r in rows:
        meta = get_meta(agent_dir, r["concept_id"])
        out.append({
            "concept_id": r["concept_id"],
            "title": meta["title"] if meta else r["concept_id"],
            "type": meta["type"] if meta else "",
            "score": -r["rank"] if r["rank"] is not None else 0.0,
            "body_preview": meta["body_preview"] if meta else "",
        })
    return out
