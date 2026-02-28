---
name: Alpaca Trading API
description: Submit stock and crypto orders, check portfolio status, and log all orders to CSV via Alpaca's Trading API
---

# Alpaca Trading API Skill

This skill enables AI agents to interact with Alpaca Markets for automated trading of stocks and cryptocurrencies.

## Prerequisites

### Required Software
- **Python 3.x** with `alpaca-py` library
- Environment variables for API credentials

### Required Credentials

**Paper Trading (this project uses paper trading only):**
```powershell
$env:ALPACA_API_KEY = "your_paper_api_key"
$env:ALPACA_API_SECRET = "your_paper_api_secret"
```

## 1. Connection & Authentication

### Connect to Alpaca

```python
from alpaca_connection import AlpacaConnection

# Connect to paper trading - uses ALPACA_API_KEY / ALPACA_API_SECRET
conn = AlpacaConnection()

# Test connection
conn.test_connection()
```

### Check Account Status

```python
account = conn.get_account()
print(f"Cash: ${float(account.cash):,.2f}")
print(f"Buying Power: ${float(account.buying_power):,.2f}")
print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
```

## 2. Portfolio Status

### View Full Status

```python
conn.print_full_status()  # Account, positions, and open orders
```

### Individual Components

```python
conn.print_account_summary()  # Account balance only
conn.print_positions()        # All positions with P&L
conn.print_open_orders()      # Pending orders only
```

### Get Raw Data

```python
positions = conn.get_positions()     # List of Position objects
orders = conn.get_orders(status='open')  # List of Order objects
```

## 3. Submitting Orders

### Initialize Order Manager

```python
from orders import OrderManager

order_mgr = OrderManager(conn.trading_client)
```

### Stock Orders

| Order Type | Example |
|------------|---------|
| Market (qty) | `order_mgr.submit_stock_order("AAPL", qty=10, side="buy")` |
| Market ($) | `order_mgr.submit_stock_order("AAPL", notional=500, side="buy")` |
| Limit | `order_mgr.submit_stock_order("AAPL", qty=10, side="buy", order_type="limit", limit_price=150.00)` |
| Stop | `order_mgr.submit_stock_order("AAPL", qty=10, side="sell", order_type="stop", stop_price=140.00)` |
| Bracket | `order_mgr.submit_stock_order("SPY", qty=10, side="buy", order_type="bracket", take_profit=550.00, stop_loss=500.00)` |

### Crypto Orders

| Order Type | Example |
|------------|---------|
| Market (qty) | `order_mgr.submit_crypto_order("BTC/USD", qty=0.01, side="buy")` |
| Market ($) | `order_mgr.submit_crypto_order("BTC/USD", notional=100, side="buy")` |
| Limit | `order_mgr.submit_crypto_order("ETH/USD", qty=0.5, limit_price=3000.00, side="buy")` |
| Sell All | `order_mgr.sell_all_crypto("BTC/USD")` |

### Order Management

```python
order_mgr.cancel_order(order_id="...")  # Cancel specific order
order_mgr.cancel_all_orders()           # Cancel all open orders
```

## 4. Order Logging

All orders are **automatically logged** to `trades` table in `data/tradebot.db`.

### CSV Schema

| Column | Description |
|--------|-------------|
| `timestamp` | ISO timestamp when order was placed |
| `orderID` | Unique Alpaca order ID |
| `assetType` | Stock or Crypto |
| `tickerSymbol` | e.g., AAPL, BTC/USD |
| `action` | buy or sell |
| `orderType` | market, limit, stop, bracket |
| `timeInForce` | day, gtc, ioc, fok |
| `quantity` | Number of shares/units |
| `notional` | Dollar amount (if notional order) |
| `limitPrice` | Limit price (if applicable) |
| `stopPrice` | Stop price (if applicable) |
| `avgFillPrice` | Actual execution price |
| `filledQty` | Quantity filled |
| `orderValue` | Total order value |
| `status` | pending_new, filled, cancelled |
| `commission` | Trading fees (0 for Alpaca) |

### Custom CSV Path

```python
order_mgr = OrderManager(conn.trading_client, csv_path="C:/custom/path/orders.csv")
```

### View Order History

