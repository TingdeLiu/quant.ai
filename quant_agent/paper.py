from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import PaperTradingConfig


def build_paper_order_plan(
    targets: pd.DataFrame,
    prices: pd.DataFrame,
    config: PaperTradingConfig,
    current_positions: pd.DataFrame | None = None,
) -> dict[str, Any]:
    current_positions = current_positions if current_positions is not None else _empty_current_positions()
    if targets.empty:
        return {"orders": pd.DataFrame(), "checks": [{"passed": False, "code": "empty_targets"}]}
    latest_date = pd.to_datetime(targets["date"]).max()
    latest_targets = targets[pd.to_datetime(targets["date"]) == latest_date].copy()
    latest_prices = prices.sort_values("date").groupby("symbol").tail(1)[["symbol", "adj_close"]]
    latest_targets = latest_targets.merge(latest_prices, on="symbol", how="left")
    current = current_positions.copy()
    if not current.empty:
        current["symbol"] = current["symbol"].astype(str).str.upper()
    plan = latest_targets.merge(current, on="symbol", how="left")
    plan["shares"] = pd.to_numeric(plan.get("shares", 0), errors="coerce").fillna(0)
    plan["target_notional"] = plan["target_weight"] * config.account_value
    plan["target_shares"] = (plan["target_notional"] / plan["adj_close"]).map(
        lambda value: math.floor(value) if pd.notna(value) and value > 0 else 0
    )
    plan["delta_shares"] = plan["target_shares"] - plan["shares"]
    plan["estimated_notional"] = (plan["delta_shares"].abs() * plan["adj_close"]).fillna(0)
    plan["side"] = plan["delta_shares"].map(lambda value: "BUY" if value > 0 else "SELL" if value < 0 else "HOLD")
    orders = plan[plan["delta_shares"] != 0][
        ["date", "symbol", "side", "delta_shares", "adj_close", "estimated_notional", "target_weight"]
    ].rename(columns={"date": "target_date", "adj_close": "reference_price"})
    checks = _checks(orders, config)
    return {
        "orders": orders.reset_index(drop=True),
        "checks": checks,
        "approved": all(bool(check["passed"]) for check in checks),
        "target_date": str(latest_date.date()),
        "account_value": config.account_value,
    }


def write_paper_order_plan(plan: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    orders = plan.get("orders")
    if isinstance(orders, pd.DataFrame):
        orders.to_csv(output_dir / "proposed_orders.csv", index=False)
    audit = {key: value for key, value in plan.items() if key != "orders"}
    (output_dir / "paper_trading_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")


def load_current_positions(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return _empty_current_positions()
    frame = pd.read_csv(path)
    missing = {"symbol", "shares"} - set(frame.columns)
    if missing:
        raise ValueError(f"Current positions file missing columns: {sorted(missing)}")
    return frame[["symbol", "shares"]].copy()


def _checks(orders: pd.DataFrame, config: PaperTradingConfig) -> list[dict[str, Any]]:
    if orders.empty:
        return [{"passed": True, "code": "no_orders", "message": "No order changes required"}]
    max_notional = float(orders["estimated_notional"].max())
    gross_notional = float(orders["estimated_notional"].sum())
    return [
        {
            "passed": max_notional <= config.max_order_notional,
            "code": "max_order_notional",
            "message": f"Max order notional {max_notional:.2f} <= {config.max_order_notional:.2f}",
        },
        {
            "passed": gross_notional <= config.account_value,
            "code": "gross_order_notional",
            "message": f"Gross order notional {gross_notional:.2f} <= account value {config.account_value:.2f}",
        },
    ]


def _empty_current_positions() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "shares"])
