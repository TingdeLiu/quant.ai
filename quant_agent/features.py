from __future__ import annotations

import numpy as np
import pandas as pd

BASE_SIGNAL_COLUMNS = ["momentum_12_1", "trend_20_50", "reversal_1m", "low_volatility"]
OPTIONAL_SIGNAL_COLUMNS = ["ml_rank"]
SIGNAL_COLUMNS = BASE_SIGNAL_COLUMNS


def build_signals(prices: pd.DataFrame, signal_weights: dict[str, float] | None = None) -> pd.DataFrame:
    frames = []
    for symbol, group in prices.groupby("symbol", sort=False):
        g = group.sort_values("date").copy()
        adj = g["adj_close"]
        g["ret_1d"] = adj.pct_change()
        g["momentum_12_1"] = adj.pct_change(252).shift(21)
        g["ma_20"] = adj.rolling(20).mean()
        g["ma_50"] = adj.rolling(50).mean()
        g["trend_20_50"] = (g["ma_20"] / g["ma_50"]) - 1
        g["short_reversal"] = -adj.pct_change(5).shift(1)
        g["reversal_1m"] = -adj.pct_change(21).shift(1)
        g["volatility_20"] = g["ret_1d"].rolling(20).std()
        g["low_volatility"] = -g["volatility_20"]
        g["avg_dollar_volume_20"] = (g["adj_close"] * g["volume"]).rolling(20).mean()
        g["symbol"] = symbol
        frames.append(g)
    features = pd.concat(frames, ignore_index=True)
    features = _cross_sectional_zscore(features, BASE_SIGNAL_COLUMNS)
    features["score"] = weighted_score(features, signal_weights)
    return features.sort_values(["date", "symbol"]).reset_index(drop=True)


def weighted_score(features: pd.DataFrame, signal_weights: dict[str, float] | None = None) -> pd.Series:
    columns = available_signal_columns(features)
    weights = _normalized_weights(signal_weights, columns)
    weighted = []
    for signal, weight in weights.items():
        weighted.append(features[f"{signal}_z"] * weight)
    if not weighted:
        return features[[f"{signal}_z" for signal in columns]].mean(axis=1, skipna=True)
    return pd.concat(weighted, axis=1).sum(axis=1, min_count=1)


def available_signal_columns(features: pd.DataFrame) -> list[str]:
    columns = []
    for signal in [*BASE_SIGNAL_COLUMNS, *OPTIONAL_SIGNAL_COLUMNS]:
        if f"{signal}_z" in features.columns:
            columns.append(signal)
    return columns


def _cross_sectional_zscore(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        mean = out.groupby("date")[column].transform("mean")
        std = out.groupby("date")[column].transform("std").replace(0, np.nan)
        out[f"{column}_z"] = (out[column] - mean) / std
    return out


def _normalized_weights(signal_weights: dict[str, float] | None, columns: list[str]) -> dict[str, float]:
    raw = signal_weights or {signal: 1.0 for signal in columns}
    cleaned = {signal: float(raw.get(signal, 0.0)) for signal in columns}
    total = sum(abs(weight) for weight in cleaned.values())
    if total == 0:
        return {signal: 1.0 / len(columns) for signal in columns}
    return {signal: weight / total for signal, weight in cleaned.items()}
