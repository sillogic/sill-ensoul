# sill-ensoul 线上部署文档（公网 HTTP MCP）

> 适用形态：单租户、公网直连、Bearer token 鉴权（SIL-7 / D11）。
> 防火墙/安全组在云控制台操作（阿里云 ECS 控制台 → 安全组），不在本文档范围。
> 服务器已经部署好的同学：直接看 [二、日常运维](#二日常运维) 和 [四、客户端切换](#四客户端切换各-cli-指向远程)。

## 形态总览

```
本地 CLI（Claude Code / Codex / zcode）
   │  每个请求带 Authorization: Bearer <token>
   ▼
公网 ──► sill-ensoul-http（服务器，systemd 托管，默认 0.0.0.0:8930）
           │  ENSOUL_MCP_TOKEN 门禁（fail-closed，缺 token 拒绝启动）
           ▼
         knowledge/（唯一权威记忆源，ENSOUL_KB 指向）
```

- 服务器是**唯一权威记忆源**，本地机器不再各持一份 `knowledge/`。
- 鉴权回答"谁能连"（token → 身份 owner）；多租户是未来（SIL-8），接缝已留（`ensoul/http.py` 的 `_identity_for_token` / `_kb_root_for_identity`），当前无需配置。

---

## 一、服务器端部署（一次性）

### 1.1 安装

要求 Python ≥ 3.10。包还没发布到 PyPI，从 git 装：

```bash
git clone https://github.com/sillogic/sill-ensoul.git
cd sill-ensoul
# 建 venv（uv 或 python -m venv 都行），然后：
.venv/bin/python -m pip install ".[http]"     # uvicorn 等 HTTP 依赖走 optional extra
```

> **坑（H20/H21）**：uv 建的 venv **默认不带 pip**，裸 `pip` 会落到系统解释器（如 Python 3.6），把 `mcp>=1.2,<2` 全部过滤 → 报 `(from versions: none)`。**一律用 `.venv/bin/python -m pip` 显式指定解释器。**
> 依赖已钉 `mcp>=1.2,<2`（mcp 2.x 删了 `mcp.server.fastmcp`，两条 server 路径一起崩，commit `22ce243`）。

### 1.2 环境变量

模板在仓库根 `.env.example`，复制成 root-only 文件再填：

```bash
sudo mkdir -p /etc/sill-ensoul
sudo cp .env.example /etc/sill-ensoul/env && sudo chmod 600 /etc/sill-ensoul/env
sudo vi /etc/sill-ensoul/env    # 必填 ENSOUL_MCP_TOKEN；建议填 ENSOUL_KB
```

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `ENSOUL_MCP_TOKEN` | **必填（fail-closed）** | — | 强随机串：`openssl rand -hex 32`。所有客户端填同一个值 |
| `ENSOUL_KB` | 建议 | Linux 平台默认 `~/.local/share/ensoul/knowledge` | 服务器记忆根，KB 迁移后指向解包位置 |
| `ENSOUL_MCP_HOST` | 否 | `0.0.0.0` | 只想内网访问就改 `127.0.0.1` |
| `ENSOUL_MCP_PORT` | 否 | `8930` | 公网形态建议改高位随机端口 |

### 1.3 systemd 托管

```bash
sudo cp deploy/sill-ensoul-http.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sill-ensoul-http
```

unit 里 `EnvironmentFile=/etc/sill-ensoul/env` = systemd 在启动进程前把该文件所有 `KEY=VALUE` 注入环境变量；`ExecStart` 用 venv 解释器直启（绕开裸 pip 同款 PATH 陷阱）。可建独立用户（`User=sill-ensoul`）替代 root，需给该用户 `ENSOUL_KB` 目录读写权限。

### 1.4 启动验证

```bash
systemctl status sill-ensoul-http        # active (running)
ss -tlnp | grep 8930                     # 端口在听（按实际端口）
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8930/mcp
```

第三条返回 **401 = 对**（鉴权门禁在工作）；返回 200/404 说明没走鉴权中间件（代码不是 master 上的 SIL-7 版本）。

---

## 二、日常运维

### 2.1 重启（高频问题）

环境变量**只在进程启动时读一次，不热更新**：

| 你改了什么 | 要做什么 |
|---|---|
| `/etc/sill-ensoul/env`（token、KB 路径等） | `sudo systemctl restart sill-ensoul-http` |
| unit 文件本身 | `sudo systemctl daemon-reload` 之后 `restart` |
| 什么都没改，就是服务挂了/想拉起 | `sudo systemctl restart sill-ensoul-http` |

验证重启生效：`curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<port>/mcp` 应返回 401。

### 2.2 看日志

```bash
journalctl -u sill-ensoul-http -f
```

### 2.3 更新服务器（新版本发布后）

```bash
cd /opt/sill-ensoul && git pull
# 依赖没变就不用重装；变了（pyproject 动过）再跑：
.venv/bin/python -m pip install -U ".[http]"
sudo systemctl restart sill-ensoul-http
```

注意：`--version` / `pip show` 显示的是 dist-info 元数据，不是源码。确认"装的是不是最新"以 `git log -1 --oneline` 为准（SIL-28 教训）。

---

## 三、KB 迁移（本地 → 服务器）

记忆就是纯文件：本地 KB 根下 `knowledge/`，每个分身一个 `agents/<id>/` 目录。整包复制即可：

```bash
# 本地（Windows PowerShell，在 %LOCALAPPDATA%\ensoul 下）：
tar -cf knowledge.tar --exclude=.fts knowledge
scp knowledge.tar root@<服务器IP>:/opt/sill-ensoul/
# 服务器：
cd /opt/sill-ensoul && tar -xf knowledge.tar && ls knowledge/agents/
```

两条注意：

1. **排除 `.fts/`** —— 每台机器本地生成的搜索索引缓存，复制过去没意义，服务器会自动重建。
2. **多台机器都有记忆时先定基准**：选内容最新最全的一台整包搬，另一台有而基准没有的内容手工合并。**别两台都覆盖**，会互相冲掉。

搬完把 `ENSOUL_KB` 指到解包位置（示例 `/opt/sill-ensoul/knowledge`），重启服务（见 2.1）。验证：本地 CLI 远程调 `agent_index("ensoul-dev")` 能读到 persona = 迁移成功。

**顺序别反**：先迁移 KB、再切客户端（否则那段时间 CLI 对着空库干活）。

---

## 四、客户端切换（各 CLI 指向远程）

不手敲命令 —— **一份"投喂提示词"适用所有 CLI**：`deploy/cli-setup/switch-to-remote.md`。文件里 A–D 按 CLI 分节（A Claude Code streamable-http 原生；B Codex desktop / C zcode / D 其他 CLI 用 `npx mcp-remote` stdio↔HTTP 桥），把文件内容整个丢给对应 CLI，它会先判断自己是哪类、只做自己那一节，自己读配置、自己改、自己验证。

用法三步：① 打开目标 CLI 的聊天窗口；② **先把文件复制出仓库再改**（文件在公开仓库里，直接改会在 `git add .` 提交时泄露；`cp deploy/cli-setup/switch-to-remote.md ~/switch-to-remote.md`，Windows 用 `Copy-Item deploy\cli-setup\switch-to-remote.md $HOME\switch-to-remote.md`），在副本上把 `<服务器公网IP>` / `<端口>` / `<TOKEN>` 三个占位符换成真实值（token 在服务器 `/etc/sill-ensoul/env` 里）；③ 把整个文件内容粘贴给它，用完删除副本。仓库内原文件始终保持占位符。

要点（提示词里已带，这里提醒）：
- server 名保持 `sill-ensoul` 不变，只是把注册从 stdio 换成 HTTP；
- **mcp-remote 桥接命令必带 `--allow-http --transport http-only`**（非 HTTPS 地址 mcp-remote 默认拒绝；默认 http-first 的 SSE 回退探测与 FastMCP session 管理冲突 → 400 Missing session ID，已实测，见 switch-to-remote.md 顶部公共参数说明）；
- 改之前先把旧注册备份；
- **改完必须完全退出该 CLI 再重开**（配置启动时加载，不热加载）；
- 不要把填了真实值的提示词文件提交进任何 git 仓库（一律在仓库外副本上改）。

---

## 五、安全要点

- **token 是唯一防线**：别提交 git、别贴到公网；泄露 = 换 token + 重启服务 + 更新各 CLI。
- **公网直连建议挂 TLS**：在服务器前面挂一层 Caddy/nginx 反代出 HTTPS（客户端 url 改 `https://...`），否则 Bearer token 在网络上明文传输。
- 端口建议高位随机，安全组只放行该端口。
- 防火墙/安全组操作在云控制台做，本文档不覆盖。

---

## 六、排障速查

| 现象 | 根因 | 解法 |
|---|---|---|
| `sill-ensoul-http --help` 崩 `No module named 'mcp.server.fastmcp'` | 装到了 mcp 2.x（模块被删） | `.venv/bin/python -m pip install -U "mcp>=1.2,<2" uvicorn` |
| `pip install ...` 报 `(from versions: none)` | 裸 `pip` 落到系统 Python 3.6，mcp 全部版本 requires-python ≥3.10 被滤掉 | 用 `.venv/bin/python -m pip`；uv venv 无 pip 则 `uv pip install --python .venv/bin/python ...` |
| `curl` 返回 200/404 | 没走鉴权中间件（代码版本不对） | `git pull` 到 master（≥ a41f42e）后重启 |
| `curl` 返回 401 | ✅ 正常，门禁在工作 | — |
| 客户端调不到 sill-ensoul 工具 | 配置没生效 / 没重启 | 完全退出 CLI 重开；检查备份前后配置差异 |
| 远程连不上（超时/拒绝） | 服务没起 / 端口没放行 / 公网 IP 变了 | `systemctl status` + `ss -tlnp`；按量付费实例停机再开可能换公网 IP，介意就绑弹性 IP |
| 某用户的 token 报 401 | 用户被 revoke / token 换过 | `sill-ensoul-admin user list` 看 enabled；`reset` 换新 token + 新接入卡 |

---

## 七、多租户用户管理（SIL-8，方案 A）

多用户共用同一服务器时，每个用户 = 一个 Bearer token = 一个**隔离的 KB 根**（`<ENSOUL_KB>/tenants/<user_id>/`）。

### 7.1 用户管理（服务器上跑，零 UI）

```bash
# 创建用户：打印 token（仅此一次）+ 生成接入卡 md（含真实 URL+token，转发给该用户）
sill-ensoul-admin user create --name 小王 --url http://<公网IP>:<端口>/mcp
# 也可以显式指定 user_id（默认是名字的 slug，中文名会退化成 u-xxxxxx）
sill-ensoul-admin user create --name 小王 --id xiaowang --url http://1.2.3.4:8930/mcp
# 列表（永远不显示 token，只有哈希前缀供核对）
sill-ensoul-admin user list
# 吊销（token 立即失效，下次请求生效，无需重启）/ 恢复 / 轮换（换新 token + 新接入卡）
sill-ensoul-admin user revoke xiaowang
sill-ensoul-admin user enable  xiaowang
sill-ensoul-admin user reset   xiaowang --url http://1.2.3.4:8930/mcp
```

KB 不在默认位置时加 `--kb <路径>`（或设 `ENSOUL_KB`）。

### 7.2 鉴权两路（owner 向后兼容）

- **owner token**（`ENSOUL_MCP_TOKEN`）：身份 `owner`，看 base 根 —— 存量部署零改动，owner 是管理员，能看到所有租户数据（管理/排障用）。
- **用户 token**（用户表）：身份 = `user_id`，只能读写自己的 `tenants/<user_id>/` —— 两个租户可以有同名 agent（都是 `ensoul-dev`），互不干扰。

### 7.3 接入卡说明

- `user create` / `user reset` 会在 `--out`（默认当前目录）写 `sill-ensoul-card-<id>.md`：SIL-35 自识别分节（A Claude Code / B Codex / C zcode / D 其他）+ E Multica（平台 agent 先装工具再绑分身）。
- **卡里是活 token，等于钥匙**：只走私密渠道转发，绝不进 git / 公开渠道；接入完成后建议删除。
- 用户 token 泄露时 `user revoke`（立即杀死）或 `user reset`（换新）。
- 用户表在 `<ENSOUL_KB>/users.json`，只存 sha256 哈希，服务器文件泄露 ≠ 凭据泄露。
- 公网形态下 Bearer 是明文裸奔风险，仍须挂 TLS（见§5）。

---

## 附录：关键变量与路径

| 项 | 值 |
|---|---|
| 服务名 | `sill-ensoul-http`（命令同名） |
| 默认监听 | `0.0.0.0:8930`（`ENSOUL_MCP_PORT` / `--port` 可改） |
| 环境变量文件 | `/etc/sill-ensoul/env`（root-only, chmod 600） |
| systemd unit | `deploy/sill-ensoul-http.service` |
| 环境变量模板 | `.env.example` |
| 客户端提示词 | `deploy/cli-setup/switch-to-remote.md` |
| KB 根 | `ENSOUL_KB`，示例 `/opt/sill-ensoul/knowledge` |
| 源码 | https://github.com/sillogic/sill-ensoul （从 git 装，未发布 PyPI） |

---

## 修订记录

- 2026-08-27：初版。沉淀自 SIL-7 首次线上部署全程（a41f42e 鉴权落地 → 22ce243 mcp 钉版本 → e9faf39 env+systemd → 排障 H20/H21 → 客户端提示词文件）。
