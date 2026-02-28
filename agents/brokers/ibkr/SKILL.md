---
name: IBKR Client Portal API
description: Execute LIVE trades for stocks, options, and futures via Interactive Brokers Client Portal Gateway API
---

# IBKR Client Portal API Skill

This skill enables AI agents to execute **LIVE trades** via Interactive Brokers Client Portal Gateway API.

## Broker Architecture

| Broker | Purpose | Asset Types |
|--------|---------|-------------|
| **Alpaca** | Paper trading ONLY | Stocks, Crypto (testing) |
| **IBKR** | Live trading | Stocks, Options, Futures |
| **OKX** | Live crypto (US endpoint) | Crypto only |

**Important**: IBKR is for LIVE trading with real money. Always test orders via Alpaca paper trading first.

## Prerequisites

### Required Software
- **Java Runtime Environment 8+** (for Client Portal Gateway)
- **Python 3.x** with `requests` and `urllib3` libraries
- **IBKR Client Portal Gateway** (installed in `clientportal.beta.gw/`)

### Required Credentials
- Active IBKR Pro account (funded)
- Two-Factor Authentication enabled
- Environment variables (optional, for reference):
```powershell
$env:IBKR_USERNAME = "your_username"
$env:IBKR_PASSWORD = "your_password"
```

## 1. Starting the Gateway

The Client Portal Gateway must be running before any API operations.

### Start Command
```powershell
cd "3. Implement/IBKR Client Portal API/clientportal.beta.gw"
bin\run.bat root\conf.yaml
```

### Expected Output
```
Open https://localhost:5000 to login
```

### Important Notes
- Gateway runs on `https://localhost:5000` by default
- Uses self-signed SSL certificate
- Gateway must remain running for all API operations

## 2. Authentication

**CRITICAL**: IBKR does NOT support programmatic login. Authentication MUST be done manually through a web browser.

### Authentication Steps

1. **Navigate to**: `https://localhost:5000`
2. **Enter credentials**: Username and password
3. **Complete Two-Factor Authentication**
4. **Wait for**: "Client login succeeds" message

### Checking Authentication Status

```python
from ibkr_connection import IBKRConnection

conn = IBKRConnection()
if conn.is_authenticated():
    print("Session is authenticated")
else:
    print("Please login via browser at https://localhost:5000")
```

## 3. Session Management

IBKR sessions timeout after 10-15 minutes of inactivity.

### Automatic Session Refresh

```python
from ibkr_session_manager import IBKRSessionManager

manager = IBKRSessionManager()
manager.start()  # Starts background keepalive
# ... do trading operations ...
manager.stop()   # Graceful shutdown
```

### Manual Session Refresh

```python
conn.tickle_session()  # Keep session alive
```

## 4. Portfolio Status

### View Full Status

```python
from ibkr_connection import IBKRConnection

conn = IBKRConnection()
conn.print_full_status()  # Account, positions, and orders
```

### Individual Components

```python
conn.print_account_summary()  # Account balance only
conn.print_positions()        # All positions with P&L
conn.print_open_orders()      # Pending orders only
```

### Get Raw Data

```python
account = conn.get_account()
positions = conn.get_positions()
orders = conn.get_orders(status='open')
```

## 5. Submitting Orders

### Initialize Order Manager

```python
from ibkr_connection import IBKRConnection
from ibkr_orders import IBKROrderManager

conn = IBKRConnection()
order_mgr = IBKROrderManager(conn)
```

### Stock Orders

| Order Type | Example |
|------------|---------|
| Market | `order_mgr.submit_market_order("AAPL", 10, side="BUY")` |
| Limit | `order_mgr.submit_limit_order("AAPL", 10, price=150.00, side="BUY")` |
| Stop | `order_mgr.submit_stop_order("AAPL", 10, stop_price=140.00, side="SELL")` |

### Detailed Order Submission

```python
order_mgr.submit_stock_order(
    symbol="AAPL",
    qty=10,
    side="BUY",
    order_type="LMT",
    price=150.00,
    tif="DAY"
)
```

### Order Management

```python
order_mgr.cancel_order("order_id")  # Cancel specific order
order_mgr.cancel_all_orders()       # Cancel all open orders
order_mgr.get_order_status("order_id")  # Check order status
```

## 6. Order Confirmation Flow

