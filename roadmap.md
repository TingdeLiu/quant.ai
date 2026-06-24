# Quant Agent Roadmap

更新日期: 2026-06-14

## 当前状态

项目已经完成 v1 研究与回测原型，并打通 full roadmap 基础闭环。当前系统可以从 Yahoo Finance 或本地 CSV/Parquet 读取美股日线数据，生成基础量化信号和 ML ranking signal，构建 long-only 组合，执行风控检查，完成回测，输出研究审阅报告，生成纸面订单计划，并通过本地 dashboard 服务完成运行状态查看、API token 认证、操作审计和人工审批基础流程。

v1 明确不做纸面交易或实盘交易。AI/LLM 角色限定为研究审阅、解释和风险提示，不直接生成交易指令。

## 已完成工作

### 资料整理

- 新建 `reference/` 目录。
- 整理 AI 量化交易、美股交易 agent、回测和执行基础设施相关 GitHub 项目。
- 重点参考项目包括 Qlib、FinRL、LEAN、FinGPT、TradingAgents、RD-Agent、vectorbt、PyBroker、Lumibot、NautilusTrader。
- 补充 agent 架构笔记、数据与评估检查表、来源链接。
- 为误拼写目录 `refrence/` 添加跳转说明。

### v1 Agent 实现

- 新建 Python 包 `quant_agent/`。
- 新增默认配置 `configs/default.yaml`。
- 新增推荐配置 `configs/recommended.yaml`。
- 新增 walk-forward 聚合推荐配置 `configs/walk_forward_recommended.yaml`。
- 新增全功能基础版配置 `configs/full_roadmap.yaml`。
- 新增默认股票池 `configs/universe_default.csv`，支持从 CSV 读取 universe。
- 新增多策略报告对比命令 `compare-reports`。
- 新增数据质量、纸面订单计划和 dashboard CLI 命令。
- 新增 CLI 入口：

```powershell
python -m quant_agent run-backtest --config configs/default.yaml
```

- 实现数据层：
  - `yfinance` 数据下载。
  - 本地缓存到 `data/cache/`。
  - 本地 CSV/Parquet 单文件读取。
  - 本地 CSV/Parquet 目录读取，支持按文件名推断单标的 `symbol`。
  - 数据质量报告。
  - point-in-time 字段约定识别。
  - corporate action 元数据列识别。
  - Local/YFinance data adapter，以及 Alpaca/Polygon 预留 adapter。
  - 标准化 OHLCV 字段。
  - 数据质量检查。

- 实现信号层：
  - 12-1 动量。
  - 20/50 均线趋势。
  - 1-month reversal。
  - 20-day low-volatility score。
  - 横截面 z-score 合成 score。
  - 支持 `strategy.signal_weights` 调整信号权重。

- 实现组合层：
  - long-only。
  - 月度调仓。
  - top N 选股。
  - 等权配置。
  - 单票权重上限。

- 实现风控层：
  - 最大持仓数。
  - 最大单票权重。
  - long-only 检查。
  - 最大换手检查。

- 实现回测层：
  - 日线 close-to-close 回测。
  - 交易成本。
  - 滑点。
  - SPY benchmark。
  - CAGR、Sharpe、Sortino、Calmar、最大回撤、波动率、胜率、换手、beta、alpha、information ratio 等指标。
  - average/max holding days。

- 实现 ML ranking 基础版：
  - 基于技术特征的 Ridge ranking signal。
  - 配置化 model version、feature version 和 prediction horizon。
  - 输出 `ml_feature_matrix.csv`、`ml_predictions.csv`、`ml_diagnostics.json`。
  - ML signal 通过同一组合构建、风险检查和权重搜索层。

- 实现分类型研究买入候选基础版：
  - 输出 `recommendations.csv` 和 `recommendations.json`。
  - 输出长期、波段、短期、防守、激进五类候选 CSV。
  - 每条候选包含 score、confidence、risk level、target weight、latest price、data date 和 reason。
  - 明确为 research candidate，不构成投资建议或实盘交易授权。

- 实现可选 LLM 研究审阅基础版：
  - 默认离线模板审阅。
  - 可选 OpenAI-compatible chat completions client。
  - 缺少 key 或请求失败时自动回落离线模板。
  - 保存 prompt version、model、input hash 和 output hash 元数据。
  - 拦截明显 broker/order 指令化输出。

