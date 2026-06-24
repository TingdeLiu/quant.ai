from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.broker import PaperBroker

APPROVAL_FILE = "paper_order_approval.json"
BROKER_PREVIEW_FILE = "broker_preview.csv"


def approve_paper_orders(
    report_dir: Path,
    approver: str = "local_operator",
    comment: str = "",
    allow_submit: bool = False,
) -> dict[str, Any]:
    orders = _load_orders(report_dir)
    audit = _load_audit(report_dir)
    checks = audit.get("checks", []) if isinstance(audit, dict) else []
    if not all(bool(check.get("passed")) for check in checks):
        record = _record("rejected", approver, comment or "Cannot approve failed paper order checks.", report_dir)
        record["checks"] = checks
        _write_record(report_dir, record)
        return record
    broker = PaperBroker(allow_submit=allow_submit)
    preview = broker.preview_orders(orders)
    preview.to_csv(report_dir / BROKER_PREVIEW_FILE, index=False)
    record = _record("approved", approver, comment, report_dir)
    record["checks"] = checks
    record["broker_preview_file"] = BROKER_PREVIEW_FILE
    record["order_count"] = int(len(orders))
    _write_record(report_dir, record)
    return record


def reject_paper_orders(report_dir: Path, approver: str = "local_operator", comment: str = "") -> dict[str, Any]:
    record = _record("rejected", approver, comment, report_dir)
    _write_record(report_dir, record)
    return record


def load_approval(report_dir: Path) -> dict[str, Any]:
    path = report_dir / APPROVAL_FILE
    if not path.exists():
        return {"status": "pending", "report_dir": str(report_dir)}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_orders(report_dir: Path) -> pd.DataFrame:
    path = report_dir / "proposed_orders.csv"
    if not path.exists():
        raise FileNotFoundError(f"Proposed orders file not found: {path}")
    return pd.read_csv(path)


def _load_audit(report_dir: Path) -> dict[str, Any]:
    path = report_dir / "paper_trading_audit.json"
    if not path.exists():
        raise FileNotFoundError(f"Paper trading audit file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _record(status: str, approver: str, comment: str, report_dir: Path) -> dict[str, Any]:
    return {
        "status": status,
        "approver": approver,
        "comment": comment,
        "approved_at": datetime.now(UTC).isoformat() if status == "approved" else None,
        "rejected_at": datetime.now(UTC).isoformat() if status == "rejected" else None,
        "report_dir": str(report_dir),
    }


def _write_record(report_dir: Path, record: dict[str, Any]) -> None:
    (report_dir / APPROVAL_FILE).write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
