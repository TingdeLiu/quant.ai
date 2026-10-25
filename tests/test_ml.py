"""`_fit_standardized_ridge` 必须一直等价于 sklearn 的
Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))])。

项目已经不装 scikit-learn，所以这里没法现场对照，改用金标准：下面的数值是
scikit-learn 1.9.0 在同一份夹具上的真实输出，于移除依赖前采集。夹具故意把列尺度
拉开 10 个数量级、放一列常数、再放一列与首列完全共线 —— 这三样正是标准化与岭
回归各自的边界条件。

夹具靠 np.random.default_rng(7) 复现：PCG64 的数据流由 NumPy 承诺跨版本稳定。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_agent.ml import _fit_standardized_ridge

# scikit-learn 1.9.0 的输出。改动 _fit_standardized_ridge 后若这些值对不上，
# 说明等价性被破坏了，不要直接改数字 —— 先确认新实现到底算的是什么。
GOLDEN_COEF = [
    0.5381117201137445,
    -0.031478573960284716,
    0.006411565536263167,
    0.0,
    0.5381117201137368,
]
GOLDEN_INTERCEPT = 9.758506816239509
GOLDEN_FIRST_FIVE = [
    9.995731804678483,
    8.861547439500878,
    10.564247350910216,
    10.855371760844509,
    7.864950563469806,
]


def _fixture() -> tuple[pd.DataFrame, pd.Series]:
    """列尺度差 10 个数量级；第 3 列为常数；第 4 列与第 0 列完全共线。"""
    rng = np.random.default_rng(7)
    x = rng.normal(size=(120, 5))
    x[:, 1] *= 1e4
    x[:, 2] *= 1e-5
    x[:, 3] = 3.5
    x[:, 4] = x[:, 0] * 2.0
    y = x[:, 0] * 1.2 - x[:, 2] * 5.0 + rng.normal(scale=0.3, size=120) + 10.0
    return pd.DataFrame(x, columns=[f"f{i}" for i in range(5)]), pd.Series(y, name="y")


def test_matches_sklearn_golden_values() -> None:
    features, target = _fixture()

    model = _fit_standardized_ridge(features, target)

    assert model.coef == pytest.approx(GOLDEN_COEF, abs=1e-12)
    assert model.intercept == pytest.approx(GOLDEN_INTERCEPT, abs=1e-12)
    assert model.predict(features)[:5] == pytest.approx(GOLDEN_FIRST_FIVE, abs=1e-12)


def test_constant_column_yields_zero_coefficient_without_nan() -> None:
    """常数列标准差为 0。尺度不置 1 的话，除零会让整列变 NaN，预测随之全废。"""
    features, target = _fixture()

    model = _fit_standardized_ridge(features, target)
    predictions = model.predict(features)

    assert model.scale[3] == 1.0  # 常数列的尺度被置 1
    assert model.coef[3] == 0.0  # 中心化后该列全为 0，拿不到权重
    assert np.isfinite(model.coef).all()
    assert np.isfinite(predictions).all()


def test_larger_alpha_shrinks_coefficients() -> None:
    """岭回归的定义性质：惩罚越重，系数越往 0 收。"""
    features, target = _fixture()

    light = _fit_standardized_ridge(features, target, alpha=0.01)
    heavy = _fit_standardized_ridge(features, target, alpha=1000.0)

    assert np.linalg.norm(heavy.coef) < np.linalg.norm(light.coef)
    # 截距不受惩罚，始终等于训练目标的均值。
    assert heavy.intercept == pytest.approx(float(target.mean()), abs=1e-9)
