# Data Schemas

## Overview

This document defines the **canonical data schemas** for all data stores in the TradeBot system.

> [!IMPORTANT]
> **As of v2.0**, the primary data store is the **SQLite Blackboard Database** (`data/tradebot.db`). CSV files have been migrated and archived to `data/archive/`. JSON state files are being superseded by the `system_state` table. See **Database Tables** below for current schemas.

**Purpose**:
- Enforce consistent data formats across all system components
- Enable automated schema validation
- Facilitate data exchange between agents via shared database
- Prevent data corruption and parsing errors

**Last Updated**: 2026-02-10
**Version**: 2.0

---

## Database Tables (v2.0 — Primary)

All agents communicate through `data/tradebot.db` (SQLite, WAL mode).
ORM models: `agents/common/models.py` | Enums: `agents/common/enums.py`

### 1. system_state

**Replaces**: `active_policy.json`, `portfolio_health.json`

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| key | STRING | PK | Unique config key (e.g. `risk_mode`) |
| value | TEXT | | JSON-serializable value |
| updated_at | DATETIME | | Auto-updated timestamp |

### 2. market_news

**Replaces**: `news_assessments_log.csv`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | INTEGER | PK (auto) | Unique ID |
| source | STRING | Yes | News source |
| headline | STRING | Yes | Headline text |
| content | TEXT | No | Full content |
| sentiment_score | FLOAT | No | -1.0 to 1.0 |
| impact_rating | ENUM | Yes | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO` |
| affected_assets | TEXT | No | Comma-separated tickers |
| opportunities_identified | TEXT | No | Trading opportunities |
| sources_urls | TEXT | No | Comma-separated URLs |
| discovered_at | DATETIME | Auto | Discovery timestamp |
| processed_by_manager | BOOLEAN | Default=False | Manager read flag |

### 3. strategies

**Replaces**: `trade_ideas_log.csv`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | INTEGER | PK (auto) | Unique ID |
| name | STRING | Yes | Strategy name |
| asset_class | STRING | No | e.g. `Crypto`, `Stocks` |
| strategy_type | STRING | No | e.g. `Breakout`, `Mean Reversion` |
| status | ENUM | Yes | See `StrategyStatus` enum |
| priority | STRING | Default=Medium | `High`, `Medium`, `Low` |
| parameters | JSON | No | Strategy params dict |
| source | STRING | No | Origin of idea |
| notes | TEXT | No | Additional context |
| news_id | INTEGER | FK→market_news | Linked news event |
| created_at | DATETIME | Auto | Creation timestamp |
| updated_at | DATETIME | Auto | Last modified |

**StrategyStatus** lifecycle: `NEW` → `READY_FOR_BACKTEST` → `BACKTESTING` → `BACKTEST_COMPLETE` → `LIVE_PAPER` → `LIVE_REAL` → `RETIRED`

### 4. backtest_results

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | INTEGER | PK (auto) | Unique ID |
| strategy_id | INTEGER | FK→strategies | Linked strategy |
| sharpe_ratio | FLOAT | No | Sharpe ratio |
| max_drawdown | FLOAT | No | Max drawdown % |
| win_rate | FLOAT | No | Win rate 0-1 |
| profit_factor | FLOAT | No | Profit factor |
| trades_count | INTEGER | No | Total trades |
| total_return_pct | FLOAT | No | Total return % |
| test_directory | STRING | No | Path to test results |
| notes | TEXT | No | Additional context |
| run_at | DATETIME | Auto | Test timestamp |

### 5. trades

**Replaces**: `order_history.csv`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | STRING | PK | Broker order ID |
| strategy_id | INTEGER | FK→strategies | Linked strategy |
| symbol | STRING | Yes | Ticker symbol |
| side | ENUM | Yes | `BUY`, `SELL` |
| qty | FLOAT | Yes | Ordered quantity |
| filled_qty | FLOAT | No | Filled quantity |
| filled_price | FLOAT | No | Avg fill price |
| order_type | STRING | No | `market`, `limit`, etc. |
| status | ENUM | Yes | `FILLED`, `PARTIAL`, `CANCELLED`, `REJECTED` |
| commission | FLOAT | No | Commission paid |
| broker | STRING | No | `ALPACA`, `OKX`, `IBKR` |
| risk_policy | ENUM | No | Active policy at execution |
| notes | TEXT | No | Additional context |
| executed_at | DATETIME | Auto | Execution timestamp |

### 6. portfolio_snapshots

**Replaces**: `portfolio_health_log.csv`, `portfolio_health.json`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | INTEGER | PK (auto) | Unique ID |
| total_equity | FLOAT | Yes | Total portfolio value |
| cash_balance | FLOAT | No | Cash available |
| daily_pnl | FLOAT | No | Day's P&L |
| drawdown_pct | FLOAT | No | Current drawdown % |
| vix_level | FLOAT | No | VIX at snapshot |
| positions_count | INTEGER | No | Open positions |
| leverage | FLOAT | No | Current leverage |
| risk_policy | ENUM | No | Active risk policy |
| timestamp | DATETIME | Auto | Snapshot time |

### 7. event_log

**New table** — inter-agent communication bus

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | INTEGER | PK (auto) | Unique ID |
| event_type | ENUM | Yes | See `EventType` enum |
| urgency | ENUM | No | `INFO`, `WARNING`, `CRITICAL`, `EMERGENCY` |
| source_agent | STRING | No | Emitting agent |
| target_agent | STRING | No | Target agent |
| summary | TEXT | No | Brief description |
| details | JSON | No | Event payload |
| acknowledged | BOOLEAN | Default=False | Manager saw it |
| acknowledged_by | STRING | No | Who acknowledged |
| acknowledged_at | DATETIME | No | Ack timestamp |
| response | TEXT | No | Manager response |
| created_at | DATETIME | Auto | Event timestamp |

### 8. policy_history

**Replaces**: `policy_change_history.csv`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| id | INTEGER | PK (auto) | Unique ID |
| old_policy | ENUM | Yes | Previous risk policy |
| new_policy | ENUM | Yes | New risk policy |
| changed_by | STRING | No | `manager`, `auto` |
| reason | TEXT | No | Why policy changed |
| vix_level | FLOAT | No | VIX at change time |
| drawdown_pct | FLOAT | No | Drawdown at change |
| trigger_type | ENUM | No | `MANUAL`, `VIX`, `DRAWDOWN`, `REGIME`, `EMERGENCY` |
| timestamp | DATETIME | Auto | Change timestamp |

---

## CSV Schemas (v1.0 — Legacy / Archived)

### 1. trade_ideas_log.csv

**Location**: `data/logs/trade_ideas_log.csv`
**Purpose**: Master pipeline for all trading strategy ideas from research to deployment

| Column | Type | Required | Valid Values | Example | Notes |
|--------|------|----------|--------------|---------|-------|
| ID | string | Yes | `ti-XXX` format | `ti-001` | Unique identifier, sequential |
| Name | string | Yes | Any | `BB Breakout BTC 6h` | Descriptive strategy name |
| Asset_Class | string | Yes | `Stocks`, `Crypto`, `Options`, `Forex` | `Crypto` | Primary asset class |
| Type | string | Yes | `Momentum`, `Mean-Reversion`, `Income`, `Volatility`, `Breakout`, `Arbitrage` | `Breakout` | Strategy category |
| Status | enum | Yes | See Status Values below | `Ready for Backtest` | Current pipeline stage |
| Priority | enum | Yes | `High`, `Medium`, `Low` | `High` | Research/backtest priority |
| Created_Date | date | Yes | `YYYY-MM-DD` | `2026-01-15` | Idea creation date |
| Last_Updated | date | Yes | `YYYY-MM-DD` | `2026-01-25` | Last status change |
| Source | string | No | Any | `Moon Dev YouTube` | Where idea originated |
| Notes | text | No | Any | `NEWS-DRIVEN from NA-003: Fed rate cut` | Additional context |
| Strategy_Logic_Summary | text | No | Any | `Enter long on BB upper band break, exit on lower band` | Brief logic description |
| Expected_Sharpe | float | No | > 0 | `1.2` | Expected Sharpe ratio |
| Expected_Max_DD | float | No | 0-100 | `15.5` | Expected max drawdown % |
| Backtest_ID | string | No | `test<N>` | `test1` | Reference to backtest directory |
| Deployed_Date | date | No | `YYYY-MM-DD` | `2026-03-01` | Live deployment date |
| Capital_Allocated | float | No | > 0 | `5000.00` | USD capital for live trading |

**Status Values** (in order of progression):
1. `Pending` - Initial research, not ready for backtest
2. `Ready for Backtest` - Fully specified, awaiting backtest
3. `In Backtest` - Currently being tested
4. `Failed Backtest` - Did not meet validation criteria
5. `Ready for Implementation` - Passed backtest validation
6. `Paper Trading` - Live paper trading phase
7. `Live` - Deployed to live trading
8. `Archived` - Retired or rejected

**Example Row**:
```csv
ti-001,BB Breakout BTC 6h,Crypto,Breakout,Ready for Implementation,High,2026-01-15,2026-01-20,Moon Dev YouTube,Bollinger Band breakout on 6h timeframe,Enter long on upper band break with volume confirmation,1.2,14.5,test1,,
```

**Validation Rules**:
- ID must be unique
- Status must progress logically (can't skip stages)
- Created_Date ≤ Last_Updated
- If Status = "Live", Deployed_Date and Capital_Allocated must be set
- If Status ≥ "In Backtest", Backtest_ID should be set

---

### 2. news_assessments_log.csv

**Location**: `data/logs/news_assessments_log.csv`
**Purpose**: Log all market news assessments and identified trading opportunities

| Column | Type | Required | Valid Values | Example | Notes |
|--------|------|----------|--------------|---------|-------|
| ID | string | Yes | `NA-XXX` | `NA-001` | Unique identifier |
| Date | datetime | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-03 09:30:00` | When news assessed |
| Event_Name | string | Yes | Any | `Fed Rate Decision` | Brief event description |
| Category | enum | Yes | See Categories below | `Monetary Policy` | News classification |
| Severity | enum | Yes | `Critical`, `High`, `Medium`, `Low`, `Info` | `High` | Market impact severity |
| USD_Impact_Probability | int | Yes | 0-100 | `85` | Likelihood of USD impact % |
| USD_Impact_Direction | enum | No | `Positive`, `Negative`, `Neutral`, `Mixed` | `Positive` | Expected USD direction |
| Affected_Assets | list | No | Comma-separated | `BTC,ETH,SPY,TLT` | Assets likely affected |
| Opportunities_Identified | text | No | Any | `Potential BTC momentum trade on rate cut` | Trading opportunities spotted |
| Sources | list | Yes | Comma-separated URLs | `https://bloomberg.com/...` | News source links |
| Assessment_Notes | text | No | Any | `Market expecting 25bp cut, consensus bullish` | Analyst notes |
| Follow_Up_Required | boolean | Yes | `true`, `false` | `true` | Needs continued monitoring |

