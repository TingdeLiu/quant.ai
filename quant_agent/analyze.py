"""Fast, zero-config single-stock analysis for ordinary investors.

`python -m quant_agent analyze AAPL MSFT` pulls recent prices, computes explainable
technical indicators, and returns a "rating + reasons + key levels" verdict. No
backtest, no universe, no YAML config required. Output defaults to English; pass
`language="zh"` (CLI `--lang zh`) for Chinese.

This is quantitative research over historical prices only — not investment advice,
and it never produces any order instruction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant_agent.config import DataConfig, LLMConfig
from quant_agent.data import load_prices
from quant_agent.i18n import DEFAULT_LANGUAGE, normalize_language, tr


def _disclaimer(lang: str) -> str:
    return tr(
        "This analysis uses quantitative indicators over historical prices, for research "
        "reference only — not investment advice. Make your own decisions and manage risk.",
        "本分析基于历史价格的量化指标，仅供研究参考，不构成投资建议，请自行决策并控制风险。",
        lang,
    )


# 评级桶：从看多到看空。标签与操作语气都带 (英文, 中文)。
RATING_BUCKETS: list[tuple[float, tuple[str, str], tuple[str, str]]] = [
    (
        1.10,
        ("Strong Buy", "强烈看多"),
        (
            "Trend and momentum are strengthening together — a research buy candidate; "
            "still match it to your own risk tolerance.",
            "趋势与动量同向走强，属于研究买入候选；仍需结合个人风险承受能力。",
        ),
    ),
    (
        0.40,
        ("Mildly Bullish", "偏多"),
        ("Bullish signals dominate; watch for pullbacks rather than chasing highs.", "多头信号占优，可逢回调关注，不建议追高。"),
    ),
    (
        -0.40,
        ("Neutral", "中性"),
        ("Bulls and bears are roughly balanced; direction unclear — wait for a clearer trend.", "多空力量接近均衡，方向不明，宜观望等待趋势明朗。"),
    ),
    (
        -1.10,
        ("Mildly Bearish", "偏空"),
        ("Bearish signals dominate; trend weakening — holders should manage risk.", "空头信号占优，趋势走弱，持仓者注意控制风险。"),
    ),
    (
        -99.0,
        ("Strong Sell", "强烈看空"),
        ("Trend and momentum are weakening together; from a research view, avoid.", "趋势与动量同向走弱，研究层面建议回避。"),
    ),
]


@dataclass
class SymbolAnalysis:
    symbol: str
    ok: bool
    rating: str = ""
    composite: float = 0.0
    confidence: str = ""
    note: str = ""
    price: float | None = None
    data_date: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    levels: dict[str, float | None] = field(default_factory=dict)
    error: str = ""
    # 绘图用的近端价格序列，不参与 JSON 序列化。
    frame: pd.DataFrame | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "ok": self.ok,
            "rating": self.rating,
            "composite_score": round(self.composite, 3),
            "confidence": self.confidence,
            "note": self.note,
            "price": self.price,
            "data_date": self.data_date,
            "metrics": self.metrics,
            "reasons": self.reasons,
            "levels": self.levels,
            "error": self.error,
        }


def analyze_symbols(
    symbols: list[str],
    lookback_days: int = 600,
    cache_dir: Path | None = None,
    llm_config: LLMConfig | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    """分析一组标的，返回结构化结果（含可选的 LLM 自然语言综述）。"""
    lang = normalize_language(language)
    cleaned = _clean_symbols(symbols)
    if not cleaned:
        raise ValueError(tr("Please provide at least one ticker, e.g. AAPL", "请至少提供一个股票代码，例如 AAPL", lang))

    prices, fetch_error = _fetch_prices(cleaned, lookback_days=lookback_days, cache_dir=cache_dir)
    by_symbol = {sym: g for sym, g in prices.groupby("symbol")} if not prices.empty else {}

    if fetch_error == "network":
        missing_msg = tr(
            "Network unavailable: can't reach the market data source (Yahoo Finance). Check your network/proxy and retry.",
            "网络不可用：无法连接行情数据源（Yahoo Finance）。请检查网络/代理后重试。",
            lang,
        )
    elif fetch_error == "other":
        missing_msg = tr(
            "Data fetch failed: the data source is temporarily unresponsive, please retry later.",
            "行情拉取失败：数据源暂时无响应，请稍后重试。",
            lang,
        )
    else:
        missing_msg = tr(
            "Not enough data: make sure it's a US ticker (e.g. AAPL, MSFT) that isn't delisted or halted.",
            "未获取到足够数据：请确认是美股代码（如 AAPL、MSFT），且该标的未退市或暂停交易。",
            lang,
        )

    results: list[SymbolAnalysis] = []
    for symbol in cleaned:
        group = by_symbol.get(symbol)
        if group is None or len(group) < 30:
            results.append(SymbolAnalysis(symbol=symbol, ok=False, error=missing_msg))
            continue
        results.append(_analyze_one(symbol, group.sort_values("date"), language=lang))

    narrative, narrative_meta = _maybe_narrative(results, llm_config, lang)
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "language": lang,
        "symbols": cleaned,
        "results": [r.to_dict() for r in results],
        "narrative": narrative,
        "narrative_meta": narrative_meta,
        "disclaimer": _disclaimer(lang),
        "_objects": results,
    }


def _analyze_one(symbol: str, g: pd.DataFrame, language: str = DEFAULT_LANGUAGE) -> SymbolAnalysis:
    lang = normalize_language(language)
    adj = g["adj_close"].astype(float).reset_index(drop=True)
    ret_1d = adj.pct_change()
    price = float(adj.iloc[-1])
    data_date = str(pd.to_datetime(g["date"].iloc[-1]).date())

    ma20 = _safe_last(adj.rolling(20).mean())
    ma50 = _safe_last(adj.rolling(50).mean())
    ma200 = _safe_last(adj.rolling(200).mean())
    vol_annual = _safe_last(ret_1d.rolling(20).std()) * np.sqrt(252) if len(adj) > 20 else None
    rsi = _rsi(adj, 14)
    mom_12_1 = _pct_change_at(adj, periods=252, shift=21)
    ret_1m = _trailing_return(adj, 21)
    ret_3m = _trailing_return(adj, 63)
    ret_6m = _trailing_return(adj, 126)
    ret_1y = _trailing_return(adj, 252)

    window_52w = adj.tail(252)
    high_52w = float(window_52w.max())
    low_52w = float(window_52w.min())
    dist_high = price / high_52w - 1 if high_52w else None
    dist_low = price / low_52w - 1 if low_52w else None

    reasons: list[str] = []

    # --- 趋势分 ---
    trend = 0.0
    if ma50 is not None:
        if price > ma50:
            trend += 1.0
            reasons.append(tr(
                f"Price {price:.2f} is above the 50-day MA {ma50:.2f} (mid-term uptrend)",
                f"价格 {price:.2f} 在 50 日均线 {ma50:.2f} 上方（中期趋势偏多）",
                lang,
            ))
        else:
            trend -= 1.0
            reasons.append(tr(
                f"Price {price:.2f} broke below the 50-day MA {ma50:.2f} (mid-term trend weakening)",
                f"价格 {price:.2f} 跌破 50 日均线 {ma50:.2f}（中期趋势偏弱）",
                lang,
            ))
    if ma20 is not None and ma50 is not None:
        trend += 0.6 if ma20 > ma50 else -0.6
    if ma200 is not None:
        trend += 0.4 if price > ma200 else -0.4
        if price < ma200:
            reasons.append(tr(
                f"Price is below the 200-day MA {ma200:.2f} (long-term trend under pressure)",
                f"价格低于 200 日均线 {ma200:.2f}（长期趋势承压）",
                lang,
            ))

    # --- 动量分 ---
    momentum = 0.0
    if mom_12_1 is not None:
        momentum += _bucket(mom_12_1, [(0.20, 2.0), (0.05, 1.0), (-0.05, 0.0), (-0.20, -1.0)], -2.0)
        reasons.append(tr(f"12-1 month momentum {mom_12_1:+.1%}", f"12-1 月动量 {mom_12_1:+.1%}", lang))
    if ret_3m is not None:
        momentum += _bucket(ret_3m, [(0.10, 0.6), (0.0, 0.2), (-0.10, -0.2)], -0.6)

    # --- 反转 / 超买超卖分 ---
    reversal = 0.0
    if rsi is not None:
        if rsi >= 75:
            reversal -= 0.8
            reasons.append(tr(
                f"RSI {rsi:.0f} is in overbought territory; near-term pullback risk",
                f"RSI {rsi:.0f} 进入超买区，短线有回调风险",
                lang,
            ))
        elif rsi <= 30:
            reversal += 0.8
            reasons.append(tr(
                f"RSI {rsi:.0f} is in oversold territory; possible near-term bounce",
                f"RSI {rsi:.0f} 进入超卖区，短线或有反弹",
                lang,
            ))
        else:
            reasons.append(tr(f"RSI {rsi:.0f} (neutral range)", f"RSI {rsi:.0f}（中性区间）", lang))

    composite = 0.45 * trend + 0.40 * momentum + 0.15 * reversal
    composite = float(np.clip(composite, -2.5, 2.5))

    rating, note = _rating_for(composite, lang)

    # 波动率作为信心调节，而非方向
    confidence = _confidence(composite, vol_annual, lang)
    if vol_annual is not None and vol_annual > 0.55:
        reasons.append(tr(
            f"Annualized volatility ~{vol_annual:.0%}; large swings, mind position sizing",
            f"年化波动率约 {vol_annual:.0%}，价格波动较大，注意仓位控制",
            lang,
        ))

    if dist_high is not None and dist_high > -0.03:
        reasons.append(tr(
            f"Near the 52-week high ({dist_high:+.1%} from high)",
            f"接近 52 周高点（距高点 {dist_high:+.1%}）",
            lang,
        ))
    if dist_low is not None and dist_low < 0.05:
        reasons.append(tr(
            f"Near the 52-week low ({dist_low:+.1%} from low)",
            f"接近 52 周低点（距低点 {dist_low:+.1%}）",
            lang,
        ))

    levels = _key_levels(price, ma20, ma50, low_52w, vol_annual)

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(g["date"].values),
            "close": adj.values,
            "ma20": adj.rolling(20).mean().values,
            "ma50": adj.rolling(50).mean().values,
            "ma200": adj.rolling(200).mean().values,
            "rsi": _rsi_series(adj, 14).values,
        }
    )

    metrics = {
        "ret_1m": _round(ret_1m),
        "ret_3m": _round(ret_3m),
        "ret_6m": _round(ret_6m),
        "ret_1y": _round(ret_1y),
        "momentum_12_1": _round(mom_12_1),
        "ma20": _round(ma20, 2),
        "ma50": _round(ma50, 2),
        "ma200": _round(ma200, 2),
        "rsi_14": _round(rsi, 1),
        "vol_annual": _round(vol_annual),
        "dist_52w_high": _round(dist_high),
        "dist_52w_low": _round(dist_low),
    }

    return SymbolAnalysis(
        symbol=symbol,
        ok=True,
        rating=rating,
        composite=composite,
        confidence=confidence,
        note=note,
        price=round(price, 2),
        data_date=data_date,
        metrics=metrics,
        reasons=reasons[:6],
        levels=levels,
        frame=frame,
    )


def _key_levels(
    price: float,
    ma20: float | None,
    ma50: float | None,
    low_52w: float | None,
    vol_annual: float | None,
) -> dict[str, float | None]:
    """给出参考性的关注位（支撑/止损），不构成下单指令。"""
    # 支撑取现价下方最近的均线；若价格已跌破所有均线，则回退到 52 周低点。
    supports = [v for v in (ma20, ma50) if v is not None and v < price]
    if supports:
        support = round(max(supports), 2)
    elif low_52w is not None and low_52w < price:
        support = round(low_52w, 2)
    else:
        support = None
    # 参考止损：放在支撑位下方一点，并结合波动率给缓冲；取两者更靠下的一个。
    daily_vol = (vol_annual / np.sqrt(252)) if vol_annual else 0.02
    vol_stop = price * (1 - max(2.0 * daily_vol, 0.06))
    support_stop = support * 0.97 if support else None
    stop_candidates = [v for v in (support_stop, vol_stop) if v is not None and v < price]
    ref_stop = round(min(stop_candidates), 2) if stop_candidates else round(price * 0.92, 2)
    return {
        "reference_support": support,
        "reference_stop": ref_stop,
        "ma20": round(ma20, 2) if ma20 else None,
        "ma50": round(ma50, 2) if ma50 else None,
    }


def _maybe_narrative(
    results: list[SymbolAnalysis], llm_config: LLMConfig | None, lang: str = DEFAULT_LANGUAGE
) -> tuple[str | None, dict[str, Any]]:
    if llm_config is None or not llm_config.enabled:
        return None, {"status": "disabled"}
    ok_results = [r for r in results if r.ok]
    if not ok_results:
        return None, {"status": "no_data"}
    lines = []
    for r in ok_results:
        m = r.metrics
        lines.append(
            f"{r.symbol}: rating={r.rating} score={r.composite:+.2f} price={r.price} "
            f"1M={m.get('ret_1m')} 3M={m.get('ret_3m')} momentum={m.get('momentum_12_1')} "
            f"RSI={m.get('rsi_14')} ann_vol={m.get('vol_annual')}; reasons: {'; '.join(r.reasons)}"
        )
    prompt = tr(
        "Below are quantitative technical indicators and rule-based ratings for several US "
        "stocks. Write a concise English summary for an ordinary investor: the trend and risk "
        "of each name, a watch idea (e.g. buy on dips / wait / manage risk), and make clear this "
        "is research analysis, not investment advice. Do not fabricate prices or fundamentals.\n\n",
        "以下是若干美股标的的量化技术指标和规则评级。请用简洁中文为普通投资者写一段综合解读，"
        "说明每只标的的趋势与风险，给出关注思路（如逢低关注/观望/控制风险），"
        "并明确这是研究分析而非投资建议。不要编造价格或基本面信息。\n\n",
        lang,
    ) + "\n".join(lines)
    try:
        from quant_agent.llm import generate_market_narrative

        return generate_market_narrative(llm_config, prompt)
    except Exception as exc:  # pragma: no cover - LLM 可选
        return None, {"status": "error", "error": str(exc)}


_NETWORK_HINTS = (
    "getaddrinfo",
    "name resolution",
    "name or service not known",
    "temporary failure in name resolution",
    "max retries",
    "connection",
    "timed out",
    "timeout",
    "unreachable",
    "ssl",
    "proxy",
    "remote end closed",
    "newconnectionerror",
    "failed to establish",
)


def _classify_fetch_error(exc: Exception) -> str:
    """把底层异常分类为 network / other，供调用方给出友好提示。"""
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(hint in text for hint in _NETWORK_HINTS):
        return "network"
    return "other"


def _fetch_prices(
    symbols: list[str], lookback_days: int, cache_dir: Path | None
) -> tuple[pd.DataFrame, str | None]:
    """拉取行情。返回 (DataFrame, 失败原因)；成功时原因为 None。"""
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    config = DataConfig(
        source="yfinance",
        start=start,
        end=None,
        cache_dir=cache_dir or Path("data/cache"),
        universe=symbols,
        cache_ttl_hours=6.0,
    )
    try:
        return load_prices(config), None
    except Exception as exc:  # noqa: BLE001 - 对普通用户统一降级为友好提示
        empty = pd.DataFrame(columns=["date", "symbol", "adj_close", "volume"])
        return empty, _classify_fetch_error(exc)


# ----------------------- 小工具 -----------------------


def read_symbols_file(path: Path) -> list[str]:
    """从自选股文件读取代码：支持每行一个或逗号分隔，`#` 之后视为注释。"""
    raw = Path(path).read_text(encoding="utf-8-sig")
    tokens: list[str] = []
    for line in raw.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            tokens.append(line)
    return _clean_symbols(tokens)


def _clean_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in symbols:
        for part in str(raw).replace(",", " ").split():
            value = part.strip().upper()
            if value and value not in seen:
                seen.add(value)
                cleaned.append(value)
    return cleaned


def _rating_for(composite: float, lang: str = DEFAULT_LANGUAGE) -> tuple[str, str]:
    for threshold, label, note in RATING_BUCKETS:
        if composite >= threshold:
            return tr(*label, lang), tr(*note, lang)
    _, label, note = RATING_BUCKETS[-1]
    return tr(*label, lang), tr(*note, lang)


def _confidence(composite: float, vol_annual: float | None, lang: str = DEFAULT_LANGUAGE) -> str:
    strength = abs(composite)
    if vol_annual is not None and vol_annual > 0.6:
        strength *= 0.8
    if strength >= 1.1:
        return tr("High", "高", lang)
    if strength >= 0.5:
        return tr("Medium", "中", lang)
    return tr("Low", "低", lang)


def _bucket(value: float, thresholds: list[tuple[float, float]], floor: float) -> float:
    for cutoff, score in thresholds:
        if value >= cutoff:
            return score
    return floor


def _rsi_series(series: pd.Series, period: int = 14) -> pd.Series:
    """整段 RSI 序列（用于绘图）；数据不足时返回全 NaN。"""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _rsi(series: pd.Series, period: int = 14) -> float | None:
    if len(series) <= period:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    last_gain = gain.iloc[-1]
    last_loss = loss.iloc[-1]
    if pd.isna(last_gain) or pd.isna(last_loss):
        return None
    if last_loss == 0:
        return 100.0
    rs = last_gain / last_loss
    return float(100 - (100 / (1 + rs)))


def _pct_change_at(series: pd.Series, periods: int, shift: int) -> float | None:
    shifted = series.pct_change(periods).shift(shift)
    value = _safe_last(shifted)
    return value


def _trailing_return(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    past = series.iloc[-periods - 1]
    if pd.isna(past) or past == 0:
        return None
    return float(series.iloc[-1] / past - 1)


def _safe_last(series: pd.Series) -> float | None:
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    return None if pd.isna(value) else float(value)


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def write_analysis(
    payload: dict[str, Any], output_dir: Path, with_charts: bool = False
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    serializable = {k: v for k, v in payload.items() if k != "_objects"}
    json_path = output_dir / "analysis.json"
    json_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path = output_dir / "analysis.md"
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    charts: list[Path] = []
    if with_charts:
        for result in payload.get("_objects", []):
            if result.ok and result.frame is not None:
                png = render_chart(result, output_dir)
                if png is not None:
                    charts.append(png)
    return {"json": json_path, "markdown": md_path, "charts": charts}


_CJK_FONTS = ["Microsoft YaHei", "SimHei", "PingFang SC", "Heiti SC", "Noto Sans CJK SC", "WenQuanYi Zen Hei"]


def _setup_cjk_font(matplotlib) -> None:
    """若系统装有常见中文字体则启用，避免图中中文显示为方块。"""
    try:
        from matplotlib.font_manager import FontProperties, findSystemFonts

        available = set()
        for path in findSystemFonts():
            try:
                available.add(FontProperties(fname=path).get_name())
            except Exception:
                continue
        chosen = [f for f in _CJK_FONTS if f in available]
        if chosen:
            matplotlib.rcParams["font.sans-serif"] = chosen + matplotlib.rcParams.get("font.sans-serif", [])
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:  # pragma: no cover
        pass


def render_chart(result: SymbolAnalysis, output_dir: Path, lookback: int = 252) -> Path | None:
    """导出价格+均线+RSI 的 PNG。matplotlib 缺失或数据不足时安全跳过。"""
    if result.frame is None or result.frame.empty:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")  # 无界面后端，适合服务器/CI
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover - matplotlib 可选
        return None

    _setup_cjk_font(matplotlib)

    df = result.frame.tail(lookback)
    fig, (ax_price, ax_rsi) = plt.subplots(
        2, 1, figsize=(9, 5.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    ax_price.plot(df["date"], df["close"], label="Close", color="#1f77b4", linewidth=1.4)
    for col, color, name in (("ma20", "#ff7f0e", "MA20"), ("ma50", "#2ca02c", "MA50"), ("ma200", "#9467bd", "MA200")):
        if df[col].notna().any():
            ax_price.plot(df["date"], df[col], label=name, color=color, linewidth=1.0, alpha=0.9)
    support = result.levels.get("reference_support")
    stop = result.levels.get("reference_stop")
    if support:
        ax_price.axhline(support, color="#2ca02c", linestyle="--", linewidth=0.8, alpha=0.6)
    if stop:
        ax_price.axhline(stop, color="#d62728", linestyle="--", linewidth=0.8, alpha=0.6)
    ax_price.set_title(f"{result.symbol}  —  {result.rating}", fontsize=12)
    ax_price.legend(loc="upper left", fontsize=8, ncol=4)
    ax_price.grid(alpha=0.25)

    ax_rsi.plot(df["date"], df["rsi"], color="#7f7f7f", linewidth=1.0)
    ax_rsi.axhline(70, color="#d62728", linestyle=":", linewidth=0.7)
    ax_rsi.axhline(30, color="#2ca02c", linestyle=":", linewidth=0.7)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", fontsize=8)
    ax_rsi.grid(alpha=0.25)

    fig.tight_layout()
    png_path = output_dir / f"{result.symbol}.png"
    fig.savefig(png_path, dpi=110)
    plt.close(fig)
    return png_path


def render_markdown(payload: dict[str, Any]) -> str:
    lang = normalize_language(payload.get("language", DEFAULT_LANGUAGE))
    lines = [f"# {tr('Market analysis', '行情分析', lang)} · {payload['as_of']}", ""]
    for r in payload["results"]:
        if not r["ok"]:
            lines.append(f"## {r['symbol']} — {tr('Unable to analyze', '无法分析', lang)}\n\n> {r['error']}\n")
            continue
        m = r["metrics"]
        lines.append(f"## {r['symbol']} — {r['rating']}（{tr('confidence', '信心', lang)}: {r['confidence']}）")
        lines.append("")
        lines.append(f"- {tr('Last', '最新价', lang)}: {r['price']}（{tr('as of', '数据日期', lang)} {r['data_date']}）")
        lines.append(
            f"- {tr('Returns', '区间涨跌', lang)}: 1M {_pct(m.get('ret_1m'))} ｜ 3M {_pct(m.get('ret_3m'))} ｜ "
            f"6M {_pct(m.get('ret_6m'))} ｜ 1Y {_pct(m.get('ret_1y'))}"
        )
        lines.append(
            f"- {tr('Key metrics', '关键指标', lang)}: RSI {m.get('rsi_14')} ｜ {tr('ann. vol', '年化波动', lang)} {_pct(m.get('vol_annual'))} ｜ "
            f"MA20 {m.get('ma20')} ｜ MA50 {m.get('ma50')} ｜ MA200 {m.get('ma200')}"
        )
        lines.append(f"- {tr('Note', '解读', lang)}: {r['note']}")
        if r["reasons"]:
            lines.append(f"- {tr('Reasons', '依据', lang)}:")
            for reason in r["reasons"]:
                lines.append(f"  - {reason}")
        levels = r["levels"]
        lines.append(
            f"- {tr('Key levels', '参考关注位', lang)}: {tr('support', '支撑', lang)} {levels.get('reference_support')} ｜ "
            f"{tr('stop', '参考止损', lang)} {levels.get('reference_stop')}"
        )
        lines.append("")
    if payload.get("narrative"):
        lines.append(f"## {tr('AI summary', 'AI 综合解读', lang)}")
        lines.append("")
        lines.append(payload["narrative"])
        lines.append("")
    lines.append(f"> {payload['disclaimer']}")
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1%}"
