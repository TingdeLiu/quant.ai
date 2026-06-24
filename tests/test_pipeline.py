from __future__ import annotations

from pathlib import Path

import pandas as pd
from _helpers import _config, _synthetic_prices

from quant_agent.config import parse_config
from quant_agent.data_quality import build_data_quality_report
from quant_agent.features import build_signals
from quant_agent.metrics import calculate_metrics
from quant_agent.ml import apply_ml_ranking_signal
from quant_agent.paper import build_paper_order_plan
from quant_agent.pipeline import run_research_backtest
from quant_agent.portfolio import build_target_positions
from quant_agent.recommendations import RECOMMENDATION_PROFILES, build_recommendations
from quant_agent.risk import check_targets, risk_passed


def test_signals_are_lagged_and_backtestable() -> None:
    prices = _synthetic_prices()
    signals = build_signals(prices)
    momentum_only = build_signals(prices, {"momentum_12_1": 1.0})
    matured = signals.dropna(subset=["score"])
    assert not matured.empty
    first_signal_date = matured["date"].min()
    assert first_signal_date > prices["date"].min()
    assert {"reversal_1m", "low_volatility", "reversal_1m_z", "low_volatility_z"}.issubset(signals.columns)
    comparable = signals["score"].notna() & momentum_only["score"].notna()
    assert not signals.loc[comparable, "score"].equals(momentum_only.loc[comparable, "score"])


def test_targets_satisfy_risk_limits() -> None:
    prices = _synthetic_prices()
    signals = build_signals(prices)
    config = _config(Path("."))
    targets = build_target_positions(signals, config.strategy, config.risk)
    checks = check_targets(targets, config.risk)
    assert not targets.empty
    assert risk_passed(checks)
    assert targets["target_weight"].max() <= config.risk.max_position_weight


def test_full_pipeline_writes_expected_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    _synthetic_prices().to_csv(csv_path, index=False)
    config = _config(tmp_path, csv_path=csv_path)
    result = run_research_backtest(config)
    assert result["metrics"]["total_return"] != 0
    assert (tmp_path / "reports" / "summary.md").exists()
    assert (tmp_path / "reports" / "audit.json").exists()
    assert (tmp_path / "reports" / "trades.csv").exists()
    assert (tmp_path / "reports" / "period_metrics.csv").exists()
    assert (tmp_path / "reports" / "equal_weight_equity.csv").exists()
    assert (tmp_path / "reports" / "exposure_by_symbol.csv").exists()
    assert (tmp_path / "reports" / "signal_diagnostics.csv").exists()
    assert (tmp_path / "reports" / "signal_weight_search.csv").exists()
    assert (tmp_path / "reports" / "recommended_signal_weights.json").exists()
    assert (tmp_path / "reports" / "recommended_equity_curve.csv").exists()
    assert (tmp_path / "reports" / "recommended_period_metrics.csv").exists()
    assert (tmp_path / "reports" / "walk_forward_signal_search.csv").exists()
    assert (tmp_path / "reports" / "walk_forward_stability.csv").exists()
    assert (tmp_path / "reports" / "walk_forward_recommended_signal_weights.json").exists()
    assert (tmp_path / "reports" / "walk_forward_recommended_equity_curve.csv").exists()
    assert (tmp_path / "reports" / "walk_forward_recommended_period_metrics.csv").exists()
    assert (tmp_path / "reports" / "alerts.json").exists()
    assert (tmp_path / "reports" / "alerts.csv").exists()
    assert (tmp_path / "reports" / "notifications.json").exists()
    assert (tmp_path / "reports" / "recommendations.csv").exists()
    assert (tmp_path / "reports" / "recommendations.json").exists()
    assert (tmp_path / "reports" / "recommendations_long_term.csv").exists()
    assert not result["period_metrics"].empty
    assert not result["exposure"].empty
    assert not result["signal_diagnostics"].empty
    assert not result["signal_weight_search"].empty
    assert result["recommended_signal_weights"]
    assert not result["recommended_period_metrics"].empty
    assert result["recommended_metrics"]
    assert not result["walk_forward_signal_search"].empty
    assert not result["walk_forward_stability"].empty
    assert result["walk_forward_recommended_signal_weights"]
    assert not result["walk_forward_recommended_period_metrics"].empty
    assert result["walk_forward_recommended_metrics"]
    assert not result["recommendations"].empty
    assert "equal_weight_total_return" in result["metrics"]
    assert "excess_vs_equal_weight" in result["metrics"]
    dashboard = (tmp_path / "reports" / "dashboard.html").read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in dashboard
    assert "setLanguage('zh')" in dashboard
    assert "研究买入候选" in dashboard


