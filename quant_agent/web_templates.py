"""Dashboard 控制台 HTML 生成。

从 server.py 拆出，集中存放纯字符串/HTML 渲染逻辑，便于阅读与维护。
"""

from __future__ import annotations

import json
from typing import Any

from quant_agent.config import AppConfig


def build_home_html(config: AppConfig, status: dict[str, Any], history: list[dict[str, Any]] | None = None) -> str:
    report_dir = str(config.report.output_dir)
    history = history or []
    schedule_state = "enabled" if config.schedule.enabled else "disabled"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quant Agent Control</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f5f7fa; color: #17202a; }}
    header {{ background: #102a43; color: white; padding: 18px 28px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
    .lang-switch {{ display: flex; gap: 8px; }}
    .lang-switch button {{ border: 1px solid rgba(255,255,255,0.45); background: transparent; color: white; padding: 6px 10px; border-radius: 5px; cursor: pointer; }}
    .lang-switch button.active {{ background: white; color: #102a43; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px 28px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    h2 {{ font-size: 18px; margin: 24px 0 10px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }}
    .card {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; padding: 14px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .label {{ color: #57606a; font-size: 12px; margin-bottom: 4px; }}
    .value {{ font-size: 16px; font-weight: 700; word-break: break-word; }}
    button, a.button {{ border: 0; background: #0969da; color: white; padding: 9px 12px; border-radius: 5px; text-decoration: none; cursor: pointer; display: inline-block; margin-right: 8px; }}
    button:disabled {{ opacity: 0.5; cursor: wait; }}
    input {{ border: 1px solid #d8dee4; border-radius: 5px; padding: 8px 10px; min-width: 260px; }}
    .notice {{ color: #57606a; font-size: 13px; margin-top: 8px; }}
    pre {{ background: #0b1220; color: #dbeafe; padding: 12px; border-radius: 6px; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; background: white; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #d8dee4; padding: 7px 9px; text-align: left; }}
  </style>
</head>
<body>
<header>
  <div class="topbar">
    <div>
      <h1 data-i18n="control_title">Quant Agent Control</h1>
      <div data-i18n="control_disclaimer">Research operations dashboard. No live orders are submitted from this service.</div>
    </div>
    <div class="lang-switch">
      <button type="button" data-lang="zh" onclick="setLanguage('zh')">中文</button>
      <button type="button" data-lang="en" onclick="setLanguage('en')">EN</button>
    </div>
  </div>
</header>
<main>
  <div class="grid">
    <div class="card"><div class="label" data-i18n="status">Status</div><div class="value" id="status">{_escape(status.get("last_status", "unknown"))}</div></div>
    <div class="card"><div class="label" data-i18n="running">Running</div><div class="value" id="running">{_escape(status.get("running", False))}</div></div>
    <div class="card"><div class="label" data-i18n="report_dir">Report Dir</div><div class="value">{_escape(report_dir)}</div></div>
    <div class="card"><div class="label" data-i18n="config">Config</div><div class="value">{_escape(status.get("config", ""))}</div></div>
    <div class="card"><div class="label" data-i18n="last_run_id">Last Run ID</div><div class="value" id="run-id">{_escape(status.get("last_run_id", ""))}</div></div>
    <div class="card"><div class="label" data-i18n="schedule">Schedule</div><div class="value"><span data-status-value="{schedule_state}">{schedule_state}</span> / {config.schedule.interval_minutes} min</div></div>
  </div>
  <h2 data-i18n="actions">Actions</h2>
  <div class="actions">
    <input id="api-token" type="password" autocomplete="off" placeholder="API token" data-placeholder-i18n="api_token">
    <button onclick="saveToken()" data-i18n="save_token">Save Token</button>
    <button id="run" onclick="runBacktest()" data-i18n="run_backtest">Run Backtest</button>
    <button id="market-report" onclick="runMarketReport()" data-i18n="market_report">Daily Market Report</button>
    <button onclick="openJson('/api/audit')" data-i18n="audit_json">Audit JSON</button>
    <button onclick="openJson('/api/operation-audit')" data-i18n="operation_audit">Operation Audit</button>
    <button onclick="openJson('/api/status')" data-i18n="status_json">Status JSON</button>
  </div>
  <div id="auth-message" class="notice"></div>
  <div id="market-message" class="notice"></div>
  <a class="button" href="/dashboard" data-i18n="open_report_dashboard">Open Report Dashboard</a>
  <a class="button" href="/market-report" target="_blank" data-i18n="open_market_report">Open Market Report</a>
  <a class="button" href="/markets" target="_blank" data-i18n="open_markets">Open Markets</a>
  <h2 data-i18n="latest_status">Latest Status</h2>
  <pre id="status-json">{_escape(json.dumps(status, indent=2, default=str))}</pre>
  <h2 data-i18n="report_files">Report Files</h2>
  <div id="files"></div>
  <h2 data-i18n="run_history">Run History</h2>
  <div id="runs">{_runs_table(history)}</div>
</main>
<script>
const translations = {{
  zh: {{
    control_title: 'Quant Agent 控制台',
    control_disclaimer: '研究运行控制台。本服务不会提交真实订单。',
    status: '状态',
    running: '运行中',
    report_dir: '报告目录',
    config: '配置',
    last_run_id: '最近运行 ID',
    schedule: '定时任务',
    actions: '操作',
    api_token: 'API token',
    save_token: '保存 Token',
    run_backtest: '运行回测',
    market_report: '生成今日美股分析报告',
    market_report_running: '正在搜索最新资料并生成报告（约需 10-60 秒）…',
    market_report_done: '报告已生成。',
    market_report_failed: '报告生成失败',
    open_market_report: '打开美股分析报告',
    open_markets: '打开 Markets 仪表盘',
    audit_json: '研究审计 JSON',
    operation_audit: '操作审计',
    status_json: '状态 JSON',
    open_report_dashboard: '打开报告 Dashboard',
    latest_status: '最新状态',
    report_files: '报告文件',
    run_history: '运行历史',
    token_saved: 'Token 已保存在当前浏览器。',
    token_required_invalid: '需要 API token，或 token 无效。',
    token_required: '需要 API token。',
    enabled: '启用',
    disabled: '关闭',
    unknown: '未知',
    true: '是',
    false: '否',
    dashboard: 'dashboard',
    approve: '批准',
    reject: '拒绝',
    no_runs: '暂无运行记录。'
  }},
  en: {{
    control_title: 'Quant Agent Control',
    control_disclaimer: 'Research operations dashboard. No live orders are submitted from this service.',
    status: 'Status',
    running: 'Running',
    report_dir: 'Report Dir',
    config: 'Config',
    last_run_id: 'Last Run ID',
    schedule: 'Schedule',
    actions: 'Actions',
    api_token: 'API token',
    save_token: 'Save Token',
    run_backtest: 'Run Backtest',
    market_report: 'Daily Market Report',
    market_report_running: 'Searching latest sources and building report (10-60s)...',
    market_report_done: 'Report ready.',
    market_report_failed: 'Report generation failed',
    open_market_report: 'Open Market Report',
    open_markets: 'Open Markets',
    audit_json: 'Audit JSON',
    operation_audit: 'Operation Audit',
    status_json: 'Status JSON',
    open_report_dashboard: 'Open Report Dashboard',
    latest_status: 'Latest Status',
    report_files: 'Report Files',
    run_history: 'Run History',
    token_saved: 'Token saved locally in this browser.',
    token_required_invalid: 'API token required or invalid.',
    token_required: 'API token required.',
    enabled: 'enabled',
    disabled: 'disabled',
    unknown: 'unknown',
    true: 'true',
    false: 'false',
    dashboard: 'dashboard',
    approve: 'Approve',
    reject: 'Reject',
    no_runs: 'No runs recorded.'
  }}
}};
const headerTranslations = {{
  zh: {{
    Name: '文件名',
    Size: '大小',
    'Run ID': '运行 ID',
    Status: '状态',
    Started: '开始时间',
    Finished: '结束时间',
    Alerts: '告警',
    Approval: '审批',
    Report: '报告'
  }},
  en: {{}}
}};
function currentLanguage() {{
  return localStorage.getItem('quantAgentLanguage') || 'zh';
}}
function t(key) {{
  const lang = currentLanguage();
  return (translations[lang] && translations[lang][key]) || translations.en[key] || key;
}}
function formatStatusValue(value) {{
  const key = String(value).toLowerCase();
  return t(key) || String(value);
}}
function setLanguage(lang) {{
  localStorage.setItem('quantAgentLanguage', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  }});
  document.querySelectorAll('[data-placeholder-i18n]').forEach(el => {{
    el.setAttribute('placeholder', t(el.getAttribute('data-placeholder-i18n')));
  }});
  document.querySelectorAll('[data-lang]').forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-lang') === lang));
  document.querySelectorAll('[data-status-value]').forEach(el => {{
    el.textContent = formatStatusValue(el.getAttribute('data-status-value'));
  }});
  translateTableHeaders();
}}
function translateTableHeaders() {{
  const lang = currentLanguage();
  document.querySelectorAll('th').forEach(th => {{
    if (!th.dataset.originalText) {{
      th.dataset.originalText = th.textContent.trim();
    }}
    th.textContent = headerTranslations[lang][th.dataset.originalText] || th.dataset.originalText;
  }});
}}
const authRequired = {json.dumps(config.dashboard_security.enabled).lower()};
const tokenInput = document.getElementById('api-token');
tokenInput.value = localStorage.getItem('quantAgentApiToken') || '';
function saveToken() {{
  localStorage.setItem('quantAgentApiToken', tokenInput.value);
  document.getElementById('auth-message').textContent = t('token_saved');
  refresh();
}}
function authHeaders() {{
  const token = tokenInput.value || localStorage.getItem('quantAgentApiToken') || '';
  return token ? {{ 'Authorization': `Bearer ${{token}}` }} : {{}};
}}
async function apiFetch(path, options = {{}}) {{
  const response = await fetch(path, {{ ...options, headers: {{ ...(options.headers || {{}}), ...authHeaders() }} }});
  if (response.status === 401) {{
    document.getElementById('auth-message').textContent = t('token_required_invalid');
    throw new Error('unauthorized');
  }}
  if (!response.ok) {{
    throw new Error(`request failed: ${{response.status}}`);
  }}
  document.getElementById('auth-message').textContent = '';
  return response;
}}
async function refresh() {{
  if (authRequired && !(tokenInput.value || localStorage.getItem('quantAgentApiToken'))) {{
    document.getElementById('auth-message').textContent = t('token_required');
    return;
  }}
  const status = await apiFetch('/api/status').then(r => r.json());
  document.getElementById('status').textContent = formatStatusValue(status.last_status || 'unknown');
  document.getElementById('running').textContent = formatStatusValue(Boolean(status.running));
  document.getElementById('run-id').textContent = status.last_run_id || '';
  document.getElementById('run').disabled = Boolean(status.running);
  document.getElementById('status-json').textContent = JSON.stringify(status, null, 2);
  const files = await apiFetch('/api/files').then(r => r.json());
  document.getElementById('files').innerHTML = '<table><thead><tr><th>Name</th><th>Size</th></tr></thead><tbody>' +
    files.map(f => `<tr><td><a href="/report/${{encodeURIComponent(f.name)}}">${{f.name}}</a></td><td>${{f.size}}</td></tr>`).join('') +
    '</tbody></table>';
  const runs = await apiFetch('/api/runs').then(r => r.json());
  document.getElementById('runs').innerHTML = '<table><thead><tr><th>Run ID</th><th>Status</th><th>Started</th><th>Finished</th><th>Alerts</th><th>Approval</th><th>Report</th></tr></thead><tbody>' +
    runs.map(r => `<tr><td>${{r.run_id}}</td><td>${{formatStatusValue(r.status)}}</td><td>${{r.started_at || ''}}</td><td>${{r.finished_at || ''}}</td><td>${{(r.alert_summary || {{}}).highest_severity || ''}}</td><td><button onclick="approveRun('${{r.run_id}}')">${{t('approve')}}</button><button onclick="rejectRun('${{r.run_id}}')">${{t('reject')}}</button></td><td><a href="/runs/${{encodeURIComponent(r.run_id)}}/dashboard">${{t('dashboard')}}</a></td></tr>`).join('') +
    '</tbody></table>';
  translateTableHeaders();
}}
async function runBacktest() {{
  document.getElementById('run').disabled = true;
  await apiFetch('/api/run', {{ method: 'POST' }});
  await refresh();
}}
async function runMarketReport() {{
  const btn = document.getElementById('market-report');
  btn.disabled = true;
  document.getElementById('market-message').textContent = t('market_report_running');
  try {{
    await apiFetch('/api/market-report', {{ method: 'POST' }});
    pollMarketReport();
  }} catch (e) {{
    btn.disabled = false;
  }}
}}
async function pollMarketReport() {{
  let status;
  try {{
    status = await apiFetch('/api/market-report/status').then(r => r.json());
  }} catch (e) {{
    document.getElementById('market-report').disabled = false;
    return;
  }}
  if (status.running) {{
    setTimeout(pollMarketReport, 2500);
    return;
  }}
  document.getElementById('market-report').disabled = false;
  const msg = document.getElementById('market-message');
  if (status.last_status === 'success') {{
    msg.innerHTML = t('market_report_done') + ' <a href="/market-report" target="_blank">' + t('open_market_report') + '</a>';
  }} else if (status.last_status === 'failed') {{
    msg.textContent = t('market_report_failed') + ': ' + (status.last_error || '');
  }} else {{
    msg.textContent = '';
  }}
}}
async function approveRun(runId) {{
  await apiFetch(`/api/runs/${{encodeURIComponent(runId)}}/approve-paper`, {{ method: 'POST' }});
  await refresh();
}}
async function rejectRun(runId) {{
  await apiFetch(`/api/runs/${{encodeURIComponent(runId)}}/reject-paper`, {{ method: 'POST' }});
  await refresh();
}}
async function openJson(path) {{
  const data = await apiFetch(path).then(r => r.text());
  const tab = window.open('', '_blank');
  tab.document.write(`<pre>${{data.replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]))}}</pre>`);
}}
setInterval(() => {{
  if (!authRequired || tokenInput.value || localStorage.getItem('quantAgentApiToken')) {{
    refresh();
  }}
}}, 3000);
setLanguage(currentLanguage());
refresh();
</script>
</body>
</html>
"""


def _runs_table(history: list[dict[str, Any]]) -> str:
    if not history:
        return '<p data-i18n="no_runs">No runs recorded.</p>'
    rows = "".join(
        "<tr>"
        f"<td>{_escape(row.get('run_id', ''))}</td>"
        f"<td>{_escape(row.get('status', ''))}</td>"
        f"<td>{_escape(row.get('started_at', ''))}</td>"
        f"<td>{_escape(row.get('finished_at', ''))}</td>"
        f"<td>{_escape((row.get('alert_summary') or {}).get('highest_severity', ''))}</td>"
        f"<td>pending</td>"
        f"<td><a href=\"/runs/{_escape(row.get('run_id', ''))}/dashboard\">dashboard</a></td>"
        "</tr>"
        for row in history
    )
    return "<table><thead><tr><th>Run ID</th><th>Status</th><th>Started</th><th>Finished</th><th>Alerts</th><th>Approval</th><th>Report</th></tr></thead><tbody>" + rows + "</tbody></table>"


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
