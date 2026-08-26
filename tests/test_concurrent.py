"""并发写回归测试:ROADMAP #12 / D9 —— okf._agent_lock 跨进程互斥量。

SQLite 互斥量(_agent_lock,三平台同一份代码)的两类回归防护:

A. 确定性语义测试(所有平台有效,不依赖竞态窗口):
   1. 互斥:进程 H 持锁期间,进程 C 用短 timeout 抢锁必须得到
      sqlite3.OperationalError("database is locked"),且等待了约一个
      busy_timeout —— 证明 C 观察到了被占用的锁(而非瞬时失败);
   2. 释放:H 退出临界区后,C 同参数抢锁立即成功 —— 锁不会残留。

B. 数据不丢(并发压力;fork 平台可稳定触发丢更新,Windows 上 spawn
   启动开销天然摊开时序,弱检测,但无害):
   3. N 进程并发 append_log(读-改-写,无锁会静默丢条目) -> 一条不丢;
   4. N 进程并发写同一 concept -> 最终文件完整可解析(不撕裂);
   5. 并发写后 agent_index / search 索引同步不报 database is locked;
      .lock.db 存在 -> 证明写路径确实走了锁。

自建临时 KB,不碰真实 agent,可任意次数重复运行。

用法:  python -m tests.test_concurrent
"""
import multiprocessing
import os
import sqlite3
import sys
import tempfile
import time
import uuid

from ensoul import okf

AGENT = "concurrency-fixture"   # 隔离测试 agent,随临时 KB 一起清理
AGENT_B = "concurrency-fixture-b"  # 并发压力段用独立 agent:锁文件归属可归因
HOLD_SECS = 3.0                # 持锁时长(给争抢进程留足窗口)
SHORT_TIMEOUT = 0.5            # 争抢进程的 busy_timeout


# ---- 进程 worker(模块级,便于 spawn pickle)----

def _append_worker(args):
    kb, agent, tag = args
    os.environ["ENSOUL_KB"] = kb
    okf.append_log(agent, "concurrent-append", tag)


def _write_worker(args):
    kb, agent, tag = args
    os.environ["ENSOUL_KB"] = kb
    okf.write_concept(agent, "expertise/race", "Reference",
                      title="并发写测试", body=f"body-{tag}", tags=["test"])


def _holder_worker(args):
    """持锁 HOLD_SECS;acquire 成功后写 sentinel,便于主进程同步。"""
    kb, agent, hold = args
    os.environ["ENSOUL_KB"] = kb
    with okf._agent_lock(agent):
        (okf._agent_dir(agent) / "lock-held").write_text("1", encoding="utf-8")
        time.sleep(hold)


def _contender_worker(args):
    """用短 timeout 抢锁。返回 (是否被阻塞, 等待秒数)。"""
    kb, agent, timeout = args
    os.environ["ENSOUL_KB"] = kb
    t0 = time.time()
    try:
        with okf._agent_lock(agent, timeout=timeout):
            pass
        return (False, time.time() - t0)
    except sqlite3.OperationalError:
        return (True, time.time() - t0)


# ---- 主流程 ----

