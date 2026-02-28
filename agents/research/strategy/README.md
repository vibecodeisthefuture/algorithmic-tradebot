# Strategy Research Agent

## Overview

This agent **continuously researches** trading strategies, generates testable hypotheses, and logs trade ideas for validation by the Backtest Agent.

## Operating Mode

**Continuous Automated Research** - Not human time-based research sessions.

```yaml
Research Cycles:
  Academic Scan (24h):     Google Scholar, SSRN, arXiv
  Pattern Detection (6h):  Perplexity Screener, market data
  News Integration:        On trigger from Market News Agent
  Consensus Tracking (12h): Perplexity Predictions, analyst views
```

## Core Workflows

| Workflow | Trigger | Output |
|----------|---------|--------|
| **Hypothesis Generation** | Research cycle | `strategies` table |
| **News-Triggered Research** | Market News Agent signal | NEWS-DRIVEN ideas |
| **Crypto Pattern Research** | 10-min scan cycle (configurable) | Pattern-based strategy ideas |
| **Strategy Validation** | New hypothesis OR backtest feedback | Updated status |

## Agent Integration

| Agent | Direction | Data |
|-------|-----------|------|
| **Market News** | ← Receive | NEWS-DRIVEN opportunities, regime changes |
| **Backtest** | → Push | Trade ideas with status=Ready |
| **Backtest** | ← Receive | Validation results, feedback |
| **Manager** | → Push | Validated strategies, research summaries |

## Files

| File | Purpose |
|------|---------|
| **SKILL.md** | Complete agent instructions |
| **README.md** | This quick reference |
| **crypto_strategy_generator.py** | Live crypto pattern detection (PatternRegistry plugin system) |
| **OPTIONS_STRATEGIES.md** | Options strategy encyclopedia |
| **CRYPTO_INVESTING_GUIDE.md** | Crypto liquidation/whale tracking methods |
| **TRADE_IDEAS_LOG.md** | Log format documentation |

## Strategy Categories

1. **Momentum** - Cross-sectional, time-series, dual momentum
2. **Mean Reversion** - Pairs trading, statistical arbitrage
3. **Options** - Volatility premium, theta decay, spreads
4. **Crypto** - Liquidation cascades, whale tracking, funding rates
5. **Crypto Pattern Detection** - Pluggable `PatternRegistry` detectors: momentum breakout, mean reversion bounce, volatility squeeze, volume divergence, MACD bullish cross, EMA ribbon expansion

## Quality Filters

All ideas must pass before logging:
- ✅ Theoretical foundation documented
- ✅ Transaction costs considered
- ✅ Risk factors identified
- ✅ Success criteria defined
- ❌ Reject: >5 parameters (curve-fit risk)
- ❌ Reject: No WHY explanation

## Output

- `strategies` table in `data/tradebot.db` - All trade ideas
- Push to Backtest Agent queue when status=Ready

## Performance Targets

- Hypothesis Rate: 3-5 new ideas per week
- Backtest Pass Rate: >30%
- Theoretical Grounding: 100%
- News Integration: 100% triggers processed

---

*Autonomous strategy research for systematic validation.*
