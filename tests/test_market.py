from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from _helpers import _config, _synthetic_prices

from quant_agent.config import parse_config
from quant_agent.market_intel import (
    build_market_report,
    render_artifact_html,
    render_html,
    render_markdown,
    write_market_report,
)
from quant_agent.markets_data import build_markets_data
from quant_agent.recommendations import RECOMMENDATION_PROFILES


def _offline_raw(tmp_path: Path) -> dict:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices(periods=620).to_csv(csv_path, index=False)
    return {
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": ["AAA", "BBB", "CCC", "SPY"]},
        "strategy": {"benchmark": "SPY", "signal_weights": {"momentum_12_1": 1.0, "trend_20_50": 1.0}},
        "report": {"output_dir": str(tmp_path / "reports")},
        # No network: empty feeds and LLM disabled keep the test fully offline.
        "market_intel": {"use_llm": False, "news_feeds": [], "social_enabled": False, "request_timeout": 1},
        "portfolio": {"path": "pf.json"},
    }


def _prices_with_extra_symbol(periods: int, symbol: str, start: float, drift: float) -> pd.DataFrame:
    """``_synthetic_prices`` plus one more symbol — SPY is now a fund-tracker ETF excluded from
    the single-stock picks, so tests that need a *real* (name-mapped) ticker among the picks
    add one here instead of overloading SPY's original 4-symbol synthetic universe."""
    base = _synthetic_prices(periods=periods)
    dates = pd.bdate_range("2022-01-03", periods=periods)
    rows = []
    for i, date in enumerate(dates):
        price = start * ((1 + drift) ** i)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": price * 0.99,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "adj_close": price,
                "volume": 1_000_000,
            }
        )
    return pd.concat([base, pd.DataFrame(rows)], ignore_index=True)


def _write_portfolio(tmp_path: Path) -> None:
    (tmp_path / "pf.json").write_text(
        json.dumps(
            {
                "watchlist": ["BBB"],
                "holdings": [
                    {"symbol": "AAA", "shares": 10, "cost_basis": 100.0},
                    {"symbol": "CCC", "shares": 2},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_market_report_builds_offline(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices(periods=620).to_csv(csv_path, index=False)
    raw = {
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": ["AAA", "BBB", "CCC", "SPY"]},
        "strategy": {"benchmark": "SPY", "signal_weights": {"momentum_12_1": 1.0, "trend_20_50": 1.0}},
        "report": {"output_dir": str(tmp_path / "reports")},
        # No network: empty feeds and LLM disabled keep the test fully offline.
        "market_intel": {"use_llm": False, "news_feeds": [], "social_enabled": False, "request_timeout": 1},
    }
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})  # English by default

    assert report["data_status"] == "ok"
    assert report["as_of_date"]
    assert report["language"] == "en"
    assert set(RECOMMENDATION_PROFILES).issuperset(report["quant_candidates"].keys())
    assert report["news"] == []  # no feeds configured
    assert "not investment advice" in report["disclaimer"]
    # Renderers must not raise on the structured payload.
    assert "Daily US Equity Research Brief" in render_markdown(report)
    assert "<html" in render_html(report)


def test_market_report_chinese(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices(periods=620).to_csv(csv_path, index=False)
    raw = {
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": ["AAA", "BBB", "CCC", "SPY"]},
        "strategy": {"benchmark": "SPY", "signal_weights": {"momentum_12_1": 1.0, "trend_20_50": 1.0}},
        "market_intel": {"use_llm": False, "news_feeds": [], "social_enabled": False, "request_timeout": 1},
        "language": "zh",
    }
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})
    assert report["language"] == "zh"
    assert "不构成投资建议" in report["disclaimer"]
    assert "今日美股研究简报" in render_markdown(report)
    assert "今日美股研究简报" in render_html(report)


def test_market_report_includes_holdings(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    fetched: list[list[str]] = []

    def fake_quotes(symbols: list[str]) -> dict[str, float]:
        fetched.append(symbols)
        return {}

    report = build_market_report(config, quote_fetcher=fake_quotes, target_fetcher=lambda symbols: {})

    assert fetched == [["AAA", "CCC"]]  # 只对持仓标的取实时价
    holdings = report["holdings"]
    assert holdings["quotes_source"] == "last_close"
    by_symbol = {p["symbol"]: p for p in holdings["positions"]}
    assert by_symbol["AAA"]["unrealized_pnl"] is not None
    assert by_symbol["CCC"]["unrealized_pnl"] is None  # 未提供成本 → 不算盈亏
    assert holdings["totals"]["market_value"] is not None

    markdown = render_markdown(report)
    assert "My holdings" in markdown
    assert "| AAA |" in markdown
    assert "Total" in markdown
    # 持仓段位于市场概览之前。
    assert markdown.index("My holdings") < markdown.index("Market overview")


def test_market_report_holdings_chinese(tmp_path: Path) -> None:
    raw = {**_offline_raw(tmp_path), "language": "zh"}
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})
    markdown = render_markdown(report)
    assert "我的持仓" in markdown
    assert "合计" in markdown


def test_market_report_without_portfolio_has_no_holdings(tmp_path: Path) -> None:
    config = parse_config(_offline_raw(tmp_path), base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})
    assert "holdings" not in report
    assert "My holdings" not in render_markdown(report)
    # 无持仓时 artifact 第一个 section 是市场概览，编号从 01 开始。
    artifact = render_artifact_html(report)
    assert "My holdings" not in artifact
    assert '<span class="sec-num">01</span><h2>Market overview</h2>' in artifact


