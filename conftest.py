"""Pytest 根配置。

两件事：

1. 在部分受限/企业 Windows 环境下，系统临时目录里的 `pytest-of-<user>` 目录可能
   被 ACL 锁定（WinError 5 拒绝访问），导致 pytest 的 `tmp_path` fixture 在 setup
   阶段就 PermissionError。这里在会话开始前精确复现 pytest 的 basetemp 选址逻辑做一次
   探测：若该目录不可用，则把临时目录重定向到项目内的 `.pytest_tmp/`（已在 .gitignore）。
   正常环境（含 CI）下探测会通过，不产生任何副作用。

2. 强制「测试必须离线」：阻断一切到外部主机的连接（放行回环，dashboard 测试要起本地
   HTTP server）。此前这条只是约定，漏网的取数会静默走真网络 —— 表现为测试慢，且结果
   随网络环境漂移。现在漏网会当场报错，而不是等超时。
"""

from __future__ import annotations

import getpass
import os
import socket
import tempfile
from pathlib import Path

import pytest


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


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", ""}


def _is_loopback(host: object) -> bool:
    return isinstance(host, str) and host.lower() in _LOOPBACK_HOSTS


@pytest.fixture(autouse=True)
def _offline_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁止测试访问外部网络（回环除外，dashboard 测试要起本地 HTTP server）。

    离线取数（yfinance 报价/估值、RSS、个股新闻）必须在测试里注入或 monkeypatch 掉；
    真漏了就在这里当场 OSError，调用方的 `except Exception` 仍会走它本来的降级分支，
    只是不必再等网络超时。
    """
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else address
        if not _is_loopback(host):
            raise OSError(f"external network blocked in tests: {host!r}")
        return real_connect(self, address, *args, **kwargs)

    def guarded_getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not _is_loopback(host):
            raise OSError(f"external DNS blocked in tests: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
