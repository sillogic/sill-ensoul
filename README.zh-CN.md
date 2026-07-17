# Sill-Ensoul

[English](README.md) | 简体中文

**跟随你的 agent 跨工具、跨项目、跨会话的长期记忆。**

给 CLI agent 装上一份不会因为换项目、换工具、重开会话就消失的经验——不动你的工作流，只给你已经在用的 agent 加记忆。

> *ensoul* /ɪnˈsoʊl/ — 动词。赋予某个 CLI agent 跨会话延续的记忆，让它在每次新对话里不只是从零开始的空白助手。一个被 ensoul 过的 agent 叫 **ensouler**。

---

## 它能做什么

- **跨工具**：一份记忆，在 Claude Code / Codex / zcode / Cursor / OpenCode 之间通用。今天用 Claude，明天切 Codex，你的 agent 记忆不丢。
- **跨项目**：记忆存在全局 KB，不绑定任何项目仓库。algo-engineer 在项目 A 踩的坑，项目 B 直接召回。
- **跨会话**：每次新对话，agent 先 `wiki_search` 自己的历史经验，带着记忆开工，而不是从零。
- **agent 记忆隔离**：建多个 ensouler（算法工程师、后端、测试、UI……），各自独立记忆 bundle，互不污染。唤醒谁，就用谁的经验。
- **记忆即文件**：纯 markdown（遵循 [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)），可 git、可 diff、用 Obsidian 直接读改。向量库只是索引，md 永远是 source of truth。
- **零外部依赖**：SQLite FTS5 全文检索（CJK 按字分词 + BM25），无需 OpenAI key、无需 Docker、无需云服务。模型供应商无关——推理始终在你的 CLI 里。
- **主动沉淀**：agent 在任务中踩了非平凡的坑、做了可复用的决策，会**主动提醒你**"这条值得记进 wiki"，你确认才写入——既不靠你自律去记，也不往记忆里灌垃圾。

---

## Quick Start

clone 仓库后，在你的 CLI（Claude Code / Codex / zcode / OpenCode 等）里**任选以下一种方式**：

```text
# 方式 A：让 CLI 的 AI 自己装（推荐，全程你只发一句）
说：帮我配置 sill-ensoul，按 <repo>/SETUP.md 来

# 方式 B：更直接——把 SETUP.md 内容粘贴进对话框，回车
```

CLI 的 AI 会按 [SETUP.md](SETUP.md)：装包 → 建知识库 → 建默认 agent `alter-ego` → 注册 MCP server → 装薄壳。装完重启 CLI，说：

```text
唤醒 alter-ego      # 或 wake up alter-ego / 唤醒分身
```

`alter-ego` 是你的数字分身（默认 agent，空记忆）。先用它积累经验，攒够某个领域（算法/后端/…）后，对 CLI 说"帮我建一个叫 algo-engineer 的 agent"分裂出专门 ensouler。

<details>
<summary>不想让 AI 装包？手动 3 步</summary>

```bash
pip install -e <repo>          # 或发布后 pip install sill-ensoul
sill-ensoul-init               # 建全局 KB + 默认 agent alter-ego
# 然后让 CLI 的 AI 读 SETUP.md 完成 MCP 注册 + 薄壳放置
```
</details>

<details>
<summary>记忆存在哪？能放云盘同步吗？</summary>

全局 KB，不在任何项目仓库里（私人记忆绝不进 git）：

| 平台 | 默认路径 |
|---|---|
| Windows | `%LOCALAPPDATA%\ensoul\knowledge` |
| macOS | `~/Library/Application Support/ensoul/knowledge` |
| Linux | `$XDG_DATA_HOME/ensoul/knowledge`（默认 `~/.local/share/ensoul/knowledge`） |

设环境变量 `ENSOUL_KB=<路径>` 可放到任意位置（比如 Dropbox / iCloud 目录做多设备同步）。用 Obsidian 打开这个目录，每个 agent 是一个子文件夹，里面的 `.md` 就是记忆。
</details>

