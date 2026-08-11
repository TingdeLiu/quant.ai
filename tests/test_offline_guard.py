"""验证 conftest 的离线护栏本身有效。

护栏一旦静默失效，"离线测试"就会重新变成"悄悄走真网络"—— 慢，且结果随网络环境漂移。
这里只确认护栏这一层：外部主机被挡、回环放行。取数模块遇错后的降级分支由
`test_market.py::test_collect_feeds_concurrent_keeps_order_retry_and_errors` 覆盖
（那里 monkeypatch `_fetch_rss` 抛错，不必真发请求）。
"""

from __future__ import annotations

import socket

import pytest


def test_external_dns_and_connect_are_blocked() -> None:
    with pytest.raises(OSError, match="external DNS blocked"):
        socket.getaddrinfo("query1.finance.yahoo.com", 443)
    with pytest.raises(OSError, match="external network blocked"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("93.184.216.34", 80))


def test_loopback_still_allowed() -> None:
    # dashboard 测试要起本地 HTTP server，回环必须放行。
    assert socket.getaddrinfo("127.0.0.1", 0)
    assert socket.getaddrinfo("localhost", 0)
