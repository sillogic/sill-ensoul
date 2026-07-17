"""端到端:模拟"在 A 项目激活 Agent → 更新记忆 → 换到 B 项目唤醒 → 验证记忆还在"。

完全自动,不污染真实 agent 数据:用临时 KB + 隔离的测试 agent (qa-tester),
跑完自动清理。走真实 MCP server(stdio),所以连壳层一起验证。

不依赖 repo/knowledge(H4:KB 不在 repo),用 tempfile 建临时 KB + 临时项目目录,
可任意次数重复运行。

场景脚本:
  [A 项目] 唤醒 qa-tester → 它一开始对某主题一无所知
  [A 项目] 你(脚本)让它"记一条经验" → wiki_write_concept + wiki_append_log
  [B 项目] 换了 cwd(模拟换项目)→ 唤醒同一个 qa-tester
  [B 项目] wiki_search 该主题 → 命中 → wiki_read 读出细节
  → 证明记忆跨项目留存

用法:  python -m tests.test_cross_project
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parent.parent
AGENT = "qa-tester"  # 隔离的测试 agent,跑完随临时 KB 一起清理,绝不碰真实 agent


def _server_params(kb: str, cwd: str):
    """同一个临时 KB(SOVA_KB 不变),只改 cwd —— 模拟换项目目录。
    PYTHONPATH 指向 repo,这样 server 从任意 cwd 启动都能 import sova
    (暴露了 H9:server 不应依赖 cwd,需 PYTHONPATH/打包才能跨项目用)。"""
    env = {**os.environ,
           "SOVA_KB": kb,
           "PYTHONPATH": str(REPO)}
    return StdioServerParameters(
        command=sys.executable, args=["-m", "sova.server"],
        cwd=cwd, env=env,
    )


async def _tools(session):
    async def call(tool, **args):
        r = await session.call_tool(tool, args)
        return json.loads(r.content[0].text)
    return call


async def main():
    # 临时 KB + 临时项目目录,跑完一起清理。不碰全局 KB,不碰 repo。
    with tempfile.TemporaryDirectory() as tmp_kb, \
         tempfile.TemporaryDirectory() as proj_a, \
         tempfile.TemporaryDirectory() as proj_b:
        try:
            # ============ [A 项目] 激活一个全新的 Agent ============
            print("=" * 60)
            print("  [A 项目] cwd = 一个临时项目目录")
            print("=" * 60)

            async with stdio_client(_server_params(tmp_kb, proj_a)) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    call = await _tools(s)

                    # 唤醒:agent_index 对一个空 agent 也安全(返回空 persona/concepts)
                    idx = await call("agent_index", agent_id=AGENT)
                    print(f"[A1] 唤醒 {AGENT} -> "
                          f"已有 concept 数: {len(idx['concepts'])}  (预期 0,全新 agent)")

                    # 先搜:对"flaky test 根因"应该一无所知
                    hits_before = await call("wiki_search", agent_id=AGENT,
                                             query="flaky test 根因")
                    print(f"[A2] 搜索 'flaky test 根因' -> "
                          f"{len(hits_before)} 条命中  (预期 0,还没学过)")

                    # —— 这就是"如何让 Agent 更新记忆":显式调用写工具 ——
                    print("\n[A3] >>> 对话式指令:『把这条经验记进 wiki』")
                    print("     (对应调用 wiki_write_concept + wiki_append_log)")
                    written = await call(
                        "wiki_write_concept",
                        agent_id=AGENT,
                        concept_id="expertise/flaky-tests",
                        type="Reference",
                        title="Flaky 测试根因集",
                        description="跨项目沉淀的 flaky test 诊断经验",
                        body=(
                            "# Flaky 测试根因\n\n"
                            "## 1. 隐式时序依赖\n"
                            "测试间共享可变状态、未 reset fixture,导致按不同顺序跑结果不同。\n"
                            "**解法**:每个 test 强制独立的 setup/teardown,禁用共享全局态。\n\n"
                            "## 2. 异步竞态\n"
                            "用 sleep 等待而非事件/条件,在慢 CI 上必 flaky。\n"
                            "**解法**:把 sleep 换成显式 await 事件或轮询收敛断言。\n"
                        ),
                        tags=["testing", "flaky", "ci"],
                    )
                    print(f"     已写入 concept: {written['concept_id']}  "
                          f"type={written['frontmatter']['type']}")

                    log = await call("wiki_append_log", agent_id=AGENT,
                                     action="Creation",
                                     detail="新建 expertise/flaky-tests:flaky test 根因集")
                    print(f"     已记 log: {log['entry']}")

            # ============ [B 项目] 换了目录,唤醒同一个 Agent ============
            print("\n" + "=" * 60)
            print("  [B 项目] cwd 换成另一个目录 —— 模拟换项目")
            print("=" * 60)
            # 两次 stdio 连接之间给前一个进程彻底退出的时间(Windows 上 client
            # 管道关闭有延迟,立刻开第二个会在 initialize 时 Connection closed)。
            await asyncio.sleep(1.5)

            async with stdio_client(_server_params(tmp_kb, proj_b)) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    call = await _tools(s)

                    # 注意:cwd 变了,但 SOVA_KB(临时 KB)没变 -> 记忆是角色作用域
                    idx = await call("agent_index", agent_id=AGENT)
                    print(f"[B1] 在 B 项目唤醒 {AGENT} -> "
                          f"已有 concept 数: {len(idx['concepts'])}  (预期 1,带着 A 项目的经验)")

                    hits = await call("wiki_search", agent_id=AGENT,
                                      query="flaky test 根因")
                    print(f"[B2] 搜索 'flaky test 根因' -> "
                          f"{len(hits)} 条命中  (预期 1)")
                    for h in hits:
                        print(f"      - {h['concept_id']} (score={h['score']}) "
                              f"| {h['title']}")

                    assert hits, "❌ 记忆没跨项目留存!"
                    top = hits[0]["concept_id"]
                    c = await call("wiki_read", agent_id=AGENT, concept_id=top)
                    body = c["body"]
                    print(f"\n[B3] 读出 '{top}' 内容片段:")
                    for line in body.splitlines()[:6]:
                        print(f"      {line}")
                    # 关键断言:A 项目写的具体经验,B 项目能读到
                    assert "sleep" in body and "竞态" in body, "❌ 经验细节丢失"
                    print("\n[B4] ✅ 验证通过:在 A 项目学到的经验,B 项目能检索并读出。")

            print("\n" + "=" * 60)
            print("  CROSS-PROJECT GOOD. 记忆是角色作用域,跨项目留存。")
            print("  (临时 KB 和项目目录已自动清理)")
            print("=" * 60)

        except Exception:
            # TemporaryDirectory 会自动清理,这里只重新抛出
            raise


if __name__ == "__main__":
    asyncio.run(main())