def test_holdings_section_first_in_html(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})

    html = render_html(report)
    artifact = render_artifact_html(report)
    for rendered in (html, artifact):
        assert rendered.index("My holdings") < rendered.index("Market overview")
    # 持仓段占用 01 号，概览顺延为 02。
    assert '<span class="sec-num">01</span><h2>My holdings</h2>' in artifact
    assert '<span class="sec-num">02</span><h2>Market overview</h2>' in artifact


def test_render_artifact_html_self_contained(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})
    artifact = render_artifact_html(report)

    # 片段形态：无文档包装、零外部资源（artifact 的严格 CSP 下必须可渲染）。
    assert "<html" not in artifact
    assert "<head>" not in artifact and "<body" not in artifact and "<!doctype" not in artifact.lower()
    assert "fonts.googleapis" not in artifact
    assert "<link" not in artifact
    # 明暗双主题钩子齐备。
    assert 'class="qa-report"' in artifact
    assert "prefers-color-scheme: dark" in artifact
    assert 'data-theme="dark"' in artifact
    assert 'data-theme="light"' in artifact
    # 整页版保持完整文档 + 网络字体。
    html = render_html(report)
    assert html.startswith("<!doctype html>")
    assert "fonts.googleapis" in html


def test_write_market_report_writes_artifact(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})
    paths = write_market_report(report, tmp_path / "reports")

    assert set(paths) == {"json", "markdown", "html", "artifact"}
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0
    assert paths["artifact"].name == "market_intel_artifact.html"


