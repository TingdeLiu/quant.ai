"""Daily US market intelligence report.

Collects free, no-API-key market data and turns it into a daily research
briefing: recent financial-media headlines, per-company news, and a
quant-grounded split between relatively favorable research candidates and
elevated-risk names.

This module is research-only. It never produces broker instructions, order
tickets, or live-trading authorization. All "buy"/"risk" language refers to
research candidates derived from public news and historical price statistics.
"""

from __future__ import annotations

import dataclasses
import html
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pandas as pd

from quant_agent import holdings as holdings_store
from quant_agent.company_names import name_zh
from quant_agent.config import AppConfig
from quant_agent.data import load_prices
from quant_agent.features import build_signals
from quant_agent.i18n import normalize_language, tr
from quant_agent.recommendations import (
    RECOMMENDATION_PROFILES,
    classify_recommendation_risk,
    recommendation_confidence,
)
from quant_agent.yf_cache import import_yfinance


def _disclaimer(lang: str) -> str:
    return tr(
        "This report is for quantitative research and learning only — not investment advice, "
        "and not authorization to trade. The 'potential picks' and 'high risk' lists are research "
        "candidates from public news and historical-price statistics; any real trade needs "
        "independent data validation, compliance review and risk control. The valuation-range bar "
        "uses sell-side analyst consensus (median target, low/high, via Yahoo Finance) — typically "
        "a ~12-month view, not intrinsic value, and analyst targets tend to lag and skew optimistic.",
        "本报告仅用于量化研究与学习，不构成投资建议，也不是实盘交易授权。"
        "所谓“潜力股”和“高风险”均为基于公开新闻与历史价格统计的研究候选，"
        "任何真实交易都需要独立的数据校验、合规审查和风险控制。"
        "估值区间条采用卖方分析师一致预期（中位数目标价及最低/最高，数据源 Yahoo Finance）——"
        "通常是未来约12个月的展望，不等于内在价值，且分析师预测普遍存在滞后与偏乐观的倾向。",
        lang,
    )


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Display metadata for the holding-horizon recommendation cards (en/zh).
PROFILE_DISPLAY: dict[str, dict[str, Any]] = {
    "long_term": {"en": "Long-term", "zh": "长线", "horizon_en": "6-24 months", "horizon_zh": "6-24 个月", "tag_en": "momentum / low-vol", "tag_zh": "动量 / 低波动", "order": 1},
    "medium_term": {"en": "Medium-term", "zh": "中线", "horizon_en": "1-6 months", "horizon_zh": "1-6 个月", "tag_en": "trend / reversal", "tag_zh": "趋势 / 反转", "order": 2},
    "short_term": {"en": "Short-term", "zh": "短线", "horizon_en": "1-4 weeks", "horizon_zh": "1-4 周", "tag_en": "reversal / short trend", "tag_zh": "反转 / 短趋势", "order": 3},
}

# Index/sector ETFs tracked in the "fund & index" section regardless of the user's universe.
FUND_TRACKERS: list[dict[str, str]] = [
    {"symbol": "QQQ", "label_en": "Nasdaq 100", "label_zh": "纳斯达克100"},
    {"symbol": "SPY", "label_en": "S&P 500", "label_zh": "标普500"},
    {"symbol": "DIA", "label_en": "Dow Jones", "label_zh": "道琼斯"},
    {"symbol": "SMH", "label_en": "Semiconductors", "label_zh": "半导体"},
    {"symbol": "AIQ", "label_en": "AI & Tech", "label_zh": "人工智能"},
]
# Index/sector ETFs never have analyst price targets and are already covered by their own
# section above — keep them out of the single-stock picks (潜力股/高风险/研究推荐).
_FUND_TRACKER_SYMBOLS = {spec["symbol"] for spec in FUND_TRACKERS}

# Click-to-expand detail charts: timeframe windows in trading days, from daily closes.
# 数据库是日线收盘，无盘中数据 —— 最短窗口为 1 周（当日涨跌已在行内展示）。
_DETAIL_WINDOWS: list[tuple[str, int]] = [("1W", 5), ("1M", 21), ("6M", 126), ("1Y", 252), ("5Y", 1260)]
_DETAIL_MAX_POINTS = 100  # 每条曲线降采样上限，控制 HTML/JSON 体积
_DETAIL_DEFAULT_TF = "1M"
_CHART_H = 150  # 走势图 viewBox 高度，与 CSS 里的 .dp-svg 高度一致
_CHART_W = 640  # viewBox 宽度；preserveAspectRatio="none"，实际按容器宽拉伸
_CHART_PAD = 6  # 上下留白，避免曲线贴边；hover 反算价格要用同一个值
_TF_LABELS: dict[str, tuple[str, str]] = {
    "1W": ("1W", "近1周"),
    "1M": ("1M", "近1月"),
    "6M": ("6M", "近6月"),
    "1Y": ("1Y", "近1年"),
    "5Y": ("5Y", "近5年"),
}

_MAX_TARGET_WORKERS = 5
_TARGET_RETRY_DELAY_S = 0.6


def fetch_analyst_price_targets(symbols: list[str]) -> dict[str, dict[str, float]]:
    """Best-effort analyst price-target range (low/target/high + analyst count) via yfinance —
    degrades to partial/{}.

    仅对当日入选的推荐标的取数（研究推荐卡片的"机构估值区间"条），单只失败直接跳过，
    不影响其余标的；线程池上限沿用 holdings.fetch_live_quotes 的写法。一次失败重试一次
    （短暂延时后），缓解并发请求偶发被限流导致同一只标的在报告里退化成旧强度条。
    用 ``.info`` 而非 ``get_analyst_price_targets()``，同一次请求里顺带拿到覆盖机构数
    （``numberOfAnalystOpinions``），供卡片标注置信度用，实测耗时相近、不多花网络成本。
    """
    if not symbols:
        return {}
    try:
        yf = import_yfinance()
    except Exception:
        return {}

    def _fetch(symbol: str) -> dict[str, float] | None:
        info = yf.Ticker(symbol).info
        low = info.get("targetLowPrice")
        high = info.get("targetHighPrice")
        mid = info.get("targetMedianPrice", info.get("targetMeanPrice"))
        if low is None or high is None or mid is None or float(high) <= float(low):
            return None
        result = {"low": float(low), "target": float(mid), "high": float(high)}
        analyst_count = info.get("numberOfAnalystOpinions")
        if analyst_count is not None:
            result["analyst_count"] = int(analyst_count)
        return result

    def _one(symbol: str) -> tuple[str, dict[str, float]] | None:
        for attempt in range(2):
            try:
                result = _fetch(symbol)
                if result is not None:
                    return symbol, result
            except Exception:
                pass
            if attempt == 0:
                time.sleep(_TARGET_RETRY_DELAY_S)
        return None

    workers = max(1, min(_MAX_TARGET_WORKERS, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_one, symbols))
    return dict(item for item in results if item is not None)


def _level_zh(level: str) -> str:
    return {"low": "低", "medium": "中", "high": "高"}.get(level, level)


def build_market_report(
    config: AppConfig,
    quote_fetcher: Callable[[list[str]], dict[str, float]] | None = None,
    target_fetcher: Callable[[list[str]], dict[str, dict[str, float]]] | None = None,
) -> dict[str, Any]:
    """Build the full daily market intelligence report payload.

    ``quote_fetcher`` is injectable for offline tests (None -> live yfinance quotes);
    it is only invoked when the chat-managed portfolio actually has holdings.
    ``target_fetcher`` is likewise injectable (None -> live yfinance analyst targets);
    it is only invoked when the quant picks section is non-empty.
    """
    mi = config.market_intel
    lang = normalize_language(config.language)
    generated_at = datetime.now(UTC).isoformat()

    # Fixed index/sector ETFs are always tracked, regardless of the user's own universe.
    fund_symbols = [spec["symbol"] for spec in FUND_TRACKERS]
    extra_funds = [s for s in fund_symbols if s not in config.data.universe]
    if extra_funds:
        merged_data = dataclasses.replace(config.data, universe=[*config.data.universe, *extra_funds])
        config = dataclasses.replace(config, data=merged_data)

    report: dict[str, Any] = {
        "generated_at": generated_at,
        "language": lang,
        "as_of_date": None,
        "data_status": "unavailable",
        "universe_size": len(config.data.universe),
        "market_overview": {},
        "fund_trackers": [],
        "buy_candidates": [],
        "high_risk": [],
        "quant_candidates": {},
        "holding_profiles": [],
        "detail_charts": {},
        "news": [],
        "company_news": {},
        "social": [],
        "social_enabled": mi.social_enabled,
        "warnings": [],
        "sources": {"news_feeds": mi.news_feeds, "social_feeds": mi.social_feeds},
        "disclaimer": _disclaimer(lang),
    }

    prices: pd.DataFrame | None = None
    try:
        prices = load_prices(config.data)
    except Exception as exc:  # pragma: no cover - network/data dependent
        report["warnings"].append(f"price_data_unavailable: {exc}")

    # 按标的分组一次，供持仓 sparkline / 基金追踪 / 详情走势图复用。
    by_symbol = _group_by_symbol(prices)

    analysis_symbols: list[str] = []
    analysis_metrics: dict[str, Any] = {}
    if by_symbol:
        report["data_status"] = "ok"
        analysis = _price_analysis(prices, config.strategy.benchmark, lang)
        analysis_metrics = analysis["metrics_by_symbol"]
        report["as_of_date"] = analysis["as_of_date"]
        report["market_overview"] = analysis["overview"]
        report["buy_candidates"] = analysis["buy_candidates"]
        report["high_risk"] = analysis["high_risk"]
        analysis_symbols = analysis["focus_symbols"]
        report["quant_candidates"] = _quant_candidates(prices, config, lang)
        report["fund_trackers"] = _fund_tracker_snapshot(by_symbol, lang)

    # Chat-managed portfolio: holdings snapshot (P&L) + held symbols lead the news focus.
    portfolio: dict[str, Any] = {}
    try:
        portfolio = holdings_store.load_portfolio(config.portfolio_path)
    except Exception as exc:
        report["warnings"].append(f"portfolio_unreadable: {exc}")
    holding_symbols = [h["symbol"] for h in portfolio.get("holdings", [])]
    if holding_symbols:
        # 运行时经模块属性取默认 fetcher（而非 import 期绑定），保证可注入/可 monkeypatch。
        fetcher = quote_fetcher if quote_fetcher is not None else holdings_store.fetch_live_quotes
        quotes = fetcher(holding_symbols)  # {} on network failure -> last close
        report["holdings"] = holdings_store.build_holdings_snapshot(portfolio, prices, quotes)
        _attach_holding_sparklines(report["holdings"], by_symbol)
        focus = list(holding_symbols)
        focus += [symbol for symbol in analysis_symbols if symbol not in focus]
        analysis_symbols = focus[:12]

    valuations: dict[str, dict[str, float]] = {}
    if report["quant_candidates"] or report.get("holdings"):
        valuations = _attach_valuation_and_holdings(report, target_fetcher)

    # 持仓画像：每只持仓的趋势/风险统计 + 分析师区间 + 量化打分名次（纯事实，不含买卖方向）。
    if report.get("holdings") and analysis_metrics:
        report["holding_profiles"] = _build_holding_profiles(
            report, analysis_metrics, valuations, config.strategy.benchmark
        )

    # 点开展开的走势详情：报告里出现过的每只标的都配 1W-5Y 的收盘价序列。
    if by_symbol:
        report["detail_charts"] = _build_detail_charts(by_symbol, _detail_chart_symbols(report))

    # Market-wide financial media headlines.
    report["news"], news_errors = _collect_feeds(mi.news_feeds, mi.max_news_items, mi.request_timeout)
    report["warnings"].extend(news_errors)
    if mi.news_feeds and not report["news"]:
        report["warnings"].append("no_news_fetched: all financial RSS feeds returned no items (check network)")

    # Optional social / X-style commentary feeds (default off, often unstable).
    if mi.social_enabled and mi.social_feeds:
        report["social"], social_errors = _collect_feeds(mi.social_feeds, mi.max_news_items, mi.request_timeout)
        report["warnings"].extend(social_errors)
    elif mi.social_enabled and not mi.social_feeds:
        report["warnings"].append("social_enabled but no social_feeds configured")

    # Per-company latest news for the focus symbols.
    if analysis_symbols:
        report["company_news"] = _collect_symbol_news(
            analysis_symbols, mi.symbol_news_count, mi.max_symbol_news, mi.request_timeout
        )

    # 回填到持仓画像：持仓标的排在 focus 最前，所以这里基本都能命中。
    # （放在这里是因为 company_news 到这一步才抓完；画像段本身在渲染时才用到它。）
    company_news = report.get("company_news") or {}
    for profile in report.get("holding_profiles") or []:
        profile["news"] = company_news.get(profile["symbol"], [])

    # 手写的持仓资讯归纳（data/news_digest.json，与 portfolio 同目录）—— 不触发任何 LLM 调用。
    try:
        _attach_news_digest(report, load_news_digest(config.portfolio_path.parent / "news_digest.json"))
    except ValueError as exc:
        report["warnings"].append(f"news_digest_unreadable: {exc}")

    return report