- 实现纸面交易基础版：
  - broker 抽象接口。
  - PaperBroker 预览/受控提交模拟器。
  - target positions 到 proposed orders 的订单计划。
  - current positions CSV 输入。
  - max order notional、gross notional 风控审批。
  - paper trading audit log。

- 实现本地 dashboard 基础版：
  - 展示 metrics、period metrics、risk checks、data quality、paper trading checks、equity、positions、trades、proposed orders。
  - 输出单文件 HTML。
  - 本地服务入口 `serve-dashboard`，支持运行状态、报告文件浏览和触发回测任务。
  - 每次服务端运行生成独立 `run_id` 报告目录。
  - 维护 `service/runtime_status.json` 和 `service/run_history.json`。
  - full roadmap 输出已整理为 `current/`、`service/`、`runs/`、`notifications/`、`paper/`。
  - 支持配置化定时运行基础版。
  - 支持 API token 认证，校验 `Authorization: Bearer <token>` 或 `X-API-Token`。
  - dashboard 前端支持输入并本地保存 API token。
  - 输出 dashboard 操作审计日志 `dashboard_audit.jsonl`，记录触发回测、approve/reject 和未授权 API 访问。

- 实现告警与失败处理基础版：
  - 生成 `alerts.json`、`alerts.csv`、`alerts.md`。
  - 覆盖 max drawdown、低 Sharpe、risk check 失败、stale data、missing universe symbols、point-in-time 元数据缺失、paper order plan 未审批。
  - dashboard 和 `/api/alerts` 展示告警。
  - run history 记录 alert summary。

- 实现通知与人工审批基础版：
  - 生成 `notifications.json`、`notifications.csv`。
  - 支持本地 file outbox：`notification_outbox.json`、`notification_outbox.csv`。
  - 支持可选 webhook channel。
  - 提供 paper order approve/reject API。
  - 审批通过后生成 `paper_order_approval.json` 和 `broker_preview.csv`。
  - 默认仍不提交 broker orders。

- 实现研究审阅 agent：
  - 输出结构化 Markdown 审阅。
  - 明确不授权 live 或 paper trading。
  - 不产生 broker/order 指令。

- 实现报告输出：
  - `reports/latest/summary.md`
  - `reports/latest/audit.json`
  - `reports/latest/equity_curve.csv`
  - `reports/latest/equal_weight_equity.csv`
  - `reports/latest/positions.csv`
  - `reports/latest/trades.csv`
  - `reports/latest/benchmark_equity.csv`
  - `reports/latest/period_metrics.csv`
  - `reports/latest/exposure_by_symbol.csv`
  - `reports/latest/signal_diagnostics.csv`
  - `reports/latest/signal_weight_search.csv`
  - `reports/latest/recommended_signal_weights.json`
  - `reports/latest/recommended_equity_curve.csv`
  - `reports/latest/recommended_period_metrics.csv`
  - `reports/latest/recommended_positions.csv`
  - `reports/latest/recommended_trades.csv`
  - `reports/latest/walk_forward_signal_search.csv`
  - `reports/latest/walk_forward_stability.csv`
  - `reports/latest/walk_forward_recommended_signal_weights.json`
  - `reports/latest/walk_forward_recommended_equity_curve.csv`
  - `reports/latest/walk_forward_recommended_period_metrics.csv`

### 测试与验证

- 新增 `tests/test_quant_agent.py`。
- 覆盖数据标准化、信号滞后、组合风控、完整 pipeline 输出。
- 增加 CSV 股票池解析测试。
- 增加 benchmark-relative 指标测试。
- 增加 evaluation period 配置和分段指标输出测试。
- 增加新信号列、equal-weight baseline 和持仓暴露输出测试。
- 增加信号权重解析和单信号诊断输出测试。
- 增加 train/validation 信号权重搜索和推荐权重输出测试。
- 增加 recommended strategy 冻结 test period 对比测试。
- 增加多窗口 walk-forward 信号搜索和稳定性输出测试。
- 增加 walk-forward 聚合推荐权重和冻结 test 对比测试。
- 增加多策略 comparison report 输出测试。
- 增加本地 CSV/Parquet 数据源配置解析和目录读取测试。
- 增加 ML ranking、数据质量、纸面订单计划、PaperBroker 测试。
- 增加分类型研究买入候选测试。
- 增加 dashboard API token 认证和操作审计日志测试。
- 已运行并通过：

