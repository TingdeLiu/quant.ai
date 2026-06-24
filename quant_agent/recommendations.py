from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import AppConfig

RECOMMENDATION_PROFILES: dict[str, dict[str, Any]] = {
    "long_term": {
        "label": "Long Term",
        "horizon": "6-12 months",
        "weights": {"momentum_12_1_z": 0.45, "trend_20_50_z": 0.25, "low_volatility_z": 0.20, "ml_rank_z": 0.10},
    },
    "swing": {
        "label": "Swing",
        "horizon": "1-3 months",
        "weights": {"trend_20_50_z": 0.35, "reversal_1m_z": 0.30, "momentum_12_1_z": 0.20, "ml_rank_z": 0.15},
    },
    "short_term": {
        "label": "Short Term",
        "horizon": "1-4 weeks",
        "weights": {"reversal_1m_z": 0.45, "trend_20_50_z": 0.25, "momentum_12_1_z": 0.15, "ml_rank_z": 0.15},
    },
    "defensive": {
        "label": "Defensive",
        "horizon": "3-12 months",
        "weights": {"low_volatility_z": 0.55, "trend_20_50_z": 0.20, "momentum_12_1_z": 0.15, "ml_rank_z": 0.10},
    },
    "aggressive": {
        "label": "Aggressive",
        "horizon": "1-6 months",
        "weights": {"momentum_12_1_z": 0.45, "trend_20_50_z": 0.30, "ml_rank_z": 0.20, "low_volatility_z": -0.05},
    },
}


def build_recommendations(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    config: AppConfig,
    per_profile: int = 10,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest = _latest_signal_frame(signals)
    if latest.empty:
        empty = pd.DataFrame(columns=_columns())
        return empty, _payload(empty, config)

    latest_prices = prices.sort_values("date").groupby("symbol").tail(1)[["symbol", "adj_close"]].rename(
        columns={"adj_close": "latest_price"}
    )
    latest_targets = _latest_targets(targets)
    frame = latest.merge(latest_prices, on="symbol", how="left").merge(latest_targets, on="symbol", how="left")
    frame["target_weight"] = frame["target_weight"].fillna(0.0)

    rows: list[dict[str, Any]] = []
    for profile, spec in RECOMMENDATION_PROFILES.items():
        scored = frame.copy()
        scored["recommendation_score"] = _profile_score(scored, spec["weights"])
        scored = scored.dropna(subset=["recommendation_score"]).sort_values("recommendation_score", ascending=False)
        scored = scored.head(per_profile)
        for rank, (_, row) in enumerate(scored.iterrows(), start=1):
            score = float(row["recommendation_score"])
            rows.append(
                {
                    "recommendation_type": profile,
                    "label": spec["label"],
                    "horizon": spec["horizon"],
                    "rank": rank,
                    "symbol": row["symbol"],
                    "suggested_action": "research_buy_candidate",
                    "recommendation_score": score,
                    "confidence": _confidence(score),
                    "risk_level": _risk_level(profile, row),
                    "target_weight": float(row.get("target_weight", 0.0) or 0.0),
                    "research_weight": min(float(config.risk.max_position_weight), 1.0 / max(config.strategy.top_n, 1)),
                    "latest_price": float(row["latest_price"]) if pd.notna(row.get("latest_price")) else None,
                    "data_date": str(pd.to_datetime(row["date"]).date()),
                    "avg_dollar_volume_20": float(row.get("avg_dollar_volume_20", 0.0) or 0.0),
                    "reason": _reason(row, spec["weights"]),
                    "disclaimer": "Research candidate only; not investment advice or live trading authorization.",
                }
            )

    recommendations = pd.DataFrame(rows, columns=_columns())
    return recommendations, _payload(recommendations, config)


def write_recommendations(recommendations: pd.DataFrame, payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    recommendations.to_csv(output_dir / "recommendations.csv", index=False)
    for profile in RECOMMENDATION_PROFILES:
        subset = recommendations[recommendations["recommendation_type"] == profile]
        subset.to_csv(output_dir / f"recommendations_{profile}.csv", index=False)
    (output_dir / "recommendations.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _latest_signal_frame(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame()
    matured = signals.dropna(subset=["score"]).copy()
    if matured.empty:
        return pd.DataFrame()
    latest_date = pd.to_datetime(matured["date"]).max()
    return matured[pd.to_datetime(matured["date"]) == latest_date].copy()


def _latest_targets(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame(columns=["symbol", "target_weight"])
    latest_date = pd.to_datetime(targets["date"]).max()
    latest = targets[pd.to_datetime(targets["date"]) == latest_date].copy()
    return latest[["symbol", "target_weight"]]


def _profile_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    parts = []
    total = 0.0
    for column, weight in weights.items():
        if column not in frame.columns:
            continue
        parts.append(frame[column] * weight)
        total += abs(weight)
    if not parts or total == 0:
        return pd.Series([pd.NA] * len(frame), index=frame.index, dtype="Float64")
    return pd.concat(parts, axis=1).sum(axis=1, min_count=1) / total


def _confidence(score: float) -> str:
    if score >= 1.0:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _risk_level(profile: str, row: pd.Series) -> str:
    volatility = row.get("volatility_20")
    low_vol_z = row.get("low_volatility_z")
    if profile == "aggressive":
        return "high"
    if profile == "defensive":
        return "low" if pd.notna(low_vol_z) and float(low_vol_z) > 0 else "medium"
    if pd.notna(volatility) and float(volatility) > 0.035:
        return "high"
    if pd.notna(low_vol_z) and float(low_vol_z) > 0.5:
        return "low"
    return "medium"


def _reason(row: pd.Series, weights: dict[str, float]) -> str:
    labels = {
        "momentum_12_1_z": "12-1 momentum",
        "trend_20_50_z": "20/50 trend",
        "reversal_1m_z": "1-month reversal",
        "low_volatility_z": "low volatility",
        "ml_rank_z": "ML rank",
    }
    contributions = []
    for column, weight in weights.items():
        value = row.get(column)
        if pd.isna(value):
            continue
        contributions.append((abs(float(value) * weight), labels.get(column, column), float(value)))
    contributions.sort(reverse=True)
    top = contributions[:3]
    if not top:
        return "Ranked by available cross-sectional signal score."
    return "; ".join(f"{label} z={value:.2f}" for _, label, value in top)


def _payload(recommendations: pd.DataFrame, config: AppConfig) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for profile in RECOMMENDATION_PROFILES:
        subset = recommendations[recommendations["recommendation_type"] == profile] if not recommendations.empty else recommendations
        grouped[profile] = subset.to_dict(orient="records") if not subset.empty else []
    return {
        "disclaimer": "Research candidates only; not investment advice or live trading authorization.",
        "config": {
            "benchmark": config.strategy.benchmark,
            "top_n": config.strategy.top_n,
            "max_position_weight": config.risk.max_position_weight,
        },
        "profiles": RECOMMENDATION_PROFILES,
        "recommendations": grouped,
    }


def _columns() -> list[str]:
    return [
        "recommendation_type",
        "label",
        "horizon",
        "rank",
        "symbol",
        "suggested_action",
        "recommendation_score",
        "confidence",
        "risk_level",
        "target_weight",
        "research_weight",
        "latest_price",
        "data_date",
        "avg_dollar_volume_20",
        "reason",
        "disclaimer",
    ]
