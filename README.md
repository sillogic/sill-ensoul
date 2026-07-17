# Sova

带长期记忆（OKF Wiki）的多智能体系统，与 CLI / 模型供应商解耦。每个 sova（Agent）拥有一个 OKF 知识 bundle；一个轻量 MCP server 把这些 bundle 暴露成工具，让你在 zcode / Claude Code / Codex 等 CLI 里直接读写 sova 的记忆。

> **Sova** — 给 CLI agent 的跨项目长期记忆。每个被唤醒的 agent 也是一个 **sova**（复数 sovas）。

**核心差异化**：记忆是**角色作用域**的——一个 sova 的经验跨所有项目累积，而不是像现有 CLI 那样只有项目级记忆。algo-engineer sova 在项目 A 学到的教训，项目 B 能用到。

> 设计背景见 [docs/DESIGN.md](docs/DESIGN.md)。记忆格式遵循 Google [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)（OKF v0.1）。进度跟踪见 [docs/ROADMAP.md](docs/ROADMAP.md)。

---

## 架构

```
  zcode / Claude Code / Codex   （推理发生在各 CLI 的模型供应商，不锁死）
           |  加载 persona + wiki 切片（薄壳指令：AGENTS.md / CLAUDE.md）
        MCP server（sova/，记忆引擎，14 个工具）
           |  读写
  knowledge/agents/<id>/  ← 每个 Agent 一个 OKF bundle（md 文件，全局 KB）
```

三层分离（设计决策 D1/D2，详见 docs/ROADMAP.md）：

- **引擎层**（`sova/`）— CLI 无关，只管数据/工具，不碰推理。
- **薄壳层**（`AGENTS.md` / `CLAUDE.md`）— 每 CLI 一份，定义"何时唤醒/检索/沉淀"，引用共享的 [WORKFLOW.md](WORKFLOW.md)。
- **记忆本体**（`knowledge/agents/<id>/`）— OKF markdown 文件，可 git、可 diff、人可读（用 Obsidian 直接看，见下文"用 Obsidian 管理记忆"）。

---

## 用 Obsidian 管理记忆

记忆是 markdown 文件，天然适合用 Obsidian 直接读改。**KB 默认路径**（H4：全局 KB，不在任何项目仓库里）：

| 平台 | 路径 |
|---|---|
| Windows | `%LOCALAPPDATA%\sova\knowledge`（即 `C:\Users\<你>\AppData\Local\sova\knowledge`） |
| Linux | `$XDG_DATA_HOME/sova/knowledge`（默认 `~/.local/share/sova/knowledge`） |
| macOS / 兜底 | `~/.sova/knowledge` |

可用环境变量 `SOVA_KB` 覆盖到任意位置（比如想放在 Dropbox / iCloud 同步）。

**用 Obsidian 打开**：Open vault → 选上面的路径 → 每个 agent 是一个子目录（`agents/<id>/`），里面的 `.md` 就是记忆。`.fts/` 和 `.obsidian/` 已在 `.gitignore`（索引和编辑器配置不入库）。

> 提示：KB 是你的私人记忆，不在仓库里。想多设备同步用 git 单独管理 KB 目录，或放云盘——但**别和 sova 代码仓库混在一起**（代码仓库的 `.gitignore` 排除了 `knowledge/`）。

---

## 安装与分享

> **命名状态**：项目品牌名为 **Sova**，agent 也称 sova（复数 sovas）。代码包名 `sova`、命令 `sova-mcp` / `sova-init` 已统一。

### 自己装（从 GitHub）

```bash
pip install git+https://github.com/<你的用户名>/sova.git
sova-init              # 初始化 KB + 创建默认 agent alter-ego + 打印各 CLI 适配步骤
```

`sova-init` 会打印 Claude Code / zcode 的适配命令（注册 MCP + 放薄壳）。

### 分享给同事（他只装了 Claude Code）

发给他这段：

```bash
pip install git+https://github.com/<你>/sova.git
sova-init                                    # 初始化 + 看步骤
claude mcp add sova --scope user -- sova-mcp
sova-init --print-shell >> ~/.claude/CLAUDE.md   # 追加薄壳，勿覆盖
```

装完新开 Claude Code 会话，已有一个默认 agent `alter-ego`（你的数字分身），对它说"唤醒 alter-ego"开始积累。

### 从 PyPI 装（发布后）

```bash
pip install sova-agent       # 发布后改为此名
sova-init
```

（发 PyPI 只需在 `pyproject.toml` 上加发版动作 + 改名，不改逻辑。）

