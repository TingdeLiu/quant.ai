from __future__ import annotations

import contextlib
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from quant_agent.config import DataConfig
from quant_agent.yf_cache import import_yfinance

PRICE_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "adj_close", "volume"]
SUPPORTED_LOCAL_SUFFIXES = {".csv", ".parquet"}


def load_prices(config: DataConfig, force_refresh: bool = False) -> pd.DataFrame:
    if config.source == "csv":
        if config.csv_path is None:
            raise ValueError("data.csv_path or data.path is required when data.source is csv")
        prices = _read_price_file(config.csv_path)
    elif config.source == "parquet":
        if config.path is None:
            raise ValueError("data.path is required when data.source is parquet")
        prices = _read_price_file(config.path)
    elif config.source == "local":
        prices = _load_local_directory(config)
    elif config.source == "yfinance":
        prices = _load_yfinance(config, force_refresh=force_refresh)
    else:
        raise ValueError(f"Unsupported data source: {config.source}")

    prices = normalize_prices(prices)
    issues = validate_prices(prices)
    blocking = [issue for issue in issues if issue["severity"] == "error"]
    if blocking:
        raise ValueError(f"Price data validation failed: {blocking}")
    return prices


def _load_local_directory(config: DataConfig) -> pd.DataFrame:
    data_dir = config.data_dir or config.path
    if data_dir is None:
        raise ValueError("data.data_dir or data.path is required when data.source is local")
    if not data_dir.exists():
        raise FileNotFoundError(f"Local data directory not found: {data_dir}")
    if not data_dir.is_dir():
        raise ValueError(f"Local data path is not a directory: {data_dir}")

    files = sorted(path for path in data_dir.rglob("*") if path.suffix.lower() in SUPPORTED_LOCAL_SUFFIXES)
    if not files:
        raise ValueError(f"No CSV or Parquet price files found in {data_dir}")
    frames = [_read_price_file(path, infer_symbol=True) for path in files]
    return pd.concat(frames, ignore_index=True)


def _read_price_file(path: Path, infer_symbol: bool = False) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
    elif suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported price file type: {path}")
    if infer_symbol and not _has_symbol_column(frame):
        frame = frame.copy()
        frame["symbol"] = path.stem.upper()
    return frame


def _has_symbol_column(frame: pd.DataFrame) -> bool:
    normalized = {str(column).strip().lower().replace(" ", "_") for column in frame.columns}
    return bool({"symbol", "ticker"} & normalized)


def normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.copy()
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    rename_map = {"datetime": "date", "ticker": "symbol", "adj_close": "adj_close", "adjclose": "adj_close"}
    frame = frame.rename(columns=rename_map)
    missing = [c for c in PRICE_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing price columns: {missing}")
    ordered_columns = PRICE_COLUMNS + [column for column in frame.columns if column not in PRICE_COLUMNS]
    frame = frame[ordered_columns].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False).dt.tz_localize(None)
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    numeric = ["open", "high", "low", "close", "adj_close", "volume"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def validate_prices(prices: pd.DataFrame) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if prices.empty:
        issues.append({"severity": "error", "code": "empty_prices", "message": "No price rows loaded"})
        return issues
    if prices.duplicated(["date", "symbol"]).any():
        issues.append({"severity": "error", "code": "duplicate_rows", "message": "Duplicate date/symbol rows"})
    numeric = ["open", "high", "low", "close", "adj_close", "volume"]
    if prices[numeric].isna().any().any():
        issues.append({"severity": "error", "code": "missing_values", "message": "Missing numeric price values"})
    if (prices[["open", "high", "low", "close", "adj_close"]] <= 0).any().any():
        issues.append({"severity": "error", "code": "non_positive_prices", "message": "Non-positive price values"})
    if (prices["volume"] < 0).any():
        issues.append({"severity": "error", "code": "negative_volume", "message": "Negative volume values"})
    counts = prices.groupby("symbol")["date"].count()
    thin = counts[counts < 80]
    if not thin.empty:
        issues.append({"severity": "warning", "code": "short_history", "message": f"Short history: {thin.to_dict()}"})
    return issues


# 最长保留约 10 年历史：更久远的数据参考价值有限，也减少每次下载量。
_MAX_HISTORY_DAYS = 365 * 10 + 3


def _effective_start(config: DataConfig) -> str:
    """下载/保留窗口的起始日：不早于约 10 年前（在用户 start 与 10 年下限中取较晚者）。"""
    floor = (datetime.now().date() - timedelta(days=_MAX_HISTORY_DAYS)).isoformat()
    return max(config.start, floor) if config.start else floor


def _trim_window(prices: pd.DataFrame, start: str) -> pd.DataFrame:
    if prices.empty:
        return prices
    keep = pd.to_datetime(prices["date"]) >= pd.Timestamp(start)
    return prices[keep].reset_index(drop=True)


def _load_yfinance(config: DataConfig, force_refresh: bool = False) -> pd.DataFrame:
    """Maintain a rolling per-universe price database: download only the user's symbols,
    keep at most ~10 years, refresh at most once per local day, and on a new day fetch
    only the missing dates and append them (no full re-download). When the universe
    changes (new cache key, e.g. a watchlist edit), seed history from sibling cache
    files and download only the genuinely missing symbols/dates."""
    if not config.universe:
        raise ValueError("data.universe cannot be empty")
    cache_path = _cache_path(config)
    existing = pd.read_csv(cache_path) if cache_path.exists() else None

    # Same-day (or still-fresh) cache: reuse as-is — never re-hit Yahoo for the same day.
    if existing is not None and not force_refresh and not _cache_is_stale(config, cache_path):
        return existing

    window_start = _effective_start(config)  # never earlier than ~10 years ago
    if existing is None and not force_refresh:
        # Universe 变了（新的缓存键）：从旧缓存播种交集标的的历史，只补缺口，不整库重下。
        existing = _seed_from_sibling_caches(config, window_start)

    start_by_symbol: dict[str, str] | None = None
    if existing is not None and not existing.empty and not force_refresh:
        start_by_symbol = _incremental_starts(existing, config.universe, window_start)

    try:
        fresh = _download_yfinance(config, window_start, start_by_symbol)
    except Exception:
        fresh = pd.DataFrame()

    if fresh.empty:
        # No new trading data (weekend/holiday) or a transient Yahoo failure: keep the
        # cached database and mark it checked-today so we don't keep hitting Yahoo.
        if existing is not None and not existing.empty:
            if cache_path.exists():
                cache_path.touch()
            else:
                _write_cache(existing, cache_path)  # 播种结果落地为本 universe 的数据库
                _prune_sibling_caches(cache_path)
            return existing
        raise ValueError("yfinance returned no data and no cache is available")

    combined = pd.concat([existing, fresh], ignore_index=True) if existing is not None and not existing.empty else fresh
    combined["date"] = pd.to_datetime(combined["date"]).dt.tz_localize(None)
    combined = (
        combined.drop_duplicates(["date", "symbol"], keep="last")  # newly fetched rows win
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )
    combined = _trim_window(combined, window_start)  # drop data older than the 10y window
    _write_cache(combined, cache_path)
    _prune_sibling_caches(cache_path)
    return combined


def _write_cache(frame: pd.DataFrame, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False)


def _sibling_caches(cache_path: Path) -> list[Path]:
    """Other universes' cache files in the same directory, newest first (by mtime)."""
    if not cache_path.parent.exists():
        return []
    return sorted(
        (path for path in cache_path.parent.glob("prices_*.csv") if path.name != cache_path.name),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _seed_from_sibling_caches(config: DataConfig, window_start: str) -> pd.DataFrame | None:
    """Reuse history for this universe's symbols from other cache files (newest first).

    自选池增删会改变缓存键；没有播种的话，加一只股票就要整个 universe 全量重下 10 年。
    每只标的取自含它的最新一份缓存（滚动库里新文件的历史总不短于旧文件）；全部标的凑齐
    就停止，不再把余下的旧文件逐个读完。
    """
    remaining = set(config.universe)
    frames: list[pd.DataFrame] = []
    for path in _sibling_caches(_cache_path(config)):
        if not remaining:
            break
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if any(column not in frame.columns for column in PRICE_COLUMNS):
            continue
        symbols = frame["symbol"].astype(str).str.upper()
        subset = frame[symbols.isin(remaining)][PRICE_COLUMNS]
        if not subset.empty:
            frames.append(subset)
            remaining -= set(symbols[symbols.isin(remaining)].unique())
    if not frames:
        return None
    seeded = pd.concat(frames, ignore_index=True)
    seeded["date"] = pd.to_datetime(seeded["date"]).dt.tz_localize(None)
    seeded = (
        seeded.drop_duplicates(["date", "symbol"], keep="first")  # 文件按 mtime 新→旧，先见者（新文件）优先
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )
    return _trim_window(seeded, window_start)


# 旧 universe 的缓存只在播种时有用（改一次自选就多出一份十几 MB 的全量库，且播种会逐个读它们）。
# 写入新库后只保留最近几份，既控制磁盘占用，也把播种的读盘量封顶。
_MAX_SIBLING_CACHES = 3


def _prune_sibling_caches(cache_path: Path, keep: int = _MAX_SIBLING_CACHES) -> None:
    """Delete other universes' cache files beyond the ``keep`` newest; the current file is never touched."""
    for stale in _sibling_caches(cache_path)[keep:]:
        with contextlib.suppress(OSError):  # 被占用等删不掉的情况不影响主流程，下次写库再试
            stale.unlink()


def _incremental_starts(existing: pd.DataFrame, universe: list[str], window_start: str) -> dict[str, str]:
    """Per-symbol download start: symbols with history resume at last date + 1; new symbols get the full window."""
    last_by_symbol = pd.to_datetime(existing["date"]).groupby(existing["symbol"]).max()
    starts: dict[str, str] = {}
    for symbol in universe:
        last = last_by_symbol.get(symbol)
        if last is None or pd.isna(last):
            starts[symbol] = window_start
        else:
            starts[symbol] = max(window_start, (last.date() + timedelta(days=1)).isoformat())
    return starts


def _cache_is_stale(config: DataConfig, cache_path: Path) -> bool:
    """Refresh the open-ended (end=null) cache at most once per local calendar day.

    A cache written today is always reused, so repeated same-day calls never re-hit
    Yahoo (anti-scraping friendly). On a later day it refreshes once it is older than
    ``cache_ttl_hours``. ``cache_ttl_hours=None`` or a fixed end date never expires.
    """
    if config.cache_ttl_hours is None or config.end is not None:
        return False
    mtime = cache_path.stat().st_mtime
    if datetime.fromtimestamp(mtime).date() >= datetime.now().date():
        return False  # written today — reuse, don't re-pull
    age_hours = (time.time() - mtime) / 3600.0
    return age_hours >= config.cache_ttl_hours


def _yf_download_retry(yf, symbol: str, config: DataConfig, start: str | None, attempts: int = 3) -> pd.DataFrame:
    """单只下载，带指数退避重试，缓解网络抖动和 yfinance 限流（空返回）。"""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            raw = yf.download(
                symbol, start=start, end=config.end, auto_adjust=False, progress=False
            )
            if not raw.empty:
                return raw
        except Exception as exc:  # noqa: BLE001 - 统一按可重试的瞬时错误处理
            last_exc = exc
        if attempt < attempts - 1:
            time.sleep(0.5 * (2**attempt))  # 0.5s, 1s, 2s ...
    if last_exc is not None:
        raise last_exc
    return pd.DataFrame()  # 多次重试仍为空：视为该标的无数据


# 单只下载本质是网络 IO（释放 GIL），用线程池并发能把大股票池从分钟级降到秒级。
_MAX_DOWNLOAD_WORKERS = 8


def _download_one(yf, symbol: str, config: DataConfig, start: str | None) -> pd.DataFrame | None:
    raw = _yf_download_retry(yf, symbol, config, start)
    if raw.empty:
        return None
    raw = raw.reset_index()
    frame = pd.DataFrame(
        {
            "date": raw["Date"],
            "symbol": symbol.upper(),
            "open": _column(raw, "Open"),
            "high": _column(raw, "High"),
            "low": _column(raw, "Low"),
            "close": _column(raw, "Close"),
            "adj_close": _column(raw, "Adj Close", fallback="Close"),
            "volume": _column(raw, "Volume"),
        }
    )
    # Drop incomplete rows — e.g. the latest, not-yet-settled session where Yahoo
    # returns a NaN adj_close — so one unsettled row doesn't fail the whole load.
    return frame.dropna(subset=["open", "high", "low", "close", "adj_close", "volume"])


def _download_yfinance(
    config: DataConfig, start: str | None, start_by_symbol: dict[str, str] | None = None
) -> pd.DataFrame:
    yf = import_yfinance()

    starts = start_by_symbol or {}
    today = datetime.now().date().isoformat()

    def _fetch(symbol: str) -> pd.DataFrame | None:
        symbol_start = starts.get(symbol, start)
        if symbol_start is not None and symbol_start > today:
            return None  # 该标的已最新（起点在未来），无需请求
        return _download_one(yf, symbol, config, symbol_start)

    workers = max(1, min(_MAX_DOWNLOAD_WORKERS, len(config.universe)))
    if workers == 1:
        frames = [_fetch(symbol) for symbol in config.universe]
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            frames = list(executor.map(_fetch, config.universe))
    rows = [frame for frame in frames if frame is not None and not frame.empty]
    if not rows:
        return pd.DataFrame()  # no new rows — caller reuses the cached database / decides
    return pd.concat(rows, ignore_index=True)


def _cache_path(config: DataConfig) -> Path:
    # 按排序后 universe 的哈希做 key（与 ticker 顺序无关，也不会撑爆 Windows 路径长度）。
    # 不含起止日期：这是一个滚动累积的「数据库」文件，每天增量追加、并裁掉超过 10 年的旧数据。
    digest = hashlib.sha1("_".join(sorted(config.universe)).encode("utf-8")).hexdigest()[:16]
    return config.cache_dir / f"prices_{len(config.universe)}_{digest}.csv"


def _column(frame: pd.DataFrame, name: str, fallback: str | None = None) -> pd.Series:
    column_name = name if name in frame.columns else fallback
    if column_name is None:
        raise KeyError(name)
    values = frame[column_name]
    if isinstance(values, pd.DataFrame):
        if values.shape[1] != 1:
            raise ValueError(f"Expected one column for {column_name}, got {values.shape[1]}")
        return values.iloc[:, 0]
    return values
