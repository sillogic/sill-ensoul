"""搜索回归测试:防 H1(FTS5 检索)/H7(persona 排除)退化。

自建隔离的临时 agent,写多条 concept,验证检索行为,跑完清理。
不依赖真实 algo-engineer 数据,可任意次数重复运行。

用法:  python -m tests.test_search
"""
import shutil
import tempfile

from ensoul import okf, fts

AGENT = "search-regression-fixture"  # 临时 agent,跑完删除


def setup_agent(kb_root):
    """写 3 条 concept + persona,测检索与 persona 排除。"""
    ag = kb_root / "agents" / AGENT
    ag.mkdir(parents=True, exist_ok=True)
    # persona —— 含"推荐"字样,用于验证它不污染搜索(H7)
    (ag / "AGENT.md").write_text(
        "---\ntype: Profile\ntitle: 测试 Agent\n---\n# 身份\n我做推荐系统。\n",
        encoding="utf-8")
    okf.write_concept(AGENT, "projects/demo-project", "Project",
                      title="推荐系统重构", body="召回用双塔模型,精排 GBDT。负采样比例 1:4。",
                      tags=["demo-project"])
    okf.write_concept(AGENT, "projects/nlp", "Project",
                      title="NLP 文本分类",
                      body="用 BERT 做情感分类,数据增强提升召回。",
                      tags=["nlp", "bert"])
    okf.write_concept(AGENT, "expertise/overfitting", "Reference",
                      title="过拟合防治",
                      body="Dropout 加早停加正则化三件套。rank 越大越容易过拟合。",
                      tags=["training"])
    # 注意:demo-project 文档故意不含"过拟合",避免与 overfitting 文档构成平局干扰断言


def main():
    fts.reset_cache_for_tests()
    # 临时 KB,完全隔离
    with tempfile.TemporaryDirectory() as tmp:
        import os
        os.environ["ENSOUL_KB"] = tmp
        kb = okf.kb_root()
        try:
            setup_agent(kb)
            fts.reset_cache_for_tests()  # 新 KB 要重置连接缓存

            ok_count = 0
            fail_count = 0

            def check(label, cond):
                nonlocal ok_count, fail_count
                if cond:
                    ok_count += 1
                    print(f"  ✅ {label}")
                else:
                    fail_count += 1
                    print(f"  ❌ {label}")

            print("=" * 60)
            print("  H7: persona 不进 concept 清单 / 不进搜索")
            print("=" * 60)
            idx = okf.agent_index(AGENT)
            cids = [c["concept_id"] for c in idx["concepts"]]
            check("concept 清单无 AGENT", "AGENT" not in cids)
            check("concept 清单含 3 条", len(cids) == 3)
            # persona 含"推荐",但搜"推荐"不应被 persona 污染到异常位置
            hits = okf.search(AGENT, "推荐")
            check("搜'推荐'有结果", len(hits) > 0)
            check("搜'推荐'结果里无 persona", all(h["concept_id"] != "AGENT" for h in hits))

            print("\n" + "=" * 60)
            print("  H1: FTS5 检索精准命中")
            print("=" * 60)
            # 精确场景
            def top(q):
                h = okf.search(AGENT, q)
                return h[0]["concept_id"] if h else None
            check("搜'双塔' -> projects/demo-project", top("双塔") == "projects/demo-project")
            check("搜'BERT' -> projects/nlp", top("BERT") == "projects/nlp")
            check("搜'过拟合' -> expertise/overfitting",
                  top("过拟合") == "expertise/overfitting")
            check("搜'推荐系统' -> projects/demo-project",
                  top("推荐系统") == "projects/demo-project")
            # 无关查询返回空
            check("搜'量子计算' -> 空", okf.search(AGENT, "量子计算") == [])
            # 英文前缀匹配
            check("搜'rank' -> overfitting(含rank)",
                  top("rank") == "expertise/overfitting")

            print("\n" + "=" * 60)
            print("  H1: 增量索引一致(写后立刻可搜)")
            print("=" * 60)
            okf.write_concept(AGENT, "projects/new", "Project",
                              title="新增项目", body="刚写入的 unique-token-xyz",
                              tags=["new"])
            fts.reset_cache_for_tests()  # 新进程模拟
            h = okf.search(AGENT, "unique-token-xyz")
            check("写后立即搜得到", len(h) == 1 and h[0]["concept_id"] == "projects/new")

            print("\n" + "=" * 50)
            if fail_count == 0:
                print(f"  SEARCH GOOD. {ok_count} checks passed.")
            else:
                print(f"  {fail_count} FAILED, {ok_count} passed.")
            print("=" * 50)
            return fail_count == 0
        finally:
            # Close cached sqlite connections BEFORE TemporaryDirectory tries
            # to delete index.db (Windows holds an exclusive lock while open).
            fts.reset_cache_for_tests()
            del os.environ["ENSOUL_KB"]


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
