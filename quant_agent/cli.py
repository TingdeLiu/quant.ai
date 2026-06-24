from __future__ import annotations

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
from quant_agent.market_intel import build_market_report, write_market_report
from quant_agent.ml import apply_ml_ranking_signal
from quant_agent.onboarding import (
    DISCOVERY_STATUS_MESSAGES,
    RISK_TO_PROFILE,
    UserProfile,
    build_personal_universe,
    catalog_sectors,
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
    "强烈看多": "bold green",
    "偏多": "green",
    "中性": "yellow",
    "偏空": "red",
    "强烈看空": "bold red",
}


@app.command("analyze")
def analyze_command(
    symbols: list[str] = typer.Argument(None, help="股票代码，例如 AAPL MSFT NVDA"),
    file: Path | None = typer.Option(None, "--file", "-f", help="自选股文件：每行一个或逗号分隔，# 后为注释"),
    watchlist: bool = typer.Option(False, "--watchlist", "-w", help="分析个性化股票池（quant-ai init 生成的 my_universe.csv）"),
    watchlist_path: Path = typer.Option(Path("configs/my_universe.csv"), "--watchlist-path", help="个性化股票池 CSV 路径"),
    config: Path | None = typer.Option(None, "--config", "-c", help="可选配置文件，用于启用 LLM 综述"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="可选：把分析写入目录（json+md）"),
    chart: bool = typer.Option(False, "--chart", help="额外导出价格+均线+RSI 的 PNG 图（需配合 --output-dir）"),
    json_only: bool = typer.Option(False, "--json", help="只输出 JSON，便于脚本调用"),
) -> None:
    """快速分析一只或多只美股，给出评级、理由和关键价位（零配置，秒级）。"""
    requested = list(symbols or [])
    if file is not None:
        requested.extend(read_symbols_file(file))
    if watchlist:
        if not watchlist_path.exists():
            console.print(f"[red]未找到个性化股票池 {watchlist_path}，请先运行 quant-ai init。[/red]")
            raise typer.Exit(code=2)
        requested.extend(read_universe_symbols(watchlist_path))
    if not requested:
        console.print("[red]请提供至少一个股票代码，或用 --file / --watchlist 指定股票来源。[/red]")
        raise typer.Exit(code=2)

    llm_config = load_config(config).llm if config else None
    payload = analyze_symbols(requested, llm_config=llm_config)

    if json_only:
        import json as _json

        serializable = {k: v for k, v in payload.items() if k != "_objects"}
        console.print_json(_json.dumps(serializable, ensure_ascii=False, default=str))
        return

    for result in payload["_objects"]:
        if not result.ok:
            console.print(Panel(f"[red]{result.error}[/red]", title=f"{result.symbol} 无法分析", border_style="red"))
            continue
        _render_symbol(result)

    if payload.get("narrative"):
        console.print(Panel(payload["narrative"], title="AI 综合解读", border_style="cyan"))

    console.print(f"[dim]{payload['disclaimer']}[/dim]")

    if output_dir is not None:
        paths = write_analysis(payload, output_dir, with_charts=chart)
        console.print(f"[green]已写入[/green] {paths['markdown']}")
        for png in paths.get("charts", []):
            console.print(f"[green]图表[/green] {png}")
    elif chart:
        console.print("[yellow]--chart 需要配合 --output-dir 使用（图表会写入该目录）。[/yellow]")