def test_pick_cards_pin_holding_and_show_valuation_range(tmp_path: Path) -> None:
    # SPY 现在是固定基金追踪 ETF，会被排除出个股类候选榜单，所以另加一只真实代码（MU）
    # 来验证"命中中文名映射表"这条路径。
    csv_path = tmp_path / "prices.csv"
    _prices_with_extra_symbol(periods=620, symbol="MU", start=100.0, drift=0.001).to_csv(csv_path, index=False)
    raw = {
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": ["AAA", "BBB", "CCC", "SPY", "MU"]},
        "strategy": {"benchmark": "SPY", "signal_weights": {"momentum_12_1": 1.0, "trend_20_50": 1.0}},
        "market_intel": {"use_llm": False, "news_feeds": [], "social_enabled": False, "request_timeout": 1},
        "portfolio": {"path": "pf.json"},
        "language": "zh",
    }
    (tmp_path / "pf.json").write_text(  # 只持仓 AAA，避免和 _write_portfolio 的 CCC 混在一起
        json.dumps({"holdings": [{"symbol": "AAA", "shares": 10, "cost_basis": 100.0}]}), encoding="utf-8"
    )
    config = parse_config(raw, base=tmp_path)
    fake_targets = {"AAA": {"low": 80.0, "target": 130.0, "high": 180.0}}
    report = build_market_report(
        config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: fake_targets
    )

    for data in report["quant_candidates"].values():
        symbols = data["symbols"]
        assert "SPY" not in {s["symbol"] for s in symbols}  # 基金追踪 ETF 不进个股候选榜单
        assert symbols[0]["symbol"] == "AAA"  # 持仓标的置顶（榜首 = 01）
        assert symbols[0]["holding"]["shares"] == 10.0
        by_symbol = {s["symbol"]: s for s in symbols}
        assert by_symbol["AAA"]["valuation"] == fake_targets["AAA"]
        assert by_symbol["AAA"]["name_zh"] is None  # 假代码不在中文名映射表里
        assert by_symbol["MU"]["name_zh"] == "美光科技"
        assert by_symbol["MU"]["valuation"] is None  # 无估值数据 -> 卡片降级为"暂无覆盖"占位
        assert by_symbol["MU"]["day_change_pct"] is not None

    artifact = render_artifact_html(report)
    assert 'class="pick is-holding"' in artifact
    assert "range-zero" in artifact  # AAA 卡片：目标价居中的估值偏离条
    assert "暂无机构估值覆盖" in artifact  # MU 无估值数据 -> 占位文案，不是误导性的条
    assert '<span class="name-zh">美光科技</span>' in artifact
    assert "12-1动量" not in artifact and "20/50趋势" not in artifact  # z-score 依据已被替换
    assert "当日" in artifact  # 改为显示当日涨跌值/幅度

    # 部分标的取到估值（AAA 有、MU 没有）属于正常降级，不应触发整体取数失败警告。
    assert not any(w.startswith("analyst_targets_unavailable") for w in report["warnings"])


def test_all_targets_missing_adds_fetch_failure_warning(tmp_path: Path) -> None:
    """入选标的一只估值都没取到时（典型原因是 yfinance 取数环节挂了），报告必须带警告，
    避免满屏“暂无机构估值覆盖”被误读为机构真的没有覆盖。"""
    config = parse_config(_offline_raw(tmp_path), base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})

    assert report["quant_candidates"]  # 前提：确实有入选标的
    warnings = [w for w in report["warnings"] if w.startswith("analyst_targets_unavailable")]
    assert len(warnings) == 1
    assert warnings[0] in render_markdown(report)


def test_fund_tracker_section(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)  # universe: AAA/BBB/CCC/SPY
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})

    symbols = {f["symbol"] for f in report["fund_trackers"]}
    assert symbols == {"SPY"}  # 只有 SPY 有合成价格数据，QQQ/SMH/AIQ 无数据时静默跳过
    assert report["fund_trackers"][0]["day_change_pct"] is not None

    markdown = render_markdown(report)
    assert "Fund & index tracker" in markdown
    html = render_html(report)
    assert "Fund &amp; index tracker" in html
    assert 'class="tile fund"' in html


def test_high_risk_section_flags_near_high(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})

    assert "High risk" in render_markdown(report)
    html = render_html(report)
    assert "High risk" in html
    for item in report["high_risk"]:
        assert "dist_from_high_pct" in item and "ret_21d_pct" in item
        assert "name_zh" in item


