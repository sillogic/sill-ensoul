# Changelog

All notable changes to sill-ensoul. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

Version numbers have **one authoritative source**: `pyproject.toml`.
`ensoul.__version__` reads the installed package metadata (source tree without
an install falls back to the same value), and `sill-ensoul-init --version`
prints it — so "what's installed vs what's in the repo" is always comparable.
Tag releases as `v<version>` on `master` after merge.

## [0.5.0] — 2026-11-24

版本收尾 + 远程优先 + CLI 适配对齐（SILL-415）。**没有破坏性改动。**

### Changed — 文档口径：远程 MCP 成为推荐形态
- `README.md` / `README.zh-CN.md`：Quick Start 不再声称"默认形态 = 本地单机"。
  推荐形态 = 远程 MCP（服务器一份 KB，客户端零安装）；本地 stdio 降为"离线 / 只给自己用"。
  部署场景表重排：**1 连现成服务器**（朋友/同事/多机）→ 2 自建服务器 → 3 本地单机 → 4 切远程。
- `SETUP.md` 顶部路由：远程入口排在本地前面，并写明"连现成服务器不需要 clone 代码、不装本地包"。
- 中文 README 补齐原缺失的「选择部署形态」表，与英文版对齐。

### Fixed — CLI 适配落后于现实（Codex / pi）
- `deploy/cli-setup/cli-remote.md` **Codex（B 节）**：改用原生 streamable HTTP
  （`url` + `[mcp_servers.X.http_headers]`），mcp-remote 桥降为旧版回退并收进折叠块。
  补四个实测坑：改完必须完全退出重开、`codex mcp list` 里有子进程 ≠ 会话可用、
  同一 name 不能同时存在 `command` 与 `url`、Windows 的 `cmd /c` 只属于 stdio 旧写法。
- `deploy/cli-setup/cli-remote.md` **pi（E 节）**：从"pi 没有原生 MCP，只能写扩展"改为
  **pi 1.x 原生 MCP**（`~/.pi/agent/mcp.json`，`url` + `headers` + `${VAR}` 插值，
  `pi mcp add --url ... --bearer-token-env-var`）。旧扩展路线标注为 2026-10 以前的历史，
  并提醒移除旧扩展避免同名双开。
- `deploy/cli-setup/cli-remote.md` **D 节（通用 CLI）**：先判断是否支持原生 streamable
  HTTP，支持就写 `url`，不支持才退回 `npx mcp-remote` 桥（保留 `--allow-http` /
  `--transport http-only` / 串行握手三个已实测坑）。
- `deploy/cli-setup/update-machine-id.md`：Codex（`http_headers` 子表）与 pi
  （`mcp.json` 而非 `settings.json`）两节同步改成原生写法，旧桥写法保留在"旧版"段。
- 两个文件都加了**已验证版本基线**（2026-11-24）：Claude Code 2.1.292 / Codex 0.153.4 /
  pi 1.0.4 / OpenCode 1.18.26。

### Added
- `sill-ensoul-init --sync-shell` 支持 **pi** 的指令文件 `~/.pi/agent/AGENTS.md`
  （此前只覆盖 Claude Code / Zcode / Codex / OpenCode）。
- `README` 维护命令表补 `sill-ensoul-admin user create|list|revoke|reset`（多租户管理，
  远程部署用，生成可直接转发的接入卡）。
- 本文件 `CHANGELOG.md`（0.3.0 之后的改动此前从未归档）。

### Fixed — 版本号三处不一致
- `ensoul/__init__.py` 硬编码的 `__version__ = "0.1.0"`（pyproject 已是 0.5.0）改为从
  包元数据解析，未安装时回退到 `0.5.0`。
- `docs/multica.md` 里"pip v0.3.0 == 仓库 v0.3.0"的过期断言改为指向单一权威源。

## [0.4.0] — 2026-08-27

### Added
- **远程 MCP 部署（SIL-7 / D11）**：`ensoul/http.py` — streamable HTTP + Bearer token，
  `sill-ensoul-http` 入口，fail-closed（没有 token 不启动）。
- **多租户 Phase 1（SIL-8 / D12）**：用户表 + `sill-ensoul-admin` CLI（create / list /
  revoke / reset）+ 接入卡；身份 → KB root 的隔离缝。
- **部署文档体系（SIL-35）**：`docs/deployment.md` 上线 runbook、per-CLI 切换提示词
  （后合并为单个自适应文件 `deploy/cli-setup/cli-remote.md`）、`.env.example` + systemd 示例。
- 文档记下 mcp-remote 桥的两个必踩坑：`--allow-http`、`--transport http-only`。

### Changed
- `SETUP.md` 拆成 per-scenario 文件（`deploy/cli-setup/`），根 SETUP 变成路由表。
- `.mcp.json` 视为机器本地配置（untrack + ignore）。

### Fixed
- 依赖上界 `mcp>=1.2,<2`：mcp 2.x 删掉了 `mcp.server.fastmcp`，不钉上界会让新装直接
  起不来。

## [0.3.0] — 2026-08-26

### Added
- **机器身份（SIL-9 / D13）**：客户端 `X-Machine-Id` header → contextvar → 写入自动把
  `machine:` 打进 concept frontmatter，薄壳注入 `current machine` banner，解决多机共享
  一份 KB 时"本机"的指代歧义。
- 首次安装创建并绑定默认分身 agent，而不是让用户改自己已有 agent 的名字。

### Changed
- 并发写串行化（SQLite mutex，ROADMAP #12 / D9）。
