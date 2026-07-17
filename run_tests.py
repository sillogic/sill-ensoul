"""One-command test runner for sova.

Usage:
    python run_tests.py
"""
import subprocess
import sys


def run(name: str) -> bool:
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}\n")
    result = subprocess.run(
        [sys.executable, "-m", name],
        cwd=sys.path[0] if sys.path else ".",
    )
    return result.returncode == 0


def main() -> None:
    # 四个测试都自建临时 KB,可任意次数重复运行(见 playbook SOP-4)。
    tests = [
        "tests.test_smoke",        # OKF 纯逻辑
        "tests.test_search",       # H1/H7 检索回归(FTS5 + persona 排除)
        "tests.test_mcp_live",     # MCP 壳层(8 工具)
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