```powershell
python -m pytest
python -m compileall quant_agent tests
python -m quant_agent run-backtest --config configs/default.yaml
python -m quant_agent run-backtest --config configs/full_roadmap.yaml
```

- 默认配置回测已跑通，最近一次结果：
  - Universe: 26 symbols from `configs/universe_default.csv`
  - Total return: 495.50%
  - Sharpe: 1.07
  - Sortino: 1.41
  - Calmar: 0.79
  - Beta: 1.16
  - Alpha: 13.40%
  - Information ratio: 0.84
  - Max drawdown: -40.24%
- 全功能基础版配置已跑通，最近一次结果：
  - Config: `configs/full_roadmap.yaml`
  - Output: `reports/full_roadmap/current/`
  - Total return: 108.50%
  - Sharpe: 0.61
  - Max drawdown: -33.15%
  - ML train rows: 12558
  - ML scored rows: 35022
  - Paper trading approval: true

## 当前限制

- `yfinance` 是原型级数据源，不保证生产级 point-in-time 正确性。
- 当前默认 universe 已扩展到 26 个大型流动性标的，但仍不是完整美股股票池。
- 还没有 survivorship-bias-free universe。
- 没有基本面、新闻、财报电话会或 SEC filing 数据。
- walk-forward 已完成信号权重搜索和稳定性基础版，尚未实现生产级 rolling retrain orchestration。
- ML 排名模型已完成基础版，尚未做模型注册中心、特征存储服务或漂移监控。
- LLM API 已完成可选 OpenAI-compatible client，尚未做多 provider 路由和人工审批工作流。
- 纸面交易已完成订单计划和 PaperBroker 基础版，尚未接入真实 broker API、完整订单生命周期或自动持仓对账。
- Web dashboard 已完成本地服务、定时运行、告警、通知 outbox、人工审批、API token 认证和操作审计日志基础版，尚未实现多用户权限系统和真实外部通知投递保障。
- 当前回测是研究级 close-to-close 模型，不是生产级事件驱动撮合。

## 下一阶段规划

### Phase 1: 研究质量增强

- 扩展 universe 配置，支持从 CSV 读取股票池。`已完成基础版`
- 增加更多 baseline：
  - 12-1 momentum。
  - 1-month reversal。`已完成基础版`
  - volatility filter。`已完成 low-volatility score 基础版`
  - moving average trend。
  - equal-weight benchmark。`已完成基础版`
- 增加 walk-forward 回测框架。`已完成分段评估基础版，尚未接入 ML rolling retrain`
- 增加 train/validation/test 时间段配置。`已完成基础版`
- 增加更完整的绩效指标。`已完成基础版`
  - Sortino。
  - Calmar。
  - beta。
  - alpha。
  - information ratio。
  - exposure by symbol。
    `已完成基础版`
  - holding period。`已完成基础版`

### Phase 2: ML 信号

- 引入 supervised ranking model。`已完成基础版`
- 支持特征矩阵缓存。`已完成基础版`
- 增加模型版本记录。`已完成基础版`
- 增加 rolling retrain。`已完成基础版：沿用 train/validation period 配置，尚未生产级编排`
- 输出每次预测的 model version、feature version 和 timestamp。`已完成基础版`
- 强制所有 ML 信号通过同一组合和风控层。`已完成基础版`

### Phase 1.5: 信号诊断与权重优化

- 单信号诊断输出。`已完成基础版`
- 配置化信号权重。`已完成基础版`
- train/validation 权重搜索，只允许用 validation 选择推荐权重。`已完成基础版`
- 推荐权重单独回测，并在 test period 与当前配置对比。`已完成基础版`
- 显式生成 recommended config 的 CLI，不覆盖默认配置。`已完成基础版`
- 多窗口 walk-forward 搜索和稳定性排名。`已完成基础版`
- 多窗口推荐权重聚合，避免只采纳单一 validation period 的最优候选。`已完成基础版`
- 支持从 walk-forward 推荐权重生成独立配置文件。`已完成基础版`
- 把三条配置的关键指标汇总成 comparison report。`已完成基础版`
- 增加 SVG equity/drawdown 图表，提升人工审阅效率。`已完成基础版`
- 增加 HTML 汇总页，把表格、图表和关键结论放在同一文件。`已完成基础版`
- 下一步：把基础版能力生产化，包括更严格数据治理、真实 broker sandbox、交互式 dashboard 和任务调度。

