from __future__ import annotations

import pandas as pd

from quant_agent.config import EvaluationPeriod, StrategyConfig
from quant_agent.metrics import calculate_metrics, calculate_period_metrics


def run_backtest(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    strategy: StrategyConfig,
    evaluation_periods: list[EvaluationPeriod] | None = None,
) -> dict[str, object]:
    returns = _daily_returns(prices)
    target_weights = _daily_weights(returns.index, targets)
    aligned_returns = returns.reindex(columns=target_weights.columns).fillna(0.0)
    weights = target_weights.shift(1).fillna(0.0)
    gross_returns = (weights * aligned_returns).sum(axis=1)
    turnover = target_weights.diff().abs().sum(axis=1).fillna(target_weights.abs().sum(axis=1))
    cost_rate = (strategy.transaction_cost_bps + strategy.slippage_bps) / 10000.0
    net_returns = gross_returns - turnover * cost_rate
    equity = pd.DataFrame({"date": net_returns.index, "equity": strategy.initial_cash * (1 + net_returns).cumprod()})
    benchmark_equity = _benchmark_equity(prices, strategy)
    equal_weight_equity = _equal_weight_equity(returns, strategy)
    trades = _trades(target_weights, strategy.initial_cash)
    positions = _positions(target_weights)
    exposure = _exposure_summary(positions)
    metrics = calculate_metrics(equity, benchmark_equity)
    metrics["average_turnover"] = float(turnover.mean()) if not turnover.empty else 0.0
    holding = _holding_period_metrics(exposure)
    metrics.update(holding)
    if not equal_weight_equity.empty:
        equal_weight_metrics = calculate_metrics(equal_weight_equity)
        metrics["equal_weight_total_return"] = equal_weight_metrics["total_return"]
        metrics["excess_vs_equal_weight"] = metrics["total_return"] - equal_weight_metrics["total_return"]
    period_metrics = calculate_period_metrics(equity, benchmark_equity, evaluation_periods or [])
    return {
        "equity_curve": equity.reset_index(drop=True),
        "benchmark_equity": benchmark_equity,
        "equal_weight_equity": equal_weight_equity,
        "positions": positions,
        "trades": trades,
        "exposure": exposure,
        "metrics": metrics,
        "period_metrics": period_metrics,
    }


def _daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    close = prices.pivot(index="date", columns="symbol", values="adj_close").sort_index()
    return close.pct_change().fillna(0.0)


def _daily_weights(index: pd.Index, targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame(index=index)
    wide = targets.pivot_table(index="date", columns="symbol", values="target_weight", fill_value=0.0)
    wide = wide.reindex(index).ffill().fillna(0.0)
    return wide


def _benchmark_equity(prices: pd.DataFrame, strategy: StrategyConfig) -> pd.DataFrame:
    bench = prices[prices["symbol"] == strategy.benchmark].sort_values("date")
    if bench.empty:
        return pd.DataFrame(columns=["date", "equity"])
    ret = bench["adj_close"].pct_change().fillna(0.0)
    return pd.DataFrame({"date": bench["date"], "equity": strategy.initial_cash * (1 + ret).cumprod()})


def _equal_weight_equity(returns: pd.DataFrame, strategy: StrategyConfig) -> pd.DataFrame:
    symbols = [symbol for symbol in returns.columns if symbol != strategy.benchmark]
    if not symbols:
        return pd.DataFrame(columns=["date", "equity"])
    daily = returns[symbols].mean(axis=1).fillna(0.0)
    return pd.DataFrame({"date": daily.index, "equity": strategy.initial_cash * (1 + daily).cumprod()}).reset_index(drop=True)


def _positions(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "symbol", "weight"])
    rows = weights.stack().rename("weight").reset_index()
    rows = rows[rows["weight"] != 0].rename(columns={"level_0": "date"})
    return rows[["date", "symbol", "weight"]].reset_index(drop=True)


def _trades(weights: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "symbol", "delta_weight", "estimated_notional"])
    deltas = weights.diff().fillna(weights)
    rows = deltas.stack().rename("delta_weight").reset_index()
    rows = rows[rows["delta_weight"] != 0].rename(columns={"level_0": "date"})
    rows["estimated_notional"] = rows["delta_weight"].abs() * initial_cash
    return rows[["date", "symbol", "delta_weight", "estimated_notional"]].reset_index(drop=True)


def _exposure_summary(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["symbol", "days_held", "average_weight", "max_weight"])
    exposure = (
        positions.groupby("symbol")["weight"]
        .agg(days_held="count", average_weight="mean", max_weight="max")
        .reset_index()
        .sort_values(["average_weight", "days_held"], ascending=False)
    )
    return exposure


def _holding_period_metrics(exposure: pd.DataFrame) -> dict[str, float]:
    if exposure.empty or "days_held" not in exposure.columns:
        return {"average_holding_days": 0.0, "max_holding_days": 0.0}
    return {
        "average_holding_days": float(exposure["days_held"].mean()),
        "max_holding_days": float(exposure["days_held"].max()),
    }
