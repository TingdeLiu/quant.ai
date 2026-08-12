# CLAUDE.md

quant.ai：接入 Claude/Codex（MCP）的美股量化研究助手。**Research only** —— 永远不下单、不审批、不接券商；持仓是用户口述的记账数据，仅作研究上下文。

## 常用命令

```bash
python -m pytest                                   # 全部测试（离线，无网络）
python -m ruff check quant_agent tests conftest.py
python -m quant_agent.mcp_server                   # MCP server（stdio）
quant-ai market-report                             # 每日报告（默认 configs/my.yaml，存在时）
```

## 架构速览

- `config.py` — frozen dataclass 体系；`parse_config(raw, base)`；路径一律 `_resolve_path(base, ...)` 解析。`portfolio_path` 默认 `data/portfolio.json`。
- `data.py` — 滚动价格数据库：按 universe 哈希键控的 CSV（`data/cache/prices_{n}_{hash}.csv`），每日至多刷新一次、≤10 年、按标的增量追加；universe 变化时从旧缓存播种（`_seed_from_sibling_caches`），不整库重下。
- `holdings.py` — 聊天管理的自选/持仓存储（`data/portfolio.json`，原子写；损坏 JSON 必须报错而非返回空，防止后续保存毁数据）；`apply_portfolio_universe` 把用户标的叠加进 universe；`build_holdings_snapshot` 算盈亏（实时价尽力取、降级最新收盘）。
- `market_intel.py` — 每日报告：`build_market_report`（payload）+ 三个渲染器 `render_markdown` / `render_html`（整页，允许网络字体）/ `render_artifact_html`（自包含片段，零外链，明暗双主题）。三者共享 `_html_*` section 构建器；持仓段永远排第一。
- `console.py` — 本地服务的统一控制台（`/`）：报告 / 行情 / 回测 / 运行 四个标签页，复用 `market_intel.report_css()` 与 `build_tabs()`，不自带视觉。同一文件的 `write_dashboard()` 生成每次 run 的存档诊断页（`/runs/<id>/dashboard` 用）。**内嵌报告时外层标签页必须换 `group` 名**（radio 的 `name` 全局互斥，同名会互相清掉选中态）。
- `mcp_server.py` — FastMCP，10 个 `quant_*` 工具。约定：pydantic 输入模型继承 `_Base`（`extra="forbid"`）、async + `asyncio.to_thread`、异常统一 `_err()` 返回 `{"error": ...}`；`_load()` 统一叠加 portfolio universe。

## 项目约定

- **项目不调用任何 LLM API**。服务端只产出可核对的事实：量化统计、规则评级、第三方一致预期、手写归纳。综合、叙述、对话一律交给挂载 MCP 的宿主客户端 —— 那里已经是更强的模型，服务端再调一次是质量倒挂加额外成本。没有 `llm.py`、没有 `LLMConfig`、没有 `/api/chat`，也不要加回来。
- **测试必须离线**，由 `conftest.py` 的 autouse fixture 强制（外部 DNS/connect 一律 OSError，仅放行回环给 dashboard 的本地 HTTP server）。写测试时仍要主动关掉取数，否则只是从"等超时"变成"走降级分支"：`data.source=csv` + `tests/_helpers._synthetic_prices()`；`market_intel: {news_feeds: [], social_enabled: false, symbol_news_count: 0}`（**个股新闻不受 `news_feeds: []` 约束，必须单独置 0**）；实时价与估值用注入或 monkeypatch（`quant_agent.holdings.fetch_live_quotes`、`quant_agent.market_intel.fetch_analyst_price_targets`）—— MCP 工具内部不注入 fetcher，测它必须 monkeypatch。无 pytest-asyncio，MCP 工具测试用 `asyncio.run()` 直调。
- **双语**：面向用户的字符串用 `tr(en, zh, lang)`（`i18n.py`），英中并排书写。
- **报告即 artifact**：生成报告后按 MCP instructions 呈现 —— 有文件访问时直接发布 `artifact_html_path`；否则 `quant_read_report('market_intel_artifact.html')` 取 HTML；最后才用 `report_markdown`。免责声明必须保留。
- **持仓画像段不给方向**：`holding_profiles` 只摆客观统计与第三方一致预期，**不含买卖建议、不含价格预测**（有测试盯着措辞）。用户要买卖建议时说明这是持牌顾问的事，改代码也不解除；能给的是情景分析、集中度量化、回测他自己的规则。
- **持仓资讯归纳是手写的**：助手把总结写进 `data/news_digest.json`（`{as_of, digests:{SYMBOL: 一句话}}`，与 portfolio 同目录、已 gitignore），报告读取渲染。`as_of` 与报告数据日不一致时，卡片自动标「归纳截至 X」，旧归纳不会假装成当天的。每次更新报告都要一并重写这份文件。
- `data/portfolio.json` 只经 `holdings.py` / 两个 MCP 管理工具读写；它是叠加层，`refresh-universe` 重新生成 `my_universe.csv` 不影响它。
