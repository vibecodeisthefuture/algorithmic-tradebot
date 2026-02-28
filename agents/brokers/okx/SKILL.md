---
name: OKX Crypto Trading API
description: Submit real cryptocurrency buy/sell orders, check account balance, and log orders via OKX's Trading API
---

# OKX Crypto Trading API Skill

This skill enables AI agents to interact with OKX for **automated cryptocurrency trading with real funds**.

> [!CAUTION]
> **REAL MONEY TRADING**: This integration executes actual trades with real funds. Double-check all orders before execution.

## Prerequisites

### Required Software
- **Python 3.x** with `python-okx` library
- Environment variables for API credentials

### Required Credentials

Create API key at [OKX API Management](https://us.okx.com/account/my-api) with:
- **Read** permission (account info)
- **Trade** permission (place/cancel orders)
- IP whitelist configured for security

```powershell
$env:OKX_API_KEY = "your_api_key"
$env:OKX_SECRET_KEY = "your_secret_key"
$env:OKX_PASSPHRASE = "your_passphrase"
```

## 1. Connection & Authentication

### Connect to OKX

```python
from okx_connection import OKXConnection

# Connect using environment variables (US endpoint: us.okx.com)
conn = OKXConnection()

# Test connection
conn.test_connection()
```

### Check Account Status

```python
# Get balance info
result = conn.get_account_balance()
print(f"Total Equity: ${result['data'][0]['totalEq']}")
```

## 2. Account Status

### View Full Status

```python
conn.print_full_status()  # Account, balances, positions
```

### Individual Components

```python
conn.print_account_summary()  # Total equity only
conn.print_balances()         # All currency balances
conn.print_positions()        # Open positions
```

## 3. Submitting Orders

### Initialize Order Manager

```python
from okx_orders import OKXOrderManager

order_mgr = OKXOrderManager(conn.trade_api, conn.account_api)
```

### Crypto Orders

| Order Type | Example |
|------------|---------|
| Market Buy | `order_mgr.submit_market_order("BTC-USDT", "buy", "0.001")` |
| Market Sell | `order_mgr.submit_market_order("ETH-USDT", "sell", "0.1")` |
| Limit Buy | `order_mgr.submit_limit_order("BTC-USDT", "buy", "0.001", "40000")` |
| Limit Sell | `order_mgr.submit_limit_order("ETH-USDT", "sell", "0.1", "4000")` |

### Order Management

```python
order_mgr.cancel_order(inst_id="BTC-USDT", ord_id="...")  # Cancel specific
order_mgr.cancel_all_orders()  # Cancel all pending
order_mgr.print_open_orders()  # View open orders
```

## 4. Order Logging

All orders are **automatically logged** to `trades` table in `data/tradebot.db`.

### CSV Schema

| Column | Description |
|--------|-------------|
| `timestamp` | ISO timestamp |
| `orderID` | OKX order ID |
| `instId` | Instrument (e.g., BTC-USDT) |
| `action` | buy or sell |
| `orderType` | market or limit |
| `quantity` | Order size |
| `limitPrice` | Limit price |
| `avgFillPrice` | Execution price |
| `status` | Order status |
| `fee` | Trading fee |

### View Order History

```python
from okx_order_logger import OKXOrderLogger

logger = OKXOrderLogger()
logger.print_recent_orders(limit=10)
logger.analyze()  # Full statistics
```

## 5. Instrument ID Format

OKX uses specific instrument ID formats:

| Type | Format | Examples |
|------|--------|----------|
| Spot | `{BASE}-{QUOTE}` | `BTC-USDT`, `ETH-USDT`, `SOL-USDT` |

### Common Trading Pairs

- `BTC-USDT`, `ETH-USDT`, `SOL-USDT`, `XRP-USDT`
- `DOGE-USDT`, `AVAX-USDT`, `LINK-USDT`, `DOT-USDT`

## 6. Common Workflows

### Buy Crypto with Market Order

```python
from okx_connection import OKXConnection
from okx_orders import OKXOrderManager

conn = OKXConnection()
order_mgr = OKXOrderManager(conn.trade_api)

# Buy 0.001 BTC at market price
order_mgr.submit_market_order("BTC-USDT", "buy", "0.001")
```

### Place Limit Order

```python
# Buy 0.01 ETH at $3000
order_mgr.submit_limit_order("ETH-USDT", "buy", "0.01", "3000")
```

### Check and Cancel Orders

```python
# View open orders
order_mgr.print_open_orders()

# Cancel all orders
order_mgr.cancel_all_orders()
```

## 7. Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `API credentials not provided` | Missing env vars | Set OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE |
| `Invalid API key` | Wrong credentials | Verify keys at OKX website |
| `Insufficient balance` | Not enough funds | Check account balance |
| `Invalid instId` | Wrong format | Use format like `BTC-USDT` |

### Best Practices

1. **Verify credentials** before trading
2. **Start with small orders** to test
3. **Check balances** before placing orders
4. **Monitor order status** after submission
5. **Review CSV logs** regularly

## 8. File Reference

| File | Purpose |
|------|---------|
| `okx_connection.py` | API connection and account status |
| `okx_orders.py` | Order submission and management |
| `okx_order_logger.py` | CSV logging and analysis |
| `data/tradebot.db` → `trades` | Order archive |
| `requirements.txt` | Python dependencies |

## Summary Checklist

When placing orders via OKX:

- [ ] Set environment variables for API credentials
- [ ] Connect with `OKXConnection()`
- [ ] Verify connection with `conn.test_connection()`
- [ ] Check balance before orders
- [ ] Use correct instrument format (`BTC-USDT`)
- [ ] Orders auto-logged to CSV
- [ ] Review `trades` table for audit

## Additional Resources

- [OKX US API Documentation](https://us.okx.com/docs-v5/en/)
- [OKX API Key Management](https://us.okx.com/account/my-api)
- [python-okx SDK](https://pypi.org/project/python-okx/)
