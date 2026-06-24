from __future__ import annotations

import pandas as pd

from quant_agent.config import RiskConfig, StrategyConfig


def build_target_positions(signals: pd.DataFrame, strategy: StrategyConfig, risk: RiskConfig) -> pd.DataFrame:
    candidates = signals.dropna(subset=["score", "avg_dollar_volume_20"]).copy()
    candidates = candidates[candidates["avg_dollar_volume_20"] >= risk.min_avg_dollar_volume]
    rebalance_dates = _rebalance_dates(candidates["date"], strategy.rebalance_frequency)
    rows: list[dict[str, object]] = []
    max_count = min(strategy.top_n, risk.max_positions)
    weight = min(1.0 / max_count, risk.max_position_weight) if max_count > 0 else 0.0

    for date in rebalance_dates:
        day = candidates[candidates["date"] == date].sort_values("score", ascending=False).head(max_count)
        for _, row in day.iterrows():
            rows.append({"date": date, "symbol": row["symbol"], "target_weight": weight, "score": row["score"]})

    positions = pd.DataFrame(rows, columns=["date", "symbol", "target_weight", "score"])
    if not positions.empty:
        positions["date"] = pd.to_datetime(positions["date"])
    return positions


def _rebalance_dates(dates: pd.Series, frequency: str) -> list[pd.Timestamp]:
    unique = pd.Series(pd.to_datetime(dates.dropna().unique())).sort_values()
    if unique.empty:
        return []
    freq = frequency.upper()
    if freq in {"D", "DAILY"}:
        return list(unique)
    period = "M" if freq in {"M", "ME", "MONTHLY"} else freq
    grouped = unique.groupby(unique.dt.to_period(period)).max()
    return list(grouped)