### Phase 3: LLM 研究审阅增强

- 新增可选 OpenAI/OpenAI-compatible LLM client。`已完成基础版`
- 保持默认离线模板审阅，避免无 key 时不可运行。`已完成`
- LLM 只允许生成：
  - 研究摘要。`已完成基础版`
  - 风险提示。`已完成基础版`
  - 因子假设。`已完成基础版`
  - 回测异常检查建议。`已完成基础版`
- 禁止 LLM 直接输出 broker order。`已完成基础拦截`
- 保存 prompt version、model name、input hash 和 output。`已完成基础版`

### Phase 4: 数据层升级

- 支持本地 CSV/Parquet 数据目录。`已完成基础版`
- 支持 point-in-time 字段约定。`已完成基础识别`
- 增加 corporate action 元数据。`已完成基础识别`
- 增加 delisted symbol 支持。`已完成基础版：missing universe symbols 报告`
- 增加数据质量报告。`已完成基础版`
- 为后续 Alpaca 或 Polygon 数据源预留 adapter。`已完成基础版`

### Phase 5: 纸面交易

- 增加 broker 抽象接口。`已完成基础版`
- 优先支持 Alpaca paper trading。`已预留 adapter；当前实现 PaperBroker 模拟器`
- 增加订单计划：
  - target positions。`已完成基础版`
  - current positions。`已完成 CSV 输入基础版`
  - proposed orders。`已完成基础版`
  - risk approval。`已完成基础版`
- 增加持仓和订单对账。`已完成基础版：current positions 到 target diff`
- 增加 kill switch。`已完成基础版：PaperBroker 默认禁止 submit`
- 增加 paper trading audit log。`已完成基础版`
- 增加人工审批流。`已完成基础版`

### Phase 6: Web UI 和监控

- 增加本地 dashboard。`已完成本地服务基础版`
- 展示 equity curve、drawdown、持仓、交易、风险检查、agent review。`已完成基础版`
- 增加每日运行状态。`已完成基础版：runtime status/run history/dashboard/audit 输出`
- 增加数据 stale 检查。`已完成基础版`
- 增加异常 alert 入口。`已完成基础版：data quality、paper/risk checks、metrics 阈值和 API 展示`
- 增加通知和人工审批入口。`已完成基础版：file outbox、webhook 预留、approve/reject API`
- 增加 API token 认证。`已完成基础版：Authorization Bearer / X-API-Token`
- 增加操作审计日志。`已完成基础版：dashboard_audit.jsonl`
- 整理 full roadmap 输出目录。`已完成基础版：current/service/runs 分层`

## 推荐近期优先级

1. 把基础版能力生产化：真实数据供应商、survivorship-bias-free universe、严格 point-in-time 数据治理。
2. 接入 broker sandbox，并把 PaperBroker 扩展成完整订单生命周期和持仓对账。
3. 增加 dashboard 多用户权限、真实通知投递保障和运行失败处理策略。
4. 为 ML 增加模型注册、特征存储、漂移监控和可重复训练任务。
5. 为 LLM 审阅增加人工审批流和多 provider 路由。

## 运行命令

推荐使用项目专用 conda 环境：

```powershell
conda env create -f environment.yml
conda activate quant-ai
```

如果环境已存在，更新依赖：

```powershell
conda env update -n quant-ai -f environment.yml --prune
```

运行测试：

```powershell
python -m pytest
```

运行默认回测：

```powershell
python -m quant_agent run-backtest --config configs/default.yaml
```

运行 walk-forward 推荐配置：

```powershell
python -m quant_agent run-backtest --config configs/walk_forward_recommended.yaml
```

运行全功能基础版：

```powershell
python -m quant_agent run-backtest --config configs/full_roadmap.yaml
```

查看报告：

```text
reports/latest/summary.md
```

查看多策略对比：

```text
reports/comparison/strategy_comparison.md
```
