from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from quant_agent.config import AppConfig, EvaluationPeriod
from quant_agent.features import BASE_SIGNAL_COLUMNS, weighted_score

ML_FEATURE_COLUMNS = [
    "momentum_12_1_z",
    "trend_20_50_z",
    "reversal_1m_z",
    "low_volatility_z",
    "ret_1d",
    "volatility_20",
]


def apply_ml_ranking_signal(signals: pd.DataFrame, config: AppConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not config.ml.enabled:
        return signals, {}

    frame = signals.copy()
    horizon = config.ml.prediction_horizon_days
    frame["future_return"] = frame.groupby("symbol")["adj_close"].pct_change(horizon).shift(-horizon)
    train_period = _period(config.evaluation.periods, config.ml.train_period)
    train = _slice_period(frame, train_period).dropna(subset=[*ML_FEATURE_COLUMNS, "future_return"])
    scored = frame.dropna(subset=ML_FEATURE_COLUMNS).copy()
    diagnostics: dict[str, Any] = {
        "enabled": True,
        "model_version": config.ml.model_version,
        "feature_version": config.ml.feature_version,
        "prediction_horizon_days": horizon,
        "train_period": config.ml.train_period,
        "train_rows": int(len(train)),
        "feature_columns": ML_FEATURE_COLUMNS,
        "input_hash": _input_hash(train),
    }

    if len(train) < 20 or scored.empty:
        frame["ml_rank"] = pd.NA
        frame["ml_rank_z"] = pd.NA
        diagnostics["status"] = "skipped_insufficient_training_rows"
        return frame, diagnostics

    model = Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
    model.fit(train[ML_FEATURE_COLUMNS], train["future_return"])
    frame["ml_rank"] = pd.NA
    frame.loc[scored.index, "ml_rank"] = model.predict(scored[ML_FEATURE_COLUMNS])
    frame["ml_rank"] = pd.to_numeric(frame["ml_rank"], errors="coerce")
    frame["ml_rank_z"] = _cross_sectional_zscore(frame, "ml_rank")
    frame["score"] = weighted_score(frame, config.strategy.signal_weights)
    diagnostics["status"] = "trained"
    diagnostics["scored_rows"] = int(frame["ml_rank"].notna().sum())
    diagnostics["coefs"] = {
        feature: float(coef)
        for feature, coef in zip(ML_FEATURE_COLUMNS, model.named_steps["ridge"].coef_, strict=True)
    }
    return frame, diagnostics


def _period(periods: list[EvaluationPeriod], name: str) -> EvaluationPeriod | None:
    for period in periods:
        if period.name == name:
            return period
    return None


def _slice_period(frame: pd.DataFrame, period: EvaluationPeriod | None) -> pd.DataFrame:
    if period is None:
        return frame
    mask = pd.Series(True, index=frame.index)
    if period.start is not None:
        mask &= frame["date"] >= pd.Timestamp(period.start)
    if period.end is not None:
        mask &= frame["date"] <= pd.Timestamp(period.end)
    return frame.loc[mask]


def _cross_sectional_zscore(frame: pd.DataFrame, column: str) -> pd.Series:
    mean = frame.groupby("date")[column].transform("mean")
    std = frame.groupby("date")[column].transform("std").replace(0, pd.NA)
    return (frame[column] - mean) / std


def _input_hash(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    payload = {
        "rows": len(frame),
        "min_date": str(frame["date"].min()),
        "max_date": str(frame["date"].max()),
        "symbols": sorted(frame["symbol"].dropna().astype(str).unique().tolist()),
        "features": BASE_SIGNAL_COLUMNS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