def _group_by_symbol(prices: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    """Split the long price table into per-symbol, date-sorted frames — once per report.

    多个 section 都要按标的取序列（持仓 sparkline / 基金追踪 / 详情走势图）；各自做
    ``prices[prices["symbol"] == sym]`` 是一次全表扫描，标的一多就退化成 O(标的数 × 总行数)。
    ``normalize_prices`` 已按 (symbol, date) 排好序，这里的 sort 只是对未规范化输入的兜底。
    """
    if prices is None or prices.empty:
        return {}
    return {str(symbol): group.sort_values("date") for symbol, group in prices.groupby("symbol", sort=False)}


def _attach_holding_sparklines(holdings: dict[str, Any], by_symbol: dict[str, pd.DataFrame], window: int = 30) -> None:
    """Attach the Chinese display name and a recent-close series (for the sparkline) to each position."""
    for position in holdings.get("positions", []):
        position["name_zh"] = name_zh(position["symbol"])
        group = by_symbol.get(position["symbol"])
        if group is None:
            continue
        series = group["adj_close"].astype(float).tail(window).tolist()
        position["spark"] = [round(v, 4) for v in series]


def _attach_valuation_and_holdings(
    report: dict[str, Any],
    target_fetcher: Callable[[list[str]], dict[str, dict[str, float]]] | None,
) -> dict[str, dict[str, float]]:
    """Attach the analyst valuation range to each pick and pin held symbols to the front.

    就地修改 ``report["quant_candidates"]``：每只标的挂上 ``valuation``（估值区间，取不到则
    为 None，卡片降级为"暂无机构估值覆盖"占位文案）和 ``holding``（命中本人持仓时的股数/成本/盈亏）；
    每个持有周期栏目内，命中持仓的标的稳定排到最前（榜首 = 01）。

    返回取到的估值表（symbol -> 区间），持仓画像栏目复用它，避免二次抓取。
    """
    quant = report["quant_candidates"]
    all_symbols: list[str] = []
    for data in quant.values():
        for s in data.get("symbols", []):
            if s["symbol"] not in all_symbols:
                all_symbols.append(s["symbol"])
    # 持仓标的即使没进推荐榜也要取估值 —— 持仓画像栏目要展示它们的分析师区间。
    for position in report.get("holdings", {}).get("positions", []):
        if position["symbol"] not in all_symbols:
            all_symbols.append(position["symbol"])
    fetcher = target_fetcher if target_fetcher is not None else fetch_analyst_price_targets
    valuations = fetcher(all_symbols) if all_symbols else {}
    if all_symbols and not valuations:
        # 大盘个股几乎总有分析师覆盖：全军覆没基本可以断定是取数环节挂了（网络 /
        # yfinance cookie 缓存），必须在报告里说明，否则满屏“暂无机构估值覆盖”会误导读者。
        report["warnings"].append(
            f"analyst_targets_unavailable: got 0 analyst price targets for all {len(all_symbols)} "
            "pick/holding symbols — the 'no analyst coverage' placeholders below almost certainly mean "
            "the fetch failed (network / yfinance cache), not that coverage is actually missing"
        )
    holding_positions = {p["symbol"]: p for p in report.get("holdings", {}).get("positions", [])}

    for data in quant.values():
        symbols = data.get("symbols", [])
        for s in symbols:
            s["valuation"] = valuations.get(s["symbol"])
            position = holding_positions.get(s["symbol"])
            s["holding"] = (
                {
                    "shares": position["shares"],
                    "cost_basis": position.get("cost_basis"),
                    "unrealized_pnl_pct": position.get("unrealized_pnl_pct"),
                }
                if position
                else None
            )
        symbols.sort(key=lambda s: 0 if s["holding"] else 1)
    return valuations


def load_news_digest(path: Path) -> dict[str, Any]:
    """Load the hand-written per-holding news digest (``data/news_digest.json``).

    这份归纳由助手在对话里写好后存盘，报告只负责呈现 —— 项目本身不为此调用任何 LLM API。
    结构：``{"as_of": "YYYY-MM-DD", "digests": {"WDC": "一句话", ...}}``。
    文件不存在是正常情况（返回空）；存在但解析不了则报错，避免把损坏内容当"没有归纳"静默略过。
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid news digest file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid news digest file {path}: top-level JSON must be an object")
    digests = raw.get("digests")
    if digests is not None and not isinstance(digests, dict):
        raise ValueError(f"Invalid news digest file {path}: 'digests' must be an object")
    return {
        "as_of": str(raw.get("as_of") or ""),
        "digests": {str(k).strip().upper(): str(v) for k, v in (digests or {}).items() if str(v).strip()},
    }


def _attach_news_digest(report: dict[str, Any], digest: dict[str, Any]) -> None:
    """把手写归纳挂到持仓画像上，并记录它的日期（与报告不同日时渲染层会标注）。"""
    digests = digest.get("digests") or {}
    if not digests:
        return
    as_of = digest.get("as_of") or ""
    stale = bool(as_of) and as_of != report.get("as_of_date")
    for profile in report.get("holding_profiles") or []:
        if text := digests.get(profile["symbol"]):
            profile["news_digest"] = text
            profile["news_digest_as_of"] = as_of
            profile["news_digest_stale"] = stale


def _build_holding_profiles(
    report: dict[str, Any],
    metrics: dict[str, Any],
    valuations: dict[str, dict[str, float]],
    benchmark: str,
) -> list[dict[str, Any]]:
    """Per-holding factual snapshot: trend, returns, risk stats, analyst range, quant standing.

    只汇总客观统计与第三方一致预期，**不产生任何买卖方向或目标价预测** —— 报告的定位是
    把判断材料摆齐，决策留给读者（见 disclaimer）。数据全部复用已算好的结果，不额外取数。
    """
    positions = report.get("holdings", {}).get("positions") or []
    if not positions:
        return []
    bench = metrics.get(benchmark.upper()) or {}
    bench_21d = bench.get("ret_21d")

    # 该标的在各持有周期榜单里的名次（1-based），用于说明量化打分怎么看它。
    standing: dict[str, list[dict[str, Any]]] = {}
    for data in (report.get("quant_candidates") or {}).values():
        for rank, s in enumerate(data.get("symbols", []), start=1):
            standing.setdefault(s["symbol"], []).append(
                {"label": data.get("label_zh") or data.get("label"), "rank": rank, "score": s.get("score")}
            )

    out: list[dict[str, Any]] = []
    for position in positions:
        symbol = position["symbol"]
        m = metrics.get(symbol)
        if not m:
            continue
        ret_21d = m.get("ret_21d")
        out.append(
            {
                "symbol": symbol,
                "name_zh": position.get("name_zh"),
                "last_price": m.get("last_price"),
                "weight_pct": None,  # 由下面统一按市值占比回填
                "trend_up": m.get("trend_up"),
                "ret_5d_pct": _as_pct(m.get("ret_5d")),
                "ret_21d_pct": _as_pct(ret_21d),
                "ret_63d_pct": _as_pct(m.get("ret_63d")),
                "vol_annual_pct": _as_pct(m.get("vol_annual")),
                "max_drawdown_252_pct": _as_pct(m.get("max_drawdown_252")),
                "dist_from_high_pct": _as_pct(m.get("dist_from_high")),
                "vs_benchmark_21d_pct": (
                    round((ret_21d - bench_21d) * 100, 2) if ret_21d is not None and bench_21d is not None else None
                ),
                "valuation": valuations.get(symbol),
                "quant_standing": standing.get(symbol, []),
            }
        )

    total_mv = report.get("holdings", {}).get("totals", {}).get("market_value")
    if total_mv:
        by_symbol = {p["symbol"]: p for p in positions}
        for profile in out:
            mv = by_symbol[profile["symbol"]].get("market_value")
            if mv is not None:
                profile["weight_pct"] = round(mv / total_mv * 100, 1)
    return out


def _as_pct(value: float | None) -> float | None:
    """比率 -> 百分比（两位小数）；None 透传。"""
    return round(value * 100, 2) if value is not None else None


def write_market_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "market_intel.json"
    md_path = output_dir / "market_intel.md"
    html_path = output_dir / "market_intel.html"
    artifact_path = output_dir / "market_intel_artifact.html"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    artifact_path.write_text(render_artifact_html(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path, "html": html_path, "artifact": artifact_path}


# ---------------------------------------------------------------------------
# Price-based analysis
# ---------------------------------------------------------------------------


def _price_analysis(prices: pd.DataFrame, benchmark: str, lang: str = "en") -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    as_of = prices["date"].max()
    for symbol, group in prices.groupby("symbol", sort=False):
        g = group.sort_values("date")
        adj = g["adj_close"].astype(float)
        if len(adj) < 30:
            continue
        last = float(adj.iloc[-1])
        ret_1d = _pct(adj, 1)
        ret_5d = _pct(adj, 5)
        ret_21d = _pct(adj, 21)
        ret_63d = _pct(adj, 63)
        daily_ret = adj.pct_change().dropna()
        window = daily_ret.tail(20)
        vol_annual = float(window.std() * (252 ** 0.5)) if len(window) >= 5 else None
        ma_20 = float(adj.tail(20).mean())
        ma_50 = float(adj.tail(50).mean()) if len(adj) >= 50 else ma_20
        trend_up = ma_20 >= ma_50
        hist = adj.tail(252)
        high_252 = float(hist.max())
        dist_from_high = (last / high_252) - 1.0 if high_252 else 0.0
        drawdown = _max_drawdown(hist)
        rows.append(
            {
                "symbol": str(symbol),
                "last_price": round(last, 2),
                "ret_1d": ret_1d,
                "ret_5d": ret_5d,
                "ret_21d": ret_21d,
                "ret_63d": ret_63d,
                "vol_annual": round(vol_annual, 4) if vol_annual is not None else None,
                "trend_up": bool(trend_up),
                "dist_from_high": round(dist_from_high, 4),
                "max_drawdown_252": round(drawdown, 4),
            }
        )

    frame = pd.DataFrame(rows)
    overview = _market_overview(frame, benchmark)
    # Benchmark lookup needs the full frame; candidate ranking excludes the fixed fund/index ETFs.
    candidate_frame = frame[~frame["symbol"].isin(_FUND_TRACKER_SYMBOLS)] if not frame.empty else frame
    buy_candidates = _rank_buy_candidates(candidate_frame, lang)
    high_risk = _rank_high_risk(candidate_frame, lang)
    focus = []
    for item in (*buy_candidates, *high_risk):
        if item["symbol"] not in focus:
            focus.append(item["symbol"])
    return {
        "as_of_date": str(as_of.date()),
        "overview": overview,
        "buy_candidates": buy_candidates,
        "high_risk": high_risk,
        "focus_symbols": focus[:12],
        # 每只标的的完整指标（持仓画像栏目要用；上面的榜单只保留了入选的那些）。
        "metrics_by_symbol": {r["symbol"]: r for r in rows},
    }


def _market_overview(frame: pd.DataFrame, benchmark: str) -> dict[str, Any]:
    if frame.empty:
        return {}
    valid = frame.dropna(subset=["ret_21d"])
    advancing = float((valid["ret_5d"] > 0).mean()) if not valid.empty else 0.0
    overview = {
        "symbols_analyzed": int(len(frame)),
        "breadth_5d_advancing_pct": round(advancing * 100, 1),
        "avg_ret_5d_pct": round(float(valid["ret_5d"].mean()) * 100, 2) if not valid.empty else None,
        "avg_ret_21d_pct": round(float(valid["ret_21d"].mean()) * 100, 2) if not valid.empty else None,
    }
    bench = frame[frame["symbol"] == benchmark.upper()]
    if not bench.empty:
        row = bench.iloc[0]
        overview["benchmark"] = benchmark.upper()
        overview["benchmark_ret_5d_pct"] = round(float(row["ret_5d"]) * 100, 2) if pd.notna(row["ret_5d"]) else None
        overview["benchmark_ret_21d_pct"] = round(float(row["ret_21d"]) * 100, 2) if pd.notna(row["ret_21d"]) else None
        overview["benchmark_trend_up"] = bool(row["trend_up"])
    return overview


def _rank_buy_candidates(frame: pd.DataFrame, lang: str = "en", limit: int = 8) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    df = frame.dropna(subset=["ret_21d", "vol_annual"]).copy()
    if df.empty:
        return []
    vol_median = float(df["vol_annual"].median())
    favorable = df[
        df["trend_up"]
        & (df["ret_21d"] > 0)
        & (df["ret_5d"] > -0.05)
        & (df["dist_from_high"] > -0.15)
        & (df["vol_annual"] <= vol_median * 1.25)
    ].copy()
    if favorable.empty:
        favorable = df[df["trend_up"] & (df["ret_21d"] > 0)].copy()
    # Reward trend strength, penalize volatility.
    favorable["focus_score"] = favorable["ret_21d"] / favorable["vol_annual"].clip(lower=0.05)
    favorable = favorable.sort_values("focus_score", ascending=False).head(limit)
    out = []
    for _, row in favorable.iterrows():
        out.append(
            {
                "symbol": row["symbol"],
                "name_zh": name_zh(str(row["symbol"])),
                "last_price": row["last_price"],
                "ret_21d_pct": round(float(row["ret_21d"]) * 100, 2),
                "ret_5d_pct": round(float(row["ret_5d"]) * 100, 2),
                "vol_annual_pct": round(float(row["vol_annual"]) * 100, 1),
                "reason": _favorable_reason(row, lang),
            }
        )
    return out


def _rank_high_risk(frame: pd.DataFrame, lang: str = "en", limit: int = 8) -> list[dict[str, Any]]:
    """High-risk list: names already selling off, plus names stretched near their 52-week
    high that look prone to a pullback under the current run (elevated vol or an extended
    1-month gain while sitting near the high)."""
    if frame.empty:
        return []
    df = frame.dropna(subset=["vol_annual"]).copy()
    if df.empty:
        return []
    vol_threshold = float(df["vol_annual"].quantile(0.75))
    near_high = df["dist_from_high"] >= -0.05
    overextended = df["ret_21d"].fillna(0) >= 0.12
    elevated_vol = df["vol_annual"] >= vol_threshold
    flagged = df[
        (near_high & (overextended | elevated_vol))
        | (df["max_drawdown_252"] <= -0.20)
        | (df["ret_5d"] <= -0.08)
        | (df["dist_from_high"] <= -0.25)
    ].copy()
    if flagged.empty:
        return []
    # Near-high overextension surfaces first (forward-looking pullback risk), then vol/drawdown.
    flagged["risk_score"] = (
        flagged["vol_annual"].fillna(0)
        - flagged["max_drawdown_252"].fillna(0)
        + flagged["ret_21d"].clip(lower=0).fillna(0) * (flagged["dist_from_high"] >= -0.05)
    )
    flagged = flagged.sort_values("risk_score", ascending=False).head(limit)
    out = []
    for _, row in flagged.iterrows():
        out.append(
            {
                "symbol": row["symbol"],
                "name_zh": name_zh(str(row["symbol"])),
                "last_price": row["last_price"],
                "ret_5d_pct": round(float(row["ret_5d"]) * 100, 2) if pd.notna(row["ret_5d"]) else None,
                "ret_21d_pct": round(float(row["ret_21d"]) * 100, 2) if pd.notna(row["ret_21d"]) else None,
                "vol_annual_pct": round(float(row["vol_annual"]) * 100, 1),
                "max_drawdown_252_pct": round(float(row["max_drawdown_252"]) * 100, 1),
                "dist_from_high_pct": round(float(row["dist_from_high"]) * 100, 1),
                "reason": _risk_reason(row, lang),
            }
        )
    return out


def _favorable_reason(row: pd.Series, lang: str = "en") -> str:
    sep = tr("; ", "；", lang)
    parts = []
    if row["trend_up"]:
        parts.append(tr("20-day MA above the 50-day (uptrend)", "20日均线在50日均线上方（趋势向上）", lang))
    parts.append(tr(f"1M {_signed(row['ret_21d'])}", f"近1月{_signed(row['ret_21d'])}", lang))
    parts.append(tr(
        f"annualized vol ~{float(row['vol_annual']) * 100:.0f}% (relatively contained)",
        f"年化波动约{float(row['vol_annual']) * 100:.0f}%（相对可控）",
        lang,
    ))
    if row["dist_from_high"] > -0.05:
        parts.append(tr("near the 52-week high", "接近52周高点附近", lang))
    return sep.join(parts)


def _risk_reason(row: pd.Series, lang: str = "en") -> str:
    sep = tr("; ", "；", lang)
    parts: list[str] = []
    near_high = row["dist_from_high"] >= -0.05
    overextended = pd.notna(row["ret_21d"]) and row["ret_21d"] >= 0.12
    if near_high:
        parts.append(tr("near the 52-week high — pullback risk", "处于52周高点附近，警惕回撤", lang))
    if overextended:
        parts.append(tr(
            f"1M {_signed(row['ret_21d'])} — extended run",
            f"近1月{_signed(row['ret_21d'])}，涨幅偏多",
            lang,
        ))
    parts.append(tr(
        f"annualized vol ~{float(row['vol_annual']) * 100:.0f}% (elevated)",
        f"年化波动约{float(row['vol_annual']) * 100:.0f}%（偏高）",
        lang,
    ))
    if row["max_drawdown_252"] <= -0.20:
        parts.append(tr(
            f"1Y max drawdown {float(row['max_drawdown_252']) * 100:.0f}%",
            f"近一年最大回撤{float(row['max_drawdown_252']) * 100:.0f}%",
            lang,
        ))
    if pd.notna(row["ret_5d"]) and row["ret_5d"] <= -0.08:
        parts.append(tr(
            f"sharp 5-day drop {float(row['ret_5d']) * 100:.0f}%",
            f"近5日急跌{float(row['ret_5d']) * 100:.0f}%",
            lang,
        ))
    if row["dist_from_high"] <= -0.25:
        parts.append(tr(
            f"{float(row['dist_from_high']) * 100:.0f}% from 52-week high",
            f"距52周高点{float(row['dist_from_high']) * 100:.0f}%",
            lang,
        ))
    return sep.join(parts)


def _quant_candidates(prices: pd.DataFrame, config: AppConfig, lang: str = "en") -> dict[str, Any]:
    """Latest cross-sectional quant ranking per research profile."""
    try:
        signals = build_signals(prices, config.strategy.signal_weights)
    except Exception:  # pragma: no cover - defensive
        return {}
    matured = signals.dropna(subset=["score"])
    if matured.empty:
        return {}
    # date 列由 normalize_prices 保证已是 datetime64，无需（重复）转换。
    latest_date = matured["date"].max()
    latest = matured[matured["date"] == latest_date].copy()
    # Index/sector ETFs are covered by the fund-tracker section; they have no analyst targets
    # and don't belong in the single-stock research picks.
    latest = latest[~latest["symbol"].isin(_FUND_TRACKER_SYMBOLS)]
    out: dict[str, Any] = {}
    for profile, spec in RECOMMENDATION_PROFILES.items():
        scored = latest.copy()
        total = 0.0
        parts = []
        for column, weight in spec["weights"].items():
            if column not in scored.columns:
                continue
            parts.append(scored[column] * weight)
            total += abs(weight)
        if not parts or total == 0:
            continue
        scored["profile_score"] = pd.concat(parts, axis=1).sum(axis=1, min_count=1) / total
        scored = scored.dropna(subset=["profile_score"]).sort_values("profile_score", ascending=False).head(5)
        if scored.empty:
            continue
        top_score = float(scored["profile_score"].iloc[0])
        disp = PROFILE_DISPLAY.get(profile, {})
        symbols = []
        for _, r in scored.iterrows():
            score = float(r["profile_score"])
            strength = 100 if top_score <= 0 else max(12, min(100, round(score / top_score * 100)))
            symbol = str(r["symbol"])
            last_price = round(float(r["adj_close"]), 2) if pd.notna(r.get("adj_close")) else None
            day_value, day_pct = _day_change(last_price, r.get("ret_1d"))
            symbols.append(
                {
                    "symbol": symbol,
                    "name_zh": name_zh(symbol),
                    "score": round(score, 3),
                    "strength": strength,
                    "last_price": last_price,
                    "day_change_value": day_value,
                    "day_change_pct": day_pct,
                    "confidence": recommendation_confidence(score),
                    "risk_level": classify_recommendation_risk(r),
                    "reason": _day_change_reason(day_value, day_pct, lang),
                }
            )
        out[profile] = {
            "label": tr(disp.get("en", spec["label"]), disp.get("zh", spec["label"]), lang),
            "label_zh": disp.get("zh", spec["label"]),
            "horizon": tr(disp.get("horizon_en", spec["horizon"]), disp.get("horizon_zh", spec["horizon"]), lang),
            "tag": tr(disp.get("tag_en", ""), disp.get("tag_zh", ""), lang),
            "order": disp.get("order", 99),
            "symbols": symbols,
        }
    return dict(sorted(out.items(), key=lambda kv: kv[1].get("order", 99)))


def _day_change(last_price: float | None, ret_1d: Any) -> tuple[float | None, float | None]:
    """(day_change_value, day_change_pct) from the latest close and its 1-day return."""
    if last_price is None or ret_1d is None or pd.isna(ret_1d) or (1 + float(ret_1d)) == 0:
        return None, None
    ret_1d = float(ret_1d)
    prev_price = last_price / (1 + ret_1d)
    return round(last_price - prev_price, 2), round(ret_1d * 100, 2)


def _day_change_reason(value: float | None, pct: float | None, lang: str = "en") -> str:
    if value is None or pct is None:
        return tr("no intraday change data", "暂无当日涨跌数据", lang)
    sign = "+" if value >= 0 else "-"
    amount = f"{sign}${abs(value):.2f}"
    return tr(f"today {amount} ({pct:+.2f}%)", f"当日 {amount}（{pct:+.2f}%）", lang)


def _pct(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    prev = float(series.iloc[-1 - periods])
    if prev == 0:
        return None
    return round(float(series.iloc[-1]) / prev - 1.0, 4)


def _fund_tracker_snapshot(by_symbol: dict[str, pd.DataFrame], lang: str = "en") -> list[dict[str, Any]]:
    """Latest price + 1D/5D/1M return for the fixed index/sector ETF watch list."""
    out: list[dict[str, Any]] = []
    for spec in FUND_TRACKERS:
        symbol = spec["symbol"]
        group = by_symbol.get(symbol)
        if group is None:
            continue
        adj = group["adj_close"].astype(float)
        if adj.empty:
            continue
        last_price = round(float(adj.iloc[-1]), 2)
        ret_1d = _pct(adj, 1)
        day_value, day_pct = _day_change(last_price, ret_1d)
        out.append(
            {
                "symbol": symbol,
                "label": tr(spec["label_en"], spec["label_zh"], lang),
                "last_price": last_price,
                "day_change_value": day_value,
                "day_change_pct": day_pct,
                "ret_5d_pct": round(r * 100, 2) if (r := _pct(adj, 5)) is not None else None,
                "ret_21d_pct": round(r * 100, 2) if (r := _pct(adj, 21)) is not None else None,
            }
        )
    return out


def _day_str(value: Any) -> str:
    """价格表里的单个日期值 -> ``YYYY-MM-DD``（normalize_prices 已保证是 datetime，这里兜底字符串输入）。"""
    return str(pd.Timestamp(value).date())


def _downsample(values: list[float], max_points: int = _DETAIL_MAX_POINTS) -> list[float]:
    """均匀抽样到 ≤max_points 个点（保首尾），供小尺寸 SVG 曲线用。"""
    if len(values) <= max_points:
        return values
    step = (len(values) - 1) / (max_points - 1)
    return [values[round(i * step)] for i in range(max_points)]


def _detail_chart_symbols(report: dict[str, Any]) -> list[str]:
    """Symbols shown anywhere in the report, in display order (holdings first)."""
    seen: list[str] = []

    def _add(symbol: str) -> None:
        if symbol and symbol not in seen:
            seen.append(symbol)

    for p in (report.get("holdings") or {}).get("positions", []):
        _add(p["symbol"])
    for f in report.get("fund_trackers") or []:
        _add(f["symbol"])
    for c in [*(report.get("buy_candidates") or []), *(report.get("high_risk") or [])]:
        _add(c["symbol"])
    for data in (report.get("quant_candidates") or {}).values():
        for s in data.get("symbols", []):
            _add(s["symbol"])
    return seen


def _build_detail_charts(by_symbol: dict[str, pd.DataFrame], symbols: list[str]) -> dict[str, Any]:
    """Per-symbol close series per timeframe window, for the click-to-expand detail charts.

    每个窗口按交易日数取尾部日线收盘；某窗口已覆盖全部可用历史时不再生成更长的
    重复窗口（避免 1Y/5Y 显示同一条曲线）。序列降采样到 ≤_DETAIL_MAX_POINTS 点。
    """
    out: dict[str, Any] = {}
    for symbol in symbols:
        group = by_symbol.get(symbol)
        if group is None:
            continue
        closes = group["adj_close"].astype(float).tolist()
        if len(closes) < 2:
            continue
        dates = group["date"]  # 只取每个窗口的首尾两天，不整段转换
        available = len(closes) - 1
        windows: dict[str, Any] = {}
        for label, n in _DETAIL_WINDOWS:
            tail_closes = closes[-(n + 1) :]
            if len(tail_closes) < 2:
                continue
            first, last = tail_closes[0], tail_closes[-1]
            windows[label] = {
                "points": [round(v, 4) for v in _downsample(tail_closes)],
                "start": _day_str(dates.iloc[-len(tail_closes)]),
                "mid": _day_str(dates.iloc[-(len(tail_closes) // 2 or 1)]),  # 横轴中间刻度
                "end": _day_str(dates.iloc[-1]),
                "chg_pct": round((last / first - 1) * 100, 2) if first else None,
                "low": round(min(tail_closes), 2),
                "high": round(max(tail_closes), 2),
            }
            if n >= available:
                break  # 该窗口已覆盖全部历史，更长窗口只会重复同一条曲线
        if windows:
            out[symbol] = windows
    return out


def _max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    running_max = series.cummax()
    drawdown = series / running_max - 1.0
    return float(drawdown.min())


def _signed(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:+.1f}%"


# ---------------------------------------------------------------------------
# RSS / news collection
# ---------------------------------------------------------------------------


# RSS 源彼此独立且以超时等待为主：并发抓取把整段耗时从「各源之和」压到「最慢一源」。
_MAX_FEED_WORKERS = 6


def _fetch_feed_with_retry(feed: dict[str, str], per_feed: int, timeout: int) -> list[dict[str, Any]] | Exception:
    """成功返回条目列表；两次尝试都失败时返回最后一个异常（并发 map 下代替 raise）。"""
    last_error: Exception = RuntimeError("unreachable")
    for _attempt in range(2):  # one retry to absorb transient network hiccups
        try:
            return _fetch_rss(feed["url"], per_feed, timeout)
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = exc
    return last_error


def _collect_feeds(
    feeds: list[dict[str, str]], max_items: int, timeout: int
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    per_feed = max(3, max_items // max(len(feeds), 1) + 1)
    if not feeds:
        return items, errors
    workers = max(1, min(_MAX_FEED_WORKERS, len(feeds)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda feed: _fetch_feed_with_retry(feed, per_feed, timeout), feeds))
    for feed, result in zip(feeds, results, strict=True):  # map 保持输入顺序：错误与条目顺序与串行版一致
        if isinstance(result, Exception):
            errors.append(f"feed_failed:{feed.get('name', feed['url'])}: {result}")
            continue
        for entry in result:
            entry["source"] = feed.get("name", feed["url"])
            items.append(entry)
    # Sort newest first when timestamps are available.
    items.sort(key=lambda e: e.get("published_ts") or 0, reverse=True)
    for item in items:
        item.pop("published_ts", None)
    return items[:max_items], errors


def _fetch_rss(url: str, limit: int, timeout: int) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    root = ElementTree.fromstring(raw)
    entries: list[dict[str, Any]] = []
    # RSS 2.0: channel/item ; Atom: feed/entry
    channel_items = root.findall(".//item")
    if channel_items:
        for node in channel_items[:limit]:
            entries.append(
                _news_entry(
                    title=_text(node, "title"),
                    link=_text(node, "link"),
                    published=_text(node, "pubDate"),
                    summary=_text(node, "description"),
                )
            )
        return entries
    ns = "{http://www.w3.org/2005/Atom}"
    for node in root.findall(f".//{ns}entry")[:limit]:
        link_node = node.find(f"{ns}link")
        link = link_node.get("href") if link_node is not None else ""
        entries.append(
            _news_entry(
                title=_text(node, f"{ns}title"),
                link=link or "",
                published=_text(node, f"{ns}updated") or _text(node, f"{ns}published"),
                summary=_text(node, f"{ns}summary"),
            )
        )
    return entries


def _news_entry(title: str, link: str, published: str, summary: str) -> dict[str, Any]:
    return {
        "title": _clean(title),
        "link": link.strip(),
        "published": published.strip(),
        "summary": _clean(summary)[:280],
        "published_ts": _parse_date(published),
    }


def _collect_symbol_news(
    symbols: list[str], symbol_count: int, per_symbol: int, timeout: int
) -> dict[str, list[dict[str, Any]]]:
    try:
        yf = import_yfinance()
    except Exception:  # pragma: no cover - optional dependency
        return {}
    picked = symbols[:symbol_count]
    if not picked:
        return {}

    def _fetch_news(symbol: str) -> list[dict[str, Any]]:
        try:
            return yf.Ticker(symbol).news or []
        except Exception:  # pragma: no cover - network dependent
            return []

    # 逐只请求是纯网络 IO，与估值取数同为 yfinance 端点，沿用相同的并发上限。
    workers = max(1, min(_MAX_TARGET_WORKERS, len(picked)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        raw_by_symbol = list(executor.map(_fetch_news, picked))
    out: dict[str, list[dict[str, Any]]] = {}
    for symbol, raw_news in zip(picked, raw_by_symbol, strict=True):  # map 保持输入顺序
        parsed = []
        for entry in raw_news[: per_symbol * 2]:
            item = _parse_yf_news(entry)
            if item:
                parsed.append(item)
            if len(parsed) >= per_symbol:
                break
        if parsed:
            out[symbol] = parsed
    return out


def _parse_yf_news(entry: dict[str, Any]) -> dict[str, Any] | None:
    # Older yfinance: flat dict; newer: nested under "content".
    content = entry.get("content") if isinstance(entry.get("content"), dict) else entry
    title = content.get("title") or entry.get("title")
    if not title:
        return None
    link = ""
    if isinstance(content.get("clickThroughUrl"), dict):
        link = content["clickThroughUrl"].get("url", "")
    elif isinstance(content.get("canonicalUrl"), dict):
        link = content["canonicalUrl"].get("url", "")
    link = link or entry.get("link", "")
    publisher = ""
    provider = content.get("provider")
    if isinstance(provider, dict):
        publisher = provider.get("displayName", "")
    publisher = publisher or entry.get("publisher", "")
    published = content.get("pubDate") or content.get("displayTime") or ""
    if not published and entry.get("providerPublishTime"):
        try:
            published = datetime.fromtimestamp(int(entry["providerPublishTime"]), tz=UTC).isoformat()
        except (ValueError, OSError):
            published = ""
    return {
        "title": _clean(str(title)),
        "link": str(link).strip(),
        "publisher": str(publisher).strip(),
        "published": str(published).strip(),
    }


def _text(node: Any, tag: str) -> str:
    found = node.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text


def _clean(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    # Strip naive HTML tags from RSS descriptions.
    out = []
    depth = 0
    for char in text:
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
    return " ".join("".join(out).split())


def _parse_date(value: str) -> float | None:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value.strip(), fmt).timestamp()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# LLM prompt + rendering
# ---------------------------------------------------------------------------


def _fmt_money(value: Any, signed: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:+,.2f}" if signed else f"{value:,.2f}"


def _fmt_pct_signed(value: Any) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _fmt_qty(value: Any) -> str:
    return "—" if value is None else f"{float(value):g}"


def _md_symbol_label(symbol: str, name: str | None) -> str:
    return f"{symbol} {name}" if name else symbol


def _quotes_source_label(source: str | None, lang: str) -> str:
    labels = {
        "realtime": tr("realtime quotes", "实时行情", lang),
        "mixed": tr("realtime + last close", "实时/收盘混合", lang),
        "last_close": tr("last close", "上一收盘", lang),
    }
    return labels.get(source or "", labels["last_close"])


def _profile_note(profile: dict[str, Any], lang: str) -> str:
    """把画像里的统计翻译成中性描述短语 —— 只陈述状态，不给方向。"""
    bits: list[str] = []
    bits.append(tr("trend up", "趋势向上", lang) if profile.get("trend_up") else tr("trend down", "趋势向下", lang))
    vol = profile.get("vol_annual_pct")
    if vol is not None:
        level = (
            tr("high vol", "高波动", lang)
            if vol >= 60
            else tr("moderate vol", "中等波动", lang)
            if vol >= 30
            else tr("low vol", "低波动", lang)
        )
        bits.append(f"{level} {vol:.0f}%")
    dist = profile.get("dist_from_high_pct")
    if dist is not None:
        bits.append(tr(f"{dist:.0f}% from 52w high", f"距52周高点 {dist:.0f}%", lang))
    rel = profile.get("vs_benchmark_21d_pct")
    if rel is not None:
        word = tr("ahead of", "跑赢", lang) if rel >= 0 else tr("behind", "跑输", lang)
        bits.append(tr(f"1M {word} benchmark {abs(rel):.1f}pp", f"近1月{word}基准 {abs(rel):.1f}pp", lang))
    return " · ".join(bits)


def _markdown_holding_profiles(report: dict[str, Any], lang: str) -> list[str]:
    profiles = report.get("holding_profiles") or []
    if not profiles:
        return []
    lines = [f"## {tr('Holdings at a glance', '持仓标的画像', lang)}"]
    lines.append(
        tr(
            "_Factual statistics and third-party analyst consensus only — no buy/sell direction, "
            "no price forecast. See the disclaimer._",
            "_仅为客观统计与第三方分析师一致预期，**不含买卖方向、不含价格预测**。见免责声明。_",
            lang,
        )
    )
    lines.append("")
    header = tr(
        "Symbol|Weight|Last|5D|1M|3M|Ann. vol|Max DD (1y)|From 52w high|vs Benchmark (1M)|Analyst range|Quant standing",
        "代码|仓位占比|最新价|近5日|近1月|近3月|年化波动|近一年最大回撤|距52周高点|近1月相对基准|分析师区间|量化榜单名次",
        lang,
    ).split("|")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for p in profiles:
        val = p.get("valuation")
        val_text = (
            f"${val['low']:,.0f}–${val['target']:,.0f}–${val['high']:,.0f}（{val.get('analyst_count', 0)}）"
            if val
            else tr("no coverage", "暂无覆盖", lang)
        )
        standing = p.get("quant_standing") or []
        stand_text = "、".join(f"{s['label']}#{s['rank']}" for s in standing) if standing else "—"
        weight = f"{p['weight_pct']:.1f}%" if p.get("weight_pct") is not None else "—"
        lines.append(
            f"| {p['symbol']}{(' ' + p['name_zh']) if p.get('name_zh') else ''} | {weight} | "
            f"{_fmt_money(p.get('last_price'))} | {_fmt_pct_signed(p.get('ret_5d_pct'))} | "
            f"{_fmt_pct_signed(p.get('ret_21d_pct'))} | {_fmt_pct_signed(p.get('ret_63d_pct'))} | "
            f"{p.get('vol_annual_pct')}% | {p.get('max_drawdown_252_pct')}% | {p.get('dist_from_high_pct')}% | "
            f"{_fmt_pct_signed(p.get('vs_benchmark_21d_pct'))}pp | {val_text} | {stand_text} |"
        )
    lines.append("")
    # 每只持仓的近期资讯：手写归纳（如有）+ 出处标题。
    if any(p.get("news") or p.get("news_digest") for p in profiles):
        lines.append(f"### {tr('Recent news per holding', '持仓近期资讯', lang)}")
        for p in profiles:
            items = p.get("news") or []
            digest = p.get("news_digest")
            if not items and not digest:
                continue
            lines.append(f"- **{p['symbol']}**")
            if digest:
                stale = (
                    f"（{tr('digest as of', '归纳截至', lang)} {p['news_digest_as_of']}）"
                    if p.get("news_digest_stale") and p.get("news_digest_as_of")
                    else ""
                )
                lines.append(f"  - {digest}{stale}")
            for item in items:
                publisher = f" （{item['publisher']}）" if item.get("publisher") else ""
                lines.append(f"  - {item.get('title', '')}{publisher} {item.get('link', '')}")
        lines.append("")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    lang = normalize_language(report.get("language", "en"))
    na = tr("unavailable", "不可用", lang)
    lines = [tr("# Daily US Equity Research Brief", "# 今日美股研究简报", lang), ""]
    lines.append(f"- {tr('Generated (UTC)', '生成时间（UTC）', lang)}: {report.get('generated_at')}")
    lines.append(f"- {tr('Data as of', '数据截止日', lang)}: {report.get('as_of_date') or na}")
    lines.append(f"- {tr('Data status', '数据状态', lang)}: {report.get('data_status')}")
    lines.append("")
    lines.append(f"> {report.get('disclaimer')}")
    lines.append("")

    holdings = report.get("holdings") or {}
    if holdings.get("positions"):
        lines.append(f"## {tr('My holdings', '我的持仓', lang)}")
        lines.append(
            f"_{tr('Priced from', '价格口径', lang)}: "
            f"{_quotes_source_label(holdings.get('quotes_source'), lang)}_"
        )
        lines.append("")
        header = tr(
            "Symbol|Shares|Price|Day|Mkt value|Cost/share|P&L|P&L %",
            "代码|股数|现价|当日|市值|成本价|盈亏|盈亏 %",
            lang,
        )
        lines.append("| " + " | ".join(header.split("|")) + " |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for position in holdings["positions"]:
            lines.append(
                f"| {position['symbol']} | {_fmt_qty(position['shares'])} | {_fmt_money(position['price'])} | "
                f"{_fmt_pct_signed(position['day_change_pct'])} | {_fmt_money(position['market_value'])} | "
                f"{_fmt_money(position['cost_basis'])} | {_fmt_money(position['unrealized_pnl'], signed=True)} | "
                f"{_fmt_pct_signed(position['unrealized_pnl_pct'])} |"
            )
        totals = holdings.get("totals") or {}
        lines.append(
            f"| **{tr('Total', '合计', lang)}** |  |  | {_fmt_money(totals.get('day_pnl'), signed=True)} | "
            f"{_fmt_money(totals.get('market_value'))} | {_fmt_money(totals.get('cost_value'))} | "
            f"{_fmt_money(totals.get('unrealized_pnl'), signed=True)} | "
            f"{_fmt_pct_signed(totals.get('unrealized_pnl_pct'))} |"
        )
        lines.append("")

    lines.extend(_markdown_holding_profiles(report, lang))

    overview = report.get("market_overview") or {}
    if overview:
        lines.append(f"## {tr('Market overview', '市场概览', lang)}")
        if overview.get("benchmark"):
            trend = tr("up", "向上", lang) if overview.get("benchmark_trend_up") else tr("down", "向下", lang)
            lines.append(tr(
                f"- Benchmark {overview['benchmark']}: 5D {overview.get('benchmark_ret_5d_pct')}%, "
                f"1M {overview.get('benchmark_ret_21d_pct')}%, trend {trend}",
                f"- 基准 {overview['benchmark']}：近5日 {overview.get('benchmark_ret_5d_pct')}%，"
                f"近1月 {overview.get('benchmark_ret_21d_pct')}%，趋势{trend}",
                lang,
            ))
        lines.append(tr(
            f"- Sample: {overview.get('symbols_analyzed')}, 5D advancing: {overview.get('breadth_5d_advancing_pct')}%",
            f"- 样本数：{overview.get('symbols_analyzed')}，近5日上涨占比：{overview.get('breadth_5d_advancing_pct')}%",
            lang,
        ))
        lines.append(tr(
            f"- Sample avg: 5D {overview.get('avg_ret_5d_pct')}%, 1M {overview.get('avg_ret_21d_pct')}%",
            f"- 样本平均：近5日 {overview.get('avg_ret_5d_pct')}%，近1月 {overview.get('avg_ret_21d_pct')}%",
            lang,
        ))
        lines.append("")

    if report.get("fund_trackers"):
        lines.append(f"## {tr('Fund & index tracker', '基金/指数追踪', lang)}")
        lines.append("| " + " | ".join(tr(
            "Symbol|Name|Last|Day|5D|1M", "代码|名称|最新价|当日|近5日|近1月", lang).split("|")) + " |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for f in report["fund_trackers"]:
            day = f"{f['day_change_value']:+.2f} ({f['day_change_pct']:+.2f}%)" if f.get("day_change_pct") is not None else "—"
            lines.append(
                f"| {f['symbol']} | {f['label']} | {f['last_price']} | {day} | "
                f"{f.get('ret_5d_pct')}% | {f.get('ret_21d_pct')}% |"
            )
        lines.append("")

    if report.get("buy_candidates"):
        lines.append(f"## {tr('Potential picks (research candidates)', '潜力股（研究候选）', lang)}")
        lines.append("| " + " | ".join(tr(
            "Symbol|Last|1M|5D|Ann. vol|Reason", "代码|最新价|近1月|近5日|年化波动|依据", lang).split("|")) + " |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for c in report["buy_candidates"]:
            lines.append(
                f"| {_md_symbol_label(c['symbol'], c.get('name_zh'))} | {c['last_price']} | {c['ret_21d_pct']}% | {c['ret_5d_pct']}% | "
                f"{c['vol_annual_pct']}% | {c['reason']} |"
            )
        lines.append("")

    if report.get("high_risk"):
        lines.append(f"## {tr('High risk (caution)', '高风险（谨慎）', lang)}")
        lines.append("| " + " | ".join(tr(
            "Symbol|Last|Dist. from high|1M|5D|Reason", "代码|最新价|距52周高点|近1月|近5日|依据", lang).split("|")) + " |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for c in report["high_risk"]:
            lines.append(
                f"| {_md_symbol_label(c['symbol'], c.get('name_zh'))} | {c['last_price']} | {c.get('dist_from_high_pct')}% | "
                f"{c.get('ret_21d_pct')}% | {c.get('ret_5d_pct')}% | {c['reason']} |"
            )
        lines.append("")

    quant = report.get("quant_candidates") or {}
    if quant:
        lines.append(f"## {tr('Quant picks by holding horizon', '按持有周期的量化推荐', lang)}")
        for profile, data in quant.items():
            lines.append(f"### {data.get('label', profile)}（{data.get('horizon', '')}）")
            for s in data.get("symbols", []):
                price = f"${s['last_price']}" if s.get("last_price") is not None else "—"
                label = _md_symbol_label(s["symbol"], s.get("name_zh"))
                prefix = tr("[HELD] ", "【持仓】", lang) if s.get("holding") else ""
                valuation = s.get("valuation")
                val_text = (
                    tr(
                        f", target ${valuation['low']:.0f}-${valuation['target']:.0f}-${valuation['high']:.0f}",
                        f"，估值区间 ${valuation['low']:.0f}-${valuation['target']:.0f}-${valuation['high']:.0f}",
                        lang,
                    )
                    if valuation
                    else ""
                )
                lines.append(
                    f"- {prefix}{label}（{price}, score {s['score']}, "
                    f"risk {s.get('risk_level', 'medium')}, confidence {s.get('confidence', 'low')}{val_text}）: "
                    f"{s.get('reason', '')}"
                )
            lines.append("")

    if report.get("news"):
        lines.append(f"## {tr('Latest financial-media headlines', '最新财经媒体头条', lang)}")
        for n in report["news"][:20]:
            published = f" — {n['published']}" if n.get("published") else ""
            link = f"（{n['link']}）" if n.get("link") else ""
            lines.append(f"- [{n.get('source')}] {n.get('title')}{published} {link}")
        lines.append("")

    company_news = report.get("company_news") or {}
    if company_news:
        lines.append(f"## {tr('Per-company news', '重点个股资讯', lang)}")
        for symbol, items in company_news.items():
            lines.append(f"### {symbol}")
            for n in items:
                publisher = f"（{n['publisher']}）" if n.get("publisher") else ""
                lines.append(f"- {n.get('title')} {publisher} {n.get('link', '')}")
            lines.append("")

    if report.get("social_enabled") and report.get("social"):
        lines.append(f"## {tr('Social commentary (experimental)', '社交平台观点（实验）', lang)}")
        for n in report["social"][:15]:
            lines.append(f"- [{n.get('source')}] {n.get('title')} {n.get('link', '')}")
        lines.append("")

    if report.get("warnings"):
        lines.append(f"## {tr('Notes', '说明', lang)}")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    "family=Poppins:wght@500;600;700&"
    "family=Lora:ital,wght@0,400;0,500;0,600;1,400&"
    "family=Noto+Sans+SC:wght@400;500;700&"
    "family=Noto+Serif+SC:wght@400;500;600&"
    "family=JetBrains+Mono:wght@400;500;700&display=swap\" rel=\"stylesheet\">"
)

_CSS_PALETTE_LIGHT = (
    "--paper:#faf9f5;--card:#ffffff;--sand:#f1efe6;--sand-2:#e8e6dc;"
    "--line:#e3e0d4;--line-2:#d6d3c5;"
    "--ink:#141413;--ink-soft:#34322c;--muted:#6f6d62;--faint:#9a988c;"
    "--orange:#d97757;--orange-deep:#c25e3f;--orange-soft:#f3e0d7;"
    "--blue:#6a9bcc;--green:#788c5d;--green-deep:#5f7548;--down:#c25e3f;--down-deep:#a84a30;"
)

_CSS_PALETTE_DARK = (
    "--paper:#1f1e1a;--card:#262521;--sand:#2d2b25;--sand-2:#35332c;"
    "--line:#3a3830;--line-2:#4a4738;"
    "--ink:#f0efe9;--ink-soft:#d6d4ca;--muted:#a3a193;--faint:#7b796d;"
    "--orange:#e08b6d;--orange-deep:#d97757;--orange-soft:#4a2f24;"
    "--blue:#7fabd6;--green:#96a97a;--green-deep:#7c8f63;--down:#e2836a;--down-deep:#c96b52;"
)

_CSS_FONTS_WEB = (
    '--head:"Poppins","Noto Sans SC",-apple-system,"Segoe UI",sans-serif;'
    '--body:"Lora","Noto Serif SC",Georgia,serif;'
    '--mono:"JetBrains Mono",ui-monospace,monospace;'
)

# Artifact 片段禁止外部资源（严格 CSP），用系统字体栈近似同一气质。
_CSS_FONTS_SYSTEM = (
    '--head:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;'
    '--body:Georgia,"Iowan Old Style","Songti SC",SimSun,serif;'
    '--mono:ui-monospace,"Cascadia Code",Consolas,Menlo,monospace;'
)

# 仅整页文档使用（body 背景、外层容器）；artifact 片段不注入全局规则。
_CSS_PAGE = """
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background:
    radial-gradient(1200px 620px at 82% -8%, rgba(217,119,87,0.08), transparent 62%),
    radial-gradient(900px 500px at -5% 4%, rgba(106,155,204,0.06), transparent 58%),
    var(--paper);
  background-attachment: fixed;
}
.wrap { position: relative; z-index: 1; max-width: 1120px; margin: 0 auto; padding: 0 26px 80px; }
"""

# 组件样式：整页与 artifact 片段共用，全部作用域在 .qa-report 之下。
_CSS_COMPONENTS = """
.qa-report, .qa-report * { box-sizing: border-box; }
.qa-report { color: var(--ink); font-family: var(--body); line-height: 1.65; font-size: 15px; -webkit-font-smoothing: antialiased; }

