from __future__ import annotations

import contextlib
import hmac
import json
import os
import sys
import threading
import time
import traceback
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from quant_agent.config import AppConfig, DashboardSecurityConfig, ReportConfig, load_config
from quant_agent.console import render_console_html
from quant_agent.market_intel import build_market_report, write_market_report
from quant_agent.markets_data import build_markets_data
from quant_agent.pipeline import run_research_backtest

STATUS_FILE = "runtime_status.json"
HISTORY_FILE = "run_history.json"
MARKET_INTEL_STATUS_FILE = "market_intel_status.json"


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
                self._send_console()
            elif path in ("/console", "/dashboard", "/markets") or path.startswith("/m/"):
                self._redirect("/")  # 三个旧页面已并进 / 的标签页
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
            if parts[3] == "alerts":
                report = _report_dir_from_record(record)
                self._send_json(_load_json(report / "alerts.json"))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

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

        def _send_console(self) -> None:
            """统一控制台：报告 / 行情 / 回测 / 运行 四个标签页。

            报告与行情取数都可能失败（还没生成、数据源挂了），各自降级为占位块，不让
            整页 500。
            """
            self._send_html(
                render_console_html(
                    config,
                    status.read(),
                    history.read(),
                    report=_load_json(market_intel.output_dir / "market_intel.json"),
                    markets=_safe_markets_data(config),
                )
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
    if suffix == ".js":
        return "application/javascript; charset=utf-8"
    return "application/octet-stream"


# 控制台每次打开和 /api/markets-data 每次请求都要这份数据，而底层价格库每天至多刷新
# 一次 —— 逐请求重算（读全库 + 全历史滚动信号）纯属浪费。短 TTL 记忆缓存即可，
# 失败结果不缓存，保证瞬时故障不会黏住 60 秒。
_MARKETS_CACHE_TTL_S = 60.0
_markets_cache: dict[int, tuple[float, AppConfig, dict[str, Any]]] = {}
_markets_cache_lock = threading.Lock()


def _safe_markets_data(config: AppConfig) -> dict[str, Any]:
    """Build the markets payload (60s memoized), degrading to an empty payload on any failure."""
    now = time.monotonic()
    with _markets_cache_lock:
        hit = _markets_cache.get(id(config))
        # id 可能被回收复用，须验证确为同一 config 对象。
        if hit is not None and hit[1] is config and now - hit[0] < _MARKETS_CACHE_TTL_S:
            return hit[2]
    try:
        data = build_markets_data(config)
    except Exception as exc:  # pragma: no cover - data/network dependent
        return {"TICKERS": {}, "WATCH": [], "PRICE": {}, "TFS": [], "defaultSym": None, "error": str(exc)}
    with _markets_cache_lock:
        _markets_cache[id(config)] = (now, config, data)
    return data


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


