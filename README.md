# Sill-Ensoul

[English](README.en.md) | 简体中文

带长期记忆（OKF Wiki）的多智能体系统，与 CLI / 模型供应商解耦。每个 ensouler（Agent）拥有一个 OKF 知识 bundle；一个轻量 MCP server 把这些 bundle 暴露成工具，让你在 zcode / Claude Code / Codex 等 CLI 里直接读写 ensouler 的记忆。

> **Sill-Ensoul** — 给 CLI agent 的跨项目长期记忆。每个被唤醒的 agent 也是一个 **ensouler**（复数 ensoulers）。

**核心差异化**：记忆是**角色作用域**的——一个 ensouler 的经验跨所有项目累积，而不是像现有 CLI 那样只有项目级记忆。algo-engineer ensouler 在项目 A 学到的教训，项目 B 能用到。

> 设计背景见 [docs/DESIGN.md](docs/DESIGN.md)。记忆格式遵循 Google [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)（OKF v0.1）。进度跟踪见 [docs/ROADMAP.md](docs/ROADMAP.md)。

---

## 架构

```
  zcode / Claude Code / Codex   （推理发生在各 CLI 的模型供应商，不锁死）
           |  加载 persona + wiki 切片（薄壳指令：AGENTS.md / CLAUDE.md）
        MCP server（ensoul/，记忆引擎，8 个工具）
           |  读写
  knowledge/agents/<id>/  ← 每个 Agent 一个 OKF bundle（md 文件，全局 KB）
```

三层分离（设计决策 D1/D2，详见 docs/ROADMAP.md）：

- **引擎层**（`ensoul/`）— CLI 无关，只管数据/工具，不碰推理。
- **薄壳层**（`AGENTS.md` / `CLAUDE.md`）— 每 CLI 一份，定义"何时唤醒/检索/沉淀"，引用共享的 [WORKFLOW.md](WORKFLOW.md)。
- **记忆本体**（`knowledge/agents/<id>/`）— OKF markdown 文件，可 git、可 diff、人可读（用 Obsidian 直接看，见下文"用 Obsidian 管理记忆"）。

---

## 用 Obsidian 管理记忆

记忆是 markdown 文件，天然适合用 Obsidian 直接读改。**KB 默认路径**（H4：全局 KB，不在任何项目仓库里）：

| 平台 | 路径 |
|---|---|
| Windows | `%LOCALAPPDATA%\ensoul\knowledge`（即 `C:\Users\<你>\AppData\Local\ensoul\knowledge`） |
| macOS | `~/Library/Application Support/ensoul/knowledge` |
| Linux | `$XDG_DATA_HOME/ensoul/knowledge`（默认 `~/.local/share/ensoul/knowledge`） |
| 兜底 | `~/.ensoul/knowledge` |

可用环境变量 `ENSOUL_KB` 覆盖到任意位置（比如想放在 Dropbox / iCloud 同步）。

**用 Obsidian 打开**：Open vault → 选上面的路径 → 每个 agent 是一个子目录（`agents/<id>/`），里面的 `.md` 就是记忆。`.fts/` 和 `.obsidian/` 已在 `.gitignore`（索引和编辑器配置不入库）。

> 提示：KB 是你的私人记忆，不在仓库里。想多设备同步用 git 单独管理 KB 目录，或放云盘——但**别和 sill-ensoul 代码仓库混在一起**（代码仓库的 `.gitignore` 排除了 `knowledge/`）。

---

## 安装与分享

> **命名状态**：项目品牌名为 **Sill-Ensoul**，agent 也称 ensouler（复数 ensoulers）。代码包名 `sill-ensoul`、命令 `sill-ensoul-mcp` / `sill-ensoul-init` 已统一。

### 自己装（从 GitHub）

clone 仓库后，在你的 CLI（Claude Code / Codex / zcode 等）里二选一：

- 说一句：`帮我配置 sill-ensoul，按 <repo>/SETUP.md 来`
- 或更直接：把 [SETUP.md](SETUP.md) 的内容**复制粘贴**进对话框，按回车

CLI 的 AI 会按 SETUP.md：先 `pip install` 装 sill-ensoul 包（会征求你同意）、跑 `sill-ensoul-init` 建知识库和默认 agent `alter-ego`、然后自己注册 MCP server + 装薄壳。全程你只发一次，装完重启 CLI 说"唤醒 alter-ego"即可。

> 不想让 AI 装包？自己敲 `pip install -e <repo>` + `sill-ensoul-init`，再让 AI 适配也行。

> **首次使用**：装完适配好 CLI 后，新开会话直接说 **`唤醒 alter-ego`**——这是你的数字分身（默认 agent），空记忆，先用它积累经验。攒够某领域经验后再 `create_agent` 分裂出专门 agent。也可以说"唤醒分身"或"wake up alter-ego"，薄壳会识别。

> **想要自己的 agent 名字？** 直接对 CLI 说"帮我建一个叫小索的 agent"，它会调 `create_agent(agent_id="小索", ...)`。之后说 **`唤醒 小索`** 即可——agent_id 就是你起的名字，无需改薄壳、无需重启 CLI。alter-ego 只是开箱即用的默认起点，不是唯一选择。