/* Masthead */
.qa-report header { padding: 56px 0 26px; border-bottom: 1px solid var(--line-2); }
.qa-report .kicker { font-family: var(--mono); font-size: 11.5px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--orange-deep); margin-bottom: 18px; }
.qa-report .kicker::before { content: "✦ "; color: var(--orange); }
.qa-report h1.title { font-family: var(--head); font-weight: 700; font-size: clamp(34px, 5.6vw, 58px); line-height: 1.06; letter-spacing: -0.01em; margin: 0; color: var(--ink); }
.qa-report .title .en { display: block; font-family: var(--body); font-style: italic; font-weight: 400; font-size: clamp(15px, 2vw, 20px); color: var(--muted); letter-spacing: 0.01em; margin-top: 14px; }
.qa-report .metabar { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 26px; }
.qa-report .pill { font-family: var(--mono); font-size: 11.5px; letter-spacing: 0.03em; color: var(--ink-soft); border: 1px solid var(--line-2); border-radius: 999px; padding: 6px 13px; background: var(--card); }
.qa-report .pill b { color: var(--orange-deep); font-weight: 700; }
.qa-report .pill.ok b { color: var(--green); } .qa-report .pill.bad b { color: var(--down); }

/* Disclaimer */
.qa-report .ribbon { display: flex; gap: 12px; align-items: flex-start; margin: 28px 0 6px; padding: 14px 17px; border: 1px solid var(--line); border-left: 3px solid var(--orange); background: linear-gradient(90deg, var(--orange-soft), transparent); border-radius: 0 10px 10px 0; font-size: 13px; color: var(--ink-soft); }
.qa-report .ribbon::before { content: "✦"; color: var(--orange); font-family: var(--mono); }

