from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from quant_agent.agents import ResearchReviewAgent
from quant_agent.alerts import build_alerts, write_alerts
from quant_agent.backtest import run_backtest
from quant_agent.config import AppConfig
from quant_agent.dashboard import write_dashboard
from quant_agent.data import load_prices
from quant_agent.data_quality import build_data_quality_report, write_data_quality_report
from quant_agent.features import SIGNAL_COLUMNS, build_signals
from quant_agent.ml import apply_ml_ranking_signal
from quant_agent.notifications import build_notifications, dispatch_notifications
from quant_agent.optimization import optimize_signal_weights
from quant_agent.paper import build_paper_order_plan, write_paper_order_plan
from quant_agent.portfolio import build_target_positions
from quant_agent.recommendations import build_recommendations
from quant_agent.reports import write_report
from quant_agent.risk import check_targets, risk_passed


def run_research_backtest(config: AppConfig) -> dict[str, object]:
    prices = load_prices(config.data)
    data_quality = build_data_quality_report(prices, config.data.universe)
    signals = build_signals(prices, config.strategy.signal_weights)
    signals, ml_diagnostics = apply_ml_ranking_signal(signals, config)
    targets = build_target_positions(signals, config.strategy, config.risk)
    risk_checks = check_targets(targets, config.risk)
    if not risk_passed(risk_checks):
        raise ValueError(f"Risk checks failed: {risk_checks}")
    result = run_backtest(prices, targets, config.strategy, config.evaluation.periods)
    result["signal_diagnostics"] = _signal_diagnostics(prices, signals, config)
    result.update(optimize_signal_weights(prices, signals, config))
    recommendations, recommendation_payload = build_recommendations(signals, prices, targets, config)
    result["recommendations"] = recommendations
    result["recommendations_payload"] = recommendation_payload
    result["data_quality"] = data_quality
    result["ml_diagnostics"] = ml_diagnostics
    if config.ml.enabled:
        generated_at = datetime.now(UTC).isoformat()
        feature_columns = [
            "date",
            "symbol",
            "momentum_12_1_z",
            "trend_20_50_z",
            "reversal_1m_z",
            "low_volatility_z",
            "ret_1d",
            "volatility_20",
        ]
        result["ml_feature_matrix"] = signals[[column for column in feature_columns if column in signals.columns]].copy()
        prediction_columns = ["date", "symbol", "ml_rank", "ml_rank_z"]
        predictions = signals[[column for column in prediction_columns if column in signals.columns]].dropna(
            subset=["ml_rank"],
            how="all",
        )
        predictions = predictions.copy()
        predictions["model_version"] = config.ml.model_version
        predictions["feature_version"] = config.ml.feature_version
        predictions["generated_at"] = generated_at
        result["ml_predictions"] = predictions
    review, review_metadata = ResearchReviewAgent().review_with_metadata(
        result["metrics"],
        risk_checks,
        config.llm,
        context={"ml": ml_diagnostics, "data_quality": data_quality.get("summary", {})},
    )
    result["review_metadata"] = review_metadata
    if config.paper_trading.enabled:
        paper_plan = build_paper_order_plan(targets, prices, config.paper_trading)
        result["paper_order_plan"] = paper_plan
        write_paper_order_plan(paper_plan, config.paper_trading.output_dir)
    alerts = build_alerts(result, risk_checks, config.alerts)
    result["alerts"] = alerts
    notifications = build_notifications(
        alerts,
        config.notifications,
        run_id=_run_id_from_report_dir(config.report.output_dir),
        report_dir=config.report.output_dir,
    )
    notifications = dispatch_notifications(notifications, config.notifications, config.report.output_dir)
    result["notifications"] = notifications
    write_report(config.report.output_dir, config, result, risk_checks, review)
    write_data_quality_report(data_quality, config.report.output_dir)
    write_alerts(alerts, config.report.output_dir)
    if config.dashboard.enabled:
        write_dashboard(config.report.output_dir, config.dashboard.output_path, config.language)
    return {"prices": prices, "signals": signals, "targets": targets, "risk_checks": risk_checks, **result}


def _run_id_from_report_dir(output_dir) -> str | None:
    path = output_dir
    if path.parent.name == "runs":
        return path.name
    return None


def _signal_diagnostics(prices: pd.DataFrame, signals: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for signal in SIGNAL_COLUMNS:
        diagnostic_signals = signals.copy()
        diagnostic_signals["score"] = diagnostic_signals[f"{signal}_z"]
        targets = build_target_positions(diagnostic_signals, config.strategy, config.risk)
        checks = check_targets(targets, config.risk)
        passed = risk_passed(checks)
        row: dict[str, object] = {
            "signal": signal,
            "risk_passed": passed,
            "target_count": len(targets),
        }
        if passed and not targets.empty:
            result = run_backtest(prices, targets, config.strategy, config.evaluation.periods)
            row.update(
                {
                    "total_return": result["metrics"].get("total_return", 0.0),
                    "cagr": result["metrics"].get("cagr", 0.0),
                    "sharpe": result["metrics"].get("sharpe", 0.0),
                    "max_drawdown": result["metrics"].get("max_drawdown", 0.0),
                    "excess_vs_equal_weight": result["metrics"].get("excess_vs_equal_weight", 0.0),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)
