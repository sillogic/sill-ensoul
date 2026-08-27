"""SIL-8 multi-tenant user table (option A: admin CLI).

One user = one Bearer token = one isolated KB root (`knowledge/tenants/<id>/`).
This module owns the mapping table itself — `knowledge/users.json` at the BASE
KB root (NOT inside any tenant root, so no tenant can see the table). Plaintext
tokens are never stored: only a `sha256:` hex digest, so a server file leak is
not a credential leak, and tokens can be revoked/reset any time.

Pure logic, no MCP dependency (same discipline as okf.py): unit-testable on its
own, and usable by both the admin CLI (sill-ensoul-admin) and the HTTP auth
seam (ensoul/http.py `_identity_for_token`).

Table schema (users.json):
{
  "version": 1,
  "users": {
    "<user_id>": {
      "name": "display name",
      "token_hash": "sha256:<hexdigest>",
      "enabled": true,
      "created_at": "<ISO 8601>",
      "note": ""
    }
  }
}

Concurrency: the table is admin-single-writer (one operator on the server).
Read-modify-write with atomic replace is sufficient; the per-agent D9 lock is
for multi-process agent writes and is intentionally not reused here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import okf

_USER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_TABLE_VERSION = 1


def users_path(base: Path | None = None) -> Path:
    """Location of the user table: `<base>/users.json` at the BASE KB root."""
    return (base or okf.base_kb_root()) / "users.json"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent),
                                    prefix=f".{path.name}.tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_users(base: Path | None = None) -> dict:
    """Load the table. Missing/corrupt file => empty table (never raises)."""
    p = users_path(base)
    if not p.exists():
        return {"version": _TABLE_VERSION, "users": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": _TABLE_VERSION, "users": {}}
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, dict):
        return {"version": _TABLE_VERSION, "users": {}}
    return {"version": _TABLE_VERSION, "users": users}


def save_users(table: dict, base: Path | None = None) -> None:
    table["version"] = _TABLE_VERSION
    _atomic_write(users_path(base), json.dumps(
        table, ensure_ascii=False, indent=2) + "\n")


def _gen_token() -> str:
    """Fresh 64-hex bearer token. Shown to the admin ONCE, then only hashed."""
    return secrets.token_hex(32)


def _hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_user_id(name: str) -> str:
    """Readable id from the display name, else a random fallback."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    if slug and _USER_ID_RE.match(slug):
        return slug[:64]
    return "u-" + secrets.token_hex(3)


def _validate_user_id(user_id: str) -> None:
    if not _USER_ID_RE.match(user_id or ""):
        raise ValueError(
            "invalid user_id: use 1-64 chars of [A-Za-z0-9_-], starting "
            "with a letter or digit")


def create_user(name: str, note: str = "", user_id: str | None = None,
                base: Path | None = None) -> dict:
    """Create a user; returns the plaintext token (shown once)."""
    if not name or not name.strip():
        raise ValueError("user name is required")
    user_id = user_id or _new_user_id(name)
    _validate_user_id(user_id)

    table = load_users(base)
    if user_id in table["users"]:
        raise ValueError(f"user '{user_id}' already exists")
    token = _gen_token()
    table["users"][user_id] = {
        "name": name.strip(),
        "token_hash": _hash_token(token),
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note.strip(),
    }
    save_users(table, base)
    return {"user_id": user_id, "token": token}


def get_user(user_id: str, base: Path | None = None) -> dict | None:
    return load_users(base)["users"].get(user_id)


def list_users(base: Path | None = None) -> list[dict]:
    """All users, token-hash never exposed — only a short prefix for
    human cross-checking (same convention as showing a key fingerprint)."""
    table = load_users(base)
    out = []
    for uid, u in sorted(table["users"].items()):
        prefix = u.get("token_hash", "")[:18]
        out.append({
            "user_id": uid,
            "name": u.get("name", ""),
            "enabled": bool(u.get("enabled", False)),
            "created_at": u.get("created_at", ""),
            "token_hash_prefix": prefix,
            "note": u.get("note", ""),
        })
    return out


def _require_user(user_id: str, base: Path | None = None) -> dict:
    table = load_users(base)
    if user_id not in table["users"]:
        raise KeyError(f"no such user: '{user_id}'")
    return table


def set_enabled(user_id: str, enabled: bool, base: Path | None = None) -> dict:
    """Revoke (enabled=False, token dead immediately) or re-enable."""
    table = _require_user(user_id, base)
    table["users"][user_id]["enabled"] = bool(enabled)
    save_users(table, base)
    return {"user_id": user_id, "enabled": bool(enabled)}


def reset_token(user_id: str, base: Path | None = None) -> dict:
    """Rotate a user's token (old one is dead immediately); new token shown once."""
    table = _require_user(user_id, base)
    token = _gen_token()
    table["users"][user_id]["token_hash"] = _hash_token(token)
    table["users"][user_id]["enabled"] = True
    save_users(table, base)
    return {"user_id": user_id, "token": token}


def verify_token(token: str, base: Path | None = None) -> str | None:
    """Map a presented Bearer token to a user_id, or None if unknown/revoked."""
    if not token:
        return None
    hashed = _hash_token(token)
    for uid, u in load_users(base)["users"].items():
        if u.get("token_hash") == hashed:
            return uid if u.get("enabled", False) else None
    return None
