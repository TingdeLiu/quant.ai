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


def test_yfinance_seeds_from_sibling_cache_and_downloads_gap(tmp_path: Path, monkeypatch) -> None:
    """Universe 变化（新缓存键）时：老标的从旧缓存播种并按 last+1 增量，新标的才走全量窗口。"""
    from _helpers import _trending_prices

    from quant_agent import data as data_mod
    from quant_agent.config import DataConfig

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    sibling = _synthetic_prices()[lambda f: f["symbol"].isin(["AAA", "SPY"])]
    sibling.to_csv(cache_dir / "prices_2_deadbeef0000.csv", index=False)
    last_aaa = pd.to_datetime(sibling["date"]).max().date()

    cfg = DataConfig(
        source="yfinance", start="2022-01-01", end=None, cache_dir=cache_dir, universe=["AAA", "NEW", "SPY"]
    )

    captured: dict = {}

    def fake_download(config, start, start_by_symbol=None):
        captured["start"] = start
        captured["by_symbol"] = start_by_symbol
        return _trending_prices("NEW", 0.001, periods=200)

    monkeypatch.setattr(data_mod, "_download_yfinance", fake_download)
    out = data_mod._load_yfinance(cfg)

    from datetime import timedelta

    assert captured["by_symbol"]["AAA"] == (last_aaa + timedelta(days=1)).isoformat()
    assert captured["by_symbol"]["NEW"] == "2022-01-01"  # 播种没有的新标的：完整窗口
    assert sorted(out["symbol"].unique()) == ["AAA", "NEW", "SPY"]
    assert len(out[out["symbol"] == "AAA"]) == 330  # 播种历史完整保留
    assert data_mod._cache_path(cfg).exists()  # 滚动库落地到新缓存键


def test_yfinance_seed_persists_when_no_new_data(tmp_path: Path, monkeypatch) -> None:
    from quant_agent import data as data_mod
    from quant_agent.config import DataConfig

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _synthetic_prices().to_csv(cache_dir / "prices_4_deadbeef0000.csv", index=False)

    cfg = DataConfig(source="yfinance", start="2022-01-01", end=None, cache_dir=cache_dir, universe=["AAA", "SPY"])
    monkeypatch.setattr(data_mod, "_download_yfinance", lambda *a, **k: pd.DataFrame())
    out = data_mod._load_yfinance(cfg)

    assert sorted(out["symbol"].unique()) == ["AAA", "SPY"]
    assert data_mod._cache_path(cfg).exists()  # 即使无新数据，播种结果也持久化


def test_download_skips_symbols_already_current(monkeypatch) -> None:
    """增量起点在未来（已最新）的标的不发起请求。"""
    from quant_agent import data as data_mod
    from quant_agent.config import DataConfig

    calls: list[str] = []

    def fake_one(yf, symbol, config, start):
        calls.append(symbol)
        return None

    monkeypatch.setattr(data_mod, "_download_one", fake_one)
    cfg = DataConfig(source="yfinance", start="2024-01-01", end=None, cache_dir=Path("."), universe=["AAA", "BBB"])
    out = data_mod._download_yfinance(cfg, "2024-01-01", {"AAA": "2999-01-01", "BBB": "2024-01-01"})
    assert calls == ["BBB"]
    assert out.empty


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
    out = data_mod._yf_download_retry(_FakeYf(), "AAPL", cfg, cfg.start, attempts=3)
    assert not out.empty
    assert calls["n"] == 3
