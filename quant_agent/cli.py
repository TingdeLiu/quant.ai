from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from quant_agent.analyze import _clean_symbols, analyze_symbols, read_symbols_file, write_analysis
from quant_agent.comparison import write_strategy_comparison
from quant_agent.config import load_config
from quant_agent.config_tools import write_recommended_config
from quant_agent.dashboard import write_dashboard
from quant_agent.data import load_prices
from quant_agent.data_quality import build_data_quality_report, write_data_quality_report
from quant_agent.features import build_signals
from quant_agent.i18n import normalize_language, tr
from quant_agent.market_intel import build_market_report, write_market_report
from quant_agent.ml import apply_ml_ranking_signal
from quant_agent.onboarding import (
    UserProfile,
    build_personal_universe,
    catalog_sectors,
    discovery_status_message,
    load_catalog,
    load_profile,
    read_universe_symbols,
    write_personal_universe,
)
from quant_agent.paper import build_paper_order_plan, load_current_positions, write_paper_order_plan
from quant_agent.pipeline import run_research_backtest
from quant_agent.portfolio import build_target_positions
from quant_agent.server import run_dashboard_server

app = typer.Typer(help="US equity quant research agent.", no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """Research and backtest US equity strategies."""


_RATING_COLORS = {
    "Strong Buy": "bold green", "强烈看多": "bold green",
    "Mildly Bullish": "green", "偏多": "green",
    "Neutral": "yellow", "中性": "yellow",
    "Mildly Bearish": "red", "偏空": "red",
    "Strong Sell": "bold red", "强烈看空": "bold red",
}


def _resolve_language(lang: str | None) -> str:
    """语言优先级：--lang 显式 > quant-ai init 存的偏好(configs/profile.json) > 英文。"""
    if lang:
        return normalize_language(lang)
    profile = Path("configs/profile.json")
    if profile.exists():
        try:
            return normalize_language(json.loads(profile.read_text(encoding="utf-8")).get("language"))
        except Exception:  # noqa: BLE001 - 读不到就用默认
            pass
    return "en"


@app.command("analyze")
def analyze_command(
    symbols: list[str] = typer.Argument(None, help="股票代码，例如 AAPL MSFT NVDA"),
    file: Path | None = typer.Option(None, "--file", "-f", help="自选股文件：每行一个或逗号分隔，# 后为注释"),
    watchlist: bool = typer.Option(False, "--watchlist", "-w", help="分析个性化股票池（quant-ai init 生成的 my_universe.csv）"),
    watchlist_path: Path = typer.Option(Path("configs/my_universe.csv"), "--watchlist-path", help="个性化股票池 CSV 路径"),
    lang: str | None = typer.Option(None, "--lang", "-l", help="output language en/zh (default en; uses your init choice if set)"),
    config: Path | None = typer.Option(None, "--config", "-c", help="可选配置文件，用于启用 LLM 综述"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="可选：把分析写入目录（json+md）"),
    chart: bool = typer.Option(False, "--chart", help="额外导出价格+均线+RSI 的 PNG 图（需配合 --output-dir）"),
    json_only: bool = typer.Option(False, "--json", help="只输出 JSON，便于脚本调用"),
) -> None:
    """快速分析一只或多只美股，给出评级、理由和关键价位（零配置，秒级）。"""
    language = _resolve_language(lang)
    requested = list(symbols or [])
    if file is not None:
        requested.extend(read_symbols_file(file))
    if watchlist:
        if not watchlist_path.exists():
            console.print("[red]" + tr(
                f"Personalized watchlist {watchlist_path} not found — run quant-ai init first.",
                f"未找到个性化股票池 {watchlist_path}，请先运行 quant-ai init。",
                language,
            ) + "[/red]")
            raise typer.Exit(code=2)
        requested.extend(read_universe_symbols(watchlist_path))
    if not requested:
        console.print("[red]" + tr(
            "Provide at least one ticker, or use --file / --watchlist.",
            "请提供至少一个股票代码，或用 --file / --watchlist 指定股票来源。",
            language,
        ) + "[/red]")
        raise typer.Exit(code=2)

    llm_config = load_config(config).llm if config else None
    payload = analyze_symbols(requested, llm_config=llm_config, language=language)

    if json_only:
        serializable = {k: v for k, v in payload.items() if k != "_objects"}
        console.print_json(json.dumps(serializable, ensure_ascii=False, default=str))
        return

    for result in payload["_objects"]:
        if not result.ok:
            title = f"{result.symbol} {tr('— unable to analyze', '无法分析', language)}"
            console.print(Panel(f"[red]{result.error}[/red]", title=title, border_style="red"))
            continue
        _render_symbol(result, language)

    if payload.get("narrative"):
        console.print(Panel(payload["narrative"], title=tr("AI summary", "AI 综合解读", language), border_style="cyan"))

    console.print(f"[dim]{payload['disclaimer']}[/dim]")

    if output_dir is not None:
        paths = write_analysis(payload, output_dir, with_charts=chart)
        console.print(f"[green]{tr('Written', '已写入', language)}[/green] {paths['markdown']}")
        for png in paths.get("charts", []):
            console.print(f"[green]{tr('Chart', '图表', language)}[/green] {png}")
    elif chart:
        console.print("[yellow]" + tr(
            "--chart needs --output-dir (the chart is written there).",
            "--chart 需要配合 --output-dir 使用（图表会写入该目录）。",
            language,
        ) + "[/yellow]")


def _render_symbol(result, language: str = "en") -> None:
    lang = normalize_language(language)
    color = _RATING_COLORS.get(result.rating, "white")
    m = result.metrics

    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value:+.1%}"

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()
    table.add_row(tr("Last", "最新价", lang), f"{result.price}  ({result.data_date})")
    table.add_row(
        tr("Returns", "区间涨跌", lang),
        tr(
            f"1M {pct(m['ret_1m'])}  ·  3M {pct(m['ret_3m'])}  ·  6M {pct(m['ret_6m'])}  ·  1Y {pct(m['ret_1y'])}",
            f"1月 {pct(m['ret_1m'])}  ·  3月 {pct(m['ret_3m'])}  ·  6月 {pct(m['ret_6m'])}  ·  1年 {pct(m['ret_1y'])}",
            lang,
        ),
    )
    table.add_row(
        tr("RSI / Vol", "RSI / 波动", lang),
        tr(f"RSI {m['rsi_14']}  ·  ann. vol {pct(m['vol_annual'])}", f"RSI {m['rsi_14']}  ·  年化波动 {pct(m['vol_annual'])}", lang),
    )
    table.add_row(tr("MAs", "均线", lang), f"MA20 {m['ma20']}  ·  MA50 {m['ma50']}  ·  MA200 {m['ma200']}")
    table.add_row(tr("Note", "解读", lang), result.note)
    if result.reasons:
        table.add_row(tr("Reasons", "依据", lang), "\n".join(f"· {r}" for r in result.reasons))
    levels = result.levels
    table.add_row(
        tr("Key levels", "参考关注位", lang),
        tr(
            f"support {levels.get('reference_support')}  ·  stop {levels.get('reference_stop')}",
            f"支撑 {levels.get('reference_support')}  ·  参考止损 {levels.get('reference_stop')}",
            lang,
        ),
    )

    title = f"[{color}]{result.symbol} — {result.rating}[/{color}]  ({tr('confidence', '信心', lang)}: {result.confidence})"
    console.print(Panel(table, title=title, border_style=color))


