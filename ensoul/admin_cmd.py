"""`sill-ensoul-admin` console script: SIL-8 multi-tenant user management
(option A — zero-UI admin CLI on the server, chosen by the owner).

Create/revoke/enable/reset users on the server's user table (`users.json` at
the BASE KB root). `user create` / `user reset` print the plaintext bearer
token exactly once and write a ready-to-forward **access card** markdown —
the SIL-35 self-adapting pattern (A Claude Code / B Codex / C zcode / D other
CLI) with the real URL+token filled in, plus an E. Multica section (SIL-8
decision: one card, both tool-layer and platform-agent paths). The recipient
just pastes the card into their CLI.

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

# ---- Access card template (SIL-35 self-adapting sections + SIL-8 Multica) ----
# Placeholders __URL__ / __TOKEN__ / __USER_ID__ / __USER_NAME__ are replaced
# at generation time; the OUTPUT file carries real secrets and must never be
# committed (the CLI prints a warning; the file lives wherever --out says).

_CARD_TEMPLATE = """# 接入卡：sill-ensoul 远程 MCP（用户：__USER_NAME__）

> ⚠️ **本文件包含你的私有 Bearer token —— 相当于一把钥匙。**
> - 不要提交进任何 git 仓库，不要走公开渠道（群聊 / 明文邮件）转发。
> - 接入完成、CLI 配置并验证通过后，建议删除本文件。
> - 怀疑 token 泄露时，联系管理员执行 `sill-ensoul-admin user reset __USER_ID__` 吊销换新。

你是本机 CLI。请帮我完成一次 sill-ensoul 远程 MCP 接入：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 目标服务器

- MCP 端点：`__URL__`
- 鉴权头：`Authorization: Bearer __TOKEN__`（每个请求都带）

## 第一步：确认你是谁，只做对应那一节

下面 A–E 按使用场景分节。先判断你属于哪一类，**只执行对应小节的步骤，其余小节直接忽略**；各节做完后再执行最后的「收尾」。

| 你是 | 走哪节 | 方式 |
|---|---|---|
| Claude Code | **A** | streamable-http 原生 |
| Codex（desktop） | **B** | `npx mcp-remote` stdio↔HTTP 桥 |
| zcode | **C** | `npx mcp-remote` stdio↔HTTP 桥 |
| 其他任何 CLI | **D** | `npx mcp-remote` stdio↔HTTP 桥（通用） |
| Multica 平台 agent | **E** | 先按 A–D 装工具，再绑分身（见 E 节） |

> **mcp-remote 桥接公共参数（B/C/D 的 mcp-remote 命令都要带，缺了必踩坑，已实测）**：
> - `--allow-http`：mcp-remote 默认拒绝非 HTTPS 地址，裸 HTTP 端点必须显式加；
> - `--transport http-only`：默认 `http-first` 会先发一个假 initialize 探测 SSE，再开第二个真 session，与 FastMCP 的 session 管理冲突 → 后续调用全部 `400 Bad Request: Missing session ID`；`http-only` 纯 POST 直连完全兼容。
> - 客户端握手必须串行：等 initialize 响应（session id 在响应头里）再发后续请求（正规 CLI 客户端本身就是串行的）。

---

## A. Claude Code

