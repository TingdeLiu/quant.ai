from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
from email import message_from_string
from http.server import ThreadingHTTPServer

import pytest
from _helpers import _synthetic_prices
from pydantic import ValidationError
from typer.testing import CliRunner

from quant_agent import holdings as store
from quant_agent.cli import app
from quant_agent.config import load_config, parse_config
from quant_agent.demo import prepare_demo
from quant_agent.market_intel import build_market_report
from quant_agent.server import (
    MAX_REQUEST_BODY,
    MarketIntelJob,
    RunHistory,
    RuntimeStatus,
    _handler_factory,
)
from quant_agent.workspace import PortfolioChange, render_workspace_html


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    prices = tmp_path / "prices.csv"
    _synthetic_prices(periods=620).to_csv(prices, index=False)
    config = parse_config({
        "language": "zh",
        "data": {"source": "csv", "csv_path": str(prices), "universe": ["AAA", "SPY"]},
        "report": {"output_dir": "reports"},
        "portfolio": {"path": "portfolio.json"},
        "market_intel": {"news_feeds": [], "social_enabled": False, "symbol_news_count": 0},
        "dashboard_security": {"enabled": True, "token": "beta-test-token", "audit_log_path": "audit.jsonl"},
    }, base=tmp_path)
    seen = []

    def offline_build(cfg):
        seen.append(cfg.data.universe)
        return build_market_report(cfg, quote_fetcher=lambda _: {}, target_fetcher=lambda _: {})

    monkeypatch.setattr("quant_agent.server.build_market_report", offline_build)
    history = RunHistory(tmp_path / "history.json")
    status = RuntimeStatus(tmp_path / "status.json", history)
    job = MarketIntelJob(config, tmp_path / "job.json")
    handler = _handler_factory(tmp_path / "config.yaml", config, status, history, market_intel=job)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, body=None, *, auth=True, origin=None, content_type="application/json"):
        headers = {"Content-Type": content_type}
        if auth:
            headers["Authorization"] = "Bearer beta-test-token"
        if origin:
            headers["Origin"] = origin
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}" + path, data=data, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read().decode()
            payload = json.loads(raw) if response.headers.get_content_type() == "application/json" else raw
            return response.status, payload

    yield config, job, seen, request
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_workspace_flow_keeps_report_in_sync_with_saved_portfolio(workspace):
    config, job, seen, request = workspace
    code, page = request("/app", auth=False)
    assert code == 200 and "你的个人美股研究台" in page
    assert "beta-test-token" not in page
    assert request("/api/workspace")[1]["report_available"] is False
    assert request("/api/workspace/portfolio", {"action": "watchlist.add", "symbols": ["bbb"]})[0] == 200
    position = {"symbol": "CCC", "shares": 2.5, "cost_basis": 95.0, "note": "research only"}
    assert request("/api/workspace/portfolio", {"action": "holding.set", "position": position})[0] == 200
    job._run()
    assert {"AAA", "BBB", "CCC", "SPY"}.issubset(seen[-1])
    code, payload = request("/api/workspace")
    assert code == 200 and payload["report_current"] and payload["report_available"]
    assert payload["data_status"] == "ok"
    assert "CCC" in request("/api/workspace/report")[1]
    assert "不构成投资建议" in request("/api/workspace/context")[1]
    assert request("/api/workspace/portfolio", {"action": "holding.remove", "symbols": ["CCC"]})[0] == 200
    assert request("/api/workspace")[1]["report_current"] is False
    assert store.load_portfolio(config.portfolio_path)["holdings"] == []


def test_workspace_private_apis_require_auth_and_reject_cross_origin_mutations(workspace):
    config, _, _, request = workspace
    for path in ("/api/workspace", "/api/workspace/report", "/api/workspace/context"):
        assert request(path, auth=False)[0] == 401
    body = {"action": "watchlist.add", "symbols": ["AAA"]}
    assert request("/api/workspace/portfolio", body, auth=False)[0] == 401
    assert request("/api/workspace/portfolio", body, origin="https://other.example")[0] == 403
    assert request("/api/workspace/portfolio", body, content_type="text/plain")[0] == 415
    assert not config.portfolio_path.exists()


def test_error_responses_drain_the_request_body(tmp_path):
    """401/403/415 这些不看 body 就拒绝的路径，必须先把请求体读掉。

    服务跑在 HTTP/1.0 上，响应完即关连接；而关闭一个接收缓冲区里尚有未读数据的
    socket 会让 TCP 发 RST 而不是 FIN，把客户端还没读到的响应一起打掉 —— Windows
    上报 ConnectionAbortedError。这正是上面那个测试曾经间歇失败的原因（实测
    403/415 路径失败率 3%–5%），也意味着真实页面的 fetch 会偶尔看到网络错误而不是
    干净的状态码。这里直接验「排空」这个不变量，不写成概率性测试。
    """
    handler_cls = _handler_factory(tmp_path / "config.yaml", parse_config({}, base=tmp_path), None, None)

    def leftover(body: bytes, *, declared: int | None = None, consumed: bool = False) -> bytes:
        handler = handler_cls.__new__(handler_cls)
        handler.rfile = io.BytesIO(body)
        handler.headers = message_from_string(f"Content-Length: {len(body) if declared is None else declared}\n")
        if consumed:
            handler._body_consumed = True
        handler_cls._drain_request_body(handler)
        return handler.rfile.read()

    assert leftover(b"x" * 500) == b""
    assert leftover(b"") == b""
    # 已被 _read_json_body 读过的请求体不重复读，否则会吞掉下一次读取。
    assert leftover(b"already handled", consumed=True) == b"already handled"
    # 超过上限的只排空到上限：那种请求本来就被拒，不值得为它读进任意大的数据。
    assert len(leftover(b"x" * (MAX_REQUEST_BODY + 100))) == 100


