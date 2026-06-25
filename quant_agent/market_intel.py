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

import html
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pandas as pd

from quant_agent.config import AppConfig
from quant_agent.data import load_prices
from quant_agent.features import build_signals
from quant_agent.i18n import normalize_language, tr
from quant_agent.llm import generate_market_narrative
from quant_agent.recommendations import RECOMMENDATION_PROFILES


def _disclaimer(lang: str) -> str:
    return tr(
        "This report is for quantitative research and learning only — not investment advice, "
        "and not authorization to trade. The 'worth watching' and 'high risk' lists are research "
        "candidates from public news and historical-price statistics; any real trade needs "
        "independent data validation, compliance review and risk control.",
        "本报告仅用于量化研究与学习，不构成投资建议，也不是实盘交易授权。"
        "所谓“适合关注”和“高风险”均为基于公开新闻与历史价格统计的研究候选，"
        "任何真实交易都需要独立的数据校验、合规审查和风险控制。",
        lang,
    )


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Display metadata for the holding-horizon recommendation cards (en/zh).
PROFILE_DISPLAY: dict[str, dict[str, Any]] = {
    "long_term": {"en": "Long-term", "zh": "长线", "horizon_en": "6-12 months", "horizon_zh": "6-12 个月", "tag_en": "trend / low-vol", "tag_zh": "趋势 / 低波动", "order": 1},
    "swing": {"en": "Swing", "zh": "中线 · 波段", "horizon_en": "1-3 months", "horizon_zh": "1-3 个月", "tag_en": "trend / reversal", "tag_zh": "趋势 / 反转", "order": 2},
    "short_term": {"en": "Short-term", "zh": "短线", "horizon_en": "1-4 weeks", "horizon_zh": "1-4 周", "tag_en": "reversal / short trend", "tag_zh": "反转 / 短趋势", "order": 3},
    "defensive": {"en": "Defensive", "zh": "防守", "horizon_en": "3-12 months", "horizon_zh": "3-12 个月", "tag_en": "low-vol first", "tag_zh": "低波动优先", "order": 4},
    "aggressive": {"en": "Aggressive", "zh": "激进", "horizon_en": "1-6 months", "horizon_zh": "1-6 个月", "tag_en": "high momentum / beta", "tag_zh": "高动量 / 高弹性", "order": 5},
}

_Z_LABELS: dict[str, tuple[str, str]] = {
    "momentum_12_1_z": ("12-1 momentum", "12-1动量"),
    "trend_20_50_z": ("20/50 trend", "20/50趋势"),
    "reversal_1m_z": ("1M reversal", "1月反转"),
    "low_volatility_z": ("low vol", "低波动"),
    "ml_rank_z": ("ML rank", "ML排名"),
}


def _z_label(column: str, lang: str) -> str:
    pair = _Z_LABELS.get(column)
    return tr(*pair, lang) if pair else column


def build_market_report(config: AppConfig) -> dict[str, Any]:
    """Build the full daily market intelligence report payload."""
    mi = config.market_intel
    lang = normalize_language(config.language)
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "language": lang,
        "as_of_date": None,
        "data_status": "unavailable",
        "universe_size": len(config.data.universe),
        "market_overview": {},
        "buy_candidates": [],
        "high_risk": [],
        "quant_candidates": {},
        "news": [],
        "company_news": {},
        "social": [],
        "social_enabled": mi.social_enabled,
        "llm_narrative": None,
        "llm_metadata": {"status": "skipped"},
        "warnings": [],
        "sources": {"news_feeds": mi.news_feeds, "social_feeds": mi.social_feeds},
        "disclaimer": _disclaimer(lang),
    }

    prices: pd.DataFrame | None = None
    try:
        prices = load_prices(config.data)
    except Exception as exc:  # pragma: no cover - network/data dependent
        report["warnings"].append(f"price_data_unavailable: {exc}")

    analysis_symbols: list[str] = []
    if prices is not None and not prices.empty:
        report["data_status"] = "ok"
        analysis = _price_analysis(prices, config.strategy.benchmark, lang)
        report["as_of_date"] = analysis["as_of_date"]
        report["market_overview"] = analysis["overview"]
        report["buy_candidates"] = analysis["buy_candidates"]
        report["high_risk"] = analysis["high_risk"]
        analysis_symbols = analysis["focus_symbols"]
        report["quant_candidates"] = _quant_candidates(prices, config, lang)

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

    # Optional LLM synthesis (offline-safe fallback inside the llm helper).
    if mi.use_llm:
        prompt = _build_llm_prompt(report)
        narrative, meta = generate_market_narrative(config.llm, prompt)
        report["llm_narrative"] = narrative
        report["llm_metadata"] = meta

    return report