---

## 它怎么工作

```
  Claude Code / Codex / zcode / Cursor   ← 推理发生在各 CLI 的模型供应商，不锁死
           |  加载 persona + wiki 切片（薄壳：AGENTS.md / CLAUDE.md）
        sill-ensoul-mcp（MCP server，8 个工具，读写检索）
           |  读写
  knowledge/agents/<id>/   ← 每个 ensouler 一个 OKF bundle（markdown 文件）
```

**三层分离**（设计决策 D1/D2，详见 [docs/ROADMAP.md](docs/ROADMAP.md)）：

- **引擎层**（`ensoul/`）— CLI 无关，只管数据/工具，不碰推理。`server.py` 是薄 MCP 壳，只透传。
- **薄壳层**（`AGENTS.md` / `CLAUDE.md`）— 每 CLI 一份，定义"何时唤醒/检索/沉淀"，引用共享的 [WORKFLOW.md](WORKFLOW.md)。
- **记忆本体**（`knowledge/agents/<id>/`）— OKF markdown 文件，可 git、可 diff、人可读。

核心循环：**唤醒**（加载 persona + 知识地图）→ **召回**（检索相关经验）→ **引用**（带 concept_id 引用真实记忆）→ **沉淀**（提炼新经验，你确认才写入）→ 跨项目/会话留存。

---

## 8 个工具

| 工具 | 作用 |
|---|---|
| `list_agents` | 列出所有 ensouler |
| `create_agent` | 新建 ensouler（目录 + persona + index + log 模板） |
| `delete_agent` | 删除 ensouler（不可逆，需确认） |
| `agent_index` | 唤醒/切换 ensouler（persona + 知识地图） |
| `wiki_search` | 全文检索某 ensouler 的经验（FTS5 + BM25，支持中文） |
| `wiki_read` | 读某条经验的细节 |
| `wiki_write_concept` | 沉淀新经验（type 必填） |
| `wiki_append_log` | 记一笔变更 |

> 多 ensouler 协作不需要专门工具：任何 agent 都能用 `wiki_write_concept(agent_id=...)` 操作**其他** agent 的记忆——编排者直接读写（见 [docs/ROADMAP.md](docs/ROADMAP.md) D6）。

---

## 测试

```bash
pip install -e .
python -m tests.run_tests
```

三个发布测试全绿 = 核心闭环跑通（都自建临时 KB，clone 后直接跑）：

| 测试 | 验什么 |
|---|---|
| `test_search` | FTS5 检索 + persona 排除（11 项回归） |
| `test_mcp_live` | MCP 壳层（8 工具，走真实 stdio） |
| `test_cross_project` | 跨项目记忆留存（端到端） |

---

## 状态

- ✅ 核心闭环跑通：唤醒 → 召回 → 引用 → 沉淀 → 跨项目留存
- ✅ 可安装：`pip install` + `sill-ensoul-init` 自举适配各 CLI
- ✅ 跨 CLI 验证：zcode + Claude Code 均适配成功
- ✅ 设计定案：提醒式半自动蒸馏是**终态设计**（不是全自动的过渡态）；多 agent 协作走编排者模式（D6）
- 详见 [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 深入阅读

- [docs/DESIGN.md](docs/DESIGN.md) — 设计背景：为什么 OKF、为什么 MCP、与 mem0/letta/graphiti 的对比
- [docs/ROADMAP.md](docs/ROADMAP.md) — 进度跟踪 + 设计决策 D1-D6 + 历史踩坑 H1-H12
- [WORKFLOW.md](WORKFLOW.md) — CLI 无关的工作流权威版（唤醒/召回/沉淀/skill 调度）
- [SETUP.md](SETUP.md) — 给 CLI 的 AI 读的适配意图（机器可读）

## License

基于 [MIT 协议](LICENSE) 发布 © 2026 sillogic。
