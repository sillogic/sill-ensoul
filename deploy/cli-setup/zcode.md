# 任务：把 sill-ensoul MCP 从本地 stdio 切换到远程 HTTP 服务器

你是本机 zcode。请帮我完成一次 sill-ensoul MCP 配置切换：**自己动手改配置、自己验证，不要只给我命令让我执行。**

## 目标服务器（已确认可连）

- MCP 端点：`http://<服务器公网IP>:<端口>/mcp`
- 鉴权头：`Authorization: Bearer <TOKEN>`

## 步骤

1. 找到 sill-ensoul 的 MCP server 注册 —— 通常在 `~/.zcode/cli/config.json` 的 `servers.sill-ensoul` 键下（以你的实际配置文件为准），把现在的注册内容告诉我。
2. 先把旧注册**原样备份**（如 `~/.zcode/sill-ensoul-mcp.backup.json`），告诉我备份路径。
3. 把 sill-ensoul 的注册改成「stdio 命令桥接远程 HTTP」：命令用 `npx`，参数为 `--yes mcp-remote http://<服务器公网IP>:<端口>/mcp --header "Authorization: Bearer <TOKEN>"`，按你自己配置 schema 里注册一个 stdio server 的既有写法来放（Windows 下若命令名找不到，可加 `cmd /c` 包一层）。server 名保持 `sill-ensoul` 不变。
4. 校验：配置文件是合法 JSON、结构正确；说明改了什么、备份在哪。
5. 收尾：告诉我**必须完全退出 zcode 再重开**才生效；重启后会话里能调 `agent_index` / `wiki_search` 就是成功。

## 不要做

- 不要动你的 `AGENTS.md` 规则引用（薄壳只管规则，不管 MCP server 注册）。
- 不要把 token 写进任何会被 git 提交的文件。
