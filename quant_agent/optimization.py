from __future__ import annotations

from itertools import combinations

import pandas as pd

from quant_agent.backtest import run_backtest
from quant_agent.config import AppConfig
from quant_agent.features import available_signal_columns, weighted_score
from quant_agent.portfolio import build_target_positions
from quant_agent.risk import check_targets, risk_passed


def optimize_signal_weights(prices: pd.DataFrame, signals: pd.DataFrame, config: AppConfig) -> dict[str, object]:
    if not config.optimization.enabled:
        return {"signal_weight_search": pd.DataFrame(), "recommended_signal_weights": {}}

    rows: list[dict[str, object]] = []
    signal_columns = available_signal_columns(signals)
    for label, weights in _candidate_weights(signal_columns):
        candidate_signals = signals.copy()
        candidate_signals["score"] = weighted_score(candidate_signals, weights)
        targets = build_target_positions(candidate_signals, config.strategy, config.risk)
        checks = check_targets(targets, config.risk)
        passed = risk_passed(checks)
        row: dict[str, object] = {"candidate": label, "risk_passed": passed, **_prefixed_weights(weights)}
        if passed and not targets.empty:
            result = run_backtest(prices, targets, config.strategy, config.evaluation.periods)
            row.update(_period_values(result["period_metrics"], config.optimization.train_period, "train"))
            row.update(_period_values(result["period_metrics"], config.optimization.validation_period, "validation"))
        rows.append(row)

    search = pd.DataFrame(rows)
    if search.empty or f"validation_{config.optimization.objective}" not in search.columns:
        return {"signal_weight_search": search, "recommended_signal_weights": {}}

    eligible = search[
        (search["risk_passed"])
        & (search.get("validation_max_drawdown", 0.0) >= config.optimization.max_drawdown_floor)
        & search[f"validation_{config.optimization.objective}"].notna()
    ].copy()
    if eligible.empty:
        return {"signal_weight_search": search, "recommended_signal_weights": {}}

    eligible = eligible.sort_values(
        [f"validation_{config.optimization.objective}", "validation_total_return"],
        ascending=False,
    )
    best = eligible.iloc[0]
    recommended = {signal: float(best[f"weight_{signal}"]) for signal in signal_columns}
    search["recommended"] = search["candidate"] == best["candidate"]
    evaluation = evaluate_recommended_weights(prices, signals, config, recommended)
    walk_forward = walk_forward_signal_search(prices, signals, config)
    if not walk_forward.get("walk_forward_stability", pd.DataFrame()).empty:
        wf_weights = _weights_from_candidate(
            walk_forward["walk_forward_stability"].iloc[0]["candidate"],
            signal_columns,
        )
        walk_forward["walk_forward_recommended_signal_weights"] = wf_weights
        walk_forward.update(_prefixed_recommended_evaluation("walk_forward_recommended", prices, signals, config, wf_weights))
    return {"signal_weight_search": search, "recommended_signal_weights": recommended, **evaluation, **walk_forward}


def evaluate_recommended_weights(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    config: AppConfig,
    recommended_weights: dict[str, float],
) -> dict[str, object]:
    if not recommended_weights:
        return {
            "recommended_equity_curve": pd.DataFrame(),
            "recommended_period_metrics": pd.DataFrame(),
            "recommended_metrics": {},
            "recommended_risk_checks": [],
        }
    recommended_signals = signals.copy()
    recommended_signals["score"] = weighted_score(recommended_signals, recommended_weights)
    targets = build_target_positions(recommended_signals, config.strategy, config.risk)
    checks = check_targets(targets, config.risk)
    if not risk_passed(checks) or targets.empty:
        return {
            "recommended_equity_curve": pd.DataFrame(),
            "recommended_period_metrics": pd.DataFrame(),
            "recommended_metrics": {},
            "recommended_risk_checks": checks,
        }
    result = run_backtest(prices, targets, config.strategy, config.evaluation.periods)
    return {
        "recommended_equity_curve": result["equity_curve"],
        "recommended_period_metrics": result["period_metrics"],
        "recommended_metrics": result["metrics"],
        "recommended_positions": result["positions"],
        "recommended_trades": result["trades"],
        "recommended_risk_checks": checks,
    }


def _prefixed_recommended_evaluation(
    prefix: str,
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    config: AppConfig,
    weights: dict[str, float],
) -> dict[str, object]:
    result = evaluate_recommended_weights(prices, signals, config, weights)
    mapping = {
        "recommended_equity_curve": f"{prefix}_equity_curve",
        "recommended_period_metrics": f"{prefix}_period_metrics",
        "recommended_metrics": f"{prefix}_metrics",
        "recommended_positions": f"{prefix}_positions",
        "recommended_trades": f"{prefix}_trades",
        "recommended_risk_checks": f"{prefix}_risk_checks",
    }
    return {new_key: result.get(old_key) for old_key, new_key in mapping.items()}