def _render_symbol(result) -> None:
    color = _RATING_COLORS.get(result.rating, "white")
    m = result.metrics

    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value:+.1%}"

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()
    table.add_row("最新价", f"{result.price}  （{result.data_date}）")
    table.add_row("区间涨跌", f"1月 {pct(m['ret_1m'])}  ·  3月 {pct(m['ret_3m'])}  ·  6月 {pct(m['ret_6m'])}  ·  1年 {pct(m['ret_1y'])}")
    table.add_row("RSI / 波动", f"RSI {m['rsi_14']}  ·  年化波动 {pct(m['vol_annual'])}")
    table.add_row("均线", f"MA20 {m['ma20']}  ·  MA50 {m['ma50']}  ·  MA200 {m['ma200']}")
    table.add_row("解读", result.note)
    if result.reasons:
        table.add_row("依据", "\n".join(f"· {r}" for r in result.reasons))
    levels = result.levels
    table.add_row("参考关注位", f"支撑 {levels.get('reference_support')}  ·  参考止损 {levels.get('reference_stop')}")

    title = f"[{color}]{result.symbol} — {result.rating}[/{color}]  （信心：{result.confidence}）"
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


_SOURCE_LABELS = {"picked": ("自选公司", "bold cyan"), "sector": ("板块", "cyan"), "discovery": ("发现推荐", "magenta")}


