from __future__ import annotations

import types
from pathlib import Path

from quant_agent import yf_cache


def _fake_yf(default_dir: Path, calls: list[str]) -> types.SimpleNamespace:
    class FakeTzDBManager:
        @classmethod
        def get_location(cls) -> str:
            return str(default_dir)

    cache = types.SimpleNamespace(_TzDBManager=FakeTzDBManager, set_cache_location=calls.append)
    return types.SimpleNamespace(cache=cache)


def test_cache_redirected_when_default_unwritable(monkeypatch, tmp_path: Path) -> None:
    """沙箱场景：默认缓存目录写不了 -> 重定向到 cwd 下的 data/cache/yfinance。"""
    calls: list[str] = []
    fake = _fake_yf(tmp_path / "default", calls)
    monkeypatch.setattr(yf_cache, "_dir_writable", lambda d: "default" not in str(d))

    yf_cache._ensure_writable_cache(fake)

    assert calls == [str(Path.cwd() / "data" / "cache" / "yfinance")]


def test_cache_untouched_when_default_writable(tmp_path: Path) -> None:
    """普通环境：默认目录可写 -> 不做任何重定向（零行为变化）。"""
    calls: list[str] = []
    fake = _fake_yf(tmp_path / "default", calls)

    yf_cache._ensure_writable_cache(fake)

    assert calls == []


def test_dir_writable_probes_by_real_write(tmp_path: Path) -> None:
    # 不存在的目录会被创建后判定可写；路径被文件占位时 mkdir 失败 -> 不可写。
    assert yf_cache._dir_writable(tmp_path / "new" / "nested") is True
    blocker = tmp_path / "blocker"
    blocker.write_text("")
    assert yf_cache._dir_writable(blocker) is False
