#!/usr/bin/env python3
"""MCP server for the quant.ai US-equity research agent.

Exposes the project's research and reporting capabilities as Model Context
Protocol tools so an MCP client (Claude Desktop, Claude Code) can drive them in
natural language: manage the user's chat-managed watchlist and holdings, generate
the daily market report (HTML artifact-ready), read per-symbol AI analysis, pull
categorized recommendations, run a research backtest, and browse outputs.

Design principle: this server is the *tools + data* layer; the connected model is
the analytical *brain*. Every tool is research-only. None submit broker orders,
approve paper trades, or authorize live trading — those capabilities are
deliberately not exposed here. Holdings are the user's self-reported bookkeeping,
never broker state.

Run locally over stdio:
    python -m quant_agent.mcp_server
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from quant_agent import holdings as holdings_store
from quant_agent.config import AppConfig, load_config
from quant_agent.data import load_prices
from quant_agent.data_quality import build_data_quality_report
from quant_agent.features import build_signals
from quant_agent.market_intel import _collect_feeds, build_market_report, render_markdown, write_market_report
from quant_agent.markets_data import build_markets_data
from quant_agent.portfolio import build_target_positions
from quant_agent.recommendations import RECOMMENDATION_PROFILES, build_recommendations

MCP_INSTRUCTIONS = (
    "US-equity quant research tools (research only — never orders). "
    "The user's chat-managed watchlist and holdings live in this server: when the user says "
    "something like 'watch NVDA for me' / '帮我关注英伟达', call quant_manage_watchlist; for "
    "'I bought 15 AAPL at 182.5' / '我 182.5 买了 15 股苹果', call quant_manage_holdings. "
    "Symbols managed there are automatically covered by every other tool, and the daily report "
    "opens with the user's holdings P&L. "
    "Daily report: call quant_generate_market_report and present the report AS AN ARTIFACT, "
    "preferring the polished HTML: "
    "(1) if you can read local files (e.g. Claude Code), publish the self-contained HTML file at "
    "`artifact_html_path` as an HTML artifact; "
    "(2) if not (e.g. Claude Desktop), call quant_read_report with name='market_intel_artifact.html' "
    "and render that HTML as a text/html artifact (you may wrap it in a minimal "
    "<!doctype html> shell with <meta charset=\"utf-8\">); "
    "(3) only if HTML artifacts are unsupported, fall back to `report_markdown` as a Markdown "
    "artifact titled 'US Market Report · <as_of_date>' (or '美股当日报告 · <date>'). "
    "Always keep the disclaimer at the end. For the other tools, answer normally."
)
mcp = FastMCP("quant_research_mcp", instructions=MCP_INSTRUCTIONS)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Default to the user's personal watchlist config so the tools only pull the symbols
# they care about. Falls back to the committed full_roadmap.yaml if it's absent.
DEFAULT_CONFIG = "configs/my.yaml" if (PROJECT_ROOT / "configs/my.yaml").exists() else "configs/full_roadmap.yaml"
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
    # 叠加聊天管理的自选/持仓：所有工具的 universe 自动覆盖用户标的。
    return holdings_store.apply_portfolio_universe(load_config(config_path))


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


class WatchlistInput(ConfigInput):
    action: Literal["list", "add", "remove"] = Field(
        default="list",
        description="list = show the chat-managed watchlist; add/remove = modify it.",
    )
    symbols: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Tickers for add/remove (e.g. ['NVDA', 'TSLA']). Ignored for list.",
    )


class PositionInput(_Base):
    symbol: str = Field(..., min_length=1, max_length=12, description="Ticker, e.g. 'AAPL'.")
    shares: float | None = Field(default=None, gt=0, description="Share count. Required for action='set'.")
    cost_basis: float | None = Field(default=None, gt=0, description="Optional average cost per share (USD).")
    note: str | None = Field(default=None, max_length=200, description="Optional free-form note.")


class HoldingsInput(ConfigInput):
    action: Literal["list", "set", "remove"] = Field(
        default="list",
        description="list = holdings with P&L snapshot; set = insert/replace positions; remove = delete by symbol.",
    )
    positions: list[PositionInput] = Field(
        default_factory=list,
        max_length=50,
        description="For set: full rows (symbol + shares, optional cost_basis/note). For remove: only symbol is used.",
    )


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #


@mcp.tool(
    name="quant_manage_watchlist",
    annotations={"title": "Manage chat watchlist", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
async def quant_manage_watchlist(params: WatchlistInput) -> dict[str, Any]:
    """List, add, or remove symbols on the user's chat-managed watchlist.

    The watchlist lives in ``data/portfolio.json`` (config key ``portfolio.path``) and is an
    overlay on the configured universe: symbols added here are automatically covered by every
    research tool (market data, daily report, recommendations, backtest) and survive
    ``quant-ai refresh-universe``. The rolling price database backfills new symbols on the next
    data-touching call — seeded from existing caches, so it is incremental, not a full re-download.

    Args:
        params (WatchlistInput):
            - config (str): config path relative to the project root.
            - action (str): 'list' (default) | 'add' | 'remove'.
            - symbols (list[str]): tickers for add/remove; ignored for list.

    Returns:
        dict: { action, watchlist, holdings_symbols, updated_at, portfolio_path, note }

    Examples:
        - "Watch NVDA and TSLA for me" / "帮我关注英伟达和特斯拉" -> action='add', symbols=['NVDA', 'TSLA']
        - "Stop tracking TSLA" -> action='remove', symbols=['TSLA']
        - "What's on my watchlist?" -> action='list'
    """
    try:
        if params.action in {"add", "remove"} and not params.symbols:
            return {"error": f"action '{params.action}' requires at least one symbol"}
        config = _load(params.config)

        def _run() -> dict[str, Any]:
            portfolio = holdings_store.load_portfolio(config.portfolio_path)
            if params.action == "add":
                holdings_store.add_watchlist_symbols(portfolio, params.symbols)
                holdings_store.save_portfolio(portfolio, config.portfolio_path)
            elif params.action == "remove":
                holdings_store.remove_watchlist_symbols(portfolio, params.symbols)
                holdings_store.save_portfolio(portfolio, config.portfolio_path)
            return {
                "action": params.action,
                "watchlist": portfolio["watchlist"],
                "holdings_symbols": [h["symbol"] for h in portfolio["holdings"]],
                "updated_at": portfolio.get("updated_at"),
                "portfolio_path": str(config.portfolio_path),
                "note": "Watchlist symbols are automatically included in every research tool's universe.",
            }

        return await asyncio.to_thread(_run)
    except Exception as exc:
        return _err(exc)


@mcp.tool(
    name="quant_manage_holdings",
    annotations={"title": "Manage holdings & P&L", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def quant_manage_holdings(params: HoldingsInput) -> dict[str, Any]:
    """List (with P&L), set/update, or remove the user's self-reported stock positions.

    Positions are the user's own bookkeeping in ``data/portfolio.json`` — research context only,
    never broker state or orders. Held symbols are automatically covered by every research tool,
    and the daily market report opens with this P&L snapshot. ``list`` marks positions with
    best-effort live quotes (falling back to the cached last close; see ``quotes_source``).

    Args:
        params (HoldingsInput):
            - config (str): config path relative to the project root.
            - action (str): 'list' (default) | 'set' | 'remove'.
            - positions: for 'set', rows of {symbol, shares, cost_basis?, note?} — an existing
              symbol is replaced wholesale; for 'remove', only each row's symbol is used.

    Returns:
        dict: { action, holdings, watchlist, updated_at, portfolio_path, disclaimer,
        and for list: positions[] (price, day_change_pct, market_value, unrealized_pnl, ...),
        totals{}, quotes_source }

    Examples:
        - "I bought 15 AAPL at 182.5" / "我 182.5 买了 15 股苹果" -> action='set',
          positions=[{symbol: 'AAPL', shares: 15, cost_basis: 182.5}]
        - "How are my positions doing?" / "我的持仓怎么样了" -> action='list'
        - "I sold all my AAPL" -> action='remove', positions=[{symbol: 'AAPL'}]
    """
    try:
        if params.action == "set":
            missing = [p.symbol for p in params.positions if p.shares is None]
            if not params.positions or missing:
                return {"error": f"action 'set' requires positions with shares > 0 (missing shares for: {missing or 'all'})"}
        if params.action == "remove" and not params.positions:
            return {"error": "action 'remove' requires positions (symbol only)"}
        config = _load(params.config)
        await _prewarm(config, params.refresh)

        def _run() -> dict[str, Any]:
            portfolio = holdings_store.load_portfolio(config.portfolio_path)
            if params.action == "set":
                holdings_store.upsert_holdings(portfolio, [p.model_dump() for p in params.positions])
                holdings_store.save_portfolio(portfolio, config.portfolio_path)
            elif params.action == "remove":
                holdings_store.remove_holdings(portfolio, [p.symbol for p in params.positions])
                holdings_store.save_portfolio(portfolio, config.portfolio_path)
            result: dict[str, Any] = {
                "action": params.action,
                "holdings": portfolio["holdings"],
                "watchlist": portfolio["watchlist"],
                "updated_at": portfolio.get("updated_at"),
                "portfolio_path": str(config.portfolio_path),
                "disclaimer": DISCLAIMER,
            }
            if params.action == "list" and portfolio["holdings"]:
                quotes = holdings_store.fetch_live_quotes([h["symbol"] for h in portfolio["holdings"]])
                prices = load_prices(config.data)  # config 已含持仓标的（_load 叠加过）
                result.update(holdings_store.build_holdings_snapshot(portfolio, prices, quotes))
            elif params.action == "list":
                result.update({"positions": [], "totals": {}, "quotes_source": "last_close"})
            return result

        return await asyncio.to_thread(_run)
    except Exception as exc:
        return _err(exc)


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
        # Deferred to call time: scikit-learn is only needed by the ML ranking, so the
        # stdio server boots (and the sklearn-free tools work) without loading it.
        from quant_agent.ml import apply_ml_ranking_signal

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
    """Generate the daily US-market research briefing (news + quant + the user's holdings P&L).

    Fetches recent financial-media headlines (free RSS) and per-company news, grades the universe
    into relatively-favorable research candidates vs elevated-risk names from price statistics,
    includes the categorized quant candidates, and — when the user has chat-managed holdings —
    opens with their P&L snapshot. Writes market_intel.{json,md,html} plus the artifact-ready
    market_intel_artifact.html to the configured report dir.

    Present the report to the user AS AN ARTIFACT, preferring the polished HTML:
    (1) with local file access, publish the self-contained HTML at ``artifact_html_path``;
    (2) without it, fetch the same HTML via quant_read_report(name='market_intel_artifact.html');
    (3) only as a last resort render ``report_markdown`` as a Markdown artifact.
    The structured fields are there for any follow-up reasoning.

    Args:
        params (ConfigInput): config path relative to project root.

    Returns:
        dict: { display:"html_artifact", artifact_html_path, report_markdown (fallback),
        as_of_date, data_status, holdings (P&L snapshot or None), market_overview{},
        buy_candidates[], high_risk[], quant_candidates{}, news[], warnings[], disclaimer }
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)

        def _build() -> tuple[dict[str, Any], dict[str, Path]]:
            report = build_market_report(config)
            paths = write_market_report(report, config.market_intel.output_dir)
            return report, paths

        report, paths = await asyncio.to_thread(_build)
        return {
            "display": "html_artifact",  # client hint: present the HTML artifact (see docstring)
            "artifact_html_path": str(paths["artifact"].resolve()),
            "report_markdown": render_markdown(report),
            "as_of_date": report.get("as_of_date"),
            "data_status": report.get("data_status"),
            "holdings": report.get("holdings"),
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
    Note: the universe includes the chat-managed watchlist/holdings overlay, so results can
    shift when the user edits their watchlist.

    Args:
        params (ConfigInput): config path relative to project root.

    Returns:
        dict: { "output_dir": str, "metrics": { total_return, sharpe, sortino, max_drawdown, volatility, ... } }
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)
        # Deferred to call time (the pipeline pulls in scikit-learn via ML ranking).
        from quant_agent.pipeline import run_research_backtest

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
        dict: { "summary": {...}, "issues": [...], "by_symbol": [ {symbol, rows, first_date, last_date, ...} ] }
    """
    try:
        config = _load(params.config)
        await _prewarm(config, params.refresh)

        def _compute() -> dict[str, Any]:
            prices = load_prices(config.data)
            report = build_data_quality_report(prices, config.data.universe)
            # symbol_summary is a DataFrame; round-trip through to_json so dates/numpy
            # types become JSON-native before the MCP layer serializes the result.
            summary_df = report.get("symbol_summary")
            by_symbol = (
                json.loads(summary_df.to_json(orient="records", date_format="iso"))
                if summary_df is not None and hasattr(summary_df, "to_json")
                else []
            )
            return {
                "summary": report.get("summary", {}),
                "issues": report.get("issues", []),
                "by_symbol": by_symbol,
            }

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