@pytest.mark.parametrize("body", [
    [], {"action": "watchlist.add", "symbols": []},
    {"action": "watchlist.add", "symbols": ["<script>"]},
    {"action": "holding.set", "position": {"symbol": "AAA", "shares": -1}},
    {"action": "holding.set", "position": {"symbol": "AAA", "shares": float("nan")}},
    {"action": "holding.set", "position": {"symbol": "AAA", "shares": 1, "cost_basis": float("inf")}},
    {"action": "holding.set", "symbols": ["AAA"]},
    {"action": "watchlist.add", "symbols": ["AAA"], "extra": True},
])
def test_invalid_portfolio_requests_do_not_write_anything(workspace, body):
    config, _, _, request = workspace
    assert request("/api/workspace/portfolio", body)[0] == 400
    assert not config.portfolio_path.exists()


def test_corrupt_portfolio_is_visible_and_never_overwritten(workspace):
    config, job, _, request = workspace
    config.portfolio_path.write_text("{broken", encoding="utf-8")
    assert request("/api/workspace")[0] == 409
    assert request("/api/workspace/portfolio", {"action": "watchlist.add", "symbols": ["AAA"]})[0] == 409
    job._run()
    assert job.read_status()["last_status"] == "failed"
    assert config.portfolio_path.read_text(encoding="utf-8") == "{broken"


def test_demo_stays_offline_and_preserves_previous_demo_edits(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    cfg = load_config(prepare_demo(root, "zh"))
    assert cfg.portfolio_path == root / "portfolio.json"
    assert cfg.data.source == "csv"
    portfolio = store.load_portfolio(cfg.portfolio_path)
    store.add_watchlist_symbols(portfolio, ["SPY"])
    store.save_portfolio(portfolio, cfg.portfolio_path)
    prepare_demo(root, "en")
    assert "SPY" in store.load_portfolio(cfg.portfolio_path)["watchlist"]

    def no_live_calls(*args, **kwargs):
        pytest.fail("Demo must not fetch live data")

    monkeypatch.setattr("quant_agent.holdings.fetch_live_quotes", no_live_calls)
    monkeypatch.setattr("quant_agent.market_intel.fetch_analyst_price_targets_cached", no_live_calls)
    job = MarketIntelJob(cfg, root / "status.json", demo=True)
    job._run()
    report = job.read_report()
    assert job.read_status()["last_status"] == "success"
    assert report["demo"] is True and report["data_status"] == "ok"
    assert "模拟数据" in report["disclaimer"]
    assert not (tmp_path / "portfolio.json").exists()


def test_failed_report_generation_preserves_previous_report(workspace, monkeypatch):
    _, job, _, _ = workspace
    job._run()
    old = (job.output_dir / "market_intel_artifact.html").read_bytes()

    def fail(_):
        raise RuntimeError("test failure")

    monkeypatch.setattr("quant_agent.server.build_market_report", fail)
    job._run()
    assert job.read_status()["last_status"] == "failed"
    assert (job.output_dir / "market_intel_artifact.html").read_bytes() == old


def test_start_uses_personal_config_and_is_loopback_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/my.yaml").touch()
    calls = []
    monkeypatch.setattr("quant_agent.cli.run_dashboard_server", lambda *args, **kwargs: calls.append((args, kwargs)))
    runner = CliRunner()
    assert runner.invoke(app, ["start", "--lang", "zh"]).exit_code == 0
    # resolve_config 返回绝对路径：之后谁改了工作目录都不影响已解析出的配置。
    assert calls[0][0][0] == tmp_path / "configs/my.yaml"
    assert calls[0][1] == {"port": 8765, "demo": False, "language": "zh"}
    assert runner.invoke(app, ["start", "--demo", "--config", "custom.yaml"]).exit_code != 0
    assert runner.invoke(app, ["start", "--lang", "invalid"]).exit_code != 0


def test_portfolio_input_rejects_ambiguous_actions():
    with pytest.raises(ValidationError):
        PortfolioChange(action="holding.remove", symbols=["AAA"], position={"symbol": "AAA", "shares": 1})
    assert PortfolioChange(action="watchlist.add", symbols=["brk-b"]).symbols == ["BRK-B"]


def test_ui_has_bilingual_empty_states_and_no_external_assets():
    for language, expected in (("en", "Your personal research desk"), ("zh", "你的个人美股研究台")):
        page = render_workspace_html(language)
        assert expected in page
        assert "__CONFIG__" not in page and "__GENERATE__" not in page
        assert 'sandbox="allow-scripts"' in page
        assert '<script src="http' not in page and '<link href="http' not in page
