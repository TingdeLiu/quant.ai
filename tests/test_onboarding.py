from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from quant_agent.config import load_config
from quant_agent.onboarding import (
    UserProfile,
    build_personal_universe,
    catalog_sectors,
    discovery_count,
    load_catalog,
    read_universe_symbols,
    resolve_discovery,
    resolve_user_portion,
    write_personal_universe,
)


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "NVDA", "AMD", "JPM", "XOM", "KO", "SPY"],
            "name": ["Apple", "Microsoft", "NVIDIA", "AMD", "JPMorgan", "Exxon", "Coca-Cola", "S&P 500 ETF"],
            "sector": ["科技", "科技", "半导体", "半导体", "金融", "能源", "必需消费", "宽基ETF"],
        }
    )


def _prices(drifts: dict[str, float], periods: int = 330) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=periods)
    rows = []
    for symbol, drift in drifts.items():
        for i, date in enumerate(dates):
            price = 100.0 * ((1 + drift) ** i)
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
    return pd.DataFrame(rows)


def test_real_catalog_loads_and_has_sectors() -> None:
    catalog = load_catalog(Path("configs/catalog.csv"))
    assert not catalog.empty
    assert list(catalog.columns) == ["symbol", "name", "sector"]
    assert catalog["symbol"].is_unique
    assert len(catalog_sectors(catalog)) >= 8


def test_load_catalog_dedupes_symbols(tmp_path: Path) -> None:
    path = tmp_path / "catalog.csv"
    path.write_text("symbol,name,sector\naapl,Apple,科技\nAAPL,Dup,科技\nmsft,Microsoft,科技\n", encoding="utf-8")
    catalog = load_catalog(path)
    assert list(catalog["symbol"]) == ["AAPL", "MSFT"]


def test_resolve_user_portion_merges_tickers_and_sectors() -> None:
    catalog = _catalog()
    profile = UserProfile(sectors=["半导体"], tickers=["aapl", "MSFT"])
    portion = resolve_user_portion(profile, catalog)
    # 显式 tickers 在前，板块成员补后，去重保持顺序
    assert portion == ["AAPL", "MSFT", "NVDA", "AMD"]


def test_discovery_count_is_one_third_of_total() -> None:
    # 自选 N 只占 2/3 ⇒ 发现 round(N/2) 只 ⇒ 总量≈1.5N
    assert discovery_count(20) == 10
    assert discovery_count(2) == 1
    assert discovery_count(0) == 0


def test_resolve_discovery_picks_top_excluding_user_and_benchmark() -> None:
    catalog = _catalog()
    profile = UserProfile(tickers=["AAPL", "MSFT"], benchmark="SPY")
    user_portion = resolve_user_portion(profile, catalog)  # AAPL, MSFT
    drifts = {
        "AAPL": 0.001, "MSFT": 0.001, "NVDA": 0.004, "AMD": 0.003,
        "JPM": 0.0, "XOM": -0.001, "KO": -0.002, "SPY": 0.005,
    }
    picks, status = resolve_discovery(user_portion, catalog, profile, loader=lambda _cfg: _prices(drifts))
    assert status == "ok"
    assert picks == ["NVDA"]  # want = round(2/2) = 1, NVDA 最强，AAPL/MSFT/SPY 已剔除
    assert "SPY" not in picks and "AAPL" not in picks


def test_build_personal_universe_marks_sources() -> None:
    catalog = _catalog()
    profile = UserProfile(sectors=["半导体"], tickers=["AAPL"], benchmark="SPY")
    drifts = {"AAPL": 0.001, "MSFT": 0.0, "NVDA": 0.001, "AMD": 0.001, "JPM": 0.004, "XOM": 0.003, "KO": 0.0, "SPY": 0.0}
    frame, status = build_personal_universe(profile, catalog, loader=lambda _cfg: _prices(drifts))
    assert status == "ok"
    sources = dict(zip(frame["symbol"], frame["source"], strict=False))
    assert sources["AAPL"] == "picked"
    assert sources["NVDA"] == "sector" and sources["AMD"] == "sector"
    # 自选 3 只（AAPL+NVDA+AMD）⇒ 发现 round(3/2)=2，且不与自选重叠
    discovery = frame[frame["source"] == "discovery"]["symbol"].tolist()
    assert len(discovery) == 2
    assert not set(discovery) & {"AAPL", "NVDA", "AMD"}


