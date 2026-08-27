# 任务：把 sill-ensoul MCP 从本地 stdio 切换到远程 HTTP 服务器

你是本机 Claude Code。请帮我完成一次 sill-ensoul MCP 配置切换：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 目标服务器（已确认可连）

- MCP 端点：`http://<服务器公网IP>:<端口>/mcp`
- 鉴权头：`Authorization: Bearer <TOKEN>`（每个请求都带）

## 步骤

1. 找到 sill-ensoul 的 MCP 注册。检查两处：① `~/.claude.json` 顶层 `mcpServers`（全局层）；② 当前项目 `.mcp.json` 顶层 `mcpServers`（项目层）。两处都可能存在 —— 告诉我你发现了几处、分别在哪个文件、现在的注册内容是什么。
2. 对每处现有注册，先把它**原样备份**（写到一个不会被 git 跟踪的位置，如 `~/.sill-ensoul-mcp-config.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册改成下面这个 streamable-http 形式（server 名保持 `sill-ensoul` 不变）：

```json
{ "mcpServers": { "sill-ensoul": {
  "type": "streamable-http",
  "url": "http://<服务器公网IP>:<端口>/mcp",
  "headers": { "Authorization": "Bearer <TOKEN>" }
} } }
```

如果我的 Claude Code 版本较老不支持 `streamable-http`，告诉我并改用 `"type": "http"`（或提示我先升级 CLI）。

4. 校验：确认改动后文件是合法 JSON、结构正确；逐处说明改了什么、旧值备份在哪。
5. 收尾：告诉我**必须完全退出 Claude Code 再重新打开**，新会话才会用新配置；重启后我在会话里调 `agent_index` / `wiki_search` 能通就是成功。

## 不要做

- 不要动本地 `sill-ensoul-mcp` 的安装（stdio 本地 server 保留；以后想切回来用备份即可）。
- 不要把 token 写进任何会被 git 提交的文件。
