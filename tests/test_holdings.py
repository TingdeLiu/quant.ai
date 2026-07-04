from __future__ import annotations

import json
from pathlib import Path

import pytest
from _helpers import _synthetic_prices

from quant_agent.config import parse_config
from quant_agent.holdings import (
    add_watchlist_symbols,
    apply_portfolio_universe,
    build_holdings_snapshot,
    load_portfolio,
    portfolio_symbols,
    remove_holdings,
    remove_watchlist_symbols,
    save_portfolio,
    upsert_holdings,
)


def _config(tmp_path: Path, universe: list[str] | None = None):
    return parse_config(
        {
            "data": {
                "source": "csv",
                "csv_path": str(tmp_path / "prices.csv"),
                "cache_dir": "cache",
                "universe": universe or ["AAA", "SPY"],
            },
            "portfolio": {"path": "pf.json"},
        },
        base=tmp_path,
    )


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    portfolio = load_portfolio(tmp_path / "nope.json")
    assert portfolio == {"version": 1, "watchlist": [], "holdings": [], "updated_at": None}


def test_save_load_roundtrip_atomic(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "pf.json"
    portfolio = load_portfolio(path)
    add_watchlist_symbols(portfolio, ["nvda"])
    upsert_holdings(portfolio, [{"symbol": "aapl", "shares": 15, "cost_basis": 182.5, "note": "long"}])
    save_portfolio(portfolio, path)

    assert not path.with_name(path.name + ".tmp").exists()
    reloaded = load_portfolio(path)
    assert reloaded["version"] == 1
    assert reloaded["watchlist"] == ["NVDA"]
    assert reloaded["holdings"] == [{"symbol": "AAPL", "shares": 15.0, "cost_basis": 182.5, "note": "long"}]
    assert "T" in reloaded["updated_at"]  # ISO timestamp was stamped by save


def test_load_corrupt_raises_and_keeps_file(tmp_path: Path) -> None:
    path = tmp_path / "pf.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="pf.json"):
        load_portfolio(path)
    assert path.read_text(encoding="utf-8") == "{not json"

    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        load_portfolio(path)


def test_load_normalizes_entries(tmp_path: Path) -> None:
    path = tmp_path / "pf.json"
    path.write_text(
        json.dumps(
            {
                "watchlist": [" nvda ", "NVDA", "tsla"],
                "holdings": [
                    {"symbol": "aapl", "shares": 5, "cost_basis": -3},
                    {"symbol": "aapl", "shares": 10, "cost_basis": "bad"},
                    {"symbol": "msft", "shares": 0},
                    {"symbol": "", "shares": 9},
                    "garbage",
                ],
            }
        ),
        encoding="utf-8",
    )
    portfolio = load_portfolio(path)
    assert portfolio["watchlist"] == ["NVDA", "TSLA"]
    # AAPL：后一条覆盖前一条（last wins），非法 cost_basis 宽容为 None；无效行全部丢弃。
    assert portfolio["holdings"] == [{"symbol": "AAPL", "shares": 10.0, "cost_basis": None, "note": None}]


def test_watchlist_add_remove(tmp_path: Path) -> None:
    portfolio = load_portfolio(tmp_path / "pf.json")
    add_watchlist_symbols(portfolio, ["nvda", " NVDA ", "tsla"])
    assert portfolio["watchlist"] == ["NVDA", "TSLA"]
    add_watchlist_symbols(portfolio, ["nvda"])  # re-add is a no-op
    assert portfolio["watchlist"] == ["NVDA", "TSLA"]
    remove_watchlist_symbols(portfolio, ["nvda "])
    assert portfolio["watchlist"] == ["TSLA"]


def test_upsert_and_remove_holdings() -> None:
    portfolio = {"watchlist": [], "holdings": []}
    upsert_holdings(portfolio, [{"symbol": "aapl", "shares": 10, "cost_basis": 100}])
    upsert_holdings(portfolio, [{"symbol": "msft", "shares": 2}])
    upsert_holdings(portfolio, [{"symbol": "AAPL", "shares": 12, "cost_basis": 110, "note": "added"}])
    assert portfolio["holdings"] == [
        {"symbol": "AAPL", "shares": 12.0, "cost_basis": 110.0, "note": "added"},
        {"symbol": "MSFT", "shares": 2.0, "cost_basis": None, "note": None},
    ]
    with pytest.raises(ValueError, match="shares"):
        upsert_holdings(portfolio, [{"symbol": "NVDA"}])
    with pytest.raises(ValueError, match="shares"):
        upsert_holdings(portfolio, [{"symbol": "NVDA", "shares": 0}])
    with pytest.raises(ValueError, match="cost_basis"):
        upsert_holdings(portfolio, [{"symbol": "NVDA", "shares": 1, "cost_basis": 0}])
    remove_holdings(portfolio, ["aapl"])
    assert [h["symbol"] for h in portfolio["holdings"]] == ["MSFT"]


def test_portfolio_symbols_order() -> None:
    portfolio = {"watchlist": ["NVDA", "AAPL"], "holdings": [{"symbol": "TSLA"}, {"symbol": "AAPL"}]}
    assert portfolio_symbols(portfolio) == ["NVDA", "AAPL", "TSLA"]


def test_apply_portfolio_universe(tmp_path: Path) -> None:
    config = _config(tmp_path)

    # 无文件 → 恒等（同一对象，零成本）。
    assert apply_portfolio_universe(config) is config

    portfolio = load_portfolio(config.portfolio_path)
    add_watchlist_symbols(portfolio, ["ZZZ"])
    upsert_holdings(portfolio, [{"symbol": "AAA", "shares": 1}])  # 已在 universe
    save_portfolio(portfolio, config.portfolio_path)

    merged = apply_portfolio_universe(config)
    assert merged.data.universe == ["AAA", "SPY", "ZZZ"]
    assert config.data.universe == ["AAA", "SPY"]  # 原 config 不可变

    # 全部已覆盖 → 恒等。
    only_known = _config(tmp_path, universe=["AAA", "ZZZ", "SPY"])
    assert apply_portfolio_universe(only_known) is only_known

    # 损坏文件 → 读路径打不死，原样返回。
    config.portfolio_path.write_text("{broken", encoding="utf-8")
    assert apply_portfolio_universe(config) is config


def test_snapshot_math_from_last_close() -> None:
    prices = _synthetic_prices()
    aaa = prices[prices["symbol"] == "AAA"].sort_values("date")["adj_close"]
    last, prev = float(aaa.iloc[-1]), float(aaa.iloc[-2])
    portfolio = {
        "watchlist": [],
        "holdings": [
            {"symbol": "AAA", "shares": 10.0, "cost_basis": 100.0, "note": None},
            {"symbol": "BBB", "shares": 2.0, "cost_basis": None, "note": None},
            {"symbol": "UNK", "shares": 1.0, "cost_basis": 5.0, "note": None},
        ],
    }
    snapshot = build_holdings_snapshot(portfolio, prices)
    assert snapshot["quotes_source"] == "last_close"
    by_symbol = {p["symbol"]: p for p in snapshot["positions"]}

    aaa_pos = by_symbol["AAA"]
    assert aaa_pos["price"] == pytest.approx(last, rel=1e-4)
    assert aaa_pos["price_source"] == "last_close"
    assert aaa_pos["day_change_pct"] == pytest.approx((last / prev - 1) * 100, abs=0.01)
    assert aaa_pos["market_value"] == pytest.approx(10 * last, abs=0.01)
    assert aaa_pos["unrealized_pnl"] == pytest.approx(10 * last - 1000, abs=0.01)
    assert aaa_pos["unrealized_pnl_pct"] == pytest.approx((last / 100 - 1) * 100, abs=0.01)

    bbb_pos = by_symbol["BBB"]
    assert bbb_pos["market_value"] is not None
    assert bbb_pos["cost_value"] is None
    assert bbb_pos["unrealized_pnl"] is None

    unk_pos = by_symbol["UNK"]
    assert unk_pos["price"] is None
    assert unk_pos["market_value"] is None
    assert unk_pos["price_source"] is None

    totals = snapshot["totals"]
    assert totals["positions"] == 3
    # 盈亏合计只配对「现价+成本都齐」的 AAA；市值合计含 AAA+BBB。
    assert totals["cost_value"] == pytest.approx(1000, abs=0.01)
    assert totals["unrealized_pnl"] == pytest.approx(10 * last - 1000, abs=0.01)
    assert totals["market_value"] == pytest.approx(aaa_pos["market_value"] + bbb_pos["market_value"], abs=0.01)


def test_snapshot_with_live_quotes() -> None:
    prices = _synthetic_prices()
    aaa = prices[prices["symbol"] == "AAA"].sort_values("date")["adj_close"]
    last = float(aaa.iloc[-1])
    portfolio = {
        "watchlist": [],
        "holdings": [
            {"symbol": "AAA", "shares": 10.0, "cost_basis": 100.0, "note": None},
            {"symbol": "BBB", "shares": 2.0, "cost_basis": None, "note": None},
        ],
    }
    snapshot = build_holdings_snapshot(portfolio, prices, quotes={"AAA": 123.0})
    assert snapshot["quotes_source"] == "mixed"  # AAA realtime + BBB last_close
    aaa_pos = next(p for p in snapshot["positions"] if p["symbol"] == "AAA")
    assert aaa_pos["price"] == 123.0
    assert aaa_pos["price_source"] == "realtime"
    assert aaa_pos["day_change_pct"] == pytest.approx((123.0 / last - 1) * 100, abs=0.01)

    only_aaa = {"watchlist": [], "holdings": [portfolio["holdings"][0]]}
    assert build_holdings_snapshot(only_aaa, prices, quotes={"AAA": 123.0})["quotes_source"] == "realtime"


def test_snapshot_without_prices() -> None:
    portfolio = {"watchlist": [], "holdings": [{"symbol": "AAA", "shares": 3.0, "cost_basis": 100.0, "note": None}]}
    snapshot = build_holdings_snapshot(portfolio, None, quotes={"AAA": 110.0})
    position = snapshot["positions"][0]
    assert position["price"] == 110.0
    assert position["day_change_pct"] is None  # 无历史无从计算当日
    assert position["unrealized_pnl"] == pytest.approx(30.0, abs=0.01)
    assert snapshot["totals"]["market_value"] == pytest.approx(330.0, abs=0.01)
