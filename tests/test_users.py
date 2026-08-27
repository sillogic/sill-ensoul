"""SIL-8 multi-tenant: user table + tenant KB-root isolation tests.

Covers:
1. users.py lifecycle      — create/list/revoke/enable/reset; token stored only
                             as sha256 hash (never plaintext); verify_token;
                             revoked users are rejected immediately.
2. okf.tenant-aware root   — request_identity() contextvar flips kb_root() to
                             base/tenants/<id>; outside a request it is the
                             base root (stdio/CLI behavior unchanged).
3. http seams              — _identity_for_token: owner token (SIL-7) still
                             maps to "owner"; user tokens map to user_id;
                             revoked -> None. _kb_root_for_identity returns
                             the tenant root for users, base for owner.
4. HTTP tenant isolation   — real uvicorn + official MCP client: a user token
                             writes to ITS OWN tenant tree, invisible to the
                             base root (skipped if uvicorn is missing).

Usage:  python -m tests.test_users
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from ensoul import http as http_server  # noqa: E402
from ensoul import okf, users  # noqa: E402

OWNER_TOKEN = "owner-token-0123456789abcdef"


def _fresh_env(tmp_kb: str):
    os.environ["ENSOUL_KB"] = tmp_kb
    os.environ["ENSOUL_MCP_TOKEN"] = OWNER_TOKEN


def _clear_env():
    os.environ.pop("ENSOUL_KB", None)
    os.environ.pop("ENSOUL_MCP_TOKEN", None)


# ---- 1. users.py lifecycle ----

def test_user_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_kb:
        _fresh_env(tmp_kb)
        try:
            r = users.create_user("小王", note="同事", user_id="xiaowang")
            uid, token = r["user_id"], r["token"]
            assert uid and token and uid == "xiaowang", r

            # plaintext token must NOT be in the table file
            raw = users.users_path().read_text(encoding="utf-8")
            assert token not in raw
            assert "sha256:" in raw

            # verify round-trips; unknown / wrong token -> None
            assert users.verify_token(token) == uid
            assert users.verify_token("wrong") is None

            # list exposes no hash, only a prefix
            row = users.list_users()[0]
            assert row["user_id"] == uid and row["enabled"] is True
            assert "token_hash" not in row

            # revoke -> dead immediately; enable -> back
            users.set_enabled(uid, False)
            assert users.verify_token(token) is None
            users.set_enabled(uid, True)
            assert users.verify_token(token) == uid

            # reset rotates: old dead, new works
            new = users.reset_token(uid)["token"]
            assert new != token
            assert users.verify_token(token) is None
            assert users.verify_token(new) == uid

            # duplicate / invalid ids rejected
            try:
                users.create_user("小王", user_id=uid)
                raise AssertionError("duplicate user_id must fail")
            except ValueError:
                pass
            try:
                users.create_user("x", user_id="a/b")
                raise AssertionError("invalid user_id must fail")
            except ValueError:
                pass

            # verify_token reads through a fresh table load each call, so a
            # revoke by another process is honored (no in-process cache)
            users.set_enabled(uid, False)
            assert users.verify_token(new) is None
            print("[1] user lifecycle OK (hash-only storage, revoke, reset)")
        finally:
            _clear_env()


def test_user_id_fallback():
    with tempfile.TemporaryDirectory() as tmp_kb:
        _fresh_env(tmp_kb)
        try:
            # name that can't slugify -> random u-xxxxxx id, still valid
            r = users.create_user("!!!")
            assert r["user_id"].startswith("u-")
            r2 = users.create_user("张三")
            assert r2["user_id"].startswith("u-"), r2
            print("[1b] user_id fallback OK")
        finally:
            _clear_env()


# ---- 2. okf tenant-aware root ----

def test_tenant_kb_root():
    with tempfile.TemporaryDirectory() as tmp_kb:
        _fresh_env(tmp_kb)
        try:
            base = okf.base_kb_root()
            assert okf.kb_root() == base, "no identity -> base root (unchanged)"

            r = users.create_user("租户A")
            uid = r["user_id"]
            with okf.request_identity(uid):
                assert okf.kb_root() == base / "tenants" / uid
                assert okf.current_identity() == uid
                # agent writes land in the tenant tree
                okf.create_agent("ensoul-dev", name="Tenant Agent")
                assert (base / "tenants" / uid / "agents" / "ensoul-dev").exists()
            # after the request the root is base again; base sees nothing
            assert okf.kb_root() == base
            assert not (base / "agents" / "ensoul-dev").exists()
            print("[2] tenant KB root OK (contextvar-scoped, isolation holds)")
        finally:
            _clear_env()


# ---- 3. http seams ----

def test_http_seams():
    with tempfile.TemporaryDirectory() as tmp_kb:
        _fresh_env(tmp_kb)
        try:
            # owner token (SIL-7) still maps to owner -> base root
            assert http_server._identity_for_token(OWNER_TOKEN, OWNER_TOKEN) == "owner"
            assert http_server._kb_root_for_identity("owner") == okf.base_kb_root()

            # user token -> user_id -> tenant root
            r = users.create_user("租户B")
            uid = r["user_id"]
            assert http_server._identity_for_token(r["token"], OWNER_TOKEN) == uid
            assert http_server._kb_root_for_identity(uid) == \
                okf.base_kb_root() / "tenants" / uid

            # revoked user -> None
            users.set_enabled(uid, False)
            assert http_server._identity_for_token(r["token"], OWNER_TOKEN) is None

            # garbage -> None
            assert http_server._identity_for_token("", OWNER_TOKEN) is None
            assert http_server._identity_for_token("garbage", OWNER_TOKEN) is None
            print("[3] http seams OK (owner back-compat, tenant mapping, revoke)")
        finally:
            _clear_env()


# ---- 4. HTTP tenant isolation e2e ----

try:
    import uvicorn  # noqa: F401
    _HAVE_UVICORN = True
except ImportError:
    _HAVE_UVICORN = False


async def test_tenant_e2e():
    if not _HAVE_UVICORN:
        print("[4] uvicorn not installed — skipped "
              "(pip install 'sill-ensoul[http]' to enable)")
        return
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from ensoul import fts

    with tempfile.TemporaryDirectory() as tmp_kb:
        _fresh_env(tmp_kb)
        try:
            tenant = users.create_user("租户C")
            tenant_id, tenant_token = tenant["user_id"], tenant["token"]
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

                async def call(tool, **args):
                    async with streamablehttp_client(
                            url,
                            headers={"Authorization": f"Bearer {tenant_token}"}) \
                            as (read, write, _g):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            r = await session.call_tool(tool, args)
                            return json.loads(r.content[0].text)

                await call("create_agent", agent_id="ensoul-dev",
                           name="Tenant Agent",
                           persona="# 身份\n租户C的ensoul-dev。")
                await call("wiki_write_concept",
                           agent_id="ensoul-dev",
                           concept_id="projects/secret",
                           type="Project", title="租户C机密",
                           body="只有租户C能看到这条记忆。")

                base = okf.base_kb_root()
                # tenant tree holds the data...
                tenant_agents = base / "tenants" / tenant_id / "agents"
                assert (tenant_agents / "ensoul-dev" / "projects" / "secret.md").exists()
                # ...and the base root is untouched (isolation)
                assert not (base / "agents" / "ensoul-dev").exists()
                # owner token can see the tenant's data too (admin)
                assert okf.list_agents() == []
                with okf.request_identity(tenant_id):
                    assert [a["agent_id"] for a in okf.list_agents()] == ["ensoul-dev"]
                print("[4] HTTP tenant isolation OK (user writes own tenant tree)")
            finally:
                server.should_exit = True
                await task
                fts.reset_cache_for_tests()
        finally:
            _clear_env()


if __name__ == "__main__":
    test_user_lifecycle()
    test_user_id_fallback()
    test_tenant_kb_root()
    test_http_seams()
    asyncio.run(test_tenant_e2e())
    print("\nUSERS LIVE GOOD. SIL-8 Phase 1 (user table + tenant isolation) holds.")
