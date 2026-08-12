"""Local operations console — one page, four tabs.

把原来散在 `/console`（运维控制台）和 `/dashboard`（回测诊断）两个页面、各带一套 2015 蓝白
CSS 和一份 i18n 字典的东西合并成一页，并直接复用每日报告的视觉（`market_intel.report_css`）
与标签页机制（`market_intel.build_tabs`），不再各写一套。

标签页：报告 / 行情 / 回测 / 运行。切换是纯 CSS；只有「运行」页需要脚本（轮询状态、触发
任务），这台服务本来就跑在本机，脚本可用。

Research only：这里能触发的只有回测和报告生成，不存在下单、审批或券商链路。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_agent.config import AppConfig
from quant_agent.i18n import normalize_language, tr
from quant_agent.market_intel import build_tabs, render_report_body, report_css

_METRIC_KEYS = ("total_return", "cagr", "sharpe", "sortino", "max_drawdown", "alpha", "information_ratio")


def _esc(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return _esc(value)


def _table(frame: pd.DataFrame, lang: str) -> str:
    if frame.empty:
        return f'<p class="cs-empty">{tr("No data.", "暂无数据。", lang)}</p>'
    head = "".join(f"<th>{_esc(c)}</th>" for c in frame.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in row) + "</tr>"
        for row in frame.itertuples(index=False, name=None)
    )
    return f'<div class="cs-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _section(title: str, body: str) -> str:
    return f'<section><div class="sec-head"><h2>{_esc(title)}</h2></div>{body}</section>'


def _empty(text: str) -> str:
    return f'<p class="cs-empty">{_esc(text)}</p>'


# --------------------------------------------------------------------------- 报告
def _tab_report(report: dict[str, Any], lang: str) -> list[str]:
    if not report:
        return [
            _section(
                tr("Daily report", "每日报告", lang),
                _empty(tr(
                    'No report yet — hit "Daily market report" on the Ops tab.',
                    "还没有报告 —— 到「运行」页点「生成今日报告」。",
                    lang,
                )),
            )
        ]
    # 报告自带章节编号和自己那层标签页（qa 组），外层控制台用 cs 组，两层互不干扰。
    return [render_report_body(report)]


# --------------------------------------------------------------------------- 行情
def _tab_markets(data: dict[str, Any], lang: str) -> list[str]:
    tickers = data.get("TICKERS") or {}
    if not tickers:
        return [
            _section(
                tr("Markets", "行情", lang),
                _empty(tr(
                    "No market data — run the pipeline or check the data source.",
                    "暂无行情数据 —— 请先跑流水线或检查数据源。",
                    lang,
                )),
            )
        ]
    blocks: list[str] = []
    if data.get("brief"):
        blocks.append(f'<div class="cs-brief">{_esc(data["brief"])}</div>')
    rows = []
    for sym, t in tickers.items():
        chg = t.get("chg")
        cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"
        sign = "+" if isinstance(chg, (int, float)) and chg >= 0 else ""
        rec = (t.get("recommendation") or {}).get("stance") or t.get("ratingLabel") or t.get("rating") or ""
        rows.append(
            f'<tr><td class="sym">{_esc(sym)}</td><td>{_esc(t.get("name", ""))}</td>'
            f'<td class="num">${_fmt_price(t.get("price"))}</td>'
            f'<td class="num {cls}">{sign}{_esc(chg)}%</td>'
            f"<td>{_esc(rec)}</td><td>{_esc(t.get('summary', ''))}</td></tr>"
        )
    head = tr(
        "Symbol|Name|Price|Today|Read|Summary", "代码|名称|价格|今日|研究读数|摘要", lang
    ).split("|")
    blocks.append(
        '<div class="cs-scroll"><table><thead><tr>'
        + "".join(f"<th>{_esc(h)}</th>" for h in head)
        + f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )
    as_of = data.get("as_of")
    hint = f'<p class="cs-note">{tr("Data as of", "数据截止", lang)} {_esc(as_of)}</p>' if as_of else ""
    return [_section(tr("Markets", "行情", lang), "".join(blocks) + hint)]


def _fmt_price(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


# --------------------------------------------------------------------------- 回测
def _tab_backtest(report_dir: Path, lang: str) -> list[str]:
    audit = _load_json(report_dir / "audit.json")
    if not audit:
        return [
            _section(
                tr("Backtest", "回测", lang),
                _empty(tr(
                    'No backtest yet — hit "Run backtest" on the Ops tab.',
                    "还没有回测结果 —— 到「运行」页点「运行回测」。",
                    lang,
                )),
            )
        ]
    alerts = _load_json(report_dir / "alerts.json")
    metrics = audit.get("metrics", {})
    cards = "".join(
        f'<div class="cs-card"><span>{_esc(k)}</span><strong>{_fmt(metrics[k])}</strong></div>'
        for k in _METRIC_KEYS
        if k in metrics
    )
    summary = alerts.get("summary", {})
    cards += (
        f'<div class="cs-card"><span>alerts</span>'
        f'<strong>{_esc(summary.get("highest_severity", "none"))} ({int(summary.get("total", 0) or 0)})</strong></div>'
    )
    out = [_section(tr("Key metrics", "关键指标", lang), f'<div class="cs-cards">{cards}</div>')]
    for title_en, title_zh, frame in (
        ("Alerts", "告警", pd.DataFrame(alerts.get("alerts", []))),
        ("Period metrics", "分段指标", pd.DataFrame(audit.get("period_metrics", []))),
        ("Risk checks", "风控检查", pd.DataFrame(audit.get("risk_checks", []))),
        ("Data quality", "数据质量", pd.DataFrame(_load_json(report_dir / "data_quality.json").get("issues", []))),
        ("Research candidates", "研究候选", _load_csv(report_dir / "recommendations.csv")),
        ("Equity curve (tail)", "权益曲线（末段）", _load_csv(report_dir / "equity_curve.csv").tail(20)),
        ("Latest positions", "最新持仓", _load_csv(report_dir / "positions.csv").tail(50)),
        ("Recent trades", "近期交易", _load_csv(report_dir / "trades.csv").tail(50)),
        ("Proposed orders", "纸面订单计划", _load_csv(report_dir / "proposed_orders.csv")),
    ):
        out.append(_section(tr(title_en, title_zh, lang), _table(frame, lang)))
    return out


# --------------------------------------------------------------------------- 运行
def _tab_ops(config: AppConfig, status: dict[str, Any], history: list[dict[str, Any]], lang: str) -> list[str]:
    schedule = tr("enabled", "启用", lang) if config.schedule.enabled else tr("disabled", "关闭", lang)
    cards = "".join(
        f'<div class="cs-card"><span>{_esc(label)}</span><strong id="{cid}">{_esc(value)}</strong></div>'
        for label, value, cid in (
            (tr("Status", "状态", lang), status.get("last_status", "unknown"), "cs-status"),
            (tr("Running", "运行中", lang), status.get("running", False), "cs-running"),
            (tr("Last run", "最近运行", lang), status.get("last_run_id", "—") or "—", "cs-runid"),
            (tr("Schedule", "定时", lang), f"{schedule} / {config.schedule.interval_minutes} min", "cs-sched"),
            (tr("Report dir", "报告目录", lang), config.report.output_dir, "cs-dir"),
            (tr("Config", "配置", lang), status.get("config", ""), "cs-conf"),
        )
    )
    token_row = (
        f'<input id="cs-token" type="password" autocomplete="off" placeholder="API token">'
        f'<button class="ghost" onclick="csSaveToken()">{tr("Save token", "保存 Token", lang)}</button>'
        if config.dashboard_security.enabled
        else ""
    )
    actions = (
        f'<div class="cs-actions">{token_row}'
        f'<button id="cs-run" onclick="csRun()">{tr("Run backtest", "运行回测", lang)}</button>'
        f'<button id="cs-report" onclick="csReport()">{tr("Daily market report", "生成今日报告", lang)}</button>'
        f'<a class="ghost" href="/market-report" target="_blank">{tr("Open report file", "打开报告文件", lang)}</a>'
        f"</div>"
        f'<p class="cs-msg" id="cs-msg"></p>'
    )
    return [
        _section(tr("Service", "服务状态", lang), f'<div class="cs-cards">{cards}</div>{actions}'),
        _section(tr("Run history", "运行历史", lang), _runs_table(history, lang)),
        _section(tr("Report files", "报告文件", lang), '<div id="cs-files"></div>'),
    ]


def _runs_table(history: list[dict[str, Any]], lang: str) -> str:
    if not history:
        return f'<p class="cs-empty">{tr("No runs recorded.", "暂无运行记录。", lang)}</p>'
    head = tr("Run ID|Status|Started|Finished|Alerts|Report", "运行 ID|状态|开始|结束|告警|报告", lang).split("|")
    rows = "".join(
        "<tr>"
        f'<td class="sym">{_esc(r.get("run_id", ""))}</td>'
        f'<td>{_esc(r.get("status", ""))}</td>'
        f'<td class="num">{_esc(r.get("started_at", ""))}</td>'
        f'<td class="num">{_esc(r.get("finished_at", ""))}</td>'
        f'<td>{_esc((r.get("alert_summary") or {}).get("highest_severity", ""))}</td>'
        f'<td><a href="/runs/{_esc(r.get("run_id", ""))}/dashboard">{tr("open", "查看", lang)}</a></td>'
        "</tr>"
        for r in history
    )
    return (
        '<div class="cs-scroll"><table><thead><tr>'
        + "".join(f"<th>{_esc(h)}</th>" for h in head)
        + f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


_CSS = """
.qa-report .cs-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.qa-report .cs-card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 13px 15px; min-width: 0; }
.qa-report .cs-card span { display: block; font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
.qa-report .cs-card strong { font-family: var(--mono); font-size: 15px; font-weight: 600; color: var(--ink); word-break: break-all; }
.qa-report .cs-scroll { overflow: auto; max-height: 420px; border: 1px solid var(--line); border-radius: 12px; background: var(--card); }
.qa-report .cs-scroll table { font-size: 13px; }
.qa-report .cs-scroll thead th { position: sticky; top: 0; z-index: 1; }
.qa-report .cs-empty { color: var(--muted); font-size: 13.5px; padding: 16px 18px; border: 1px dashed var(--line-2); border-radius: 12px; background: var(--card); }
.qa-report .cs-note { font-family: var(--mono); font-size: 11px; color: var(--faint); margin: 8px 2px 0; }
.qa-report .cs-note a { color: var(--orange-deep); }
.qa-report .cs-brief { background: var(--sand); border-left: 3px solid var(--orange); border-radius: 0 12px 12px 0; padding: 14px 18px; margin-bottom: 14px; font-size: 14.5px; line-height: 1.7; }
.qa-report .cs-actions { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; margin-top: 16px; }
.qa-report .cs-actions button, .qa-report .cs-actions a.ghost { font-family: var(--head); font-size: 13px; font-weight: 600; padding: 9px 16px; border-radius: 10px; border: 1px solid var(--orange); background: var(--orange); color: #fff; cursor: pointer; text-decoration: none; }
.qa-report .cs-actions .ghost { background: transparent; color: var(--orange-deep); }
.qa-report .cs-actions button:disabled { opacity: 0.45; cursor: progress; }
.qa-report .cs-actions input { font-family: var(--mono); font-size: 12.5px; padding: 9px 12px; border: 1px solid var(--line-2); border-radius: 10px; background: var(--card); color: var(--ink); min-width: 220px; }
.qa-report .cs-msg { font-family: var(--mono); font-size: 11.5px; color: var(--muted); margin: 10px 2px 0; min-height: 1em; }
.qa-report .cs-msg a { color: var(--orange-deep); }
.qa-report .num.up { color: var(--green-deep); } .qa-report .num.down { color: var(--down-deep); }
.qa-report .cs-foot { margin-top: 40px; font-family: var(--mono); font-size: 11px; color: var(--faint); }
"""

# 「运行」页的脚本：轮询状态、触发回测/报告、列报告文件。只有这一页需要它，其余标签页
# 纯 CSS 就能切换；这台服务跑在本机，脚本不受 artifact 那套 CSP 约束。
_JS = """
<script>
var CS_AUTH = __AUTH__;
function csTokenInput(){ return document.getElementById("cs-token"); }
function csToken(){ var i = csTokenInput(); return (i && i.value) || localStorage.getItem("quantAgentApiToken") || ""; }
function csSaveToken(){ localStorage.setItem("quantAgentApiToken", csToken()); csMsg("token saved"); csRefresh(); }
function csMsg(html){ document.getElementById("cs-msg").innerHTML = html; }
function csHeaders(){ var t = csToken(); return t ? { Authorization: "Bearer " + t } : {}; }
async function csFetch(path, opts){
  opts = opts || {};
  var res = await fetch(path, Object.assign({}, opts, { headers: Object.assign({}, opts.headers || {}, csHeaders()) }));
  if (res.status === 401) { csMsg("API token required or invalid."); throw new Error("unauthorized"); }
  if (!res.ok) throw new Error("request failed: " + res.status);
  return res;
}
function csSet(id, value){ var el = document.getElementById(id); if (el) el.textContent = value; }
async function csRefresh(){
  if (CS_AUTH && !csToken()) return;
  try {
    var s = await csFetch("/api/status").then(function(r){ return r.json(); });
    csSet("cs-status", s.last_status || "unknown");
    csSet("cs-running", String(Boolean(s.running)));
    csSet("cs-runid", s.last_run_id || "—");
    var run = document.getElementById("cs-run"); if (run) run.disabled = Boolean(s.running);
    var files = await csFetch("/api/files").then(function(r){ return r.json(); });
    document.getElementById("cs-files").innerHTML = files.length
      ? '<div class="cs-scroll"><table><thead><tr><th>file</th><th>size</th></tr></thead><tbody>' +
        files.map(function(f){ return '<tr><td><a href="/report/' + encodeURIComponent(f.name) + '">' +
          f.name + "</a></td><td class=\\"num\\">" + f.size + "</td></tr>"; }).join("") + "</tbody></table></div>"
      : '<p class="cs-empty">no files</p>';
  } catch (e) { /* 离线或未授权：保留页面上已有的静态快照 */ }
}
async function csRun(){
  var b = document.getElementById("cs-run"); b.disabled = true;
  try { await csFetch("/api/run", { method: "POST" }); csMsg("backtest started"); } catch (e) { b.disabled = false; }
  csRefresh();
}
async function csReport(){
  var b = document.getElementById("cs-report"); b.disabled = true;
  csMsg("building report (10-60s)…");
  try { await csFetch("/api/market-report", { method: "POST" }); csPoll(); } catch (e) { b.disabled = false; }
}
async function csPoll(){
  var s;
  try { s = await csFetch("/api/market-report/status").then(function(r){ return r.json(); }); }
  catch (e) { document.getElementById("cs-report").disabled = false; return; }
  if (s.running) { setTimeout(csPoll, 2500); return; }
  document.getElementById("cs-report").disabled = false;
  if (s.last_status === "success") csMsg('report ready — <a href="/">reload this page</a>');
  else if (s.last_status === "failed") csMsg("report failed: " + (s.last_error || ""));
  else csMsg("");
}
setInterval(csRefresh, 5000);
csRefresh();
</script>
"""


def render_console_html(
    config: AppConfig,
    status: dict[str, Any],
    history: list[dict[str, Any]],
    report: dict[str, Any] | None = None,
    markets: dict[str, Any] | None = None,
) -> str:
    """The single operations page served at ``/``."""
    lang = normalize_language(config.language)
    report_dir = config.report.output_dir
    groups = [
        (tr("Report", "报告", lang), _tab_report(report or {}, lang)),
        (tr("Markets", "行情", lang), _tab_markets(markets or {}, lang)),
        (tr("Backtest", "回测", lang), _tab_backtest(report_dir, lang)),
        (tr("Ops", "运行", lang), _tab_ops(config, status, history, lang)),
    ]
    title = tr("Quant Agent Console", "Quant Agent 控制台", lang)
    disclaimer = tr(
        "Research operations only — this service never submits orders.",
        "仅用于研究运维 —— 本服务不会提交任何订单。",
        lang,
    )
    js = _JS.replace("__AUTH__", json.dumps(config.dashboard_security.enabled))
    return f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{report_css()}{_CSS}</style>
</head>
<body>
<div class="wrap qa-report">
<header>
  <div class="kicker">Quant.ai · {tr('local console', '本地控制台', lang)}</div>
  <h1 class="title">{_esc(title)}</h1>
</header>
<div class="ribbon">{_esc(disclaimer)}</div>
{build_tabs(groups, group="cs")}
<footer><span>QUANT.AI · RESEARCH ONLY — {tr('not investment advice', '不构成投资建议', lang)}</span></footer>
</div>
{js}
</body>
</html>
"""


def write_dashboard(report_dir: Path, output_path: Path, language: str = "en") -> None:
    """Standalone backtest-diagnostics page archived next to a run's outputs.

    每次回测由 pipeline 调用，写进该 run 的目录；`/runs/<id>/dashboard` 直接吐这个文件，
    所以历史 run 不依赖当时的服务配置也能打开。内容等于控制台的「回测」页。
    """
    lang = normalize_language(language)
    title = tr("Backtest diagnostics", "回测诊断", lang)
    body = "".join(_tab_backtest(report_dir, lang))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{report_css()}{_CSS}</style>
</head>
<body>
<div class="wrap qa-report">
<header>
  <div class="kicker">Quant.ai · {tr('backtest diagnostics', '回测诊断', lang)}</div>
  <h1 class="title">{_esc(title)}</h1>
</header>
<div class="ribbon">{tr('Research diagnostics only. No live trading authorization.', '仅用于研究诊断，不授权实盘交易。', lang)}</div>
{body}
<footer><span>QUANT.AI · RESEARCH ONLY</span><span>{_esc(report_dir)}</span></footer>
</div>
</body>
</html>
""",
        encoding="utf-8",
    )
