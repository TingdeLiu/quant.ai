# quant.ai

> **One command to research any US stock** — explainable ratings and key price levels, in seconds. No account, no API key, no setup.

[English](README.md) | [中文](README_CN.md)

[![CI](https://github.com/Tyndall-Labs/quant.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Tyndall-Labs/quant.ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

`quant.ai` is a command-line quant-research toolkit for **US equities**, built for everyday investors. Type one command and get an explainable rating, key support/stop levels, and the reasoning behind them — all derived from historical prices, fully offline-friendly, and with no brokerage attached.

> ⚠️ Research only — **not investment advice**. It never places or suggests live orders.
> Analysis output (ratings, reasons) is in **Chinese**; the tool targets Chinese-speaking investors researching US stocks.

## Quick start

```bash
pip install -e .          # or: pip install -r requirements.txt
quant-ai doctor           # environment self-check (deps + data connectivity)
quant-ai analyze AAPL     # rate one stock in seconds
```

No entry point? `python -m quant_agent analyze AAPL` works the same.

## What you get

```text
╭─ AAPL — 偏多  (confidence: medium) ─────────────────────────────╮
│        最新价 (last)   226.34   (2025-06-20)                    │
│      区间涨跌 (return)  1M +3.2%  ·  3M +8.1%  ·  6M +12.4%      │
│    RSI / 波动           RSI 58.3  ·  ann. vol 24.5%             │
│          均线 (MA)      MA20 220.15 · MA50 212.40 · MA200 198.7 │
│          解读 (note)    多头排列，动量偏强，回踩 MA20 不破即偏多 │
│          依据 (reasons) · 站上所有均线  · 12-1 动量为正          │
│      参考关注位         支撑 212.40  ·  参考止损 205.10          │
╰─────────────────────────────────────────────────────────────────╯
```

`偏多` = mildly bullish (the five ratings range from 强烈看多 *strong buy* to 强烈看空 *strong sell*). Add `--output-dir` to export Markdown + JSON, or `--chart` for a price/MA/RSI PNG.

## Highlights

- 🎯 **Zero-config single-stock analysis** — `analyze AAPL` returns rating, returns, RSI, volatility, MA positions, support/stop levels, and human-readable reasons.
- 🧩 **Personalized watchlist** — `quant-ai init` interactively builds a universe that is **2/3 your own picks** (companies + sectors you care about) and **1/3 discovered** by the engine from the wider market (top cross-sectional signals you didn't pick).
- 🔬 **Research backtests** — cross-sectional signals (12-1 momentum, 20/50 trend, 1-month reversal, low-vol), signal-weight search, **walk-forward** stability analysis, plus SPY and equal-weight baselines to separate alpha from beta.
- 📊 **Local dashboard & daily market report** — a no-key market-intelligence brief (RSS headlines + quant signals) and an interactive Markets dashboard, served locally.
- 🤖 **MCP server** — ask Claude things like "what's the read on NVDA?" and it calls into real project data.
- 🛡️ **Safe by design** — deterministic signals + risk layer, friendly degradation on network/data errors (clear Chinese messages, no stack traces), paper trading only — never submits real orders.

## Common commands

| Command | What it does |
| --- | --- |
| `quant-ai analyze AAPL MSFT NVDA` | Rate one or more stocks |
| `quant-ai analyze --file watchlist.txt` | Rate symbols from a file |
| `quant-ai init` | Build a personalized watchlist (interactive) |
| `quant-ai analyze --watchlist` | Rate your personalized watchlist |
| `quant-ai run-backtest --config configs/default.yaml` | Run the research backtest |
| `quant-ai market-report` | Generate the daily market-intel report |
| `quant-ai serve-dashboard` | Start the local dashboard service |
| `quant-ai doctor` | Environment self-check |

## How it works

1. **Data** — daily OHLCV from Yahoo Finance (`yfinance`) by default, or local CSV/Parquet. Cached and validated.
2. **Signals** — cross-sectional, point-in-time-lagged factors, z-scored per day.
3. **Portfolio & risk** — deterministic target weights under position/turnover/liquidity limits.
4. **Evaluation** — train / validation / test split, walk-forward windows, and benchmark-relative metrics (Sharpe, Sortino, Calmar, max drawdown, alpha/beta).
5. **AI (optional)** — an LLM only *reviews* and *narrates* research; it never generates orders. Falls back to an offline template when no API key is set.

## Documentation

- **Full manual (Chinese):** [README_CN.md](README_CN.md) — detailed config, backtest/walk-forward, dashboard API, MCP integration, output files.
- **Changelog:** [CHANGELOG.md](CHANGELOG.md) · **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md) · **Roadmap:** [roadmap.md](roadmap.md)

## Tests

```bash
python -m pytest      # 47 tests, network-free
python -m ruff check quant_agent tests conftest.py
```

## Disclaimer

This project is for **quantitative research and education only**. It analyzes historical prices and produces research signals — **not investment advice**, and **not** authorization to trade. Markets carry risk; you are responsible for your own decisions.

## License

[MIT](LICENSE)
