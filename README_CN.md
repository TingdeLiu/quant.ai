# quant.ai

> **长在你 AI 助手里的美股量化研究工具。**
> 通过 [MCP](https://modelcontextprotocol.io) 接入 **Claude 或 Codex**，随口问任何一只股票——拿到可解释的评级、关键价位和判断依据，然后*就在同一个对话里继续讨论*。也可以当作一行命令的 CLI 使用。

[English](README.md) | 中文

[![CI](https://github.com/TingdeLiu/quant.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/TingdeLiu/quant.ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

`quant.ai` 是一个面向普通投资者的美股命令行量化研究工具箱。一行命令即可得到可解释的评级、支撑/止损参考位与判断依据——全部由历史价格计算，离线友好，不接任何券商。

> ⚠️ 仅供研究——**不构成投资建议**，永远不会提交或建议实盘订单。
> 输出**默认英文**；加 `--lang zh`（或在 `quant-ai init` 时选择）切换中文。

## 快速开始

```bash
pip install -e .          # 或：pip install -r requirements.txt
quant-ai doctor           # 环境自检（依赖 + 数据连通性）
quant-ai analyze AAPL     # 秒级评级一只股票
```

没有命令入口？`python -m quant_agent analyze AAPL` 效果相同。

## 你会得到什么

<img src="assets/analyze-example-zh.png" alt="quant-ai analyze AAPL --lang zh 的真实输出" width="820">

`quant-ai analyze AAPL --lang zh` 的真实输出——**默认英文**，`--lang zh` 切中文。评级从**强烈看多**经**中性**到**强烈看空**。加 `--output-dir` 导出 Markdown + JSON，或 `--chart` 输出 PNG 图表。

## 在 Claude 或 Codex 里使用

头号特性——把 quant.ai 暴露为 [MCP](https://modelcontextprotocol.io) server，让你的 AI 助手直接调用：

```bash
claude mcp add quant-research -- python -m quant_agent.mcp_server
```

然后在你日常工作的对话里直接问：

> *「NVDA 现在怎么看？」* · *「帮我关注特斯拉」* · *「我 182.5 买了 15 股苹果，帮我记着」* · *「我的持仓怎么样了？」* · *「生成今日美股报告」*

Claude（或 Codex）会调取项目的真实数据，把量化分析摆在你面前，你就地讨论——不用开网站，不用复制粘贴。每日报告**以你的持仓盈亏开篇**，并渲染成精致的 **HTML artifact**。Claude Desktop / Codex 配置详见[中文手册](docs/manual_zh.md#集成到-claudemcp)。

**让 AI 替你安装**——把下面这段丢给 Claude Code（或任何 AI CLI）即可搞定一切：

```text
把 https://github.com/TingdeLiu/quant.ai 安装为 MCP server：
1. git clone https://github.com/TingdeLiu/quant.ai && cd quant.ai
2. pip install -e .
3. claude mcp add quant-research -- python -m quant_agent.mcp_server
4. 用 `claude mcp list` 验证（应显示 quant-research ✓ connected）
```

## 亮点

- 🤖 **住在你的 AI 助手里——头号特性。** 把内置 MCP server 接进 **Claude 或 Codex**，问一句*「NVDA 现在怎么看？」*，它就会调取本项目的真实量化分析——**看结果和聊分析在同一个对话里完成**。多数股票分析工具是独立网站，这一个直接嵌在你天天在用的 AI 里。
- 💼 **对话管理自选与持仓。** 对 Claude 说*「帮我关注 NVDA」*或*「我 182.5 买了 15 股苹果」*——数据存在本地 `data/portfolio.json`，自动并入每一次分析，每日报告**以你的持仓与未实现盈亏开篇**（尽力取实时报价，降级用上一收盘价）。
- 🖼️ **Artifact 级每日报告**——市场简报以自包含、明暗双主题的 HTML 文件产出，Claude 直接渲染为内嵌 artifact；同时写出 Markdown 和 JSON 以备他用。
- 🎯 **零配置个股分析**——`analyze AAPL` 返回评级、区间收益、RSI、波动率、均线位置、支撑/止损参考位和人话版判断依据。
- 🧩 **个性化股票池**——`quant-ai init` 生成的股票池 **2/3 来自你的自选**（你关心的公司 + 板块），**1/3 由引擎**从更大的市场中发现。
- 🔬 **研究级回测**——横截面信号（12-1 动量、20/50 趋势、1 月反转、低波动）、信号权重搜索、**walk-forward** 稳定性分析，外加 SPY 与等权基准用来区分 alpha 和 beta。
- 📊 **本地控制台**——一页四个标签（报告 / 行情 / 回测诊断 / 运行），全部本地服务，整条链路不需要任何 API key。
- 🛡️ **安全设计**——确定性信号 + 风控层，网络/数据异常友好降级，仅纸面模拟——永远不提交真实订单。

## 每日报告与本地控制台

`quant-ai market-report` 生成每日美股研究简报，Anthropic 风格设计，一次产出四份：完整 HTML 页、自包含 artifact 片段、Markdown 和 JSON。报告是一页四个标签——**持仓**、**大盘**、**机会**、**资讯**——切换是纯 CSS，所以在 AI 客户端的沙箱 artifact 里照样点得动。

### 持仓——你的仓位排在最前

<img src="assets/report-holdings-zh.png" alt="每日报告 · 持仓页——盈亏表与每只持仓的画像卡片" width="820">

简报以你的盈亏开篇：总市值、未实现盈亏、当日盈亏，每个仓位一条走势折线（实时价尽力取，取不到降级用上一收盘价）。紧跟着的**持仓标的画像**给每只持仓一张卡片：仓位占比、趋势状态、近 5 日 / 1 月 / 3 月收益、年化波动、近一年最大回撤、距 52 周高点、相对基准强弱、卖方分析师估值区间、在量化榜单里的名次、近期资讯，以及可点开的 1W–5Y 收盘走势图。

这一段刻意只到事实为止：**不含买卖建议、不含价格预测**，并有测试盯着措辞不许漂移。它是研究工具而不是持牌顾问——把证据摆齐，决定留给你自己。

每只持仓的资讯归纳是**手写的，从 `data/news_digest.json` 读取**（`{as_of, digests: {代码: "一句话"}}`）——项目不为此调用任何 LLM API。当这份文件的 `as_of` 早于报告的数据日时，卡片会自动标注「归纳截至 …」，旧归纳不会假装成当天的。

### 大盘——盘面到底在走什么

<img src="assets/report-market-zh.png" alt="大盘页——基准、VIX 风险计、市场广度、板块轮动、跨资产追踪" width="820">

不只是报一个指数点位：基准的当日 / 近 5 日 / 1 月 / 3 月涨跌，连同它距 52 周高点、回撤与波动；带近一年分位的 **VIX 风险计**；**市场广度**——近 5 日 / 1 月上涨占比、站上 20 日 / 50 日均线的占比，**只统计个股**，免得一堆指数 ETF 把读数系统性抬高；**板块轮动**——11 只 SPDR 行业 ETF 按近 1 月涨跌排序，并给出相对基准的超额；以及分成宽基指数、主题板块（半导体、AI）、跨资产（VIX、长期美债、黄金、美元、原油）三组的**基金追踪**，用来看钱在股票之外往哪儿去。

### 机会——量化推荐、潜力股与高风险

<img src="assets/report-picks-zh.png" alt="机会页——按持有周期的研究推荐、潜力股与高风险名单" width="820">

研究推荐按持有周期分成长线 / 中线 / 短线三栏，每只带机构估值区间条、当日涨跌、风险与置信标签——你已经持有的标的会置顶并高亮。下面的**潜力股**与**高风险**两张表则写清每只标的入选的统计理由。指数与板块 ETF 不进这两张榜。

### 本地控制台

`quant-ai serve-dashboard` 启动一页四标签的本地控制台——报告、行情、回测诊断、运行，直接复用报告的视觉，而不是另起一套。`write-dashboard` 则把回测诊断页单独写到该次 run 的目录旁。页面语言跟随配置里的 `language:`。

<img src="assets/console-example-zh.png" alt="本地控制台——回测诊断页" width="820">

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `quant-ai analyze AAPL MSFT NVDA` | 评级一只或多只股票 |
| `quant-ai analyze --file watchlist.txt` | 从文件读取代码并评级 |
| `quant-ai init` | 交互式生成个性化股票池 |
| `quant-ai analyze --watchlist` | 评级你的个性化股票池 |
| `quant-ai run-backtest --config configs/default.yaml` | 运行研究回测 |
| `quant-ai market-report` | 生成每日市场情报报告 |
| `quant-ai serve-dashboard` | 启动本地控制台（报告 / 行情 / 回测 / 运行） |
| `quant-ai doctor` | 环境自检 |

## 工作原理

1. **数据**——默认来自 Yahoo Finance（`yfinance`）的日线 OHLCV，也支持本地 CSV/Parquet。带缓存与校验。
2. **信号**——横截面、时点滞后的因子，逐日 z-score 标准化。
3. **组合与风控**——在持仓数/换手/流动性约束下生成确定性目标权重。
4. **评估**——train / validation / test 分段、walk-forward 窗口，以及基准相对指标（Sharpe、Sortino、Calmar、最大回撤、alpha/beta）。
5. **AI**——项目**自身不调用任何 LLM API**，只产出可核对的事实：量化统计、规则评级、第三方一致预期。综合与讨论交给挂载 MCP 的 AI 客户端完成，因此无需 API key、不产生额外费用，你与数据之间也不隔着第二个模型。

## 文档

- **完整中文手册：**[docs/manual_zh.md](docs/manual_zh.md)——详细配置、回测/walk-forward、dashboard API、MCP 集成、输出文件。
- **更新日志：**[CHANGELOG.md](CHANGELOG.md) · **贡献指南：**[CONTRIBUTING.md](CONTRIBUTING.md) · **路线图：**[roadmap.md](roadmap.md)

## 测试

```bash
python -m pytest      # 106 个测试，全程无网络
python -m ruff check quant_agent tests conftest.py
```

## 重要声明

本项目仅用于**量化研究与学习**。它分析历史价格并产出研究信号——**不构成投资建议**，也**不是**交易授权。市场有风险，决策需自负。

## 许可证

[MIT](LICENSE)