def test_offline_degradation_writes_only_user_portion() -> None:
    catalog = _catalog()
    profile = UserProfile(sectors=["半导体"], tickers=["AAPL"])

    def _boom(_cfg):
        raise ConnectionError("Max retries exceeded with url")

    frame, status = build_personal_universe(profile, catalog, loader=_boom)
    assert status == "offline"
    assert set(frame["source"].unique()) <= {"picked", "sector"}
    assert "discovery" not in set(frame["source"])
    assert list(frame["symbol"]) == ["AAPL", "NVDA", "AMD"]


def test_no_discovery_skips_download() -> None:
    catalog = _catalog()
    profile = UserProfile(sectors=["半导体"])

    def _should_not_be_called(_cfg):
        raise AssertionError("enable_discovery=False 不应下载行情")

    frame, status = build_personal_universe(profile, catalog, loader=_should_not_be_called, enable_discovery=False)
    assert status == "ok"
    assert "discovery" not in set(frame["source"])


def test_write_personal_universe_outputs_parseable_config(tmp_path: Path) -> None:
    base_config = tmp_path / "base.yaml"
    base_config.write_text(
        "data:\n  source: yfinance\n  start: '2020-01-01'\n  end: null\n  cache_dir: data/cache\n"
        "  universe_path: configs/universe_default.csv\n"
        "strategy:\n  benchmark: SPY\n  top_n: 5\n  rebalance_frequency: M\n"
        "  initial_cash: 100000\n  transaction_cost_bps: 10\n  slippage_bps: 5\n"
        "  signal_weights:\n    momentum_12_1: 1.0\nrisk:\n  max_position_weight: 0.25\n"
        "  max_positions: 5\n  min_avg_dollar_volume: 0\n  max_turnover: 2.0\n  long_only: true\n"
        "report:\n  output_dir: reports/latest\n",
        encoding="utf-8",
    )
    catalog = _catalog()
    profile = UserProfile(sectors=["半导体"], tickers=["AAPL"], benchmark="QQQ")
    frame, _ = build_personal_universe(profile, catalog, enable_discovery=False)
    paths = write_personal_universe(frame, profile, tmp_path / "configs", base_config)

    assert paths["universe"].exists() and paths["config"].exists() and paths["profile"].exists()
    config = load_config(paths["config"])
    assert config.strategy.benchmark == "QQQ"
    assert config.data.universe == ["AAPL", "NVDA", "AMD"]
    # universe_path 指向生成的 my_universe.csv，而非旧 universe
    raw = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))
    assert "my_universe.csv" in raw["data"]["universe_path"]


def test_read_universe_symbols(tmp_path: Path) -> None:
    path = tmp_path / "my_universe.csv"
    path.write_text(
        "symbol,name,sector,source\nAAPL,Apple,科技,picked\nNVDA,NVIDIA,半导体,sector\nAAPL,Dup,科技,discovery\n",
        encoding="utf-8",
    )
    assert read_universe_symbols(path) == ["AAPL", "NVDA"]


def test_init_command_non_interactive_offline(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    import quant_agent.cli as cli_mod

    result = CliRunner().invoke(
        cli_mod.app,
        [
            "init",
            "--non-interactive",
            "--no-discovery",
            "--sector",
            "半导体",
            "--ticker",
            "AAPL",
            "--configs-dir",
            str(tmp_path / "configs"),
        ],
    )
    assert result.exit_code == 0, result.output
    universe_csv = tmp_path / "configs" / "my_universe.csv"
    assert universe_csv.exists()
    assert read_universe_symbols(universe_csv)[0] == "AAPL"
