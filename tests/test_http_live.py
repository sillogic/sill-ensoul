"""HTTP transport + Bearer-token auth tests (SIL-7).

Proves ensoul/http.py works standalone, in test_mcp_live's self-contained style:
temp KB, no dependence on repo/prestored agents.

Three layers:
1. fail-closed  — create_app() refuses to start without ENSOUL_MCP_TOKEN.
2. auth gate    — protocol-level 401s via in-process ASGI (no port): missing /
   wrong token on POST/GET are rejected; the right token gets a valid
   JSON-RPC initialize response.
3. e2e          — real uvicorn server on a random port + the official MCP
   streamable-HTTP client with the Authorization header: initialize ->
   tools/list -> full tool loop against a temp KB.

Usage:  python -m tests.test_http_live
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
from starlette.testclient import TestClient

from ensoul import http as http_server

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

TOKEN = "test-token-0123456789abcdef"
FIXTURE_AGENT = "http-live-fixture"
FIXTURE_CONCEPT = "projects/demo"
FIXTURE_BODY = "召回用双塔模型，精排 GBDT。负采样比例 1:4 时 AUC 最高。"

INIT_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "test_http_live", "version": "1.0"},
}


def test_fail_closed():
    """No token configured => refusing to start is the ONLY safe outcome."""
    saved = os.environ.pop("ENSOUL_MCP_TOKEN", None)
    try:
        try:
            http_server.create_app()
            raise AssertionError("create_app() must refuse to start without a token")
        except RuntimeError:
            pass
    finally:
        if saved is not None:
            os.environ["ENSOUL_MCP_TOKEN"] = saved


async def test_auth_gate():
    """Protocol level: unauthenticated / wrong-token requests are 401.

    Uses Starlette TestClient (runs the ASGI lifespan, which is what starts the
    FastMCP session-manager task group) — no port needed.
    """
    with tempfile.TemporaryDirectory() as tmp_kb:
        os.environ["ENSOUL_KB"] = str(tmp_kb)
        os.environ["ENSOUL_MCP_TOKEN"] = TOKEN
        try:
            app = http_server.create_app()
            with TestClient(app) as client:
                # POST without auth -> 401
                r = client.post(
                    "/mcp", json={"jsonrpc": "2.0", "id": 1,
                                  "method": "initialize", "params": INIT_PARAMS})
                assert r.status_code == 401, r.status_code
                assert "www-authenticate" in {k.lower() for k in r.headers}

                # POST with a wrong token -> 401
                r = client.post(
                    "/mcp", headers={"Authorization": "Bearer wrong-token"},
                    json={"jsonrpc": "2.0", "id": 1,
                          "method": "initialize", "params": INIT_PARAMS})
                assert r.status_code == 401, r.status_code

                # GET (SSE stream endpoint) without auth -> 401
                r = client.get("/mcp")
                assert r.status_code == 401, r.status_code

                # Unknown path without auth -> 401 (no endpoint leakage)
                r = client.get("/healthz")
                assert r.status_code == 401, r.status_code

                # Correct token -> initialize is accepted and answers JSON-RPC
                r = client.post(
                    "/mcp", headers={
                        "Authorization": f"Bearer {TOKEN}",
                        "Accept": "application/json, text/event-stream",
                    },
                    json={"jsonrpc": "2.0", "id": 1,
                          "method": "initialize", "params": INIT_PARAMS})
                assert r.status_code == 200, (r.status_code, r.text)
                # Streamable HTTP answers initialize as an SSE frame (event:
                # message / data: {...}); the e2e test below validates the full
                # protocol with the official client. Here we check the frame
                # carries the JSON-RPC result and a session id was issued.
                data = "".join(
                    line[6:] for line in r.text.splitlines()
                    if line.startswith("data:"))
                body = json.loads(data)
                assert body.get("jsonrpc") == "2.0", body
                assert body["result"]["serverInfo"]["name"] == "sill-ensoul-mcp"
                assert "mcp-session-id" in {k.lower() for k in r.headers}
                print("[auth] initialize OK with token (session id issued)")
        finally:
            os.environ.pop("ENSOUL_MCP_TOKEN", None)
            os.environ.pop("ENSOUL_KB", None)


try:
    import uvicorn
    _HAVE_UVICORN = True
except ImportError:
    _HAVE_UVICORN = False


async def test_e2e():
    """End-to-end: real uvicorn server + official MCP streamable-HTTP client."""
    if not _HAVE_UVICORN:
        print("[e2e] uvicorn not installed — skipped "
              "(pip install 'sill-ensoul[http]' to enable)")
        return
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from ensoul import fts

    with tempfile.TemporaryDirectory() as tmp_kb:
        os.environ["ENSOUL_KB"] = str(tmp_kb)
        os.environ["ENSOUL_MCP_TOKEN"] = TOKEN
        try:
            app = http_server.create_app()
            config = uvicorn.Config(app, host="127.0.0.1", port=0,
                                    log_level="warning")
            server = uvicorn.Server(config)
            task = asyncio.create_task(server.serve())
            try:
                while not server.started:
                    await asyncio.sleep(0.05)
                port = server.servers[0].sockets[0].getsockname()[1]
                url = f"http://127.0.0.1:{port}/mcp"
                print(f"[e2e] server up on {url}")

                async with streamablehttp_client(
                        url,
                        headers={
                            "Authorization": f"Bearer {TOKEN}",
                            # Machine-aware memory (SIL-9): the client reports
                            # which machine it runs on; the server stamps it
                            # into every concept's frontmatter.
                            "X-Machine-Id": "test-http-client",
                        }) \
                        as (read, write, _get_session_id):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        print("[e2e] MCP initialize OK")

                        tools = await session.list_tools()
                        names = sorted(t.name for t in tools.tools)
                        print(f"[e2e] tools/list OK -> {len(names)} tools")
                        core = {"list_agents", "agent_index", "wiki_search",
                                "wiki_read", "wiki_write_concept",
                                "wiki_append_log", "create_agent"}
                        assert core <= set(names), f"missing: {core - set(names)}"

                        async def call(tool, **args):
                            r = await session.call_tool(tool, args)
                            return json.loads(r.content[0].text)

                        await call("create_agent", agent_id=FIXTURE_AGENT,
                                   name="HTTP Live Fixture",
                                   persona="# 身份\n测试用 agent，做推荐系统。")
                        await call("wiki_write_concept",
                                   agent_id=FIXTURE_AGENT,
                                   concept_id=FIXTURE_CONCEPT,
                                   type="Project", title="推荐系统重构",
                                   body=FIXTURE_BODY, tags=["recsys"])
                        await call("wiki_append_log", agent_id=FIXTURE_AGENT,
                                   action="Creation",
                                   detail="fixture concept for test_http_live")
                        print("[e2e] fixture 已建: "
                              f"agent={FIXTURE_AGENT}, concept={FIXTURE_CONCEPT}")

                        hits = await call("wiki_search", agent_id=FIXTURE_AGENT,
                                          query="推荐系统")
                        print(f"[e2e] wiki_search OK -> {len(hits)} hit(s)")
                        assert hits, "search returned nothing"

                        c = await call("wiki_read", agent_id=FIXTURE_AGENT,
                                       concept_id=hits[0]["concept_id"])
                        assert c["frontmatter"].get("type"), "missing 'type'"
                        # X-Machine-Id header must land in frontmatter.
                        assert c["frontmatter"].get("machine") == "test-http-client", \
                            c["frontmatter"]
                        print("[e2e] machine stamping OK "
                              "(X-Machine-Id -> frontmatter.machine)")

                        # A client that sends NO X-Machine-Id must degrade to
                        # 'unknown' — never to the SERVER's own hostname.
                        async with streamablehttp_client(
                                url,
                                headers={"Authorization": f"Bearer {TOKEN}"}) \
                                as (read2, write2, _sid2):
                            async with ClientSession(read2, write2) as s2:
                                await s2.initialize()
                                r = await s2.call_tool("wiki_write_concept", {
                                    "agent_id": FIXTURE_AGENT,
                                    "concept_id": "projects/no-machine",
                                    "type": "Project",
                                    "title": "no machine header",
                                    "body": "written without X-Machine-Id",
                                })
                                c2 = json.loads(r.content[0].text)
                                assert c2["frontmatter"].get("machine") == "unknown", \
                                    c2["frontmatter"]
                        print("[e2e] missing X-Machine-Id -> 'unknown' OK")
            finally:
                server.should_exit = True
                await task
                # In-process server means the FTS SQLite connection cache in
                # THIS process holds .fts/index.db open; Windows won't delete a
                # locked file, so release the cache before the temp dir is
                # removed (test_mcp_live never needs this — its server is a
                # subprocess whose handles die with it).
                fts.reset_cache_for_tests()
        finally:
            os.environ.pop("ENSOUL_MCP_TOKEN", None)
            os.environ.pop("ENSOUL_KB", None)
    print("\nHTTP LIVE GOOD. ensoul/http.py works standalone (D11 holds).")


if __name__ == "__main__":
    test_fail_closed()
    print("[1] fail-closed OK: no token => create_app refuses to start")
    asyncio.run(test_auth_gate())
    print("[2] auth gate OK: 401 on missing/wrong token, initialize with token")
    asyncio.run(test_e2e())
