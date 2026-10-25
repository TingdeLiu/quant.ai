"""The first-use research workspace. No model calls or broker connections."""

from __future__ import annotations

import html
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from quant_agent.i18n import normalize_language, tr

Ticker = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9.\-]{0,11}$")]


class WorkspacePosition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    symbol: Ticker
    shares: float = Field(gt=0, allow_inf_nan=False)
    cost_basis: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class PortfolioChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["watchlist.add", "watchlist.remove", "holding.set", "holding.remove"]
    symbols: list[Ticker] = Field(default_factory=list, max_length=50)
    position: WorkspacePosition | None = None

    @field_validator("symbols", mode="before")
    @classmethod
    def uppercase_symbols(cls, value: object) -> object:
        if isinstance(value, list):
            return [s.strip().upper() if isinstance(s, str) else s for s in value]
        return value

    @model_validator(mode="after")
    def validate_action(self) -> PortfolioChange:
        if self.action == "holding.set":
            if self.position is None or self.symbols:
                raise ValueError("holding.set requires a position and no symbols")
        elif not self.symbols or self.position is not None:
            raise ValueError("this action requires symbols and no position")
        return self


def render_workspace_html(language: str = "en", *, demo: bool = False) -> str:
    lang = normalize_language(language)
    pairs = {
        "title": ("Your personal research desk", "你的个人美股研究台"),
        "beta": ("Private beta", "早期试用版"),
        "local": ("Runs on your computer", "在你的电脑上运行"),
        "nav_portfolio": ("My coverage", "我的关注"),
        "nav_report": ("Research brief", "研究简报"),
        "nav_ai": ("Discuss with AI", "和 AI 继续研究"),
        "console": ("Advanced console", "高级控制台"),
        "hero": ("Start with what you own.", "从你的持仓开始，\n看懂市场变化。"),
        "intro": ("Bring your holdings and watchlist together. Build a factual brief, then explore the questions that matter with your AI assistant.", "把持仓、自选和市场变化放在一起。先看有依据的简报，再让 AI 帮你把问题研究清楚。"),
        "step1": ("Add your coverage", "添加关注的股票"),
        "step2": ("Build your brief", "生成个人研究简报"),
        "step3": ("Explore with AI", "带着问题继续研究"),
        "coverage": ("What are you following?", "你在关注哪些股票？"),
        "coverage_hint": ("Start with a few tickers. You can add holdings below.", "先添加几只自选股，也可以在下方记录持仓。"),
        "tickers": ("Stock tickers", "股票代码"),
        "ticker_hint": ("Separate tickers with spaces or commas. Up to 50 at a time.", "用空格或逗号分隔，每次最多添加 50 个。"),
        "add": ("Add to watchlist", "添加自选"),
        "watchlist_empty": ("No stocks followed yet. Add the companies you want to understand.", "还没有自选股。添加你想持续了解的公司。"),
        "holding_title": ("Record a holding", "记录一笔持仓"),
        "holding_hint": ("Optional. Self-reported records help put your research in context.", "选填。记录股数和平均每股成本，让简报围绕你的持仓展开。"),
        "symbol": ("Ticker", "股票代码"),
        "shares": ("Shares", "持有股数"),
        "cost": ("Avg. cost / share (USD)", "每股平均成本（美元）"),
        "note": ("Your research note (optional)", "研究备注（选填）"),
        "optional": ("Optional", "选填"),
        "save_holding": ("Save holding", "保存持仓"),
        "holding_empty": ("No holdings recorded. A watchlist is enough to get started.", "还没有持仓记录。只添加自选股也能开始研究。"),
        "remove": ("Remove", "移除"),
        "edit": ("Edit", "编辑"),
        "cancel": ("Cancel edit", "取消编辑"),
        "recorded": ("Recorded holdings", "已记录的持仓"),
        "brief": ("Your next research brief", "把关注，变成一份简报。"),
        "brief_hint": ("Holdings first, then market context, relative performance and public news where available.", "先看持仓表现，再看大盘环境、相对强弱与可用的公开资讯。"),
        "generate": ("Generate research brief", "生成研究简报"),
        "generating": ("Building your brief…", "正在整理研究简报…"),
        "generated": ("Your brief is ready. Review it below or copy a research question to your AI assistant.", "简报已生成。可以在下方查看，或复制研究问题给你的 AI 助手。"),
        "generate_hint": ("The first report can take a few minutes while historical prices are downloaded. Closing this page does not cancel it.", "首次生成需下载历史行情，可能需要几分钟。关闭页面后任务仍会继续。"),
        "report_empty": ("Your brief will appear here.", "你的第一份简报会显示在这里。"),
        "report_empty_hint": ("Add a ticker, then generate your first brief.", "添加一只股票，再点击生成简报。"),
        "download": ("Download HTML brief", "下载 HTML 简报"),
        "preview": ("Research brief preview", "研究简报预览"),
        "ai_title": ("A better starting point for your AI conversation.", "让 AI 的分析，从事实出发。"),
        "ai_hint": ("Copy a question with the full brief and paste it into your AI assistant. Answers happen there; this workspace prepares the evidence.", "复制研究问题和完整简报，粘贴到你正在使用的 AI 助手里继续讨论。简报提供依据，AI 帮你分析。"),
        "q1": ("What changed in my holdings?", "我的持仓，哪些变化值得关注？"),
        "q2": ("Where is my risk concentrated?", "我的风险集中在哪里？"),
        "q3": ("What should I research next?", "下一步应该核实哪些信息？"),
        "copy": ("Copy brief + question", "复制简报与问题"),
        "copied": ("Copied. Paste into your AI assistant to continue.", "已复制，粘贴到你的 AI 助手里继续研究。"),
        "clipboard_error": ("Clipboard unavailable. Select and copy the text below.", "无法自动复制，请选中下方文字手动复制。"),
        "saved": ("Saved. Generate a new brief to include the change.", "已保存。重新生成简报即可纳入这次修改。"),
        "loading": ("Loading your workspace…", "正在读取你的研究台…"),
        "ready": ("Ready to research", "可以开始研究了"),
        "fresh": ("Latest generated brief", "最近生成的简报"),
        "stale": ("Your coverage changed. Generate a new brief to update it.", "你的自选或持仓已变化，请重新生成简报。"),
        "failed": ("Report generation failed. Check your data connection and retry. Any previous brief is kept below.", "简报生成失败，请检查数据连接后重试。下方仍保留上次简报。"),
        "data_error": ("Price data is unavailable. This brief may be incomplete; check your data source and retry.", "暂时无法取得价格数据，简报可能不完整；请检查数据源后重试。"),
        "network_error": ("Unable to connect. Check that the local service is running and retry.", "连接失败，请确认本地服务仍在运行，再重试。"),
        "retry": ("Reconnect", "重新连接"),
        "auth_title": ("Connect to your workspace", "连接你的研究台"),
        "auth_hint": ("This local service requires an access token. It stays in this tab's memory.", "本地服务启用了访问保护。令牌仅保留在当前标签页内存中。"),
        "token": ("Access token", "访问令牌"),
        "connect": ("Connect", "连接"),
        "auth_error": ("Access denied. Check your token and connect again.", "无法访问，请检查令牌后重新连接。"),
        "demo": ("Demo workspace · simulated prices and holdings · no network requests", "演示研究台 · 模拟价格与持仓 · 全程离线"),
        "demo_hint": ("Try AAPL, MSFT, NVDA or SPY. Other tickers have no demo prices.", "可以体验 AAPL、MSFT、NVDA、SPY；其他代码暂无演示价格。"),
        "privacy": ("Your watchlist and holdings are saved on this computer. When you copy a brief to an AI assistant, the text includes your recorded holdings.", "自选和持仓保存在这台电脑上。复制简报给 AI 时，文本会包含你记录的持仓。"),
        "disclaimer": ("Research and learning only. Not investment advice. No orders, approvals or broker connection. Quotes may be delayed or unavailable.", "仅供研究与学习，不构成投资建议。不下单、不审批、不连接券商。行情可能延迟或暂不可用。"),
        "prompt_rule": ("Use only the evidence in the brief below. Separate observations from inferences, state the data date and gaps, and suggest what to verify. Do not provide trade instructions or promise returns.", "请基于下方简报中的证据分析，区分事实与推测，注明数据日期和缺失信息，提出待核实的问题；不要给出交易指令或收益承诺。"),
        "demo_prompt": ("This is a demo with simulated data, not real market information.", "这是模拟数据演示，不代表真实市场信息。"),
        "source_label": ("Report data date", "报告数据截止"),
        "working": ("Saving…", "正在保存…"),
        "empty_tickers": ("Add at least one stock ticker first.", "请先添加至少一只股票。"),
    }
    copy = {key: tr(*pair, lang) for key, pair in pairs.items()}
    if demo:
        copy["generate_hint"] = tr(
            "Uses simulated historical prices stored separately from your real portfolio. No market-data downloads.",
            "使用独立保存的模拟历史价格与演示持仓，无需下载行情。",
            lang,
        )
    page = _HTML.replace("__LANG__", lang).replace("__CONFIG__", json.dumps(copy, ensure_ascii=False).replace("<", "\\u003c"))
    page = page.replace("__DEMO_HIDDEN__", "" if demo else "hidden")
    for key, value in copy.items():
        page = page.replace("__" + key.upper() + "__", html.escape(value))
    return page