def _candidate_weights(signal_columns: list[str]) -> list[tuple[str, dict[str, float]]]:
    candidates: list[tuple[str, dict[str, float]]] = []
    for size in range(1, len(signal_columns) + 1):
        for subset in combinations(signal_columns, size):
            weight = 1.0 / len(subset)
            weights = {signal: (weight if signal in subset else 0.0) for signal in signal_columns}
            candidates.append(("+".join(subset), weights))
    return candidates


def _weights_from_candidate(candidate: str, signal_columns: list[str]) -> dict[str, float]:
    selected = set(candidate.split("+"))
    selected = {signal for signal in selected if signal in signal_columns}
    if not selected:
        return {signal: 0.0 for signal in signal_columns}
    weight = 1.0 / len(selected)
    return {signal: (weight if signal in selected else 0.0) for signal in signal_columns}


def walk_forward_signal_search(prices: pd.DataFrame, signals: pd.DataFrame, config: AppConfig) -> dict[str, object]:
    if not config.optimization.walk_forward_enabled or not config.optimization.walk_forward_windows:
        return {"walk_forward_signal_search": pd.DataFrame(), "walk_forward_stability": pd.DataFrame()}
    rows: list[dict[str, object]] = []
    for window in config.optimization.walk_forward_windows:
        for label, weights in _candidate_weights(available_signal_columns(signals)):
            candidate_signals = signals.copy()
            candidate_signals["score"] = weighted_score(candidate_signals, weights)
            targets = build_target_positions(candidate_signals, config.strategy, config.risk)
            checks = check_targets(targets, config.risk)
            passed = risk_passed(checks)
            row: dict[str, object] = {
                "window": window["name"],
                "candidate": label,
                "risk_passed": passed,
                **_prefixed_weights(weights),
            }
            if passed and not targets.empty:
                result = run_backtest(prices, targets, config.strategy, [])
                row.update(_date_window_values(result["equity_curve"], result["benchmark_equity"], window, "train"))
                row.update(_date_window_values(result["equity_curve"], result["benchmark_equity"], window, "validation"))
            rows.append(row)
    search = pd.DataFrame(rows)
    if search.empty or "validation_sharpe" not in search.columns:
        return {"walk_forward_signal_search": search, "walk_forward_stability": pd.DataFrame()}
    search["window_rank"] = (
        search[search["risk_passed"]]
        .groupby("window")["validation_sharpe"]
        .rank(method="min", ascending=False)
    )
    stability = _walk_forward_stability(search, config.optimization.objective)
    return {"walk_forward_signal_search": search, "walk_forward_stability": stability}


def _prefixed_weights(weights: dict[str, float]) -> dict[str, float]:
    return {f"weight_{signal}": float(value) for signal, value in weights.items()}


def _period_values(period_metrics: pd.DataFrame, period: str, prefix: str) -> dict[str, float]:
    if period_metrics.empty or "period" not in period_metrics.columns:
        return {}
    match = period_metrics[period_metrics["period"] == period]
    if match.empty:
        return {}
    row = match.iloc[0]
    keys = ["total_return", "cagr", "sharpe", "sortino", "max_drawdown", "alpha", "information_ratio"]
    return {f"{prefix}_{key}": float(row[key]) for key in keys if key in row and pd.notna(row[key])}


def _date_window_values(
    equity: pd.DataFrame,
    benchmark: pd.DataFrame,
    window: dict[str, str | None],
    prefix: str,
) -> dict[str, float]:
    from quant_agent.config import EvaluationPeriod
    from quant_agent.metrics import calculate_period_metrics

    period = EvaluationPeriod(
        name=prefix,
        start=window.get(f"{prefix}_start"),
        end=window.get(f"{prefix}_end"),
    )
    metrics = calculate_period_metrics(equity, benchmark, [period])
    return _period_values(metrics, prefix, prefix)


def _walk_forward_stability(search: pd.DataFrame, objective: str) -> pd.DataFrame:
    metric = f"validation_{objective}"
    eligible = search[(search["risk_passed"]) & search[metric].notna()].copy()
    if eligible.empty:
        return pd.DataFrame()
    best_by_window = eligible.sort_values([metric, "validation_total_return"], ascending=False).groupby("window").head(1)
    summary = (
        eligible.groupby("candidate")
        .agg(
            windows=("window", "nunique"),
            average_validation_objective=(metric, "mean"),
            median_validation_objective=(metric, "median"),
            average_validation_total_return=("validation_total_return", "mean"),
            average_validation_max_drawdown=("validation_max_drawdown", "mean"),
            average_rank=("window_rank", "mean"),
        )
        .reset_index()
    )
    wins = best_by_window.groupby("candidate")["window"].count().rename("window_wins").reset_index()
    summary = summary.merge(wins, on="candidate", how="left").fillna({"window_wins": 0})
    return summary.sort_values(
        ["window_wins", "average_validation_objective", "average_validation_total_return"],
        ascending=False,
    ).reset_index(drop=True)
