# TradeBot — Algorithmic Trading System

> Autonomous, multi-agent trading system built on the **RBI (Research → Backtest → Implement)** pipeline. Agents operate independently, communicate through a shared SQLite blackboard, and are governed by a risk-policy framework that spans four tiers from conservative to aggressive.

---

## Architecture

```
Manager Agent
│
├── Research
│   ├── Strategy Agent       — generates and scores trade strategies
│   ├── Market News Agent    — monitors news sentiment and catalysts
│   ├── Predictions Agent    — ML models: Monte Carlo, ARIMA, LightGBM,
│   │                          HMM, Prophet, LSTM, TFT + Ensemble layer
│   └── Crypto Liquidation   — liquidation heatmaps and whale signals
│
├── Backtest Agent           — validates strategies before live deployment
│
├── Brokers
│   ├── Alpaca               — paper trading (stocks + crypto)
│   ├── IBKR                 — live trading (stocks, options, futures)
│   └── OKX                  — live crypto (US endpoint)
│
├── Portfolio Tracker        — live risk management, position sizing, stop-loss
└── Analytics Agent          — performance tracking, model accuracy surveillance
```

---

## Asset Coverage

| Class | Assets | Candle Size |
|:---|:---|:---:|
| Crypto | BTC, ETH, SOL, XRP, ADA, DOGE | 6h |
| Stocks | AAPL, GOOG, NVDA, META, NFLX, ASTS | 1d |

---

## Key Components

### Predictions Agent *(Active — v1.0.0)*
ML forecasting pipeline that generates probabilistic BUY/SELL/HOLD signals for all 12 assets. Signals are regime-gated by an HMM detector that runs first every cycle and determines which models activate.

| Model | Role | Regime |
|:---|:---|:---:|
| HMM | Regime classifier — runs first, gates all others | Always |
| Monte Carlo | Price distribution / risk bands (P5/P50/P95) | Always |
| ARIMA/SARIMA | Mean-reversion detection | BEAR/NEUTRAL |
| LightGBM | Next-candle direction (primary entry signal) | BULL/NEUTRAL |
| Prophet | Seasonality decomposition, trend confirmation | BULL/NEUTRAL |
| LSTM | Nonlinear pattern sequences | BULL/NEUTRAL |
| TFT | Multi-horizon quantile forecast (1/6/14 candles) | All |
| Ensemble | Confidence-weighted signal synthesis | All |

→ See [`agents/research/predictions/README.md`](agents/research/predictions/README.md)

### Risk Policy Framework
Four-tier risk policy (HIGH → LOW) governs leverage, position sizing, and drawdown limits. The Manager Agent enforces the active policy across all brokers and the Portfolio Tracker.

→ See [`agents/manager/README.md`](agents/manager/README.md)

### Blackboard Architecture
All agents share state through `tradebot.db` (SQLite, WAL mode). No direct agent-to-agent calls — everything is event-driven via the `event_log` table and ZeroMQ pub/sub bus.

---

## Project Layout

```
TradeBot/
├── agents/
│   ├── common/          — shared ORM models, enums, database session
│   ├── manager/         — orchestrator, risk policy, event routing
│   ├── research/        — strategy, news, predictions, liquidations
│   ├── backtest/        — walk-forward validation engine
│   ├── brokers/         — Alpaca / IBKR / OKX integrations
│   ├── portfolio_tracker/
│   └── analytics/
├── data/
│   ├── datasets/        — historical OHLCV CSVs (500 weeks crypto, 1000 weeks stocks)
│   ├── backtests/       — backtest results
│   ├── state/           — model weights, runtime state
│   └── tradebot.db      — shared blackboard (SQLite)
├── config/              — environment and system configuration
├── docs/
│   ├── DATA_SCHEMAS.md  — all database table schemas
│   └── changelogs/      — versioned release notes
└── scripts/             — data collection, utilities
```

---

## Brokers

| Broker | Mode | Assets |
|:---|:---|:---|
| **Alpaca** | Paper trading | Stocks, Crypto |
| **IBKR** | Live trading | Stocks, Options, Futures |
| **OKX** | Live trading | Crypto (US endpoint) |

---

## Documentation

| Document | Description |
|:---|:---|
| [`agents/manager/README.md`](agents/manager/README.md) | System orchestration, risk policy, full agent map |
| [`agents/research/AGENTS.md`](agents/research/AGENTS.md) | Research domain agent responsibilities |
| [`agents/research/predictions/README.md`](agents/research/predictions/README.md) | Predictions Agent — models, DB schema, usage |
| [`docs/DATA_SCHEMAS.md`](docs/DATA_SCHEMAS.md) | All database table schemas (v2.0) |
| [`docs/changelogs/`](docs/changelogs/) | Release changelogs |