**Category Values**:
- `Monetary Policy` - Central bank actions, interest rates
- `Economic Data` - GDP, unemployment, inflation, etc.
- `Geopolitical` - Wars, elections, sanctions
- `Earnings` - Corporate earnings reports
- `Regulation` - New laws, SEC actions
- `Technical` - Market structure, circuit breakers
- `Crypto-Specific` - Crypto regulations, exchange news
- `Other` - Miscellaneous

**Example Row**:
```csv
NA-001,2026-02-03 09:30:00,Fed Rate Decision,Monetary Policy,High,85,Positive,"BTC,ETH,SPY,TLT",Potential BTC momentum trade on rate cut,"https://bloomberg.com/fed-rates,https://wsj.com/fed",Market expecting 25bp cut consensus bullish,true
```

**Validation Rules**:
- ID must be unique
- Date must be ≤ current date
- USD_Impact_Probability must be 0-100
- Sources must be valid URLs
- If Opportunities_Identified is not empty, should link to trade_ideas_log.csv

---

### 3. order_history.csv

**Location**: `data/logs/order_history.csv`
**Purpose**: Complete audit trail of all order executions

| Column | Type | Required | Valid Values | Example | Notes |
|--------|------|----------|--------------|---------|-------|
| order_id | string | Yes | Alpaca order ID | `f8a7b3c2-1234-5678-abcd-...` | Unique Alpaca ID |
| timestamp | datetime | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-03 10:15:32` | Order submission time |
| symbol | string | Yes | Valid ticker | `BTC/USD`, `AAPL` | Asset symbol |
| side | enum | Yes | `buy`, `sell` | `buy` | Order direction |
| quantity | float | Yes | > 0 | `0.5`, `100` | Shares/coins/contracts |
| order_type | enum | Yes | `market`, `limit`, `stop`, `bracket` | `market` | Order type |
| limit_price | float | No | > 0 | `150.50` | Limit price (if applicable) |
| stop_price | float | No | > 0 | `145.00` | Stop price (if applicable) |
| filled_quantity | float | Yes | ≥ 0 | `0.5` | Actual filled amount |
| filled_avg_price | float | No | > 0 | `48250.75` | Average fill price |
| status | enum | Yes | `filled`, `partial`, `cancelled`, `rejected` | `filled` | Final order status |
| commission | float | Yes | ≥ 0 | `0.00` | Commission paid (usually $0 on Alpaca) |
| slippage_pct | float | No | Any | `0.05` | Slippage as % of expected price |
| strategy_id | string | No | From trade_ideas_log.csv | `ti-001` | Strategy that generated order |
| risk_policy | enum | Yes | `HIGH`, `MODERATE`, `LOW` | `HIGH` | Active risk policy at order time |
| notes | text | No | Any | `Circuit breaker close` | Additional context |

**Example Row**:
```csv
f8a7b3c2-1234,2026-02-03 10:15:32,BTC/USD,buy,0.5,market,,,0.5,48250.75,filled,0.00,0.05,ti-001,HIGH,Initial position entry
```

**Validation Rules**:
- order_id must be unique
- filled_quantity ≤ quantity
- If status = "filled", filled_quantity must = quantity
- If order_type = "limit", limit_price must be set
- commission should be 0.00 for Alpaca
- strategy_id should reference valid trade_ideas_log.csv ID

---

### 4. alerts_log.csv

**Location**: `data/logs/alerts_log.csv`
**Purpose**: Log all Portfolio Tracker alerts to Manager

| Column | Type | Required | Valid Values | Example | Notes |
|--------|------|----------|--------------|---------|-------|
| alert_id | string | Yes | `alert-XXX` | `alert-001` | Unique identifier |
| timestamp | datetime | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-03 14:30:00` | Alert generation time |
| level | enum | Yes | `INFO`, `CAUTION`, `URGENT`, `CRITICAL` | `URGENT` | Alert urgency level |
| asset_type | enum | Yes | `Stocks`, `Crypto`, `Mixed`, `Portfolio` | `Crypto` | What triggered alert |
| message | text | Yes | Any | `VIX at 26, recommend MODERATE policy` | Alert message |
| conditions | json | No | JSON object | `{"vix": 26, "drawdown": 9.5}` | Triggering conditions |
| recommendation | text | No | Any | `Switch to MODERATE policy` | Recommended action |
| manager_acknowledged | boolean | Yes | `true`, `false` | `true` | Manager saw alert |
| manager_response | text | No | Any | `Approved switch to MODERATE` | Manager's decision |
| response_time_minutes | int | No | ≥ 0 | `45` | Minutes until Manager response |
| action_taken | text | No | Any | `Updated active_policy.json to MODERATE` | What was done |

