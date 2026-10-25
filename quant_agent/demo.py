"""An isolated, deterministic demo: synthetic prices, no external services."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from quant_agent import holdings as holdings_store
from quant_agent.i18n import normalize_language
from quant_agent.market_intel import FUND_TRACKERS, SECTOR_ETFS


def prepare_demo(root: Path, language: str = "en") -> Path:
    """Create demo-only files; preserve any portfolio edits from a previous demo."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "prices.csv"
    symbols = list(dict.fromkeys(["AAPL", "MSFT", "NVDA", *[s["symbol"] for s in FUND_TRACKERS + SECTOR_ETFS]]))
    if not csv_path.exists():
        dates = pd.bdate_range("2023-01-03", periods=620)
        steps = np.arange(len(dates))
        frames = []
        for index, symbol in enumerate(symbols):
            close = (80 + index * 11) * np.exp((0.0002 + (index % 5) * 0.0001) * steps)
            close *= 1 + 0.035 * np.sin(steps / (13 + index % 7) + index) + 0.015 * np.cos(steps / 5 + index)
            frames.append(pd.DataFrame({
                "date": dates, "symbol": symbol, "open": close * 0.997,
                "high": close * 1.012, "low": close * 0.988,
                "close": close, "adj_close": close, "volume": 2_000_000,
            }))
        pd.concat(frames, ignore_index=True).to_csv(csv_path, index=False)
    portfolio_path = root / "portfolio.json"
    if not portfolio_path.exists():
        portfolio = holdings_store.load_portfolio(portfolio_path)
        holdings_store.add_watchlist_symbols(portfolio, ["NVDA", "MSFT"])
        holdings_store.upsert_holdings(portfolio, [{"symbol": "AAPL", "shares": 10, "cost_basis": 85}])
        holdings_store.save_portfolio(portfolio, portfolio_path)
    raw = {
        "language": normalize_language(language),
        "data": {"source": "csv", "csv_path": str(csv_path), "universe": symbols, "cache_dir": str(root / "cache")},
        "portfolio": {"path": str(portfolio_path)},
        "strategy": {"benchmark": "SPY", "top_n": 5},
        "report": {"output_dir": str(root / "reports")},
        "market_intel": {"news_feeds": [], "social_enabled": False, "symbol_news_count": 0},
        "dashboard": {"service_dir": str(root / "service"), "runs_dir": str(root / "runs")},
        "dashboard_security": {"audit_log_path": str(root / "service" / "audit.jsonl")},
        "optimization": {"enabled": False, "walk_forward_enabled": False},
        "schedule": {"enabled": False},
    }
    config_path = root / "demo.yaml"
    config_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return config_path