IBKR orders require explicit confirmation (unlike Alpaca's fire-and-forget).

### Automatic Handling
The `IBKROrderManager` handles confirmation automatically:
1. Submit order → receive `reply_id`
2. POST confirmation to `/iserver/reply/{reply_id}`
3. Extract and return `order_id`

### Order States
- **PreSubmitted**: Order validated but not sent
- **Submitted**: Active on exchange
- **PendingSubmit**: Waiting for market open
- **Filled**: Execution complete
- **Cancelled**: Order cancelled

## 7. Order Logging

All orders are **automatically logged** to `trades` table in `data/tradebot.db`.

### CSV Schema (Same as Alpaca)

| Column | Description |
|--------|-------------|
| `timestamp` | ISO timestamp |
| `orderID` | IBKR order ID |
| `assetType` | Stock, Option, Future |
| `tickerSymbol` | e.g., AAPL, SPY |
| `action` | buy or sell |
| `orderType` | market, limit, stop |
| `timeInForce` | DAY, GTC, IOC |
| `quantity` | Number of shares |
| `limitPrice` | Limit price (if applicable) |
| `stopPrice` | Stop price (if applicable) |
| `avgFillPrice` | Actual execution price |
| `filledQty` | Quantity filled |
| `orderValue` | Total order value |
| `status` | submitted, filled, cancelled |
| `commission` | Trading fees |

## 8. Common Workflows

### Complete Trading Workflow

```powershell
# 1. Start Gateway
cd "3. Implement/IBKR Client Portal API/clientportal.beta.gw"
bin\run.bat root\conf.yaml

# 2. Authenticate (browser)
# Navigate to https://localhost:5000 and log in

# 3. Run Python script
```

```python
from ibkr_connection import IBKRConnection
from ibkr_orders import IBKROrderManager
from ibkr_session_manager import IBKRSessionManager

# Connect and verify
conn = IBKRConnection()
if not conn.is_authenticated():
    print("Please login via browser")
    exit()

# Start session manager
session_mgr = IBKRSessionManager(conn)
session_mgr.start()

# Check account
conn.print_full_status()

# Place order
order_mgr = IBKROrderManager(conn)
order_mgr.submit_limit_order("AAPL", 10, price=150.00, side="BUY")

# Cleanup
session_mgr.stop()
```

## 9. Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Connection refused | Gateway not running | Start gateway with `bin\run.bat` |
| 401 Unauthorized | Session timeout | Re-authenticate via browser |
| Empty response `{}` | Session expired | Check auth status, re-login |
| Order rejected | Invalid params/hours | Check order parameters, market hours |

### Best Practices

1. **Always verify authentication** before trading
2. **Start session manager** for long operations
3. **Test with Alpaca paper trading first**
4. **Check market hours** before stock orders
5. **Review order history CSV** regularly

## 10. API Endpoints Reference

### Base URL
```
https://localhost:5000/v1/api
```

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/tickle` | POST | Refresh session |
| `/iserver/auth/status` | POST | Check authentication |
| `/portfolio/accounts` | GET | Get account IDs |
| `/iserver/secdef/search` | GET | Search for contracts |
| `/iserver/account/{id}/orders` | POST | Place order |
| `/iserver/reply/{replyId}` | POST | Confirm order |
| `/iserver/account/orders` | GET | Get live orders |
| `/portfolio/{id}/positions/0` | GET | Get positions |

## 11. File Reference

| File | Purpose |
|------|---------|
| `ibkr_connection.py` | Gateway connection & portfolio status |
| `ibkr_orders.py` | Order submission & management |
| `ibkr_session_manager.py` | Background session keepalive |
| `data/tradebot.db` → `trades` | Unified order archive |
| `clientportal.beta.gw/` | IBKR Gateway installation |

## 12. Security Considerations

- **Never commit credentials** to version control
- Store credentials in environment variables only
- Gateway uses self-signed SSL (verification disabled locally)
- Two-factor authentication required for login

## Summary Checklist

When trading via IBKR:

- [ ] Start the Client Portal Gateway
- [ ] Authenticate via browser at `https://localhost:5000`
- [ ] Complete two-factor authentication
- [ ] Start session manager for long operations
- [ ] Verify authentication before placing orders
- [ ] **Test order via Alpaca paper trading first**
- [ ] Check market hours for order execution
- [ ] Review order status after submission
- [ ] Check `trades` table for audit trail

## Additional Resources

- [IBKR Client Portal API Documentation](https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/)
- [IBKR Campus API Guide](https://www.interactivebrokers.com/campus/ibkr-api-page/)
- Archived reference: `_archive/IBKR Client Portal API/SKILL.md`