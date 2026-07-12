"""yfinance import wrapper — keep its sqlite caches usable under sandboxed hosts.

yfinance 把 cookie / 时区缓存放在用户级缓存目录（Windows 上 ``%LOCALAPPDATA%\\py-yfinance``）。
Codex app 等沙箱宿主只允许写工作区内的路径，默认缓存目录打不开时 yfinance 的每一次请求
都会抛 ``sqlite3.OperationalError: unable to open database file``，表现为实时价、机构估值
全部取不到（走 urllib 的 RSS 新闻不受影响，报告照常生成，极易误判为“没有机构覆盖”）。
这里在首次 import 时做一次真实写探测：默认目录可写就维持原状（普通环境零行为变化）；
不可写则用官方 ``set_cache_location`` 把缓存重定向到 ``./data/cache/yfinance``
（相对当前工作目录——沙箱内命令的 cwd 就是工作区写根）。
"""

from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType

_configured = False


def import_yfinance() -> ModuleType:
    """Drop-in replacement for the lazy ``import yfinance as yf`` sites (once per process)."""
    global _configured
    import yfinance as yf

    if not _configured:
        _configured = True
        _ensure_writable_cache(yf)
    return yf


def _ensure_writable_cache(yf: ModuleType) -> None:
    try:
        default_dir = Path(yf.cache._TzDBManager.get_location())
        if _dir_writable(default_dir):
            return
        fallback = Path.cwd() / "data" / "cache" / "yfinance"
        if not _dir_writable(fallback):
            return
        # 两个在用版本里 set_tz_cache_location 都是 set_cache_location 的别名（cookie/tz/isin
        # 一起重定向）；老版本没有 set_cache_location 时退回公开导出的 set_tz_cache_location。
        setter = getattr(yf.cache, "set_cache_location", None) or yf.set_tz_cache_location
        setter(str(fallback))
    except Exception:
        # 探测或重定向本身出问题就维持 yfinance 默认行为，由各取数函数的降级逻辑兜底。
        return


def _dir_writable(directory: Path) -> bool:
    """真实写一次探测文件 —— 沙箱受限令牌下 ACL 看着可写、实际写会被拒，os.access 不可信。"""
    probe = directory / f".write-probe-{os.getpid()}"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False
