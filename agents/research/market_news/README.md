# Market News Research Agent

## Overview

This agent **continuously monitors** global market news sources to detect opportunities, validate strategies, and generate actionable intelligence for the TradeBot system.

## Operating Mode

**Continuous Automated Operation** - Not human time-based schedules.

```yaml
Query Cycles:
  High Priority (5 min):  Reuters, Bloomberg alerts, Grok trending
  Standard (15 min):      Perplexity Finance, WSJ, FT, CNBC
  Background (1 hour):    Earnings calendar, economic events, predictions
  Deep Analysis (6 hr):   Regime analysis, historical context
```

## Core Workflows

| Workflow | Trigger | Output |
|----------|---------|--------|
| **News Monitoring** | Query interval | `market_news` table |
| **Strategy Validation** | New high-impact news OR 6hr | Validation flags to Manager |
| **Opportunity Detection** | Critical/High news event | `strategies` table (NEWS-DRIVEN) |
| **Calendar Monitoring** | Hourly | Pre-event alerts to Manager |

## Agent Integration

| Target Agent | Push Data |
|--------------|-----------|
| **Manager** | Critical assessments, strategy validation failures, action needed |
| **Research** | NEWS-DRIVEN opportunities, regime changes |
| **Backtest** | Historical event data for stress testing |
| **Portfolio Tracker** | VIX alerts, position-specific risks |

## Files

| File | Purpose |
|------|---------|
| **SKILL.md** | Complete agent instructions and protocols |
| **README.md** | This quick reference |
| **PERPLEXITY_GROK_GUIDE.md** | Detailed AI source configuration |
| **NEWS_ASSESSMENTS_LOG.md** | Log format documentation |

## Source Tiers

1. **Real-Time** (5min): Reuters, Bloomberg, Grok
2. **Analysis** (15min): Perplexity Finance, WSJ, FT
3. **Forward-Looking** (1hr): Earnings, Predictions, Economic Calendars
4. **Data/Visualization** (On-demand): FINVIZ, Yahoo Finance

## Verification Protocol

| Severity | Min Sources | Max Time |
|----------|-------------|----------|
| Critical | 3 | 5 min |
| High | 3 | 15 min |
| Medium | 2 | 1 hour |
| Low/Info | 1 | Best effort |

## Key Outputs

- `market_news` table in `data/tradebot.db` - All assessments
- `strategies` table - NEWS-DRIVEN opportunities
- `system_state` table - Regime change updates
- Push alerts to Manager and Portfolio Tracker agents
- **ZeroMQ Event Bus**: `NEWS.CRITICAL`, `NEWS.HIGH`, `NEWS.SENTIMENT_SHIFT` topics for instant notifications

## Performance Targets

- Detection Speed: Critical news within 5 min of first source
- Verification Accuracy: >95% correct assessments
- Strategy Protection: 100% coverage of material position impacts
- False Positive Rate: <20% immaterial high-priority alerts

---

*This agent operates autonomously for continuous market awareness.*
