"""个性化股票池构建与首次 onboarding 的核心逻辑。

用户最终股票池 ≈ 2/3 自选（显式公司 + 感兴趣板块的代表股）+ 1/3 系统在自选之外的
「全市场」发现性推荐（在候选目录 `configs/catalog.csv` 上按横截面信号打分挑最强）。

本模块只负责纯逻辑（可离线、可单测）；交互式问答在 cli.py。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from quant_agent.analyze import _classify_fetch_error
from quant_agent.config import DataConfig
from quant_agent.data import load_prices
from quant_agent.features import build_signals
from quant_agent.recommendations import (
    RECOMMENDATION_PROFILES,
    _latest_signal_frame,
    _profile_score,
)

DEFAULT_BENCHMARK = "SPY"
# 自选占 2/3、发现占 1/3 ⇒ 发现数量 = round(自选数量 × 0.5)。
DISCOVERY_RATIO = 0.5
DEFAULT_HISTORY_START = "2020-01-01"

# 风险偏好（中文）→ 推荐打分风格（recommendations.RECOMMENDATION_PROFILES 的 key）。
RISK_TO_PROFILE: dict[str, str] = {
    "长线": "long_term",
    "波段": "swing",
    "短线": "short_term",
    "防守": "defensive",
    "激进": "aggressive",
}

DISCOVERY_STATUS_MESSAGES: dict[str, str] = {
    "ok": "",
    "offline": "网络不可用，已跳过「发现池」推荐，仅写入你自选的部分；联网后运行 `quant-ai refresh-universe` 即可补全。",
    "no_data": "行情数据暂时不可用，已跳过「发现池」推荐；稍后运行 `quant-ai refresh-universe` 可补全。",
    "empty": "候选目录在你的自选之外已无可推荐标的。",
}

CATALOG_COLUMNS = ["symbol", "name", "sector"]
UNIVERSE_COLUMNS = ["symbol", "name", "sector", "source"]


@dataclass
class UserProfile:
    """一次 onboarding 收集到的用户偏好，可序列化以便后续 refresh 复用。"""

    sectors: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    risk: str = "长线"
    benchmark: str = DEFAULT_BENCHMARK

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UserProfile:
        return cls(
            sectors=list(payload.get("sectors", [])),
            tickers=list(payload.get("tickers", [])),
            risk=str(payload.get("risk", "长线")),
            benchmark=str(payload.get("benchmark", DEFAULT_BENCHMARK)).upper(),
        )


def load_catalog(path: Path) -> pd.DataFrame:
    """读取候选目录 CSV，规范列名/代码并按 symbol 去重。"""
    frame = pd.read_csv(path)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "symbol" not in frame.columns:
        raise ValueError(f"候选目录缺少 symbol 列：{path}")
    if "name" not in frame.columns:
        frame["name"] = frame["symbol"]
    if "sector" not in frame.columns:
        frame["sector"] = "其他"
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["name"] = frame["name"].astype(str).str.strip()
    frame["sector"] = frame["sector"].astype(str).str.strip()
    frame = frame[frame["symbol"] != ""].drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    return frame[CATALOG_COLUMNS]


def catalog_sectors(catalog: pd.DataFrame) -> list[str]:
    """按首次出现顺序返回去重的板块列表。"""
    seen: list[str] = []
    for sector in catalog["sector"]:
        if sector not in seen:
            seen.append(sector)
    return seen


def discovery_count(user_size: int, ratio: float = DISCOVERY_RATIO) -> int:
    """自选 N 只 → 发现 round(N × ratio) 只（自选 2/3、发现 1/3）。"""
    if user_size <= 0:
        return 0
    return int(round(user_size * ratio))


def resolve_user_portion(profile: UserProfile, catalog: pd.DataFrame) -> list[str]:
    """用户 2/3：显式 tickers ∪ 所选板块的全部代表股，按加入顺序去重。"""
    by_sector: dict[str, list[str]] = {}
    for sym, sector in zip(catalog["symbol"], catalog["sector"], strict=False):
        by_sector.setdefault(sector, []).append(sym)

    picked: list[str] = []
    seen: set[str] = set()

    def _add(symbol: str) -> None:
        value = str(symbol).strip().upper()
        if value and value not in seen:
            seen.add(value)
            picked.append(value)

    for ticker in profile.tickers:
        _add(ticker)
    for sector in profile.sectors:
        for symbol in by_sector.get(sector, []):
            _add(symbol)
    return picked


def resolve_discovery(
    user_portion: list[str],
    catalog: pd.DataFrame,
    profile: UserProfile,
    loader: Callable[[DataConfig], pd.DataFrame] = load_prices,
    *,
    start: str = DEFAULT_HISTORY_START,
    cache_dir: Path = Path("data/cache"),
) -> tuple[list[str], str]:
    """发现池 1/3：在候选目录（自选之外）按横截面信号挑最强。

    返回 (symbols, status)。status ∈ {ok, offline, no_data, empty}，便于 CLI 给出
    友好提示并在离线时优雅降级（不抛栈）。
    """
    want = discovery_count(len(user_portion))
    if want <= 0:
        return [], "ok"

    exclude = {s.upper() for s in user_portion} | {profile.benchmark.upper()}
    pool = [s for s in catalog["symbol"].tolist() if s not in exclude]
    if not pool:
        return [], "empty"

    data_config = DataConfig(
        source="yfinance",
        start=start,
        end=None,
        cache_dir=cache_dir,
        universe=catalog["symbol"].tolist(),
    )
    try:
        prices = loader(data_config)
    except Exception as exc:  # noqa: BLE001 - 统一翻译为友好状态，离线降级
        return [], "offline" if _classify_fetch_error(exc) == "network" else "no_data"

    signals = build_signals(prices)
    latest = _latest_signal_frame(signals)
    if latest.empty:
        return [], "no_data"

    spec = RECOMMENDATION_PROFILES[RISK_TO_PROFILE.get(profile.risk, "long_term")]
    ranked = latest.copy()
    ranked["discovery_score"] = _profile_score(ranked, spec["weights"])
    ranked = ranked.dropna(subset=["discovery_score"])
    ranked = ranked[~ranked["symbol"].str.upper().isin(exclude)]
    ranked = ranked.sort_values("discovery_score", ascending=False)
    return ranked["symbol"].astype(str).str.upper().head(want).tolist(), "ok"


def build_personal_universe(
    profile: UserProfile,
    catalog: pd.DataFrame,
    loader: Callable[[DataConfig], pd.DataFrame] = load_prices,
    *,
    enable_discovery: bool = True,
    start: str = DEFAULT_HISTORY_START,
    cache_dir: Path = Path("data/cache"),
) -> tuple[pd.DataFrame, str]:
    """合并 2/3 自选 + 1/3 发现，输出带 source 标注的股票池。

    `enable_discovery=False` 时只产出自选部分、不下载行情（status 仍为 ok）。
    """
    user_portion = resolve_user_portion(profile, catalog)
    if enable_discovery:
        discovery, status = resolve_discovery(
            user_portion, catalog, profile, loader, start=start, cache_dir=cache_dir
        )
    else:
        discovery, status = [], "ok"

    meta = catalog.drop_duplicates(subset=["symbol"]).set_index("symbol")
    explicit = {str(t).strip().upper() for t in profile.tickers}

    def _row(symbol: str, source: str) -> dict[str, Any]:
        info = meta.loc[symbol] if symbol in meta.index else None
        return {
            "symbol": symbol,
            "name": str(info["name"]) if info is not None else symbol,
            "sector": str(info["sector"]) if info is not None else "其他",
            "source": source,
        }

    rows: list[dict[str, Any]] = []
    for symbol in user_portion:
        rows.append(_row(symbol, "picked" if symbol in explicit else "sector"))
    for symbol in discovery:
        rows.append(_row(symbol, "discovery"))

    frame = pd.DataFrame(rows, columns=UNIVERSE_COLUMNS)
    return frame, status


def write_personal_universe(
    frame: pd.DataFrame,
    profile: UserProfile,
    configs_dir: Path,
    base_config_path: Path,
) -> dict[str, Path]:
    """写出 my_universe.csv + my.yaml（继承 base 配置）+ profile.json。"""
    configs_dir.mkdir(parents=True, exist_ok=True)
    universe_csv = configs_dir / "my_universe.csv"
    frame.to_csv(universe_csv, index=False)

    base: dict[str, Any] = yaml.safe_load(base_config_path.read_text(encoding="utf-8")) or {}
    base.setdefault("data", {})
    base["data"].pop("universe", None)
    # 绝对路径：my.yaml 是用户本地生成文件（已 gitignore），不同 base 解析下都稳妥。
    base["data"]["universe_path"] = universe_csv.resolve().as_posix()
    base.setdefault("strategy", {})["benchmark"] = profile.benchmark

    my_yaml = configs_dir / "my.yaml"
    my_yaml.write_text(
        yaml.safe_dump(base, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    profile_json = configs_dir / "profile.json"
    profile_json.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"universe": universe_csv, "config": my_yaml, "profile": profile_json}


def load_profile(path: Path) -> UserProfile:
    return UserProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def read_universe_symbols(path: Path) -> list[str]:
    """从个性化股票池 CSV 读取 symbol 列（顺序保留、去重、大写）。"""
    frame = pd.read_csv(path)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    column = "symbol" if "symbol" in frame.columns else frame.columns[0]
    symbols: list[str] = []
    seen: set[str] = set()
    for value in frame[column].astype(str):
        sym = value.strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    return symbols
