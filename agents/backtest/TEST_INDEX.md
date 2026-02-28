# Backtest Index

## Overview

Quick reference index for all backtest executions in the TradeBot system. Each backtest is assigned a sequential test number (`test1`, `test2`, etc.) and has a corresponding directory with complete RESULTS.md documentation.

**Last Updated**: 2026-02-03
**Total Tests Completed**: 1

---

## Active/Completed Backtests

| Test # | Strategy Name | Asset Class | Hypothesis | Start Date | End Date | Status | Result | Link |
|--------|---------------|-------------|------------|------------|----------|--------|--------|------|
| test1 | BB Breakout | Crypto (BTC) | Bollinger Band breakouts on 6h timeframe with volume confirmation | 2026-01-15 | 2026-01-20 | ✅ Complete | **PASS** (Sharpe 1.2) | [RESULTS](test1/RESULTS.md) |

---

## Test Results Summary

### test1: Bollinger Band Breakout (BTC 6h)

**Strategy**: BB Breakout
**Asset**: BTC/USD
**Timeframe**: 6-hour candles
**Data Period**: 500+ weeks
**Test Duration**: 2026-01-15 to 2026-01-20

**Key Metrics**:
- **Sharpe Ratio**: 1.2 ✅ (target ≥1.0)
- **Maximum Drawdown**: -14% ✅ (target ≤15%)
- **Win Rate**: 42% ✅ (target ≥40%)
- **Total Trades**: 156 ✅ (target ≥100)
- **Profit Factor**: 1.45 ✅ (target ≥1.2)

**Validation Tests**:
- ✅ Out-of-sample: 30% of data, performance 75% of in-sample
- ✅ Walk-forward: 5 periods, 80% profitable
- ✅ Black swan tests: Passed 2008, 2020 simulations
- ✅ Transaction costs: Included, strategy still profitable

**Recommendation**: ✅ **Ready for Implementation**
**Status**: Awaiting paper trading deployment
**Trade Idea Reference**: ti-001

**Files**:
- [RESULTS.md](test1/RESULTS.md) - Complete backtest documentation
- [bb_breakout.py](test1/bb_breakout.py) - Strategy implementation

---

## Backtest Pipeline

### In Progress

| Test # | Strategy Name | Asset Class | Started | Assigned To | Expected Completion | Progress |
|--------|---------------|-------------|---------|-------------|---------------------|----------|
| - | - | - | - | - | - | No active backtests |

### Queued (Ready to Start)

| Queue # | Trade Idea ID | Strategy Name | Asset Class | Priority | Created | Notes |
|---------|---------------|---------------|-------------|----------|---------|-------|
| - | - | - | - | - | - | No queued backtests |

---

## Historical Statistics

### Success Rate
```
Total Tests: 1
Passed: 1 (100%)
Failed: 0 (0%)
In Progress: 0
```

### Average Metrics (Passed Tests Only)
```
Average Sharpe Ratio: 1.2
Average Max Drawdown: -14%
Average Win Rate: 42%
Average Total Trades: 156
Average Test Duration: 5 days
```

### Validation Pass Rates
```
Out-of-Sample Test: 100% (1/1)
Walk-Forward Test: 100% (1/1)
Black Swan Tests: 100% (1/1)
Transaction Cost Test: 100% (1/1)
```

---

## Test Numbering Convention

### Directory Structure
```
data/backtests/
├── TEST_INDEX.md (this file)
├── test1/
│   ├── RESULTS.md
│   └── bb_breakout.py
├── test2/
│   ├── RESULTS.md
│   └── strategy_script.py
└── test<N>/
    ├── RESULTS.md (required)
    └── *.py (strategy implementation)
```

### Naming Rules
- Sequential numbering: `test1`, `test2`, `test3`, ...
- Never reuse test numbers (even for failed tests)
- Each test gets its own directory
- RESULTS.md is mandatory for all tests
- Strategy implementation files are optional but recommended

---

## Backtest Stages

### Stage 1: Setup
- Create `test<N>/` directory
- Copy backtest template from `test_template.py`
- Define strategy parameters
- Load historical data

### Stage 2: Implementation
- Implement entry/exit logic
- Add risk management rules
- Configure position sizing
- Set transaction costs

### Stage 3: Initial Testing
- Run on full dataset
- Calculate performance metrics
- Generate initial results

### Stage 4: Validation
- Out-of-sample test (30%+ of data)
- Walk-forward analysis (5+ windows)
- Cross-asset validation (if applicable)
- Regime testing (bull/bear/sideways)
- Black swan stress tests (2008, 2020)
- Transaction cost analysis

### Stage 5: Documentation
- Complete RESULTS.md with all sections
- Document assumptions and limitations
- Record overfitting risk assessment
- Mark status: PASS or FAIL

