from __future__ import annotations

import pandas as pd
from _helpers import _analyze_one_dict, _trending_prices


def test_analyze_bullish_vs_bearish() -> None:
    from quant_agent.analyze import _analyze_one

    # 默认英文
    up = _analyze_one("UP", _trending_prices("UP", 0.0025))
    down = _analyze_one("DN", _trending_prices("DN", -0.0025))

    assert up.ok and down.ok
    assert up.composite > down.composite
    assert up.rating in {"Strong Buy", "Mildly Bullish"}
    assert down.rating in {"Strong Sell", "Mildly Bearish"}
    assert up.confidence in {"High", "Medium", "Low"}
    assert up.price is not None
    assert up.levels["reference_stop"] is not None
    # 止损应低于支撑（若两者都存在）。
    if up.levels["reference_support"] is not None:
        assert up.levels["reference_stop"] <= up.levels["reference_support"]


def test_analyze_chinese_language() -> None:
    from quant_agent.analyze import _analyze_one

    up = _analyze_one("UP", _trending_prices("UP", 0.0025), language="zh")
    assert up.rating in {"强烈看多", "偏多"}
    assert up.confidence in {"高", "中", "低"}
    # 理由也应是中文
    assert any("均线" in r or "动量" in r for r in up.reasons)


def test_analyze_markdown_and_clean_symbols() -> None:
    from quant_agent.analyze import _clean_symbols, render_markdown

    assert _clean_symbols(["aapl, msft", "AAPL", " nvda "]) == ["AAPL", "MSFT", "NVDA"]

    payload = {
        "as_of": "2026-01-01 09:00",
        "results": [_analyze_one_dict()],
        "narrative": None,
        "disclaimer": "测试免责声明",
    }
    text = render_markdown(payload)
    assert "测试免责声明" in text
    assert "DEMO" in text


def test_read_symbols_file_handles_comments_and_separators(tmp_path) -> None:
    from quant_agent.analyze import read_symbols_file

    wl = tmp_path / "watchlist.txt"
    wl.write_text("AAPL, MSFT  # tech\nnvda\n# 整行注释\n\n AAPL \n", encoding="utf-8")
    assert read_symbols_file(wl) == ["AAPL", "MSFT", "NVDA"]


def test_render_chart_and_write_analysis_with_charts(tmp_path) -> None:
    from quant_agent.analyze import _analyze_one, write_analysis

    result = _analyze_one("UP", _trending_prices("UP", 0.0015))
    assert result.frame is not None and not result.frame.empty

    payload = {
        "as_of": "2026-01-01",
        "symbols": ["UP"],
        "results": [result.to_dict()],
        "narrative": None,
        "disclaimer": "x",
        "_objects": [result],
    }
    paths = write_analysis(payload, tmp_path / "out", with_charts=True)
    assert paths["charts"], "应生成至少一张图表"
    png = paths["charts"][0]
    assert png.exists() and png.stat().st_size > 0


def test_classify_fetch_error_distinguishes_network() -> None:
    from quant_agent.analyze import _classify_fetch_error

    assert _classify_fetch_error(ConnectionError("Max retries exceeded with url")) == "network"
    assert _classify_fetch_error(TimeoutError("connection timed out")) == "network"
    assert _classify_fetch_error(ValueError("bad column")) == "other"


def test_analyze_symbols_network_failure_is_friendly(monkeypatch) -> None:
    import quant_agent.analyze as analyze_mod

    def _boom(_config):
        raise ConnectionError("HTTPSConnectionPool: Max retries exceeded")

    monkeypatch.setattr(analyze_mod, "load_prices", _boom)

    payload = analyze_mod.analyze_symbols(["AAPL", "MSFT"])  # 默认英文
    assert [r.ok for r in payload["_objects"]] == [False, False]
    for result in payload["_objects"]:
        assert "Network unavailable" in result.error

    payload_zh = analyze_mod.analyze_symbols(["AAPL"], language="zh")
    assert "网络不可用" in payload_zh["_objects"][0].error


def test_doctor_command_reports_environment(monkeypatch) -> None:
    from typer.testing import CliRunner

    import quant_agent.cli as cli_mod

    class _FakeYf:
        @staticmethod
        def download(*_args, **_kwargs):
            return pd.DataFrame({"Close": [1.0, 2.0, 3.0]})

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _FakeYf)

    result = CliRunner().invoke(cli_mod.app, ["doctor"])
    # 依赖齐全且行情可达时应正常退出（rich 中文表格在不同平台编码不一，只校验退出码）。
    assert result.exit_code == 0


def test_doctor_command_flags_network_failure(monkeypatch) -> None:
    from typer.testing import CliRunner

    import quant_agent.cli as cli_mod

    class _FakeYf:
        @staticmethod
        def download(*_args, **_kwargs):
            raise ConnectionError("Max retries exceeded")

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _FakeYf)

    result = CliRunner().invoke(cli_mod.app, ["doctor"])
    # 行情源不可达时应以错误码退出，便于脚本/CI 检测环境问题。
    assert result.exit_code == 1