@app.command("doctor")
def doctor_command() -> None:
    """环境自检：检查 Python 版本、关键依赖与行情数据源连通性。"""
    import sys

    table = Table(title="quant.ai 环境自检", show_header=True, header_style="bold")
    table.add_column("检查项")
    table.add_column("状态", justify="center")
    table.add_column("说明")

    ok_all = True

    def add(name: str, ok: bool, detail: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, mark, detail)

    py_ok = sys.version_info >= (3, 11)
    add("Python ≥ 3.11", py_ok, f"当前 {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # 必需依赖：缺失则自检失败；可选依赖：缺失仅提示，不影响整体结论。
    required_deps = ["pandas", "numpy", "yfinance", "yaml", "pydantic", "typer", "rich", "sklearn"]
    optional_deps = {"pyarrow": "读取 Parquet 数据", "matplotlib": "--chart 导出图表"}

    def check_dep(mod: str, *, required: bool, purpose: str = "") -> None:
        try:
            imported = __import__(mod)
            ver = getattr(imported, "__version__", "")
            add(f"依赖 {mod}", True, f"已安装 {ver}".strip())
        except Exception as exc:  # noqa: BLE001
            if required:
                add(f"依赖 {mod}", False, f"缺失：pip install -r requirements.txt（{type(exc).__name__}）")
            else:
                # 不调用 add，避免拉低 ok_all；仅作为可选项提示。
                table.add_row(f"依赖 {mod}", "[yellow]○[/yellow]", f"可选，缺失则无法{purpose}（pip install {mod}）")

    for mod in required_deps:
        check_dep(mod, required=True)
    for mod, purpose in optional_deps.items():
        check_dep(mod, required=False, purpose=purpose)

    # 行情数据源连通性：拉取 SPY 近几日数据
    net_ok = False
    net_detail = ""
    try:
        import yfinance as yf

        raw = yf.download("SPY", period="5d", auto_adjust=False, progress=False)
        net_ok = not raw.empty
        net_detail = f"成功获取 SPY 近 {len(raw)} 条数据" if net_ok else "返回空数据（可能被限流，请稍后重试）"
    except Exception as exc:  # noqa: BLE001
        net_detail = f"无法连接 Yahoo Finance：{type(exc).__name__}（检查网络/代理）"
    add("行情数据源连通", net_ok, net_detail)

    console.print(table)
    if ok_all:
        console.print("[green]全部正常，可以开始使用：quant-ai analyze AAPL[/green]")
    else:
        console.print("[yellow]存在未通过项，请按上表说明处理后重试。[/yellow]")
        raise typer.Exit(code=1)


@app.command("run-backtest")
def run_backtest_command(config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c")) -> None:
    app_config = load_config(config)
    result = run_research_backtest(app_config)
    metrics = result["metrics"]
    console.print("[bold green]Backtest complete[/bold green]")
    console.print(f"Output: {app_config.report.output_dir}")
    console.print(f"Total return: {metrics['total_return']:.2%}")
    console.print(f"Sharpe: {metrics['sharpe']:.2f}")
    console.print(f"Max drawdown: {metrics['max_drawdown']:.2%}")


@app.command("write-recommended-config")
def write_recommended_config_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    weights: Path = typer.Option(Path("reports/latest/recommended_signal_weights.json"), "--weights", "-w"),
    output: Path = typer.Option(Path("configs/recommended.yaml"), "--output", "-o"),
    report_output_dir: str = typer.Option("reports/recommended", "--report-output-dir"),
) -> None:
    applied = write_recommended_config(config, weights, output, report_output_dir)
    console.print("[bold green]Recommended config written[/bold green]")
    console.print(f"Output: {output}")
    console.print(f"Signal weights: {applied}")


@app.command("compare-reports")
def compare_reports_command(
    reports: list[Path] = typer.Argument(..., help="Report directories containing audit.json"),
    output_dir: Path = typer.Option(Path("reports/comparison"), "--output-dir", "-o"),
) -> None:
    comparison = write_strategy_comparison(reports, output_dir)
    console.print("[bold green]Comparison written[/bold green]")
    console.print(f"Output: {output_dir}")
    console.print(comparison[["name", "overall_total_return", "overall_sharpe", "test_total_return", "test_sharpe"]])


@app.command("data-quality")
def data_quality_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    output_dir: Path = typer.Option(Path("reports/data_quality"), "--output-dir", "-o"),
) -> None:
    app_config = load_config(config)
    prices = load_prices(app_config.data)
    report = build_data_quality_report(prices, app_config.data.universe)
    write_data_quality_report(report, output_dir)
    console.print("[bold green]Data quality report written[/bold green]")
    console.print(f"Output: {output_dir}")
    console.print(report["summary"])