> **隐私**：`knowledge/` 和 `shared/` 在 `.gitignore` 里，你的私人记忆和协作数据不会进仓库。同事装完是空 KB，各人的 sova 记忆独立、互不串。

---

## 目录结构

```
sova/                         # 仓库根
  sova/                       # 记忆引擎（纯逻辑 + MCP 壳）
    okf.py                    # OKF bundle 读写检索（纯逻辑，无 MCP 依赖）
    fts.py                    # SQLite FTS5 全文索引（CJK 按字分词 + BM25）
    server.py                 # FastMCP，把 okf 包成 14 个工具（薄壳，只透传）
    registry.py               # Phase 2: 所有权声明 + 边界扫描
    comm.py                   # Phase 2: agent 间通讯 + 边界协议
    init_cmd.py               # sova-init 命令（初始化 KB + 默认 agent + 适配步骤）
  tests/                      # 4 个测试，python run_tests.py 一键跑（自建临时 KB，不依赖 repo）
  WORKFLOW.md                 # CLI 无关的工作流权威版（唤醒/召回/沉淀/skill 调度）
  SHELL.md                    # CLI 无关薄壳（权威源，随包发布）
  docs/                       # 深入阅读：DESIGN.md（设计背景）/ ROADMAP.md（进度/决策）
  pyproject.toml              # 包定义（sova-mcp + sova-init 命令）
```

> KB（`knowledge/agents/<id>/`）和 Phase 2 协作数据（`shared/`）不在仓库里——它们是私有记忆，默认在 `%LOCALAPPDATA%/sova/knowledge`（见上节）。

---

## 测试

```bash
pip install -e .
python run_tests.py
```

四个测试，全绿 = 核心闭环跑通：

| 测试 | 验什么 |
|---|---|
| `test_smoke` | OKF 纯逻辑（读写检索 + log） |
| `test_search` | FTS5 检索 + persona 排除（11 项回归） |
| `test_mcp_live` | MCP 壳层（14 工具，走真实 stdio） |
| `test_cross_project` | 跨项目记忆留存（端到端） |

> 四个测试都自建临时 KB（不依赖 repo 预存数据），clone 后 `python run_tests.py` 直接跑。

---

## 14 个工具速查

| 工具 | 作用 |
|---|---|
| `list_agents` | 列出所有 sova |
| `create_agent` | 新建 sova（目录 + persona + index + log 模板） |
| `delete_agent` | 删除 sova（不可逆，需确认） |
| `agent_index` | 唤醒/切换 sova（persona + 知识地图） |
| `wiki_search` | 全文检索某 sova 的经验（FTS5 + BM25） |
| `wiki_read` | 读某条 concept 的细节 |
| `wiki_write_concept` | 沉淀新经验（type 必填） |
| `wiki_append_log` | 记一笔变更 |
| `registry_list` / `registry_update` | 多 sova 所有权声明（Phase 2） |
| `boundary_scan` | 检测 sova 间资源重叠（Phase 2） |
| `comm_send` / `comm_read` | sova 间消息（Phase 2） |
| `boundary_record` | 记录边界协议（Phase 2） |

> Phase 2（registry/comm/boundary）已实现但暂缓，当前聚焦孤立多 Agent。

---

## 核心特性

- **角色作用域记忆**：sova 经验跨项目累积，不是项目级。
- **OKF 文件本体**：记忆是 markdown，可 git/diff，用 Obsidian 直接读改。向量库只是索引（未来），md 永远是 source of truth。
- **FTS5 中文检索**：SQLite FTS5 + CJK 按字分词 + BM25，零依赖。
- **跨 CLI/跨模型**：MCP 是接口，推理在各 CLI 的供应商，不锁死。
- **提醒式半自动沉淀**：agent 主动判断时机 + 提炼，用户确认才写入（守质量门禁）。
- **skill 调度**：agent 积累"用 CLI skill 的经验"，推荐用、没有提醒装，不代装。

---

## 现在的状态

- ✅ 核心闭环跑通：唤醒 → 召回 → 引用 → 沉淀 → 跨项目留存。全特性测试 8/8 通过。
- ✅ 可发布：`pip install` 一键装，`sova-init` 自举适配各 CLI。
- ✅ 跨 CLI 验证：zcode + Claude Code 均适配成功。
- 🟡 暂缓：Phase 2 多 Agent 编排、sleeptime 全自动蒸馏。
- 详见 [docs/ROADMAP.md](docs/ROADMAP.md)。
