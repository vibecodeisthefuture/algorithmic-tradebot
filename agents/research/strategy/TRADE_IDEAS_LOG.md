# Trade Ideas Log

> [!IMPORTANT]
> **Trade ideas are now tracked in the `strategies` database table:** `data/tradebot.db`

This document explains the database-backed trade ideas tracking system and provides a template example. The database format enables better automation, filtering, and integration with backtesting scripts.

---

## Database Schema

The `strategies` table uses the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| **ID** | Unique identifier (001, 002, etc.) | 001 |
| **Name** | Strategy name | Short Iron Condor - Low VIX |
| **Type** | Strategy type | Income, Momentum, Mean-Reversion, Volatility, Arbitrage |
| **Asset_Class** | Asset class | Equities, Options, Futures, Crypto |
| **Market_Outlook** | Required market conditions | Bullish, Bearish, Neutral, High Vol, Low Vol |
| **Status** | Current status | Research, Ready for Backtest, Backtesting, Validated, Rejected, Active, Retired |
| **Priority** | Priority level | High, Medium, Low |
| **Date_Created** | Creation date | YYYY-MM-DD |
| **Last_Updated** | Last modification date | YYYY-MM-DD |
| **Strategy_Logic_Summary** | Brief 1-2 sentence summary | "Sell iron condors on SPY when VIX<15..." |
| **Expected_Win_Rate** | Expected win rate | 70-75% |
| **Expected_Sharpe** | Expected Sharpe ratio | >1.0 |
| **Max_Drawdown** | Expected maximum drawdown | 15-20% |
| **Backtest_Status** | Backtesting progress | Not Started, In Progress, Completed, Failed |
| **Notes** | Additional notes | Brief observations or warnings |
| **File_Link** | Link to detailed strategy file (optional) | Path to detailed markdown if exists |

---

## How to Add a New Trade Idea

### Method 1: SQLAlchemy Entry (Recommended)
```python
from agents.common.database import get_db_session
from agents.common.models import Strategy, StrategyStatus
from datetime import datetime, timezone

with get_db_session() as session:
    strategy = Strategy(
        name='Crypto Liquidation Bounce',
        type='Mean-Reversion',
        asset_class='Crypto',
        market_outlook='High Volatility',
        status=StrategyStatus.READY_FOR_BACKTEST,
        priority='High',
        strategy_logic_summary='Buy BTC after $200M+ liquidation cascade completes',
        expected_win_rate='70%',
        expected_sharpe='1.5',
        max_drawdown='12%',
        notes='Requires CoinGlass API data',
        created_at=datetime.now(timezone.utc),
    )
    session.add(strategy)
```

### Method 2: Direct Database Entry (Python)
```python
from agents.common.database import get_db_session
from agents.common.models import Strategy
from datetime import date, datetime, timezone

with get_db_session() as session:
    new_idea = Strategy(
        name='Crypto Liquidation Bounce',
        type='Mean-Reversion',
        asset_class='Crypto',
        market_outlook='High Volatility',
        status='Ready for Backtest',
        priority='High',
        strategy_logic_summary='Buy BTC after $200M+ liquidation cascade completes',
        expected_win_rate='70%',
        expected_sharpe='1.5',
        max_drawdown='12%',
        notes='Requires CoinGlass API data',
        created_at=datetime.now(timezone.utc),
    )
    session.add(new_idea)
```

---

## Status Definitions

- **Research**: Currently investigating, hypothesis not fully formed
- **Ready for Backtest**: Complete hypothesis, entry/exit rules defined, ready to test
- **Backtesting**: Currently being tested with historical data
- **Validated**: Passed backtest criteria, approved for paper/live trading
- **Rejected**: Failed backtest or invalidated by research
- **Active**: Currently trading in paper or live account
- **Retired**: Previously traded but no longer active

---

## Workflow Integration

### Research → Backtest → Implementation

