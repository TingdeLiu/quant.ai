from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DataConfig:
    source: str
    start: str | None
    end: str | None
    cache_dir: Path
    universe: list[str]
    path: Path | None = None
    csv_path: Path | None = None
    data_dir: Path | None = None
    universe_path: Path | None = None
    # Hours before an open-ended (end=null) yfinance cache is refreshed.
    # None disables expiry (cache reused forever); fixed end dates never expire.
    cache_ttl_hours: float | None = 6.0


@dataclass(frozen=True)
class StrategyConfig:
    benchmark: str
    top_n: int
    rebalance_frequency: str
    initial_cash: float
    transaction_cost_bps: float
    slippage_bps: float
    signal_weights: dict[str, float]


@dataclass(frozen=True)
class RiskConfig:
    max_position_weight: float
    max_positions: int
    min_avg_dollar_volume: float
    max_turnover: float
    long_only: bool


@dataclass(frozen=True)
class ReportConfig:
    output_dir: Path


@dataclass(frozen=True)
class EvaluationPeriod:
    name: str
    start: str | None
    end: str | None


@dataclass(frozen=True)
class EvaluationConfig:
    periods: list[EvaluationPeriod]


@dataclass(frozen=True)
class SignalOptimizationConfig:
    enabled: bool
    train_period: str
    validation_period: str
    objective: str
    max_drawdown_floor: float
    walk_forward_enabled: bool
    walk_forward_windows: list[dict[str, str | None]]


@dataclass(frozen=True)
class MLConfig:
    enabled: bool
    train_period: str
    prediction_horizon_days: int
    model_version: str
    feature_version: str


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    provider: str
    model: str
    endpoint: str | None
    api_key_env: str
    prompt_version: str


@dataclass(frozen=True)
class MarketIntelConfig:
    enabled: bool
    output_dir: Path
    news_feeds: list[dict[str, str]]
    social_enabled: bool
    social_feeds: list[dict[str, str]]
    max_news_items: int
    symbol_news_count: int
    max_symbol_news: int
    use_llm: bool
    request_timeout: int


@dataclass(frozen=True)
class PaperTradingConfig:
    enabled: bool
    account_value: float
    max_order_notional: float
    output_dir: Path


@dataclass(frozen=True)
class DashboardConfig:
    enabled: bool
    output_path: Path
    service_dir: Path
    runs_dir: Path


@dataclass(frozen=True)
class DashboardSecurityConfig:
    enabled: bool
    token_env: str
    token: str | None
    audit_log_path: Path


@dataclass(frozen=True)
class ScheduleConfig:
    enabled: bool
    interval_minutes: int
    run_on_start: bool


@dataclass(frozen=True)
class AlertConfig:
    enabled: bool
    max_drawdown_floor: float
    min_sharpe: float
    max_stale_rows: int
    require_paper_approval: bool


@dataclass(frozen=True)
class NotificationConfig:
    enabled: bool
    min_severity: str
    channels: list[str]
    output_dir: Path
    webhook_url_env: str


@dataclass(frozen=True)
class ApprovalConfig:
    require_manual_paper_approval: bool
    allow_broker_submit_after_approval: bool


@dataclass(frozen=True)
class AppConfig:
    data: DataConfig
    strategy: StrategyConfig
    risk: RiskConfig
    report: ReportConfig
    evaluation: EvaluationConfig
    optimization: SignalOptimizationConfig
    ml: MLConfig
    llm: LLMConfig
    market_intel: MarketIntelConfig
    paper_trading: PaperTradingConfig
    dashboard: DashboardConfig
    dashboard_security: DashboardSecurityConfig
    schedule: ScheduleConfig
    alerts: AlertConfig
    notifications: NotificationConfig
    approvals: ApprovalConfig


