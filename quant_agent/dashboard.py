from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_dashboard(report_dir: Path, output_path: Path) -> None:
    audit = _load_json(report_dir / "audit.json")
    data_quality = _load_json(report_dir / "data_quality.json")
    paper_audit = _load_json(report_dir / "paper_trading_audit.json")
    alerts = _load_json(report_dir / "alerts.json")
    notifications = _load_json(report_dir / "notifications.json")
    approval = _load_json(report_dir / "paper_order_approval.json")
    equity = _load_csv(report_dir / "equity_curve.csv")
    positions = _load_csv(report_dir / "positions.csv")
    trades = _load_csv(report_dir / "trades.csv")
    orders = _load_csv(report_dir / "proposed_orders.csv")
    recommendations = _load_csv(report_dir / "recommendations.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _html(
            metrics=audit.get("metrics", {}),
            period_metrics=audit.get("period_metrics", []),
            risk_checks=audit.get("risk_checks", []),
            outputs=audit.get("outputs", []),
            data_quality=data_quality,
            paper_audit=paper_audit,
            alerts=alerts,
            notifications=notifications,
            approval=approval,
            equity=equity,
            positions=positions,
            trades=trades,
            orders=orders,
            recommendations=recommendations,
        ),
        encoding="utf-8",
    )