1. 找到 sill-ensoul 的 MCP 注册：检查 `~/.claude.json` 顶层 `mcpServers`（全局层）和当前项目 `.mcp.json` 顶层 `mcpServers`（项目层）。两处都可能存在 —— 告诉我你发现了几处、分别在哪个文件、现在的注册内容。
2. 对每处现有注册先**原样备份**（写到一个不会被 git 跟踪的位置，如 `~/.sill-ensoul-mcp-config.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册改成下面这个 streamable-http 形式（server 名保持 `sill-ensoul` 不变）：

```json
{ "mcpServers": { "sill-ensoul": {
  "type": "streamable-http",
  "url": "__URL__",
  "headers": { "Authorization": "Bearer __TOKEN__" }
} } }
```

如果你的版本较老不支持 `streamable-http`，告诉我并改用 `"type": "http"`（或提示我先升级 CLI）。

4. 校验：确认改动后文件是合法 JSON、结构正确；逐处说明改了什么、旧值备份在哪。
5. 不要动本地 `sill-ensoul-mcp` 的安装（stdio 本地 server 保留；以后想切回来用备份即可）。

---

## B. Codex（desktop）

1. 打开 `~/.codex/config.toml`，找到（或新增）`[mcp_servers.sill-ensoul]` 段。
2. 若已有旧注册，先把该段**原样备份**（如 `~/.codex/sill-ensoul-mcp.backup.toml`），告诉我备份路径。
3. 把该段改成用 `mcp-remote` 桥接远程 HTTP（Windows 用 `cmd /c` 包一层，Linux/macOS 直接写）：

Windows：

```toml
[mcp_servers.sill-ensoul]
command = "cmd"
args = ["/c", "npx", "--yes", "mcp-remote", "__URL__", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer __TOKEN__"]
startup_timeout_ms = 15000
```

Linux / macOS：

```toml
[mcp_servers.sill-ensoul]
command = "npx"
args = ["--yes", "mcp-remote", "__URL__", "--allow-http", "--transport", "http-only", "--header", "Authorization: Bearer __TOKEN__"]
startup_timeout_ms = 15000
```

4. 校验：确认 config.toml 是合法 TOML、段结构正确；说明改了什么、备份在哪。
5. 不要动 `~/.codex/AGENTS.md` 里的规则引用（薄壳只管规则，不管 MCP server 注册）。

---

## C. zcode

1. 找到 sill-ensoul 的 MCP server 注册 —— 通常在 `~/.zcode/cli/config.json` 的 `servers.sill-ensoul` 键下（以你的实际配置文件为准），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**（如 `~/.zcode/sill-ensoul-mcp.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册改成「stdio 命令桥接远程 HTTP」：命令用 `npx`，参数为 `--yes mcp-remote __URL__ --allow-http --transport http-only --header "Authorization: Bearer __TOKEN__"`，按你自己配置 schema 里注册一个 stdio server 的既有写法来放（Windows 下若命令名找不到，可加 `cmd /c` 包一层）。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件是合法 JSON、结构正确；说明改了什么、备份在哪。
5. 不要动你的 `AGENTS.md` 规则引用（薄壳只管规则，不管 MCP server 注册）。

---

## D. 其他 CLI（通用）

1. 找到本 CLI 里 sill-ensoul 的 MCP server 注册位置（你比任何人都清楚自己的配置放哪、什么格式），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**到不会被 git 跟踪的位置，告诉我备份路径。
3. 把 sill-ensoul 的注册改成「stdio 命令桥接远程 HTTP」—— 这是任何 CLI 都通用的方式：命令用 `npx`，参数为 `--yes mcp-remote __URL__ --allow-http --transport http-only --header "Authorization: Bearer __TOKEN__"`，按你既有 stdio server 注册的写法放。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件格式合法、结构正确；说明改了什么、备份在哪。

---

## E. Multica（平台 agent）

如果你是在 Multica 工作区里以平台 agent 的身份使用，除了按 A–D 装好工具外，再补这四步（被粘贴的 agent 自我判断）：

1. **先有工具**：按 A–D 之一把 sill-ensoul MCP 配到本机（用你自己的 token）。工具是 per-runtime / per-CLI 注入的，你的 runtime 是本机 daemon，所以 A–D 照常有效。
2. **没有平台 agent 就先建一个**：UI 建或 `multica agent create`。注意「装工具」≠「建平台实体」——平台 agent 是平台动作创建的，md 装不了也**不该**由 md 创建。
3. **绑定 ensoul 分身**：对该 agent 说「绑定 ensoul 分身」或直接丢本文件 —— 它会按 `ensoul-multica-binding` 规则用 `list_agents` 按领域匹配：有匹配的分身就绑定，没有就新建分身再绑定，唤醒块写进 instructions。
4. **当前 run 可能拿不到工具**：MCP 配置不热加载，刚装完的当前 run 可能还调用不了 —— 先按降级规则干活，下个 run 验证工具后再补绑定。

---

## 收尾（所有 CLI 都做）

- **必须完全退出本 CLI 再重新打开**，新会话才会用新配置（配置启动时加载，不热更新）。
- 重启后在会话里调 `agent_index` / `wiki_search` 能通 = 接入成功。
- 不要把 token / IP / 端口写进任何会被 git 提交的文件。
- 顺序别反：先确认服务器服务在跑、再配客户端。
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
