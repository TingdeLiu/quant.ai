from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from quant_agent.config import DataConfig

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


def _load_yfinance(config: DataConfig, force_refresh: bool = False) -> pd.DataFrame:
    if not config.universe:
        raise ValueError("data.universe cannot be empty")
    cache_path = _cache_path(config)
    if cache_path.exists() and not force_refresh and not _cache_is_stale(config, cache_path):
        return pd.read_csv(cache_path)

    try:
        prices = _download_yfinance(config)
    except Exception:
        # Network/API failure: fall back to whatever cache we have rather than erroring.
        if cache_path.exists():
            return pd.read_csv(cache_path)
        raise
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(cache_path, index=False)
    return prices


def _cache_is_stale(config: DataConfig, cache_path: Path) -> bool:
    """Open-ended (end=null) caches expire after cache_ttl_hours; fixed ranges never do."""
    if config.cache_ttl_hours is None or config.end is not None:
        return False
    age_hours = (time.time() - cache_path.stat().st_mtime) / 3600.0
    return age_hours >= config.cache_ttl_hours


def _yf_download_retry(yf, symbol: str, config: DataConfig, attempts: int = 3) -> pd.DataFrame:
    """单只下载，带指数退避重试，缓解网络抖动和 yfinance 限流（空返回）。"""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            raw = yf.download(
                symbol, start=config.start, end=config.end, auto_adjust=False, progress=False
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


def _download_one(yf, symbol: str, config: DataConfig) -> pd.DataFrame | None:
    raw = _yf_download_retry(yf, symbol, config)
    if raw.empty:
        return None
    raw = raw.reset_index()
    return pd.DataFrame(
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


def _download_yfinance(config: DataConfig) -> pd.DataFrame:
    import yfinance as yf

    workers = max(1, min(_MAX_DOWNLOAD_WORKERS, len(config.universe)))
    rows: list[pd.DataFrame] = []
    if workers == 1:
        frames = [_download_one(yf, symbol, config) for symbol in config.universe]
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            frames = list(executor.map(lambda s: _download_one(yf, s, config), config.universe))
    rows = [frame for frame in frames if frame is not None and not frame.empty]
    if not rows:
        raise ValueError("yfinance returned no data")
    return pd.concat(rows, ignore_index=True)


def _cache_path(config: DataConfig) -> Path:
    # 用排序后 universe 的哈希做 key：股票数量多时不会撑爆文件名/路径长度
    # （Windows 上拼接全部 ticker 容易超过 260 字符上限），且与 ticker 顺序无关。
    digest = hashlib.sha1("_".join(sorted(config.universe)).encode("utf-8")).hexdigest()[:16]
    universe_key = f"{len(config.universe)}_{digest}"
    start = config.start or "none"
    end = config.end or "latest"
    return config.cache_dir / f"prices_{universe_key}_{start}_{end}.csv"


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
