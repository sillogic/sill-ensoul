"""用官方 MCP 客户端 spawn sova server 并调用工具。

证明 server.py 这一壳层能独立工作（D1：只是 okf 的透传层）。
不依赖任何 CLI——纯 in-process MCP 客户端。

自建临时 KB + 通过工具写入 fixture 数据，不依赖 repo 里的预存 agent
（H4：KB 不在 repo，测试也不该依赖 repo/knowledge）。可任意次数重复运行。

用法：  python -m tests.test_mcp_live
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REPO = Path(__file__).resolve().parent.parent

# 测试用 fixture agent + concept（自给自足，不依赖任何外部数据）
FIXTURE_AGENT = "mcp-live-fixture"
FIXTURE_CONCEPT = "projects/demo"
FIXTURE_BODY = "召回用双塔模型，精排 GBDT。负采样比例 1:4 时 AUC 最高。"


async def main():
    # 临时 KB，跑完自动清理。不碰全局 KB，不依赖 repo/knowledge。
    with tempfile.TemporaryDirectory() as tmp_kb:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "sova.server"],
            cwd=str(REPO),
            env={**os.environ, "SOVA_KB": str(tmp_kb)},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("[1] MCP initialize OK")

                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                print(f"[2] tools/list OK -> {len(names)} tools")
                for n in names:
                    print(f"      - {n}")
                core = {"list_agents", "agent_index", "wiki_search", "wiki_read",
                        "wiki_write_concept", "wiki_append_log", "create_agent"}
                assert core <= set(names), f"missing: {core - set(names)}"

                async def call(tool, **args):
                    r = await session.call_tool(tool, args)
                    return json.loads(r.content[0].text)

                # 自建 fixture agent + 写一条 concept（顺带测了写工具，闭环验证）
                await call("create_agent", agent_id=FIXTURE_AGENT,
                           name="MCP Live Fixture",
                           persona="# 身份\n测试用 agent，做推荐系统。")
                await call("wiki_write_concept", agent_id=FIXTURE_AGENT,
                           concept_id=FIXTURE_CONCEPT, type="Project",
                           title="推荐系统重构", body=FIXTURE_BODY,
                           tags=["recsys"])
                await call("wiki_append_log", agent_id=FIXTURE_AGENT,
                           action="Creation",
                           detail="fixture concept for test_mcp_live")
                print(f"[3] fixture 已建: agent={FIXTURE_AGENT}, concept={FIXTURE_CONCEPT}")

                agents = await call("list_agents")
                ids = [a["agent_id"] for a in agents]
                print(f"[4] list_agents OK -> {ids}")
                assert FIXTURE_AGENT in ids

                idx = await call("agent_index", agent_id=FIXTURE_AGENT)
                preview = (idx.get("persona_preview") or "")[:40].replace("\n", " ")
                print(f"[5] agent_index OK -> persona: {preview}...")
                assert idx["concepts"], "no concepts"

                hits = await call("wiki_search", agent_id=FIXTURE_AGENT,
                                  query="推荐系统")
                print(f"[6] wiki_search OK -> {len(hits)} hit(s)")
                for h in hits[:3]:
                    print(f"      - {h['concept_id']} (score={h['score']})")
                assert hits, "search returned nothing"

                target = hits[0]["concept_id"]
                c = await call("wiki_read", agent_id=FIXTURE_AGENT,
                               concept_id=target)
                body_preview = (c.get("body") or "")[:60].replace("\n", " ")
                print(f"[7] wiki_read OK -> read '{target}', "
                      f"type={c['frontmatter'].get('type')}, body: {body_preview}...")
                assert c["frontmatter"].get("type"), "concept missing required 'type'"

                print("\nMCP LIVE GOOD. server.py works standalone (D1 holds).")


if __name__ == "__main__":
    asyncio.run(main())