def test_potential_picks_renamed_and_show_chinese_names(tmp_path: Path) -> None:
    # SPY 现在是基金追踪 ETF，会被排除出「潜力股」榜单，另加一只真实代码（MU）验证中文名。
    csv_path = tmp_path / "prices.csv"
    _prices_with_extra_symbol(periods=620, symbol="MU", start=100.0, drift=0.001).to_csv(csv_path, index=False)
    raw = {
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": ["AAA", "BBB", "CCC", "SPY", "MU"]},
        "strategy": {"benchmark": "SPY", "signal_weights": {"momentum_12_1": 1.0, "trend_20_50": 1.0}},
        "market_intel": {"use_llm": False, "news_feeds": [], "social_enabled": False, "request_timeout": 1},
        "language": "zh",
    }
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})

    markdown = render_markdown(report)
    assert "潜力股" in markdown
    assert "相对值得关注" not in markdown
    by_symbol = {c["symbol"]: c for c in report["buy_candidates"]}
    assert "SPY" not in by_symbol  # 基金追踪 ETF 不进「潜力股」榜单
    assert by_symbol["MU"]["name_zh"] == "美光科技"
    assert "美光科技" in render_html(report)


def test_holdings_table_has_sparkline(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})

    position = report["holdings"]["positions"][0]
    assert len(position["spark"]) > 1

    artifact = render_artifact_html(report)
    assert 'class="spark-cell"' in artifact
    assert "<svg" in artifact and "polyline" in artifact


def test_markets_data_builds_offline(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices(periods=620).to_csv(csv_path, index=False)
    config = _config(tmp_path, csv_path)
    data = build_markets_data(config)

    assert data["TICKERS"], "expected at least one ticker"
    assert data["defaultSym"] in data["TICKERS"]
    # Every watchlist symbol must be a clickable (known) ticker.
    for w in data["WATCH"]:
        assert w["sym"] in data["TICKERS"]
        assert w["sym"] in data["PRICE"]
    sample = data["TICKERS"][data["defaultSym"]]
    assert sample["rating"] in {"Bullish", "Neutral", "Volatile", "Cautious"}
    assert len(sample["bull"]) >= 1 and len(sample["bear"]) >= 1
    assert {"1M return", "Ann. vol", "52-wk range", "Signal"}.issubset(sample["stats"].keys())
    assert "investment advice" in sample["summary"].lower()


def test_collect_feeds_concurrent_keeps_order_retry_and_errors(monkeypatch) -> None:
    from quant_agent import market_intel

    calls: list[str] = []

    def fake_fetch(url: str, limit: int, timeout: int) -> list[dict]:
        calls.append(url)
        if "bad" in url:
            raise OSError("connection refused")
        idx = 1 if "one" in url else 2
        return [{"title": f"t{idx}", "link": f"https://n/{idx}", "published": "", "summary": "", "published_ts": float(idx)}]

    monkeypatch.setattr(market_intel, "_fetch_rss", fake_fetch)
    feeds = [
        {"name": "One", "url": "https://one"},
        {"name": "Bad", "url": "https://bad"},
        {"name": "Two", "url": "https://two"},
    ]
    items, errors = market_intel._collect_feeds(feeds, max_items=10, timeout=1)

    assert [i["source"] for i in items] == ["Two", "One"]  # newest first by published_ts
    assert all("published_ts" not in i for i in items)  # internal sort key must not leak
    assert errors == ["feed_failed:Bad: connection refused"]
    assert calls.count("https://bad") == 2  # failed feed gets exactly one retry


def test_collect_feeds_caps_total_items(monkeypatch) -> None:
    from quant_agent import market_intel

    def fake_fetch(url: str, limit: int, timeout: int) -> list[dict]:
        return [
            {"title": f"{url}-{i}", "link": url, "published": "", "summary": "", "published_ts": float(i)}
            for i in range(limit)
        ]

    monkeypatch.setattr(market_intel, "_fetch_rss", fake_fetch)
    feeds = [{"name": f"F{i}", "url": f"https://f{i}"} for i in range(4)]
    items, errors = market_intel._collect_feeds(feeds, max_items=5, timeout=1)
    assert errors == []
    assert len(items) == 5


def test_collect_symbol_news_concurrent_keeps_input_order(monkeypatch) -> None:
    from quant_agent import market_intel

    class _FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        @property
        def news(self) -> list[dict]:
            if self.symbol == "BAD":
                raise ValueError("boom")
            return [
                {"title": f"{self.symbol} headline {i}", "link": f"https://n/{self.symbol}/{i}", "publisher": "Wire"}
                for i in range(5)
            ]

    class _FakeYF:
        Ticker = _FakeTicker

    monkeypatch.setattr(market_intel, "import_yfinance", lambda: _FakeYF)
    out = market_intel._collect_symbol_news(["CCC", "BAD", "AAA"], symbol_count=3, per_symbol=2, timeout=1)

    assert list(out) == ["CCC", "AAA"]  # 输入顺序保留；失败标的静默跳过
    assert all(len(v) == 2 for v in out.values())  # per_symbol 截断
    assert out["AAA"][0]["title"] == "AAA headline 0"

    capped = market_intel._collect_symbol_news(["CCC", "AAA", "BBB"], symbol_count=1, per_symbol=2, timeout=1)
    assert list(capped) == ["CCC"]  # symbol_count 截断


def test_detail_charts_windows_and_downsampling(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})

    charts = report["detail_charts"]
    assert charts, "expected per-symbol detail chart series"
    assert "AAA" in charts  # 持仓标的必有走势数据
    windows = charts["AAA"]
    # 620 个交易日：1W/1M/6M/1Y 完整，5Y 覆盖全部历史后停止（无更长的重复窗口）
    assert list(windows) == ["1W", "1M", "6M", "1Y", "5Y"]
    for w in windows.values():
        assert len(w["points"]) >= 2
        assert len(w["points"]) <= 100  # 降采样上限
        assert w["chg_pct"] is not None
        assert w["low"] <= w["high"]
        assert w["start"] <= w["end"]
    assert len(windows["1W"]["points"]) == 6  # 5 个交易日 + 起点，不足上限时不采样


