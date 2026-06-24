from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import AppConfig
from quant_agent.recommendations import RECOMMENDATION_PROFILES, write_recommendations


def write_report(
    output_dir: Path,
    config: AppConfig,
    result: dict[str, Any],
    risk_checks: list[dict[str, object]],
    review_markdown: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result["equity_curve"].to_csv(output_dir / "equity_curve.csv", index=False)
    result["positions"].to_csv(output_dir / "positions.csv", index=False)
    result["trades"].to_csv(output_dir / "trades.csv", index=False)
    if isinstance(result.get("exposure"), pd.DataFrame):
        result["exposure"].to_csv(output_dir / "exposure_by_symbol.csv", index=False)
    if isinstance(result.get("signal_diagnostics"), pd.DataFrame):
        result["signal_diagnostics"].to_csv(output_dir / "signal_diagnostics.csv", index=False)
    if isinstance(result.get("signal_weight_search"), pd.DataFrame):
        result["signal_weight_search"].to_csv(output_dir / "signal_weight_search.csv", index=False)
    if isinstance(result.get("recommended_signal_weights"), dict):
        (output_dir / "recommended_signal_weights.json").write_text(
            json.dumps(result["recommended_signal_weights"], indent=2),
            encoding="utf-8",
        )
    if isinstance(result.get("walk_forward_recommended_signal_weights"), dict):
        (output_dir / "walk_forward_recommended_signal_weights.json").write_text(
            json.dumps(result["walk_forward_recommended_signal_weights"], indent=2),
            encoding="utf-8",
        )
    if isinstance(result.get("recommended_equity_curve"), pd.DataFrame) and not result["recommended_equity_curve"].empty:
        result["recommended_equity_curve"].to_csv(output_dir / "recommended_equity_curve.csv", index=False)
    if isinstance(result.get("recommended_positions"), pd.DataFrame) and not result["recommended_positions"].empty:
        result["recommended_positions"].to_csv(output_dir / "recommended_positions.csv", index=False)
    if isinstance(result.get("recommended_trades"), pd.DataFrame) and not result["recommended_trades"].empty:
        result["recommended_trades"].to_csv(output_dir / "recommended_trades.csv", index=False)
    if isinstance(result.get("recommended_period_metrics"), pd.DataFrame) and not result["recommended_period_metrics"].empty:
        result["recommended_period_metrics"].to_csv(output_dir / "recommended_period_metrics.csv", index=False)
    if isinstance(result.get("walk_forward_signal_search"), pd.DataFrame):
        result["walk_forward_signal_search"].to_csv(output_dir / "walk_forward_signal_search.csv", index=False)
    if isinstance(result.get("walk_forward_stability"), pd.DataFrame):
        result["walk_forward_stability"].to_csv(output_dir / "walk_forward_stability.csv", index=False)
    if (
        isinstance(result.get("walk_forward_recommended_equity_curve"), pd.DataFrame)
        and not result["walk_forward_recommended_equity_curve"].empty
    ):
        result["walk_forward_recommended_equity_curve"].to_csv(
            output_dir / "walk_forward_recommended_equity_curve.csv",
            index=False,
        )
    if (
        isinstance(result.get("walk_forward_recommended_period_metrics"), pd.DataFrame)
        and not result["walk_forward_recommended_period_metrics"].empty
    ):
        result["walk_forward_recommended_period_metrics"].to_csv(
            output_dir / "walk_forward_recommended_period_metrics.csv",
            index=False,
        )
    if (
        isinstance(result.get("walk_forward_recommended_positions"), pd.DataFrame)
        and not result["walk_forward_recommended_positions"].empty
    ):
        result["walk_forward_recommended_positions"].to_csv(output_dir / "walk_forward_recommended_positions.csv", index=False)
    if (
        isinstance(result.get("walk_forward_recommended_trades"), pd.DataFrame)
        and not result["walk_forward_recommended_trades"].empty
    ):
        result["walk_forward_recommended_trades"].to_csv(output_dir / "walk_forward_recommended_trades.csv", index=False)
    if isinstance(result.get("period_metrics"), pd.DataFrame) and not result["period_metrics"].empty:
        result["period_metrics"].to_csv(output_dir / "period_metrics.csv", index=False)
    if isinstance(result.get("benchmark_equity"), pd.DataFrame):
        result["benchmark_equity"].to_csv(output_dir / "benchmark_equity.csv", index=False)
    if isinstance(result.get("equal_weight_equity"), pd.DataFrame):
        result["equal_weight_equity"].to_csv(output_dir / "equal_weight_equity.csv", index=False)
    if isinstance(result.get("paper_order_plan"), dict):
        paper_orders = result["paper_order_plan"].get("orders")
        if isinstance(paper_orders, pd.DataFrame):
            paper_orders.to_csv(output_dir / "proposed_orders.csv", index=False)
        paper_audit = {key: value for key, value in result["paper_order_plan"].items() if key != "orders"}
        (output_dir / "paper_trading_audit.json").write_text(
            json.dumps(paper_audit, indent=2, default=str),
            encoding="utf-8",
        )
    if isinstance(result.get("ml_feature_matrix"), pd.DataFrame):
        result["ml_feature_matrix"].to_csv(output_dir / "ml_feature_matrix.csv", index=False)
    if isinstance(result.get("ml_predictions"), pd.DataFrame):
        result["ml_predictions"].to_csv(output_dir / "ml_predictions.csv", index=False)
    if isinstance(result.get("ml_diagnostics"), dict) and result["ml_diagnostics"]:
        (output_dir / "ml_diagnostics.json").write_text(
            json.dumps(result["ml_diagnostics"], indent=2, default=str),
            encoding="utf-8",
        )
    if isinstance(result.get("recommendations"), pd.DataFrame):
        write_recommendations(
            result["recommendations"],
            result.get("recommendations_payload", {}),
            output_dir,
        )
    outputs = [
        "summary.md",
        "equity_curve.csv",
        "positions.csv",
        "trades.csv",
        "audit.json",
        "exposure_by_symbol.csv",
        "signal_diagnostics.csv",
        "signal_weight_search.csv",
        "recommended_signal_weights.json",
        "walk_forward_signal_search.csv",
        "walk_forward_stability.csv",
        "walk_forward_recommended_signal_weights.json",
        "data_quality.json",
        "data_quality.md",
        "data_quality_by_symbol.csv",
        "alerts.json",
        "alerts.csv",
        "alerts.md",
        "notifications.json",
        "notifications.csv",
        "recommendations.csv",
        "recommendations.json",
    ]
    if isinstance(result.get("recommendations"), pd.DataFrame):
        outputs.extend([f"recommendations_{profile}.csv" for profile in RECOMMENDATION_PROFILES])
    if isinstance(result.get("paper_order_plan"), dict):
        outputs.extend(["proposed_orders.csv", "paper_trading_audit.json"])
    if isinstance(result.get("ml_feature_matrix"), pd.DataFrame):
        outputs.append("ml_feature_matrix.csv")
    if isinstance(result.get("ml_predictions"), pd.DataFrame):
        outputs.append("ml_predictions.csv")
    if isinstance(result.get("ml_diagnostics"), dict) and result["ml_diagnostics"]:
        outputs.append("ml_diagnostics.json")
    if config.dashboard.enabled:
        outputs.append(str(config.dashboard.output_path))
    if isinstance(result.get("recommended_equity_curve"), pd.DataFrame) and not result["recommended_equity_curve"].empty:
        outputs.append("recommended_equity_curve.csv")
    if isinstance(result.get("recommended_positions"), pd.DataFrame) and not result["recommended_positions"].empty:
        outputs.append("recommended_positions.csv")
    if isinstance(result.get("recommended_trades"), pd.DataFrame) and not result["recommended_trades"].empty:
        outputs.append("recommended_trades.csv")
    if isinstance(result.get("recommended_period_metrics"), pd.DataFrame) and not result["recommended_period_metrics"].empty:
        outputs.append("recommended_period_metrics.csv")
    if isinstance(result.get("period_metrics"), pd.DataFrame) and not result["period_metrics"].empty:
        outputs.append("period_metrics.csv")
    if isinstance(result.get("equal_weight_equity"), pd.DataFrame):
        outputs.append("equal_weight_equity.csv")
    for key, filename in [
        ("walk_forward_recommended_equity_curve", "walk_forward_recommended_equity_curve.csv"),
        ("walk_forward_recommended_period_metrics", "walk_forward_recommended_period_metrics.csv"),
        ("walk_forward_recommended_positions", "walk_forward_recommended_positions.csv"),
        ("walk_forward_recommended_trades", "walk_forward_recommended_trades.csv"),
    ]:
        if isinstance(result.get(key), pd.DataFrame) and not result[key].empty:
            outputs.append(filename)
    audit = {
        "config": _config_dict(config),
        "metrics": result["metrics"],
        "period_metrics": _period_records(result.get("period_metrics")),
        "exposure": _period_records(result.get("exposure")),
        "signal_diagnostics": _period_records(result.get("signal_diagnostics")),
        "signal_weight_search": _period_records(result.get("signal_weight_search")),
        "recommended_signal_weights": result.get("recommended_signal_weights", {}),
        "recommended_metrics": result.get("recommended_metrics", {}),
        "recommended_period_metrics": _period_records(result.get("recommended_period_metrics")),
        "recommended_risk_checks": result.get("recommended_risk_checks", []),
        "walk_forward_signal_search": _period_records(result.get("walk_forward_signal_search")),
        "walk_forward_stability": _period_records(result.get("walk_forward_stability")),
        "walk_forward_recommended_signal_weights": result.get("walk_forward_recommended_signal_weights", {}),
        "walk_forward_recommended_metrics": result.get("walk_forward_recommended_metrics", {}),
        "walk_forward_recommended_period_metrics": _period_records(result.get("walk_forward_recommended_period_metrics")),
        "walk_forward_recommended_risk_checks": result.get("walk_forward_recommended_risk_checks", []),
        "walk_forward_recommended_test_comparison": _test_comparison_records(
            result.get("period_metrics"),
            result.get("walk_forward_recommended_period_metrics"),
        ),
        "recommended_test_comparison": _test_comparison_records(
            result.get("period_metrics"),
            result.get("recommended_period_metrics"),
        ),
        "data_quality_summary": result.get("data_quality", {}).get("summary", {}),
        "ml_diagnostics": result.get("ml_diagnostics", {}),
        "review_metadata": result.get("review_metadata", {}),
        "paper_trading": {
            key: value for key, value in result.get("paper_order_plan", {}).items() if key != "orders"
        },
        "alerts": result.get("alerts", []),
        "notifications": result.get("notifications", []),
        "recommendations": _period_records(result.get("recommendations")),
        "risk_checks": risk_checks,
        "outputs": outputs,
    }
    (output_dir / "audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    (output_dir / "summary.md").write_text(
        _summary_markdown(
            config,
            result["metrics"],
            result.get("period_metrics"),
            result.get("signal_diagnostics"),
            result.get("signal_weight_search"),
            result.get("recommended_signal_weights"),
            result.get("recommended_period_metrics"),
            result.get("walk_forward_stability"),
            result.get("walk_forward_recommended_signal_weights"),
            result.get("walk_forward_recommended_period_metrics"),
            result.get("recommendations"),
            review_markdown,
        ),
        encoding="utf-8",
    )


def _summary_markdown(
    config: AppConfig,
    metrics: dict[str, float],
    period_metrics: object,
    signal_diagnostics: object,
    signal_weight_search: object,
    recommended_signal_weights: object,
    recommended_period_metrics: object,
    walk_forward_stability: object,
    walk_forward_recommended_signal_weights: object,
    walk_forward_recommended_period_metrics: object,
    recommendations: object,
    review_markdown: str,
) -> str:
    metric_lines = "\n".join(f"- {key}: {value:.6f}" for key, value in sorted(metrics.items()))
    universe = ", ".join(config.data.universe)
    period_section = _period_markdown(period_metrics)
    diagnostics_section = _signal_diagnostics_markdown(signal_diagnostics)
    optimization_section = _optimization_markdown(signal_weight_search, recommended_signal_weights)
    recommended_section = _recommended_markdown(period_metrics, recommended_period_metrics)
    walk_forward_section = _walk_forward_markdown(walk_forward_stability)
    walk_forward_recommended_section = _walk_forward_recommended_markdown(
        period_metrics,
        walk_forward_recommended_signal_weights,
        walk_forward_recommended_period_metrics,
    )
    recommendations_section = _recommendations_markdown(recommendations)
    return (
        "# Quant Agent Backtest Summary\n\n"
        "## Configuration\n\n"
        f"- Data source: {config.data.source}\n"
        f"- Universe: {universe}\n"
        f"- Benchmark: {config.strategy.benchmark}\n"
        f"- Rebalance: {config.strategy.rebalance_frequency}\n"
        f"- Initial cash: {config.strategy.initial_cash:.2f}\n"
        f"- Costs: {config.strategy.transaction_cost_bps:.2f} bps commission + "
        f"{config.strategy.slippage_bps:.2f} bps slippage\n\n"
        "## Metrics\n\n"
        f"{metric_lines}\n\n"
        f"{period_section}"
        f"{diagnostics_section}"
        f"{optimization_section}"
        f"{recommended_section}"
        f"{walk_forward_section}"
        f"{walk_forward_recommended_section}"
        f"{recommendations_section}"
        f"{review_markdown}\n"
    )


def _config_dict(config: AppConfig) -> dict[str, Any]:
    return {
        "data": {
            "source": config.data.source,
            "start": config.data.start,
            "end": config.data.end,
            "cache_dir": str(config.data.cache_dir),
            "universe": config.data.universe,
            "path": str(config.data.path) if config.data.path else None,
            "csv_path": str(config.data.csv_path) if config.data.csv_path else None,
            "data_dir": str(config.data.data_dir) if config.data.data_dir else None,
            "universe_path": str(config.data.universe_path) if config.data.universe_path else None,
        },
        "strategy": config.strategy.__dict__,
        "risk": config.risk.__dict__,
        "report": {"output_dir": str(config.report.output_dir)},
        "evaluation": {
            "periods": [
                {"name": period.name, "start": period.start, "end": period.end} for period in config.evaluation.periods
            ]
        },
        "optimization": config.optimization.__dict__,
        "ml": config.ml.__dict__,
        "llm": config.llm.__dict__,
        "paper_trading": {**config.paper_trading.__dict__, "output_dir": str(config.paper_trading.output_dir)},
        "dashboard": {
            "enabled": config.dashboard.enabled,
            "output_path": str(config.dashboard.output_path),
            "service_dir": str(config.dashboard.service_dir),
            "runs_dir": str(config.dashboard.runs_dir),
        },
        "dashboard_security": {
            "enabled": config.dashboard_security.enabled,
            "token_env": config.dashboard_security.token_env,
            "token_configured": bool(config.dashboard_security.token),
            "audit_log_path": str(config.dashboard_security.audit_log_path),
        },
        "schedule": config.schedule.__dict__,
        "alerts": config.alerts.__dict__,
        "notifications": {**config.notifications.__dict__, "output_dir": str(config.notifications.output_dir)},
        "approvals": config.approvals.__dict__,
    }


def _period_markdown(period_metrics: object) -> str:
    if not isinstance(period_metrics, pd.DataFrame) or period_metrics.empty:
        return ""
    columns = ["period", "total_return", "cagr", "sharpe", "sortino", "max_drawdown", "alpha", "information_ratio"]
    available = [column for column in columns if column in period_metrics.columns]
    lines = ["## Period Metrics", "", "| " + " | ".join(available) + " |", "| " + " | ".join(["---"] * len(available)) + " |"]
    for _, row in period_metrics.iterrows():
        values = []
        for column in available:
            value = row[column]
            if column == "period":
                values.append(str(value))
            elif pd.isna(value):
                values.append("")
            else:
                values.append(f"{float(value):.4f}")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n\n"


def _period_records(period_metrics: object) -> list[dict[str, object]]:
    if not isinstance(period_metrics, pd.DataFrame) or period_metrics.empty:
        return []
    return period_metrics.to_dict(orient="records")


def _signal_diagnostics_markdown(signal_diagnostics: object) -> str:
    if not isinstance(signal_diagnostics, pd.DataFrame) or signal_diagnostics.empty:
        return ""
    columns = ["signal", "total_return", "sharpe", "max_drawdown", "excess_vs_equal_weight", "risk_passed"]
    available = [column for column in columns if column in signal_diagnostics.columns]
    lines = [
        "## Signal Diagnostics",
        "",
        "| " + " | ".join(available) + " |",
        "| " + " | ".join(["---"] * len(available)) + " |",
    ]
    for _, row in signal_diagnostics.iterrows():
        values = []
        for column in available:
            value = row[column]
            if column in {"signal", "risk_passed"}:
                values.append(str(value))
            elif pd.isna(value):
                values.append("")
            else:
                values.append(f"{float(value):.4f}")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n\n"


def _optimization_markdown(signal_weight_search: object, recommended_signal_weights: object) -> str:
    if not isinstance(signal_weight_search, pd.DataFrame) or signal_weight_search.empty:
        return ""
    ranked = signal_weight_search[signal_weight_search.get("risk_passed", False)].copy()
    if "validation_sharpe" in ranked.columns:
        ranked = ranked.sort_values(["validation_sharpe", "validation_total_return"], ascending=False).head(5)
    else:
        ranked = ranked.head(5)
    columns = ["candidate", "validation_total_return", "validation_sharpe", "validation_max_drawdown", "recommended"]
    available = [column for column in columns if column in ranked.columns]
    lines = [
        "## Signal Weight Search",
        "",
        "| " + " | ".join(available) + " |",
        "| " + " | ".join(["---"] * len(available)) + " |",
    ]
    for _, row in ranked.iterrows():
        values = []
        for column in available:
            value = row[column]
            if column in {"candidate", "recommended"}:
                values.append(str(value))
            elif pd.isna(value):
                values.append("")
            else:
                values.append(f"{float(value):.4f}")
        lines.append("| " + " | ".join(values) + " |")
    if isinstance(recommended_signal_weights, dict) and recommended_signal_weights:
        weight_text = ", ".join(f"{key}={value:.2f}" for key, value in recommended_signal_weights.items())
        lines.extend(["", f"Recommended validation-selected weights: `{weight_text}`"])
    return "\n".join(lines) + "\n\n"


def _recommended_markdown(period_metrics: object, recommended_period_metrics: object) -> str:
    comparison = _test_comparison_records(period_metrics, recommended_period_metrics)
    if not comparison:
        return ""
    columns = ["metric", "current_test", "recommended_test", "delta"]
    lines = [
        "## Recommended Weights Test Comparison",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in comparison:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["metric"]),
                    f"{float(row['current_test']):.4f}",
                    f"{float(row['recommended_test']):.4f}",
                    f"{float(row['delta']):.4f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n\n"


def _walk_forward_markdown(walk_forward_stability: object) -> str:
    if not isinstance(walk_forward_stability, pd.DataFrame) or walk_forward_stability.empty:
        return ""
    ranked = walk_forward_stability.head(5)
    columns = [
        "candidate",
        "window_wins",
        "average_validation_objective",
        "average_validation_total_return",
        "average_validation_max_drawdown",
        "average_rank",
    ]
    available = [column for column in columns if column in ranked.columns]
    lines = [
        "## Walk-Forward Signal Stability",
        "",
        "| " + " | ".join(available) + " |",
        "| " + " | ".join(["---"] * len(available)) + " |",
    ]
    for _, row in ranked.iterrows():
        values = []
        for column in available:
            value = row[column]
            if column == "candidate":
                values.append(str(value))
            elif pd.isna(value):
                values.append("")
            else:
                values.append(f"{float(value):.4f}")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n\n"


def _walk_forward_recommended_markdown(
    period_metrics: object,
    weights: object,
    walk_forward_recommended_period_metrics: object,
) -> str:
    comparison = _test_comparison_records(period_metrics, walk_forward_recommended_period_metrics)
    if not comparison:
        return ""
    lines = ["## Walk-Forward Recommended Test Comparison", ""]
    if isinstance(weights, dict) and weights:
        weight_text = ", ".join(f"{key}={value:.2f}" for key, value in weights.items())
        lines.append(f"Walk-forward stability-selected weights: `{weight_text}`")
        lines.append("")
    columns = ["metric", "current_test", "recommended_test", "delta"]
    lines.extend(["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"])
    for row in comparison:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["metric"]),
                    f"{float(row['current_test']):.4f}",
                    f"{float(row['recommended_test']):.4f}",
                    f"{float(row['delta']):.4f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n\n"


