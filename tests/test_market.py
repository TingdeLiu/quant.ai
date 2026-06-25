from __future__ import annotations

from pathlib import Path

from _helpers import _config, _synthetic_prices

from quant_agent.config import parse_config
from quant_agent.market_intel import build_market_report, render_html, render_markdown
from quant_agent.markets_data import build_markets_data
from quant_agent.recommendations import RECOMMENDATION_PROFILES


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
    report = build_market_report(config)  # English by default

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
    report = build_market_report(config)
    assert report["language"] == "zh"
    assert "不构成投资建议" in report["disclaimer"]
    assert "今日美股研究简报" in render_markdown(report)
    assert "今日美股研究简报" in render_html(report)


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