**Example Row**:
```csv
alert-001,2026-02-03 14:30:00,URGENT,Crypto,VIX at 26 recommend MODERATE policy,"{""vix"": 26 ""drawdown"": 9.5}",Switch to MODERATE policy,true,Approved switch to MODERATE,45,Updated active_policy.json to MODERATE
```

---

### 5. policy_change_history.csv

**Location**: `data/logs/policy_change_history.csv`
**Purpose**: Audit trail of all risk policy switches

| Column | Type | Required | Valid Values | Example | Notes |
|--------|------|----------|--------------|---------|-------|
| timestamp | datetime | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-03 14:35:00` | When policy switched |
| from_policy | enum | Yes | `HIGH`, `MODERATE`, `LOW` | `HIGH` | Previous policy |
| to_policy | enum | Yes | `HIGH`, `MODERATE`, `LOW` | `MODERATE` | New policy |
| changed_by | string | Yes | `Manager`, `AutoSwitch` (if enabled) | `Manager` | Who initiated switch |
| reason | text | Yes | Any | `VIX spike to 27, precautionary buffer` | Why policy changed |
| vix | float | No | ≥ 0 | `27.0` | VIX level at switch time |
| drawdown | float | No | 0-100 | `9.5` | Portfolio drawdown % at switch |
| trigger_type | enum | No | `Manual`, `VIX`, `Drawdown`, `Regime`, `Emergency` | `VIX` | What triggered switch |

**Example Row**:
```csv
2026-02-03 14:35:00,HIGH,MODERATE,Manager,VIX spike to 27 precautionary buffer,27.0,9.5,VIX
```

---

## JSON Schemas

### 6. active_policy.json

**Location**: `data/state/active_policy.json`
**Purpose**: Current active risk policy configuration

**Schema**:
```json
{
  "policy": "HIGH | MODERATE | LOW",
  "timestamp": "ISO 8601 datetime",
  "changed_by": "Manager | AutoSwitch",
  "reason": "string - explanation for current policy",
  "custom_overrides": {
    "max_leverage": "float (optional override)",
    "circuit_breaker_pct": "float (optional override)",
    "notes": "string (optional)"
  }
}
```

**Example**:
```json
{
  "policy": "HIGH",
  "timestamp": "2026-02-03T09:00:00",
  "changed_by": "Manager",
  "reason": "Markets stable, VIX 18, drawdown 3%, favorable growth conditions",
  "custom_overrides": {}
}
```

**Validation Rules**:
- policy must be one of: HIGH, MODERATE, LOW
- timestamp must be valid ISO 8601 format
- custom_overrides is optional, can be empty object

---

### 7. portfolio_health.json

**Location**: `data/state/portfolio_health.json`
**Purpose**: Real-time portfolio metrics for risk monitoring

**Schema**:
```json
{
  "peak_value": "float - all-time high portfolio value",
  "current_value": "float - current portfolio value",
  "drawdown_pct": "float - current drawdown %",
  "vix_current": "float - latest VIX reading",
  "last_updated": "ISO 8601 datetime",
  "positions_count": "int - number of open positions",
  "total_exposure": "float - total deployed capital as %",
  "leverage": "float - current leverage ratio",
  "cash_pct": "float - cash as % of portfolio",
  "top_positions": [
    {"symbol": "string", "value_pct": "float", "unrealized_pl_pct": "float"}
  ],
  "risk_metrics": {
    "portfolio_beta": "float (optional)",
    "sharpe_ratio_30d": "float (optional)",
    "correlation_avg": "float (optional)"
  }
}
```

**Example**:
```json
{
  "peak_value": 105000.00,
  "current_value": 98500.00,
  "drawdown_pct": 6.2,
  "vix_current": 22.0,
  "last_updated": "2026-02-03T14:30:00",
  "positions_count": 12,
  "total_exposure": 0.85,
  "leverage": 1.2,
  "cash_pct": 15.0,
  "top_positions": [
    {"symbol": "BTC/USD", "value_pct": 18.5, "unrealized_pl_pct": 12.3},
    {"symbol": "AAPL", "value_pct": 12.0, "unrealized_pl_pct": -3.2}
  ],
  "risk_metrics": {
    "portfolio_beta": 1.15,
    "sharpe_ratio_30d": 1.8,
    "correlation_avg": 0.45
  }
}
```

---

### 8. recommendations_queue.json

**Location**: `data/state/recommendations_queue.json`
**Purpose**: Pending Portfolio Tracker recommendations awaiting Manager review

**Schema**:
```json
[
  {
    "id": "string - rec-XXX format",
    "timestamp": "ISO 8601 datetime",
    "urgency": "INFO | CAUTION | URGENT | CRITICAL",
    "recommendation": "string - recommended action",
    "reasoning": "string - why recommendation made",
    "conditions": {
      "vix": "float (optional)",
      "drawdown": "float (optional)",
      "regime": "string (optional)",
      "custom": "any (optional)"
    },
    "status": "pending | approved | rejected | modified",
    "manager_response": "string or null",
    "manager_response_time": "ISO 8601 datetime or null"
  }
]
```

**Example**:
```json
[
  {
    "id": "rec-789",
    "timestamp": "2026-02-03T14:30:00",
    "urgency": "CAUTION",
    "recommendation": "Consider switching to MODERATE policy",
    "reasoning": "VIX rising to 26, approaching 25 threshold",
    "conditions": {
      "vix": 26.0,
      "drawdown": 9.5,
      "regime": "volatile"
    },
    "status": "pending",
    "manager_response": null,
    "manager_response_time": null
  }
]
```

---

### 9. crypto_volatility_index.json

**Location**: `data/state/crypto_volatility_index.json`
**Purpose**: Crypto-specific volatility metrics for risk assessment

**Schema**:
```json
{
  "btc_24h_volatility": "float - BTC 24h volatility %",
  "eth_24h_volatility": "float - ETH 24h volatility %",
  "funding_rate_btc": "float - BTC perpetual funding rate",
  "funding_rate_eth": "float - ETH perpetual funding rate",
  "open_interest_change_24h": "float - OI change %",
  "crypto_fear_index": "int 0-100",
  "last_updated": "ISO 8601 datetime",
  "regime": "normal | elevated | high | extreme"
}
```

**Example**:
```json
{
  "btc_24h_volatility": 4.2,
  "eth_24h_volatility": 5.8,
  "funding_rate_btc": 0.01,
  "funding_rate_eth": 0.015,
  "open_interest_change_24h": -12.5,
  "crypto_fear_index": 35,
  "last_updated": "2026-02-03T14:30:00",
  "regime": "elevated"
}
```

---

## Schema Validation

### Python Validation Example

```python
import pandas as pd
from datetime import datetime

