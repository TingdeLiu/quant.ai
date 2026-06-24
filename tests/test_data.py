from __future__ import annotations

from pathlib import Path

import pandas as pd
from _helpers import _synthetic_prices

from quant_agent.config import parse_config
from quant_agent.data import load_prices, normalize_prices, validate_prices


def test_normalize_and_validate_prices() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-02"],
            "Ticker": ["aapl"],
            "Open": [100],
            "High": [101],
            "Low": [99],
            "Close": [100],
            "Adj Close": [100],
            "Volume": [1000],
        }
    )
    prices = normalize_prices(raw)
    assert prices.loc[0, "symbol"] == "AAPL"
    assert validate_prices(prices)[0]["code"] == "short_history"


def test_csv_source_accepts_generic_path(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices().to_csv(csv_path, index=False)
    config = parse_config(
        {
            "data": {
                "source": "csv",
                "path": str(csv_path),
                "universe": ["AAA", "BBB", "CCC", "SPY"],
            }
        },
        base=tmp_path,
    )
    prices = load_prices(config.data)
    assert config.data.csv_path == csv_path
    assert not prices.empty


def test_local_directory_loads_multiple_price_files_and_infers_symbol(tmp_path: Path) -> None:
    data_dir = tmp_path / "local_prices"
    data_dir.mkdir()
    prices = _synthetic_prices()
    for symbol in ["AAA", "BBB", "SPY"]:
        frame = prices[prices["symbol"] == symbol].drop(columns=["symbol"])
        frame.to_csv(data_dir / f"{symbol.lower()}.csv", index=False)

    config = parse_config(
        {
            "data": {
                "source": "local",
                "data_dir": str(data_dir),
                "universe": ["AAA", "BBB", "SPY"],
            }
        },
        base=tmp_path,
    )
    loaded = load_prices(config.data)
    assert sorted(loaded["symbol"].unique()) == ["AAA", "BBB", "SPY"]
    assert len(loaded) == 990


def test_yf_download_retry_recovers_after_transient_errors(monkeypatch) -> None:
    from quant_agent import data as data_mod
    from quant_agent.config import DataConfig

    calls = {"n": 0}

    class _FakeYf:
        def download(self, *_args, **_kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("Max retries exceeded")
            return pd.DataFrame({"Close": [1.0, 2.0]})

    monkeypatch.setattr("time.sleep", lambda *_: None)
    cfg = DataConfig(source="yfinance", start="2024-01-01", end=None, cache_dir=Path("."), universe=["AAPL"])
    out = data_mod._yf_download_retry(_FakeYf(), "AAPL", cfg, attempts=3)
    assert not out.empty
    assert calls["n"] == 3
