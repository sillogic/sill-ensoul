"""One-command test runner for sill-ensoul.

Usage:
    python -m tests.run_tests      # from repo root (preferred)
    python tests/run_tests.py      # also works
"""
import subprocess
import sys
from pathlib import Path

# Repo root = parent of this tests/ directory. Tests are imported as
# `tests.test_*`, so cwd must be the repo root regardless of how the
# runner is invoked.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def run(name: str) -> bool:
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}\n")
    result = subprocess.run(
        [sys.executable, "-m", name],
        cwd=_REPO_ROOT,
    )
    return result.returncode == 0


def main() -> None:
    # 三个发布测试都自建临时 KB,可任意次数重复运行(见 playbook SOP-4)。
    # test_smoke 不纳入:它依赖维护者全局 KB 里的真实 algo-engineer,
    # 新用户 clone 后没有该 agent 会挂;它对维护者仍有价值,单独跑即可。
    tests = [
        "tests.test_search",         # H1/H7 检索回归(FTS5 + persona 排除)
        "tests.test_mcp_live",       # MCP 壳层(8 工具)
        "tests.test_cross_project",  # 跨项目记忆端到端
    ]
    ok = True
    for t in tests:
        ok = run(t) and ok
    print("\n" + "=" * 50)
    if ok:
        print("  ALL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED")
    print("=" * 50)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