def main():
    ctx = multiprocessing.get_context("spawn")

    from ensoul import fts
    fts.reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ENSOUL_KB"] = tmp
        ok_count = 0
        fail_count = 0

        def check(label, cond):
            nonlocal ok_count, fail_count
            if cond:
                ok_count += 1
                print(f"  [OK] {label}")
            else:
                fail_count += 1
                print(f"  [FAIL] {label}")

        try:
            okf.create_agent(AGENT, name="Concurrency Fixture")

            # ---- A. 确定性:锁的互斥与释放语义 ----
            print("=" * 60)
            print("  A1) 持锁期间,另一进程抢锁必须被阻塞(OperationalError)")
            print("=" * 60)
            holder = ctx.Process(target=_holder_worker,
                                 args=((tmp, AGENT, HOLD_SECS),))
            holder.start()
            # 等 holder 确实拿到锁(sentinel 出现)
            sentinel = okf._agent_dir(AGENT) / "lock-held"
            deadline = time.time() + 15
            while not sentinel.exists() and time.time() < deadline:
                time.sleep(0.02)
            check("holder 已获取锁(sentinel 出现)", sentinel.exists())

            with ctx.Pool(1) as pool:
                blocked, waited = pool.map(
                    _contender_worker, [(tmp, AGENT, SHORT_TIMEOUT)])[0]
            check(f"抢锁被阻塞:OperationalError(waited={waited:.2f}s)",
                  blocked and 0.4 <= waited <= 2.0)

            holder.join(timeout=20)
            check("holder 正常退出", not holder.is_alive())

            print("\n" + "=" * 60)
            print("  A2) 释放后,同参数抢锁立即成功(锁不残留)")
            print("=" * 60)
            with ctx.Pool(1) as pool:
                blocked2, waited2 = pool.map(
                    _contender_worker, [(tmp, AGENT, SHORT_TIMEOUT)])[0]
            check(f"释放后抢锁成功(waited={waited2:.2f}s)",
                  not blocked2 and waited2 < 1.0)

            # ---- B. 并发压力:数据不丢(独立 agent,锁文件归属可归因) ----
            okf.create_agent(AGENT_B, name="Concurrency Fixture B")
            N = 8  # 比单机典型并发(multica max_concurrent_tasks=6)更狠
            tags = [f"proc-{i}-{uuid.uuid4().hex[:8]}" for i in range(N)]

            print("\n" + "=" * 60)
            print(f"  B3) {N} 进程并发 append_log:日志一条不丢")
            print("=" * 60)
            with ctx.Pool(N) as pool:
                pool.map(_append_worker, [(tmp, AGENT_B, t) for t in tags])
            log_text = (okf._agent_dir(AGENT_B) / "log.md").read_text(encoding="utf-8")
            found = sum(1 for t in tags if f"**concurrent-append**: {t}" in log_text)
            check(f"log.md 含全部 {N} 条并发追加(实际 {found} 条)", found == N)
            # 该 agent 此前没有任何锁活动:只有 append_log 走了锁才会创建 .lock.db
            check("append 路径确实走锁(.lock.db 已创建)",
                  (okf._agent_dir(AGENT_B) / ".lock.db").exists())

            print("\n" + "=" * 60)
            print(f"  B4) {N} 进程并发写同一 concept:最终文件完整可解析")
            print("=" * 60)
            with ctx.Pool(N) as pool:
                pool.map(_write_worker, [(tmp, AGENT_B, t) for t in tags])
            concept_path = okf._agent_dir(AGENT_B) / "expertise" / "race.md"
            fm, body = okf.parse_markdown(concept_path.read_text(encoding="utf-8"))
            check("frontmatter 合法且 type=Reference",
                  fm.get("type") == "Reference")
            check("body 是某个 writer 的完整内容(无撕裂/拼接)",
                  any(body.strip() == f"body-{t}" for t in tags))

            print("\n" + "=" * 60)
            print("  B5) 并发写后 agent_index / search 索引同步不报错")
            print("=" * 60)
            idx = okf.agent_index(AGENT_B)
            cids = [c["concept_id"] for c in idx["concepts"]]
            check("agent_index 正常返回且含新 concept", "expertise/race" in cids)
            hits = okf.search(AGENT_B, "body")
            check("search 命中并发写入的 concept",
                  any(h["concept_id"] == "expertise/race" for h in hits))

            print("\n" + "=" * 50)
            if fail_count == 0:
                print(f"  CONCURRENCY GOOD. {ok_count} checks passed.")
            else:
                print(f"  {fail_count} FAILED, {ok_count} passed.")
            print("=" * 50)
            return fail_count == 0
        finally:
            # Close cached sqlite connections BEFORE TemporaryDirectory deletes
            # index.db (Windows holds an exclusive lock while open).
            fts.reset_cache_for_tests()
            del os.environ["ENSOUL_KB"]


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