/* Sections */
.qa-report section { margin-top: 48px; opacity: 0; transform: translateY(16px); animation: qa-rise 0.7s cubic-bezier(.2,.7,.2,1) forwards; }
.qa-report section:nth-of-type(1){animation-delay:.05s} .qa-report section:nth-of-type(2){animation-delay:.12s} .qa-report section:nth-of-type(3){animation-delay:.19s} .qa-report section:nth-of-type(4){animation-delay:.26s} .qa-report section:nth-of-type(5){animation-delay:.33s} .qa-report section:nth-of-type(6){animation-delay:.40s} .qa-report section:nth-of-type(n+7){animation-delay:.45s}
@keyframes qa-rise { to { opacity: 1; transform: none; } }
.qa-report .sec-head { display: flex; align-items: baseline; gap: 13px; margin-bottom: 22px; }
.qa-report .sec-num { font-family: var(--mono); font-size: 12px; color: var(--orange); letter-spacing: 0.08em; font-weight: 500; }
.qa-report h2 { font-family: var(--head); font-weight: 600; font-size: 23px; margin: 0; color: var(--ink); letter-spacing: -0.01em; }
.qa-report .sec-head .hint { font-size: 12px; color: var(--faint); margin-left: auto; font-family: var(--mono); }

/* Stat tiles */
.qa-report .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.qa-report .tile { background: var(--card); padding: 18px 18px 16px; }
.qa-report .tile .t-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
.qa-report .tile .t-value { font-family: var(--mono); font-size: 27px; font-weight: 700; margin-top: 8px; color: var(--ink); }
.qa-report .tile .t-sub { font-family: var(--mono); font-size: 11px; color: var(--muted); margin-top: 6px; }

