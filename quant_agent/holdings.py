"""Chat-managed portfolio state: watchlist + holdings persisted to a single JSON file.

Store shape (``data/portfolio.json``, git-ignored, path from ``AppConfig.portfolio_path``)::

    {"version": 1,
     "watchlist": ["NVDA"],
     "holdings": [{"symbol": "AAPL", "shares": 15.0, "cost_basis": 182.5, "note": null}],
     "updated_at": "2026-07-04T09:00:00+00:00"}

这是用户口述的记账数据（研究用途），不是券商状态；本模块绝不下单。
watchlist/holdings 作为叠加层并入 config 的 universe，滚动价格库随之自动覆盖这些标的。
"""

from __future__ import annotations

import dataclasses
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import AppConfig, _normalize_universe

PORTFOLIO_VERSION = 1
_MAX_QUOTE_WORKERS = 8


def _empty_portfolio() -> dict[str, Any]:
    return {"version": PORTFOLIO_VERSION, "watchlist": [], "holdings": [], "updated_at": None}


def load_portfolio(path: Path) -> dict[str, Any]:
    """Load and normalize the portfolio store; missing file -> empty portfolio.

    A corrupted/unparseable file raises ``ValueError`` instead of returning an empty
    portfolio — a silent empty result followed by a save would destroy user data.
    """
    if not path.exists():
        return _empty_portfolio()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid portfolio file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid portfolio file {path}: top-level JSON must be an object")

    watchlist = _normalize_universe(list(raw.get("watchlist") or []))
    holdings: dict[str, dict[str, Any]] = {}
    for entry in raw.get("holdings") or []:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol", "")).strip().upper()
        try:
            shares = float(entry.get("shares") or 0)
        except (TypeError, ValueError):
            continue
        if not symbol or shares <= 0:
            continue
        try:
            cost_raw = entry.get("cost_basis")
            cost_basis = float(cost_raw) if cost_raw is not None and float(cost_raw) > 0 else None
        except (TypeError, ValueError):
            cost_basis = None
        note = str(entry["note"]) if entry.get("note") else None
        holdings[symbol] = {"symbol": symbol, "shares": shares, "cost_basis": cost_basis, "note": note}
    return {
        "version": PORTFOLIO_VERSION,
        "watchlist": watchlist,
        "holdings": list(holdings.values()),
        "updated_at": raw.get("updated_at"),
    }


