# Data And Evaluation Checklist

Use this before trusting any AI-generated or ML-generated US equity strategy.

## Data Requirements

- Point-in-time prices and corporate actions.
- Split/dividend adjustment policy documented.
- Survivorship-bias-free universe when possible.
- Delisted symbols handled.
- Trading calendar and holidays handled.
- Market open/close and timezone explicitly defined.
- News/filing timestamps use publish/acceptance time, not scraped time after the fact.
- Fundamental data has reporting dates and availability dates.
- All feature rows can be reproduced from data available at the decision time.

## Backtest Requirements

- Train/validation/test split is chronological.
- Walk-forward or rolling retraining for ML models.
- Transaction costs included.
- Slippage model included.
- Liquidity filter included.
- Borrow/shorting assumptions explicit if shorting is allowed.
- Benchmark defined before running experiments.
- Rebalancing schedule fixed before evaluation.
- No parameter search on the final test window.
- Strategy reports include drawdown, volatility, turnover, hit rate, exposure, and benchmark-relative returns.

## AI/LLM Signal Requirements

- Prompt version saved.
- Model name/version saved.
- Source documents saved or hash-referenced.
- Input timestamps saved.
- Output converted into structured features before trading.
- LLM output never directly becomes a broker order.
- Hallucination checks for tickers, dates, corporate actions, and news events.
- Human-readable rationale stored separately from numeric trading signal.

## RL Requirements

- Environment state excludes future information.
- Reward includes costs and risk penalties where appropriate.
- Same action space is valid in backtest and live mode.
- Random seeds and training configs saved.
- Evaluation uses unseen periods and unseen regimes.
- Compare against simple baselines: buy-and-hold, equal-weight, momentum, mean-reversion.
- Report turnover and drawdown, not just cumulative return.

## Production Safety Requirements

- Paper trading before live trading.
- Daily notional and order count limits.
- Per-symbol max order size and position size.
- Kill switch.
- Broker reconciliation after every order state change.
- Idempotent order submission.
- Full audit trail for every decision.
- Alerting for data gaps, stale models, failed jobs, and abnormal exposures.

## Useful Metrics

- CAGR
- Sharpe ratio
- Sortino ratio
- Max drawdown
- Calmar ratio
- Volatility
- Beta to benchmark
- Alpha to benchmark
- Information ratio
- Turnover
- Average holding period
- Win/loss ratio
- Profit factor
- Exposure by sector and symbol
- Capacity estimate using average dollar volume

## Initial Experiment Plan

1. Build a daily-bar research dataset for a liquid US equity universe.
2. Implement baseline strategies: equal weight, 12-1 momentum, short-term reversal, moving-average trend.
3. Add supervised ML ranking model using point-in-time features.
4. Add LLM-derived sentiment as a separate feature, not a trade decision.
5. Run walk-forward tests and compare against baselines.
6. Promote only stable signals to event-driven backtest.
7. Paper trade with strict risk limits.