def write_market_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "market_intel.json"
    md_path = output_dir / "market_intel.md"
    html_path = output_dir / "market_intel.html"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path, "html": html_path}


# ---------------------------------------------------------------------------
# Price-based analysis
# ---------------------------------------------------------------------------


def _price_analysis(prices: pd.DataFrame, benchmark: str, lang: str = "en") -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    as_of = pd.to_datetime(prices["date"]).max()
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
    buy_candidates = _rank_buy_candidates(frame, lang)
    high_risk = _rank_high_risk(frame, lang)
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
                "last_price": row["last_price"],
                "ret_21d_pct": round(float(row["ret_21d"]) * 100, 2),
                "ret_5d_pct": round(float(row["ret_5d"]) * 100, 2),
                "vol_annual_pct": round(float(row["vol_annual"]) * 100, 1),
                "reason": _favorable_reason(row, lang),
            }
        )
    return out


def _rank_high_risk(frame: pd.DataFrame, lang: str = "en", limit: int = 8) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    df = frame.dropna(subset=["vol_annual"]).copy()
    if df.empty:
        return []
    vol_threshold = float(df["vol_annual"].quantile(0.75))
    flagged = df[
        (df["vol_annual"] >= vol_threshold)
        | (df["max_drawdown_252"] <= -0.20)
        | (df["ret_5d"] <= -0.08)
        | (df["dist_from_high"] <= -0.25)
    ].copy()
    if flagged.empty:
        return []
    # Highest volatility + deepest drawdown surface first.
    flagged["risk_score"] = flagged["vol_annual"].fillna(0) - flagged["max_drawdown_252"].fillna(0)
    flagged = flagged.sort_values("risk_score", ascending=False).head(limit)
    out = []
    for _, row in flagged.iterrows():
        out.append(
            {
                "symbol": row["symbol"],
                "last_price": row["last_price"],
                "ret_5d_pct": round(float(row["ret_5d"]) * 100, 2) if pd.notna(row["ret_5d"]) else None,
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
    parts = [tr(
        f"annualized vol ~{float(row['vol_annual']) * 100:.0f}% (elevated)",
        f"年化波动约{float(row['vol_annual']) * 100:.0f}%（偏高）",
        lang,
    )]
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
    latest_date = pd.to_datetime(matured["date"]).max()
    latest = matured[pd.to_datetime(matured["date"]) == latest_date].copy()
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
            symbols.append(
                {
                    "symbol": str(r["symbol"]),
                    "score": round(score, 3),
                    "strength": strength,
                    "last_price": round(float(r["adj_close"]), 2) if pd.notna(r.get("adj_close")) else None,
                    "reason": _quant_reason(r, spec["weights"], lang),
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


def _quant_reason(row: pd.Series, weights: dict[str, float], lang: str = "en") -> str:
    contributions = []
    for column, weight in weights.items():
        value = row.get(column)
        if value is None or pd.isna(value):
            continue
        contributions.append((abs(float(value) * weight), _z_label(column, lang), float(value)))
    contributions.sort(reverse=True)
    top = contributions[:2]
    if not top:
        return tr("composite cross-sectional ranking", "综合横截面信号排名", lang)
    sep = tr(", ", "、", lang)
    return sep.join(f"{label} z={value:+.1f}" for _, label, value in top)


def _pct(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    prev = float(series.iloc[-1 - periods])
    if prev == 0:
        return None
    return round(float(series.iloc[-1]) / prev - 1.0, 4)


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


def _collect_feeds(
    feeds: list[dict[str, str]], max_items: int, timeout: int
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    per_feed = max(3, max_items // max(len(feeds), 1) + 1)
    for feed in feeds:
        entries = None
        last_error: Exception | None = None
        for _attempt in range(2):  # one retry to absorb transient network hiccups
            try:
                entries = _fetch_rss(feed["url"], per_feed, timeout)
                break
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
        if entries is None:
            errors.append(f"feed_failed:{feed.get('name', feed['url'])}: {last_error}")
            continue
        for entry in entries:
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
        import yfinance as yf
    except Exception:  # pragma: no cover - optional dependency
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for symbol in symbols[:symbol_count]:
        try:
            raw_news = yf.Ticker(symbol).news or []
        except Exception:  # pragma: no cover - network dependent
            continue
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


def _build_llm_prompt(report: dict[str, Any]) -> str:
    lang = normalize_language(report.get("language", "en"))
    lines = [tr(
        "Using the data below, write a daily US-equity research brief in English, clearly "
        "separating relatively-strong research candidates from high-risk names, with reasoning.",
        "请基于以下数据，写一份今日美股研究简报（中文），明确区分相对值得关注的研究候选和高风险标的，并给出依据。",
        lang,
    ), ""]
    overview = report.get("market_overview") or {}
    if overview:
        lines.append(f"{tr('Market overview', '市场概览', lang)}: {json.dumps(overview, ensure_ascii=False)}")
    if report.get("buy_candidates"):
        lines.append(f"{tr('Relatively strong candidates (quant screen)', '相对偏强候选（量化筛选）', lang)}: {json.dumps(report['buy_candidates'], ensure_ascii=False)}")
    if report.get("high_risk"):
        lines.append(f"{tr('High-risk names (quant screen)', '高风险标的（量化筛选）', lang)}: {json.dumps(report['high_risk'], ensure_ascii=False)}")
    if report.get("quant_candidates"):
        lines.append(f"{tr('Quant candidates by horizon', '分类型量化候选', lang)}: {json.dumps(report['quant_candidates'], ensure_ascii=False)}")
    headlines = [f"- [{n.get('source')}] {n.get('title')}" for n in report.get("news", [])[:15]]
    if headlines:
        lines.append(tr("Latest financial-media headlines:", "最新财经媒体头条：", lang))
        lines.extend(headlines)
    lines.append("")
    lines.append(tr(
        "Requirements: a research tone; no order/position instructions or live-trading authorization; "
        "cite the data behind each conclusion; end with one risk note.",
        "要求：用研究口吻，不要给出下单指令、仓位指令或实盘授权；对每个结论说明数据依据；最后加一句风险提示。",
        lang,
    ))
    return "\n".join(lines)


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

    if report.get("llm_narrative"):
        lines.append(f"## {tr('AI synthesis', 'AI 综合分析', lang)}")
        lines.append(report["llm_narrative"])
        lines.append("")

    if report.get("buy_candidates"):
        lines.append(f"## {tr('Worth watching (research candidates)', '相对值得关注（研究候选）', lang)}")
        lines.append("| " + " | ".join(tr(
            "Symbol|Last|1M|5D|Ann. vol|Reason", "代码|最新价|近1月|近5日|年化波动|依据", lang).split("|")) + " |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for c in report["buy_candidates"]:
            lines.append(
                f"| {c['symbol']} | {c['last_price']} | {c['ret_21d_pct']}% | {c['ret_5d_pct']}% | "
                f"{c['vol_annual_pct']}% | {c['reason']} |"
            )
        lines.append("")

    if report.get("high_risk"):
        lines.append(f"## {tr('High-risk names (caution)', '高风险标的（谨慎）', lang)}")
        lines.append("| " + " | ".join(tr(
            "Symbol|Last|5D|Ann. vol|1Y max DD|Reason", "代码|最新价|近5日|年化波动|近一年最大回撤|依据", lang).split("|")) + " |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for c in report["high_risk"]:
            lines.append(
                f"| {c['symbol']} | {c['last_price']} | {c.get('ret_5d_pct')}% | {c['vol_annual_pct']}% | "
                f"{c.get('max_drawdown_252_pct')}% | {c['reason']} |"
            )
        lines.append("")

    quant = report.get("quant_candidates") or {}
    if quant:
        lines.append(f"## {tr('Quant picks by holding horizon', '按持有周期的量化推荐', lang)}")
        for profile, data in quant.items():
            lines.append(f"### {data.get('label', profile)}（{data.get('horizon', '')}）")
            for s in data.get("symbols", []):
                price = f"${s['last_price']}" if s.get("last_price") is not None else "—"
                lines.append(f"- {s['symbol']}（{price}, score {s['score']}）: {s.get('reason', '')}")
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

_REPORT_CSS = """
:root {
  --paper: #faf9f5; --card: #ffffff; --sand: #f1efe6; --sand-2: #e8e6dc;
  --line: #e3e0d4; --line-2: #d6d3c5;
  --ink: #141413; --ink-soft: #34322c; --muted: #6f6d62; --faint: #9a988c;
  --orange: #d97757; --orange-deep: #c25e3f; --orange-soft: #f3e0d7;
  --blue: #6a9bcc; --green: #788c5d; --down: #c25e3f;
  --head: "Poppins", "Noto Sans SC", -apple-system, "Segoe UI", sans-serif;
  --body: "Lora", "Noto Serif SC", Georgia, serif;
  --mono: "JetBrains Mono", ui-monospace, monospace;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; color: var(--ink); font-family: var(--body); line-height: 1.65; font-size: 15px;
  background:
    radial-gradient(1200px 620px at 82% -8%, rgba(217,119,87,0.08), transparent 62%),
    radial-gradient(900px 500px at -5% 4%, rgba(106,155,204,0.06), transparent 58%),
    var(--paper);
  background-attachment: fixed;
  -webkit-font-smoothing: antialiased;
}
.wrap { position: relative; z-index: 1; max-width: 1120px; margin: 0 auto; padding: 0 26px 80px; }

/* Masthead */
header { padding: 56px 0 26px; border-bottom: 1px solid var(--line-2); }
.kicker { font-family: var(--mono); font-size: 11.5px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--orange-deep); margin-bottom: 18px; }
.kicker::before { content: "✦ "; color: var(--orange); }
h1.title { font-family: var(--head); font-weight: 700; font-size: clamp(34px, 5.6vw, 58px); line-height: 1.06; letter-spacing: -0.01em; margin: 0; color: var(--ink); }
.title .en { display: block; font-family: var(--body); font-style: italic; font-weight: 400; font-size: clamp(15px, 2vw, 20px); color: var(--muted); letter-spacing: 0.01em; margin-top: 14px; }
.metabar { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 26px; }
.pill { font-family: var(--mono); font-size: 11.5px; letter-spacing: 0.03em; color: var(--ink-soft); border: 1px solid var(--line-2); border-radius: 999px; padding: 6px 13px; background: var(--card); }
.pill b { color: var(--orange-deep); font-weight: 700; }
.pill.ok b { color: var(--green); } .pill.bad b { color: var(--down); }

/* Disclaimer */
.ribbon { display: flex; gap: 12px; align-items: flex-start; margin: 28px 0 6px; padding: 14px 17px; border: 1px solid var(--line); border-left: 3px solid var(--orange); background: linear-gradient(90deg, var(--orange-soft), rgba(243,224,215,0.18)); border-radius: 0 10px 10px 0; font-size: 13px; color: var(--ink-soft); }
.ribbon::before { content: "✦"; color: var(--orange); font-family: var(--mono); }

/* Sections */
section { margin-top: 48px; opacity: 0; transform: translateY(16px); animation: rise 0.7s cubic-bezier(.2,.7,.2,1) forwards; }
section:nth-of-type(1){animation-delay:.05s} section:nth-of-type(2){animation-delay:.12s} section:nth-of-type(3){animation-delay:.19s} section:nth-of-type(4){animation-delay:.26s} section:nth-of-type(5){animation-delay:.33s} section:nth-of-type(6){animation-delay:.40s} section:nth-of-type(n+7){animation-delay:.45s}
@keyframes rise { to { opacity: 1; transform: none; } }
.sec-head { display: flex; align-items: baseline; gap: 13px; margin-bottom: 22px; }
.sec-num { font-family: var(--mono); font-size: 12px; color: var(--orange); letter-spacing: 0.08em; font-weight: 500; }
h2 { font-family: var(--head); font-weight: 600; font-size: 23px; margin: 0; color: var(--ink); letter-spacing: -0.01em; }
.sec-head .hint { font-size: 12px; color: var(--faint); margin-left: auto; font-family: var(--mono); }

/* Stat tiles */
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.tile { background: var(--card); padding: 18px 18px 16px; }
.tile .t-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
.tile .t-value { font-family: var(--mono); font-size: 27px; font-weight: 700; margin-top: 8px; color: var(--ink); }

/* Recommendation columns */
.reco-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(248px, 1fr)); gap: 16px; }
.reco { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 0 0 6px; overflow: hidden; box-shadow: 0 1px 2px rgba(20,20,19,0.03); }
.reco-top { padding: 17px 18px 14px; border-bottom: 1px solid var(--line); position: relative; }
.reco-top::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--orange), var(--orange-soft)); }
.reco-name { font-family: var(--head); font-weight: 600; font-size: 19px; color: var(--ink); }
.reco-meta { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.chip { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.04em; padding: 3px 9px; border-radius: 999px; border: 1px solid var(--orange-soft); background: var(--orange-soft); color: var(--orange-deep); }
.reco-tag { font-size: 11px; color: var(--faint); font-family: var(--mono); }
.pick { padding: 13px 18px; border-bottom: 1px solid var(--sand); }
.pick:last-child { border-bottom: 0; }
.pick-row { display: flex; align-items: center; gap: 10px; }
.rank { font-family: var(--mono); font-size: 11px; color: var(--faint); width: 16px; }
.ticker { font-family: var(--mono); font-weight: 700; font-size: 16px; color: var(--ink); letter-spacing: 0.01em; }
.price { margin-left: auto; font-family: var(--mono); font-size: 13px; color: var(--muted); }
.bar { height: 5px; border-radius: 3px; background: var(--sand-2); margin: 10px 0 7px; overflow: hidden; }
.bar > span { display: block; height: 100%; background: linear-gradient(90deg, var(--orange-deep), var(--orange)); border-radius: 3px; }
.pick .why { font-size: 11.5px; color: var(--muted); font-family: var(--mono); }

/* Data tables (buy / risk) */
.panel { border: 1px solid var(--line); border-radius: 16px; overflow: hidden; background: var(--card); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
thead th { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); text-align: left; padding: 13px 16px; background: var(--sand); border-bottom: 1px solid var(--line); }
tbody td { padding: 13px 16px; border-bottom: 1px solid var(--sand); vertical-align: middle; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover td { background: var(--sand); }
td.sym { font-family: var(--mono); font-weight: 700; font-size: 15px; }
.buy td.sym { color: var(--green); } .risk td.sym { color: var(--down); }
td.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.why-cell { color: var(--muted); font-size: 12.5px; max-width: 320px; }
.pos { color: var(--green); } .neg { color: var(--down); } .flat { color: var(--muted); } .muted { color: var(--faint); }

/* Narrative */
.narrative { background: var(--card); border: 1px solid var(--line); border-left: 3px solid var(--orange); border-radius: 0 14px 14px 0; padding: 20px 24px; white-space: pre-wrap; line-height: 1.9; font-size: 15px; color: var(--ink-soft); }

/* News */
.news-list { display: grid; gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.news-item { background: var(--card); padding: 14px 17px; display: flex; gap: 14px; align-items: baseline; transition: background .15s; }
.news-item:hover { background: var(--sand); }
.src { flex: none; font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.03em; color: var(--orange-deep); border: 1px solid var(--orange-soft); background: var(--orange-soft); border-radius: 6px; padding: 3px 8px; min-width: 100px; text-align: center; }
.news-item a, .news-item .h { color: var(--ink); text-decoration: none; font-size: 14.5px; }
.news-item a:hover { color: var(--orange-deep); text-decoration: underline; }
.news-item time { margin-left: auto; flex: none; font-family: var(--mono); font-size: 11px; color: var(--faint); white-space: nowrap; }

/* Company news */
.co-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
.co { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; }
.co h3 { font-family: var(--mono); font-size: 14px; color: var(--orange-deep); margin: 0 0 10px; letter-spacing: 0.03em; font-weight: 700; }
.co ul { margin: 0; padding: 0; list-style: none; }
.co li { padding: 8px 0; border-top: 1px solid var(--sand); font-size: 13.5px; }
.co li:first-child { border-top: 0; }
.co a { color: var(--ink); text-decoration: none; } .co a:hover { color: var(--orange-deep); }
.co .pub { color: var(--faint); font-size: 11px; font-family: var(--mono); }

/* Warnings + footer */
.notes { font-size: 12.5px; color: var(--muted); }
.notes li { font-family: var(--mono); }
footer { margin-top: 64px; padding-top: 22px; border-top: 1px solid var(--line-2); font-size: 11.5px; color: var(--faint); font-family: var(--mono); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.empty { color: var(--muted); font-size: 13px; padding: 18px; border: 1px dashed var(--line-2); border-radius: 12px; background: var(--card); }
@media (max-width: 600px) { .news-item { flex-wrap: wrap; } .news-item time { margin-left: 0; } header { padding-top: 36px; } }
"""


def render_html(report: dict[str, Any]) -> str:
    lang = normalize_language(report.get("language", "en"))
    n = _SectionCounter()
    body = [
        _html_overview(report, n, lang),
        _html_narrative(report, n, lang),
        _html_reco(report, n, lang),
        _html_table(report, "buy_candidates", tr("Worth watching", "相对值得关注", lang), n, lang),
        _html_table(report, "high_risk", tr("High-risk names", "高风险标的", lang), n, lang),
        _html_news(report, n, lang),
        _html_company(report, n, lang),
        _html_social(report, n, lang),
        _html_notes(report, n, lang),
    ]
    sections = "\n".join(block for block in body if block)
    status = str(report.get("data_status"))
    status_cls = "ok" if status == "ok" else "bad"
    overview = report.get("market_overview") or {}
    sample_count = overview.get("symbols_analyzed", report.get("universe_size", 0))
    na = tr("unavailable", "不可用", lang)
    title_main = tr("Daily US Equity Research Brief", "今日美股研究简报", lang)
    return f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_main}</title>
{_FONT_LINK}
<style>{_REPORT_CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="kicker">Daily US Equity Briefing · {tr('US market research', '美股每日研究', lang)}</div>
  <h1 class="title">{title_main}<span class="en">A quantitative reading of today's US market</span></h1>
  <div class="metabar">
    <span class="pill">{tr('Data as of', '数据截止', lang)} <b>{_esc(report.get('as_of_date') or na)}</b></span>
    <span class="pill {status_cls}">{tr('Status', '状态', lang)} <b>{_esc(status)}</b></span>
    <span class="pill">{tr('Generated', '生成', lang)} (UTC) <b>{_esc(str(report.get('generated_at'))[:19])}</b></span>
    <span class="pill">{tr('Sample', '样本', lang)} <b>{_esc(sample_count)}</b></span>
  </div>
</header>
<div class="ribbon">{_esc(report.get('disclaimer', ''))}</div>
{sections}
<footer>
  <span>QUANT.AI · RESEARCH ONLY — {tr('not investment advice', '不构成投资建议', lang)}</span>
  <span>generated {_esc(str(report.get('generated_at'))[:19])} UTC</span>
</footer>
</div>
</body>
</html>
"""


class _SectionCounter:
    def __init__(self) -> None:
        self.value = 0

    def next(self) -> str:
        self.value += 1
        return f"{self.value:02d}"


def _esc(value: Any) -> str:
    return html.escape(str(value))


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


def _html_narrative(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    narrative = report.get("llm_narrative")
    if not narrative:
        return ""
    return f'<section>{_sec_head(n.next(), tr("AI synthesis", "AI 综合分析", lang), "model synthesis")}<div class="narrative">{_esc(narrative)}</div></section>'


def _html_reco(report: dict[str, Any], n: _SectionCounter, lang: str = "en") -> str:
    quant = report.get("quant_candidates") or {}
    if not quant:
        return ""
    columns = []
    for data in quant.values():
        picks = []
        for i, s in enumerate(data.get("symbols", []), start=1):
            price = f"${s['last_price']}" if s.get("last_price") is not None else "—"
            strength = int(s.get("strength", 60))
            picks.append(
                f'<div class="pick"><div class="pick-row"><span class="rank">{i:02d}</span>'
                f'<span class="ticker">{_esc(s["symbol"])}</span><span class="price">{_esc(price)}</span></div>'
                f'<div class="bar"><span style="width:{strength}%"></span></div>'
                f'<div class="why">{_esc(s.get("reason", ""))}</div></div>'
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
    head = _sec_head(n.next(), tr("Research picks by holding horizon", "按持有周期的研究推荐", lang), tr("long / mid / short …", "长线 / 中线 / 短线 …", lang))
    return f'<section>{head}<div class="reco-grid">{"".join(columns)}</div></section>'


def _html_table(report: dict[str, Any], key: str, title: str, n: _SectionCounter, lang: str = "en") -> str:
    rows_data = report.get(key) or []
    if not rows_data:
        return ""
    if key == "buy_candidates":
        ths = tr("Symbol|Last|1M|5D|Ann. vol|Reason", "代码|最新价|近1月|近5日|年化波动|依据", lang).split("|")
        head = "<tr>" + "".join(f"<th>{_esc(t)}</th>" for t in ths) + "</tr>"
        body = "".join(
            f'<tr><td class="sym">{_esc(c["symbol"])}</td><td class="num">{c["last_price"]}</td>'
            f'<td class="num">{_delta(c.get("ret_21d_pct"))}</td><td class="num">{_delta(c.get("ret_5d_pct"))}</td>'
            f'<td class="num muted">{c.get("vol_annual_pct")}%</td><td class="why-cell">{_esc(c.get("reason", ""))}</td></tr>'
            for c in rows_data
        )
        cls, hint = "buy", tr("uptrend · contained vol", "趋势向上 · 波动可控", lang)
    else:
        ths = tr("Symbol|Last|5D|Ann. vol|1Y max DD|Reason", "代码|最新价|近5日|年化波动|近一年最大回撤|依据", lang).split("|")
        head = "<tr>" + "".join(f"<th>{_esc(t)}</th>" for t in ths) + "</tr>"
        body = "".join(
            f'<tr><td class="sym">{_esc(c["symbol"])}</td><td class="num">{c["last_price"]}</td>'
            f'<td class="num">{_delta(c.get("ret_5d_pct"))}</td><td class="num neg">{c.get("vol_annual_pct")}%</td>'
            f'<td class="num neg">{c.get("max_drawdown_252_pct")}%</td><td class="why-cell">{_esc(c.get("reason", ""))}</td></tr>'
            for c in rows_data
        )
        cls, hint = "risk", tr("high vol · deep drawdown · sharp drop", "高波动 · 深回撤 · 急跌", lang)
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
        cards.append(f'<div class="co"><h3>{_esc(symbol)}</h3><ul>{lis}</ul></div>')
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
