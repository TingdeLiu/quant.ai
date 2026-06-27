from __future__ import annotations

import contextlib
import hmac
import json
import os
import sys
import threading
import traceback
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from quant_agent.approvals import approve_paper_orders, load_approval, reject_paper_orders
from quant_agent.config import AppConfig, DashboardSecurityConfig, ReportConfig, load_config
from quant_agent.dashboard import write_dashboard
from quant_agent.i18n import normalize_language, tr
from quant_agent.llm import generate_chat_reply
from quant_agent.market_intel import build_market_report, write_market_report
from quant_agent.markets_data import build_markets_data
from quant_agent.pipeline import run_research_backtest
from quant_agent.web_templates import build_home_html

STATUS_FILE = "runtime_status.json"
HISTORY_FILE = "run_history.json"
MARKET_INTEL_STATUS_FILE = "market_intel_status.json"
WEB_DIR = Path(__file__).resolve().parent / "web"
MARKETS_INDEX_REL = "ui_kits/markets/index.html"


class RunHistory:
    def __init__(self, history_path: Path):
        self.history_path = history_path
        self._lock = threading.Lock()
        if not history_path.exists():
            self.write([])

    def read(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.history_path.exists():
                return []
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []

    def write(self, records: list[dict[str, Any]]) -> None:
        with self._lock:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        with self._lock:
            if self.history_path.exists():
                records = json.loads(self.history_path.read_text(encoding="utf-8"))
                if not isinstance(records, list):
                    records = []
            else:
                records = []
            records.insert(0, record)
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(json.dumps(records[:250], indent=2, default=str), encoding="utf-8")

    def get(self, run_id: str) -> dict[str, Any] | None:
        for record in self.read():
            if record.get("run_id") == run_id:
                return record
        return None


class RuntimeStatus:
    def __init__(self, status_path: Path, history: RunHistory):
        self.status_path = status_path
        self.history = history
        self._lock = threading.Lock()
        self._running = False
        if not self.status_path.exists():
            self.write(
                {
                    "running": False,
                    "last_started_at": None,
                    "last_finished_at": None,
                    "last_status": "idle",
                    "last_error": None,
                    "report_dir": None,
                    "last_run_id": None,
                }
            )

    def read(self) -> dict[str, Any]:
        with self._lock:
            if not self.status_path.exists():
                return {}
            return json.loads(self.status_path.read_text(encoding="utf-8"))

    def write(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            self.status_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def start_job(self, config_path: Path) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
        thread = threading.Thread(target=self._run_job, args=(config_path,), daemon=True)
        thread.start()
        return True

    def _run_job(self, config_path: Path) -> None:
        started = _now()
        run_id = _run_id()
        self.write(
            {
                "running": True,
                "last_started_at": started,
                "last_finished_at": None,
                "last_status": "running",
                "last_error": None,
                "config": str(config_path),
                "report_dir": None,
                "last_run_id": run_id,
            }
        )
        try:
            config = load_config(config_path)
            run_config = _config_for_run(config, run_id)
            run_research_backtest(run_config)
            finished = _now()
            record = _run_record(
                run_id=run_id,
                status="success",
                started_at=started,
                finished_at=finished,
                config_path=config_path,
                report_dir=run_config.report.output_dir,
            )
            self.history.append(record)
            self.write(
                {
                    "running": False,
                    "last_started_at": started,
                    "last_finished_at": finished,
                    "last_status": "success",
                    "last_error": None,
                    "config": str(config_path),
                    "report_dir": str(run_config.report.output_dir),
                    "last_run_id": run_id,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive runtime path
            finished = _now()
            self.history.append(
                _run_record(
                    run_id=run_id,
                    status="failed",
                    started_at=started,
                    finished_at=finished,
                    config_path=config_path,
                    report_dir=None,
                    error=str(exc),
                )
            )
            self.write(
                {
                    "running": False,
                    "last_started_at": started,
                    "last_finished_at": finished,
                    "last_status": "failed",
                    "last_error": str(exc),
                    "traceback": traceback.format_exc(),
                    "config": str(config_path),
                    "report_dir": None,
                    "last_run_id": run_id,
                }
            )
        finally:
            with self._lock:
                self._running = False


class MarketIntelJob:
    """Background runner for the daily market intelligence report."""

    def __init__(self, config: AppConfig, status_path: Path):
        self.config = config
        self.status_path = status_path
        self.output_dir = config.market_intel.output_dir
        self._lock = threading.Lock()
        self._running = False

    def read_status(self) -> dict[str, Any]:
        if not self.status_path.exists():
            return {"running": False, "last_status": "idle", "last_finished_at": None}
        try:
            return json.loads(self.status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"running": False, "last_status": "idle"}

    def read_report(self) -> dict[str, Any]:
        return _load_json(self.output_dir / "market_intel.json")

    def _write_status(self, payload: dict[str, Any]) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
        self._write_status({"running": True, "last_status": "running", "last_started_at": _now(), "last_finished_at": None, "last_error": None})
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return True

    def _run(self) -> None:
        started = _now()
        try:
            report = build_market_report(self.config)
            write_market_report(report, self.output_dir)
            self._write_status(
                {
                    "running": False,
                    "last_status": "success",
                    "last_started_at": started,
                    "last_finished_at": _now(),
                    "last_error": None,
                    "data_status": report.get("data_status"),
                    "as_of_date": report.get("as_of_date"),
                    "buy_candidates": len(report.get("buy_candidates", [])),
                    "high_risk": len(report.get("high_risk", [])),
                    "news_items": len(report.get("news", [])),
                    "report_path": str(self.output_dir / "market_intel.html"),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive runtime path
            self._write_status(
                {
                    "running": False,
                    "last_status": "failed",
                    "last_started_at": started,
                    "last_finished_at": _now(),
                    "last_error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
        finally:
            with self._lock:
                self._running = False


class OperationAuditLog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def append(
        self,
        action: str,
        *,
        status: str,
        request: BaseHTTPRequestHandler | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "timestamp": _now(),
            "action": action,
            "status": status,
            "client": _client_address(request),
            "path": request.path if request is not None else None,
            "details": details or {},
        }
        line = json.dumps(record, default=str, sort_keys=True)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def read(self, limit: int = 250) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        records: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                records.append(data)
        return records


class Scheduler:
    def __init__(self, config_path: Path, config: AppConfig, status: RuntimeStatus):
        self.config_path = config_path
        self.config = config
        self.status = status
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.config.schedule.enabled:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        if self.config.schedule.run_on_start:
            self.status.start_job(self.config_path)
        interval = max(self.config.schedule.interval_minutes, 1) * 60
        while not self._stop.wait(interval):
            self.status.start_job(self.config_path)


def run_dashboard_server(config_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    config = load_config(config_path)
    history = RunHistory(config.dashboard.service_dir / HISTORY_FILE)
    status = RuntimeStatus(config.dashboard.service_dir / STATUS_FILE, history)
    audit_log = OperationAuditLog(config.dashboard_security.audit_log_path)
    market_intel = MarketIntelJob(config, config.dashboard.service_dir / MARKET_INTEL_STATUS_FILE)
    scheduler = Scheduler(config_path, config, status)
    scheduler.start()
    handler = _handler_factory(
        config_path=config_path,
        config=config,
        status=status,
        history=history,
        audit_log=audit_log,
        market_intel=market_intel,
    )
    server = ThreadingHTTPServer((host, port), handler)
    _safe_print(f"Quant Agent dashboard listening on http://{host}:{port}")
    server.serve_forever()


def _handler_factory(
    config_path: Path,
    config: AppConfig,
    status: RuntimeStatus,
    history: RunHistory,
    audit_log: OperationAuditLog | None = None,
    market_intel: MarketIntelJob | None = None,
) -> type[BaseHTTPRequestHandler]:
    report_dir = config.report.output_dir
    audit_log = audit_log or OperationAuditLog(config.dashboard_security.audit_log_path)
    market_intel = market_intel or MarketIntelJob(config, config.dashboard.service_dir / MARKET_INTEL_STATUS_FILE)

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._send_markets_app()
            elif path == "/console":
                self._send_html(build_home_html(config, status.read(), history.read()))
            elif path == "/dashboard":
                self._send_file(report_dir / "dashboard.html", "text/html; charset=utf-8")
            elif path == "/markets" or path == "/m/" + MARKETS_INDEX_REL:
                self._send_markets_app()
            elif path.startswith("/m/"):
                self._send_web_static(unquote(path[len("/m/"):]))
            elif path.startswith("/api/") and not self._authorized("api_read"):
                return
            elif path == "/api/status":
                self._send_json(status.read())
            elif path == "/api/audit":
                self._send_json(_load_json(report_dir / "audit.json"))
            elif path == "/api/operation-audit":
                self._send_json(audit_log.read())
            elif path == "/api/files":
                self._send_json(_report_files(report_dir))
            elif path == "/api/alerts":
                self._send_json(_load_json(report_dir / "alerts.json"))
            elif path == "/api/notifications":
                self._send_json(_load_json(report_dir / "notifications.json"))
            elif path == "/api/market-report/status":
                self._send_json(market_intel.read_status())
            elif path == "/api/market-report":
                self._send_json(market_intel.read_report())
            elif path == "/api/markets-data":
                self._send_json(_safe_markets_data(config))
            elif path == "/market-report":
                self._send_file(market_intel.output_dir / "market_intel.html", "text/html; charset=utf-8")
            elif path == "/api/runs":
                self._send_json(history.read())
            elif path.startswith("/api/runs/"):
                self._send_run_api(path, history)
            elif path.startswith("/runs/"):
                self._send_run_file(path, history)
            elif path.startswith("/report/"):
                relative = unquote(path.removeprefix("/report/"))
                self._send_report_file(report_dir, relative)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path.startswith("/api/") and not self._authorized("api_write"):
                return
            if path == "/api/chat":
                self._handle_chat()
                return
            if path == "/api/run":
                started = status.start_job(config_path)
                code = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
                audit_log.append(
                    "run_backtest",
                    status="accepted" if started else "conflict",
                    request=self,
                    details={"config": str(config_path)},
                )
                self._send_json({"started": started, "status": status.read()}, code=code)
                return
            if path == "/api/market-report":
                started = market_intel.start()
                code = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
                audit_log.append(
                    "market_report",
                    status="accepted" if started else "conflict",
                    request=self,
                )
                self._send_json({"started": started, "status": market_intel.read_status()}, code=code)
                return
            if path.startswith("/api/runs/") and path.endswith("/approve-paper"):
                self._approve_run(path, history)
                return
            if path.startswith("/api/runs/") and path.endswith("/reject-paper"):
                self._reject_run(path, history)
                return
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

        def log_message(self, format: str, *args: object) -> None:
            return

        def _authorized(self, action: str) -> bool:
            if _request_authorized(self.headers, config.dashboard_security):
                return True
            audit_log.append(action, status="unauthorized", request=self)
            self._send_json({"error": "unauthorized"}, code=HTTPStatus.UNAUTHORIZED)
            return False

        def _send_html(self, html: str) -> None:
            payload = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, data: object, code: HTTPStatus = HTTPStatus.OK) -> None:
            payload = json.dumps(data, indent=2, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_report_file(self, root: Path, relative: str) -> None:
            target = (root / relative).resolve()
            root_resolved = root.resolve()
            if root_resolved not in target.parents and target != root_resolved:
                self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
                return
            self._send_file(target, _content_type(target))

        def _send_run_api(self, path: str, history_store: RunHistory) -> None:
            parts = [unquote(part) for part in path.split("/") if part]
            if len(parts) < 3:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            run_id = parts[2]
            record = history_store.get(run_id)
            if record is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            if len(parts) == 3:
                self._send_json(record)
                return
            if parts[3] == "approval":
                report = _report_dir_from_record(record)
                self._send_json(load_approval(report))
                return
            if parts[3] == "alerts":
                report = _report_dir_from_record(record)
                self._send_json(_load_json(report / "alerts.json"))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def _approve_run(self, path: str, history_store: RunHistory) -> None:
            record = _record_from_post_path(path, history_store, "approve-paper")
            if record is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            approval = approve_paper_orders(
                report_dir := _report_dir_from_record(record),
                approver="dashboard",
                comment="Approved from local dashboard API.",
                allow_submit=config.approvals.allow_broker_submit_after_approval,
            )
            write_dashboard(report_dir, report_dir / "dashboard.html", config.language)
            audit_log.append(
                "approve_paper_orders",
                status="success",
                request=self,
                details={"run_id": record.get("run_id"), "report_dir": str(report_dir)},
            )
            self._send_json(approval)

        def _reject_run(self, path: str, history_store: RunHistory) -> None:
            record = _record_from_post_path(path, history_store, "reject-paper")
            if record is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            approval = reject_paper_orders(
                report_dir := _report_dir_from_record(record),
                approver="dashboard",
                comment="Rejected from local dashboard API.",
            )
            write_dashboard(report_dir, report_dir / "dashboard.html", config.language)
            audit_log.append(
                "reject_paper_orders",
                status="success",
                request=self,
                details={"run_id": record.get("run_id"), "report_dir": str(report_dir)},
            )
            self._send_json(approval)

        def _send_run_file(self, path: str, history_store: RunHistory) -> None:
            parts = [unquote(part) for part in path.split("/") if part]
            if len(parts) < 2:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            run_id = parts[1]
            record = history_store.get(run_id)
            if record is None or not record.get("report_dir"):
                self.send_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            report_root = Path(str(record["report_dir"]))
            relative = "dashboard.html" if len(parts) == 3 and parts[2] == "dashboard" else "/".join(parts[2:])
            self._send_report_file(report_root, relative)

        def _send_file(self, path: Path, content_type: str) -> None:
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            payload = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _send_web_static(self, relative: str) -> None:
            target = (WEB_DIR / relative).resolve()
            if WEB_DIR not in target.parents and target != WEB_DIR:
                self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
                return
            self._send_file(target, _content_type(target))

        def _send_markets_app(self) -> None:
            index_path = WEB_DIR / MARKETS_INDEX_REL
            if not index_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "Markets UI not found")
                return
            html = index_path.read_text(encoding="utf-8")
            # Absolute <base> so the relative asset refs in index.html/chrome.jsx
            # (../../styles.css, chrome.jsx, in-JSX images) resolve regardless of
            # which URL serves this page ("/", "/markets", or the static path).
            base_dir = MARKETS_INDEX_REL.rsplit("/", 1)[0]
            html = html.replace("<head>", f'<head>\n<base href="/m/{base_dir}/">', 1)
            html = html.replace(
                '<script type="text/babel" src="chrome.jsx"></script>',
                _markets_data_script(config) + '\n<script type="text/babel" src="chrome.jsx"></script>',
                1,
            )
            self._send_html(html)

        def _handle_chat(self) -> None:
            body = self._read_json_body()
            if body is None:
                return
            symbol = str(body.get("symbol") or "").upper()
            raw = body.get("messages")
            messages: list[dict[str, str]] = []
            for item in raw if isinstance(raw, list) else []:
                if not isinstance(item, dict):
                    continue
                content = str(item.get("text") or item.get("content") or "").strip()
                if not content:
                    continue
                role = "assistant" if item.get("role") == "assistant" else "user"
                messages.append({"role": role, "content": content})
            if not messages:
                self._send_json({"error": "empty"}, code=HTTPStatus.BAD_REQUEST)
                return
            data = _safe_markets_data(config)
            lang = normalize_language(data.get("lang") or config.language)
            ticker = (data.get("TICKERS") or {}).get(symbol)
            system = _chat_system(lang) + "\n\n" + _chat_context(symbol, ticker, data, lang)
            text, meta = generate_chat_reply(config.llm, system, messages)
            offline = text is None
            if offline:
                text = _offline_chat_reply(messages[-1]["content"], symbol, ticker, lang)
            self._send_json(
                {"role": "assistant", "text": text, "offline": offline, "status": meta.get("status")}
            )

        def _read_json_body(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                length = 0
            raw = self.rfile.read(length) if length > 0 else b""
            if not raw:
                return {}
            try:
                data = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json({"error": "invalid_json"}, code=HTTPStatus.BAD_REQUEST)
                return None
            return data if isinstance(data, dict) else {}

    return DashboardHandler


def _report_files(report_dir: Path) -> list[dict[str, Any]]:
    if not report_dir.exists():
        return []
    rows = []
    for path in sorted(report_dir.iterdir()):
        if path.is_file():
            rows.append({"name": path.name, "size": path.stat().st_size})
    return rows


def _request_authorized(headers: Any, security: DashboardSecurityConfig) -> bool:
    if not security.enabled:
        return True
    expected = os.environ.get(security.token_env) or security.token
    if not expected:
        return False
    provided = headers.get("X-API-Token") or ""
    authorization = headers.get("Authorization") or ""
    if authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    return hmac.compare_digest(str(provided), str(expected))


def _client_address(request: BaseHTTPRequestHandler | None) -> str | None:
    if request is None:
        return None
    host, port = request.client_address
    return f"{host}:{port}"


def _config_for_run(config: AppConfig, run_id: str) -> AppConfig:
    run_dir = config.dashboard.runs_dir / run_id
    paper_dir = run_dir / "paper"
    dashboard_path = run_dir / "dashboard.html"
    return replace(
        config,
        report=ReportConfig(output_dir=run_dir),
        paper_trading=replace(config.paper_trading, output_dir=paper_dir),
        dashboard=replace(config.dashboard, output_path=dashboard_path),
    )


def _run_record(
    run_id: str,
    status: str,
    started_at: str,
    finished_at: str,
    config_path: Path,
    report_dir: Path | None,
    error: str | None = None,
) -> dict[str, Any]:
    audit = _load_json(report_dir / "audit.json") if report_dir is not None else {}
    alerts = _load_json(report_dir / "alerts.json") if report_dir is not None else {}
    metrics = audit.get("metrics", {}) if isinstance(audit, dict) else {}
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "config": str(config_path),
        "report_dir": str(report_dir) if report_dir is not None else None,
        "error": error,
        "total_return": metrics.get("total_return"),
        "sharpe": metrics.get("sharpe"),
        "max_drawdown": metrics.get("max_drawdown"),
        "alert_summary": alerts.get("summary", {}) if isinstance(alerts, dict) else {},
    }


def _record_from_post_path(path: str, history: RunHistory, action: str) -> dict[str, Any] | None:
    parts = [unquote(part) for part in path.split("/") if part]
    if len(parts) != 4 or parts[0] != "api" or parts[1] != "runs" or parts[3] != action:
        return None
    return history.get(parts[2])


def _report_dir_from_record(record: dict[str, Any]) -> Path:
    report_dir = record.get("report_dir")
    if not report_dir:
        raise FileNotFoundError("Run does not have a report_dir")
    return Path(str(report_dir))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    if suffix == ".csv":
        return "text/csv; charset=utf-8"
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".md":
        return "text/markdown; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix in (".js", ".jsx"):
        return "text/babel; charset=utf-8" if suffix == ".jsx" else "application/javascript; charset=utf-8"
    return "application/octet-stream"


def _safe_markets_data(config: AppConfig) -> dict[str, Any]:
    """Build the markets payload, degrading to an empty payload on any failure."""
    try:
        return build_markets_data(config)
    except Exception as exc:  # pragma: no cover - data/network dependent
        return {"TICKERS": {}, "WATCH": [], "PRICE": {}, "TFS": [], "defaultSym": None, "error": str(exc)}


def _markets_data_script(config: AppConfig) -> str:
    """Inline the real markets data so the dashboard renders it instead of placeholders."""
    data = _safe_markets_data(config)
    if not data.get("TICKERS"):
        return ""  # fall back to the seeded data bundled in chrome.jsx
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    return f"<script>window.MARKETS_DATA = {payload};</script>"


def _chat_system(lang: str) -> str:
    """System prompt for the dashboard AI analyst — research only, never order tickets."""
    if lang == "zh":
        return (
            "你是 Tyndall Lumen，一位严谨的美股量化研究助理。只能基于下方提供的量化数据与研究结论进行讨论，"
            "可以解释评级、多空逻辑、风险与各项指标的含义。这是研究与学习用途，不构成投资建议，"
            "绝不能给出下单指令、订单票、仓位指令或实盘交易授权。若被问到是否买入，请从研究角度说明依据与风险，"
            "并提醒用户自行做尽职调查。请用简洁、专业的中文回答，并尽量引用具体数字。"
        )
    return (
        "You are Tyndall Lumen, a rigorous US-equity quant research assistant. Discuss ONLY using the "
        "quantitative data and research read provided below; explain the rating, the bull/bear logic, the "
        "risks, and what the figures mean. This is research and education, not investment advice — never "
        "produce order tickets, broker instructions, position-sizing directives, or live-trading "
        "authorization. If asked whether to buy, frame the evidence and the risks from a research view and "
        "remind the user to do their own due diligence. Answer concisely and professionally, citing the "
        "specific figures."
    )


def _chat_context(symbol: str, ticker: dict[str, Any] | None, data: dict[str, Any], lang: str) -> str:
    """Compact, grounding context block appended to the system prompt for the chat."""
    lines = [tr("Data for this discussion:", "本次讨论的数据：", lang)]
    if data.get("as_of"):
        lines.append(tr(f"As-of date: {data['as_of']}", f"数据截止日：{data['as_of']}", lang))
    if data.get("brief"):
        lines.append(tr("Market brief: ", "市场简报：", lang) + str(data["brief"]))
    picks = data.get("picks") or []
    if picks:
        joined = "; ".join(
            f"{p.get('sym')} {p.get('ratingLabel')}/{p.get('stance')} ({_pct(p.get('chg'))})" for p in picks
        )
        lines.append(tr("Quant-screen watchlist: ", "量化筛选自选：", lang) + joined)
    if ticker is None:
        lines.append(tr(f"No data is available for {symbol or 'this symbol'}.",
                        f"暂无 {symbol or '该标的'} 的数据。", lang))
        return "\n".join(lines)
    lines.append(
        tr(
            f"Focus symbol {symbol} — {ticker.get('name')} ({ticker.get('sector')}): price {_money(ticker.get('price'))}, "
            f"today {_pct(ticker.get('chg'))}, rating {ticker.get('rating')} ({ticker.get('ratingLabel')}).",
            f"重点标的 {symbol} — {ticker.get('name')}（{ticker.get('sector')}）：价格 {_money(ticker.get('price'))}，"
            f"今日 {_pct(ticker.get('chg'))}，评级 {ticker.get('rating')}（{ticker.get('ratingLabel')}）。",
            lang,
        )
    )
    stats = ticker.get("stats") or {}
    if stats:
        lines.append(tr("Stats — ", "关键数据 — ", lang) + "; ".join(f"{k}: {v}" for k, v in stats.items()))
    rec = ticker.get("recommendation") or {}
    if rec:
        lines.append(tr("Research stance: ", "研究立场：", lang) + f"{rec.get('stance')} — {rec.get('line')}")
    if ticker.get("bull"):
        lines.append(tr("Bull case: ", "看多逻辑：", lang) + " | ".join(ticker["bull"]))
    if ticker.get("bear"):
        lines.append(tr("Bear case: ", "看空逻辑：", lang) + " | ".join(ticker["bear"]))
    if ticker.get("summary"):
        lines.append(tr("Analyst summary: ", "分析摘要：", lang) + str(ticker["summary"]))
    return "\n".join(lines)


def _offline_chat_reply(question: str, symbol: str, ticker: dict[str, Any] | None, lang: str) -> str:
    """Deterministic, data-grounded fallback when no LLM provider is reachable."""
    if ticker is None:
        return tr(
            f"I don't have data for {symbol or 'that symbol'} yet — load the markets data and ask again.",
            f"我暂时没有 {symbol or '该标的'} 的数据，请先加载行情数据后再提问。",
            lang,
        )
    q = question.lower()
    label = ticker.get("ratingLabel") or ticker.get("rating")
    rec = ticker.get("recommendation") or {}
    parts = [tr(f"{symbol} reads as {label} on the quant screen.",
                f"{symbol} 在量化筛选中呈现「{label}」。", lang)]
    if any(w in q for w in ("risk", "风险", "drawdown", "回撤", "volat", "波动")):
        parts.append(tr("Key risks — ", "主要风险 — ", lang) + " ".join(ticker.get("bear") or []))
    elif any(w in q for w in ("buy", "should", "买", "能买", "值得", "hold", "sell", "卖")):
        if rec.get("line"):
            parts.append(rec["line"])
        parts.append(tr("This is research only — not a buy or sell instruction; do your own due diligence.",
                        "这只是研究判断，并非买卖指令，请自行做尽职调查。", lang))
    elif any(w in q for w in ("valuation", "估值", "pe", "市盈", "stat", "数据", "number", "指标")):
        stats = ticker.get("stats") or {}
        parts.append(tr("Key stats — ", "关键数据 — ", lang) + "; ".join(f"{k}: {v}" for k, v in stats.items()))
    else:
        if rec.get("line"):
            parts.append(rec["line"])
        parts.append(tr("Bull: ", "看多：", lang) + (ticker.get("bull") or [""])[0])
        parts.append(tr("Bear: ", "看空：", lang) + (ticker.get("bear") or [""])[0])
    return " ".join(p for p in parts if p)


def _pct(value: Any) -> str:
    try:
        return f"{float(value):+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _safe_print(message: str) -> None:
    try:
        print(message)
    except OSError:
        if sys.stderr is not None:
            with contextlib.suppress(OSError):
                sys.stderr.write(message + "\n")