def save_portfolio(portfolio: dict[str, Any], path: Path) -> Path:
    """Persist the portfolio atomically (tmp file + ``os.replace``, safe on Windows)."""
    portfolio["version"] = PORTFOLIO_VERSION
    portfolio["updated_at"] = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(portfolio, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def add_watchlist_symbols(portfolio: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    portfolio["watchlist"] = _normalize_universe([*portfolio.get("watchlist", []), *symbols])
    return portfolio


def remove_watchlist_symbols(portfolio: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    drop = set(_normalize_universe(symbols))
    portfolio["watchlist"] = [s for s in portfolio.get("watchlist", []) if s not in drop]
    return portfolio


def upsert_holdings(portfolio: dict[str, Any], positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Insert or replace holdings by symbol (whole entry replaced; order preserved, new appended)."""
    current: dict[str, dict[str, Any]] = {h["symbol"]: h for h in portfolio.get("holdings", [])}
    for entry in positions:
        symbol = str(entry.get("symbol", "")).strip().upper()
        if not symbol:
            raise ValueError("holding requires a symbol")
        shares = entry.get("shares")
        if shares is None or float(shares) <= 0:
            raise ValueError(f"holding {symbol} requires shares > 0")
        cost_raw = entry.get("cost_basis")
        if cost_raw is not None and float(cost_raw) <= 0:
            raise ValueError(f"holding {symbol} cost_basis must be > 0 when given")
        note = entry.get("note")
        current[symbol] = {
            "symbol": symbol,
            "shares": float(shares),
            "cost_basis": float(cost_raw) if cost_raw is not None else None,
            "note": str(note) if note else None,
        }
    portfolio["holdings"] = list(current.values())
    return portfolio


def remove_holdings(portfolio: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    drop = set(_normalize_universe(symbols))
    portfolio["holdings"] = [h for h in portfolio.get("holdings", []) if h["symbol"] not in drop]
    return portfolio


def portfolio_symbols(portfolio: dict[str, Any]) -> list[str]:
    """Watchlist first, then held symbols not already present (order-preserving, upper-case)."""
    return _normalize_universe(
        [*portfolio.get("watchlist", []), *(h["symbol"] for h in portfolio.get("holdings", []))]
    )


def apply_portfolio_universe(config: AppConfig) -> AppConfig:
    """Overlay watchlist + held symbols onto the config universe (identity when nothing to add).

    读路径必须打不死：portfolio 文件损坏时研究工具继续用原 universe，
    错误只由管理工具（严格 load）向用户暴露。
    """
    try:
        portfolio = load_portfolio(config.portfolio_path)
    except Exception:
        return config
    existing = set(config.data.universe)
    extra = [s for s in portfolio_symbols(portfolio) if s not in existing]
    if not extra:
        return config
    merged_data = dataclasses.replace(config.data, universe=[*config.data.universe, *extra])
    return dataclasses.replace(config, data=merged_data)


def fetch_live_quotes(symbols: list[str]) -> dict[str, float]:
    """Best-effort live quotes via yfinance ``fast_info`` — degrades to partial/{} on any failure.

    仅用于持仓盈亏展示；报告其余部分仍基于日线收盘。持仓一般只有几只，线程池上限沿用 data.py。
    """
    if not symbols:
        return {}
    try:
        import yfinance as yf
    except Exception:
        return {}

    def _one(symbol: str) -> tuple[str, float] | None:
        try:
            info = yf.Ticker(symbol).fast_info
            price = getattr(info, "last_price", None)
            if price is None:
                price = info["lastPrice"]
            value = float(price)
            return (symbol, value) if value > 0 else None
        except Exception:
            return None

    workers = max(1, min(_MAX_QUOTE_WORKERS, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_one, symbols))
    return dict(item for item in results if item is not None)


def build_holdings_snapshot(
    portfolio: dict[str, Any],
    prices: pd.DataFrame | None,
    quotes: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute per-position marks and P&L plus totals from the price history and optional live quotes.

    Returns ``{"positions": [...], "totals": {...}, "quotes_source": "realtime"|"last_close"|"mixed"}``.
    ``prices`` may be None/empty (positions are then priced from quotes only); ``cost_basis`` may be
    None (P&L fields stay None). 当日口径：有实时价 → 实时价对上一收盘；否则 → 库内最近两个收盘。
    """
    quotes = quotes or {}
    closes: dict[str, tuple[float | None, float | None]] = {}
    if prices is not None and not prices.empty:
        for symbol, group in prices.sort_values(["symbol", "date"]).groupby("symbol"):
            tail = group["adj_close"].astype(float).tail(2).tolist()
            closes[str(symbol)] = (tail[-1], tail[0] if len(tail) == 2 else None)

    positions: list[dict[str, Any]] = []
    totals_market = totals_cost = totals_pnl = totals_day = 0.0
    has_market = has_pnl = has_day = False
    sources: set[str] = set()
    for holding in portfolio.get("holdings", []):
        symbol = holding["symbol"]
        shares = float(holding["shares"])
        cost_basis = holding.get("cost_basis")
        last_close, prev_close = closes.get(symbol, (None, None))
        quote = quotes.get(symbol)
        price = quote if quote is not None else last_close
        price_source = "realtime" if quote is not None else ("last_close" if price is not None else None)
        if quote is not None and last_close:
            day_change_pct = (quote / last_close - 1) * 100
            day_pnl = shares * (quote - last_close)
        elif last_close and prev_close:
            day_change_pct = (last_close / prev_close - 1) * 100
            day_pnl = shares * (last_close - prev_close)
        else:
            day_change_pct = day_pnl = None
        market_value = round(shares * price, 2) if price is not None else None
        cost_value = round(shares * cost_basis, 2) if cost_basis else None
        unrealized_pnl = (
            round(market_value - cost_value, 2) if market_value is not None and cost_value is not None else None
        )
        unrealized_pnl_pct = (
            round((price / cost_basis - 1) * 100, 2) if price is not None and cost_basis else None
        )
        positions.append(
            {
                "symbol": symbol,
                "shares": shares,
                "cost_basis": cost_basis,
                "note": holding.get("note"),
                "price": round(price, 4) if price is not None else None,
                "price_source": price_source,
                "day_change_pct": round(day_change_pct, 2) if day_change_pct is not None else None,
                "day_pnl": round(day_pnl, 2) if day_pnl is not None else None,
                "market_value": market_value,
                "cost_value": cost_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": unrealized_pnl_pct,
            }
        )
        if price_source:
            sources.add(price_source)
        if market_value is not None:
            totals_market += market_value
            has_market = True
        if unrealized_pnl is not None:
            # 盈亏合计只累加「现价与成本都齐」的仓位，保证 pnl 与 cost 口径配对。
            totals_cost += cost_value
            totals_pnl += unrealized_pnl
            has_pnl = True
        if day_pnl is not None:
            totals_day += day_pnl
            has_day = True

    totals = {
        "positions": len(positions),
        "market_value": round(totals_market, 2) if has_market else None,
        "cost_value": round(totals_cost, 2) if has_pnl else None,
        "unrealized_pnl": round(totals_pnl, 2) if has_pnl else None,
        "unrealized_pnl_pct": round(totals_pnl / totals_cost * 100, 2) if has_pnl and totals_cost > 0 else None,
        "day_pnl": round(totals_day, 2) if has_day else None,
    }
    quotes_source = "mixed" if len(sources) > 1 else next(iter(sources), "last_close")
    return {"positions": positions, "totals": totals, "quotes_source": quotes_source}
