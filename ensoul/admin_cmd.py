"""`sill-ensoul-admin` console script: SIL-8 multi-tenant user management
(option A — zero-UI admin CLI on the server, chosen by the owner).

Create/revoke/enable/reset users on the server's user table (`users.json` at
the BASE KB root). `user create` / `user reset` print the plaintext bearer
token exactly once and write a ready-to-forward **access card** markdown —
credentials (real URL + token) plus a routing table to the per-scenario
setup files (SIL-8 doc-split decision 2026-08-27: one file per scenario
instead of one card covering everything — local MCP → SETUP.md, remote MCP →
cli-remote.md, Multica → multica.md). The recipient pastes the card
into their CLI / Multica conversation.

Run on the server (or wherever the KB lives):
    sill-ensoul-admin user create --name 小王 --url http://<host>:<port>/mcp
    sill-ensoul-admin user list
    sill-ensoul-admin user revoke u-xiaowang
    sill-ensoul-admin user reset  u-xiaowang --url http://<host>:<port>/mcp

Security: tokens are shown once, stored only as sha256 hashes (users.py);
the card file contains a live token — never commit it or send it over public
channels. Revocation is effective on the next HTTP request (no restart).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import users

_URL_DEFAULT_PLACEHOLDER = "http://<服务器公网IP>:<端口>/mcp"
_CARD_FILENAME = "sill-ensoul-card-{user_id}.md"

# ---- Access card template (SIL-8 doc-split: credentials + per-scenario routing) ----
# Placeholders __URL__ / __TOKEN__ / __USER_ID__ / __USER_NAME__ are replaced
# at generation time; the OUTPUT file carries real secrets and must never be
# committed (the CLI prints a warning; the file lives wherever --out says).
# The card intentionally does NOT inline setup steps — it routes to the three
# scenario files (one file per scenario, SIL-8 decision), so steps stay single-
# sourced in the repo instead of being maintained twice.

_CARD_TEMPLATE = """# 接入卡：sill-ensoul（用户：__USER_NAME__）

> ⚠️ **本文件包含你的私有 Bearer token —— 相当于一把钥匙。**
> - 不要提交进任何 git 仓库，不要走公开渠道（群聊 / 明文邮件）转发。
> - 接入完成、CLI 配置并验证通过后，建议删除本文件。
> - 怀疑 token 泄露时，联系管理员执行 `sill-ensoul-admin user reset __USER_ID__` 吊销换新。

## 你的接入凭据

- MCP 端点：`__URL__`
- 鉴权头：`Authorization: Bearer __TOKEN__`（每个请求都带）

## 按场景选一份文件（仓库内，各管一种场景）

| 你的场景 | 用哪个文件 | 说明 |
|---|---|---|
| 本地 MCP（本机 stdio） | `SETUP.md` | 首次安装，不需要 token |
| 远程 MCP（本卡场景） | `deploy/cli-setup/cli-remote.md` | 用上面的真实值替换占位符 |
| Multica 平台 agent | `deploy/cli-setup/multica.md` | **前提：先配好 MCP**，再绑**已有**分身（不新建） |

你是本机 CLI / Multica agent。请按你所属场景读对应文件：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 收尾（所有场景）

