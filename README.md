# TradeBot - Algorithmic Trading Robot

Multi-agent trading system using the RBI (Research-Backtest-Implementation) methodology.

## Quick Navigation

| Directory | Purpose |
|-----------|---------|
| [`agents/`](agents/) | All agent implementations |
| [`data/`](data/) | Logs, datasets, backtests, state |
| [`config/`](config/) | System configuration |
| [`docs/`](docs/) | Extended documentation |
| [`scripts/`](scripts/) | Utility scripts |

## Agent Hierarchy

```
agents/
├── manager/              # Project Manager - orchestrates all agents
├── research/
│   ├── strategy/         # Trade strategy research
│   ├── market_news/      # Market news monitoring
│   ├── predictions/      # ML predictions (future)
│   └── crypto_liquidation/  # Crypto signals (future)
├── backtest/             # Strategy validation
├── brokers/
│   ├── alpaca/           # Paper trading
│   ├── ibkr/             # Live trading (stocks, options, futures)
│   └── okx/              # Crypto trading
├── portfolio_tracker/    # Risk management
└── analytics/            # Performance analytics
```

## Data Directory

```
data/
├── logs/                 # CSV logs (trade ideas, news, orders)
├── datasets/             # Historical data for backtesting
├── backtests/            # Backtest results (test1/, test2/, etc.)
└── state/                # Runtime state (managed via system_state table in tradebot.db)
```

## Getting Started

See [agents/manager/README.md](agents/manager/README.md) for full system documentation.

## Multi-Broker Architecture

| Broker | Mode | Asset Types |
|--------|------|-------------|
| **Alpaca** | Paper Trading | Stocks, Crypto (testing) |
| **IBKR** | Live Trading | Stocks, Options, Futures |
| **OKX** | Live Trading | Crypto only (US endpoint) |
