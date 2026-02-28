# Strategy Registry

## Overview

This document provides a **centralized tracking system** for all trading strategies across the entire RBI (Research, Backtest, Implementation) pipeline. Use this registry to quickly assess the current state of all strategies and identify bottlenecks in the development pipeline.

**Last Updated**: 2026-02-03
**Total Strategies**: 0 (system initialized)

---

## Active Strategies (Live Trading)

| ID | Name | Asset Class | Status | Deployed | Capital Allocated | Performance (30d) | Sharpe | Notes |
|----|------|-------------|--------|----------|-------------------|------------------|--------|-------|
| - | - | - | - | - | - | - | - | No active strategies yet |

---

## Paper Trading Strategies

| ID | Name | Asset Class | Status | Paper Start | Expected Live | Performance vs Backtest | Notes |
|----|------|-------------|--------|-------------|---------------|------------------------|-------|
| - | - | - | - | - | - | - | No paper trading strategies |

---

## Backtest Pipeline

### Ready for Implementation

| ID | Name | Asset Class | Backtest Completed | Test # | Sharpe | Max DD | Win Rate | Next Action |
|----|------|-------------|-------------------|--------|--------|--------|----------|-------------|
| - | - | - | - | - | - | - | - | No strategies ready |

### In Backtest

| ID | Name | Asset Class | Started | Test # | Expected Completion | Tester | Notes |
|----|------|-------------|---------|--------|---------------------|--------|-------|
| - | - | - | - | - | - | - | No active backtests |

---

## Research Pipeline

### Ready for Backtest

| ID | Name | Asset Class | Type | Priority | Created | Source | Assigned To |
|----|------|-------------|------|----------|---------|--------|-------------|
| - | - | - | - | - | - | - | No ideas ready for backtest |

### Pending Research

| ID | Name | Asset Class | Type | Priority | Created | Status | Notes |
|----|------|-------------|------|----------|---------|--------|-------|
| - | - | - | - | - | - | - | No pending research ideas |

---

## Archived Strategies

### Retired (Poor Performance)

| ID | Name | Reason for Retirement | Deployed Period | Final Performance | Lessons Learned |
|----|------|---------------------|-----------------|-------------------|-----------------|
| - | - | - | - | - | No retired strategies |

### Rejected (Failed Backtest)

| ID | Name | Reason for Rejection | Test # | Key Issue | Lessons Learned |
|----|------|---------------------|--------|-----------|-----------------|
| - | - | - | - | - | No rejected strategies |

---

## Backtest Index

Quick reference for all completed backtests:

| Test # | Strategy Name | Asset Class | Result | Date | Sharpe | Max DD | Status | RESULTS.md |
|--------|---------------|-------------|--------|------|--------|--------|--------|------------|
| test1 | BB Breakout | Crypto (BTC) | PASS | 2026-01-20 | 1.2 | -14% | Ready for Implementation | [Link](data/backtests/test1/RESULTS.md) |

*See [data/backtests/TEST_INDEX.md](data/backtests/TEST_INDEX.md) for detailed backtest information.*

---

## Pipeline Statistics

### Conversion Rates

```
Research Ideas → Ready for Backtest:  N/A (insufficient data)
Backtest → Validated:                 100% (1/1)
Validated → Paper Trading:            0% (0/1)
Paper Trading → Live:                 N/A
Overall Pipeline Conversion:          0% (0 live strategies from ideas)
```

### Average Timeline

```
Research → Backtest Ready:     N/A
Backtest Execution:            N/A
Paper Trading Duration:        Target 30-60 days
Total Idea → Live:             Target 60-120 days
```

### Strategy Type Distribution

| Type | Research | Backtest | Live | Success Rate |
|------|----------|----------|------|--------------|
| Momentum | 0 | 1 | 0 | N/A |
| Mean Reversion | 0 | 0 | 0 | N/A |
| Income (Options) | 0 | 0 | 0 | N/A |
| Volatility | 0 | 0 | 0 | N/A |
| Breakout | 0 | 1 | 0 | N/A |

---

## How to Use This Registry

### Adding a New Research Idea

```bash
# 1. Insert to strategies table: Strategy(status=NEW)
# 2. Update "Pending Research" section above with:
#    - ID, Name, Asset Class, Type, Priority
#    - Created date, Status
```

### Promoting to Backtest

```bash
# 1. Update strategies table: status → READY_FOR_BACKTEST
# 2. Move entry from "Pending Research" to "Ready for Backtest"
# 3. Assign backtest agent
```

### Recording Backtest Results

```bash
# 1. Create test<N>/ directory with RESULTS.md
# 2. Update "Backtest Index" section
# 3. If PASS: Move to "Ready for Implementation"
# 4. If FAIL: Move to "Rejected" with reason
```

### Deploying to Paper Trading

```bash
# 1. Update strategies table: status → LIVE_PAPER
# 2. Move from "Ready for Implementation" to "Paper Trading Strategies"
# 3. Set paper start date and expected live date
```

### Promoting to Live

```bash
# 1. Update strategies table: status → LIVE_REAL
# 2. Move from "Paper Trading" to "Active Strategies"
# 3. Record capital allocation and deployment date
```

### Retiring a Strategy

```bash
# 1. Update strategies table: status → RETIRED
# 2. Move from "Active Strategies" to "Retired"
# 3. Document reason, performance, lessons learned
```

---

## Quick Links

**Data Sources**:
- `data/tradebot.db` → `strategies` table — Master strategy pipeline
- `data/tradebot.db` → `trades` table — Live trading history
- [Backtest Directory](data/backtests/) - All backtest results

**Documentation**:
- [Manager README](agents/manager/README.md) - RBI workflow
- [Research Guide](agents/research/strategy/README.md) - Research methodology
- [Backtest Guide](agents/backtest/README.md) - Backtesting standards
- [Delegation Rules](docs/DELEGATION_RULES.md) - Manager/Portfolio Tracker authority

**Analytics**:
- Run `python agents/analytics/analytics_dashboard.py` for detailed pipeline metrics
- Run `python agents/analytics/trade_ideas_analytics.py` for idea funnel analysis

---

## Alerts & Reviews

### Manager Weekly Review Checklist

Every week, review this registry and:
- [ ] Check for stuck strategies (>30 days in same status)
- [ ] Verify backtest pipeline is moving (at least 1 active test)
- [ ] Confirm paper trading performance vs backtest expectations
- [ ] Review live strategy performance vs benchmarks
- [ ] Update conversion rates and timeline averages
- [ ] Identify bottlenecks in the pipeline

### Automated Notifications

Configure Portfolio Tracker to alert Manager when:
- Strategy stuck in Research for >30 days
- Backtest running for >14 days without completion
- Paper trading underperforming backtest by >30%
- Live strategy drawdown exceeds backtest max by >50%

---

**This registry is maintained by the AI Manager and should be updated after each stage transition in the RBI pipeline.**
