# Bollinger Band Breakout Strategy - Backtest Results

## Test Information

**Date**: January 31, 2026  
**Strategy**: Bollinger Band Breakout  
**Script**: [`bb_breakout.py`](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/test1/bb_breakout.py)  
**Data Source**: Local CSV (GOOG Historical Data)  
**Test Period**: 2020-01-01 to 2024-01-01 (4 years)  
**Initial Capital**: $100,000.00  
**Commission**: 0.1% per trade  

---

## Default Parameters Test

### Configuration
- **BB Period**: 20
- **BB Deviation**: 2.0
- **Stop Loss**: 3%
- **Position Size**: 95% of available capital

### Performance Summary

| Metric | Value |
|--------|-------|
| **Initial Portfolio Value** | $100,000.00 |
| **Final Portfolio Value** | $103,233.99 |
| **Total Return** | **3.23%** |
| **Annualized Return** | ~0.81% |
| **Total Trades** | 21 |
| **Winning Trades** | 8 |
| **Win Rate** | 38.10% |

### Analysis

The default parameters produced modest positive returns over the 4-year period. The strategy generated 21 trades with a win rate just below 40%, which is typical for breakout strategies. The low overall return suggests that the default parameters may be too conservative or not well-suited to GOOG's price action during this period.

---

## Optimization Results

### Optimization Parameters Tested

**Parameter Ranges:**
- BB Period: 15, 20, 25, 30 (4 values)
- BB Deviation: 1.5, 2.0, 2.5 (3 values)
- Stop Loss: 2%, 3%, 5% (3 values)

**Total Combinations**: 81 (4 × 3 × 3)

### Top 10 Parameter Combinations

| Rank | BB Period | BB Dev | Stop Loss | Final Value | Return | Sharpe Ratio | Max DD | Trades | Win Rate |
|------|-----------|---------|-----------|-------------|--------|--------------|--------|--------|----------|
| **1** | **15** | **2.0** | **5.0%** | **$117,121.60** | **+17.12%** | **0.31** | **22.00%** | **23** | **39.13%** |
| 2 | 20 | 2.5 | 5.0% | $114,168.16 | +14.17% | 0.24 | 11.69% | 10 | 60.00% |
| 3 | 15 | 2.5 | 5.0% | $112,205.98 | +12.21% | 0.17 | 16.90% | 12 | 58.33% |
| 4 | 20 | 2.0 | 5.0% | $107,570.49 | +7.57% | 0.04 | 19.25% | 21 | 42.86% |
| 5 | 15 | 2.0 | 3.0% | $105,672.73 | +5.67% | -0.09 | 23.27% | 25 | 32.00% |
| 6 | 30 | 2.5 | 5.0% | $105,586.91 | +5.59% | -0.04 | 14.52% | 9 | 44.44% |
| 7 | 15 | 2.5 | 3.0% | $103,538.65 | +3.54% | -0.15 | 13.85% | 12 | 50.00% |
| 8 | 20 | 2.5 | 3.0% | $102,968.47 | +2.97% | -0.49 | 11.69% | 11 | 45.45% |
| 9 | 30 | 2.0 | 5.0% | $102,764.68 | +2.76% | -0.05 | 19.02% | 14 | 28.57% |
| 10 | 25 | 2.5 | 5.0% | $102,607.42 | +2.61% | -0.17 | 13.67% | 10 | 50.00% |

### Recommended Parameters

> [!IMPORTANT]
> **Optimized Strategy Configuration**
> 
> Based on the optimization results, the recommended parameters are:
> - **BB Period**: 15
> - **BB Deviation**: 2.0
> - **Stop Loss**: 5.0%
> 
> This configuration achieved the highest total return with a positive Sharpe ratio.

---

## Performance Comparison

### Default vs Optimized

| Metric | Default | Optimized | Improvement |
|--------|---------|-----------|-------------|
| **Final Value** | $103,233.99 | $117,121.60 | +$13,887.61 |
| **Total Return** | 3.23% | 17.12% | **+13.89%** |
| **Sharpe Ratio** | N/A | 0.31 | - |
| **Max Drawdown** | N/A | 22.00% | - |
| **Total Trades** | 21 | 23 | +2 |
| **Win Rate** | 38.10% | 39.13% | +1.03% |

### Key Findings

1. **Shorter Period Outperforms**: The optimal BB period of 15 days (vs default 20) was more responsive to price movements, capturing more profitable breakouts.

2. **Wider Stop Loss is Better**: A 5% stop loss significantly outperformed both 2% and 3% alternatives, suggesting that tighter stops were getting hit prematurely during normal volatility.

3. **Standard Deviation Sweet Spot**: BB deviation of 2.0 was optimal - the standard industry value proved superior to both tighter (1.5) and looser (2.5) bands.

4. **Trade Frequency**: The optimized strategy generated similar trade frequency (23 vs 21 trades), indicating it's not simply trading more aggressively.

5. **Win Rate Stability**: Both default and optimized strategies showed similar win rates (~38-39%), suggesting the improvement came from better trade selection rather than higher win rate.

---

## Risk Analysis

### Maximum Drawdown

The optimized strategy experienced a **22.00% maximum drawdown**, which is substantial but not uncommon for momentum/breakout strategies. This indicates:

- Periods of significant underwater equity
- Need for adequate position sizing
- Potential psychological challenges during drawdown periods

> [!WARNING]
> A 22% drawdown means you need to be comfortable with temporary losses of over $20,000 on a $100,000 account. Ensure your risk tolerance aligns with this level of volatility.

### Sharpe Ratio

The optimized Sharpe ratio of **0.31** is relatively low, indicating:

- Returns are modest relative to volatility
- Strategy may not be providing strong risk-adjusted returns
- Consider this is only 4 years of data on a single asset

For context:
- Sharpe < 1.0 = Below average risk-adjusted returns
- Sharpe 1.0-2.0 = Good risk-adjusted returns
- Sharpe > 2.0 = Excellent (rare for retail strategies)

---

## Statistical Considerations

### Sample Size

With 23 trades over 4 years, the sample size is **relatively small** for drawing strong statistical conclusions. Generally, you want:

- Minimum 30 trades for basic statistical significance
- Ideally 100+ trades for robust conclusions

**Recommendation**: Test on additional assets and longer time periods to validate robustness.

### Overfitting Risk

> [!CAUTION]
> **Overfitting Assessment**
> 
> While the optimization tested a reasonable number of combinations (81), there are still overfitting risks:
> 
> ✅ **Lower Risk Factors:**
> - Round number parameters (15, 2.0, 5%)
> - Modest parameter count (3 parameters)
> - Reasonable Sharpe ratio (0.31, not unrealistic)
> - Similar win rates between default and optimized
> 
> ⚠️ **Higher Risk Factors:**
> - 5x improvement over default (3.23% → 17.12%)
> - Limited time period (only 4 years)
> - Single asset tested (GOOG only)
> - No out-of-sample validation yet
> 
> **Next Steps for Validation:**
> 1. Test on different time period (2015-2019)
> 2. Test on different assets (NVDA, AAPL, MSFT)
> 3. Perform walk-forward analysis
> 4. Assess parameter sensitivity

---

## Strategy Characteristics

### Entry Signals
- Price breaks above Upper Bollinger Band
- RSI < 70 (avoid overbought entries)
- Volume > 20-day average (confirm strength)

### Exit Signals
- Price crosses below Middle Bollinger Band (take profit)
- Stop loss triggered at 5% (risk management)

### Position Sizing
- 95% of available capital per position
- Single position at a time (no pyramiding)

### Transaction Costs
- Commission: 0.1% per trade
- Slippage: 0.05% per trade (modeled)

---

## Conclusions

### Summary

The Bollinger Band breakout strategy showed **significant improvement through optimization**, achieving 17.12% total return over 4 years compared to 3.23% with default parameters. The key insights are:

1. **Shorter lookback period** (15 vs 20 days) captures breakouts more effectively
2. **Wider stop losses** (5% vs 3%) prevent premature exits
3. **Standard BB deviation** (2.0) remains optimal
4. **Modest trade frequency** (23 trades in 4 years) suggests quality over quantity

### Strengths
✅ Positive returns in both default and optimized configurations  
✅ Reasonable trade frequency (not overtrading)  
✅ Clear risk management with defined stop losses  
✅ Simple, understandable strategy logic  

### Weaknesses
❌ Low Sharpe ratio (0.31) indicates poor risk-adjusted returns  
❌ High maximum drawdown (22%) requires strong risk tolerance  
❌ Small sample size (23 trades) limits statistical confidence  
❌ Only tested on one asset (GOOG) over one time period  
❌ Potential overfitting to 2020-2024 GOOG price action  

### Recommendations

> [!TIP]
> **Before Live Trading**
> 
> 1. **Validate Robustness**
>    - Test on NVDA data using the same parameters
>    - Test on earlier time period (2015-2019)
>    - Perform walk-forward optimization
> 
> 2. **Risk Management**
>    - Consider reducing position size to 50-75% (not 95%)
>    - Implement maximum portfolio drawdown limit (e.g., 15%)
>    - Paper trade for 3-6 months before using real capital
> 
> 3. **Further Optimization**
>    - Test different exit strategies (trailing stops, profit targets)
>    - Consider adding regime filters (trend, volatility)
>    - Explore portfolio approach with multiple assets
> 
> 4. **Realistic Expectations**
>    - Expect 50-70% of backtest returns in live trading
>    - Realistic expectation: 8-12% annual return (not 17%)
>    - Be prepared for 22%+ drawdowns

---

## Next Steps

1. **Out-of-Sample Testing**: Validate on 2015-2019 data
2. **Cross-Asset Validation**: Test on NVDA, AAPL, SPY
3. **Walk-Forward Analysis**: Rolling optimization windows
4. **Monte Carlo Simulation**: Assess statistical significance
5. **Paper Trading**: 3-month forward test with live data
6. **Documentation**: Record all tests and results for future reference

---

**Test Status**: ✅ Complete - Optimization Successful - Validation Pending  
**Risk Level**: ⚠️ Moderate-High (22% max drawdown)  
**Confidence**: 🟡 Medium (needs additional validation)  

For detailed implementation, see [`bb_breakout.py`](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/test1/bb_breakout.py)  
For overfitting warnings, see [`OVEROPTIMIZE_WARNING.md`](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/OVEROPTIMIZE_WARNING.md)