```python
from order_logger import OrderLogger

logger = OrderLogger()
logger.print_recent_orders(limit=10)

# Get statistics
stats = logger.get_statistics()
print(f"Total Orders: {stats['total_orders']}")
print(f"Total Value: ${stats['total_value']:,.2f}")
```

## 5. Order Parameters Reference

### Time in Force

| Value | Description |
|-------|-------------|
| `day` | Valid for current trading day |
| `gtc` | Good til cancelled (default for crypto) |
| `ioc` | Immediate or cancel |
| `fok` | Fill or kill |

### Supported Crypto Pairs

- `BTC/USD`, `ETH/USD`, `LTC/USD`, `BCH/USD`
- `DOGE/USD`, `AVAX/USD`, `SOL/USD`, and more

### Market Hours

- **Stocks**: 9:30 AM - 4:00 PM ET
- **Crypto**: 24/7

## 6. Common Workflows

### Buy Stock with Stop Loss

```python
from alpaca_connection import AlpacaConnection
from orders import OrderManager

conn = AlpacaConnection()
order_mgr = OrderManager(conn.trading_client)

# Buy 10 SPY with take profit and stop loss
order_mgr.submit_stock_order(
    symbol="SPY",
    qty=10,
    side="buy",
    order_type="bracket",
    take_profit=550.00,
    stop_loss=500.00
)
```

### Dollar-Cost Average Crypto

```python
# Buy $50 of Bitcoin
order_mgr.submit_crypto_order("BTC/USD", notional=50, side="buy")

# Buy $50 of Ethereum
order_mgr.submit_crypto_order("ETH/USD", notional=50, side="buy")
```

### Check and Rebalance

```python
# Check current positions
conn.print_positions()

# Sell all of a crypto position
order_mgr.sell_all_crypto("BTC/USD")
```

## 7. Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `API credentials not provided` | Missing env vars | Set `ALPACA_API_KEY` and `ALPACA_API_SECRET` |
| `403 Forbidden` | Invalid keys | Verify keys are valid paper trading credentials |
| `Symbol not found` | Wrong format | Stocks: `AAPL`, Crypto: `BTC/USD` |
| `Insufficient buying power` | Not enough funds | Check account balance |

### Best Practices

1. **Always use paper trading** for testing
2. **Check market hours** before stock orders
3. **Verify buying power** before large orders
4. **Monitor order status** after submission
5. **Review order history CSV** regularly

## 8. File Reference

| File | Purpose |
|------|---------|
| `alpaca_connection.py` | API connection and portfolio status |
| `orders.py` | Stock and crypto order submission |
| `order_logger.py` | CSV logging and order analysis |
| `data/tradebot.db` → `trades` | Persistent order archive |
| `requirements.txt` | Python dependencies |

## 9. ZeroMQ Event Bus Integration

All orders logged to the database are also broadcast as **real-time ZeroMQ notifications** so the Manager Orchestrator and Portfolio Tracker can react instantly to trade fills.

| Topic | Trigger | Payload |
|-------|---------|---------|
| `TRADE.EXECUTED` | Order filled or partially filled | `{order_id, symbol, side, qty, filled_price, status, broker, asset_type}` |
| `TRADE.FAILED` | Order rejected, cancelled, or expired | Same schema as `TRADE.EXECUTED` |

> [!NOTE]
> ZeroMQ publishing is best-effort. If `pyzmq` is not installed or the proxy is not running, orders are still logged to the database normally.

## Summary Checklist

When placing orders via Alpaca:

- [ ] Set environment variables for API credentials
- [ ] Connect with `AlpacaConnection()`
- [ ] Verify connection with `conn.test_connection()`
- [ ] Check buying power before orders
- [ ] Use correct symbol format (stocks vs crypto)
- [ ] Orders are automatically logged to CSV
- [ ] Check order status after submission
- [ ] Review `trades` table for audit trail

## Additional Resources

- [Alpaca Trading API Docs](https://docs.alpaca.markets/docs/getting-started-with-trading-api)
- [Alpaca Python SDK](https://github.com/alpacahq/alpaca-py)
- [Supported Crypto Pairs](https://alpaca.markets/support/crypto-pairs-on-alpaca/)
