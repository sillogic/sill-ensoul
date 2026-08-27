# 任务：把 sill-ensoul MCP 从本地 stdio 切换到远程 HTTP 服务器

你是本机 CLI（非 Claude Code / Codex / zcode 的其他工具）。请帮我完成一次 sill-ensoul MCP 配置切换：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 目标服务器（已确认可连）

- MCP 端点：`http://<服务器公网IP>:<端口>/mcp`
- 鉴权头：`Authorization: Bearer <TOKEN>`

## 步骤

1. 找到本 CLI 里 sill-ensoul 的 MCP server 注册位置（你比任何人都清楚自己的配置放哪、什么格式），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**到不会被 git 跟踪的位置，告诉我备份路径。
3. 把 sill-ensoul 的注册改成「stdio 命令桥接远程 HTTP」—— 这是任何 CLI 都通用的方式（不依赖各家对 http 的原生支持）：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --header "Authorization: Bearer <TOKEN>"`，按你既有 stdio server 注册的写法放。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件格式合法、结构正确；说明改了什么、备份在哪。
5. 收尾：告诉我**必须完全退出本 CLI 再重开**才生效；重启后会话里能调 `agent_index` / `wiki_search` 就是成功。

## 不要做

- 不要把 token 写进任何会被 git 提交的文件。
