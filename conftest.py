"""Pytest 根配置。

在部分受限/企业 Windows 环境下，系统临时目录里的 `pytest-of-<user>` 目录可能
被 ACL 锁定（WinError 5 拒绝访问），导致 pytest 的 `tmp_path` fixture 在 setup
阶段就 PermissionError。这里在会话开始前精确复现 pytest 的 basetemp 选址逻辑做一次
探测：若该目录不可用，则把临时目录重定向到项目内的 `.pytest_tmp/`（已在 .gitignore）。

正常环境（含 CI）下探测会通过，本文件不产生任何副作用。
"""

from __future__ import annotations

import getpass
import os
import tempfile
from pathlib import Path


def _pytest_basetemp_is_usable() -> bool:
    """复刻 pytest 的 basetemp 选址（<tmp>/pytest-of-<user>）并验证可写。"""
    try:
        user = getpass.getuser() or "unknown"
    except Exception:
        user = "unknown"
    candidate = Path(tempfile.gettempdir()) / f"pytest-of-{user}"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write_probe"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def _ensure_writable_tmpdir() -> None:
    if _pytest_basetemp_is_usable():
        return
    fallback = Path(__file__).parent / ".pytest_tmp"
    fallback.mkdir(exist_ok=True)
    resolved = str(fallback.resolve())
    for var in ("TMPDIR", "TEMP", "TMP"):
        os.environ[var] = resolved
    tempfile.tempdir = resolved


_ensure_writable_tmpdir()