### 分享给同事（他装了任意 MCP-capable CLI）

发给他仓库地址，让他在 CLI 里二选一：说 `帮我配置 sill-ensoul，按 <repo>/SETUP.md 来`，或直接把 [SETUP.md](SETUP.md) 内容贴进对话框。他什么都不用敲——CLI 的 AI 跑完全程（装包 + 建库 + 适配）。sill-ensoul 不绑死任何 CLI 的配置方式，CLI 更新了也不用改 sill-ensoul。适配完重启 CLI，说"唤醒 alter-ego"开始。

### 从 PyPI 装（发布后）

```bash
pip install sill-ensoul       # 发布后改为此名
sill-ensoul-init
```

（发 PyPI 只需在 `pyproject.toml` 上加发版动作 + 改名，不改逻辑。）

> **隐私**：`knowledge/` 在 `.gitignore` 里，你的私人记忆不会进仓库。同事装完是空 KB，各人的 ensouler 记忆独立、互不串。

---

## 目录结构

```
ensoul/                         # 仓库根
  ensoul/                       # 记忆引擎（纯逻辑 + MCP 壳）
    okf.py                    # OKF bundle 读写检索（纯逻辑，无 MCP 依赖）
    fts.py                    # SQLite FTS5 全文索引（CJK 按字分词 + BM25）
    server.py                 # FastMCP，把 okf 包成 8 个工具（薄壳，只透传）
    init_cmd.py               # sill-ensoul-init 命令（初始化 KB + 默认 agent + 适配步骤）
  tests/                      # 3 个发布测试，python -m tests.run_tests 一键跑（自建临时 KB，不依赖 repo）
  WORKFLOW.md                 # CLI 无关的工作流权威版（唤醒/召回/沉淀/skill 调度）
  SHELL.md                    # CLI 无关薄壳（权威源，随包发布）
  SETUP.md                    # CLI 适配意图（给 CLI 的 AI 读，让它自己注册 MCP + 装薄壳）
  docs/                       # 深入阅读：DESIGN.md（设计背景）/ ROADMAP.md（进度/决策）
  pyproject.toml              # 包定义（sill-ensoul-mcp + sill-ensoul-init 命令）
```

> KB（`knowledge/agents/<id>/`）不在仓库里——它是私有记忆，默认在 `%LOCALAPPDATA%/ensoul/knowledge`（见上节）。

---

## 测试

```bash
pip install -e .
python -m tests.run_tests
```

三个发布测试，全绿 = 核心闭环跑通：

| 测试 | 验什么 |
|---|---|
| `test_search` | FTS5 检索 + persona 排除（11 项回归） |
| `test_mcp_live` | MCP 壳层（8 工具，走真实 stdio） |
| `test_cross_project` | 跨项目记忆留存（端到端） |

> 三个发布测试都自建临时 KB（不依赖 repo 预存数据），clone 后 `python -m tests.run_tests` 直接跑。
>
> 另有 `test_smoke`（维护者本地用，依赖开发者全局 KB 里的真实 `algo-engineer`，不纳入 `run_tests.py`，新用户无需跑它）。

---

## 8 个工具速查

| 工具 | 作用 |
|---|---|
| `list_agents` | 列出所有 ensouler |
| `create_agent` | 新建 ensouler（目录 + persona + index + log 模板） |
| `delete_agent` | 删除 ensouler（不可逆，需确认） |
| `agent_index` | 唤醒/切换 ensouler（persona + 知识地图） |
| `wiki_search` | 全文检索某 ensouler 的经验（FTS5 + BM25） |
| `wiki_read` | 读某条 concept 的细节 |
| `wiki_write_concept` | 沉淀新经验（type 必填） |
| `wiki_append_log` | 记一笔变更 |

> 多 agent 协作不需要专门工具：任何 agent 都能用 `wiki_write_concept(agent_id=...)` / `wiki_read` / `wiki_search` 操作**其他** agent 的记忆——编排者直接读写，无需自治协商基础设施（见 docs/ROADMAP.md 的 D6 决策）。

---

## 核心特性

- **角色作用域记忆**：ensouler 经验跨项目累积，不是项目级。
- **OKF 文件本体**：记忆是 markdown，可 git/diff，用 Obsidian 直接读改。向量库只是索引（未来），md 永远是 source of truth。
- **FTS5 中文检索**：SQLite FTS5 + CJK 按字分词 + BM25，零依赖。
- **跨 CLI/跨模型**：MCP 是接口，推理在各 CLI 的供应商，不锁死。
- **提醒式半自动沉淀**：agent 主动判断时机 + 提炼，用户确认才写入（守质量门禁）。
- **skill 调度**：agent 积累"用 CLI skill 的经验"，推荐用、没有提醒装，不代装。

---

## 现在的状态

- ✅ 核心闭环跑通：唤醒 → 召回 → 引用 → 沉淀 → 跨项目留存。全特性测试 8/8 通过。
- ✅ 可发布：`pip install` 一键装，`sill-ensoul-init` 自举适配各 CLI。
- ✅ 跨 CLI 验证：zcode + Claude Code 均适配成功。
- 🟡 未做：sleeptime 全自动蒸馏。
- 详见 [docs/ROADMAP.md](docs/ROADMAP.md)。
