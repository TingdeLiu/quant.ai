from __future__ import annotations

import math

import pandas as pd

from quant_agent.config import EvaluationPeriod


def calculate_metrics(equity: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> dict[str, float]:
    returns = _returns_by_date(equity)
    if returns.empty:
        return _empty_metrics()
    years = max((equity["date"].max() - equity["date"].min()).days / 365.25, 1 / 365.25)
    total_return = equity["equity"].iloc[-1] / equity["equity"].iloc[0] - 1
    cagr = (1 + total_return) ** (1 / years) - 1
    volatility = returns.std(ddof=0) * math.sqrt(252)
    sharpe = (returns.mean() * 252 / volatility) if volatility else 0.0
    drawdown = equity["equity"] / equity["equity"].cummax() - 1
    downside = returns[returns < 0]
    downside_volatility = downside.std(ddof=0) * math.sqrt(252) if not downside.empty else 0.0
    sortino = (returns.mean() * 252 / downside_volatility) if downside_volatility else 0.0
    max_drawdown = float(drawdown.min())
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0
    metrics = {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "calmar": calmar,
        "volatility": float(volatility),
        "max_drawdown": max_drawdown,
        "win_rate": float((returns > 0).mean()),
    }
    if benchmark is not None and not benchmark.empty:
        metrics["benchmark_total_return"] = float(benchmark["equity"].iloc[-1] / benchmark["equity"].iloc[0] - 1)
        metrics["excess_total_return"] = metrics["total_return"] - metrics["benchmark_total_return"]
        benchmark_returns = _returns_by_date(benchmark)
        joined = pd.concat({"strategy": returns, "benchmark": benchmark_returns}, axis=1, join="inner").dropna()
        if len(joined) >= 2:
            aligned = joined["strategy"]
            benchmark_aligned = joined["benchmark"]
            active = aligned - benchmark_aligned
            benchmark_variance = ((benchmark_aligned - benchmark_aligned.mean()) ** 2).mean()
            tracking_error = active.std(ddof=0) * math.sqrt(252)
            covariance = ((aligned - aligned.mean()) * (benchmark_aligned - benchmark_aligned.mean())).mean()
            beta = covariance / benchmark_variance if benchmark_variance else 0.0
            alpha = (aligned.mean() - beta * benchmark_aligned.mean()) * 252
            information_ratio = (active.mean() * 252 / tracking_error) if tracking_error else 0.0
            metrics["beta"] = float(beta)
            metrics["alpha"] = float(alpha)
            metrics["information_ratio"] = float(information_ratio)
    return metrics


def calculate_period_metrics(
    equity: pd.DataFrame,
    benchmark: pd.DataFrame | None,
    periods: list[EvaluationPeriod],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if not periods:
        return pd.DataFrame()
    equity_frame = equity.copy()
    equity_frame["date"] = pd.to_datetime(equity_frame["date"])
    benchmark_frame = None
    if benchmark is not None and not benchmark.empty:
        benchmark_frame = benchmark.copy()
        benchmark_frame["date"] = pd.to_datetime(benchmark_frame["date"])

    for period in periods:
        sliced_equity = _slice_period(equity_frame, period.start, period.end)
        if len(sliced_equity) < 2:
            rows.append({"period": period.name, "start": period.start, "end": period.end, "rows": len(sliced_equity)})
            continue
        sliced_benchmark = _slice_period(benchmark_frame, period.start, period.end) if benchmark_frame is not None else None
        metrics = calculate_metrics(sliced_equity, sliced_benchmark)
        rows.append(
            {
                "period": period.name,
                "start": period.start,
                "end": period.end,
                "rows": len(sliced_equity),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _empty_metrics() -> dict[str, float]:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "volatility": 0.0,
        "max_drawdown": 0.0,
        "win_rate": 0.0,
    }


def _returns_by_date(equity: pd.DataFrame) -> pd.Series:
    frame = equity.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date")["equity"].pct_change().dropna()


def _slice_period(frame: pd.DataFrame | None, start: str | None, end: str | None) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= frame["date"] >= pd.Timestamp(start)
    if end is not None:
        mask &= frame["date"] <= pd.Timestamp(end)
    return frame.loc[mask].reset_index(drop=True)