def validate_trade_ideas_log(csv_path):
    """Validate trade_ideas_log.csv against schema"""
    required_columns = ['ID', 'Name', 'Asset_Class', 'Type', 'Status',
                       'Priority', 'Created_Date', 'Last_Updated']

    df = pd.read_csv(csv_path)

    # Check required columns
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Validate ID format
    invalid_ids = df[~df['ID'].str.match(r'^ti-\d+$')]
    if not invalid_ids.empty:
        raise ValueError(f"Invalid IDs: {invalid_ids['ID'].tolist()}")

    # Validate dates
    df['Created_Date'] = pd.to_datetime(df['Created_Date'])
    df['Last_Updated'] = pd.to_datetime(df['Last_Updated'])

    invalid_dates = df[df['Created_Date'] > df['Last_Updated']]
    if not invalid_dates.empty:
        raise ValueError(f"Created_Date > Last_Updated for: {invalid_dates['ID'].tolist()}")

    # Validate Status values
    valid_statuses = ['Pending', 'Ready for Backtest', 'In Backtest',
                     'Failed Backtest', 'Ready for Implementation',
                     'Paper Trading', 'Live', 'Archived']
    invalid_status = df[~df['Status'].isin(valid_statuses)]
    if not invalid_status.empty:
        raise ValueError(f"Invalid Status values for: {invalid_status['ID'].tolist()}")

    print(f"✅ {csv_path} validated successfully")
    return True
