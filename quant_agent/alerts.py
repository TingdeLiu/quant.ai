from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import AlertConfig


def build_alerts(result: dict[str, Any], risk_checks: list[dict[str, object]], config: AlertConfig) -> list[dict[str, Any]]:
    if not config.enabled:
        return []
    alerts: list[dict[str, Any]] = []
    metrics = result.get("metrics", {})
    if isinstance(metrics, dict):
        max_drawdown = _float(metrics.get("max_drawdown"))
        if max_drawdown is not None and max_drawdown < config.max_drawdown_floor:
            alerts.append(
                _alert(
                    "critical",
                    "max_drawdown_breach",
                    f"Max drawdown {max_drawdown:.2%} is below floor {config.max_drawdown_floor:.2%}.",
                    {"max_drawdown": max_drawdown, "floor": config.max_drawdown_floor},
                    "Review strategy exposure, risk limits, and recent drawdown drivers before any paper/live promotion.",
                )
            )
        sharpe = _float(metrics.get("sharpe"))
        if sharpe is not None and sharpe < config.min_sharpe:
            alerts.append(
                _alert(
                    "warning",
                    "low_sharpe",
                    f"Sharpe {sharpe:.2f} is below threshold {config.min_sharpe:.2f}.",
                    {"sharpe": sharpe, "threshold": config.min_sharpe},
                    "Inspect period metrics and signal diagnostics for regime dependence.",
                )
            )

    for check in risk_checks:
        if not bool(check.get("passed")):
            alerts.append(
                _alert(
                    "critical",
                    f"risk_check_failed:{check.get('code')}",
                    str(check.get("message", "Risk check failed.")),
                    {"check": check},
                    "Do not generate orders until the risk check is resolved.",
                )
            )

    data_quality = result.get("data_quality", {})
    if isinstance(data_quality, dict):
        summary = data_quality.get("summary", {})
        if isinstance(summary, dict):
            stale_rows = int(summary.get("stale_rows", 0) or 0)
            if stale_rows > config.max_stale_rows:
                alerts.append(
                    _alert(
                        "warning",
                        "stale_price_rows",
                        f"Detected {stale_rows} stale price rows; threshold is {config.max_stale_rows}.",
                        {"stale_rows": stale_rows, "threshold": config.max_stale_rows},
                        "Refresh data and inspect symbols with repeated unchanged adjusted close values.",
                    )
                )
            missing = summary.get("missing_universe_symbols", [])
            if missing:
                alerts.append(
                    _alert(
                        "warning",
                        "missing_universe_symbols",
                        f"Missing universe symbols: {', '.join(map(str, missing))}.",
                        {"symbols": missing},
                        "Check data coverage before trusting cross-sectional rankings.",
                    )
                )
            if not summary.get("point_in_time_ready", False):
                alerts.append(
                    _alert(
                        "info",
                        "point_in_time_metadata_missing",
                        "No point-in-time metadata columns were detected.",
                        {"expected_columns": ["as_of_date", "effective_date", "announcement_date"]},
                        "Use point-in-time data columns before promoting research to production.",
                    )
                )

    paper_plan = result.get("paper_order_plan", {})
    if config.require_paper_approval and isinstance(paper_plan, dict) and not paper_plan.get("approved", True):
        alerts.append(
            _alert(
                "critical",
                "paper_order_plan_not_approved",
                "Paper order plan failed approval checks.",
                {"checks": paper_plan.get("checks", [])},
                "Resolve order sizing or account constraints before submitting paper orders.",
            )
        )

    return alerts


def alert_summary(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    severity_order = {"critical": 3, "warning": 2, "info": 1}
    highest = "none"
    for alert in alerts:
        severity = str(alert.get("severity", "info"))
        if severity_order.get(severity, 0) > severity_order.get(highest, 0):
            highest = severity
    counts = {severity: 0 for severity in ["critical", "warning", "info"]}
    for alert in alerts:
        severity = str(alert.get("severity", "info"))
        counts[severity] = counts.get(severity, 0) + 1
    return {"total": len(alerts), "highest_severity": highest, "counts": counts}


def write_alerts(alerts: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"summary": alert_summary(alerts), "alerts": alerts}
    (output_dir / "alerts.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(alerts).to_csv(output_dir / "alerts.csv", index=False)
    (output_dir / "alerts.md").write_text(_markdown(payload), encoding="utf-8")


def _alert(severity: str, code: str, message: str, details: dict[str, Any], action: str) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": severity,
        "code": code,
        "message": message,
        "details": details,
        "recommended_action": action,
    }


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    alerts = payload.get("alerts", [])
    lines = [
        "# Alerts",
        "",
        f"- Total: {summary.get('total', 0)}",
        f"- Highest severity: {summary.get('highest_severity', 'none')}",
        "",
        "| severity | code | message | recommended_action |",
        "| --- | --- | --- | --- |",
    ]
    for alert in alerts:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(alert.get("severity", "")),
                    str(alert.get("code", "")),
                    str(alert.get("message", "")).replace("|", "\\|"),
                    str(alert.get("recommended_action", "")).replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