def _html(
    metrics: dict[str, Any],
    period_metrics: list[dict[str, Any]],
    risk_checks: list[dict[str, Any]],
    outputs: list[str],
    data_quality: dict[str, Any],
    paper_audit: dict[str, Any],
    alerts: dict[str, Any],
    notifications: dict[str, Any],
    approval: dict[str, Any],
    equity: pd.DataFrame,
    positions: pd.DataFrame,
    trades: pd.DataFrame,
    orders: pd.DataFrame,
    recommendations: pd.DataFrame,
) -> str:
    metric_cards = "".join(
        f"<section><span>{_escape(key)}</span><strong>{_format(value)}</strong></section>"
        for key, value in metrics.items()
        if key in {"total_return", "cagr", "sharpe", "sortino", "max_drawdown", "alpha", "information_ratio"}
    )
    alert_summary = alerts.get("summary", {})
    alert_card = (
        f"<section><span>alerts</span><strong>{_escape(alert_summary.get('highest_severity', 'none'))} "
        f"({int(alert_summary.get('total', 0) or 0)})</strong></section>"
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quant Agent Dashboard</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #17202a; background: #f6f8fa; }}
    header {{ background: #13293d; color: white; padding: 20px 28px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
    .lang-switch {{ display: flex; gap: 8px; }}
    .lang-switch button {{ border: 1px solid rgba(255,255,255,0.45); background: transparent; color: white; padding: 6px 10px; border-radius: 5px; cursor: pointer; }}
    .lang-switch button.active {{ background: white; color: #13293d; }}
    main {{ padding: 24px 28px 40px; max-width: 1320px; margin: 0 auto; }}
    h1 {{ margin: 0; font-size: 24px; }}
    h2 {{ margin: 28px 0 12px; font-size: 18px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
    .cards section {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; padding: 12px; }}
    .cards span {{ display: block; color: #57606a; font-size: 12px; margin-bottom: 6px; }}
    .cards strong {{ font-size: 18px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d8dee4; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #d8dee4; padding: 7px 9px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #eef2f6; color: #24292f; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }}
    .panel {{ min-width: 0; }}
    .muted {{ color: #57606a; }}
    .scroll {{ overflow: auto; max-height: 360px; border: 1px solid #d8dee4; }}
  </style>
</head>
<body>
<header>
  <div class="topbar">
    <div>
      <h1 data-i18n="report_title">Quant Agent Dashboard</h1>
      <div class="muted" data-i18n="report_disclaimer">Research diagnostics only. No live trading authorization.</div>
    </div>
    <div class="lang-switch">
      <button type="button" data-lang="zh" onclick="setLanguage('zh')">中文</button>
      <button type="button" data-lang="en" onclick="setLanguage('en')">EN</button>
    </div>
  </div>
</header>
<main>
  <div class="cards">{metric_cards}{alert_card}</div>
  <h2 data-i18n="alerts">Alerts</h2>{_table(pd.DataFrame(alerts.get("alerts", [])))}
  <div class="grid">
    <div class="panel"><h2 data-i18n="notifications">Notifications</h2>{_table(pd.DataFrame(notifications.get("notifications", [])))}</div>
    <div class="panel"><h2 data-i18n="paper_approval">Paper Approval</h2>{_table(pd.DataFrame([approval] if approval else []))}</div>
  </div>
  <div class="grid">
    <div class="panel"><h2 data-i18n="period_metrics">Period Metrics</h2>{_table(pd.DataFrame(period_metrics))}</div>
    <div class="panel"><h2 data-i18n="risk_checks">Risk Checks</h2>{_table(pd.DataFrame(risk_checks))}</div>
  </div>
  <div class="grid">
    <div class="panel"><h2 data-i18n="data_quality">Data Quality</h2>{_table(pd.DataFrame(data_quality.get("issues", [])))}</div>
    <div class="panel"><h2 data-i18n="paper_checks">Paper Trading Checks</h2>{_table(pd.DataFrame(paper_audit.get("checks", [])))}</div>
  </div>
  <h2 data-i18n="equity_curve">Equity Curve</h2>{_table(equity.tail(20))}
  <h2 data-i18n="research_candidates">Research Buy Candidates</h2>{_table(recommendations)}
  <div class="grid">
    <div class="panel"><h2 data-i18n="latest_positions">Latest Positions</h2>{_table(positions.tail(50))}</div>
    <div class="panel"><h2 data-i18n="recent_trades">Recent Trades</h2>{_table(trades.tail(50))}</div>
  </div>
  <h2 data-i18n="proposed_orders">Proposed Orders</h2>{_table(orders)}
  <h2 data-i18n="outputs">Outputs</h2><p>{_escape(', '.join(outputs))}</p>
</main>
<script>
const translations = {{
  zh: {{
    report_title: 'Quant Agent 报告',
    report_disclaimer: '仅用于研究诊断，不授权实盘交易。',
    alerts: '告警',
    notifications: '通知',
    paper_approval: '纸面订单审批',
    period_metrics: '分段指标',
    risk_checks: '风控检查',
    data_quality: '数据质量',
    paper_checks: '纸面交易检查',
    equity_curve: '权益曲线',
    research_candidates: '研究买入候选',
    latest_positions: '最新持仓',
    recent_trades: '近期交易',
    proposed_orders: '纸面订单计划',
    outputs: '输出文件',
    no_data: '暂无数据'
  }},
  en: {{
    report_title: 'Quant Agent Dashboard',
    report_disclaimer: 'Research diagnostics only. No live trading authorization.',
    alerts: 'Alerts',
    notifications: 'Notifications',
    paper_approval: 'Paper Approval',
    period_metrics: 'Period Metrics',
    risk_checks: 'Risk Checks',
    data_quality: 'Data Quality',
    paper_checks: 'Paper Trading Checks',
    equity_curve: 'Equity Curve',
    research_candidates: 'Research Buy Candidates',
    latest_positions: 'Latest Positions',
    recent_trades: 'Recent Trades',
    proposed_orders: 'Proposed Orders',
    outputs: 'Outputs',
    no_data: 'No data.'
  }}
}};
const headerTranslations = {{
  zh: {{
    timestamp: '时间',
    severity: '级别',
    code: '代码',
    message: '消息',
    details: '详情',
    recommended_action: '建议动作',
    created_at: '创建时间',
    run_id: '运行 ID',
    report_dir: '报告目录',
    channel_status: '通道状态',
    alert: '告警',
    status: '状态',
    approver: '审批人',
    comment: '备注',
    submitted: '已提交',
    order_count: '订单数',
    period: '区间',
    start: '开始',
    end: '结束',
    rows: '行数',
    total_return: '总收益',
    cagr: '年化收益',
    sharpe: '夏普',
    sortino: 'Sortino',
    calmar: 'Calmar',
    volatility: '波动率',
    max_drawdown: '最大回撤',
    win_rate: '胜率',
    benchmark_total_return: '基准总收益',
    excess_total_return: '超额收益',
    beta: 'Beta',
    alpha: 'Alpha',
    information_ratio: '信息比率',
    passed: '通过',
    count: '数量',
    symbols: '标的',
    columns: '字段',
    date: '日期',
    equity: '权益',
    recommendation_type: '候选类型',
    label: '标签',
    horizon: '周期',
    rank: '排名',
    symbol: '标的',
    suggested_action: '建议动作',
    recommendation_score: '推荐分',
    confidence: '置信度',
    risk_level: '风险等级',
    target_weight: '目标权重',
    research_weight: '研究权重',
    latest_price: '最新价格',
    data_date: '数据日期',
    avg_dollar_volume_20: '20日均成交额',
    reason: '原因',
    disclaimer: '声明',
    weight: '权重',
    delta_weight: '权重变化',
    estimated_notional: '估算金额',
    target_date: '目标日期',
    side: '方向',
    delta_shares: '股数变化',
    reference_price: '参考价'
  }},
  en: {{}}
}};
function setLanguage(lang) {{
  localStorage.setItem('quantAgentLanguage', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const key = el.getAttribute('data-i18n');
    el.textContent = translations[lang][key] || translations.en[key] || el.textContent;
  }});
  document.querySelectorAll('[data-lang]').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-lang') === lang));
  document.querySelectorAll('th').forEach(th => {{
    if (!th.dataset.originalText) {{
      th.dataset.originalText = th.textContent.trim();
    }}
    th.textContent = headerTranslations[lang][th.dataset.originalText] || th.dataset.originalText;
  }});
}}
setLanguage(localStorage.getItem('quantAgentLanguage') || 'zh');
</script>
</body>
</html>
"""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return '<p class="muted" data-i18n="no_data">No data.</p>'
    return '<div class="scroll">' + frame.to_html(index=False, escape=True, border=0) + "</div>"


def _format(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return _escape(value)


def _escape(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
