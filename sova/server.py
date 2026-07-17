"""sova MCP server: exposes an OKF knowledge base as agent tools.

Run as a stdio MCP server:  python -m sova.server
Register it from Codex / Claude Code / OpenCode (see README.md).
"""
from __future__ import annotations

import json
from datetime import date, datetime

from mcp.server.fastmcp import FastMCP

from . import okf
from . import registry as reg
from . import comm

mcp = FastMCP("sova")


def _json_default(o):
    """YAML frontmatter may contain datetime/date objects (e.g. an unquoted
    `timestamp: 2026-03-10T08:00:00Z` parses to datetime); json.dumps can't
    serialize them by default. ISO-format keeps them lossless and round-trips."""
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    raise TypeError(f"{type(o).__name__} is not JSON serializable")


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)


# ---- Phase 1: per-agent OKF wiki ----

@mcp.tool()
def list_agents() -> str:
    """List every agent that owns an OKF knowledge bundle."""
    return _dump(okf.list_agents())


@mcp.tool()
def create_agent(agent_id: str, name: str = "", persona: str = "") -> str:
    """Create a new agent bundle (directory + AGENT.md persona + index.md +
    log.md). Use when starting a new role that doesn't exist yet.
    `name`: display name (defaults to agent_id). `persona`: free-text identity
    and strengths for the AGENT.md body; omit for a fill-in template.
    Fails if the agent already exists — don't clobber."""
    try:
        return _dump(okf.create_agent(agent_id, name or None, persona or None))
    except (ValueError, FileExistsError) as e:
        return _dump({"error": str(e)})


@mcp.tool()
def delete_agent(agent_id: str) -> str:
    """Delete an agent's entire bundle (all concepts + persona + log).
    IRREVERSIBLE — confirm with the user before calling. Refuses paths that
    escape the agents dir. Use when an agent is retired or created by mistake."""
    try:
        return _dump(okf.delete_agent(agent_id))
    except (ValueError, FileNotFoundError) as e:
        return _dump({"error": str(e)})


@mcp.tool()
def agent_index(agent_id: str) -> str:
    """Open an agent's wiki: persona preview, index.md text, and all concepts.
    Call this when waking an agent in a new project, before working.
    Switch agents by calling this with a different agent_id."""
    return _dump(okf.agent_index(agent_id))


@mcp.tool()
def wiki_search(agent_id: str, query: str, limit: int = 5) -> str:
    """Full-text search within one agent's wiki."""
    return _dump(okf.search(agent_id, query, limit))


@mcp.tool()
def wiki_read(agent_id: str, concept_id: str) -> str:
    """Read one concept (frontmatter + body). concept_id uses '/' (e.g. 'projects/x')."""
    try:
        return _dump(okf.read_concept(agent_id, concept_id))
    except FileNotFoundError as e:
        return _dump({"error": str(e)})


@mcp.tool()
def wiki_write_concept(agent_id: str, concept_id: str, type: str,
                       title: str = "", description: str = "", body: str = "",
                       tags: list[str] | None = None, extra_json: str = "") -> str:
    """Create or update a concept file in an agent's wiki. 'type' is required (OKF).
    extra_json: optional JSON object string for custom frontmatter fields."""
    extra = json.loads(extra_json) if extra_json else None
    try:
        return _dump(okf.write_concept(
            agent_id, concept_id, type, title or None, description or None,
            body, tags, extra))
    except ValueError as e:
        return _dump({"error": str(e)})


@mcp.tool()
def wiki_append_log(agent_id: str, action: str, detail: str) -> str:
    """Append one update entry to the agent's log.md (today's date group)."""
    return _dump(okf.append_log(agent_id, action, detail))


# ---- Phase 2: registry / boundary / agent-to-agent comms ----

@mcp.tool()
def registry_list() -> str:
    """List all agents and their ownership declarations (owns / intends / depends_on).
    This is the shared blackboard. Call it to see who owns what before assigning work."""
    return _dump(reg.registry_list())


@mcp.tool()
def registry_update(agent_id: str, owns: list[str] | None = None,
                    intends: list[str] | None = None,
                    depends_on: list[str] | None = None,
                    name: str = "") -> str:
    """Create or update an agent's ownership declaration. Pass a list to change a
    field; omit (null) to leave it. Agents declare intends when planning to touch
    an area they don't own yet, so boundary_scan can catch overlaps early."""
    return _dump(reg.registry_update(agent_id, owns, intends, depends_on,
                                     name or None))


@mcp.tool()
def boundary_scan() -> str:
    """Scan all ownership declarations for resource overlaps between agents.
    Returns conflicts: ownership_conflict / boundary_dispute / intentional_overlap.
    The orchestrator (or you) should trigger a negotiation when conflicts appear."""
    return _dump(reg.boundary_scan())


@mcp.tool()
def comm_send(from_agent: str, to_agent: str, message: str,
              subject: str = "") -> str:
    """Send a message from one agent to another via the shared mailbox.
    Used for boundary negotiation, questions, and task handoffs."""
    return _dump(comm.comm_send(from_agent, to_agent, message, subject))


@mcp.tool()
def comm_read(agent_id: str, unread_only: bool = False) -> str:
    """Read messages addressed to an agent. Call this when an agent needs to
    hear what others are saying to it (e.g. a boundary negotiation message)."""
    return _dump(comm.comm_read(agent_id, unread_only))


@mcp.tool()
def boundary_record(agent_a: str, agent_b: str, contract_body: str,
                    summary: str = "") -> str:
    """Record a resolved boundary agreement as a markdown contract file under
    shared/contracts/. After recording, both agents should registry_update their
    owns/intends to match the agreed boundary."""
    return _dump(comm.boundary_record(agent_a, agent_b, contract_body, summary))


def main() -> None:
    """Entry point for the `sova-mcp` console script (see pyproject.toml).
    Runs the stdio MCP server. Works from any cwd once the package is installed."""
    mcp.run()


if __name__ == "__main__":
    main()
