# Architecture Notes For Our AI US Stock Quant Agent

目标: 把参考项目中的可用设计转化为我们自己的系统边界。

## Recommended High-Level Architecture

```text
Data connectors
  -> normalized market/fundamental/news store
  -> feature and factor pipeline
  -> model and signal research
  -> portfolio construction
  -> risk checks
  -> execution planner
  -> broker adapter
  -> audit, monitoring, and post-trade analytics
```

LLM/agent 层应该横向服务研究、解释和监控，不应该绕过组合和风控层直接下单。

## Agent Roles Worth Building

| Role | Main responsibility | Reference projects |
| --- | --- | --- |
| Data steward | Validate timestamps, splits/dividends, missing bars, universe membership, delistings. | Qlib, LEAN |
| Factor researcher | Generate and test factors, summarize IC/turnover/decay. | Qlib, Alphalens Reloaded, RD-Agent |
| ML researcher | Train supervised/RL models and produce versioned signals. | FinRL, PyBroker, Qlib |
| News and filing analyst | Convert text into timestamped structured features. | FinGPT, TradingAgents |
| Portfolio manager | Convert signals into weights under constraints. | FinRL, Qlib, LEAN |
| Risk manager | Enforce exposure, drawdown, liquidity, leverage, sector, and single-name limits. | LEAN, NautilusTrader |
| Execution agent | Convert target weights into orders and track order lifecycle. | LEAN, Lumibot, NautilusTrader |
| Reviewer/auditor | Explain decisions and block trades when evidence is insufficient. | TradingAgents, RD-Agent |

## Minimal Viable Agent Scope

For the first practical version, avoid trying to build a fully autonomous hedge fund. A safer MVP:

1. US equities only, daily bars first.
2. Fixed universe such as S&P 500 or liquid Nasdaq/NYSE names.
3. Research mode before live mode.
4. Signals are numeric and backtestable.
5. LLM produces explanations, hypotheses, and review notes, not final order instructions.
6. Portfolio construction is deterministic.
7. Every trade decision has a saved evidence packet: data snapshot, model version, signal value, constraints, and risk checks.

## Where AI Adds Value

AI is most useful in these places:

- Financial text processing: news, earnings call transcripts, SEC filings, analyst notes.
- Factor idea generation: create hypotheses and code candidates, then test them mechanically.
- Regime classification: summarize market context from multiple indicators.
- Research assistant: compare experiments, explain failure modes, detect suspicious backtests.
- Human-readable reporting: daily decision memo and post-trade attribution.

AI is risky in these places:

- Direct position sizing from natural language.
- Direct broker order generation.
- Unreviewed code modification in live trading systems.
- Consuming news without point-in-time checks.
- Selecting benchmarks or evaluation windows after seeing results.

## Core Engineering Decisions

### Data Store

Use a point-in-time data model from the beginning. Even for a prototype, every row needs:

- symbol
- timestamp
- source
- adjusted/unadjusted flag
- ingestion time
- corporate action handling
- data quality status

### Research Pipeline

Qlib-style separation is worth copying:

- data loader
- feature processor
- model trainer
- prediction recorder
- backtest executor
- report generator

This prevents the agent from mixing data access, feature engineering, training, and trading rules in one opaque script.

### Backtesting

Use two levels:

- Vectorized research backtest for fast signal screening.
- Event-driven canonical backtest for final strategy evaluation.

vectorbt/PyBroker are useful for the first level. LEAN/NautilusTrader/Lumibot are useful references for the second level.

### Risk Layer

Risk checks should be deterministic and independent of the model:

- max position weight
- max gross/net exposure
- max sector exposure
- max daily turnover
- min average dollar volume
- max drawdown stop
- no-trade list
- earnings/event blackout rules if needed

### Execution Layer

Execution should accept target portfolio changes, not free-form agent text. A good interface:

```text
target_positions + current_positions + market_state
  -> proposed_orders
  -> risk approval
  -> broker submit
  -> order state reconciliation
```

## Repository Design Suggestion

Future codebase layout could look like:

```text
quant_agent/
  data/
  features/
  models/
  research/
  backtest/
  portfolio/
  risk/
  execution/
  agents/
  reports/
  configs/
```

The `agents/` package should orchestrate work across these modules. It should not contain hidden trading logic that cannot be replayed in backtests.
