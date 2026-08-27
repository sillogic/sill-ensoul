# 任务：把 sill-ensoul MCP 从本地 stdio 切换到远程 HTTP 服务器

你是本机 Codex（desktop）。请帮我完成一次 sill-ensoul MCP 配置切换：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 目标服务器（已确认可连）

- MCP 端点：`http://<服务器公网IP>:<端口>/mcp`
- 鉴权头：`Authorization: Bearer <TOKEN>`

## 步骤

1. 打开 `~/.codex/config.toml`，找到（或新增）`[mcp_servers.sill-ensoul]` 段。
2. 若已有旧注册，先把该段**原样备份**（如 `~/.codex/sill-ensoul-mcp.backup.toml`），告诉我备份路径。
3. 把该段改成用 `mcp-remote` 桥接远程 HTTP（Windows 用 `cmd /c` 包一层，Linux/macOS 直接写）：

Windows：

```toml
[mcp_servers.sill-ensoul]
command = "cmd"
args = ["/c", "npx", "--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--header", "Authorization: Bearer <TOKEN>"]
startup_timeout_ms = 15000
```

Linux / macOS：

```toml
[mcp_servers.sill-ensoul]
command = "npx"
args = ["--yes", "mcp-remote", "http://<服务器公网IP>:<端口>/mcp", "--header", "Authorization: Bearer <TOKEN>"]
startup_timeout_ms = 15000
```

4. 校验：确认 config.toml 是合法 TOML、段结构正确；说明改了什么、备份在哪。
5. 收尾：告诉我**必须完全退出 Codex 再重开**（配置启动时加载，不热更新）；重启后会话里能调 `agent_index` / `wiki_search` 就是成功。

## 不要做

- 不要动 `~/.codex/AGENTS.md` 里的规则引用（薄壳只管规则，不管 MCP server 注册）。
- 不要把 token 写进任何会被 git 提交的文件。
