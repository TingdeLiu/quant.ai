from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pandas as pd
from _helpers import _config, _write_audit, _write_equity

from quant_agent.alerts import alert_summary, build_alerts
from quant_agent.approvals import approve_paper_orders, load_approval, reject_paper_orders
from quant_agent.broker import PaperBroker
from quant_agent.comparison import write_strategy_comparison
from quant_agent.config import parse_config
from quant_agent.notifications import build_notifications, dispatch_notifications
from quant_agent.server import (
    OperationAuditLog,
    RunHistory,
    RuntimeStatus,
    _config_for_run,
    _handler_factory,
    build_home_html,
)


def test_paper_broker_preview_does_not_submit() -> None:
    orders = pd.DataFrame({"symbol": ["AAA"], "side": ["BUY"], "delta_shares": [10]})
    broker = PaperBroker()
    preview = broker.preview_orders(orders)
    assert preview.loc[0, "status"] == "preview"
    assert broker.audit_log == []


def test_alerts_capture_metric_and_data_quality_breaches(tmp_path: Path) -> None:
    config = _config(tmp_path)
    result = {
        "metrics": {"max_drawdown": -0.6, "sharpe": 0.1},
        "data_quality": {"summary": {"stale_rows": 3, "missing_universe_symbols": ["MISS"], "point_in_time_ready": False}},
        "paper_order_plan": {"approved": False, "checks": [{"passed": False, "code": "gross"}]},
    }
    alerts = build_alerts(result, [{"passed": False, "code": "risk", "message": "failed"}], config.alerts)
    codes = {alert["code"] for alert in alerts}
    assert "max_drawdown_breach" in codes
    assert "low_sharpe" in codes
    assert "stale_price_rows" in codes
    assert "paper_order_plan_not_approved" in codes
    assert alert_summary(alerts)["highest_severity"] == "critical"


def test_notifications_write_outbox(tmp_path: Path) -> None:
    config = _config(tmp_path)
    alerts = [
        {"severity": "info", "code": "note", "message": "note"},
        {"severity": "warning", "code": "warn", "message": "warn"},
    ]
    notifications = build_notifications(alerts, config.notifications, run_id="run-1", report_dir=tmp_path / "reports")
    dispatched = dispatch_notifications(notifications, config.notifications, tmp_path / "reports")
    assert len(dispatched) == 1
    assert (tmp_path / "reports" / "notifications.json").exists()
    assert (config.notifications.output_dir / "notification_outbox.json").exists()


def test_paper_order_approval_flow(tmp_path: Path) -> None:
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    pd.DataFrame(
        [{"target_date": "2024-01-02", "symbol": "AAA", "side": "BUY", "delta_shares": 10, "reference_price": 100}]
    ).to_csv(report_dir / "proposed_orders.csv", index=False)
    (report_dir / "paper_trading_audit.json").write_text(
        json.dumps({"checks": [{"passed": True, "code": "ok"}], "approved": True}),
        encoding="utf-8",
    )
    approval = approve_paper_orders(report_dir, approver="tester", comment="ok")
    assert approval["status"] == "approved"
    assert (report_dir / "broker_preview.csv").exists()
    assert load_approval(report_dir)["status"] == "approved"
    rejected = reject_paper_orders(report_dir, approver="tester", comment="no")
    assert rejected["status"] == "rejected"


def test_runtime_status_store_and_home_html(tmp_path: Path) -> None:
    history = RunHistory(tmp_path / "run_history.json")
    history.append({"run_id": "run-1", "status": "success", "report_dir": str(tmp_path / "runs" / "run-1")})
    status = RuntimeStatus(tmp_path / "runtime_status.json", history)
    status.write({"running": False, "last_status": "success", "config": "configs/full_roadmap.yaml"})
    config = _config(tmp_path)
    html = build_home_html(config, status.read(), history.read())
    assert "Quant Agent Control" in html
    assert "Quant Agent 控制台" in html
    assert "setLanguage('zh')" in html
    assert "/api/run" in html
    assert "api-token" in html
    assert "run-1" in html
    assert status.read()["last_status"] == "success"


def test_dashboard_run_config_uses_configured_runs_dir(tmp_path: Path) -> None:
    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["SPY"]},
            "report": {"output_dir": "reports/current"},
            "dashboard": {
                "enabled": True,
                "output_path": "reports/current/dashboard.html",
                "service_dir": "reports/service",
                "runs_dir": "reports/runs",
            },
            "paper_trading": {"enabled": True, "output_dir": "reports/paper"},
        },
        base=tmp_path,
    )
    run_config = _config_for_run(config, "run-1")
    assert run_config.report.output_dir == tmp_path / "reports/runs/run-1"
    assert run_config.dashboard.output_path == tmp_path / "reports/runs/run-1/dashboard.html"
    assert run_config.paper_trading.output_dir == tmp_path / "reports/runs/run-1/paper"


def test_dashboard_api_requires_token_and_audits_denials(tmp_path: Path) -> None:
    class FakeStatus:
        def __init__(self) -> None:
            self.started = False

        def read(self) -> dict[str, object]:
            return {"running": False, "last_status": "idle"}

        def start_job(self, config_path: Path) -> bool:
            self.started = True
            return True

    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["SPY"]},
            "report": {"output_dir": "reports"},
            "dashboard_security": {
                "enabled": True,
                "token": "test-token",
                "audit_log_path": "reports/dashboard_audit.jsonl",
            },
        },
        base=tmp_path,
    )
    history = RunHistory(tmp_path / "reports" / "run_history.json")
    status = FakeStatus()
    audit_log = OperationAuditLog(config.dashboard_security.audit_log_path)
    handler = _handler_factory(
        config_path=tmp_path / "config.yaml",
        config=config,
        status=status,
        history=history,
        audit_log=audit_log,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        try:
            urllib.request.urlopen(base_url + "/api/status")
            raise AssertionError("Expected unauthorized API request to fail")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401

        request = urllib.request.Request(
            base_url + "/api/status",
            headers={"Authorization": "Bearer test-token"},
        )
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["last_status"] == "idle"

        request = urllib.request.Request(
            base_url + "/api/run",
            headers={"Authorization": "Bearer test-token"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 202
        assert status.started

        request = urllib.request.Request(
            base_url + "/api/operation-audit",
            headers={"Authorization": "Bearer test-token"},
        )
        with urllib.request.urlopen(request) as response:
            records = json.loads(response.read().decode("utf-8"))
        assert records[-2]["action"] == "api_read"
        assert records[-2]["status"] == "unauthorized"
        assert records[-1]["action"] == "run_backtest"
        assert records[-1]["status"] == "accepted"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_write_strategy_comparison(tmp_path: Path) -> None:
    first = _write_audit(tmp_path / "first", total_return=0.1, sharpe=1.0, test_return=0.05)
    second = _write_audit(tmp_path / "second", total_return=0.2, sharpe=1.5, test_return=0.08)
    _write_equity(first)
    _write_equity(second)
    comparison = write_strategy_comparison([first, second], tmp_path / "comparison")
    assert list(comparison["name"]) == ["first", "second"]
    assert (tmp_path / "comparison" / "strategy_comparison.csv").exists()
    markdown = (tmp_path / "comparison" / "strategy_comparison.md").read_text(encoding="utf-8")
    assert "equity_comparison.svg" in markdown
    assert (tmp_path / "comparison" / "equity_comparison.svg").exists()
    assert (tmp_path / "comparison" / "drawdown_comparison.svg").exists()
    html = (tmp_path / "comparison" / "index.html").read_text(encoding="utf-8")
    assert "Strategy Comparison" in html
    assert "equity_comparison.svg" in html
