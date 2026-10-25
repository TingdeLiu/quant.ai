from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

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

# StandardScaler 判定「常数列」的阈值，照搬 sklearn 的 _handle_zeros_in_scale。
_ZERO_SCALE = 10 * np.finfo(float).eps


@dataclass(frozen=True)
class _StandardizedRidge:
    """标准化 + 岭回归的闭式解。

    等价于 sklearn 的 Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha))])，
    自己实现是为了不为这一处而扛上 scikit-learn —— 它是全项目唯一用到 sklearn 的
    地方，却是所有依赖里最重、也最容易在收紧了未签名 DLL 策略的 Windows 上装不上
    的一个。tests/test_ml.py 用 sklearn 当年的输出做金标准，锁住这份等价性。
    """

    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    intercept: float

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        standardized = (features.to_numpy(dtype=float) - self.mean) / self.scale
        return standardized @ self.coef + self.intercept


def _fit_standardized_ridge(features: pd.DataFrame, target: pd.Series, alpha: float = 1.0) -> _StandardizedRidge:
    x = features.to_numpy(dtype=float)
    y = target.to_numpy(dtype=float)

    mean = x.mean(axis=0)
    scale = x.std(axis=0)  # ddof=0，与 StandardScaler 一致
    # 常数列标准差为 0：把尺度置 1，否则除零会让整列变成 NaN 或 inf。
    scale = np.where(scale > _ZERO_SCALE, scale, 1.0)
    standardized = (x - mean) / scale

    # Ridge(fit_intercept=True) 不惩罚截距：先把 X 与 y 中心化解出系数，再回推截距。
    column_mean = standardized.mean(axis=0)
    target_mean = y.mean()
    centered = standardized - column_mean
    # 目标是 ||y - Xw||² + alpha·||w||²，无 1/n 缩放，故闭式解为 (XᵀX + αI)⁻¹Xᵀy。
    # alpha > 0 保证了正定，不会奇异。
    gram = centered.T @ centered
    gram[np.diag_indices_from(gram)] += alpha
    coef = np.linalg.solve(gram, centered.T @ (y - target_mean))

    return _StandardizedRidge(
        mean=mean,
        scale=scale,
        coef=coef,
        intercept=float(target_mean - column_mean @ coef),
    )


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

    model = _fit_standardized_ridge(train[ML_FEATURE_COLUMNS], train["future_return"])
    frame["ml_rank"] = pd.NA
    frame.loc[scored.index, "ml_rank"] = model.predict(scored[ML_FEATURE_COLUMNS])
    frame["ml_rank"] = pd.to_numeric(frame["ml_rank"], errors="coerce")
    frame["ml_rank_z"] = _cross_sectional_zscore(frame, "ml_rank")
    frame["score"] = weighted_score(frame, config.strategy.signal_weights)
    diagnostics["status"] = "trained"
    diagnostics["scored_rows"] = int(frame["ml_rank"].notna().sum())
    diagnostics["coefs"] = {
        feature: float(coef) for feature, coef in zip(ML_FEATURE_COLUMNS, model.coef, strict=True)
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
