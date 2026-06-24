#!/usr/bin/env python3
"""MCP server for the quant.ai US-equity research agent.

Exposes the project's research and reporting capabilities as Model Context
Protocol tools so an MCP client (Claude Desktop, Claude Code) can drive them in
natural language: generate the daily market report, read per-symbol AI analysis,
pull categorized recommendations, run a research backtest, and browse outputs.

Design principle: this server is the *tools + data* layer; the connected model is
the analytical *brain*. Every tool is research-only. None submit broker orders,
approve paper trades, or authorize live trading — those capabilities are
deliberately not exposed here.

Run locally over stdio:
    python -m quant_agent.mcp_server
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from quant_agent.config import AppConfig, load_config
from quant_agent.data import load_prices
from quant_agent.data_quality import build_data_quality_report
from quant_agent.features import build_signals
from quant_agent.market_intel import _collect_feeds, build_market_report
from quant_agent.markets_data import build_markets_data
from quant_agent.ml import apply_ml_ranking_signal
from quant_agent.pipeline import run_research_backtest
from quant_agent.portfolio import build_target_positions
from quant_agent.recommendations import RECOMMENDATION_PROFILES, build_recommendations

mcp = FastMCP("quant_research_mcp")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = "configs/full_roadmap.yaml"
DISCLAIMER = "Research only. Not investment advice; no live-trading authorization."


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _resolve_config_path(config: str) -> Path:
    path = Path(config)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load(config: str) -> AppConfig:
    config_path = _resolve_config_path(config)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found: {config_path}. Provide a path relative to the project root "
            f"(e.g. 'configs/full_roadmap.yaml')."
        )
    return load_config(config_path)


def _err(exc: Exception) -> dict[str, Any]:
    return {"error": f"{type(exc).__name__}: {exc}"}


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# --------------------------------------------------------------------------- #
# Input models
# --------------------------------------------------------------------------- #


class ConfigInput(_Base):
    config: str = Field(
        default=DEFAULT_CONFIG,
        description="Config file path relative to the project root (e.g. 'configs/full_roadmap.yaml').",
    )
    refresh: bool = Field(
        default=False,
        description=(
            "Force a fresh price-data download (ignore cache) so results reflect the latest available "
            "trading day. Slower. Off by default because the cache auto-refreshes once it is older than "
            "data.cache_ttl_hours, so normal calls already return current data."
        ),
    )


async def _prewarm(config: AppConfig, refresh: bool) -> None:
    """Force-refresh the cached price data before building, when requested."""
    if refresh:
        await asyncio.to_thread(load_prices, config.data, True)


class MarketsDataInput(ConfigInput):
    symbol: str | None = Field(
        default=None,
        description="Optional ticker (e.g. 'NVDA'). If given, return only that symbol's analysis; otherwise return all.",
        max_length=12,
    )


class RecommendationsInput(ConfigInput):
    profile: str | None = Field(
        default=None,
        description="Optional horizon filter: one of 'long_term', 'swing', 'short_term', 'defensive', 'aggressive'. Omit for all.",
    )
    per_profile: int = Field(default=5, description="Number of candidates per profile.", ge=1, le=25)


class NewsInput(ConfigInput):
    limit: int = Field(default=15, description="Maximum number of headlines to return.", ge=1, le=50)


class ReadReportInput(ConfigInput):
    name: str = Field(..., description="Report file name within the report output dir (e.g. 'market_intel.md', 'summary.md').", min_length=1)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #


@mcp.tool(
    name="quant_get_markets_data",
    annotations={"title": "Per-symbol AI equity read", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def quant_get_markets_data(params: MarketsDataInput) -> dict[str, Any]:
    """Return AI-analyst-style reads for the US-equity universe, derived from real quant signals.

    For each symbol this gives a rating (Bullish/Neutral/Volatile/Cautious), a plain-language
    summary, bull/bear bullet cases, key stats (1M/5D return, annualized vol, 52-week range,
    average dollar volume, blended signal score), latest price, and 1-day change. All values are
    computed from price history and cross-sectional signals — no fundamentals, no forecasts.

    Args:
        params (MarketsDataInput):
            - config (str): config path relative to project root.
            - symbol (Optional[str]): a single ticker to focus on; omit for the whole universe.

    Returns:
        dict: {
          "as_of": "YYYY-MM-DD",
          "default_symbol": str,
          "tickers": { "<SYM>": {name, sector, price, chg, rating, summary, bull[], bear[], stats{}} },
          "watchlist": [{sym, chg}],
          "brief": str,            # one-line market brief
          "disclaimer": str
        }
        If `symbol` is given, "tickers" contains just that symbol (or an "error" if unknown).

    Examples:
        - "What's the read on NVDA?" -> params with symbol="NVDA"
        - "Summarize the whole watchlist" -> params with no symbol
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)
        data = await asyncio.to_thread(build_markets_data, config)
        tickers = data.get("TICKERS", {})
        if params.symbol:
            sym = params.symbol.upper()
            if sym not in tickers:
                return {"error": f"Unknown or unanalyzed symbol '{sym}'. Available: {sorted(tickers)[:30]}"}
            tickers = {sym: tickers[sym]}
        return {
            "as_of": data.get("as_of"),
            "default_symbol": data.get("defaultSym"),
            "tickers": tickers,
            "watchlist": data.get("WATCH", []),
            "brief": data.get("brief"),
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_get_recommendations",
    annotations={"title": "Categorized research candidates", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def quant_get_recommendations(params: RecommendationsInput) -> dict[str, Any]:
    """Return categorized research buy-candidates by holding horizon.

    Profiles: long_term (6-12m), swing (1-3m), short_term (1-4w), defensive, aggressive. Each
    candidate includes rank, symbol, recommendation_score, confidence, risk_level, latest_price,
    a reason from the top signal contributions, and a research_weight. These are research
    candidates only — not orders or investment advice.

    Args:
        params (RecommendationsInput):
            - config (str): config path relative to project root.
            - profile (Optional[str]): filter to one horizon; omit for all five.
            - per_profile (int): candidates per profile (1-25).

    Returns:
        dict: { "as_of_profiles": [...], "recommendations": { "<profile>": [ {rank, symbol, recommendation_score, confidence, risk_level, latest_price, reason, ...} ] }, "disclaimer": str }
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)

        def _compute() -> dict[str, Any]:
            prices = load_prices(config.data)
            signals = build_signals(prices, config.strategy.signal_weights)
            signals, _ = apply_ml_ranking_signal(signals, config)
            targets = build_target_positions(signals, config.strategy, config.risk)
            _, payload = build_recommendations(signals, prices, targets, config, per_profile=params.per_profile)
            return payload

        payload = await asyncio.to_thread(_compute)
        grouped = payload.get("recommendations", {})
        if params.profile:
            key = params.profile.lower()
            if key not in RECOMMENDATION_PROFILES:
                return {"error": f"Unknown profile '{params.profile}'. Valid: {list(RECOMMENDATION_PROFILES)}"}
            grouped = {key: grouped.get(key, [])}
        return {"profiles": list(RECOMMENDATION_PROFILES), "recommendations": grouped, "disclaimer": DISCLAIMER}
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_generate_market_report",
    annotations={"title": "Daily US market report", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def quant_generate_market_report(params: ConfigInput) -> dict[str, Any]:
    """Generate the daily US-market research briefing (news + quant) and return a structured summary.

    Fetches recent financial-media headlines (free RSS) and per-company news, grades the universe
    into relatively-favorable research candidates vs elevated-risk names from price statistics, and
    includes the categorized quant candidates. Writes market_intel.{html,md,json} to the report dir.

    Args:
        params (ConfigInput): config path relative to project root.

    Returns:
        dict: { as_of_date, data_status, market_overview{}, buy_candidates[], high_risk[], quant_candidates{}, news[], warnings[], disclaimer }
        (full report; the HTML/MD/JSON files are also written to the configured report dir)
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)
        report = await asyncio.to_thread(build_market_report, config)
        return {
            "as_of_date": report.get("as_of_date"),
            "data_status": report.get("data_status"),
            "market_overview": report.get("market_overview", {}),
            "buy_candidates": report.get("buy_candidates", []),
            "high_risk": report.get("high_risk", []),
            "quant_candidates": report.get("quant_candidates", {}),
            "news": report.get("news", [])[:20],
            "warnings": report.get("warnings", []),
            "disclaimer": report.get("disclaimer", DISCLAIMER),
        }
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_get_market_news",
    annotations={"title": "Latest financial headlines", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def quant_get_market_news(params: NewsInput) -> dict[str, Any]:
    """Fetch the latest US financial-media headlines from the configured free RSS sources.

    Lighter than the full market report — just headlines (source, title, link, published).

    Args:
        params (NewsInput):
            - config (str): config path relative to project root.
            - limit (int): max headlines (1-50).

    Returns:
        dict: { "count": int, "news": [ {source, title, link, published, summary} ], "warnings": [...] }
    """
    try:
        config = _load(params.config)
        mi = config.market_intel

        def _fetch() -> tuple[list[dict[str, Any]], list[str]]:
            return _collect_feeds(mi.news_feeds, params.limit, mi.request_timeout)

        items, errors = await asyncio.to_thread(_fetch)
        return {"count": len(items), "news": items[: params.limit], "warnings": errors}
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_run_backtest",
    annotations={"title": "Run research backtest", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def quant_run_backtest(params: ConfigInput) -> dict[str, Any]:
    """Run the research backtest pipeline and return headline performance metrics.

    Executes the full close-to-close research backtest and writes the standard report artifacts
    (summary.md, audit.json, equity curves, metrics, recommendations, etc.) to the configured
    report dir. This is a research simulation — it never submits or proposes live orders.

    Args:
        params (ConfigInput): config path relative to project root.

    Returns:
        dict: { "output_dir": str, "metrics": { total_return, sharpe, sortino, max_drawdown, volatility, ... } }
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)
        result = await asyncio.to_thread(run_research_backtest, config)
        metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
        return {"output_dir": str(config.report.output_dir), "metrics": metrics, "disclaimer": DISCLAIMER}
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_data_quality",
    annotations={"title": "Data quality summary", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def quant_data_quality(params: ConfigInput) -> dict[str, Any]:
    """Return a data-quality summary for the configured price universe.

    Checks stale data, missing universe symbols, and point-in-time/corporate-action metadata.

    Args:
        params (ConfigInput): config path relative to project root.

    Returns:
        dict: { "summary": {...}, "issues_by_symbol": [...] } (structure from build_data_quality_report)
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)

        def _compute() -> dict[str, Any]:
            prices = load_prices(config.data)
            report = build_data_quality_report(prices, config.data.universe)
            return {"summary": report.get("summary", {}), "checks": report.get("checks", report)}

        return await asyncio.to_thread(_compute)
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_list_reports",
    annotations={"title": "List report files", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def quant_list_reports(params: ConfigInput) -> dict[str, Any]:
    """List the generated report files in the configured report output directory.

    Args:
        params (ConfigInput): config path relative to project root.

    Returns:
        dict: { "report_dir": str, "files": [ {name, size_bytes} ] }
    """
    try:
        config = _load(params.config)
        report_dir = config.report.output_dir
        if not report_dir.exists():
            return {"report_dir": str(report_dir), "files": []}
        files = [
            {"name": p.name, "size_bytes": p.stat().st_size}
            for p in sorted(report_dir.iterdir())
            if p.is_file()
        ]
        return {"report_dir": str(report_dir), "files": files}
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_read_report",
    annotations={"title": "Read a report file", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def quant_read_report(params: ReadReportInput) -> str:
    """Read a single text report file from the configured report output directory.

    Use quant_list_reports first to discover available file names. Path traversal is rejected.

    Args:
        params (ReadReportInput):
            - config (str): config path relative to project root.
            - name (str): file name within the report dir (e.g. 'market_intel.md', 'summary.md', 'recommendations.json').

    Returns:
        str: the file's text content, or an "Error: ..." message.
    """
    try:
        config = _load(params.config)
        report_dir = config.report.output_dir.resolve()
        target = (report_dir / params.name).resolve()
        if report_dir not in target.parents:
            return "Error: path escapes the report directory."
        if not target.exists() or not target.is_file():
            return f"Error: report file '{params.name}' not found. Use quant_list_reports to see available files."
        if target.stat().st_size > 1_000_000:
            return f"Error: '{params.name}' is too large to inline ({target.stat().st_size} bytes)."
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


if __name__ == "__main__":
    mcp.run()
