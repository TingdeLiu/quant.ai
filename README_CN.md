# quant.ai 中文说明

[English](README.md) | **中文**

[![CI](https://github.com/Tyndall-Labs/quant.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Tyndall-Labs/quant.ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

> 面向普通股民的美股量化研究工具：一行命令分析个股，给出可解释的中文评级与关键价位。

**30 秒上手：**

```bash
pip install -e .          # 安装（或 pip install -r requirements.txt）
quant-ai doctor           # 环境自检：依赖与行情数据源是否就绪
quant-ai analyze AAPL     # 秒级给出评级与关键价位
```

> 装完先跑 `quant-ai doctor`：逐项检查 Python 版本、必需依赖（缺失则报错退出）、可选依赖（`pyarrow` / `matplotlib`，缺失仅提示），并拉取一次 SPY 行情确认网络可用。

> ⚠️ 仅做基于历史价格的量化研究分析，**不构成投资建议**，也不会产生任何下单指令。

---

`quant.ai` 是一个美股日线量化研究与回测 agent 原型。当前版本已经打通从数据读取、信号生成、组合构建、风险检查、回测评估、ML ranking、报告输出、纸面订单计划、本地 dashboard、API token 认证、操作审计日志到人工审批的基础闭环。

这个项目的定位是研究和验证，不是实盘交易系统。默认不会提交真实订单；AI/LLM 只用于研究审阅、报告解释和风险提示，不直接生成 broker order。

## 项目已经完成了什么

### 研究与回测主流程

- 支持从 `yfinance` 下载美股日线数据。
- 支持本地 CSV、Parquet 单文件数据源。
- 支持本地 CSV、Parquet 目录数据源，并可按文件名推断单标的 `symbol`。
- 支持从 `configs/universe_default.csv` 读取默认股票池。
- 标准化 OHLCV 字段，并输出数据质量检查。
- 生成基础量化信号：
  - 12-1 momentum。
  - 20/50 moving-average trend。
  - 1-month reversal。
  - 20-day low-volatility score。
  - 可选 ML ranking signal。
- 支持通过 `strategy.signal_weights` 配置信号权重。
- 构建 long-only、top N、月度调仓、等权配置组合。
- 执行风险检查：
  - 最大持仓数。
  - 最大单票权重。
  - long-only。
  - 最大换手。
  - 最小流动性阈值配置。
- 执行 close-to-close 研究级回测。
- 计入交易成本和滑点。
- 输出 SPY benchmark 和默认股票池等权 baseline。
- 输出 CAGR、Sharpe、Sortino、Calmar、最大回撤、波动率、胜率、换手、beta、alpha、information ratio、持仓周期等指标。

### 分类型研究买入候选

- 每次回测会基于最新可用日线数据输出研究候选名单，不构成投资建议或实盘交易授权。
- 支持五类候选：
  - `long_term`: 长期，侧重 12-1 动量、趋势和低波动。
  - `swing`: 波段，侧重 20/50 趋势、1 月反转和动量。
  - `short_term`: 短期，侧重 1 月反转、短趋势和近期分数。
  - `defensive`: 防守，侧重低波动和趋势稳定性。
  - `aggressive`: 激进，侧重高动量、高趋势和 ML rank。
- 输出总表 `recommendations.csv` 和分类型文件 `recommendations_<type>.csv`。
- 输出字段包括 rank、symbol、recommendation_score、confidence、risk_level、target_weight、research_weight、latest_price、data_date 和 reason。

### 信号诊断与权重优化

- 输出单信号诊断：`signal_diagnostics.csv`。
- 使用 train/validation period 做候选信号权重搜索。
- 只用 validation period 选择推荐权重，避免用 test period 调参。
- 输出推荐权重：`recommended_signal_weights.json`。
- 用推荐权重单独跑 recommended strategy。
- 输出 recommended strategy 的 equity、positions、trades 和 period metrics。
- 支持多窗口 walk-forward 信号搜索。
- 输出 walk-forward 稳定性排名：`walk_forward_stability.csv`。
- 输出 walk-forward 聚合推荐权重：`walk_forward_recommended_signal_weights.json`。
- 提供 `write-recommended-config` 命令，把推荐权重写成独立配置。
- 提供 `compare-reports` 命令，对多个策略报告做横向对比。
- 输出 comparison CSV、Markdown、SVG 图表和 HTML 汇总页。

### ML ranking 基础版

- 基于技术特征训练 Ridge ranking signal。
- 支持配置：
  - `model_version`
  - `feature_version`
  - `prediction_horizon_days`
  - `train_period`
- 输出：
  - `ml_feature_matrix.csv`
  - `ml_predictions.csv`
  - `ml_diagnostics.json`
- ML signal 进入同一套组合构建、风险检查和权重搜索流程，不绕过风控层。

### 每日美股市场情报报告

- 在控制台点击「生成今日美股分析报告」按钮，或运行 `market-report` 命令，即可生成一份当日美股研究简报。
- 数据来源为免费、无需 API key 的公开渠道：
  - 财经媒体 RSS 头条（默认 Yahoo Finance、CNBC、MarketWatch、Investing.com）。
  - 重点个股最新资讯（基于 yfinance 个股新闻）。
  - 可选 X / 社交平台 RSS 源，默认关闭。
- 报告内容基于项目已有的量化信号和历史价格统计，明确区分：
  - 「相对值得关注」研究候选：趋势向上、近月为正、波动相对可控、接近高点。
  - 「高风险」标的：高波动、深回撤、近期急跌或显著低于 52 周高点。
  - 分类型量化候选（长期 / 波段 / 短期 / 防守 / 激进）。
- 当 `llm.enabled` 且配置了 API key 时，会用大模型把新闻和量化数据综合成自然语言分析；否则回落到结构化模板，无需任何 key 也能用。
- 输出文件：`market_intel.json`、`market_intel.md`、`market_intel.html`。
- HTML 报告采用 Anthropic / Claude 品牌视觉（暖米白底、赤陶橙点缀、Poppins 标题 + Lora 正文、绿涨橙红跌），核心板块为「按持有周期的研究推荐」（长线 / 中线·波段 / 短线 / 防守 / 激进），每只标的带价格、强度条和信号依据。
- 严格定位为研究，不构成投资建议，也不会生成任何下单指令或实盘授权。

### Markets 实时分析仪表盘

- 本地服务提供一个交互式仪表盘 `/markets`，使用 Claude Design 导出的 Tyndall Markets 设计（Anthropic 品牌设计系统），由 React 在浏览器内渲染。
- 包含：股票搜索、价格图、关键指标、AI 分析师面板（评级 + 摘要 + 多空论点 + 追问输入框）、自选股和每日简报。
- 全部内容由项目真实量化数据驱动（`/api/markets-data`）：评级、摘要、多空论点均从横截面信号和价格统计派生；无外部 key、无下单能力，纯研究展示。
- 设计文件 vendored 在 `quant_agent/web/`，相对路径结构保持原样，因此该 UI 在 Claude Design 中也能独立打开（缺少真实数据时回落到内置占位数据）。

### LLM 研究审阅基础版

- 默认使用离线模板审阅，不需要 API key 也能运行。
- 可选 OpenAI-compatible chat completions client。
- 缺少 API key 或请求失败时自动回落离线模板。
- 保存 prompt version、model、input hash、output hash 等元数据。
- 明确限制 LLM 只做研究摘要、风险提示、因子假设和异常检查建议。
- 拦截明显 broker/order 指令化输出。

### 数据质量、告警和通知

- 输出数据质量报告：
  - `data_quality.json`
  - `data_quality.md`
  - `data_quality_by_symbol.csv`
- 检查 stale data、missing universe symbols、point-in-time 元数据和 corporate action 元数据。
- 输出告警文件：
  - `alerts.json`
  - `alerts.csv`
  - `alerts.md`
- 告警覆盖：
  - 最大回撤突破阈值。
  - Sharpe 低于阈值。
  - risk check 失败。
  - stale price rows。
  - missing universe symbols。
  - point-in-time 元数据缺失。
  - paper order plan 未审批。
- 支持通知 outbox：
  - `notifications.json`
  - `notifications.csv`
  - `notification_outbox.json`
  - `notification_outbox.csv`
- 支持可选 webhook channel，通过环境变量读取 webhook URL。

### 纸面交易与人工审批基础版

- 实现 broker 抽象接口。
- 实现 PaperBroker 预览/受控提交模拟器。
- 从 target positions 和 current positions 生成 proposed orders。
- 支持 current positions CSV 输入。
- 支持 max order notional 和 gross notional 风控检查。
- 输出：
  - `proposed_orders.csv`
  - `paper_trading_audit.json`
- 支持 dashboard API approve/reject。
- 审批通过后输出：
  - `paper_order_approval.json`
  - `broker_preview.csv`
- 默认不提交真实订单，`allow_broker_submit_after_approval` 默认为 `false`。

### 本地 dashboard 与服务端

- 可生成静态 HTML dashboard：`dashboard.html`。
- dashboard 展示：
  - 关键指标。
  - 分段指标。
  - risk checks。
  - data quality。
  - paper trading checks。
  - equity curve。
  - positions。
  - trades。
  - proposed orders。
- 提供本地服务入口：`serve-dashboard`。
- 本地服务支持：
  - 查看运行状态。
  - 查看报告文件。
  - 触发新回测。
  - 查看 run history。
  - 查看 alerts、notifications 和 audit。
  - 对纸面订单执行 approve/reject。
- 每次服务端触发运行都会生成独立 run 目录：
  - `reports/full_roadmap/runs/<run_id>/`
- 服务端维护：
  - `reports/full_roadmap/service/runtime_status.json`
  - `reports/full_roadmap/service/run_history.json`
- 支持配置化定时运行基础版。
- 已实现 API token 认证：
  - 前端输入 token。
  - 服务端校验 `Authorization: Bearer <token>` 或 `X-API-Token`。
- 已实现 dashboard 操作审计日志：
  - `reports/full_roadmap/service/dashboard_audit.jsonl`
  - 记录触发回测、approve/reject 和未授权 API 访问。

## 项目目录结构

```text
quant.ai/
  quant_agent/                 核心 Python 包
    cli.py                     Typer CLI 入口
    config.py                  配置结构和解析
    data.py                    数据读取与缓存
    features.py                信号生成
    portfolio.py               组合构建
    risk.py                    风控检查
    backtest.py                回测引擎
    metrics.py                 绩效指标
    optimization.py            信号权重搜索和 walk-forward
    ml.py                      ML ranking signal
    llm.py                     LLM 审阅 client
    paper.py                   纸面订单计划
    broker.py                  Broker/PaperBroker
    alerts.py                  告警
    notifications.py           通知 outbox/webhook
    approvals.py               纸面订单审批
    dashboard.py               静态 dashboard 生成
    server.py                  本地 dashboard 服务
    reports.py                 报告输出
  configs/
    default.yaml               默认研究回测配置
    full_roadmap.yaml          打开 roadmap 基础闭环的配置
    recommended.yaml           推荐权重配置
    walk_forward_recommended.yaml
    universe_default.csv       默认股票池
  reports/                     输出目录
  tests/                       pytest 测试
  reference/                   研究参考资料
  roadmap.md                   项目路线图
```

## 环境安装

推荐使用 conda 环境：

```powershell
conda env create -f environment.yml
conda activate quant-ai
```

如果环境已经存在：

```powershell
conda env update -n quant-ai -f environment.yml --prune
conda activate quant-ai
```

如果 Windows 终端找不到 `conda`，可以在 Anaconda Prompt 里执行，或者用你本机 Miniconda/Anaconda 安装目录下的 `conda` 可执行文件（把下面的 `<你的 miniconda 路径>` 换成实际路径）：

```powershell
<你的 miniconda 路径>\Scripts\conda.exe env update -n quant-ai -f environment.yml --prune
```

也可以用 `requirements.txt` 安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

## 快速开始

### 最快上手：分析一只股票（零配置，秒级）

无需配置股票池、无需跑回测，直接分析任意美股：

```powershell
python -m quant_agent analyze AAPL
python -m quant_agent analyze AAPL MSFT NVDA --output-dir reports/analyze
```

输出包含：最新价、各周期涨跌（1/3/6 月、1 年）、RSI、年化波动率、均线位置（MA20/50/200）、中文评级（强烈看多 / 偏多 / 中性 / 偏空 / 强烈看空）、判断依据，以及参考关注位（支撑 / 止损）。

> 仅为基于历史价格的量化研究分析，不构成投资建议，也不会产生任何下单指令。

### 个性化股票池：`quant-ai init`

第一次使用时跑一次交互式引导，按你的兴趣搭一份个性化股票池：

```powershell
python -m quant_agent init
```

会问三个问题——感兴趣的**板块**、额外关注的**公司**、**风险偏好**（长线 / 波段 / 短线 / 防守 / 激进），然后生成股票池：

- **2/3 来自你的自选**：点名的公司 + 所选板块的代表股；
- **1/3 由系统发现**：在全市场候选目录 `configs/catalog.csv`（约 170 只流动美股，按中文板块归类）里，按风险偏好对应的横截面信号打分，挑出你**没选到**的强势标的。

生成物（均已 gitignore）：

- `configs/my_universe.csv`：最终股票池，`source` 列标注 `picked`（点名）/ `sector`（板块）/ `discovery`（发现）。
- `configs/my.yaml`：指向该股票池的配置，可直接喂给其它命令。
- `configs/profile.json`：保存的偏好，供 `refresh-universe` 复用。

之后：

```powershell
python -m quant_agent analyze --watchlist                          # 分析个性化股票池
python -m quant_agent market-report --config configs/my.yaml       # 用它生成每日市场简报
python -m quant_agent refresh-universe                              # 行情更新后重算发现池 1/3（自选不变）
```

脚本化/无人值守：

```powershell
python -m quant_agent init --non-interactive `
  --sector 半导体 --sector 医疗健康 --ticker AAPL --risk 波段
```

加 `--no-discovery` 跳过联网评估、只写自选部分。无网络时也会自动降级（只写自选并提示，联网后用 `refresh-universe` 补全），不会抛堆栈。

### 运行默认回测

```powershell
python -m quant_agent run-backtest --config configs/default.yaml
```

输出目录：

```text
reports/latest/
```

重点查看：

```text
reports/latest/summary.md
reports/latest/audit.json
reports/latest/dashboard.html
```

运行全功能基础版：

```powershell
python -m quant_agent run-backtest --config configs/full_roadmap.yaml
```

当前报告快照输出目录：

```text
reports/full_roadmap/current/
```

## 常用命令

### 个性化股票池

```powershell
quant-ai init                                          # 交互式引导，生成个性化股票池（2/3 自选 + 1/3 发现）
quant-ai init --non-interactive --sector 半导体 --ticker AAPL --risk 波段  # 脚本化
quant-ai refresh-universe                              # 行情更新后重算发现池 1/3
```

### 快速分析个股（零配置）

```powershell
quant-ai analyze AAPL                                  # 单只（pip install 后可用 quant-ai 命令）
quant-ai analyze AAPL MSFT NVDA                        # 多只
quant-ai analyze --watchlist                           # 分析个性化股票池 configs/my_universe.csv
quant-ai analyze --file watchlist.txt                  # 从自选股文件读取（每行一个或逗号分隔，# 为注释）
quant-ai analyze AAPL --output-dir reports/analyze     # 导出 md+json
quant-ai analyze AAPL --output-dir reports/analyze --chart  # 额外导出价格+均线+RSI 的 PNG
quant-ai analyze AAPL --json                           # 仅 JSON，便于脚本调用
quant-ai analyze AAPL --config configs/default.yaml    # 附带 AI 综合解读（需配置 LLM）
```

> 未安装命令入口时，把上面的 `quant-ai` 换成 `python -m quant_agent` 即可，效果相同。

### 运行回测

```powershell
python -m quant_agent run-backtest --config configs/default.yaml
python -m quant_agent run-backtest --config configs/full_roadmap.yaml
```

### 生成数据质量报告

```powershell
python -m quant_agent data-quality --config configs/default.yaml --output-dir reports/data_quality
```

### 生成纸面订单计划

```powershell
python -m quant_agent plan-paper-orders --config configs/full_roadmap.yaml --output-dir reports/full_roadmap/paper
```

如果有当前持仓文件：

```powershell
python -m quant_agent plan-paper-orders `
  --config configs/full_roadmap.yaml `
  --current-positions data/current_positions.csv `
  --output-dir reports/full_roadmap/paper
```

当前持仓 CSV 至少应包含系统能识别的 symbol/position 字段，具体可参考 `quant_agent/paper.py`。

### 生成每日美股市场情报报告

```powershell
python -m quant_agent market-report --config configs/full_roadmap.yaml
```

输出（默认写入 `report.output_dir`，便于 dashboard 文件列表直接展示）：

```text
market_intel.html    可读 HTML 报告
market_intel.md      Markdown 报告
market_intel.json    结构化数据
```

也可以在本地服务页面点击「生成今日美股分析报告」按钮触发，完成后点「打开美股分析报告」查看。

### 生成 dashboard HTML

```powershell
python -m quant_agent write-dashboard reports/full_roadmap/current --output reports/full_roadmap/current/dashboard.html
```

### 生成推荐权重配置

```powershell
python -m quant_agent write-recommended-config `
  --config configs/default.yaml `
  --weights reports/latest/recommended_signal_weights.json `
  --output configs/recommended.yaml

python -m quant_agent run-backtest --config configs/recommended.yaml
```

### 使用 walk-forward 推荐权重

```powershell
python -m quant_agent write-recommended-config `
  --config configs/default.yaml `
  --weights reports/latest/walk_forward_recommended_signal_weights.json `
  --output configs/walk_forward_recommended.yaml `
  --report-output-dir reports/walk_forward_recommended

python -m quant_agent run-backtest --config configs/walk_forward_recommended.yaml
```

### 生成多策略对比报告

```powershell
python -m quant_agent compare-reports `
  reports/latest `
  reports/recommended `
  reports/walk_forward_recommended `
  --output-dir reports/comparison
```

输出：

```text
reports/comparison/strategy_comparison.csv
reports/comparison/strategy_comparison.md
reports/comparison/equity_comparison.svg
reports/comparison/drawdown_comparison.svg
reports/comparison/index.html
```

## 启动本地 dashboard 服务

`configs/full_roadmap.yaml` 默认已**关闭** dashboard API token 认证（`dashboard_security.enabled: false`），本地单机直接启动即可：

```powershell
python -m quant_agent serve-dashboard --config configs/full_roadmap.yaml --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

无需输入 token，即可查看状态、刷新报告文件、触发回测、生成美股分析报告、查看操作审计和执行纸面订单审批。

如需对外暴露服务，建议改回 `dashboard_security.enabled: true` 并设置 token，再启动：

```powershell
$env:QUANT_AGENT_DASHBOARD_TOKEN = "change-me-local-token"
python -m quant_agent serve-dashboard --config configs/full_roadmap.yaml --port 8765
```

启用后页面会要求输入与 `QUANT_AGENT_DASHBOARD_TOKEN` 相同的 API token。

`full_roadmap` 输出目录已经整理为：

```text
reports/full_roadmap/current/              当前最新报告快照
reports/full_roadmap/runs/<run_id>/         每次服务端触发运行的独立报告目录
reports/full_roadmap/service/               dashboard 服务状态和操作审计
reports/full_roadmap/notifications/         通知 outbox
reports/full_roadmap/paper/                 手动生成的纸面订单计划
```

服务端相关输出：

```text
reports/full_roadmap/service/runtime_status.json
reports/full_roadmap/service/run_history.json
reports/full_roadmap/service/dashboard_audit.jsonl
```

## Dashboard API

已启用 token 时，所有 `/api/*` 请求需要带 header：

```text
Authorization: Bearer <token>
```

也支持：

```text
X-API-Token: <token>
```

PowerShell 示例：

```powershell
$headers = @{ Authorization = "Bearer $env:QUANT_AGENT_DASHBOARD_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8765/api/status -Headers $headers
Invoke-RestMethod http://127.0.0.1:8765/api/run -Method Post -Headers $headers
Invoke-RestMethod http://127.0.0.1:8765/api/operation-audit -Headers $headers
```

当前 API：

```text
GET  /api/status
GET  /api/audit
GET  /api/files
GET  /api/alerts
GET  /api/notifications
GET  /api/runs
GET  /api/runs/<run_id>
GET  /api/runs/<run_id>/approval
GET  /api/runs/<run_id>/alerts
GET  /api/operation-audit
GET  /api/market-report
GET  /api/market-report/status
POST /api/market-report
GET  /market-report
GET  /api/markets-data
GET  /markets
GET  /m/<asset>
POST /api/run
POST /api/runs/<run_id>/approve-paper
POST /api/runs/<run_id>/reject-paper
GET  /dashboard
GET  /report/<file>
GET  /runs/<run_id>/dashboard
```

## 集成到 Claude（MCP）

项目提供一个本地 MCP（Model Context Protocol）server，把研究能力暴露为工具，让 Claude 桌面端 / Claude Code 用自然语言驱动。设计理念是 **项目当「工具 + 数据」层，Claude 当「分析大脑」**。所有工具均为只读 / 研究导向，**不暴露任何下单、纸面订单审批或实盘授权能力**。

启动（stdio）：

```powershell
python -m quant_agent.mcp_server
```

可用工具（均为 `quant_` 前缀）：

```text
quant_get_markets_data        逐标的的 AI 研究解读（评级 + 摘要 + 多空 + 关键指标）
quant_get_recommendations     按持有周期的研究候选（长线/波段/短线/防守/激进）
quant_generate_market_report  生成每日美股研究简报（新闻 + 量化）
quant_get_market_news         最新财经媒体头条
quant_run_backtest            运行研究回测并返回核心指标
quant_data_quality            数据质量摘要
quant_list_reports            列出报告目录文件
quant_read_report             读取单个报告文件
```

### 在 Claude Desktop 中注册

编辑 `claude_desktop_config.json`，加入（把 `command` 换成 quant-ai 环境里的 python 路径，`cwd` 换成你的项目路径）：

```json
{
  "mcpServers": {
    "quant-research": {
      "command": "<你的 conda 环境>\\python.exe",
      "args": ["-m", "quant_agent.mcp_server"],
      "cwd": "<你的项目路径>"
    }
  }
}
```

> 提示：环境内 python 路径可用 `python -c "import sys; print(sys.executable)"` 查询。

### 在 Claude Code 中注册

在项目目录下执行（同样用环境内的 python）：

```powershell
claude mcp add quant-research -- "<你的 conda 环境>\python.exe" -m quant_agent.mcp_server
```

注册后即可直接对 Claude 说「看看 NVDA 的研究解读」「今天有哪些适合长线的候选」「生成今日美股简报」，Claude 会调用对应工具、拿到项目真实量化数据再做分析。所有结论均为研究信号，不构成投资建议。

数据时效：价格数据缓存超过 `data.cache_ttl_hours`（默认 6 小时）会自动刷新到最新交易日，所以正常调用就是当前数据。若想强制立即拉取最新，可让 Claude 在调用时带上 `refresh: true`（如「刷新数据后生成今日简报」），相关工具会忽略缓存重新下载。

## 核心配置说明

### 数据源

默认使用 `yfinance`：

```yaml
data:
  source: yfinance
  start: "2020-01-01"
  end: null
  cache_dir: data/cache
  universe_path: configs/universe_default.csv
  cache_ttl_hours: 6        # 开放区间(end=null)缓存超过该小时数自动重新下载；null 表示永不过期
```

关于数据时效：当 `end: null`（拉到最新）时，yfinance 缓存会在超过 `cache_ttl_hours`（默认 6 小时）后自动刷新到最新交易日，因此正常调用不会停留在旧日期。`end` 写成固定日期时缓存视为不可变历史、永不过期。MCP 工具还支持 `refresh: true` 参数强制立即重新下载（较慢，按需使用）。

读取本地 CSV：

```yaml
data:
  source: csv
  path: data/prices.csv
```

读取本地 Parquet：

```yaml
data:
  source: parquet
  path: data/prices.parquet
```

读取本地目录：

```yaml
data:
  source: local
  path: data/local_prices
```

价格数据标准字段：

```text
date,symbol,open,high,low,close,adj_close,volume
```

### 策略信号

```yaml
strategy:
  benchmark: SPY
  top_n: 5
  rebalance_frequency: M
  initial_cash: 100000
  transaction_cost_bps: 10
  slippage_bps: 5
  signal_weights:
    momentum_12_1: 1.0
    trend_20_50: 1.0
    reversal_1m: 1.0
    low_volatility: 1.0
    ml_rank: 1.0
```

### 风控

```yaml
risk:
  max_position_weight: 0.25
  max_positions: 5
  min_avg_dollar_volume: 10000000
  max_turnover: 2.0
  long_only: true
```

### 分段评估

```yaml
evaluation:
  periods:
    - name: train
      start: "2020-01-01"
      end: "2022-12-31"
    - name: validation
      start: "2023-01-01"
      end: "2024-12-31"
    - name: test
      start: "2025-01-01"
      end: null
```

### 权重搜索和 walk-forward

```yaml
optimization:
  enabled: true
  train_period: train
  validation_period: validation
  objective: sharpe
  max_drawdown_floor: -0.5
  walk_forward_enabled: true
```

### ML ranking

```yaml
ml:
  enabled: true
  train_period: train
  prediction_horizon_days: 21
  model_version: ridge_v1
  feature_version: technical_v1
```

### LLM 审阅

默认关闭：

```yaml
llm:
  enabled: false
  provider: openai-compatible
  model: gpt-4.1-mini
  endpoint: null
  api_key_env: OPENAI_API_KEY
  prompt_version: research_review_v1
```

启用时：

```yaml
llm:
  enabled: true
  api_key_env: OPENAI_API_KEY
```

如果没有设置 API key，系统会回落到离线模板审阅。

### Dashboard 安全

`configs/full_roadmap.yaml` 当前配置：

```yaml
dashboard:
  service_dir: reports/full_roadmap/service
  runs_dir: reports/full_roadmap/runs

dashboard_security:
  enabled: false   # 本地默认关闭；对外暴露时改为 true 并设置 token_env
  token_env: QUANT_AGENT_DASHBOARD_TOKEN
  audit_log_path: reports/full_roadmap/service/dashboard_audit.jsonl
```

启用认证后，不要把真实 token 写进配置文件。推荐使用环境变量：

```powershell
$env:QUANT_AGENT_DASHBOARD_TOKEN = "your-local-secret"
```

## 输出文件说明

默认回测输出到：

```text
reports/latest/
```

全功能基础版当前报告快照输出到：

```text
reports/full_roadmap/current/
```

服务状态和历史运行输出到：

```text
reports/full_roadmap/service/
reports/full_roadmap/runs/<run_id>/
```

常见输出文件：

```text
summary.md                                      人类可读研究摘要
audit.json                                      完整配置、指标、检查和输出清单
equity_curve.csv                                策略权益曲线
benchmark_equity.csv                            SPY benchmark 权益曲线
equal_weight_equity.csv                         默认股票池等权 baseline
positions.csv                                   持仓
trades.csv                                      交易记录
period_metrics.csv                              train/validation/test 分段指标
exposure_by_symbol.csv                          标的暴露
signal_diagnostics.csv                          单信号诊断
signal_weight_search.csv                        权重搜索结果
recommendations.csv                             分类型研究候选总表
recommendations.json                            分类型研究候选 JSON
recommendations_long_term.csv                   长期研究候选
recommendations_swing.csv                       波段研究候选
recommendations_short_term.csv                  短期研究候选
recommendations_defensive.csv                   防守型研究候选
recommendations_aggressive.csv                  激进型研究候选
recommended_signal_weights.json                 validation 推荐权重
recommended_equity_curve.csv                    recommended strategy 权益曲线
walk_forward_signal_search.csv                  walk-forward 搜索结果
walk_forward_stability.csv                      walk-forward 稳定性排名
walk_forward_recommended_signal_weights.json    walk-forward 聚合推荐权重
ml_feature_matrix.csv                           ML 特征矩阵
ml_predictions.csv                              ML 预测
ml_diagnostics.json                             ML 诊断
data_quality.json                               数据质量报告
alerts.json                                     告警
notifications.json                              通知记录
proposed_orders.csv                             纸面订单计划
paper_trading_audit.json                        纸面订单风控审计
paper_order_approval.json                       审批结果
broker_preview.csv                              PaperBroker 预览
dashboard.html                                  静态 dashboard
runtime_status.json                             本地服务运行状态
run_history.json                                本地服务运行历史
dashboard_audit.jsonl                           dashboard API 操作审计
```

如果你的 `reports/full_roadmap/` 目录里已经有旧版平铺输出，可以先保留不动；新运行会写入 `current/`、`service/` 和 `runs/`。确认新结构正常后，再把旧的根目录 CSV/JSON/HTML 报告移动到归档目录，例如 `reports/full_roadmap/archive_flat_legacy/`。

## 测试和验证

运行全部测试：

```powershell
python -m pytest
```

运行 Python 编译检查：

```powershell
python -m compileall -q quant_agent tests
```

当前测试覆盖：

- 数据标准化和数据质量。
- CSV 股票池解析。
- 本地 CSV/Parquet 数据源。
- 信号滞后和信号组合。
- 分类型研究买入候选输出。
- 风控约束。
- 完整 pipeline 输出。
- benchmark-relative 指标。
- train/validation/test 分段指标。
- 信号权重解析。
- 权重搜索和推荐权重。
- walk-forward 搜索和稳定性。
- ML ranking signal。
- 纸面订单计划和 PaperBroker。
- 通知 outbox。
- 纸面订单审批。
- dashboard runtime status。
- dashboard API token 鉴权。
- dashboard 操作审计日志。
- 多策略 comparison report。

## 当前限制

- 默认数据源 `yfinance` 适合原型研究，不保证生产级 point-in-time 正确性。
- 默认股票池是大型流动性标的样例，不是完整美股股票池。
- 还没有 survivorship-bias-free universe。
- 还没有完整基本面、新闻、财报电话会或 SEC filing 数据。
- 当前回测是研究级 close-to-close 模型，不是生产级事件驱动撮合。
- ML ranking 是基础版，没有模型注册中心、特征存储服务或漂移监控。
- LLM 审阅是基础版，没有多 provider 路由和完整人工审批工作流。
- PaperBroker 是模拟器，没有接入真实 broker API、完整订单生命周期或自动持仓对账。
- Dashboard 已有本地 API token 认证和操作审计，但不是多用户权限系统。
- 通知 outbox 和 webhook 是基础版，没有生产级投递重试、签名校验和告警升级策略。

## 推荐下一步

1. 接入更可靠的数据供应商，并建立 survivorship-bias-free universe。
2. 强化 point-in-time 数据治理、数据版本和数据质量阻断规则。
3. 把 PaperBroker 扩展成完整 broker sandbox，包括订单生命周期、成交回报和持仓对账。
4. 增加 dashboard 多用户权限、会话管理和更细粒度的操作审计。
5. 增加通知投递保障，包括 webhook 签名、重试、死信和告警升级。
6. 为 ML 增加模型注册、特征存储、漂移监控和可重复训练任务。
7. 为 LLM 审阅增加多 provider 路由、人工确认和更强的安全策略。

## 重要声明

本项目只用于工程研究和量化策略原型验证，不构成投资建议。任何真实交易都需要独立完成数据校验、合规审查、风险控制、broker sandbox 验证、人工审批和实盘监控。