### Stage 6: Manager Review
- Manager reviews RESULTS.md
- Validates all criteria met
- Makes go/no-go decision
- Updates `strategies` table status

---

## Performance Benchmarks

### Minimum Validation Criteria

**From RISK_POLICY_FRAMEWORK.md - HIGH Policy**:
- Sharpe Ratio: **≥ 0.6** (recommend ≥1.0 for deployment)
- Maximum Drawdown: **≤ 40%** (recommend ≤15% for deployment)
- Win Rate: **≥ 25%** OR Profit Factor **≥ 1.2**
- Sample Size: **≥ 100 trades**
- Out-of-Sample: **≥ 70% of in-sample performance**
- Walk-Forward: **> 70% profitable windows**

**Recommended for Deployment**:
- Sharpe Ratio: **≥ 1.0**
- Maximum Drawdown: **≤ 15%**
- Win Rate: **≥ 40%**
- Profit Factor: **≥ 1.4**

### Asset Class Expectations

| Asset Class | Expected Sharpe | Expected Max DD | Expected Win Rate |
|-------------|----------------|-----------------|-------------------|
| **Stocks** | 0.8 - 1.5 | 10-20% | 35-50% |
| **Crypto** | 1.0 - 2.0 | 15-25% | 30-45% |
| **Options** | 1.2 - 2.5 | 12-18% | 40-60% |
| **Forex** | 0.6 - 1.2 | 8-15% | 45-55% |

---

## Common Failure Reasons

### Why Backtests Fail

1. **Insufficient Sample Size**: < 100 trades
   → Solution: Extend data period or reduce trade frequency threshold

2. **Poor Out-of-Sample Performance**: < 70% of in-sample
   → Solution: Strategy likely overfit, return to research

3. **Excessive Drawdown**: > 40%
   → Solution: Add risk management, tighter stops

4. **Failed Walk-Forward**: < 70% profitable windows
   → Solution: Strategy not robust across time periods

5. **Black Swan Failure**: Large losses during 2008/2020
   → Solution: Add tail risk hedges or circuit breakers

6. **Transaction Costs Kill Edge**: Profitable before costs, unprofitable after
   → Solution: Reduce trade frequency or increase profit targets

---

## Data Requirements

### Minimum Data Periods

**From system_config.yaml and backtest requirements**:

| Asset Class | Minimum Period | Recommended Period | Timeframe |
|-------------|---------------|-------------------|-----------|
| **Crypto** | 3 years | 5+ years (500+ weeks) | 6h candles |
| **Stocks** | 5 years | 10+ years (1000+ weeks) | Daily |
| **Options** | 3 years | 5+ years | Daily |

### Data Sources

**Current Setup**:
- Crypto: `datasets/crypto/` (BTC, ETH, SOL, ADA, DOGE, XRP)
- Stocks: `datasets/stocks/` (collection scripts available)
- Index: `datasets/index/` (S&P 500)

**Collection**:
- Primary: `data_collection.py` (yfinance)
- Crypto-specific: CoinGecko, Coinbase, HyperLiquid collectors

---

## Quick Actions

### Start New Backtest

```bash
# 1. Create test directory
mkdir "data/backtests/test2"

# 2. Copy template
cp "agents/backtest/test_template.py" "data/backtests/test2/my_strategy.py"

# 3. Update TEST_INDEX.md (add to "In Progress")
# 4. Update strategies table status to "In Backtest"
```

### Complete Backtest

```bash
# 1. Create RESULTS.md in test directory
# 2. Document all validation tests
# 3. Mark status: PASS or FAIL
# 4. Update TEST_INDEX.md with results
# 5. Update strategies table status
```

### Review Backtest

```bash
# 1. Read RESULTS.md
# 2. Verify all validation criteria passed
# 3. Check for overfitting red flags
# 4. Make decision: Approve/Reject/Return for modifications
# 5. Update strategies table with Manager decision
```

---

## Backtest Checklist

Before marking a backtest as complete, ensure:

- [ ] RESULTS.md exists and is complete
- [ ] All performance metrics calculated and documented
- [ ] Out-of-sample test completed (≥30% of data)
- [ ] Walk-forward analysis completed (≥5 windows)
- [ ] Black swan stress tests passed (2008, 2020)
- [ ] Transaction costs included and strategy still profitable
- [ ] Overfitting risk assessed and documented
- [ ] Final status marked: PASS or FAIL
- [ ] Strategy implementation file(s) included
- [ ] TEST_INDEX.md updated
- [ ] `strategies` table updated

---

## Notes

- **Never delete failed tests** - keep them for learning and avoiding repeated mistakes
- **Document everything** - future backtests can learn from past tests
- **Be skeptical of perfect results** - Sharpe >3 or Win Rate >80% likely indicates overfitting
- **Respect the process** - don't skip validation steps even if initial results look good

---

**This index is maintained by the Backtest Agent and reviewed weekly by the Manager.**