```
1. Research Stage
   ↓
   Add idea to strategies table with status="Ready for Backtest"
   ↓
2. Backtest Stage
   ↓
   Update strategies table: status="Backtesting"
   ↓
   Run backtest, generate results
   ↓
   Update strategies table: status="Validated" or "Rejected"
   ↓
3. Implementation Stage (if Validated)
   ↓
   Update strategies table: status="Active"
```

---

## Example Trade Idea Template

Below is the detailed template for Trade Idea #001 (Short Iron Condor). For new ideas, you can reference this structure for creating detailed documentation if needed, though the `strategies` database table entry is the primary source of truth.

---

## Trade Idea #001: Short Iron Condor - Low VIX

### Strategy Classification
- **Type**: Income / Volatility
- **Market Outlook**: Neutral to Low Volatility
- **Asset Class**: Equity Options (ETFs)
- **Time Horizon**: 30-45 Days to Expiration

### Hypothesis

Short iron condors on high-liquidity ETFs (SPY, QQQ, IWM) during low VIX environments (VIX < 15) will generate consistent monthly income with win rates above 70% by exploiting elevated option premiums relative to realized volatility. The strategy profits from theta decay and range-bound price action, with defined risk on both upside and downside.

### Strategy Logic

#### Entry Conditions
1. **Volatility Filter**: VIX < 15 for at least 5 consecutive trading days
2. **Price Action**: Underlying ETF within ±2% of 20-day moving average (range-bound confirmation)
3. **Options Selection**: 
   - Days to Expiration (DTE): 30-45 days
   - Short Put Strike: ~10 delta (out-of-the-money)
   - Long Put Strike: ~5 delta (further out-of-the-money)
   - Short Call Strike: ~10 delta (out-of-the-money)
   - Long Call Strike: ~5 delta (further out-of-the-money)
4. **Premium Target**: Collect minimum of 33% of the spread width in credit

#### Exit Conditions
1. **Profit Target**: Close position when profit reaches 50% of maximum profit
2. **Stop Loss**: Close position if loss reaches 200% of maximum profit (2x credit received)
3. **Time Exit**: Close all positions at 7 DTE regardless of P&L (avoid gamma risk)
4. **Volatility Exit**: Close immediately if VIX spikes above 20

#### Position Sizing
- Risk no more than 2% of total account value on any single iron condor
- Maximum of 5 concurrent positions to maintain diversification

### Expected Characteristics

- **Win Rate**: 70-75%
- **Average Win**: +$80 per contract
- **Average Loss**: -$240 per contract
- **Profit Factor**: ~1.4-1.6
- **Max Drawdown**: 15-20%
- **Hold Time**: 23-38 days average

### Risk Factors

1. **Black Swan Events**: Major market crashes or volatility spikes
2. **Trending Markets**: Strong directional moves challenge one side
3. **Gap Risk**: Weekend gaps or overnight moves during earnings
4. **Liquidity Risk**: Wide bid-ask spreads erode profits

### Research Sources

1. OPTIONS_STRATEGIES.md - Section #20: Short Iron Condor
2. TastyTrade Research: "Managing Spreads at 50% Profit"
3. Interactive Brokers: "Iron Condor Strategy Guide"
4. Academic: "Selling Options: An Empirical Analysis" - Cohen, R.B. (2015)

---

**Date Created**: 2026-02-02  
**Status**: Example (Template for future trade ideas)  
**CSV Entry**: See row in `strategies` table in `data/tradebot.db`

---

## Benefits of Database Format

- ✅ **Automation**: SQLAlchemy ORM for programmatic read/write
- ✅ **Filtering**: SQL queries for status, priority, asset class filtering
- ✅ **Integration**: Direct joins with backtest_results and trades tables
- ✅ **Concurrency**: WAL mode supports concurrent agent access
- ✅ **Scalability**: Handles thousands of trade ideas efficiently
- ✅ **Analytics**: Rich SQL aggregation and reporting

---

*For detailed strategy documentation, refer to this file. For tracking and status management, use the `strategies` table in `data/tradebot.db`.*
