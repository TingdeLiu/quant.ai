"""跨测试文件共享的数据/配置构造器。

非 test_*.py，pytest 不会把它当测试收集；各测试文件通过 `import _helpers` 复用。
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant_agent.config import parse_config


def _config(base: Path, csv_path: Path | None = None):
    raw = {
        "data": {
            "source": "csv",
            "csv_path": str(csv_path or base / "unused.csv"),
            "cache_dir": "cache",
            "universe": ["AAA", "BBB", "CCC", "SPY"],
        },
        "strategy": {
            "benchmark": "SPY",
            "top_n": 2,
            "rebalance_frequency": "M",
            "initial_cash": 100000,
            "transaction_cost_bps": 10,
            "slippage_bps": 5,
            "signal_weights": {
                "momentum_12_1": 1.0,
                "trend_20_50": 1.0,
                "reversal_1m": 1.0,
                "low_volatility": 1.0,
            },
        },
        "risk": {
            "max_position_weight": 0.5,
            "max_positions": 2,
            "min_avg_dollar_volume": 0,
            "max_turnover": 2.0,
            "long_only": True,
        },
        "report": {"output_dir": "reports"},
        "dashboard": {"enabled": True, "output_path": "reports/dashboard.html"},
        "evaluation": {
            "periods": [
                {"name": "train", "start": "2022-01-03", "end": "2022-06-30"},
                {"name": "validation", "start": "2022-07-01", "end": "2022-10-31"},
                {"name": "test", "start": "2022-11-01", "end": None},
            ]
        },
        "optimization": {
            "enabled": True,
            "train_period": "train",
            "validation_period": "validation",
            "objective": "sharpe",
            "max_drawdown_floor": -0.5,
            "walk_forward_enabled": True,
            "walk_forward_windows": [
                {
                    "name": "wf_1",
                    "train_start": "2022-01-03",
                    "train_end": "2022-06-30",
                    "validation_start": "2022-07-01",
                    "validation_end": "2022-10-31",
                },
                {
                    "name": "wf_2",
                    "train_start": "2022-04-01",
                    "train_end": "2022-10-31",
                    "validation_start": "2022-11-01",
                    "validation_end": None,
                },
            ],
        },
    }
    return parse_config(raw, base=base)


def _write_audit(path: Path, total_return: float, sharpe: float, test_return: float) -> Path:
    path.mkdir(parents=True)
    (path / "audit.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "total_return": total_return,
                    "sharpe": sharpe,
                    "max_drawdown": -0.1,
                    "excess_vs_equal_weight": 0.01,
                },
                "period_metrics": [
                    {
                        "period": "test",
                        "total_return": test_return,
                        "sharpe": sharpe / 2,
                        "max_drawdown": -0.05,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_equity(path: Path) -> None:
    pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=5),
            "equity": [100000, 101000, 100500, 102000, 103000],
        }
    ).to_csv(path / "equity_curve.csv", index=False)


def _synthetic_prices(periods: int = 330) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=periods)
    specs = {
        "AAA": (100.0, 0.0018),
        "BBB": (100.0, 0.0008),
        "CCC": (100.0, -0.0002),
        "SPY": (100.0, 0.0005),
    }
    rows = []
    for symbol, (start, drift) in specs.items():
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
    return pd.DataFrame(rows)


def _trending_prices(symbol: str, drift: float, periods: int = 320) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=periods)
    rows = []
    price = 100.0
    for date in dates:
        price = price * (1 + drift)
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


def _analyze_one_dict() -> dict:
    from quant_agent.analyze import _analyze_one

    return _analyze_one("DEMO", _trending_prices("DEMO", 0.0015)).to_dict()
