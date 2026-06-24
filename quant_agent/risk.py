from __future__ import annotations

import pandas as pd

from quant_agent.config import RiskConfig


def check_targets(targets: pd.DataFrame, risk: RiskConfig) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    if targets.empty:
        return [{"passed": False, "code": "empty_targets", "message": "No target positions generated"}]

    per_day_count = targets.groupby("date")["symbol"].count()
    too_many = per_day_count[per_day_count > risk.max_positions]
    checks.append(
        {
            "passed": too_many.empty,
            "code": "max_positions",
            "message": "Target count is within limit" if too_many.empty else f"Too many positions: {too_many.to_dict()}",
        }
    )

    overweight = targets[targets["target_weight"].abs() > risk.max_position_weight]
    checks.append(
        {
            "passed": overweight.empty,
            "code": "max_position_weight",
            "message": "Position weights are within limit" if overweight.empty else "At least one target exceeds max weight",
        }
    )

    if risk.long_only:
        shorts = targets[targets["target_weight"] < 0]
        checks.append(
            {
                "passed": shorts.empty,
                "code": "long_only",
                "message": "No short targets" if shorts.empty else "Short targets are not allowed",
            }
        )

    turnover = _target_turnover(targets)
    tolerance = 1e-9
    high_turnover = turnover[turnover > risk.max_turnover + tolerance]
    checks.append(
        {
            "passed": high_turnover.empty,
            "code": "max_turnover",
            "message": "Turnover is within limit" if high_turnover.empty else f"High turnover: {high_turnover.to_dict()}",
        }
    )
    return checks


def risk_passed(checks: list[dict[str, object]]) -> bool:
    return all(bool(check["passed"]) for check in checks)


def _target_turnover(targets: pd.DataFrame) -> pd.Series:
    wide = targets.pivot_table(index="date", columns="symbol", values="target_weight", fill_value=0.0)
    return wide.diff().abs().sum(axis=1).fillna(wide.abs().sum(axis=1))
