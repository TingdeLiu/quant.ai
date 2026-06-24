from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import NotificationConfig

SEVERITY_RANK = {"info": 1, "warning": 2, "critical": 3}


def build_notifications(
    alerts: list[dict[str, Any]],
    config: NotificationConfig,
    run_id: str | None = None,
    report_dir: Path | None = None,
) -> list[dict[str, Any]]:
    if not config.enabled:
        return []
    min_rank = SEVERITY_RANK.get(config.min_severity, 2)
    selected = [alert for alert in alerts if SEVERITY_RANK.get(str(alert.get("severity", "info")), 1) >= min_rank]
    notifications = []
    for alert in selected:
        notifications.append(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "run_id": run_id,
                "report_dir": str(report_dir) if report_dir is not None else None,
                "channel_status": {},
                "alert": alert,
            }
        )
    return notifications


def dispatch_notifications(
    notifications: list[dict[str, Any]],
    config: NotificationConfig,
    output_dir: Path,
) -> list[dict[str, Any]]:
    if not notifications:
        write_notifications([], output_dir)
        return []
    dispatched = []
    for notification in notifications:
        record = dict(notification)
        statuses: dict[str, Any] = {}
        if "file" in config.channels:
            statuses["file"] = {"status": "queued"}
        if "webhook" in config.channels:
            statuses["webhook"] = _send_webhook(record, config.webhook_url_env)
        record["channel_status"] = statuses
        dispatched.append(record)
    write_notifications(dispatched, output_dir)
    if "file" in config.channels:
        append_outbox(dispatched, config.output_dir)
    return dispatched


def write_notifications(notifications: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"total": len(notifications), "notifications": notifications}
    (output_dir / "notifications.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _flatten(notifications).to_csv(output_dir / "notifications.csv", index=False)


def append_outbox(notifications: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "notification_outbox.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    else:
        existing = []
    path.write_text(json.dumps([*notifications, *existing][:500], indent=2, default=str), encoding="utf-8")
    _flatten([*notifications, *existing][:500]).to_csv(output_dir / "notification_outbox.csv", index=False)


def _send_webhook(notification: dict[str, Any], env_name: str) -> dict[str, Any]:
    url = os.environ.get(env_name)
    if not url:
        return {"status": "skipped_missing_env", "env": env_name}
    payload = json.dumps(notification, default=str).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {"status": "sent", "http_status": response.status}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "failed", "error": str(exc)}


def _flatten(notifications: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for notification in notifications:
        alert = notification.get("alert", {})
        rows.append(
            {
                "created_at": notification.get("created_at"),
                "run_id": notification.get("run_id"),
                "report_dir": notification.get("report_dir"),
                "severity": alert.get("severity") if isinstance(alert, dict) else None,
                "code": alert.get("code") if isinstance(alert, dict) else None,
                "message": alert.get("message") if isinstance(alert, dict) else None,
                "channel_status": json.dumps(notification.get("channel_status", {}), default=str),
            }
        )
    return pd.DataFrame(rows)