def test_detail_charts_skip_duplicate_long_windows(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices(periods=100).to_csv(csv_path, index=False)  # 仅 100 天历史
    raw = {
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": ["AAA", "BBB", "CCC", "SPY"]},
        "strategy": {"benchmark": "SPY", "signal_weights": {"momentum_12_1": 1.0, "trend_20_50": 1.0}},
        "market_intel": {"use_llm": False, "news_feeds": [], "social_enabled": False, "request_timeout": 1},
    }
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, target_fetcher=lambda symbols: {})
    for windows in report["detail_charts"].values():
        # 6M(126) 已覆盖全部 100 天历史 -> 1Y/5Y 不再生成同一条曲线
        assert list(windows) == ["1W", "1M", "6M"]


def test_report_html_has_expandable_detail_panels(tmp_path: Path) -> None:
    raw = _offline_raw(tmp_path)
    _write_portfolio(tmp_path)
    config = parse_config(raw, base=tmp_path)
    report = build_market_report(config, quote_fetcher=lambda symbols: {}, target_fetcher=lambda symbols: {})

    artifact = render_artifact_html(report)
    # 表格行展开：checkbox 开关 + 隐藏详情行；卡片展开：details/summary。
    assert 'class="row-toggle"' in artifact
    assert 'class="detail-row"' in artifact
    assert '<details class="dp-details">' in artifact
    # 时间段切换：radio 分组 + tab 标签 + 每窗口一块图面板。
    assert 'class="dp-radio"' in artifact and 'class="dp-tab"' in artifact
    assert artifact.count('class="dp-pane"') >= 5
    assert 'class="dp-svg"' in artifact and "polyline" in artifact
    # radio 分组名必须全文档唯一（同一标的可出现在多个栏目）。
    assert 'name="dp-1"' in artifact and 'name="dp-2"' in artifact
    # 纯 CSS 交互：artifact 片段必须保持零 JS。
    assert "<script" not in artifact
    # 整页版同样带详情面板。
    assert 'class="dp-radio"' in render_html(report)
