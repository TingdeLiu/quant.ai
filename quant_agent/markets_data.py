"""Real-data payload for the Tyndall Markets dashboard (quant_agent/web/ui_kits/markets).

Maps the project's existing quant signals and price statistics onto the data shape
the design expects (``TICKERS`` / ``WATCH`` / ``PRICE`` / ``defaultSym``). The AI
analyst rating, summary, and bull/bear cases are all derived from real metrics — no
fundamentals, no forecasts. Research only; not investment advice.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import pandas as pd

from quant_agent.config import AppConfig
from quant_agent.data import load_prices
from quant_agent.features import build_signals

# Light static enrichment for common tickers (we have no fundamentals data source).
NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation", "NVDA": "NVIDIA Corporation",
    "AMD": "Advanced Micro Devices", "GOOGL": "Alphabet Inc.", "GOOG": "Alphabet Inc.",
    "META": "Meta Platforms, Inc.", "AMZN": "Amazon.com, Inc.", "TSLA": "Tesla, Inc.",
    "JPM": "JPMorgan Chase & Co.", "BAC": "Bank of America Corp.", "V": "Visa Inc.",
    "MA": "Mastercard Inc.", "XOM": "Exxon Mobil Corporation", "CVX": "Chevron Corporation",
    "JNJ": "Johnson & Johnson", "UNH": "UnitedHealth Group", "KO": "The Coca-Cola Company",
    "PEP": "PepsiCo, Inc.", "WMT": "Walmart Inc.", "AVGO": "Broadcom Inc.",
    "CRM": "Salesforce, Inc.", "NFLX": "Netflix, Inc.", "ADBE": "Adobe Inc.",
    "COST": "Costco Wholesale", "HD": "The Home Depot", "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust",
}
SECTORS: dict[str, str] = {
    "AAPL": "Consumer Electronics", "MSFT": "Software", "NVDA": "Semiconductors",
    "AMD": "Semiconductors", "AVGO": "Semiconductors", "GOOGL": "Interactive Media",
    "GOOG": "Interactive Media", "META": "Interactive Media", "AMZN": "E-Commerce",
    "TSLA": "Automobiles", "JPM": "Banks", "BAC": "Banks", "V": "Financials",
    "MA": "Financials", "XOM": "Energy", "CVX": "Energy", "JNJ": "Pharmaceuticals",
    "UNH": "Health Care", "KO": "Beverages", "PEP": "Beverages", "WMT": "Retail",
    "HD": "Retail", "COST": "Retail", "CRM": "Software", "ADBE": "Software",
    "NFLX": "Entertainment", "SPY": "S&P 500 ETF", "QQQ": "Nasdaq-100 ETF",
}
TFS = ["1D", "1W", "1M", "6M", "1Y", "5Y"]

_Z_LABELS = {
    "momentum_12_1_z": "12-1 momentum",
    "trend_20_50_z": "20/50 trend",
    "reversal_1m_z": "1-month reversal",
    "low_volatility_z": "low volatility",
    "ml_rank_z": "the ML rank",
}


def build_markets_data(config: AppConfig) -> dict[str, Any]:
    """Build the markets dashboard payload from real quant data."""
    prices = load_prices(config.data)
    signals = build_signals(prices, config.strategy.signal_weights)
    matured = signals.dropna(subset=["score"])
    if matured.empty:
        return {"TICKERS": {}, "WATCH": [], "PRICE": {}, "TFS": TFS, "defaultSym": None}

    latest_date = pd.to_datetime(matured["date"]).max()
    latest = matured[pd.to_datetime(matured["date"]) == latest_date].sort_values("score", ascending=False)
    series_map = {str(sym): g.sort_values("date") for sym, g in prices.groupby("symbol")}

    tickers: dict[str, Any] = {}
    order: list[str] = []
    for _, row in latest.iterrows():
        sym = str(row["symbol"])
        group = series_map.get(sym)
        if group is None or len(group) < 30:
            continue
        entry = _ticker_entry(sym, row, group)
        if entry is None:
            continue
        tickers[sym] = entry
        order.append(sym)

    watch_syms = order[:6]
    watch = [{"sym": s, "chg": tickers[s]["chg"]} for s in watch_syms]
    price_map = {s: tickers[s]["price"] for s in tickers}
    return {
        "TICKERS": tickers,
        "WATCH": watch,
        "PRICE": price_map,
        "TFS": TFS,
        "defaultSym": watch_syms[0] if watch_syms else None,
        "as_of": str(latest_date.date()),
        "brief": _daily_brief(tickers, order),
        "disclaimer": "Research signals derived from price history. Not investment advice.",
    }


def _ticker_entry(sym: str, row: pd.Series, group: pd.DataFrame) -> dict[str, Any] | None:
    adj = group["adj_close"].astype(float)
    price = float(adj.iloc[-1])
    if price <= 0:
        return None
    chg = _ret(adj, 1)
    m1 = _ret(adj, 21)
    d5 = _ret(adj, 5)
    daily = adj.pct_change().dropna().tail(20)
    vol_annual = float(daily.std() * math.sqrt(252)) * 100 if len(daily) >= 5 else 0.0
    hist = adj.tail(252)
    hi, lo = float(hist.max()), float(hist.min())
    dist_high = (price / hi - 1) * 100 if hi else 0.0
    drawdown = _max_drawdown(hist) * 100
    ma_20 = float(adj.tail(20).mean())
    ma_50 = float(adj.tail(50).mean()) if len(adj) >= 50 else ma_20
    trend_up = ma_20 >= ma_50
    addv = float(row.get("avg_dollar_volume_20") or 0.0)
    score = float(row["score"])
    rating = _rating(score, vol_annual, trend_up, m1)

    stats = {
        "1M return": _signed(m1),
        "5D return": _signed(d5),
        "Ann. vol": f"{vol_annual:.0f}%",
        "52-wk range": f"${lo:,.0f}–${hi:,.0f}",
        "Avg $ vol": _human_money(addv),
        "Signal": f"{score:+.2f}",
    }
    bull, bear = _cases(row, m1, d5, vol_annual, drawdown, dist_high, trend_up)
    return {
        "name": NAMES.get(sym, sym),
        "sector": SECTORS.get(sym, "US Equity"),
        "price": round(price, 2),
        "chg": round(chg, 2) if chg is not None else 0.0,
        "seed": int(hashlib.sha1(sym.encode("utf-8")).hexdigest(), 16) % 100000,
        "drift": max(-0.6, min(0.7, score * 0.22 + (0.18 if trend_up else -0.12))),
        "stats": stats,
        "rating": rating,
        "summary": _summary(NAMES.get(sym, sym), rating, m1, vol_annual, row),
        "bull": bull,
        "bear": bear,
    }


def _rating(score: float, vol_annual: float, trend_up: bool, m1: float | None) -> str:
    if vol_annual >= 45:
        return "Volatile"
    if score >= 0.5 and trend_up:
        return "Bullish"
    if score <= -0.3 or (m1 is not None and m1 < -8):
        return "Cautious"
    return "Neutral"


def _cases(
    row: pd.Series, m1: float | None, d5: float | None, vol: float, dd: float, dist_high: float, trend_up: bool
) -> tuple[list[str], list[str]]:
    bull: list[str] = []
    if trend_up:
        bull.append("Price holds above its 20- and 50-day moving averages")
    if m1 is not None and m1 > 0:
        bull.append(f"Up {m1:.1f}% over the past month")
    mom_z = row.get("momentum_12_1_z")
    if pd.notna(mom_z) and float(mom_z) > 0.3:
        bull.append(f"12-1 momentum near the top of the cross-section (z {float(mom_z):+.1f})")
    lowvol_z = row.get("low_volatility_z")
    if pd.notna(lowvol_z) and float(lowvol_z) > 0.3:
        bull.append("Realized volatility is relatively contained")
    if dist_high > -5:
        bull.append("Trading close to its 52-week high")

    bear: list[str] = [f"Annualized volatility around {vol:.0f}%"]
    if dd <= -15:
        bear.append(f"Drew down {abs(dd):.0f}% from its 1-year peak at the worst")
    if d5 is not None and d5 <= -4:
        bear.append(f"Pulled back {d5:.1f}% over the past week")
    rev_z = row.get("reversal_1m_z")
    if pd.notna(rev_z) and float(rev_z) < -0.3:
        bear.append("Recent strength may mean-revert over the next month")
    if dist_high <= -20:
        bear.append(f"Sits {dist_high:.0f}% below its 52-week high")

    bull = bull[:3] or ["Ranks acceptably on the blended quant signal"]
    bear = bear[:3] or ["Limited historical edge in the current signal mix"]
    return bull, bear


def _summary(name: str, rating: str, m1: float | None, vol: float, row: pd.Series) -> str:
    parts = [f"{name} screens as {rating.lower()} on the blended quant signal."]
    if m1 is not None:
        direction = "up" if m1 >= 0 else "down"
        parts.append(f"It is {direction} {abs(m1):.1f}% over the past month with roughly {vol:.0f}% annualized volatility.")
    top = _top_signal(row)
    if top:
        parts.append(f"The read is led by {top}.")
    parts.append("These are research signals from price history, not a forecast or investment advice.")
    return " ".join(parts)


def _top_signal(row: pd.Series) -> str | None:
    best_label: str | None = None
    best_abs = 0.0
    for column, label in _Z_LABELS.items():
        value = row.get(column)
        if pd.isna(value):
            continue
        if abs(float(value)) > best_abs:
            best_abs = abs(float(value))
            best_label = label
    return best_label


def _daily_brief(tickers: dict[str, Any], order: list[str]) -> str:
    if not order:
        return "No symbols available for today's brief."
    changes = [tickers[s]["chg"] for s in order if tickers[s].get("chg") is not None]
    avg = sum(changes) / len(changes) if changes else 0.0
    advancing = sum(1 for c in changes if c > 0)
    leader = order[0]
    return (
        f"{advancing} of {len(changes)} watched names are higher today; the basket is "
        f"{'up' if avg >= 0 else 'down'} {abs(avg):.1f}% on average. "
        f"{tickers[leader]['name']} ({leader}) tops the quant signal screen."
    )


def _ret(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    prev = float(series.iloc[-1 - periods])
    if prev == 0:
        return None
    return (float(series.iloc[-1]) / prev - 1) * 100


def _max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    running_max = series.cummax()
    return float((series / running_max - 1.0).min())


def _signed(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def _human_money(value: float) -> str:
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.1f}M"
    if value >= 1e3:
        return f"${value / 1e3:.1f}K"
    return f"${value:.0f}"