@app.command("plan-paper-orders")
def plan_paper_orders_command(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    current_positions: Path | None = typer.Option(None, "--current-positions"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
) -> None:
    app_config = load_config(config)
    prices = load_prices(app_config.data)
    signals = build_signals(prices, app_config.strategy.signal_weights)
    signals, _ = apply_ml_ranking_signal(signals, app_config)
    targets = build_target_positions(signals, app_config.strategy, app_config.risk)
    current = load_current_positions(current_positions)
    plan = build_paper_order_plan(targets, prices, app_config.paper_trading, current)
    destination = output_dir or app_config.paper_trading.output_dir
    write_paper_order_plan(plan, destination)
    console.print("[bold green]Paper order plan written[/bold green]")
    console.print(f"Output: {destination}")
    console.print(plan.get("checks", []))


@app.command("market-report")
def market_report_command(
    config: Path = typer.Option(Path("configs/full_roadmap.yaml"), "--config", "-c"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
) -> None:
    """Generate a daily US market intelligence report (news + quant)."""
    app_config = load_config(config)
    report = build_market_report(app_config)
    destination = output_dir or app_config.market_intel.output_dir
    paths = write_market_report(report, destination)
    console.print("[bold green]Market report written[/bold green]")
    console.print(f"Output: {destination}")
    console.print(f"Data status: {report['data_status']}, as of {report['as_of_date']}")
    console.print(f"Buy candidates: {len(report['buy_candidates'])}, high risk: {len(report['high_risk'])}, news: {len(report['news'])}")
    console.print(f"HTML: {paths['html']}")


@app.command("write-dashboard")
def write_dashboard_command(
    report_dir: Path = typer.Argument(Path("reports/latest"), help="Report directory containing audit.json"),
    output: Path = typer.Option(Path("reports/latest/dashboard.html"), "--output", "-o"),
) -> None:
    write_dashboard(report_dir, output)
    console.print("[bold green]Dashboard written[/bold green]")
    console.print(f"Output: {output}")


@app.command("serve-dashboard")
def serve_dashboard_command(
    config: Path = typer.Option(Path("configs/full_roadmap.yaml"), "--config", "-c"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port", "-p"),
) -> None:
    """Start the local dashboard and operations service."""
    run_dashboard_server(config, host=host, port=port)


_SOURCE_META = {
    "picked": (("Picked", "自选公司"), "bold cyan"),
    "sector": (("Sector", "板块"), "cyan"),
    "discovery": (("Discovery", "发现推荐"), "magenta"),
}
_RISK_OPTIONS = [
    ("long_term", "Long-term", "长线"),
    ("swing", "Swing", "波段"),
    ("short_term", "Short-term", "短线"),
    ("defensive", "Defensive", "防守"),
    ("aggressive", "Aggressive", "激进"),
]


def _source_label(source: str, lang: str) -> tuple[str, str]:
    (en, zh), color = _SOURCE_META.get(source, ((source, source), "white"))
    return tr(en, zh, lang), color


def _prompt_language() -> str:
    return normalize_language(Prompt.ask("Language / 语言", choices=["en", "zh"], default="en"))


def _prompt_sectors(catalog, lang: str) -> list[str]:
    sectors = catalog_sectors(catalog)
    table = Table(title=tr("Sectors", "可选板块", lang), show_header=True, header_style="bold")
    table.add_column("#", justify="right")
    table.add_column(tr("Sector", "板块", lang))
    table.add_column(tr("Examples", "代表股（示例）", lang))
    for i, sector in enumerate(sectors, 1):
        members = catalog[catalog["sector"] == sector]["symbol"].head(6).tolist()
        table.add_row(str(i), sector, ", ".join(members))
    console.print(table)
    raw = Prompt.ask(tr("Sector numbers you care about (comma-separated, optional)", "输入感兴趣板块的编号（逗号分隔，可留空）", lang), default="")
    chosen: list[str] = []
    for token in raw.replace("，", ",").split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(sectors):
            sector = sectors[int(token) - 1]
            if sector not in chosen:
                chosen.append(sector)
    return chosen


def _prompt_risk(lang: str) -> str:
    labels = [f"{i + 1}.{tr(en, zh, lang)}" for i, (_, en, zh) in enumerate(_RISK_OPTIONS)]
    console.print(f"[dim]{tr('Risk preference', '风险偏好', lang)}: {' / '.join(labels)}[/dim]")
    raw = Prompt.ask(tr("Choose risk (number)", "选择风险偏好（编号）", lang), default="1")
    idx = int(raw) - 1 if raw.strip().isdigit() and 1 <= int(raw) <= len(_RISK_OPTIONS) else 0
    return _RISK_OPTIONS[idx][0]


def _render_universe_preview(frame, lang: str) -> None:
    if frame.empty:
        console.print("[yellow]" + tr("Nothing was selected.", "没有任何标的被选中。", lang) + "[/yellow]")
        return
    table = Table(
        title=tr(f"Personalized watchlist preview ({len(frame)} names)", f"个性化股票池预览（共 {len(frame)} 只）", lang),
        show_header=True,
        header_style="bold",
    )
    table.add_column(tr("Symbol", "代码", lang))
    table.add_column(tr("Name", "名称", lang))
    table.add_column(tr("Sector", "板块", lang))
    table.add_column(tr("Source", "来源", lang))
    for _, row in frame.iterrows():
        label, color = _source_label(row["source"], lang)
        table.add_row(row["symbol"], row["name"], row["sector"], f"[{color}]{label}[/{color}]")
    console.print(table)
    counts = frame["source"].value_counts().to_dict()
    summary = "  ·  ".join(
        f"{_source_label(src, lang)[0]} {counts.get(src, 0)}"
        for src in ("picked", "sector", "discovery")
        if counts.get(src)
    )
    console.print(f"[dim]{tr('Composition', '构成', lang)}: {summary}[/dim]")


def _write_and_report(frame, profile, configs_dir: Path, base_config: Path, status: str) -> None:
    lang = normalize_language(profile.language)
    msg = discovery_status_message(status, lang)
    if msg:
        console.print(f"[yellow]{msg}[/yellow]")
    paths = write_personal_universe(frame, profile, configs_dir, base_config)
    console.print("[bold green]" + tr("Personalized watchlist created", "个性化股票池已生成", lang) + "[/bold green]")
    console.print(f"[green]{tr('Watchlist', '股票池', lang)}[/green] {paths['universe']}")
    console.print(f"[green]{tr('Config', '配置', lang)}[/green] {paths['config']}")
    console.print(f"[green]{tr('Profile', '偏好', lang)}[/green] {paths['profile']}")
    console.print("\n" + tr("Next steps:", "下一步可以：", lang))
    console.print(f"  · [cyan]quant-ai analyze --watchlist[/cyan]   {tr('analyze your watchlist', '分析你的个性化股票池', lang)}")
    console.print(f"  · [cyan]quant-ai market-report --config {paths['config']}[/cyan]   {tr('daily market brief', '生成每日市场简报', lang)}")
    console.print(f"  · [cyan]quant-ai refresh-universe[/cyan]   {tr('refresh discovery picks', '行情更新后刷新「发现池」推荐', lang)}")


@app.command("init")
def init_command(
    catalog_path: Path = typer.Option(Path("configs/catalog.csv"), "--catalog", help="候选股票目录 CSV"),
    configs_dir: Path = typer.Option(Path("configs"), "--configs-dir", help="生成文件写入目录"),
    base_config: Path = typer.Option(Path("configs/default.yaml"), "--base-config", help="继承的基础配置"),
    sectors: list[str] | None = typer.Option(None, "--sector", help="非交互：指定板块（可多次）"),
    tickers: list[str] | None = typer.Option(None, "--ticker", help="非交互：指定关注的股票代码（可多次/逗号分隔）"),
    risk: str | None = typer.Option(None, "--risk", help="risk: long_term/swing/short_term/defensive/aggressive"),
    benchmark: str = typer.Option("SPY", "--benchmark", help="基准代码"),
    lang: str | None = typer.Option(None, "--lang", "-l", help="language en/zh (default en)"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="不弹问答，直接用上面的参数生成"),
    no_discovery: bool = typer.Option(False, "--no-discovery", help="跳过「发现池」（不下载行情，仅写自选部分）"),
) -> None:
    """First-run setup: a few questions build a 2/3 self-picked + 1/3 discovered watchlist."""
    if not catalog_path.exists():
        console.print(f"[red]Catalog not found: {catalog_path}[/red]")
        raise typer.Exit(code=2)
    catalog = load_catalog(catalog_path)

    if non_interactive:
        language = normalize_language(lang)
        profile = UserProfile(
            sectors=list(sectors or []),
            tickers=_clean_symbols(list(tickers or [])),
            risk=risk or "long_term",
            benchmark=benchmark.upper(),
            language=language,
        )
        if not profile.sectors and not profile.tickers:
            console.print("[red]--non-interactive needs at least --sector or --ticker.[/red]")
            raise typer.Exit(code=2)
    else:
        language = normalize_language(lang) if lang else _prompt_language()
        console.print(
            Panel(
                tr(
                    "Welcome to quant.ai! A few questions build a personalized watchlist:\n"
                    "2/3 from companies and sectors you pick, 1/3 the engine discovers from the wider market.",
                    "欢迎使用 quant.ai！回答几个问题，帮你搭一份个性化股票池：\n"
                    "2/3 来自你自选的公司和板块，1/3 由系统在全市场里挑你没选到的强势标的。",
                    language,
                ),
                title=tr("First-run setup", "首次使用引导", language),
                border_style="cyan",
            )
        )
        chosen_sectors = list(sectors) if sectors else _prompt_sectors(catalog, language)
        raw_ticker_input = Prompt.ask(tr("Extra tickers to follow (comma-separated, optional)", "额外关注的股票代码（逗号分隔，可留空）", language), default="")
        chosen_tickers = _clean_symbols(list(tickers) if tickers else [raw_ticker_input])
        chosen_risk = risk or _prompt_risk(language)
        profile = UserProfile(
            sectors=chosen_sectors,
            tickers=chosen_tickers,
            risk=chosen_risk,
            benchmark=benchmark.upper(),
            language=language,
        )
        if not profile.sectors and not profile.tickers:
            console.print("[red]" + tr("Pick at least one sector or enter one ticker.", "至少选择一个板块或输入一个股票代码。", language) + "[/red]")
            raise typer.Exit(code=2)

    if not no_discovery:
        console.print("[dim]" + tr("Evaluating discovery picks (may download prices)…", "正在评估「发现池」（可能需要下载行情，请稍候）…", language) + "[/dim]")
    frame, status = build_personal_universe(profile, catalog, enable_discovery=not no_discovery)
    _render_universe_preview(frame, language)
    _write_and_report(frame, profile, configs_dir, base_config, status)


@app.command("refresh-universe")
def refresh_universe_command(
    profile_path: Path = typer.Option(Path("configs/profile.json"), "--profile", help="quant-ai init 生成的偏好文件"),
    catalog_path: Path = typer.Option(Path("configs/catalog.csv"), "--catalog"),
    configs_dir: Path = typer.Option(Path("configs"), "--configs-dir"),
    base_config: Path = typer.Option(Path("configs/default.yaml"), "--base-config"),
) -> None:
    """Recompute the 1/3 discovery picks from your saved profile (your 2/3 stays)."""
    if not profile_path.exists():
        console.print(f"[red]Profile not found: {profile_path} — run quant-ai init first.[/red]")
        raise typer.Exit(code=2)
    profile = load_profile(profile_path)
    catalog = load_catalog(catalog_path)
    console.print("[dim]" + tr("Refreshing discovery picks…", "正在刷新「发现池」…", normalize_language(profile.language)) + "[/dim]")
    frame, status = build_personal_universe(profile, catalog)
    _render_universe_preview(frame, normalize_language(profile.language))
    _write_and_report(frame, profile, configs_dir, base_config, status)