/* Recommendation columns */
.qa-report .reco-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(248px, 1fr)); gap: 16px; }
.qa-report .reco { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 0 0 6px; overflow: hidden; box-shadow: 0 1px 2px rgba(20,20,19,0.03); }
.qa-report .reco-top { padding: 17px 18px 14px; border-bottom: 1px solid var(--line); position: relative; }
.qa-report .reco-top::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--orange), var(--orange-soft)); }
.qa-report .reco-name { font-family: var(--head); font-weight: 600; font-size: 19px; color: var(--ink); }
.qa-report .reco-meta { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.qa-report .chip { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.04em; padding: 3px 9px; border-radius: 999px; border: 1px solid var(--orange-soft); background: var(--orange-soft); color: var(--orange-deep); }
.qa-report .reco-tag { font-size: 11px; color: var(--faint); font-family: var(--mono); }
.qa-report .pick { padding: 13px 18px; border-bottom: 1px solid var(--sand); }
.qa-report .pick:last-child { border-bottom: 0; }
.qa-report .pick.is-holding { background: linear-gradient(90deg, var(--orange-soft), transparent 60%); }
.qa-report .pick-row { display: flex; align-items: center; gap: 10px; }
.qa-report .rank { font-family: var(--mono); font-size: 11px; color: var(--faint); width: 16px; }
.qa-report .ticker { font-family: var(--mono); font-weight: 700; font-size: 16px; color: var(--ink); letter-spacing: 0.01em; }
.qa-report .name-zh { font-family: var(--body); font-weight: 400; font-size: 0.85em; color: var(--muted); margin-left: 4px; }
.qa-report .price { margin-left: auto; font-family: var(--mono); font-size: 13px; color: var(--muted); }
.qa-report .pick-badges { display: flex; gap: 6px; margin-left: 26px; margin-top: 7px; flex-wrap: wrap; }
.qa-report .pick-badge { font-family: var(--mono); font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 1px 5px; }
.qa-report .pick-badge.high { color: var(--down); }
.qa-report .pick-badge.low { color: var(--green); }
.qa-report .pick-badge.holding { color: var(--orange-deep); border-color: var(--orange-soft); background: var(--orange-soft); }
.qa-report .range { margin: 10px 0 7px; }
.qa-report .range-track { position: relative; height: 6px; border-radius: 3px; background: var(--sand-2); }
.qa-report .range-fill { position: absolute; top: 0; bottom: 0; border-radius: 3px; }
.qa-report .range-zero { position: absolute; left: 50%; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--ink-soft); }
.qa-report .range-caption { display: flex; justify-content: space-between; margin-top: 5px; font-family: var(--mono); font-size: 10px; color: var(--faint); }
.qa-report .range-caption .tgt { color: var(--orange-deep); }
.qa-report .range-empty { margin: 10px 0 7px; font-family: var(--mono); font-size: 10.5px; color: var(--faint); }
.qa-report .pick .why { font-size: 11.5px; color: var(--muted); font-family: var(--mono); }
.qa-report .pick .why.pos { color: var(--green); } .qa-report .pick .why.neg { color: var(--down); }

/* Data tables (holdings / buy / risk) */
.qa-report .panel { border: 1px solid var(--line); border-radius: 16px; overflow: hidden; background: var(--card); }
.qa-report .panel { overflow-x: auto; }
.qa-report table { width: 100%; border-collapse: collapse; font-size: 14px; }
.qa-report thead th { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); text-align: left; padding: 13px 16px; background: var(--sand); border-bottom: 1px solid var(--line); }
.qa-report tbody td { padding: 13px 16px; border-bottom: 1px solid var(--sand); vertical-align: middle; }
.qa-report tbody tr:last-child td { border-bottom: 0; }
.qa-report tbody tr:hover td { background: var(--sand); }
.qa-report td.sym { font-family: var(--mono); font-weight: 700; font-size: 15px; }
.qa-report .buy td.sym { color: var(--green); } .qa-report .risk td.sym { color: var(--down); }
.qa-report .holdings td.sym { color: var(--orange-deep); }
.qa-report td.spark-cell { line-height: 0; }
.qa-report svg.spark { vertical-align: middle; }
.qa-report td.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.qa-report .why-cell { color: var(--muted); font-size: 12.5px; max-width: 320px; }
.qa-report .pos { color: var(--green); } .qa-report .neg { color: var(--down); } .qa-report .flat { color: var(--muted); } .qa-report .muted { color: var(--faint); }

/* Narrative */

