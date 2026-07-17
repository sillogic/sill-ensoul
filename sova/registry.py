"""Agent ownership registry + boundary-conflict scanner.

shared/registry.json is the 'blackboard': each agent declares what it owns and
what it intends to touch. boundary_scan() compares every pair and surfaces
overlaps so the orchestrator can trigger a negotiation before two agents step
on each other (DESIGN.md 5.1-5.2).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .okf import kb_root


def shared_root() -> Path:
    """shared/ directory. Override with SOVA_SHARED, else sibling of kb_root."""
    env = os.environ.get("SOVA_SHARED")
    if env:
        return Path(env).expanduser().resolve()
    return kb_root().parent / "shared"


def _registry_file() -> Path:
    return shared_root() / "registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load() -> dict:
    f = _registry_file()
    if not f.exists():
        return {"agents": []}
    return json.loads(f.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    f = _registry_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def registry_list() -> list[dict]:
    return _load().get("agents", [])


def registry_get(agent_id: str) -> dict | None:
    for a in registry_list():
        if a["agent_id"] == agent_id:
            return a
    return None


def registry_update(agent_id: str, owns: list[str] | None = None,
                    intends: list[str] | None = None,
                    depends_on: list[str] | None = None,
                    name: str | None = None) -> dict:
    """Create or update an agent's ownership declaration. Pass a list to change
    a field; pass None (omit) to leave it untouched."""
    data = _load()
    agents = data.setdefault("agents", [])
    entry = None
    for a in agents:
        if a["agent_id"] == agent_id:
            entry = a
            break
    if entry is None:
        entry = {"agent_id": agent_id, "name": name or agent_id,
                 "owns": [], "intends": [], "depends_on": []}
        agents.append(entry)
    if name is not None:
        entry["name"] = name
    if owns is not None:
        entry["owns"] = sorted(set(owns))
    if intends is not None:
        entry["intends"] = sorted(set(intends))
    if depends_on is not None:
        entry["depends_on"] = sorted(set(depends_on))
    entry["updated_at"] = _now()
    _save(data)
    return entry


def _pairs(items: list) -> list[tuple]:
    """All unordered index pairs (i<j)."""
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            out.append((items[i], items[j]))
    return out


def boundary_scan() -> dict:
    """Compare every pair of agents and surface resource overlaps.
    Conflict types:
      ownership_conflict  — both claim to own the same resource.
      boundary_dispute    — one intends to touch something another owns.
      intentional_overlap — both intend the same area, nobody owns it yet.
    """
    agents = registry_list()
    conflicts = []
    for a, b in _pairs(agents):
        a_owns, a_intends = set(a.get("owns", [])), set(a.get("intends", []))
        b_owns, b_intends = set(b.get("owns", [])), set(b.get("intends", []))

        for res in sorted(a_owns & b_owns):
            conflicts.append({"type": "ownership_conflict",
                              "agents": [a["agent_id"], b["agent_id"]],
                              "resource": res})
        for res in sorted(a_owns & b_intends):
            conflicts.append({"type": "boundary_dispute",
                              "agents": [a["agent_id"], b["agent_id"]],
                              "owner": a["agent_id"],
                              "intender": b["agent_id"], "resource": res})
        for res in sorted(a_intends & b_intends):
            if res not in a_owns and res not in b_owns:
                conflicts.append({"type": "intentional_overlap",
                                  "agents": [a["agent_id"], b["agent_id"]],
                                  "resource": res})
    return {"conflicts": conflicts,
            "total": len(conflicts),
            "clean": len(conflicts) == 0}
