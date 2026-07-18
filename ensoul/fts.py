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
- Freshness: indexed by concept_id (relative path). search() does an incremental
  sync (upsert/delete to match current files) before querying, so the index is
  always consistent with the bundle without a separate rebuild step.

Pure logic, no MCP dependency — unit-testable on its own (like okf.py).
"""
from __future__ import annotations

import sqlite3
import re
import threading
from pathlib import Path

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

# unicode61 treats a contiguous CJK run as ONE token (e.g. "双塔模型" is a
# single token), so substring search like "双塔" never matches. To make CJK
# retrievable at sub-word granularity with zero dependencies (no jieba), we
# space-separate every Han character before indexing. Then "双塔模型" is stored
# as tokens [双, 塔, 模, 型], and the phrase "双塔" matches the adjacent pair.
# ASCII/Latin runs are left intact so English word matching still works.
_CJK = re.compile(r"[一-鿿]")


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

_META_SCHEMA = """CREATE TABLE IF NOT EXISTS meta(
    concept_id TEXT PRIMARY KEY,
    mtime REAL
)"""

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
                    description: str, tags: str, body: str, mtime: float) -> None:
    # Segment CJK per-char at index time (see _segment_for_index) so sub-word
    # CJK search works without a segmenter.
    conn.execute("DELETE FROM concepts WHERE concept_id = ?", (concept_id,))
    conn.execute("DELETE FROM meta WHERE concept_id = ?", (concept_id,))
    conn.execute(
        "INSERT INTO concepts(concept_id, title, description, tags, body) "
        "VALUES (?,?,?,?,?)",
        (concept_id, _segment_for_index(title or ""),
         _segment_for_index(description or ""),
         _segment_for_index(tags or ""),
         _segment_for_index(body or "")))
    conn.execute("INSERT OR REPLACE INTO meta(concept_id, mtime) VALUES (?,?)",
                 (concept_id, mtime))


def sync_index(agent_dir: Path, concepts: list[dict]) -> None:
    """Bring the index in sync with the given concepts.

    `concepts` is a list of {concept_id, title, description, tags, body, mtime}.
    Upserts changed docs and removes docs no longer present. Called by
    okf.search() right before querying, so callers never manage freshness.
    """
    conn = _connect(agent_dir)
    seen = set()
    for c in concepts:
        cid = c["concept_id"]
        seen.add(cid)
        row = conn.execute(
            "SELECT mtime FROM meta WHERE concept_id=?", (cid,)).fetchone()
        if row and abs(row["mtime"] - c["mtime"]) < 0.001:
            continue  # unchanged
        _index_document(conn, cid, c.get("title", ""), c.get("description", ""),
                        c.get("tags", ""), c.get("body", ""), c["mtime"])
    # delete dropped concepts
    rows = conn.execute("SELECT concept_id FROM meta").fetchall()
    for r in rows:
        if r["concept_id"] not in seen:
            conn.execute("DELETE FROM concepts WHERE concept_id = ?",
                         (r["concept_id"],))
            conn.execute("DELETE FROM meta WHERE concept_id = ?",
                         (r["concept_id"],))
    conn.commit()


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
    sql = ("SELECT concept_id, title, bm25(concepts) AS rank "
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
        out.append({
            "concept_id": r["concept_id"],
            "title": r["title"],
            "score": -r["rank"] if r["rank"] is not None else 0.0,
        })
    return out