```

### Automated Validation Script

Create `scripts/validate_schemas.py` to run validation across all data files:

```python
#!/usr/bin/env python3
"""
Validate all TradeBot data files against schemas
Usage: python scripts/validate_schemas.py
"""

import sys
from pathlib import Path

# Import validation functions
from validation.trade_ideas import validate_trade_ideas_log
from validation.news import validate_news_assessments_log
from validation.orders import validate_order_history
from validation.alerts import validate_alerts_log
from validation.json_schemas import validate_active_policy, validate_portfolio_health

def main():
    errors = []

    # Validate CSV files
    try:
        validate_trade_ideas_log("data/logs/trade_ideas_log.csv")
    except Exception as e:
        errors.append(f"trade_ideas_log.csv: {e}")

    try:
        validate_news_assessments_log("data/logs/news_assessments_log.csv")
    except Exception as e:
        errors.append(f"news_assessments_log.csv: {e}")

    # Validate JSON files
    try:
        validate_active_policy("data/state/active_policy.json")
    except Exception as e:
        errors.append(f"active_policy.json: {e}")

    # Report results
    if errors:
        print(f"❌ Validation failed with {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ All schemas validated successfully")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Schema Evolution

### Version Control

When schemas change:
1. Update this document with new version number
2. Add migration script in `scripts/migrations/`
3. Update validation scripts
4. Announce changes to all agents
5. Test backward compatibility

### Migration Example

```python
# scripts/migrations/migrate_v1_to_v2.py
"""
Migrate trade_ideas_log.csv from v1.0 to v2.0
Added: Risk_Level column
"""

import pandas as pd

def migrate():
    df = pd.read_csv("data/logs/trade_ideas_log.csv")

    # Add new column with default value
    df['Risk_Level'] = 3  # Default to medium risk

    # Save with backup
    df.to_csv("data/logs/trade_ideas_log_v1_backup.csv", index=False)
    df.to_csv("data/logs/trade_ideas_log.csv", index=False)

    print("✅ Migration complete")

if __name__ == "__main__":
    migrate()
```

---

**All agents must validate their data outputs against these schemas before writing to the database. Schema violations should be treated as critical errors. Use `agents.common.models` for ORM access and `agents.common.enums` for validation.**
