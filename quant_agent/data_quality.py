from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

PIT_COLUMNS = ["as_of_date", "effective_date", "announcement_date"]
CORPORATE_ACTION_COLUMNS = ["split_coefficient", "dividend", "capital_gain"]


def build_data_quality_report(prices: pd.DataFrame, universe: list[str]) -> dict[str, Any]:
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    expected = set(universe)
    present = set(frame["symbol"].astype(str).unique())
    symbol_summary = (
        frame.groupby("symbol")
        .agg(
            rows=("date", "count"),
            first_date=("date", "min"),
            last_date=("date", "max"),
            missing_adj_close=("adj_close", lambda s: int(s.isna().sum())),
            missing_volume=("volume", lambda s: int(s.isna().sum())),
        )
        .reset_index()
        .sort_values("symbol")
    )
    duplicate_rows = int(frame.duplicated(["date", "symbol"]).sum())
    stale_rows = _stale_row_count(frame)
    non_positive_prices = int((frame[["open", "high", "low", "close", "adj_close"]] <= 0).any(axis=1).sum())
    negative_volume = int((frame["volume"] < 0).sum())
    pit_columns = [column for column in PIT_COLUMNS if column in frame.columns]
    corporate_action_columns = [column for column in CORPORATE_ACTION_COLUMNS if column in frame.columns]
    return {
        "summary": {
            "rows": int(len(frame)),
            "symbols": int(len(present)),
            "first_date": str(frame["date"].min().date()) if not frame.empty else None,
            "last_date": str(frame["date"].max().date()) if not frame.empty else None,
            "duplicate_rows": duplicate_rows,
            "stale_rows": stale_rows,
            "non_positive_price_rows": non_positive_prices,
            "negative_volume_rows": negative_volume,
            "missing_universe_symbols": sorted(expected - present),
            "extra_symbols": sorted(present - expected) if expected else [],
            "pit_columns": pit_columns,
            "corporate_action_columns": corporate_action_columns,
            "point_in_time_ready": bool(pit_columns),
            "corporate_actions_present": bool(corporate_action_columns),
        },
        "symbol_summary": symbol_summary,
        "issues": _issues(
            duplicate_rows=duplicate_rows,
            stale_rows=stale_rows,
            non_positive_prices=non_positive_prices,
            negative_volume=negative_volume,
            missing_symbols=sorted(expected - present),
            pit_columns=pit_columns,
        ),
    }


def write_data_quality_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    symbol_summary = report.get("symbol_summary")
    if isinstance(symbol_summary, pd.DataFrame):
        symbol_summary.to_csv(output_dir / "data_quality_by_symbol.csv", index=False)
    payload = {
        "summary": report.get("summary", {}),
        "issues": report.get("issues", []),
    }
    (output_dir / "data_quality.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (output_dir / "data_quality.md").write_text(_markdown(payload), encoding="utf-8")


def _stale_row_count(frame: pd.DataFrame) -> int:
    stale = 0
    for _, group in frame.sort_values(["symbol", "date"]).groupby("symbol"):
        stale += int((group["adj_close"].diff().fillna(1) == 0).sum())
    return stale


def _issues(
    duplicate_rows: int,
    stale_rows: int,
    non_positive_prices: int,
    negative_volume: int,
    missing_symbols: list[str],
    pit_columns: list[str],
) -> list[dict[str, Any]]:
    rows = [
        {"severity": "error", "code": "duplicate_rows", "count": duplicate_rows, "passed": duplicate_rows == 0},
        {
            "severity": "error",
            "code": "non_positive_prices",
            "count": non_positive_prices,
            "passed": non_positive_prices == 0,
        },
        {"severity": "error", "code": "negative_volume", "count": negative_volume, "passed": negative_volume == 0},
        {"severity": "warning", "code": "stale_prices", "count": stale_rows, "passed": stale_rows == 0},
        {
            "severity": "warning",
            "code": "missing_universe_symbols",
            "symbols": missing_symbols,
            "passed": not missing_symbols,
        },
        {
            "severity": "info",
            "code": "point_in_time_columns",
            "columns": pit_columns,
            "passed": bool(pit_columns),
        },
    ]
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    issues = payload.get("issues", [])
    lines = ["# Data Quality Report", "", "## Summary", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issues", "", "| severity | code | passed | detail |", "| --- | --- | --- | --- |"])
    for issue in issues:
        detail = {k: v for k, v in issue.items() if k not in {"severity", "code", "passed"}}
        lines.append(
            f"| {issue.get('severity')} | {issue.get('code')} | {issue.get('passed')} | {json.dumps(detail, default=str)} |"
        )
    return "\n".join(lines) + "\n"