DEFAULT_NEWS_FEEDS: list[dict[str, str]] = [
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"},
    {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"},
    {"name": "MarketWatch Top Stories", "url": "http://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "MarketWatch Markets", "url": "http://feeds.marketwatch.com/marketwatch/marketpulse/"},
    {"name": "Investing.com News", "url": "https://www.investing.com/rss/news_25.rss"},
]


def _parse_feeds(raw_feeds: Any, default: list[dict[str, str]]) -> list[dict[str, str]]:
    if raw_feeds is None:
        return [dict(feed) for feed in default]
    feeds: list[dict[str, str]] = []
    for entry in raw_feeds:
        if isinstance(entry, str):
            feeds.append({"name": entry, "url": entry})
        elif isinstance(entry, dict) and entry.get("url"):
            feeds.append({"name": str(entry.get("name", entry["url"])), "url": str(entry["url"])})
    return feeds


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    base = config_path.parent.parent if config_path.parent.name == "configs" else Path.cwd()
    return parse_config(raw, base=base)


def parse_config(raw: dict[str, Any], base: Path | None = None) -> AppConfig:
    base = base or Path.cwd()
    data = raw.get("data", {})
    strategy = raw.get("strategy", {})
    risk = raw.get("risk", {})
    report = raw.get("report", {})
    evaluation = raw.get("evaluation", {})
    optimization = raw.get("optimization", {})
    ml = raw.get("ml", {})
    llm = raw.get("llm", {})
    market_intel = raw.get("market_intel", {})
    paper_trading = raw.get("paper_trading", {})
    dashboard = raw.get("dashboard", {})
    dashboard_security = raw.get("dashboard_security", {})
    schedule = raw.get("schedule", {})
    alerts = raw.get("alerts", {})
    notifications = raw.get("notifications", {})
    approvals = raw.get("approvals", {})

    source = str(data.get("source", "yfinance")).lower()
    path = data.get("path")
    csv_path = data.get("csv_path")
    data_dir = data.get("data_dir")
    universe_path = data.get("universe_path")
    resolved_path = _resolve_path(base, path) if path else None
    resolved_csv_path = _resolve_path(base, csv_path) if csv_path else None
    if source == "csv" and resolved_path and resolved_csv_path is None:
        resolved_csv_path = resolved_path
    resolved_universe_path = _resolve_path(base, universe_path) if universe_path else None
    universe = _load_universe(resolved_universe_path) if resolved_universe_path else data.get("universe", [])
    report_output_dir = _resolve_path(base, report.get("output_dir", "reports/latest"))
    dashboard_output_path = _resolve_path(base, dashboard.get("output_path", report_output_dir / "dashboard.html"))
    dashboard_service_dir = _resolve_path(base, dashboard.get("service_dir", report_output_dir))
    dashboard_runs_dir = _resolve_path(base, dashboard.get("runs_dir", report_output_dir / "runs"))

    return AppConfig(
        data=DataConfig(
            source=source,
            start=data.get("start"),
            end=data.get("end"),
            cache_dir=_resolve_path(base, data.get("cache_dir", "data/cache")),
            universe=_normalize_universe(universe),
            path=resolved_path,
            csv_path=resolved_csv_path,
            data_dir=_resolve_path(base, data_dir) if data_dir else None,
            universe_path=resolved_universe_path,
            cache_ttl_hours=(
                None if data.get("cache_ttl_hours", 6.0) is None else float(data.get("cache_ttl_hours", 6.0))
            ),
        ),
        strategy=StrategyConfig(
            benchmark=str(strategy.get("benchmark", "SPY")).upper(),
            top_n=int(strategy.get("top_n", 5)),
            rebalance_frequency=str(strategy.get("rebalance_frequency", "M")),
            initial_cash=float(strategy.get("initial_cash", 100000)),
            transaction_cost_bps=float(strategy.get("transaction_cost_bps", 10)),
            slippage_bps=float(strategy.get("slippage_bps", 5)),
            signal_weights={str(k): float(v) for k, v in strategy.get("signal_weights", {}).items()},
        ),
        risk=RiskConfig(
            max_position_weight=float(risk.get("max_position_weight", 0.25)),
            max_positions=int(risk.get("max_positions", 5)),
            min_avg_dollar_volume=float(risk.get("min_avg_dollar_volume", 0)),
            max_turnover=float(risk.get("max_turnover", 1.0)),
            long_only=bool(risk.get("long_only", True)),
        ),
        report=ReportConfig(output_dir=report_output_dir),
        evaluation=EvaluationConfig(periods=_parse_periods(evaluation.get("periods", []))),
        optimization=SignalOptimizationConfig(
            enabled=bool(optimization.get("enabled", True)),
            train_period=str(optimization.get("train_period", "train")),
            validation_period=str(optimization.get("validation_period", "validation")),
            objective=str(optimization.get("objective", "sharpe")),
            max_drawdown_floor=float(optimization.get("max_drawdown_floor", -0.5)),
            walk_forward_enabled=bool(optimization.get("walk_forward_enabled", True)),
            walk_forward_windows=[
                {
                    "name": str(window["name"]),
                    "train_start": window.get("train_start"),
                    "train_end": window.get("train_end"),
                    "validation_start": window.get("validation_start"),
                    "validation_end": window.get("validation_end"),
                }
                for window in optimization.get("walk_forward_windows", [])
            ],
        ),
        ml=MLConfig(
            enabled=bool(ml.get("enabled", False)),
            train_period=str(ml.get("train_period", "train")),
            prediction_horizon_days=int(ml.get("prediction_horizon_days", 21)),
            model_version=str(ml.get("model_version", "ridge_v1")),
            feature_version=str(ml.get("feature_version", "technical_v1")),
        ),
        llm=LLMConfig(
            enabled=bool(llm.get("enabled", False)),
            provider=str(llm.get("provider", "openai-compatible")),
            model=str(llm.get("model", "gpt-4.1-mini")),
            endpoint=llm.get("endpoint"),
            api_key_env=str(llm.get("api_key_env", "OPENAI_API_KEY")),
            prompt_version=str(llm.get("prompt_version", "research_review_v1")),
        ),
        market_intel=MarketIntelConfig(
            enabled=bool(market_intel.get("enabled", True)),
            output_dir=_resolve_path(base, market_intel.get("output_dir", report_output_dir)),
            news_feeds=_parse_feeds(market_intel.get("news_feeds"), DEFAULT_NEWS_FEEDS),
            social_enabled=bool(market_intel.get("social_enabled", False)),
            social_feeds=_parse_feeds(market_intel.get("social_feeds"), []),
            max_news_items=int(market_intel.get("max_news_items", 24)),
            symbol_news_count=int(market_intel.get("symbol_news_count", 8)),
            max_symbol_news=int(market_intel.get("max_symbol_news", 3)),
            use_llm=bool(market_intel.get("use_llm", True)),
            request_timeout=int(market_intel.get("request_timeout", 12)),
        ),
        paper_trading=PaperTradingConfig(
            enabled=bool(paper_trading.get("enabled", False)),
            account_value=float(paper_trading.get("account_value", strategy.get("initial_cash", 100000))),
            max_order_notional=float(paper_trading.get("max_order_notional", 25000)),
            output_dir=_resolve_path(base, paper_trading.get("output_dir", "reports/paper")),
        ),
        dashboard=DashboardConfig(
            enabled=bool(dashboard.get("enabled", False)),
            output_path=dashboard_output_path,
            service_dir=dashboard_service_dir,
            runs_dir=dashboard_runs_dir,
        ),
        dashboard_security=DashboardSecurityConfig(
            enabled=bool(dashboard_security.get("enabled", False)),
            token_env=str(dashboard_security.get("token_env", "QUANT_AGENT_DASHBOARD_TOKEN")),
            token=dashboard_security.get("token"),
            audit_log_path=_resolve_path(
                base,
                dashboard_security.get("audit_log_path", "reports/latest/dashboard_audit.jsonl"),
            ),
        ),
        schedule=ScheduleConfig(
            enabled=bool(schedule.get("enabled", False)),
            interval_minutes=int(schedule.get("interval_minutes", 1440)),
            run_on_start=bool(schedule.get("run_on_start", False)),
        ),
        alerts=AlertConfig(
            enabled=bool(alerts.get("enabled", True)),
            max_drawdown_floor=float(alerts.get("max_drawdown_floor", -0.35)),
            min_sharpe=float(alerts.get("min_sharpe", 0.5)),
            max_stale_rows=int(alerts.get("max_stale_rows", 0)),
            require_paper_approval=bool(alerts.get("require_paper_approval", True)),
        ),
        notifications=NotificationConfig(
            enabled=bool(notifications.get("enabled", True)),
            min_severity=str(notifications.get("min_severity", "warning")),
            channels=[str(channel) for channel in notifications.get("channels", ["file"])],
            output_dir=_resolve_path(base, notifications.get("output_dir", "reports/notifications")),
            webhook_url_env=str(notifications.get("webhook_url_env", "QUANT_AGENT_WEBHOOK_URL")),
        ),
        approvals=ApprovalConfig(
            require_manual_paper_approval=bool(approvals.get("require_manual_paper_approval", True)),
            allow_broker_submit_after_approval=bool(approvals.get("allow_broker_submit_after_approval", False)),
        ),
    )


def _resolve_path(base: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def _load_universe(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {path}")
    symbols: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        first = f.readline().strip()
        if not first:
            return symbols
        header = [part.strip().lower() for part in first.split(",")]
        symbol_index = header.index("symbol") if "symbol" in header else 0
        if "symbol" not in header:
            symbols.append(first.split(",")[symbol_index])
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = [part.strip() for part in stripped.split(",")]
            if len(parts) > symbol_index:
                symbols.append(parts[symbol_index])
    return symbols


def _normalize_universe(symbols: list[Any]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol).strip().upper()
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _parse_periods(raw_periods: list[dict[str, Any]]) -> list[EvaluationPeriod]:
    periods: list[EvaluationPeriod] = []
    for raw in raw_periods:
        periods.append(
            EvaluationPeriod(
                name=str(raw["name"]),
                start=raw.get("start"),
                end=raw.get("end"),
            )
        )
    return periods