/* News */
.qa-report .news-list { display: grid; gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.qa-report .news-item { background: var(--card); padding: 14px 17px; display: flex; gap: 14px; align-items: baseline; transition: background .15s; }
.qa-report .news-item:hover { background: var(--sand); }
.qa-report .src { flex: none; font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.03em; color: var(--orange-deep); border: 1px solid var(--orange-soft); background: var(--orange-soft); border-radius: 6px; padding: 3px 8px; min-width: 100px; text-align: center; }
.qa-report .news-item a, .qa-report .news-item .h { color: var(--ink); text-decoration: none; font-size: 14.5px; }
.qa-report .news-item a:hover { color: var(--orange-deep); text-decoration: underline; }
.qa-report .news-item time { margin-left: auto; flex: none; font-family: var(--mono); font-size: 11px; color: var(--faint); white-space: nowrap; }

/* Company news */
.qa-report .co-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
.qa-report .co { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; }
.qa-report .co h3 { font-family: var(--mono); font-size: 14px; color: var(--orange-deep); margin: 0 0 10px; letter-spacing: 0.03em; font-weight: 700; }
.qa-report .co ul { margin: 0; padding: 0; list-style: none; }
.qa-report .co li { padding: 8px 0; border-top: 1px solid var(--sand); font-size: 13.5px; }
.qa-report .co li:first-child { border-top: 0; }
.qa-report .co a { color: var(--ink); text-decoration: none; } .qa-report .co a:hover { color: var(--orange-deep); }
.qa-report .co .pub { color: var(--faint); font-size: 11px; font-family: var(--mono); }

/* Holdings at a glance — per-holding factual cards */
.qa-report .hp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
.qa-report .hp-card { border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; background: var(--card); }
.qa-report .hp-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.qa-report .hp-weight { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--muted); }
.qa-report .hp-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 6px 10px; margin-bottom: 10px; }
.qa-report .hp-stat { display: flex; flex-direction: column; gap: 1px; }
.qa-report .hp-k { font-size: 10px; color: var(--faint); text-transform: uppercase; letter-spacing: .04em; }
.qa-report .hp-v { font-family: var(--mono); font-size: 12.5px; }
.qa-report .hp-standing { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.qa-report .hp-none { font-family: var(--mono); font-size: 10.5px; color: var(--faint); }
.qa-report .hp-news { margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--line); }
.qa-report .hp-news ul { list-style: none; margin: 5px 0 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.qa-report .hp-news li { font-size: 12px; line-height: 1.45; }
.qa-report .hp-news a { color: var(--ink-soft); text-decoration: none; }
.qa-report .hp-news a:hover { color: var(--orange-deep); }
.qa-report .hp-news .pub { margin-left: 6px; color: var(--faint); font-size: 10.5px; font-family: var(--mono); }
.qa-report .hp-digest { margin: 6px 0 2px; font-size: 12.5px; line-height: 1.55; color: var(--ink-soft); }
.qa-report .hp-stale { margin-left: 6px; font-family: var(--mono); font-size: 10px; color: var(--orange-deep); white-space: nowrap; }

/* Click-to-expand price detail (pure CSS — the artifact fragment must stay JS-free) */
.qa-report .sym-toggle { cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.qa-report .sym-toggle::after { content: "▾"; font-size: 9px; color: var(--faint); transition: transform .15s; }
.qa-report tr:has(.row-toggle:checked) .sym-toggle::after { transform: rotate(180deg); color: var(--orange-deep); }
.qa-report .row-toggle { display: none; }
.qa-report tr.detail-row { display: none; }
.qa-report tr:has(.row-toggle:checked) + tr.detail-row { display: table-row; }
.qa-report tr.detail-row > td { background: var(--sand); padding: 12px 16px 14px; }
.qa-report tr.detail-row:hover > td { background: var(--sand); }
.qa-report .dp-radio { display: none; }
.qa-report .dp-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.qa-report .dp-tab { font-family: var(--mono); font-size: 10.5px; padding: 3px 10px; border: 1px solid var(--line-2); border-radius: 999px; color: var(--muted); cursor: pointer; background: var(--card); }
.qa-report .dp-pane { display: none; }
.qa-report .dp-svg { width: 100%; height: 150px; display: block; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }
.qa-report .dp-caption { display: flex; justify-content: space-between; gap: 10px; margin-top: 6px; font-family: var(--mono); font-size: 10.5px; color: var(--muted); flex-wrap: wrap; }
/* 坐标轴 + hover 读数。所有覆盖层 pointer-events:none，鼠标事件始终落在 svg 上。 */
.qa-report .dp-chart { position: relative; }
.qa-report .dp-grid { stroke: var(--line); stroke-width: 1; stroke-dasharray: 2 5; vector-effect: non-scaling-stroke; }
.qa-report .dp-ay { position: absolute; inset: 0 auto 0 5px; height: 150px; padding: 1px 0; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; pointer-events: none; }
.qa-report .dp-ay span, .qa-report .dp-ax span { font-family: var(--mono); font-size: 9.5px; line-height: 1; color: var(--faint); }
.qa-report .dp-ay span { background: var(--card); padding: 1px 3px; border-radius: 3px; }
.qa-report .dp-ax { display: flex; justify-content: space-between; padding: 5px 4px 0; }
.qa-report .dp-cursor { position: absolute; top: 0; height: 150px; width: 1px; background: var(--orange); opacity: 0.55; pointer-events: none; }
.qa-report .dp-dot { position: absolute; width: 7px; height: 7px; margin: -3.5px 0 0 -3.5px; border-radius: 50%; background: var(--orange); box-shadow: 0 0 0 2px var(--card); pointer-events: none; }
.qa-report .dp-tip { position: absolute; transform: translate(-50%, -140%); background: var(--ink); color: var(--paper); font-family: var(--mono); font-size: 10.5px; font-weight: 500; padding: 3px 8px; border-radius: 6px; white-space: nowrap; pointer-events: none; z-index: 3; }
.qa-report .dp-cursor[hidden], .qa-report .dp-dot[hidden], .qa-report .dp-tip[hidden] { display: none; }
.qa-report details.dp-details { margin-top: 8px; }
.qa-report details.dp-details > summary { list-style: none; cursor: pointer; font-family: var(--mono); font-size: 10.5px; color: var(--faint); }
.qa-report details.dp-details > summary::-webkit-details-marker { display: none; }
.qa-report details.dp-details > summary::after { content: " ▾"; }
.qa-report details.dp-details[open] > summary::after { content: " ▴"; }
.qa-report details.dp-details[open] > summary { color: var(--orange-deep); }
.qa-report details.dp-details > .dp { margin-top: 8px; }

/* Warnings + footer */
.qa-report .notes { font-size: 12.5px; color: var(--muted); }
.qa-report .notes li { font-family: var(--mono); }
.qa-report footer { margin-top: 64px; padding-top: 22px; border-top: 1px solid var(--line-2); font-size: 11.5px; color: var(--faint); font-family: var(--mono); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.qa-report .empty { color: var(--muted); font-size: 13px; padding: 18px; border: 1px dashed var(--line-2); border-radius: 12px; background: var(--card); }
@media (max-width: 600px) { .qa-report .news-item { flex-wrap: wrap; } .qa-report .news-item time { margin-left: 0; } .qa-report header { padding-top: 36px; } }
"""

# 详情面板的时间段切换：第 k 个 radio 选中 -> 第 k 个 tab 高亮 + 第 k 个图可见（纯 CSS）。
_CSS_COMPONENTS += "".join(
    f".qa-report .dp > .dp-radio:nth-of-type({i}):checked ~ .dp-panes > .dp-pane:nth-of-type({i}) {{ display: block; }}\n"
    f".qa-report .dp > .dp-radio:nth-of-type({i}):checked ~ .dp-tabs > .dp-tab:nth-of-type({i}) "
    "{ color: var(--orange-deep); border-color: var(--orange); background: var(--orange-soft); }\n"
    for i in range(1, len(_DETAIL_WINDOWS) + 1)
)

# 顶部栏目切换：把 11 个 section 收进几个标签页，首屏只渲染一页。
_CSS_COMPONENTS += """
.qa-report .qa-tabs { margin-top: 30px; }
.qa-report .qa-tabsel { position: absolute; opacity: 0; width: 0; height: 0; pointer-events: none; }
.qa-report .qa-tabbar { display: flex; flex-wrap: wrap; gap: 0 26px; border-bottom: 1px solid var(--line-2); }
.qa-report .qa-tab { font-family: var(--head); font-size: 13.5px; font-weight: 600; letter-spacing: 0.02em; padding: 11px 2px; margin-bottom: -1px; border-bottom: 2px solid transparent; color: var(--muted); cursor: pointer; user-select: none; }
.qa-report .qa-tab:hover { color: var(--ink-soft); }
.qa-report .qa-tab .qa-tab-n { font-family: var(--mono); font-size: 10.5px; color: var(--faint); margin-left: 7px; }
.qa-report .qa-pane { display: none; }
.qa-report .qa-pane > section:first-of-type { margin-top: 36px; }
@media (max-width: 600px) { .qa-report .qa-tabbar { gap: 0 16px; } .qa-report .qa-tab { font-size: 12.5px; } }
/* 动画被禁用时不能让 section 卡在 opacity:0（入场动画是 forwards 的）。 */
@media (prefers-reduced-motion: reduce) { .qa-report section { opacity: 1; transform: none; animation: none; } }
"""

_TAB_SLOTS = 6
_CSS_COMPONENTS += "".join(
    f".qa-report .qa-tabs > .qa-tabsel:nth-of-type({i}):checked ~ .qa-panes > .qa-pane:nth-of-type({i}) {{ display: block; }}\n"
    f".qa-report .qa-tabs > .qa-tabsel:nth-of-type({i}):checked ~ .qa-tabbar > .qa-tab:nth-of-type({i}) "
    "{ color: var(--orange-deep); border-bottom-color: var(--orange); }\n"
    for i in range(1, _TAB_SLOTS + 1)
)


# 走势图的 hover 读数。渐进增强：脚本跑不起来（宿主用 innerHTML 注入片段、或 CSP 禁内联
# 脚本）时，静态坐标轴照常显示，只是少了跟随鼠标的读数。价格由 polyline 的 y 坐标反算，
# 因此不必为 9000 多个点各存一份数值 —— 那会让 artifact 体积翻三倍。
_CHART_HOVER_JS = (
    "<script>(function(){var H=__H__,P=__P__,W=__W__,last=null;"
    'function el(c,k){var e=c.querySelector("."+k);if(!e){e=document.createElement("div");'
    "e.className=k;c.appendChild(e);}return e;}"
    'function hide(c){if(!c||!c._on)return;c._on=false;["dp-cursor","dp-dot","dp-tip"]'
    '.forEach(function(k){var e=c.querySelector("."+k);if(e)e.hidden=true;});}'
    "function data(c){if(c._d)return c._d;"
    'var raw=(c.dataset.v||"").split("|"),v=[+raw[0]];'
    'if(raw[1])raw[1].split(",").forEach(function(d){v.push(v[v.length-1]+(+d));});'
    "var lo=Math.min.apply(null,v),hi=Math.max.apply(null,v),s=(hi-lo)||1;"
    "c._d={v:v,y:v.map(function(p){return H-P-(p-lo)/s*(H-2*P);})};return c._d;}"
    'document.addEventListener("mousemove",function(e){'
    'var t=e.target,c=t&&t.closest?t.closest(".dp-chart"):null;'
    "if(c!==last){hide(last);last=c;}if(!c)return;"
    "var d=data(c);if(d.v.length<2)return;"
    'var svg=c.querySelector(".dp-svg"),r=svg.getBoundingClientRect();if(!r.width)return;'
    "var f=Math.min(1,Math.max(0,(e.clientX-r.left)/r.width));"
    "var i=Math.round(f*(d.v.length-1));"
    "var px=i/(d.v.length-1)*r.width,py=d.y[i]/H*r.height;"
    'var cur=el(c,"dp-cursor"),dot=el(c,"dp-dot"),tip=el(c,"dp-tip");'
    'cur.style.left=px+"px";cur.hidden=false;'
    'dot.style.left=px+"px";dot.style.top=py+"px";dot.hidden=false;'
    'tip.textContent="$"+(d.v[i]/100).toFixed(2);'
    'tip.style.left=Math.min(Math.max(px,34),Math.max(34,r.width-34))+"px";'
    'tip.style.top=py+"px";tip.hidden=false;c._on=true;});'
    'document.addEventListener("mouseleave",function(){hide(last);last=null;});})();</script>'
).replace("__H__", str(_CHART_H)).replace("__P__", str(_CHART_PAD)).replace("__W__", str(_CHART_W))


def _hover_script(report: dict[str, Any]) -> str:
    return _CHART_HOVER_JS if report.get("detail_charts") else ""


def _html_metabar(report: dict[str, Any], lang: str) -> str:
    status = str(report.get("data_status"))
    status_cls = "ok" if status == "ok" else "bad"
    overview = report.get("market_overview") or {}
    sample_count = overview.get("symbols_analyzed", report.get("universe_size", 0))
    na = tr("unavailable", "不可用", lang)
    return f"""<div class="metabar">
    <span class="pill">{tr('Data as of', '数据截止', lang)} <b>{_esc(report.get('as_of_date') or na)}</b></span>
    <span class="pill {status_cls}">{tr('Status', '状态', lang)} <b>{_esc(status)}</b></span>
    <span class="pill">{tr('Generated', '生成', lang)} (UTC) <b>{_esc(str(report.get('generated_at'))[:19])}</b></span>
    <span class="pill">{tr('Sample', '样本', lang)} <b>{_esc(sample_count)}</b></span>
  </div>"""


def _html_masthead(report: dict[str, Any], lang: str) -> str:
    title_main = tr("Daily US Equity Research Brief", "今日美股研究简报", lang)
    return f"""<header>
  <div class="kicker">Daily US Equity Briefing · {tr('US market research', '美股每日研究', lang)}</div>
  <h1 class="title">{title_main}<span class="en">A quantitative reading of today's US market</span></h1>
  {_html_metabar(report, lang)}
</header>
<div class="ribbon">{_esc(report.get('disclaimer', ''))}</div>"""


def render_report_body(report: dict[str, Any]) -> str:
    """报告正文，供别的页面内嵌（不含文档外壳、样式和大标题）。

    带上 metabar 和免责声明 —— 数据截止日和免责声明必须跟着报告内容走，宿主页面自己的
    页眉说明不了这两件事。内嵌时报告自带的标签页用 ``qa`` 组名，宿主必须换一个组名。
    """
    lang = normalize_language(report.get("language", "en"))
    return (
        f'<div class="metawrap">{_html_metabar(report, lang)}</div>'
        f'<div class="ribbon">{_esc(report.get("disclaimer", ""))}</div>'
        f"{_html_sections(report, lang)}{_hover_script(report)}"
    )


def _html_footer(report: dict[str, Any], lang: str) -> str:
    return (
        f"<footer><span>QUANT.AI · RESEARCH ONLY — {tr('not investment advice', '不构成投资建议', lang)}</span>"
        f"<span>generated {_esc(str(report.get('generated_at'))[:19])} UTC</span></footer>"
    )


def _html_sections(report: dict[str, Any], lang: str) -> str:
    """把 section 分组进标签页。

    组内顺序与全局章节编号沿用原来的线性排列（持仓永远排最前），所以编号跨标签页仍然连续。
    空 section 不消耗编号，整组为空时该标签页直接不出现。
    """
    n = _SectionCounter()
    groups = [
        # 用户最关心自己的钱：持仓组永远排最前，也是默认打开的那页。
        (tr("Holdings", "持仓", lang), [
            _html_holdings(report, n, lang),
            _html_holding_profiles(report, n, lang),  # 紧跟持仓：每只票的判断材料
        ]),
        (tr("Market", "大盘", lang), [
            _html_overview(report, n, lang),
            _html_funds(report, n, lang),
        ]),
        (tr("Ideas", "机会", lang), [
            _html_reco(report, n, lang),
            _html_table(report, "buy_candidates", tr("Potential picks", "潜力股", lang), n, lang),
            _html_table(report, "high_risk", tr("High risk", "高风险", lang), n, lang),
        ]),
        (tr("News", "资讯", lang), [
            _html_news(report, n, lang),
            _html_company(report, n, lang),
            _html_social(report, n, lang),
        ]),
        (tr("Notes", "说明", lang), [
            _html_notes(report, n, lang),
        ]),
    ]
    filled = [(title, blocks) for title, blocks in ((t, [b for b in bs if b]) for t, bs in groups) if blocks]
    if not filled:
        return ""
    if len(filled) == 1:
        return "\n".join(filled[0][1])  # 只剩一组时不值得为它画一条标签栏
    return build_tabs(filled)


def report_css(*, web_fonts: bool = True, page: bool = True) -> str:
    """整页文档用的完整 CSS（调色板 + 字体 + 组件）。

    控制台复用它，好让运维页和报告长成同一套视觉，而不是各写一份。
    """
    fonts = _CSS_FONTS_WEB if web_fonts else _CSS_FONTS_SYSTEM
    return f":root {{ {_CSS_PALETTE_LIGHT}{fonts} }}\n" + (_CSS_PAGE if page else "") + _CSS_COMPONENTS


def build_tabs(groups: list[tuple[str, list[str]]], group: str = "qa") -> str:
    """radio + label 纯 CSS 标签页（无 JS，严格 CSP 下也能切换）。

    与 `.dp` 详情面板同一套路：显示靠 ``:checked ~ nth-of-type`` 配对，是相对各自
    ``.qa-tabs`` 的，所以嵌套一层也能各切各的。但 radio 的 ``name`` 是全局互斥的 ——
    宿主页面把带标签页的报告嵌进自己的标签页时，两层必须用不同的 ``group``，否则选中
    一个会把另一层的选中态清掉。分组数不能超过 _TAB_SLOTS，否则多出来的页没有对应的
    :checked 规则、点了打不开。
    """
    if len(groups) > _TAB_SLOTS:
        # 静默失效很难查（点了没反应也不报错），宁可在渲染时就炸。
        raise ValueError(f"标签页最多 {_TAB_SLOTS} 组，收到 {len(groups)} 组；请同步调整 _TAB_SLOTS")
    inputs: list[str] = []
    tabs: list[str] = []
    panes: list[str] = []
    for idx, (title, blocks) in enumerate(groups, start=1):
        checked = " checked" if idx == 1 else ""
        input_id = f"{group}-tab-{idx}"
        inputs.append(f'<input class="qa-tabsel" type="radio" name="{group}-tabsel" id="{input_id}"{checked}>')
        count = f'<span class="qa-tab-n">{len(blocks)}</span>' if len(blocks) > 1 else ""
        tabs.append(f'<label class="qa-tab" for="{input_id}">{_esc(title)}{count}</label>')
        panes.append(f'<div class="qa-pane">{"".join(blocks)}</div>')
    return (
        f'<div class="qa-tabs">{"".join(inputs)}'
        f'<nav class="qa-tabbar">{"".join(tabs)}</nav>'
        f'<div class="qa-panes">{"".join(panes)}</div></div>'
    )


def render_html(report: dict[str, Any]) -> str:
    """Full standalone HTML document (written to disk; web fonts allowed)."""
    lang = normalize_language(report.get("language", "en"))
    title_main = tr("Daily US Equity Research Brief", "今日美股研究简报", lang)
    return f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_main}</title>
{_FONT_LINK}
<style>:root {{ {_CSS_PALETTE_LIGHT}{_CSS_FONTS_WEB} }}
{_CSS_PAGE}{_CSS_COMPONENTS}</style>
</head>
<body>
<div class="wrap qa-report">
{_html_masthead(report, lang)}
{_html_sections(report, lang)}
{_html_footer(report, lang)}
</div>
{_hover_script(report)}
</body>
</html>
"""


def render_artifact_html(report: dict[str, Any]) -> str:
    """Self-contained HTML fragment for AI-client artifacts.

    无 doctype/html/head/body 包装、零外部资源（严格 CSP 下可渲染）；样式全部内联并
    作用域在 .qa-report 下；明暗双主题：跟随 prefers-color-scheme，宿主页面设置
    :root[data-theme="dark"|"light"] 时以宿主为准。
    """
    lang = normalize_language(report.get("language", "en"))
    css = (
        f".qa-report{{{_CSS_PALETTE_LIGHT}{_CSS_FONTS_SYSTEM}"
        "margin:0 auto;max-width:1120px;padding:8px 26px 64px;background:var(--paper);}"
        f"@media (prefers-color-scheme: dark){{.qa-report{{{_CSS_PALETTE_DARK}}}}}"
        f':root[data-theme="dark"] .qa-report{{{_CSS_PALETTE_DARK}}}'
        f':root[data-theme="light"] .qa-report{{{_CSS_PALETTE_LIGHT}}}'
        f"{_CSS_COMPONENTS}"
    )
    return (
        f'<div class="qa-report" lang="{"zh-CN" if lang == "zh" else "en"}">'
        f"<style>{css}</style>"
        f"{_html_masthead(report, lang)}"
        f"{_html_sections(report, lang)}"
        f"{_html_footer(report, lang)}"
        f"{_hover_script(report)}"
        "</div>"
    )


class _SectionCounter:
    def __init__(self) -> None:
        self.value = 0
        self._uid = 0

    def next(self) -> str:
        self.value += 1
        return f"{self.value:02d}"

    def uid(self) -> str:
        """文档内唯一 id 片段：同一标的可出现在多个栏目，radio 分组/label 配对不能撞名。"""
        self._uid += 1
        return str(self._uid)


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _ticker_html(symbol: str, name: str | None) -> str:
    """Ticker code, plus its Chinese display name in a muted span when known."""
    out = _esc(symbol)
    if name:
        out += f' <span class="name-zh">{_esc(name)}</span>'
    return out


def _sec_head(num: str, title: str, hint: str = "") -> str:
    hint_html = f'<span class="hint">{_esc(hint)}</span>' if hint else ""
    return f'<div class="sec-head"><span class="sec-num">{num}</span><h2>{_esc(title)}</h2>{hint_html}</div>'


def _delta(value: Any, suffix: str = "%") -> str:
    if value is None:
        return '<span class="muted">—</span>'
    try:
        num = float(value)
    except (TypeError, ValueError):
        return f'<span class="flat">{_esc(value)}</span>'
    cls = "pos" if num > 0 else "neg" if num < 0 else "flat"
    return f'<span class="{cls}">{num:+.2f}{suffix}</span>'


def _money_html(value: Any, signed: bool = False, colored: bool = False) -> str:
    if value is None:
        return '<span class="muted">—</span>'
    text = f"{value:+,.2f}" if signed else f"${value:,.2f}"
    if not colored:
        return _esc(text)
    cls = "pos" if value > 0 else "neg" if value < 0 else "flat"
    return f'<span class="{cls}">{_esc(text)}</span>'


def _sparkline_svg(values: list[float], width: int = 72, height: int = 24) -> str:
    """Inline SVG sparkline (no chart library — artifact HTML must stay self-contained)."""
    if len(values) < 2:
        return '<span class="muted">—</span>'
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    step = width / (len(values) - 1)
    points = " ".join(f"{i * step:.1f},{height - (v - lo) / span * height:.1f}" for i, v in enumerate(values))
    color = "var(--green)" if values[-1] >= values[0] else "var(--down)"
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def _detail_chart_svg(points: list[float], width: int = _CHART_W, height: int = _CHART_H) -> str:
    """Inline SVG close-price curve with a soft area fill (self-contained, no chart library)."""
    lo, hi = min(points), max(points)
    span = hi - lo or 1.0
    step = width / (len(points) - 1)
    pad = _CHART_PAD
    coords = [(i * step, height - pad - (v - lo) / span * (height - 2 * pad)) for i, v in enumerate(points)]
    # 坐标取整：点串在文档里出现两次（描边 + 面积填充），是 artifact HTML 的体积大头。
    # viewBox 仍是 640×150 且约按 1:1 显示，取整误差 ≤0.5px、线宽 1.8px —— 视觉无损。
    # （hover 读数不从这里反算 —— 150px 的分辨率在大价差上会差出几角钱，见 _detail_chart_block。）
    pts = " ".join(f"{round(x)},{round(y)}" for x, y in coords)
    color = "var(--green)" if points[-1] >= points[0] else "var(--down)"
    area = f"0,{height} {pts} {width},{height}"
    grid = "".join(
        f'<line class="dp-grid" x1="0" y1="{y:g}" x2="{width}" y2="{y:g}"/>'
        for y in (pad, height / 2, height - pad)
    )
    return (
        f'<svg class="dp-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">'
        f"{grid}"
        f'<polygon points="{area}" fill="{color}" opacity="0.08"/>'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def _md_day(value: Any) -> str:
    """``YYYY-MM-DD`` -> ``MM-DD``，横轴刻度用（年份在 caption 的完整日期里已经有了）。"""
    text = str(value or "")
    return text[5:] if len(text) == 10 else text


def _detail_chart_block(window: dict[str, Any]) -> str:
    """走势图 + 坐标轴 + hover 读数的数据。

    坐标轴文字走 HTML 层而不是 SVG ``<text>``：SVG 用 ``preserveAspectRatio="none"`` 横向
    拉伸填满容器，窄屏下 SVG 文字会被压扁，HTML 层不受影响。

    ``data-v`` 是这条曲线的收盘价（分为单位的整数，逐点差分）。曾经想省掉它、让脚本从
    polyline 的 y 坐标反算价格，但 150px 高的图在大价差上分辨率不够 —— 千元股能差出三毛
    多。差分编码后每点两三个字符，比存原值省一半。游标/圆点/气泡由脚本按需创建，不预先
    为 140 张图各写三个空 div。
    """
    points = window.get("points") or []
    if len(points) < 2:
        return ""
    lo, hi = min(points), max(points)
    cents = [round(v * 100) for v in points]
    deltas = ",".join(str(b - a) for a, b in zip(cents[:-1], cents[1:], strict=True))
    y_axis = "".join(f"<span>{_fmt_money(p)}</span>" for p in (hi, (hi + lo) / 2, lo))
    x_axis = "".join(f"<span>{_esc(_md_day(window.get(k)))}</span>" for k in ("start", "mid", "end"))
    return (
        f'<div class="dp-chart" data-v="{cents[0]}|{deltas}">'
        f"{_detail_chart_svg(points)}"
        f'<div class="dp-ay">{y_axis}</div></div>'
        f'<div class="dp-ax">{x_axis}</div>'
    )


def _detail_panel_html(symbol: str, charts: dict[str, Any], uid: str, lang: str) -> str:
    """Timeframe-tabbed close-price panel（1W-5Y，radio+label 纯 CSS 切换，无 JS）。

    该标的没有序列（价格数据缺失）时返回空串，调用方降级为不可展开。
    """
    windows = charts.get(symbol)
    if not windows:
        return ""
    default = _DETAIL_DEFAULT_TF if _DETAIL_DEFAULT_TF in windows else next(iter(windows))
    inputs: list[str] = []
    tabs: list[str] = []
    panes: list[str] = []
    for idx, (label, w) in enumerate(windows.items(), start=1):
        input_id = f"dp-{uid}-{idx}"
        checked = " checked" if label == default else ""
        inputs.append(f'<input class="dp-radio" type="radio" name="dp-{uid}" id="{input_id}"{checked}>')
        tabs.append(
            f'<label class="dp-tab" for="{input_id}">'
            f"{_esc(tr(*_TF_LABELS.get(label, (label, label)), lang))}</label>"
        )
        caption = (
            f'<span>{_esc(w.get("start", ""))} → {_esc(w.get("end", ""))}</span>'
            f'<span>{_delta(w.get("chg_pct"))}</span>'
            f'<span>{_esc(tr("range", "区间", lang))} ${w["low"]:,.2f}–${w["high"]:,.2f}</span>'
        )
        panes.append(f'<div class="dp-pane">{_detail_chart_block(w)}<div class="dp-caption">{caption}</div></div>')
    return (
        f'<div class="dp">{"".join(inputs)}'
        f'<div class="dp-tabs">{"".join(tabs)}</div>'
        f'<div class="dp-panes">{"".join(panes)}</div></div>'
    )


def _toggle_sym_html(symbol: str, name: str | None, panel: str) -> str:
    """表格里的代码单元：有详情面板时包一层 label+checkbox 变成展开开关。"""
    ticker = _ticker_html(symbol, name)
    if not panel:
        return ticker
    return f'<label class="sym-toggle"><input type="checkbox" class="row-toggle">{ticker}</label>'


def _detail_details_html(panel: str, lang: str) -> str:
    """卡片/瓦片里的展开块：<details> 折叠，摘要为“价格走势”。"""
    if not panel:
        return ""
    summary = _esc(tr("Price chart", "价格走势", lang))
    return f'<details class="dp-details"><summary>{summary}</summary>{panel}</details>'


def _html_holdings(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    holdings = report.get("holdings") or {}
    positions = holdings.get("positions") or []
    if not positions:
        return ""
    totals = holdings.get("totals") or {}
    tiles: list[tuple[str, str]] = [
        (tr("Market value", "总市值", lang), _money_html(totals.get("market_value"))),
        (tr("Unrealized P&L", "未实现盈亏", lang), _money_html(totals.get("unrealized_pnl"), signed=True, colored=True)),
        (tr("P&L %", "盈亏幅度", lang), _delta(totals.get("unrealized_pnl_pct"))),
        (tr("Day P&L", "今日盈亏", lang), _money_html(totals.get("day_pnl"), signed=True, colored=True)),
        (tr("Positions", "持仓数", lang), str(totals.get("positions", len(positions)))),
    ]
    cells = "".join(
        f'<div class="tile"><div class="t-label">{_esc(label)}</div><div class="t-value">{value}</div></div>'
        for label, value in tiles
    )
    ths = tr(
        "Symbol|Trend|Shares|Price|Day|Mkt value|Cost/share|P&L|P&L %",
        "代码|走势|股数|现价|当日|市值|成本价|盈亏|盈亏 %",
        lang,
    ).split("|")
    head = "<tr>" + "".join(f"<th>{_esc(t)}</th>" for t in ths) + "</tr>"
    charts = report.get("detail_charts") or {}
    row_parts: list[str] = []
    for p in positions:
        panel = _detail_panel_html(p["symbol"], charts, n.uid(), lang)
        row_parts.append(
            f'<tr><td class="sym">{_toggle_sym_html(p["symbol"], p.get("name_zh"), panel)}</td>'
            f'<td class="spark-cell">{_sparkline_svg(p.get("spark") or [])}</td>'
            f'<td class="num">{_esc(_fmt_qty(p["shares"]))}</td>'
            f'<td class="num">{_money_html(p.get("price"))}</td>'
            f'<td class="num">{_delta(p.get("day_change_pct"))}</td>'
            f'<td class="num">{_money_html(p.get("market_value"))}</td>'
            f'<td class="num muted">{_money_html(p.get("cost_basis"))}</td>'
            f'<td class="num">{_money_html(p.get("unrealized_pnl"), signed=True, colored=True)}</td>'
            f'<td class="num">{_delta(p.get("unrealized_pnl_pct"))}</td></tr>'
        )
        if panel:
            row_parts.append(f'<tr class="detail-row"><td colspan="{len(ths)}">{panel}</td></tr>')
    rows = "".join(row_parts)
    section_head = _sec_head(
        n.next(), tr("My holdings", "我的持仓", lang), _quotes_source_label(holdings.get("quotes_source"), lang)
    )
    return (
        f"<section>{section_head}"
        f'<div class="tiles" style="margin-bottom:16px">{cells}</div>'
        f'<div class="panel"><table class="holdings"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
        "</section>"
    )


def _html_overview(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    overview = report.get("market_overview") or {}
    if not overview:
        return ""
    tiles: list[tuple[str, str]] = []
    if overview.get("benchmark"):
        tiles.append((tr(f"Benchmark {overview['benchmark']} · 1M", f"基准 {overview['benchmark']} · 近1月", lang), _delta(overview.get("benchmark_ret_21d_pct"))))
        tiles.append((f"{overview['benchmark']} · {tr('5D', '近5日', lang)}", _delta(overview.get("benchmark_ret_5d_pct"))))
    tiles.append((tr("5D advancing", "近5日上涨占比", lang), f"{overview.get('breadth_5d_advancing_pct', '—')}%"))
    tiles.append((tr("Sample avg · 1M", "样本均值 · 近1月", lang), _delta(overview.get("avg_ret_21d_pct"))))
    tiles.append((tr("Sample avg · 5D", "样本均值 · 近5日", lang), _delta(overview.get("avg_ret_5d_pct"))))
    tiles.append((tr("Names analyzed", "分析标的数", lang), str(overview.get("symbols_analyzed", "—"))))
    cells = "".join(
        f'<div class="tile"><div class="t-label">{_esc(label)}</div><div class="t-value">{value}</div></div>'
        for label, value in tiles
    )
    return f'<section>{_sec_head(n.next(), tr("Market overview", "市场概览", lang))}<div class="tiles">{cells}</div></section>'


def _hp_news_html(profile: dict[str, Any], lang: str) -> str:
    """该持仓的近期资讯：有手写归纳就先给结论句，下面照旧列出处标题（结论可回溯）。"""
    items = profile.get("news") or []
    digest = profile.get("news_digest")
    if not items and not digest:
        return f'<div class="hp-news hp-none">{_esc(tr("no recent headlines", "近期无相关资讯", lang))}</div>'
    label = f'<span class="hp-k">{_esc(tr("Recent news", "近期资讯", lang))}</span>'
    digest_html = ""
    if digest:
        stamp = ""
        if profile.get("news_digest_stale") and profile.get("news_digest_as_of"):
            as_of = profile["news_digest_as_of"]
            stamp = (
                f'<span class="hp-stale">'
                f'{_esc(tr(f"digest as of {as_of}", f"归纳截至 {as_of}", lang))}</span>'
            )
        digest_html = f'<p class="hp-digest">{_esc(digest)}{stamp}</p>'
    if not items:
        return f'<div class="hp-news">{label}{digest_html}</div>'
    lis = "".join(
        f'<li><a href="{_esc(item.get("link", ""))}" target="_blank" rel="noopener">'
        f'{_esc(item.get("title", ""))}</a>'
        f'<span class="pub">{_esc(item.get("publisher", ""))}</span></li>'
        for item in items
    )
    return f'<div class="hp-news">{label}{digest_html}<ul>{lis}</ul></div>'


def _html_holding_profiles(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    """Per-holding factual card: trend/return/risk stats, analyst range, quant standing.

    刻意不给方向性结论 —— 这一段的作用是把判断材料摆齐，买卖决策由读者自己做。
    """
    profiles = report.get("holding_profiles") or []
    if not profiles:
        return ""
    charts = report.get("detail_charts") or {}
    cards = []
    for p in profiles:
        trend_cls = "pos" if p.get("trend_up") else "neg"
        trend_text = tr("Trend up", "趋势向上", lang) if p.get("trend_up") else tr("Trend down", "趋势向下", lang)
        weight = f"{p['weight_pct']:.1f}%" if p.get("weight_pct") is not None else "—"
        stats = [
            (tr("5D", "近5日", lang), _delta(p.get("ret_5d_pct"))),
            (tr("1M", "近1月", lang), _delta(p.get("ret_21d_pct"))),
            (tr("3M", "近3月", lang), _delta(p.get("ret_63d_pct"))),
            (tr("Ann. vol", "年化波动", lang), f'<span class="muted">{p.get("vol_annual_pct")}%</span>'),
            (tr("Max DD 1y", "近一年回撤", lang), f'<span class="neg">{p.get("max_drawdown_252_pct")}%</span>'),
            (tr("From 52w high", "距52周高点", lang), f'<span class="muted">{p.get("dist_from_high_pct")}%</span>'),
        ]
        rel = p.get("vs_benchmark_21d_pct")
        if rel is not None:
            label = tr("vs benchmark 1M", "近1月相对基准", lang)
            stats.append((label, f'<span class="{"pos" if rel >= 0 else "neg"}">{rel:+.2f}pp</span>'))
        stat_html = "".join(
            f'<div class="hp-stat"><span class="hp-k">{_esc(k)}</span><span class="hp-v">{v}</span></div>'
            for k, v in stats
        )
        standing = p.get("quant_standing") or []
        stand_html = (
            "".join(
                f'<span class="pick-badge">{_esc(s["label"])} #{s["rank"]}</span>'
                for s in standing
            )
            if standing
            else f'<span class="hp-none">{_esc(tr("not in any quant list", "未进任何量化榜单", lang))}</span>'
        )
        panel = _detail_panel_html(p["symbol"], charts, n.uid(), lang)
        cards.append(
            '<div class="hp-card">'
            f'<div class="hp-head">{_ticker_html(p["symbol"], p.get("name_zh"))}'
            f'<span class="hp-weight">{_esc(tr("weight", "仓位", lang))} {weight}</span>'
            f'<span class="pick-badge {trend_cls}">{_esc(trend_text)}</span></div>'
            f'<div class="hp-stats">{stat_html}</div>'
            f"{_pick_range_html(p, lang)}"
            f'<div class="hp-standing">{stand_html}</div>'
            f"{_hp_news_html(p, lang)}"
            f"{_detail_details_html(panel, lang)}"
            "</div>"
        )
    hint = tr(
        "facts only · no buy/sell call",
        "只摆事实 · 不给买卖方向",
        lang,
    )
    head = _sec_head(n.next(), tr("Holdings at a glance", "持仓标的画像", lang), hint)
    return f'<section>{head}<div class="hp-grid">{"".join(cards)}</div></section>'


def _pick_range_html(s: dict[str, Any], lang: str) -> str:
    """Deviation-from-target bar: the track center is the analyst target price (0%); the fill
    grows right/red as price exceeds target, left/green as price sits below it — scaled by how
    far the analyst low/high sit from the target, so the two edges are "at low" / "at high".
    No analyst coverage -> a neutral placeholder instead of a bar (no meaningful number to show).
    """
    valuation = s.get("valuation")
    price = s.get("last_price")
    if not valuation or price is None:
        return f'<div class="range-empty">{_esc(tr("No analyst coverage", "暂无机构估值覆盖", lang))}</div>'
    low, target, high = valuation["low"], valuation["target"], valuation["high"]
    deviation_pct = (price - target) / target * 100 if target else 0.0
    if price <= target:
        proportion = max(0.0, min(1.0, (target - price) / max(target - low, 1e-9)))
        fill_style = f"left:{50 - proportion * 50:.1f}%;width:{proportion * 50:.1f}%"
        fill_gradient = "linear-gradient(90deg, var(--green-deep), var(--green))"
    else:
        proportion = max(0.0, min(1.0, (price - target) / max(high - target, 1e-9)))
        fill_style = f"left:50%;width:{proportion * 50:.1f}%"
        fill_gradient = "linear-gradient(90deg, var(--down), var(--down-deep))"
    analyst_count = valuation.get("analyst_count")
    coverage = f" · {analyst_count}{_esc(tr(' analysts', '家覆盖', lang))}" if analyst_count else ""
    return (
        '<div class="range"><div class="range-track">'
        '<span class="range-zero"></span>'
        f'<span class="range-fill" style="{fill_style};background:{fill_gradient}"></span></div>'
        '<div class="range-caption">'
        f'<span>{_esc(tr("Low", "低", lang))} ${low:,.0f}</span>'
        f'<span class="tgt">{_esc(tr("Target", "目标", lang))} ${target:,.0f} ({deviation_pct:+.1f}%){coverage}</span>'
        f'<span>{_esc(tr("High", "高", lang))} ${high:,.0f}</span>'
        "</div></div>"
    )


def _holding_badge_html(s: dict[str, Any], lang: str) -> str:
    holding = s.get("holding")
    if not holding:
        return ""
    shares = _esc(_fmt_qty(holding.get("shares")))
    pnl_pct = holding.get("unrealized_pnl_pct")
    if pnl_pct is None:
        pnl_html = '<span class="muted">—</span>'
    else:
        cls = "pos" if pnl_pct > 0 else "neg" if pnl_pct < 0 else "flat"
        pnl_html = f'<span class="{cls}">{pnl_pct:+.1f}%</span>'
    label = _esc(tr(f"held {shares} sh", f"持仓 {shares} 股", lang))
    return f'<span class="pick-badge holding">{label} · {pnl_html}</span>'


def _html_reco(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    quant = report.get("quant_candidates") or {}
    if not quant:
        return ""
    charts = report.get("detail_charts") or {}
    columns = []
    for data in quant.values():
        picks = []
        for i, s in enumerate(data.get("symbols", []), start=1):
            price = f"${s['last_price']}" if s.get("last_price") is not None else "—"
            risk = str(s.get("risk_level", "medium"))
            confidence = str(s.get("confidence", "low"))
            risk_label = tr(f"risk {risk}", f"风险 {_level_zh(risk)}", lang)
            confidence_label = tr(f"confidence {confidence}", f"置信度 {_level_zh(confidence)}", lang)
            ticker_html = _ticker_html(s["symbol"], s.get("name_zh"))
            day_value = s.get("day_change_value")
            why_cls = "pos" if (day_value or 0) > 0 else "neg" if (day_value or 0) < 0 else "flat"
            panel = _detail_panel_html(s["symbol"], charts, n.uid(), lang)
            picks.append(
                f'<div class="pick{" is-holding" if s.get("holding") else ""}">'
                f'<div class="pick-row"><span class="rank">{i:02d}</span>'
                f'<span class="ticker">{ticker_html}</span><span class="price">{_esc(price)}</span></div>'
                f'<div class="pick-badges">{_holding_badge_html(s, lang)}'
                f'<span class="pick-badge {risk}">{_esc(risk_label)}</span>'
                f'<span class="pick-badge">{_esc(confidence_label)}</span></div>'
                f"{_pick_range_html(s, lang)}"
                f'<div class="why {why_cls}">{_esc(s.get("reason", ""))}</div>'
                f"{_detail_details_html(panel, lang)}</div>"
            )
        if not picks:
            continue
        columns.append(
            f'<div class="reco"><div class="reco-top"><div class="reco-name">{_esc(data.get("label"))}</div>'
            f'<div class="reco-meta"><span class="chip">{_esc(data.get("horizon"))}</span>'
            f'<span class="reco-tag">{_esc(data.get("tag", ""))}</span></div></div>{"".join(picks)}</div>'
        )
    if not columns:
        return ""
    head = _sec_head(n.next(), tr("Research picks by holding horizon", "按持有周期的研究推荐", lang), tr("long / medium / short", "长线 / 中线 / 短线", lang))
    return f'<section>{head}<div class="reco-grid">{"".join(columns)}</div></section>'


def _html_funds(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    funds = report.get("fund_trackers") or []
    if not funds:
        return ""
    charts = report.get("detail_charts") or {}
    cards = []
    for f in funds:
        day_pct = f.get("day_change_pct")
        day_value = f.get("day_change_value")
        if day_pct is None or day_value is None:
            day_html = '<span class="muted">—</span>'
        else:
            cls = "pos" if day_value > 0 else "neg" if day_value < 0 else "flat"
            day_html = f'<span class="{cls}">{day_value:+.2f} ({day_pct:+.2f}%)</span>'
        panel = _detail_panel_html(f["symbol"], charts, n.uid(), lang)
        cards.append(
            '<div class="tile fund">'
            f'<div class="t-label">{_esc(f["symbol"])} · {_esc(f["label"])}</div>'
            f'<div class="t-value">${f["last_price"]:,.2f}</div>'
            f'<div class="t-sub">{day_html} · 5D {_delta(f.get("ret_5d_pct"))} · 1M {_delta(f.get("ret_21d_pct"))}</div>'
            f"{_detail_details_html(panel, lang)}"
            "</div>"
        )
    head = _sec_head(n.next(), tr("Fund & index tracker", "基金/指数追踪", lang), tr("Nasdaq / S&P 500 / semis / AI", "纳指 / 标普500 / 半导体 / AI", lang))
    return f'<section>{head}<div class="tiles">{"".join(cards)}</div></section>'


def _html_table(report: dict[str, Any], key: str, title: str, n: _SectionCounter, lang: str = "en") -> str:
    rows_data = report.get(key) or []
    if not rows_data:
        return ""
    charts = report.get("detail_charts") or {}
    if key == "buy_candidates":
        ths = tr("Symbol|Last|1M|5D|Ann. vol|Reason", "代码|最新价|近1月|近5日|年化波动|依据", lang).split("|")
        cls, hint = "buy", tr("uptrend · contained vol", "趋势向上 · 波动可控", lang)
    else:
        ths = tr("Symbol|Last|Dist. from high|1M|5D|Reason", "代码|最新价|距52周高点|近1月|近5日|依据", lang).split("|")
        cls, hint = "risk", tr("near highs · overextended · sharp drop", "近高位 · 涨幅超涨 · 急跌", lang)
    head = "<tr>" + "".join(f"<th>{_esc(t)}</th>" for t in ths) + "</tr>"
    body_parts: list[str] = []
    for c in rows_data:
        panel = _detail_panel_html(c["symbol"], charts, n.uid(), lang)
        sym_cell = f'<td class="sym">{_toggle_sym_html(c["symbol"], c.get("name_zh"), panel)}</td>'
        if key == "buy_candidates":
            body_parts.append(
                f'<tr>{sym_cell}<td class="num">{c["last_price"]}</td>'
                f'<td class="num">{_delta(c.get("ret_21d_pct"))}</td><td class="num">{_delta(c.get("ret_5d_pct"))}</td>'
                f'<td class="num muted">{c.get("vol_annual_pct")}%</td><td class="why-cell">{_esc(c.get("reason", ""))}</td></tr>'
            )
        else:
            body_parts.append(
                f'<tr>{sym_cell}<td class="num">{c["last_price"]}</td>'
                f'<td class="num">{c.get("dist_from_high_pct")}%</td><td class="num">{_delta(c.get("ret_21d_pct"))}</td>'
                f'<td class="num">{_delta(c.get("ret_5d_pct"))}</td><td class="why-cell">{_esc(c.get("reason", ""))}</td></tr>'
            )
        if panel:
            body_parts.append(f'<tr class="detail-row"><td colspan="{len(ths)}">{panel}</td></tr>')
    body = "".join(body_parts)
    return (
        f'<section>{_sec_head(n.next(), title, hint)}'
        f'<div class="panel"><table class="{cls}"><thead>{head}</thead><tbody>{body}</tbody></table></div></section>'
    )


def _html_news(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    news = report.get("news") or []
    head = _sec_head(n.next(), tr("Latest financial-media headlines", "最新财经媒体头条", lang), tr(f"{len(news)} items", f"{len(news)} 条", lang))
    if not news:
        return f'<section>{head}<div class="empty">{tr("No media news fetched this run (possibly a network issue — see Notes).", "本次未抓取到媒体新闻（可能为网络问题，详见“说明”）。", lang)}</div></section>'
    items = []
    for item in news[:24]:
        title = _esc(item.get("title", ""))
        link = _esc(item.get("link", ""))
        anchor = f'<a href="{link}" target="_blank" rel="noopener">{title}</a>' if link else f'<span class="h">{title}</span>'
        published = _esc(item.get("published", ""))
        items.append(
            f'<div class="news-item"><span class="src">{_esc(item.get("source", ""))}</span>{anchor}'
            f'<time>{published}</time></div>'
        )
    return f'<section>{head}<div class="news-list">{"".join(items)}</div></section>'


def _html_company(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    company = report.get("company_news") or {}
    if not company:
        return ""
    cards = []
    for symbol, items in company.items():
        lis = "".join(
            f'<li><a href="{_esc(item.get("link", ""))}" target="_blank" rel="noopener">{_esc(item.get("title", ""))}</a>'
            f' <span class="pub">{_esc(item.get("publisher", ""))}</span></li>'
            for item in items
        )
        cards.append(f'<div class="co"><h3>{_ticker_html(symbol, name_zh(symbol))}</h3><ul>{lis}</ul></div>')
    return f'<section>{_sec_head(n.next(), tr("Per-company news", "重点个股资讯", lang))}<div class="co-grid">{"".join(cards)}</div></section>'


def _html_social(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    if not (report.get("social_enabled") and report.get("social")):
        return ""
    items = "".join(
        f'<div class="news-item"><span class="src">{_esc(item.get("source", ""))}</span>'
        f'<a href="{_esc(item.get("link", ""))}" target="_blank" rel="noopener">{_esc(item.get("title", ""))}</a></div>'
        for item in report["social"][:15]
    )
    return f'<section>{_sec_head(n.next(), tr("Social commentary", "社交平台观点", lang), tr("experimental", "实验", lang))}<div class="news-list">{items}</div></section>'


def _html_notes(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    warnings = report.get("warnings") or []
    if not warnings:
        return ""
    items = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
    return f'<section>{_sec_head(n.next(), tr("Notes", "说明", lang))}<ul class="notes">{items}</ul></section>'
