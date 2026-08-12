"""MCP 工具层测试：直接 await 工具协程（FastMCP 装饰器返回原函数），全程离线。

Config 注入方式：yaml 放在 tmp_path/configs/ 下 —— load_config 对名为 configs 的
父目录取 base=tmp_path，yaml 内所有相对路径（价格 csv、报告目录、portfolio）都落在 tmp。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from _helpers import _synthetic_prices

from quant_agent import mcp_server
from quant_agent.mcp_server import (
    ConfigInput,
    HoldingsInput,
    PositionInput,
    WatchlistInput,
    quant_generate_market_report,
    quant_manage_holdings,
    quant_manage_watchlist,
)


def _write_config(tmp_path: Path) -> str:
    _synthetic_prices(periods=620).to_csv(tmp_path / "prices.csv", index=False)
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_path = config_dir / "test.yaml"
    config_path.write_text(
        "\n".join(
            [
                "data:",
                "  source: csv",
                "  csv_path: prices.csv",
                "  cache_dir: cache",
                "  universe: [AAA, BBB, CCC, SPY]",
                "strategy:",
                "  benchmark: SPY",
                "  signal_weights: {momentum_12_1: 1.0, trend_20_50: 1.0}",
                "report:",
                "  output_dir: reports",
                "market_intel:",
                "  news_feeds: []",
                "  social_enabled: false",
                # 个股新闻走 yfinance 网络，不受 news_feeds=[] 约束 —— 置 0 才是真离线。
                "  symbol_news_count: 0",
                "  request_timeout: 1",
                "portfolio:",
                "  path: pf.json",
            ]
        ),
        encoding="utf-8",
    )
    return str(config_path)


def test_tools_are_directly_awaitable() -> None:
    # FastMCP 的 @mcp.tool() 返回原协程函数；这里锁定该行为，测试才能直调。
    assert asyncio.iscoroutinefunction(quant_manage_watchlist)
    assert asyncio.iscoroutinefunction(quant_manage_holdings)


def test_watchlist_add_list_remove_roundtrip(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)

    result = asyncio.run(quant_manage_watchlist(WatchlistInput(config=cfg, action="add", symbols=["nvda", "tsla"])))
    assert result["watchlist"] == ["NVDA", "TSLA"]
    assert (tmp_path / "pf.json").exists()

    result = asyncio.run(quant_manage_watchlist(WatchlistInput(config=cfg)))
    assert result["action"] == "list"
    assert result["watchlist"] == ["NVDA", "TSLA"]

    result = asyncio.run(quant_manage_watchlist(WatchlistInput(config=cfg, action="remove", symbols=["NVDA"])))
    assert result["watchlist"] == ["TSLA"]

    result = asyncio.run(quant_manage_watchlist(WatchlistInput(config=cfg, action="add")))
    assert "error" in result  # add 必须带 symbols


def test_load_merges_portfolio_into_universe(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    asyncio.run(quant_manage_watchlist(WatchlistInput(config=cfg, action="add", symbols=["ZZZ"])))
    config = mcp_server._load(cfg)
    assert config.data.universe == ["AAA", "BBB", "CCC", "SPY", "ZZZ"]


def test_holdings_set_list_remove(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_config(tmp_path)
    monkeypatch.setattr("quant_agent.holdings.fetch_live_quotes", lambda symbols: {})

    result = asyncio.run(
        quant_manage_holdings(
            HoldingsInput(
                config=cfg,
                action="set",
                positions=[PositionInput(symbol="aaa", shares=10, cost_basis=100.0)],
            )
        )
    )
    assert result["holdings"] == [{"symbol": "AAA", "shares": 10.0, "cost_basis": 100.0, "note": None}]

    result = asyncio.run(quant_manage_holdings(HoldingsInput(config=cfg)))
    assert result["action"] == "list"
    assert result["quotes_source"] == "last_close"
    position = result["positions"][0]
    assert position["symbol"] == "AAA"
    assert position["unrealized_pnl"] is not None  # 盈亏来自合成 csv 的收盘价
    assert result["totals"]["market_value"] is not None

    # set 缺 shares → 错误提示而非落盘。
    result = asyncio.run(
        quant_manage_holdings(HoldingsInput(config=cfg, action="set", positions=[PositionInput(symbol="BBB")]))
    )
    assert "error" in result

    result = asyncio.run(
        quant_manage_holdings(HoldingsInput(config=cfg, action="remove", positions=[PositionInput(symbol="AAA")]))
    )
    assert result["holdings"] == []

    result = asyncio.run(quant_manage_holdings(HoldingsInput(config=cfg)))
    assert result["positions"] == []  # 空持仓的 list 即时返回，不触发取数


def test_report_tool_returns_artifact_path(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_config(tmp_path)
    monkeypatch.setattr("quant_agent.holdings.fetch_live_quotes", lambda symbols: {})
    # MCP 工具内部不注入 fetcher，估值走真实 yfinance —— 不挡住测试就会联网等超时。
    monkeypatch.setattr("quant_agent.market_intel.fetch_analyst_price_targets", lambda symbols: {})
    # 自选 + 持仓都进报告：持仓触发盈亏段，自选并入 universe（AAA 已有价格数据）。
    (tmp_path / "pf.json").write_text(
        json.dumps({"watchlist": ["BBB"], "holdings": [{"symbol": "AAA", "shares": 5, "cost_basis": 90.0}]}),
        encoding="utf-8",
    )

    result = asyncio.run(quant_generate_market_report(ConfigInput(config=cfg)))

    assert result["display"] == "html_artifact"
    artifact = Path(result["artifact_html_path"])
    assert artifact.exists() and artifact.name == "market_intel_artifact.html"
    assert "My holdings" in artifact.read_text(encoding="utf-8")
    assert result["holdings"]["positions"][0]["symbol"] == "AAA"
    assert "report_markdown" in result  # Markdown 兜底仍在
    # 四份报告文件都写出。
    for name in ["market_intel.json", "market_intel.md", "market_intel.html", "market_intel_artifact.html"]:
        assert (tmp_path / "reports" / name).exists()