def test_data_quality_reports_metadata_columns() -> None:
    prices = _synthetic_prices()
    prices["as_of_date"] = prices["date"]
    prices["split_coefficient"] = 1.0
    report = build_data_quality_report(prices, ["AAA", "BBB", "MISSING", "SPY"])
    assert report["summary"]["point_in_time_ready"]
    assert report["summary"]["corporate_actions_present"]
    assert report["summary"]["missing_universe_symbols"] == ["MISSING"]


def test_ml_ranking_signal_can_score_when_enabled(tmp_path: Path) -> None:
    prices = _synthetic_prices(periods=620)
    config = _config(tmp_path)
    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["AAA", "BBB", "CCC", "SPY"]},
            "strategy": config.strategy.__dict__,
            "risk": config.risk.__dict__,
            "evaluation": {
                "periods": [
                    {"name": "train", "start": "2022-01-03", "end": "2023-06-30"},
                    {"name": "validation", "start": "2023-07-01", "end": "2023-12-31"},
                ]
            },
            "ml": {"enabled": True, "train_period": "train", "prediction_horizon_days": 21},
        },
        base=tmp_path,
    )
    signals = build_signals(prices, config.strategy.signal_weights)
    scored, diagnostics = apply_ml_ranking_signal(signals, config)
    assert diagnostics["status"] == "trained"
    assert "ml_rank_z" in scored.columns
    assert scored["ml_rank_z"].notna().any()


def test_paper_order_plan_generates_proposed_orders(tmp_path: Path) -> None:
    prices = _synthetic_prices()
    config = _config(tmp_path)
    signals = build_signals(prices)
    targets = build_target_positions(signals, config.strategy, config.risk)
    plan = build_paper_order_plan(targets, prices, config.paper_trading)
    assert "orders" in plan
    assert not plan["orders"].empty
    assert "checks" in plan


def test_recommendations_generate_multiple_horizons(tmp_path: Path) -> None:
    prices = _synthetic_prices()
    config = _config(tmp_path)
    signals = build_signals(prices, config.strategy.signal_weights)
    targets = build_target_positions(signals, config.strategy, config.risk)
    recommendations, payload = build_recommendations(signals, prices, targets, config, per_profile=3)

    assert set(recommendations["recommendation_type"]) == set(RECOMMENDATION_PROFILES)
    assert recommendations.groupby("recommendation_type")["rank"].max().eq(3).all()
    assert {"symbol", "confidence", "risk_level", "reason", "latest_price", "data_date"}.issubset(
        recommendations.columns
    )
    assert recommendations["suggested_action"].eq("research_buy_candidate").all()
    assert "not investment advice" in payload["disclaimer"]


def test_metrics_include_benchmark_relative_values() -> None:
    dates = pd.bdate_range("2024-01-02", periods=30)
    equity = pd.DataFrame({"date": dates, "equity": [100 * (1.002**i) for i in range(len(dates))]})
    benchmark = pd.DataFrame({"date": dates, "equity": [100 * (1.001**i) for i in range(len(dates))]})
    metrics = calculate_metrics(equity, benchmark)
    assert metrics["sortino"] >= 0
    assert metrics["calmar"] >= 0
    assert "beta" in metrics
    assert "alpha" in metrics
    assert "information_ratio" in metrics