def _prompt_sectors(catalog) -> list[str]:
    sectors = catalog_sectors(catalog)
    table = Table(title="可选板块", show_header=True, header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("板块")
    table.add_column("代表股（示例）")
    for i, sector in enumerate(sectors, 1):
        members = catalog[catalog["sector"] == sector]["symbol"].head(6).tolist()
        table.add_row(str(i), sector, ", ".join(members))
    console.print(table)
    raw = Prompt.ask("输入感兴趣板块的编号（逗号分隔，可留空）", default="")
    chosen: list[str] = []
    for token in raw.replace("，", ",").split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(sectors):
            sector = sectors[int(token) - 1]
            if sector not in chosen:
                chosen.append(sector)
    return chosen


def _prompt_risk() -> str:
    options = list(RISK_TO_PROFILE.keys())
    console.print(f"[dim]风险偏好可选：{' / '.join(options)}[/dim]")
    return Prompt.ask("选择风险偏好", choices=options, default=options[0])


def _render_universe_preview(frame) -> None:
    if frame.empty:
        console.print("[yellow]没有任何标的被选中。[/yellow]")
        return
    table = Table(title=f"个性化股票池预览（共 {len(frame)} 只）", show_header=True, header_style="bold")
    table.add_column("代码")
    table.add_column("名称")
    table.add_column("板块")
    table.add_column("来源")
    for _, row in frame.iterrows():
        label, color = _SOURCE_LABELS.get(row["source"], (row["source"], "white"))
        table.add_row(row["symbol"], row["name"], row["sector"], f"[{color}]{label}[/{color}]")
    console.print(table)
    counts = frame["source"].value_counts().to_dict()
    summary = "  ·  ".join(
        f"{_SOURCE_LABELS.get(src, (src, ''))[0]} {counts.get(src, 0)}"
        for src in ("picked", "sector", "discovery")
        if counts.get(src)
    )
    console.print(f"[dim]构成：{summary}[/dim]")


def _write_and_report(frame, profile, configs_dir: Path, base_config: Path, status: str) -> None:
    if status != "ok" and DISCOVERY_STATUS_MESSAGES.get(status):
        console.print(f"[yellow]{DISCOVERY_STATUS_MESSAGES[status]}[/yellow]")
    paths = write_personal_universe(frame, profile, configs_dir, base_config)
    console.print("[bold green]个性化股票池已生成[/bold green]")
    console.print(f"[green]股票池[/green] {paths['universe']}")
    console.print(f"[green]配置[/green] {paths['config']}")
    console.print(f"[green]偏好[/green] {paths['profile']}")
    console.print("\n下一步可以：")
    console.print("  · [cyan]quant-ai analyze --watchlist[/cyan]   分析你的个性化股票池")
    console.print(f"  · [cyan]quant-ai market-report --config {paths['config']}[/cyan]   生成每日市场简报")
    console.print("  · [cyan]quant-ai refresh-universe[/cyan]   行情更新后刷新「发现池」推荐")


@app.command("init")
def init_command(
    catalog_path: Path = typer.Option(Path("configs/catalog.csv"), "--catalog", help="候选股票目录 CSV"),
    configs_dir: Path = typer.Option(Path("configs"), "--configs-dir", help="生成文件写入目录"),
    base_config: Path = typer.Option(Path("configs/default.yaml"), "--base-config", help="继承的基础配置"),
    sectors: list[str] | None = typer.Option(None, "--sector", help="非交互：指定板块（可多次）"),
    tickers: list[str] | None = typer.Option(None, "--ticker", help="非交互：指定关注的股票代码（可多次/逗号分隔）"),
    risk: str | None = typer.Option(None, "--risk", help="风险偏好：长线/波段/短线/防守/激进"),
    benchmark: str = typer.Option("SPY", "--benchmark", help="基准代码"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="不弹问答，直接用上面的参数生成"),
    no_discovery: bool = typer.Option(False, "--no-discovery", help="跳过「发现池」（不下载行情，仅写自选部分）"),
) -> None:
    """首次使用引导：问几个问题，生成 2/3 自选 + 1/3 发现的个性化股票池。"""
    if not catalog_path.exists():
        console.print(f"[red]未找到候选目录 {catalog_path}。[/red]")
        raise typer.Exit(code=2)
    catalog = load_catalog(catalog_path)

    if non_interactive:
        profile = UserProfile(
            sectors=list(sectors or []),
            tickers=_clean_symbols(list(tickers or [])),
            risk=risk or "长线",
            benchmark=benchmark.upper(),
        )
        if not profile.sectors and not profile.tickers:
            console.print("[red]--non-interactive 模式至少需要 --sector 或 --ticker。[/red]")
            raise typer.Exit(code=2)
    else:
        console.print(
            Panel(
                "欢迎使用 quant.ai！回答几个问题，帮你搭一份个性化股票池：\n"
                "2/3 来自你自选的公司和板块，1/3 由系统在全市场里挑你没选到的强势标的。",
                title="首次使用引导",
                border_style="cyan",
            )
        )
        chosen_sectors = list(sectors) if sectors else _prompt_sectors(catalog)
        raw_ticker_input = Prompt.ask("额外关注的股票代码（逗号分隔，可留空）", default="")
        chosen_tickers = _clean_symbols(list(tickers) if tickers else [raw_ticker_input])
        chosen_risk = risk or _prompt_risk()
        profile = UserProfile(
            sectors=chosen_sectors,
            tickers=chosen_tickers,
            risk=chosen_risk,
            benchmark=benchmark.upper(),
        )
        if not profile.sectors and not profile.tickers:
            console.print("[red]至少选择一个板块或输入一个股票代码。[/red]")
            raise typer.Exit(code=2)

    if not no_discovery:
        console.print("[dim]正在评估「发现池」（可能需要下载行情，请稍候）…[/dim]")
    frame, status = build_personal_universe(profile, catalog, enable_discovery=not no_discovery)
    _render_universe_preview(frame)
    _write_and_report(frame, profile, configs_dir, base_config, status)


@app.command("refresh-universe")
def refresh_universe_command(
    profile_path: Path = typer.Option(Path("configs/profile.json"), "--profile", help="quant-ai init 生成的偏好文件"),
    catalog_path: Path = typer.Option(Path("configs/catalog.csv"), "--catalog"),
    configs_dir: Path = typer.Option(Path("configs"), "--configs-dir"),
    base_config: Path = typer.Option(Path("configs/default.yaml"), "--base-config"),
) -> None:
    """用已保存的偏好重新计算「发现池」1/3（市场会变），自选 2/3 不变。"""
    if not profile_path.exists():
        console.print(f"[red]未找到偏好文件 {profile_path}，请先运行 quant-ai init。[/red]")
        raise typer.Exit(code=2)
    profile = load_profile(profile_path)
    catalog = load_catalog(catalog_path)
    console.print("[dim]正在刷新「发现池」（下载/读取行情）…[/dim]")
    frame, status = build_personal_universe(profile, catalog)
    _render_universe_preview(frame)
    _write_and_report(frame, profile, configs_dir, base_config, status)
