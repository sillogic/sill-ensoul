"""Agent-to-agent communication: a shared mailbox + boundary contracts.

Messages are appended to shared/mailbox.jsonl (one JSON object per line), so
the communication log is transparent and greppable. Resolved boundaries are
written as markdown contracts under shared/contracts/ (docs/DESIGN.md 5.3-5.4).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .registry import shared_root


def _mailbox_file() -> Path:
    return shared_root() / "mailbox.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def comm_send(from_agent: str, to_agent: str, message: str,
              subject: str = "") -> dict:
    """Leave a message from one agent to another in the shared mailbox."""
    entry = {"from": from_agent, "to": to_agent, "subject": subject,
              "message": message, "timestamp": _now()}
    f = _mailbox_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def comm_read(agent_id: str, unread_only: bool = False,
              mark_read: bool = False) -> list[dict]:
    """Read messages addressed to agent_id."""
    f = _mailbox_file()
    if not f.exists():
        return []
    msgs = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("to") == agent_id:
            if unread_only and obj.get("_read"):
                continue
            msgs.append(obj)
    if mark_read:
        _mark_messages_read(agent_id)
    return msgs


def _mark_messages_read(agent_id: str) -> None:
    """Rewrite mailbox, tagging delivered messages to agent_id as read."""
    f = _mailbox_file()
    if not f.exists():
        return
    lines = f.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("to") == agent_id:
            obj["_read"] = True
        out.append(json.dumps(obj, ensure_ascii=False))
    f.write_text("\n".join(out) + "\n", encoding="utf-8")


def boundary_record(agent_a: str, agent_b: str, contract_body: str,
                    summary: str = "") -> dict:
    """Write a resolved boundary agreement as a markdown contract file.
    Both agents should then registry_update() their owns/intends to match."""
    contracts_dir = shared_root() / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    pair = "-".join(sorted([agent_a, agent_b]))
    fname = f"boundary-{pair}.md"
    f = contracts_dir / fname
    header = "---\n"
    header += "type: Boundary Contract\n"
    header += f"title: 边界协议 {agent_a} ↔ {agent_b}\n"
    header += f"description: {summary or ('边界协商结果')}\n"
    header += f"agents: [{agent_a}, {agent_b}]\n"
    header += f"timestamp: {_now()}\n"
    header += "---\n\n"
    body = f"# {agent_a} ↔ {agent_b} 边界协议\n\n{contract_body.strip()}\n"
    f.write_text(header + body, encoding="utf-8")
    return {"contract_file": fname, "agents": [agent_a, agent_b]}
def comm_clear() -> int:
    """Wipe the mailbox (used by tests). Returns count of removed messages."""
    f = _mailbox_file()
    if not f.exists():
        return 0
    n = sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
    f.write_text("", encoding="utf-8")
    return n
