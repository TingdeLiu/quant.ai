# quant.ai

> 面向普通股民的美股量化研究工具：**一行命令分析个股**，给出可解释的中文评级与关键价位。

[![CI](https://github.com/Tyndall-Labs/quant.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Tyndall-Labs/quant.ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

完整中文使用说明见 [README_CN.md](README_CN.md)。

## 30 秒上手

```bash
pip install -e .            # 安装（或 pip install -r requirements.txt）
quant-ai doctor             # 环境自检：依赖是否齐全、行情数据源是否连通
quant-ai analyze AAPL       # 分析一只股票，秒级出评级与关键价位
```

没装好命令入口也可以用 `python -m quant_agent analyze AAPL`，效果相同。装完先跑一次 `quant-ai doctor`：它会逐项检查 Python 版本、必需依赖（缺失会报错退出，退出码 1）和可选依赖（`pyarrow` 读 Parquet、`matplotlib` 出图，缺失只提示），并尝试拉取一次 SPY 行情确认网络/代理可用。

## 个性化股票池：`quant-ai init`

第一次使用时，跑一次交互式引导，按你的兴趣搭一份**个性化股票池**：

```bash
quant-ai init
```

它会问你三个问题——感兴趣的**板块**、额外关注的**公司**、**风险偏好**（长线 / 波段 / 短线 / 防守 / 激进），然后生成一份股票池：

- **2/3 来自你的自选**：你点名的公司 + 你选中板块的代表股；
- **1/3 由系统发现**：在全市场候选目录（`configs/catalog.csv`，约 170 只流动美股）里，按你的风险偏好对应的横截面信号打分，挑出你**没选到**的强势标的。

生成物（均已 gitignore，因人而异）：`configs/my_universe.csv`（带 `source` 标注 picked/sector/discovery）、`configs/my.yaml`（可直接喂给其它命令的配置）、`configs/profile.json`（你的偏好，供刷新复用）。之后：

```bash
quant-ai analyze --watchlist                       # 分析你的个性化股票池
quant-ai market-report --config configs/my.yaml    # 用它生成每日市场简报
quant-ai refresh-universe                           # 行情更新后，重算「发现池」1/3（自选不变）
```

脚本化/无人值守可用 `quant-ai init --non-interactive --sector 半导体 --sector 医疗健康 --ticker AAPL --risk 波段`；加 `--no-discovery` 可跳过联网评估、只写自选部分。无网络时也会自动降级（只写自选部分并提示，联网后 `refresh-universe` 补全）。

> ⚠️ 本工具仅做基于历史价格的量化研究分析，**不构成投资建议**，也不会产生任何下单指令。

---

美股量化 agent v1：研究与回测原型。

v1 的边界很明确：

- 只做美股日线研究和回测。
- 默认数据源为 Yahoo Finance/yfinance。
- AI/LLM 只做研究审阅和报告解释，不直接产生交易指令。
- 交易由确定性的信号、组合构建和风控层生成。
- 默认股票池从 `configs/universe_default.csv` 读取，也可以在配置里改成自己的 CSV 股票池。

## 最快上手：分析一只股票（零配置）

不想配股票池、不想跑回测，只想知道某只美股现在的状态？一行命令即可：

```powershell
python -m quant_agent analyze AAPL
```

也可以一次分析多只，并把结果导出为 Markdown/JSON：

```powershell
python -m quant_agent analyze AAPL MSFT NVDA --output-dir reports/analyze
```

输出包含：最新价、各周期涨跌、RSI/波动率、均线位置、中文评级（强烈看多/偏多/中性/偏空/强烈看空）、判断依据和参考关注位（支撑/止损）。

> 仅为基于历史价格的量化研究分析，不构成投资建议，也不会产生任何下单指令。

如果在配置文件里填了 LLM 凭证，加 `--config configs/default.yaml` 还能附带一段 AI 综合解读。

## Quick Start

```powershell
conda env create -f environment.yml
conda activate quant-ai
python -m quant_agent run-backtest --config configs/default.yaml
```

If the environment already exists, update it with:

```powershell
conda env update -n quant-ai -f environment.yml --prune
```

If `conda` is not on PATH (common on Windows), run the commands from the Anaconda Prompt, or call the `conda` executable inside your Miniconda/Anaconda install directly (e.g. `<your-miniconda>\Scripts\conda.exe`).

输出写入 `reports/latest/`：

- `summary.md`
- `equity_curve.csv`
- `equal_weight_equity.csv`
- `benchmark_equity.csv`
- `positions.csv`
- `trades.csv`
- `exposure_by_symbol.csv`
- `signal_diagnostics.csv`
- `signal_weight_search.csv`
- `recommended_signal_weights.json`
- `recommended_equity_curve.csv`
- `recommended_period_metrics.csv`
- `recommended_positions.csv`
- `recommended_trades.csv`
- `walk_forward_signal_search.csv`
- `walk_forward_stability.csv`
- `walk_forward_recommended_signal_weights.json`
- `walk_forward_recommended_equity_curve.csv`
- `walk_forward_recommended_period_metrics.csv`
- `audit.json`
- `period_metrics.csv`

## Signals And Baselines

当前研究信号包括：

- 12-1 momentum。
- 20/50 moving-average trend。
- 1-month reversal。
- 20-day low-volatility score。

报告同时输出 SPY benchmark 和默认 universe equal-weight baseline，便于区分策略 alpha、市场 beta 和简单等权组合贡献。

信号权重可在配置中调整：

```yaml
strategy:
  signal_weights:
    momentum_12_1: 1.0
    trend_20_50: 1.0
    reversal_1m: 1.0
    low_volatility: 1.0
```

`signal_diagnostics.csv` 会把每个信号单独作为 score 回测，帮助判断哪些信号贡献或拖累组合。

`recommendations.csv` 和 `recommendations_<type>.csv` 会按长期、波段、短期、防守、激进输出研究买入候选。这些只是 research candidates，不是投资建议或实盘交易授权。

## Signal Weight Search

默认会用 train/validation periods 做一个小规模权重搜索：

```yaml
optimization:
  enabled: true
  train_period: train
  validation_period: validation
  objective: sharpe
  max_drawdown_floor: -0.5
```

搜索候选是所有非空信号组合的等权权重。推荐权重只根据 validation period 选择，不使用 test period 调参。输出：

- `signal_weight_search.csv`: 每个候选组合在 train/validation 上的表现。
- `recommended_signal_weights.json`: validation objective 最优且满足 drawdown 约束的推荐权重。

系统会用推荐权重单独跑一条 recommended strategy，并在 `summary.md` 中输出 test period 对比。当前推荐权重不会自动覆盖主策略配置；要采用它，可以生成一个独立推荐配置：

```powershell
python -m quant_agent write-recommended-config `
  --config configs/default.yaml `
  --weights reports/latest/recommended_signal_weights.json `
  --output configs/recommended.yaml
```

然后运行：

```powershell
python -m quant_agent run-backtest --config configs/recommended.yaml
```

也可以用 walk-forward 聚合推荐权重生成独立配置：

```powershell
python -m quant_agent write-recommended-config `
  --config configs/default.yaml `
  --weights reports/latest/walk_forward_recommended_signal_weights.json `
  --output configs/walk_forward_recommended.yaml `
  --report-output-dir reports/walk_forward_recommended

python -m quant_agent run-backtest --config configs/walk_forward_recommended.yaml
```

生成多策略对比报告：

```powershell
python -m quant_agent compare-reports `
  reports/latest `
  reports/recommended `
  reports/walk_forward_recommended `
  --output-dir reports/comparison
```

输出：

- `reports/comparison/strategy_comparison.csv`
- `reports/comparison/strategy_comparison.md`
- `reports/comparison/equity_comparison.svg`
- `reports/comparison/drawdown_comparison.svg`
- `reports/comparison/index.html`

默认还会执行多窗口 walk-forward 诊断：

```yaml
optimization:
  walk_forward_enabled: true
  walk_forward_windows:
    - name: wf_2022
      train_start: "2020-01-01"
      train_end: "2021-12-31"
      validation_start: "2022-01-01"
      validation_end: "2022-12-31"
```

输出：

- `walk_forward_signal_search.csv`: 每个候选权重在每个滚动窗口上的训练/验证表现。
- `walk_forward_stability.csv`: 按窗口胜率、平均验证表现和平均排名汇总的稳定性排名。
- `walk_forward_recommended_signal_weights.json`: 根据稳定性排名选出的聚合推荐权重。
- `walk_forward_recommended_period_metrics.csv`: 聚合推荐权重的 train/validation/test 分段表现。

## Universe CSV

默认配置使用：

```yaml
data:
  universe_path: configs/universe_default.csv
```

CSV 至少需要一列 `symbol`。如果没有表头，系统会读取第一列作为 ticker。重复 ticker 会自动去重并转成大写。

## Local CSV/Parquet Data

除了 `yfinance`，也可以使用本地价格文件，降低对外部下载的依赖。价格数据标准字段为：

```text
date,symbol,open,high,low,close,adj_close,volume
```

读取单个合并 CSV 文件：

```yaml
data:
  source: csv
  path: data/prices.csv
```

读取单个 Parquet 文件：

```yaml
data:
  source: parquet
  path: data/prices.parquet
```

读取目录中的多个 CSV/Parquet 文件：

```yaml
data:
  source: local
  path: data/local_prices
```

目录模式会递归读取 `.csv` 和 `.parquet` 文件。如果单标的文件没有 `symbol` 或 `ticker` 列，系统会用文件名补 symbol，例如 `data/local_prices/aapl.csv` 会推断为 `AAPL`。

可从样例配置开始：

```powershell
python -m quant_agent run-backtest --config configs/local_data_example.yaml
```

## Full Roadmap Baseline

`configs/full_roadmap.yaml` 打开了当前 roadmap 的基础闭环：

- ML ranking signal，输出 `ml_feature_matrix.csv`、`ml_predictions.csv`、`ml_diagnostics.json`。
- 数据质量报告，输出 `data_quality.json`、`data_quality.md`、`data_quality_by_symbol.csv`。
- 纸面交易订单计划，输出 `proposed_orders.csv` 和 `paper_trading_audit.json`；不会连接券商或提交订单。
- 本地 dashboard，输出 `reports/full_roadmap/current/dashboard.html`。
- 本地 dashboard 服务，提供运行状态、报告文件浏览和一键触发回测。
- 每日美股市场情报报告，输出 `market_intel.html` / `market_intel.md` / `market_intel.json`。
- 交互式 Markets 仪表盘 `/markets`（Claude Design 设计，真实量化数据驱动）。

运行：

```powershell
python -m quant_agent run-backtest --config configs/full_roadmap.yaml
```

也可以单独运行工具命令：

```powershell
python -m quant_agent data-quality --config configs/default.yaml --output-dir reports/data_quality
python -m quant_agent plan-paper-orders --config configs/full_roadmap.yaml --output-dir reports/full_roadmap/paper
python -m quant_agent write-dashboard reports/full_roadmap/current --output reports/full_roadmap/current/dashboard.html
python -m quant_agent market-report --config configs/full_roadmap.yaml
```

启动本地服务：

```powershell
$env:QUANT_AGENT_DASHBOARD_TOKEN = "change-me-local-token"
python -m quant_agent serve-dashboard --config configs/full_roadmap.yaml --port 8765
```

打开 `http://127.0.0.1:8765` 后可以查看运行状态、打开报告 dashboard、浏览报告文件，并触发一次新的回测任务。`configs/full_roadmap.yaml` 默认已关闭 API token 认证（`dashboard_security.enabled: false`），本地直接使用即可；如需对外暴露，可改回 `true` 并设置 `QUANT_AGENT_DASHBOARD_TOKEN`，服务端会校验 `Authorization: Bearer <token>` 或 `X-API-Token`。该服务不会提交真实订单。

### 每日美股市场情报报告

控制台首页点击「生成今日美股分析报告」按钮，或运行 `market-report` 命令，即可生成一份当日美股研究简报：

- 数据来源为免费、无需 API key 的公开渠道：财经媒体 RSS 头条（Yahoo Finance / CNBC / MarketWatch / Investing.com）、yfinance 个股新闻，以及可选的 X / 社交平台 RSS（默认关闭）。
- 内容基于项目已有的量化信号和历史价格统计，明确区分「相对值得关注」研究候选与「高风险」标的，并按持有周期给出推荐（长线 / 中线·波段 / 短线 / 防守 / 激进），每只标的带价格、强度条和信号依据。
- 配置了 `llm.enabled` + API key 时会用大模型综合成自然语言分析，否则回落到结构化模板。
- HTML 报告采用 Anthropic / Claude 品牌视觉（暖米白底、赤陶橙点缀、Poppins + Lora 字体、绿涨橙红跌）。
- 输出 `market_intel.html` / `market_intel.md` / `market_intel.json`，写入 `report.output_dir`，会出现在 dashboard 文件列表中。
- 仅用于研究，不构成投资建议，也不会生成任何下单指令或实盘授权。

### Markets 实时分析仪表盘

本地服务额外提供交互式仪表盘 `/markets`（控制台「打开 Markets 仪表盘」按钮）：

- 使用 Claude Design 导出的 Tyndall Markets 设计（Anthropic 品牌设计系统），React 在浏览器内渲染，设计文件 vendored 在 `quant_agent/web/`。
- 包含股票搜索、价格图、关键指标、AI 分析师面板（评级 + 摘要 + 多空论点 + 追问框）、自选股、每日简报。
- 数据由 `/api/markets-data` 提供，全部从项目真实横截面信号和价格统计派生；无外部 key、无下单能力，纯研究展示。

`full_roadmap` 输出目录已经整理为：

- `reports/full_roadmap/current/`: 当前最新报告快照。
- `reports/full_roadmap/runs/<run_id>/`: 每次服务端触发运行的独立报告目录。
- `reports/full_roadmap/service/`: dashboard 服务状态和操作审计。
- `reports/full_roadmap/notifications/`: 通知 outbox。
- `reports/full_roadmap/paper/`: 手动生成的纸面订单计划。

服务端运行会写入运行历史：

- `reports/full_roadmap/service/runtime_status.json`: 当前/最近一次运行状态。
- `reports/full_roadmap/service/run_history.json`: 最近运行记录，包含 `run_id`、时间、状态、核心指标和报告路径。
- `reports/full_roadmap/service/dashboard_audit.jsonl`: dashboard API 操作审计日志，记录触发回测、审批/拒绝纸面订单和未授权 API 访问。
- `reports/full_roadmap/runs/<run_id>/`: 每次运行的独立报告目录。
- `alerts.json` / `alerts.csv` / `alerts.md`: 风险、数据质量和订单审批告警。
- `notifications.json` / `notifications.csv`: 当前 run 触发的通知记录。
- `reports/full_roadmap/notifications/notification_outbox.json`: 文件通知 outbox。
- `paper_order_approval.json` / `broker_preview.csv`: 人工审批和 PaperBroker 预览结果。

相关 API：

```text
GET  /api/status
GET  /api/alerts
GET  /api/notifications
GET  /api/runs
GET  /api/runs/<run_id>
GET  /api/runs/<run_id>/approval
GET  /api/operation-audit
GET  /api/market-report
GET  /api/market-report/status
POST /api/market-report
GET  /market-report
GET  /api/markets-data
GET  /markets
GET  /m/<asset>
POST /api/runs/<run_id>/approve-paper
POST /api/runs/<run_id>/reject-paper
POST /api/run
GET  /runs/<run_id>/dashboard
```

PowerShell API example:

```powershell
$headers = @{ Authorization = "Bearer $env:QUANT_AGENT_DASHBOARD_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8765/api/status -Headers $headers
Invoke-RestMethod http://127.0.0.1:8765/api/run -Method Post -Headers $headers
```

Dashboard API security is configured under:

```yaml
dashboard:
  service_dir: reports/full_roadmap/service
  runs_dir: reports/full_roadmap/runs

dashboard_security:
  enabled: false   # 本地默认关闭；对外暴露时改为 true 并设置 token_env
  token_env: QUANT_AGENT_DASHBOARD_TOKEN
  audit_log_path: reports/full_roadmap/service/dashboard_audit.jsonl
```

如果 `reports/full_roadmap/` 里已经有旧版平铺输出，可以先保留不动；新运行会写入 `current/`、`service/` 和 `runs/`。确认新结构正常后，再把旧的根目录 CSV/JSON/HTML 报告移动到归档目录。

可以在配置里打开定时运行：

```yaml
schedule:
  enabled: true
  interval_minutes: 1440
  run_on_start: false
```

告警阈值也可以配置：

```yaml
alerts:
  enabled: true
  max_drawdown_floor: -0.35
  min_sharpe: 0.5
  max_stale_rows: 0
  require_paper_approval: true
```

通知 outbox 和审批流配置：

```yaml
notifications:
  enabled: true
  min_severity: warning
  channels:
    - file
  output_dir: reports/full_roadmap/notifications
  webhook_url_env: QUANT_AGENT_WEBHOOK_URL

approvals:
  require_manual_paper_approval: true
  allow_broker_submit_after_approval: false
```

`file` channel 会写入本地 outbox；`webhook` channel 会读取 `webhook_url_env` 指定的环境变量并发送 JSON。审批通过后只生成 PaperBroker preview；默认仍不提交订单。

LLM 审阅默认关闭。启用时使用 OpenAI-compatible chat completions 端点，并在失败或缺少 API key 时自动回落到离线模板审阅：

```yaml
llm:
  enabled: true
  provider: openai-compatible
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY
```

## Evaluation Periods

默认配置会输出 train/validation/test 分段指标：

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

这不是完整 ML rolling retrain；它先把分阶段评估和报告输出打通，后续模型训练会接入同一套 period 定义。

## Tests

```powershell
python -m pytest
```