_HTML = r'''<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>quant.ai — __TITLE__</title>
<style>
:root{--page:#f3f6fa;--paper:#fff;--ink:#17344b;--muted:#526679;--line:#dce4ed;--accent:#087e8b;--tint:#e7f3f4;--warning:#805310}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.65 Aptos,"Segoe UI","Microsoft YaHei",sans-serif}
a{color:inherit}button,input,textarea{font:inherit}button,a,input,textarea{outline-offset:4px}button:focus-visible,a:focus-visible{outline:3px solid var(--accent)}button{cursor:pointer}button:disabled{cursor:wait;opacity:.55}button.busy{cursor:wait}button,.button{border:0;border-radius:7px;padding:11px 18px;display:inline-flex;align-items:center;justify-content:center;gap:8px;font-weight:600;text-decoration:none;background:var(--ink);color:white}button:hover,.button:hover{filter:brightness(1.08)}button.quiet,.button.quiet{background:var(--page);color:var(--ink);border:1px solid var(--line)}button.text{padding:4px 8px;background:none;color:var(--muted);font-size:13px}button.text:hover{background:var(--page)}.primary{background:var(--accent)}[hidden]{display:none!important}
.shell{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh}.sidebar{padding:32px 24px;background:var(--paper);border-right:1px solid var(--line);display:flex;flex-direction:column;position:sticky;top:0;height:100vh}.brand{font-size:27px;font-weight:750;letter-spacing:-1.4px;text-decoration:none;display:flex;align-items:center;gap:11px}.brand svg{width:27px;color:var(--accent)}.beta{color:var(--muted);font-size:12px;margin:9px 0 38px}.sidebar nav{display:grid;gap:8px}.sidebar nav a{padding:10px 12px;border-radius:7px;text-decoration:none;color:var(--muted)}.sidebar nav a:first-child{background:var(--tint);color:#086773;font-weight:600}.sidebar nav a:hover{background:var(--page)}.side-bottom{margin-top:auto;font-size:12px;color:var(--muted)}.local-dot{display:inline-block;width:6px;height:6px;background:var(--accent);border-radius:50%;margin-right:6px}.side-bottom a{display:block;margin-top:14px}
main{max-width:1250px;width:100%;padding:34px 48px 24px;margin:auto}.topline{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:13px;gap:12px}.topline a{text-decoration:none}.demo-banner{padding:10px 16px;background:#fff3d9;border:1px solid #e8cd90;border-radius:7px;margin:20px 0;color:#745215;font-size:13px}.hero{padding:35px 0 24px;display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:30px;align-items:center}h1{font-size:clamp(32px,3.3vw,48px);line-height:1.25;letter-spacing:-1.8px;white-space:pre-line;margin:0 0 18px;font-weight:650}.hero p{margin:0;color:var(--muted);max-width:570px;font-size:16px}.steps{display:grid;gap:15px;color:var(--muted);font-size:13px}.step{display:flex;gap:12px;align-items:center}.step span{border:1px solid var(--line);border-radius:50%;display:grid;place-items:center;width:28px;height:28px;background:white;flex:none}.step.complete span{background:var(--tint);border-color:var(--accent);color:var(--accent)}.step.active{color:var(--ink);font-weight:600}
.notice{padding:11px 15px;border-radius:6px;background:var(--tint);margin:0 0 20px;overflow-wrap:anywhere}.notice.error{background:#fff0ec;color:#942d1e}.notice button{margin-left:12px}.grid{display:grid;grid-template-columns:minmax(0,1.18fr) minmax(280px,.82fr);gap:22px;align-items:start}.panel{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:28px;min-width:0}h2{font-size:21px;line-height:1.4;font-weight:650;margin:0 0 8px;letter-spacing:-.4px}h3{font-size:16px;margin:0 0 7px;font-weight:650}.hint{color:var(--muted);font-size:13px;margin:0 0 22px}.watch-form{display:flex;gap:9px;align-items:start}.field{display:grid;gap:5px;min-width:0}.watch-form .field{flex:1}.watch-form button{margin-top:27px;white-space:nowrap}.field label{font-size:12px;color:var(--muted);font-weight:600}.field input{width:100%;min-width:0;background:#fbfcfe;border:1px solid #b8c8d6;border-radius:6px;padding:10px 11px;color:var(--ink)}input:focus,textarea:focus{outline:2px solid var(--accent);border-color:var(--accent)}.helper{font-size:12px;color:var(--muted);margin:7px 0}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 22px}.chip{background:var(--tint);border-radius:5px;padding:4px 5px 4px 11px;color:#09616c;font-size:13px;font-weight:650}.chip button{background:none;color:inherit;padding:0 6px;font-size:17px}.empty{font-size:13px;color:var(--muted);margin:15px 0 22px}.divider{border:0;border-top:1px solid var(--line);margin:25px 0}.holding-fields{display:grid;grid-template-columns:1fr .8fr 1.5fr;gap:10px}.note-field{margin-top:12px}.form-actions{display:flex;gap:8px;margin-top:15px;flex-wrap:wrap}.holdings{margin-top:24px}.holding-row{padding:13px 0;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:10px;align-items:center}.holding-row:last-child{border-bottom:0}.holding-row strong{font-weight:650}.holding-row small{display:block;color:var(--muted);font-size:12px;overflow-wrap:anywhere}.holding-actions{display:flex;flex-shrink:0}.brief-card{background:#eaf0f6;border-color:#d6e1ec}.brief-card h2{font-size:26px;max-width:300px;margin-bottom:14px}.brief-card p{color:var(--muted);font-size:14px}.brief-card .primary{width:100%;margin:12px 0 6px}.scope{display:flex;gap:6px;flex-wrap:wrap;margin:22px 0}.scope span{padding:4px 10px;border:1px solid #c5d2df;border-radius:4px;font-size:12px;color:var(--muted)}#job-state{font-size:13px;margin-top:16px}#report-date{font-size:12px;color:var(--muted)}.ai-panel{margin-top:22px}.question{padding:14px 0;border-bottom:1px solid var(--line)}.question:last-child{border:0}.question p{margin:0 0 8px;font-size:14px}.question button{font-size:12px;padding:5px 10px;background:var(--tint);color:#09616c}
.report-section{margin-top:28px}.section-head{display:flex;justify-content:space-between;gap:15px;align-items:center;margin-bottom:15px;flex-wrap:wrap}.section-head h2{margin:0}.report-placeholder{min-height:200px;display:grid;place-content:center;text-align:center;border:1px dashed #b8c8d6;border-radius:12px;background:#f9fbfd;padding:30px}.report-placeholder svg{width:40px;height:40px;color:#90a4b6;margin:0 auto 12px}.report-placeholder h3{font-size:17px;margin:0 0 6px}.report-placeholder p{margin:0;color:var(--muted);font-size:13px}iframe{display:block;border:1px solid var(--line);border-radius:10px;background:white;width:100%;height:760px}.auth{max-width:520px;margin:20px 0}.auth button{margin-top:12px}footer{margin-top:28px;font-size:12px;color:var(--muted)}footer p{margin:7px 0}.manual-copy textarea{width:100%;height:170px;padding:12px;border:1px solid var(--line);border-radius:6px}.manual-copy{margin-top:20px}.spinner{width:14px;height:14px;border:2px solid #ffffff70;border-top-color:white;border-radius:50%;animation:spin 1s linear infinite;display:inline-block}@keyframes spin{to{transform:rotate(360deg)}}
@media(min-width:1600px){main{padding-top:48px}.hero{padding-top:50px}}@media(max-width:1100px){main{padding:28px}.sidebar{padding:28px 16px}.shell{grid-template-columns:190px minmax(0,1fr)}.grid{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.steps{display:flex;flex-wrap:wrap;gap:14px}.brief-card h2{max-width:none}.ai-panel{margin-top:18px}.question{display:flex;justify-content:space-between;align-items:center;gap:12px}.question p{margin:0}}@media(max-width:650px){.shell{display:block}.sidebar{position:static;height:auto;padding:15px 20px;border-right:0;border-bottom:1px solid var(--line)}.brand{font-size:24px}.beta,.side-bottom{display:none}.sidebar nav{display:flex;gap:5px;margin-top:12px;font-size:12px}.sidebar nav a{padding:6px 8px}.topline{font-size:11px}main{padding:20px 16px}.hero{padding:24px 0;gap:20px}h1{font-size:32px;letter-spacing:-1px}.hero p{font-size:14px}.steps{font-size:11px;gap:10px}.step{gap:6px}.step span{width:23px;height:23px}.panel{padding:20px}.watch-form{flex-wrap:wrap}.watch-form button{margin-top:0;width:100%}.watch-form .field{flex-basis:100%}.holding-fields{grid-template-columns:1fr 1fr}.holding-fields .field:last-child{grid-column:1/-1}.holding-row{align-items:start}.holding-actions{flex-direction:column}.question{display:block}.question p{margin-bottom:8px}.section-head .button{font-size:12px;padding:8px 12px}iframe{height:650px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.spinner{animation:none}}
</style></head><body>
<div class="shell"><aside class="sidebar"><a class="brand" href="/app" aria-label="quant.ai"><svg viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="M3 21V7h6v14m5 0V12h5v9m5 0V3" stroke="currentColor" stroke-width="3"/><path d="M1 25h27" stroke="currentColor" stroke-width="2"/></svg>quant.ai</a><p class="beta">__BETA__</p><nav aria-label="quant.ai"><a href="#coverage">__NAV_PORTFOLIO__</a><a href="#brief">__NAV_REPORT__</a><a href="#discuss">__NAV_AI__</a></nav><div class="side-bottom"><span class="local-dot"></span>__LOCAL__<a href="/">__CONSOLE__</a></div></aside>
<main><div class="topline"><span>__TITLE__</span><span>__BETA__</span></div>
<div class="demo-banner" __DEMO_HIDDEN__><strong>__DEMO__</strong><br>__DEMO_HINT__</div>
<header class="hero"><div><h1>__HERO__</h1><p>__INTRO__</p></div><div class="steps" aria-label="__TITLE__"><div class="step active" id="step1"><span>1</span>__STEP1__</div><div class="step" id="step2"><span>2</span>__STEP2__</div><div class="step" id="step3"><span>3</span>__STEP3__</div></div></header>
<div id="notice" class="notice" role="status" aria-live="polite">__LOADING__</div><button id="retry" class="quiet" hidden>__RETRY__</button>
<form id="auth" class="panel auth" hidden><h2>__AUTH_TITLE__</h2><p class="hint">__AUTH_HINT__</p><div class="field"><label for="token">__TOKEN__</label><input id="token" type="password" autocomplete="off" required></div><button type="submit">__CONNECT__</button></form>
<div id="workspace" hidden><div class="grid"><section id="coverage" class="panel"><h2>__COVERAGE__</h2><p class="hint">__COVERAGE_HINT__</p>
<form id="watch-form" class="watch-form"><div class="field"><label for="tickers">__TICKERS__</label><input id="tickers" placeholder="AAPL, MSFT, NVDA" autocomplete="off" maxlength="649" aria-describedby="ticker-hint" required></div><button type="submit">__ADD__</button></form><p id="ticker-hint" class="helper">__TICKER_HINT__</p><div id="watchlist" class="chips"></div>
<hr class="divider"><h3 id="holding-heading">__HOLDING_TITLE__</h3><p class="hint">__HOLDING_HINT__</p><form id="holding-form"><div class="holding-fields"><div class="field"><label for="symbol">__SYMBOL__</label><input id="symbol" placeholder="AAPL" maxlength="12" pattern="[A-Za-z][A-Za-z0-9.\-]{0,11}" required autocomplete="off"></div><div class="field"><label for="shares">__SHARES__</label><input id="shares" type="number" min="0.00000001" step="any" placeholder="10" required></div><div class="field"><label for="cost">__COST__</label><input id="cost" type="number" min="0.00000001" step="any" placeholder="__OPTIONAL__"></div></div><div class="field note-field"><label for="holding-note">__NOTE__</label><input id="holding-note" maxlength="500"></div><div class="form-actions"><button type="submit" class="quiet">__SAVE_HOLDING__</button><button id="cancel-edit" type="button" class="text" hidden>__CANCEL__</button></div></form>
<div id="holdings" class="holdings"></div></section>
<div><section class="panel brief-card"><h2>__BRIEF__</h2><p>__BRIEF_HINT__</p><div class="scope"><span>__NAV_PORTFOLIO__</span><span>__NAV_REPORT__</span><span>__NAV_AI__</span></div><button id="generate" class="primary" disabled>__GENERATE__</button><p class="helper">__GENERATE_HINT__</p><div id="job-state" role="status" aria-live="polite"></div><div id="report-date"></div></section>
<section class="panel ai-panel" id="discuss"><h3>__AI_TITLE__</h3><p class="hint">__AI_HINT__</p><div class="question"><p>__Q1__</p><button class="copy" data-question="q1" disabled>__COPY__</button></div><div class="question"><p>__Q2__</p><button class="copy" data-question="q2" disabled>__COPY__</button></div><div class="question"><p>__Q3__</p><button class="copy" data-question="q3" disabled>__COPY__</button></div><div id="manual-copy" class="manual-copy" hidden><label for="copy-text">__CLIPBOARD_ERROR__</label><textarea id="copy-text" readonly></textarea></div></section></div></div>
<section id="brief" class="report-section"><div class="section-head"><h2>__NAV_REPORT__</h2><button id="download" class="quiet" hidden>__DOWNLOAD__</button></div><div id="report-empty" class="report-placeholder"><svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect x="8" y="3" width="24" height="34" rx="3" stroke="currentColor" stroke-width="2"/><path d="M14 13h12m-12 7h12m-12 7h7" stroke="currentColor" stroke-width="2"/></svg><h3>__REPORT_EMPTY__</h3><p>__REPORT_EMPTY_HINT__</p></div><iframe id="report-frame" title="__PREVIEW__" sandbox="allow-scripts" hidden></iframe></section></div>
<footer><p>__PRIVACY__</p><p>__DISCLAIMER__</p></footer></main></div>
<script>
'use strict';
const text=__CONFIG__;
const $=id=>document.getElementById(id);
let token='',state=null,poll=null,reportKey='',reportHTML='',polling=false,generationPending=false;
function notice(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
async function api(path,options={}){
  let response;
  try{response=await fetch(path,{...options,headers:{...options.headers,...(token?{'Authorization':'Bearer '+token}:{})},cache:'no-store'});}
  catch{throw new Error(text.network_error);}
  if(response.status===401){$('auth').hidden=false;$('workspace').hidden=true;clearTimeout(poll);throw new Error(text.auth_error);}
  if(!response.ok){let detail='';try{detail=(await response.json()).error;}catch{}throw new Error(detail||text.network_error);}
  return response;
}
function element(tag,content,className){const node=document.createElement(tag);if(content!==undefined)node.textContent=content;if(className)node.className=className;return node;}
function actionButton(label,callback){const b=element('button',label,'text');b.type='button';b.addEventListener('click',()=>callback(b));return b;}
function renderPortfolio(){
  const pf=state.portfolio,watch=$('watchlist');watch.replaceChildren();
  if(!pf.watchlist.length)watch.append(element('p',text.watchlist_empty,'empty'));
  for(const symbol of pf.watchlist){const chip=element('span',symbol,'chip');const remove=actionButton('×',b=>mutate({action:'watchlist.remove',symbols:[symbol]},b));remove.setAttribute('aria-label',text.remove+' '+symbol);chip.append(remove);watch.append(chip);}
  const holdings=$('holdings');holdings.replaceChildren();
  if(pf.holdings.length)holdings.append(element('h3',text.recorded));else holdings.append(element('p',text.holding_empty,'empty'));
  for(const h of pf.holdings){const row=element('div',undefined,'holding-row'),info=element('div');info.append(element('strong',h.symbol));info.append(element('small',text.shares+': '+h.shares+(h.cost_basis==null?'':' / '+text.cost+': $'+h.cost_basis)));if(h.note)info.append(element('small',h.note));const actions=element('div',undefined,'holding-actions');actions.append(actionButton(text.edit,()=>editHolding(h)),actionButton(text.remove,b=>mutate({action:'holding.remove',symbols:[h.symbol]},b)));row.append(info,actions);holdings.append(row);}
}
function editHolding(h){$('symbol').value=h.symbol;$('symbol').readOnly=true;$('shares').value=h.shares;$('cost').value=h.cost_basis??'';$('holding-note').value=h.note??'';$('cancel-edit').hidden=false;$('shares').focus();}
function resetHolding(){$('holding-form').reset();$('symbol').readOnly=false;$('cancel-edit').hidden=true;}
function renderStatus(){
  const job=state.report_status,running=job.running,covered=state.portfolio.watchlist.length+state.portfolio.holdings.length>0;
  $('generate').disabled=running||!covered;
  $('generate').replaceChildren();if(running)$('generate').append(element('span',undefined,'spinner'));$('generate').append(document.createTextNode(running?text.generating:text.generate));
  const message=running?text.generating:job.last_status==='failed'?text.failed:state.report_available&&!state.report_current?text.stale:state.report_available&&state.data_status!=='ok'?text.data_error:state.report_available?text.fresh:covered?text.ready:text.empty_tickers;
  $('job-state').textContent=message;$('report-date').textContent=state.as_of_date?text.source_label+': '+state.as_of_date:'';
  $('step1').classList.toggle('complete',covered);$('step2').classList.toggle('active',covered);$('step2').classList.toggle('complete',state.report_available&&state.report_current);$('step3').classList.toggle('active',state.report_available);
  for(const button of document.querySelectorAll('.copy'))button.disabled=!state.report_available||!state.report_current||running;
  $('download').hidden=!state.report_available;
}
async function refresh(){
  const wasRunning=state?.report_status.running;
  state=await(await api('/api/workspace')).json();$('auth').hidden=true;$('workspace').hidden=false;$('retry').hidden=true;
  renderPortfolio();renderStatus();
  if((wasRunning||generationPending)&&!state.report_status.running){notice(state.report_status.last_status==='failed'?text.failed:text.generated,state.report_status.last_status==='failed');generationPending=false;}
  const key=JSON.stringify([state.report_available,state.report_status.last_finished_at]);
  if(state.report_available&&key!==reportKey){reportHTML=await(await api('/api/workspace/report')).text();$('report-frame').srcdoc=reportDocument();$('report-frame').hidden=false;$('report-empty').hidden=true;reportKey=key;}
  clearTimeout(poll);poll=setTimeout(tick,state.report_status.running?1800:12000);
}
async function tick(){if(polling)return;polling=true;try{await refresh();}catch(e){notice(e.message,true);$('retry').hidden=false;}finally{polling=false;}}
async function mutate(change,button){
  button.disabled=true;
  try{await api('/api/workspace/portfolio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(change)});await refresh();notice(text.saved);return true;}
  catch(e){notice(e.message,true);return false;}finally{button.disabled=false;}
}
function reportDocument(){return '<!doctype html><html lang="'+document.documentElement.lang+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>quant.ai</title></head><body>'+reportHTML+'</body></html>';}
$('watch-form').addEventListener('submit',async e=>{e.preventDefault();const symbols=$('tickers').value.split(/[\s,，;；]+/).filter(Boolean);if(await mutate({action:'watchlist.add',symbols},e.submitter))$('watch-form').reset();});
$('holding-form').addEventListener('submit',async e=>{e.preventDefault();const position={symbol:$('symbol').value,shares:Number($('shares').value),cost_basis:$('cost').value?Number($('cost').value):null,note:$('holding-note').value||null};if(await mutate({action:'holding.set',position},e.submitter))resetHolding();});
$('cancel-edit').addEventListener('click',resetHolding);
$('generate').addEventListener('click',async()=>{$('generate').disabled=true;try{await api('/api/market-report',{method:'POST'});generationPending=true;notice(text.generating);await refresh();}catch(e){generationPending=false;notice(e.message,true);if(state)renderStatus();}});
$('auth').addEventListener('submit',async e=>{e.preventDefault();token=$('token').value;$('token').value='';try{await refresh();notice(text.ready);}catch(e){notice(e.message,true);}});
$('retry').addEventListener('click',async()=>{try{await refresh();notice(text.ready);}catch(e){notice(e.message,true);}});
$('download').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([reportDocument()],{type:'text/html;charset=utf-8'}));const link=element('a');link.href=url;link.download='quant-ai-'+(state.demo?'demo-':'')+(state.as_of_date||'brief')+'.html';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
for(const button of document.querySelectorAll('.copy'))button.addEventListener('click',async()=>{
  button.disabled=true;try{const brief=await(await api('/api/workspace/context')).text();const content=(state.demo?text.demo_prompt+'\n\n':'')+text[button.dataset.question]+'\n\n'+text.prompt_rule+'\n\n'+brief;
    try{await navigator.clipboard.writeText(content);$('manual-copy').hidden=true;notice(text.copied);}catch{$('copy-text').value=content;$('manual-copy').hidden=false;$('copy-text').focus();$('copy-text').select();notice(text.clipboard_error);}
  }catch(e){notice(e.message,true);}finally{renderStatus();}
});
refresh().then(()=>notice(text.ready)).catch(e=>{notice(e.message,true);$('retry').hidden=false;});
</script></body></html>'''