def _recommendations_markdown(recommendations: object) -> str:
    if not isinstance(recommendations, pd.DataFrame) or recommendations.empty:
        return ""
    rows = recommendations[recommendations["rank"] <= 3].copy()
    columns = ["recommendation_type", "rank", "symbol", "recommendation_score", "confidence", "risk_level", "reason"]
    lines = [
        "## Research Buy Candidates",
        "",
        "Research candidates only; not investment advice or live trading authorization.",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in rows.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if column == "recommendation_score":
                values.append(f"{float(value):.4f}")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n\n"


def _test_comparison_records(period_metrics: object, recommended_period_metrics: object) -> list[dict[str, object]]:
    if not isinstance(period_metrics, pd.DataFrame) or not isinstance(recommended_period_metrics, pd.DataFrame):
        return []
    if period_metrics.empty or recommended_period_metrics.empty:
        return []
    current = period_metrics[period_metrics["period"] == "test"]
    recommended = recommended_period_metrics[recommended_period_metrics["period"] == "test"]
    if current.empty or recommended.empty:
        return []
    current_row = current.iloc[0]
    recommended_row = recommended.iloc[0]
    metrics = ["total_return", "cagr", "sharpe", "sortino", "max_drawdown", "alpha", "information_ratio"]
    rows: list[dict[str, object]] = []
    for metric in metrics:
        if metric not in current_row or metric not in recommended_row:
            continue
        if pd.isna(current_row[metric]) or pd.isna(recommended_row[metric]):
            continue
        current_value = float(current_row[metric])
        recommended_value = float(recommended_row[metric])
        rows.append(
            {
                "metric": metric,
                "current_test": current_value,
                "recommended_test": recommended_value,
                "delta": recommended_value - current_value,
            }
        )
    return rows
