# GitHub Projects Worth Referencing

整理日期: 2026-06-13

## 一线参考项目

这些项目最值得优先阅读，分别覆盖 AI 研究平台、RL 交易、生产级回测执行、金融 LLM 和多 agent 设计。

| Project | Link | Reference value for our US stock agent | Reuse ideas | Main caveats |
| --- | --- | --- | --- | --- |
| Microsoft Qlib | https://github.com/microsoft/qlib | AI-oriented quantitative investment platform. It has data workflow, factor research, model training, backtesting, and experiment management patterns. | Research pipeline, feature/factor registry, rolling training, evaluation reports, model workflow separation. | Default examples are more research oriented. US data ingestion and live execution still need our own adapters. |
| AI4Finance FinRL | https://github.com/AI4Finance-Foundation/FinRL | Deep reinforcement learning library for automated trading, with stock market examples and gym-style environments. | Environment design, reward functions, portfolio action spaces, DRL training/evaluation structure. | RL examples can overfit easily. Must rebuild data cleaning, costs, risk control, and walk-forward evaluation before trusting signals. |
| QuantConnect LEAN | https://github.com/QuantConnect/Lean | Mature open-source algorithmic trading engine supporting equities and many asset classes. Useful as a reference for event-driven backtesting/live parity. | Security model, brokerage adapters, order lifecycle, calendar handling, corporate actions, portfolio accounting. | Large C# codebase. Better as architecture reference or engine integration candidate than something to casually fork. |
| AI4Finance FinGPT | https://github.com/AI4Finance-Foundation/FinGPT | Financial LLM project focused on data, sentiment, instruction tuning, and financial NLP workflows. | News/filing/social sentiment extraction, LLM evaluation prompts, financial text data pipeline. | LLM signal should be one input, not direct trade authority. Need strict anti-leakage timestamping. |
| TradingAgents | https://github.com/TauricResearch/TradingAgents | Multi-agent LLM financial trading framework. Useful for analyst/researcher/risk-manager style agent decomposition. | Role design for market analyst, news analyst, fundamentals analyst, risk manager, portfolio manager. | Treat as agent orchestration reference, not validated alpha source. Needs deterministic audit and backtest integration. |
| Microsoft RD-Agent | https://github.com/microsoft/RD-Agent | Research-and-development automation agent; relevant for automating factor/model discovery and experiment loops. | Auto-generate factor ideas, run experiments, summarize failures, maintain research memory. | Needs hard sandboxing and reproducibility rules before letting an agent modify research code. |

## Research and ML Backtesting Layer

These projects are useful when we need fast iteration on factors, ML strategies, and portfolio experiments.

| Project | Link | Use it for | Notes |
| --- | --- | --- | --- |
| vectorbt | https://github.com/polakowo/vectorbt | Fast vectorized backtests, parameter sweeps, signal research. | Very good for early research and factor screening. Less suitable as the sole event-driven live-trading truth source. |
| PyBroker | https://github.com/edtechre/pybroker | ML-oriented strategy backtesting with ranking, walk-forward style workflows, and model integration. | Strong candidate for rapid supervised-learning signal experiments on US equities. |
| zipline-reloaded | https://github.com/stefan-jansen/zipline-reloaded | Python event-driven backtesting lineage from Zipline. | Worth reviewing for pipeline API, calendars, bundles, and equity backtest semantics. |
| Backtrader | https://github.com/mementum/backtrader | Classic Python strategy backtesting and broker simulation. | Simple and readable reference, but check maintenance status before building new core infrastructure on it. |
| Alphalens Reloaded | https://github.com/stefan-jansen/alphalens-reloaded | Factor analysis and forward-return evaluation. | Useful for evaluating alpha factors before wrapping them in an agent. |
| Empyrical Reloaded | https://github.com/stefan-jansen/empyrical-reloaded | Performance/risk metrics such as Sharpe, drawdown, volatility. | Useful as a metrics reference for our reporting layer. |

## Live Trading and Execution Infrastructure

These are not primarily AI projects, but they matter because a trading agent needs reliable order, position, and broker behavior.

| Project | Link | Use it for | Notes |
| --- | --- | --- | --- |
| Lumibot | https://github.com/Lumiwealth/lumibot | Python backtesting/live trading framework with broker integrations including Alpaca-style US stock workflows. | Good reference for clean strategy APIs and paper/live execution handoff. |
| NautilusTrader | https://github.com/nautechsystems/nautilus_trader | High-performance event-driven trading platform. | Useful for architecture, event bus, order book, risk, execution, and live/backtest consistency. More complex than needed for a first agent. |
| Alpaca Trade API Python | https://github.com/alpacahq/alpaca-trade-api-python | US stock brokerage API client reference. | Alpaca is practical for paper trading. Check current SDK status before choosing exact package. |
| Interactive Brokers TWS API samples | https://github.com/InteractiveBrokers/tws-api-public | Broker API behavior and order types. | Useful if we later support IBKR. TWS/Gateway operational complexity is nontrivial. |

## Educational or Secondary References

Useful for concepts, but should not define our production architecture.

| Project | Link | Why keep it | Caveat |
| --- | --- | --- | --- |
| TradeMaster | https://github.com/TradeMaster-NTU/TradeMaster | Unified RL trading benchmark/platform ideas. | Check activity and dependency freshness before using code directly. |
| gym-anytrading | https://github.com/AminHP/gym-anytrading | Minimal gym environment for trading examples. | Too simplified for realistic US equities, but useful to understand environment API shape. |
| TensorTrade | https://github.com/tensortrade-org/tensortrade | Trading environment abstractions and RL components. | Maintenance and compatibility need verification before reuse. |

## How These Fit Together

Recommended dependency direction for our own agent:

1. Use Qlib/PyBroker/vectorbt patterns for research, features, factor tests, and ML experiments.
2. Use LEAN/NautilusTrader/Lumibot as references for event-driven backtest/live parity.
3. Use FinGPT/TradingAgents/RD-Agent as references for LLM reasoning, agent roles, and research automation.
4. Keep final trade authority in a deterministic portfolio/risk/execution layer, not in an LLM response.

## Projects To Avoid As Primary Foundations

- Random single-strategy notebooks without timestamped data handling.
- Crypto-only bots unless the architecture is clearly reusable.
- Repositories that directly call an LLM to output buy/sell orders without backtestable intermediate signals.
- Projects with no transaction cost, slippage, benchmark, walk-forward split, or drawdown reporting.
