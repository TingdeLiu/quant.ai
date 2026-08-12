from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from _helpers import _config

from quant_agent.alerts import alert_summary, build_alerts
from quant_agent.config import parse_config
from quant_agent.console import render_console_html
from quant_agent.notifications import build_notifications, dispatch_notifications
from quant_agent.server import (
    OperationAuditLog,
    RunHistory,
    RuntimeStatus,
    _config_for_run,
    _handler_factory,
)


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


def test_runtime_status_store_and_console_html(tmp_path: Path) -> None:
    history = RunHistory(tmp_path / "run_history.json")
    history.append({"run_id": "run-1", "status": "success", "report_dir": str(tmp_path / "runs" / "run-1")})
    status = RuntimeStatus(tmp_path / "runtime_status.json", history)
    status.write({"running": False, "last_status": "success", "config": "configs/full_roadmap.yaml"})
    config = _config(tmp_path)
    html = render_console_html(config, status.read(), history.read())

    # 四个标签页（原 /console 与 /dashboard 已并进来），用 cs 组名。
    for label in ("Report", "Markets", "Backtest", "Ops"):
        assert f">{label}<" in html or f">{label}<span" in html
    assert 'name="cs-tabsel"' in html
    # 运行页的控制项与历史。
    assert "/api/run" in html
    assert "/api/market-report" in html
    assert "run-1" in html
    assert status.read()["last_status"] == "success"
    # 复用报告的视觉，不再自带一套 CSS。
    assert "qa-report" in html and "--orange" in html


def test_console_tabs_do_not_collide_with_embedded_report(tmp_path: Path) -> None:
    """报告自带一层标签页；两层 radio 同名会互相清掉选中态，必须用不同的组名。"""
    history = RunHistory(tmp_path / "run_history.json")
    status = RuntimeStatus(tmp_path / "runtime_status.json", history)
    status.write({"running": False, "last_status": "idle"})
    config = _config(tmp_path)
    report = {
        "language": "en",
        "as_of_date": "2026-08-12",
        "data_status": "ok",
        "generated_at": "2026-08-12T00:00:00",
        "disclaimer": "Research only.",
        "market_overview": {"symbols_analyzed": 3},
        "warnings": ["synthetic"],
    }
    html = render_console_html(config, status.read(), history.read(), report=report)
    assert 'name="cs-tabsel"' in html, "外层控制台用 cs 组"
    assert 'name="qa-tabsel"' in html, "内嵌报告保留 qa 组"
    # 报告的免责声明与数据日期必须跟着内容走，不能只留控制台自己的页眉。
    assert "Research only." in html
    assert "2026-08-12" in html


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


def test_legacy_page_urls_redirect_to_console(tmp_path: Path) -> None:
    """/console、/dashboard、/markets 三个旧页面已并进 /，保留重定向不让老书签 404。"""
    config = _config(tmp_path)
    history = RunHistory(tmp_path / "reports" / "run_history.json")
    status = RuntimeStatus(tmp_path / "reports" / "runtime_status.json", history)
    handler = _handler_factory(
        config_path=tmp_path / "config.yaml",
        config=config,
        status=status,
        history=history,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args: object, **kwargs: object) -> None:
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        for path in ("/console", "/dashboard", "/markets", "/m/ui_kits/markets/index.html"):
            try:
                opener.open(base_url + path)
                raise AssertionError(f"{path} 应当重定向而不是直接返回")
            except urllib.error.HTTPError as exc:
                assert exc.code == 302, f"{path} -> {exc.code}"
                assert exc.headers["Location"] == "/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