- **必须完全退出本 CLI 再重新打开**，新会话才会用新配置（配置启动时加载，不热更新）。
- 重启后在会话里调 `agent_index` / `wiki_search` 能通 = 接入成功。
- 不要把 token / IP / 端口写进任何会被 git 提交的文件。
"""



def _resolve_base(kb: str | None) -> Path | None:
    """--kb flag wins; else None => users.py uses ENSOUL_KB / platform default."""
    return Path(kb).expanduser().resolve() if kb else None


def _card_path(user_id: str, out: str | None) -> Path:
    d = Path(out or ".").expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d / _CARD_FILENAME.format(user_id=user_id)


def _card_md(url: str, token: str, user_id: str, user_name: str) -> str:
    return _CARD_TEMPLATE \
        .replace("__URL__", url) \
        .replace("__TOKEN__", token) \
        .replace("__USER_ID__", user_id) \
        .replace("__USER_NAME__", user_name)


def _write_card(user_id: str, name: str, token: str, url: str,
                out: str | None) -> Path:
    path = _card_path(user_id, out)
    path.write_text(_card_md(url, token, user_id, name), encoding="utf-8")
    return path


def _print_token_warning(path: Path) -> None:
    print()
    print(f"  Access card written to: {path}")
    print("  ⚠️  The card contains a live bearer token (a key to this user's KB).")
    print("     Forward it privately; never commit it to git or post it publicly.")


def cmd_create(args: argparse.Namespace) -> int:
    base = _resolve_base(args.kb)
    try:
        r = users.create_user(args.name, note=args.note or "", user_id=args.id,
                              base=base)
    except ValueError as e:
        print(f"error: {e}")
        return 1
    url = args.url or os.environ.get("ENSOUL_MCP_URL") or _URL_DEFAULT_PLACEHOLDER
    path = _write_card(r["user_id"], args.name, r["token"], url, args.out)
    print(f"Created user:  {r['user_id']}")
    print(f"Name:          {args.name}")
    print(f"Token (shown once — keep it safe):")
    print()
    print(f"  {r['token']}")
    print()
    print(f"MCP endpoint (in card): {url}")
    _print_token_warning(path)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    base = _resolve_base(args.kb)
    rows = users.list_users(base)
    if not rows:
        print("No users yet. Create one with:")
        print("  sill-ensoul-admin user create --name <姓名> --url http://<host>:<port>/mcp")
        return 0
    print(f"{'USER_ID':<24} {'ENABLED':<8} {'CREATED_AT (UTC)':<24} NAME")
    print("-" * 80)
    for u in rows:
        print(f"{u['user_id']:<24} {str(u['enabled']):<8} "
              f"{u['created_at']:<24} {u['name']}")
    print()
    print("token_hash_prefix: " + ", ".join(
        f"{u['user_id']}={u['token_hash_prefix']}" for u in rows))
    return 0


def cmd_set_enabled(args: argparse.Namespace, enabled: bool) -> int:
    base = _resolve_base(args.kb)
    try:
        users.set_enabled(args.user_id, enabled, base=base)
    except KeyError as e:
        print(f"error: {e}")
        return 1
    action = "enabled" if enabled else "revoked (token is dead now)"
    print(f"{action}: {args.user_id}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    base = _resolve_base(args.kb)
    try:
        r = users.reset_token(args.user_id, base=base)
    except KeyError as e:
        print(f"error: {e}")
        return 1
    name = (users.get_user(args.user_id, base) or {}).get("name", args.user_id)
    url = args.url or os.environ.get("ENSOUL_MCP_URL") or _URL_DEFAULT_PLACEHOLDER
    path = _write_card(args.user_id, name, r["token"], url, args.out)
    print(f"Token rotated for: {args.user_id} (old token is dead)")
    print(f"New token (shown once — keep it safe):")
    print()
    print(f"  {r['token']}")
    _print_token_warning(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sill-ensoul-admin",
        description="SIL-8 multi-tenant user management for the sill-ensoul "
                    "remote MCP server (option A: admin CLI).",
    )
    parser.add_argument(
        "--kb", default=None,
        help="base KB root (default: ENSOUL_KB env or platform default)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_user = sub.add_parser("user", help="user management")
    u = p_user.add_subparsers(dest="action", required=True)

    p_create = u.add_parser("create", help="create a user; token shown once + access card")
    p_create.add_argument("--name", required=True, help="display name (e.g. 小王)")
    p_create.add_argument("--note", default="", help="optional note (e.g. 公司/用途)")
    p_create.add_argument("--id", default=None, help="user_id (default: slug of name)")
    p_create.add_argument("--url", default=None,
                          help="public MCP endpoint for the card, e.g. "
                               "http://1.2.3.4:8930/mcp (env ENSOUL_MCP_URL, "
                               "or a placeholder if omitted)")
    p_create.add_argument("--out", default=None,
                          help="dir to write the access card (default: current dir)")
    p_create.set_defaults(func=cmd_create)

    p_list = u.add_parser("list", help="list users (token hashes never shown)")
    p_list.set_defaults(func=cmd_list)

    p_revoke = u.add_parser("revoke", help="revoke a user (token dead immediately)")
    p_revoke.add_argument("user_id")
    p_revoke.set_defaults(func=lambda a: cmd_set_enabled(a, False))

    p_enable = u.add_parser("enable", help="re-enable a revoked user")
    p_enable.add_argument("user_id")
    p_enable.set_defaults(func=lambda a: cmd_set_enabled(a, True))

    p_reset = u.add_parser("reset", help="rotate a user's token + regenerate card")
    p_reset.add_argument("user_id")
    p_reset.add_argument("--url", default=None,
                         help="public MCP endpoint for the card (see create)")
    p_reset.add_argument("--out", default=None,
                         help="dir to write the access card (default: current dir)")
    p_reset.set_defaults(func=cmd_reset)

    return parser


def main() -> int:
    # Windows 控制台默认 GBK，无法编码 ⚠️ 等非 ASCII（本 CLI 大量输出中文）。
    # 强制 UTF-8；管道/重定向场景同样适用，失败则忽略（非 TTY 或已不可配）。
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
