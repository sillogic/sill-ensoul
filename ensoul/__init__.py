"""ensoul: OKF-backed long-term memory for agents, exposed via MCP."""

# 版本号只有一个权威来源：pyproject.toml（打包元数据）。
# 以前这里硬编码 "0.1.0" 而 pyproject 已经是 0.5.0，两处长期不一致（SILL-415 收尾）；
# 现在从已安装的包元数据读，源码树里未安装时回退到下面的 _FALLBACK_VERSION。
# 换版本 = 只改 pyproject.toml 一处。
_FALLBACK_VERSION = "0.5.0"


def _resolve_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("sill-ensoul")
        except PackageNotFoundError:
            return _FALLBACK_VERSION
    except Exception:  # pragma: no cover - 元数据层异常不该拖垮 import
        return _FALLBACK_VERSION


__version__ = _resolve_version()
