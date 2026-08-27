"""sill-ensoul HTTP MCP server: the same 8 OKF tools over Streamable HTTP,
protected by Bearer-token auth (SIL-7).

Purpose: deploy the knowledge base as a REMOTE MCP server (cloud VPS / tailnet)
so multiple machines share ONE memory. Authentication is the connection layer
— "who may connect". Every request must carry `Authorization: Bearer <token>`;
the server refuses to start without a configured token (fail-closed: a remote
server without auth is exactly what SIL-7 eliminates).

Transport is an adapter, not a rewrite (D1): the 8 tool callables stay defined
once in server.py as pure pass-through to okf.py; this module re-registers them
on its OWN FastMCP instance (server.mcp's session manager is single-use, so the
stdio instance can't serve HTTP). The data layer is untouched — the KB root is
still resolved by okf.kb_root() (ENSOUL_KB / platform default).

Multi-tenant seam (SIL-8, Phase 1 BUILT): a valid token maps to an identity
(`_identity_for_token` — the owner token from env, or a lookup in the user
 table at `users.json`), and an identity maps to a KB root
(`_kb_root_for_identity` — owner => base root, a tenant user =>
 `base/tenants/<user_id>/`). The middleware injects the identity into
 okf.request_identity() for the duration of the request, so the 8 tools
 resolve their KB root per-request via okf.kb_root() — the auth protocol and
 the tool layer stay unchanged. See docs/ROADMAP.md D11/D12.

Run (console script):  sill-ensoul-http [--host H] [--port P]
or:                     python -m ensoul.http [--host H] [--port P]

Requires the optional `http` extra (uvicorn):  pip install "sill-ensoul[http]"
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings

from . import okf
from . import server
from . import users

# Tool callables live in server.py (single source of truth — D1). The stdio
# FastMCP instance (server.mcp) cannot serve HTTP twice: its session manager
# is single-use (.run() can only be called once per instance). So this module
# builds its OWN FastMCP instance per create_app() call and re-registers the
# same 8 callables — keep this tuple in sync with server.py's tool set.
_TOOL_FUNCS = (
    server.list_agents,
    server.create_agent,
    server.delete_agent,
    server.agent_index,
    server.wiki_search,
    server.wiki_read,
    server.wiki_write_concept,
    server.wiki_append_log,
)


def _build_mcp() -> FastMCP:
    mcp = FastMCP("sill-ensoul-mcp")
    for fn in _TOOL_FUNCS:
        mcp.tool()(fn)
    # FastMCP enables DNS-rebinding protection by default but only whitelists
    # localhost Hosts — a remote client connecting via IP/hostname would get 421
    # out of the box. Here the Bearer gate (below) already runs before routing
    # on EVERY request, so a rebinding attacker gains nothing without the token:
    # the token is the auth boundary. Keep transport security on the deployment
    # layer (Tailscale / firewall) per docs/ROADMAP.md D11.
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )
    return mcp


def _identity_for_token(token: str, valid_token: str) -> str | None:
    """Map a presented Bearer token to an identity, or None if invalid.

    Two layers, both fail-closed:
    1. owner token (env ENSOUL_MCP_TOKEN, SIL-7): "owner" — sees the BASE KB
       root, exactly the pre-SIL-8 single-tenant behavior (backward compatible).
    2. tenant users (users.json, SIL-8 Phase 1): any enabled user's token maps
       to their user_id; revoked users get None immediately (revocation is
       effective on the next request — no restart needed).
    """
    if token and valid_token and hmac.compare_digest(token, valid_token):
        return "owner"
    return users.verify_token(token)


def _kb_root_for_identity(identity: str) -> Path:
    """KB root for an authenticated identity (SIL-8 Phase 1).

    owner => base root (single-tenant); a tenant user_id =>
    `base/tenants/<user_id>/` — fully isolated per user. This is the documented
    seam; the actual per-request resolution happens through okf.kb_root() via
    the identity injected by the middleware below.
    """
    return okf.tenant_root(identity)


class _BearerAuthMiddleware:
    """Pure-ASGI middleware: every HTTP request must present the valid token.

    Runs before FastMCP's router, so unauthenticated requests never reach MCP
    endpoints (unknown paths 401 too — no endpoint leakage). The resolved
    identity is stashed in scope for downstream use (SIL-8 seam).
    """

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        auth = next(
            (v for k, v in scope.get("headers", []) if k.lower() == b"authorization"),
            b"",
        )
        presented = auth[len(b"Bearer "):].decode("utf-8", "replace") \
            if auth.startswith(b"Bearer ") else ""
        identity = _identity_for_token(presented, self.token)
        if identity is None:
            body = json.dumps(
                {"error": "unauthorized: a valid Bearer token is required"}
            ).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b'Bearer realm="sill-ensoul"'),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return
        scope["ensoul_identity"] = identity
        # Inject the identity for the duration of this request: okf.kb_root()
        # resolves per-request, so the 8 tools read/write the right tenant root
        # with ZERO changes to the tool layer (D12). anyio's to_thread copies
        # the current context, so sync tool handlers see it too.
        with okf.request_identity(identity):
            await self.app(scope, receive, send)


def create_app(token: str | None = None):
    """Build the authenticated Streamable-HTTP ASGI app.

    `token` defaults to env ENSOUL_MCP_TOKEN. Refuses to start (RuntimeError)
    when no token is configured — fail-closed, so an unauthenticated remote
    server can never come up by accident.
    """
    token = token if token is not None else os.environ.get("ENSOUL_MCP_TOKEN", "")
    if not token:
        raise RuntimeError(
            "ENSOUL_MCP_TOKEN is not set — refusing to start an unauthenticated "
            "HTTP server. Generate a token first, e.g. `openssl rand -hex 32`."
        )
    return _BearerAuthMiddleware(_build_mcp().streamable_http_app(), token)


def main() -> None:
    """Entry point for the `sill-ensoul-http` console script (pyproject.toml)."""
    parser = argparse.ArgumentParser(
        prog="sill-ensoul-http",
        description="Run the sill-ensoul MCP server over Streamable HTTP with "
                    "Bearer-token auth (SIL-7).",
    )
    parser.add_argument(
        "--host", default=os.environ.get("ENSOUL_MCP_HOST", "0.0.0.0"),
        help="bind address (default: 0.0.0.0; env ENSOUL_MCP_HOST overrides)")
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("ENSOUL_MCP_PORT", "8930")),
        help="bind port (default: 8930; env ENSOUL_MCP_PORT overrides)")
    args = parser.parse_args()

    app = create_app()  # raises if ENSOUL_MCP_TOKEN is missing (fail-closed)
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit(
            "the HTTP server needs the optional 'http' extra — "
            "install with:  pip install \"sill-ensoul[http]\""
        ) from e
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
