# Cryptocurrency Data Collection Guide

A comprehensive guide for collecting high-quality historical cryptocurrency data for algorithmic trading backtests using public APIs.

---

## Overview

Cryptocurrency data collection requires different approaches than traditional stock data due to:
- **24/7 markets** - No market hours, continuous trading
- **Multiple exchanges** - Price variations across platforms
- **High volatility** - Rapid price movements requiring granular data
- **Newer asset class** - Limited historical data for some coins
- **Decentralized nature** - Multiple data sources with varying reliability

This guide covers **verified public APIs** that provide free access to crypto market data without requiring API keys or payment.

---

## Verified Public Data Sources

### ✅ Coinbase Exchange API

**Status:** ✓ Verified Working  
**Authentication:** None required  
**Best For:** Historical OHLCV candlestick data

#### Key Features
- **Direct exchange data** from one of the largest US crypto exchanges
- **Long history** - BTC/ETH data back to 2016
- **Multiple granularities**: 1m, 5m, 15m, 1h, 6h, 1d
- **Clean data** - Validated OHLCV with volume
- **No API key needed** for public endpoints

#### Rate Limits
- **300 candles per request** (manageable with pagination)
- **No strict rate limit** on public endpoints
- **Recommended delay**: 0.3s between requests

#### Available Cryptocurrencies
Major pairs with USD: BTC, ETH, SOL, ADA, XRP, DOGE, AVAX, MATIC, DOT, UNI, LINK, and more

#### API Endpoint
```
GET https://api.exchange.coinbase.com/products/{product_id}/candles
```

**Parameters:**
- `start`: ISO 8601 timestamp (e.g., "2024-01-01T00:00:00")
- `end`: ISO 8601 timestamp
- `granularity`: Seconds (21600 for 6-hour, 3600 for 1-hour, etc.)

**Response Format:**
```json
[
  [time, low, high, open, close, volume],
  [1706832000, 41000.50, 41500.75, 41200.00, 41450.25, 125.5],
  ...
]
```

#### Implementation
See [`coinbase_collector.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/coinbase_collector.py) for a full working implementation.

**Example collection results:**
- BTC: ~14,000 rows (9.6 years of 6h data)
- ETH: ~14,000 rows (9.6 years of 6h data)
- SOL: ~6,700 rows (4.6 years since listing)

---

### ✅ Hyperliquid API

**Status:** ✓ Verified Working  
**Authentication:** None required  
**Best For:** Decentralized perps exchange data, recent market data

#### Key Features
- **Decentralized exchange** data (on-chain perpetuals)
- **Real-time data** with minimal latency
- **228+ trading pairs** available
- **Free and unlimited** public API access
- **Modern infrastructure** - Fast and reliable

#### Rate Limits
- **No official rate limits** published
- **Recommended delay**: 0.2-0.5s between requests
- **Very generous** usage allowance

#### Available Cryptocurrencies
- All major cryptocurrencies: BTC, ETH, SOL, etc.
- Many altcoins and smaller cap tokens
- Perpetual contract markets

#### API Endpoint
```
POST https://api.hyperliquid.xyz/info
```

**Get Available Markets:**
```json
{
  "type": "meta"
}
```

**Get Candle Data:**
```json
{
  "type": "candleSnapshot",
  "req": {
    "coin": "BTC",
    "interval": "1h",
    "startTime": 1706832000000,
    "endTime": 1769925600000
  }
}
```

**Response Format:**
```json
[
  {
    "t": 1769317200000,  // timestamp (ms)
    "T": 1769320799999,  // close timestamp
    "s": "BTC",          // symbol
    "i": "1h",           // interval
    "o": "88974.0",      // open
    "h": "89010.0",      // high
    "l": "88824.0",      // low
    "c": "88958.0",      // close
    "v": "186.43192",    // volume
    "n": 4521            // num trades
  }
]
```

#### Implementation
See [`test_hyperliquid.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/test_hyperliquid.py) for working example.

---

### ✅ CoinGecko API

**Status:** ✓ Verified Working  
**Authentication:** None required for free tier  
**Best For:** Price data, market metrics, broad coverage

#### Key Features
- **14,000+ cryptocurrencies** tracked
- **Free tier**: 10,000 API calls per month
- **Market data**: Price, volume, market cap, supply
- **Historical data**: Daily granularity available
- **Reliable** - Industry-standard price aggregator

#### Rate Limits
- **~30 calls per minute** on free tier
- **10,000 calls per month** total
- **Paid plans** available for higher limits (500-1,000 calls/min)

#### Available Data
- Current prices (multiple currencies)
- 24h statistics (volume, change, high/low)
- Historical market charts
- Market cap rankings
- Trading volume by exchange

#### API Endpoints

**Ping (connectivity test):**
```
GET https://api.coingecko.com/api/v3/ping
```

**Current Price:**
```
GET https://api.coingecko.com/api/v3/simple/price
?ids=bitcoin,ethereum
&vs_currencies=usd
&include_market_cap=true
&include_24hr_vol=true
```

**Historical Chart Data:**
```
GET https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart
?vs_currency=usd
&days=90
&interval=daily
```

**Response Format (price):**
```json
{
  "bitcoin": {
    "usd": 78735.0,
    "usd_market_cap": 1572561894857,
    "usd_24h_vol": 83176988190,
    "usd_24h_change": -6.12
  }
}
```

**Response Format (chart):**
```json
{
  "prices": [
    [1706832000000, 41250.50],
    [1706918400000, 41680.25],
    ...
  ],
  "market_caps": [...],
  "total_volumes": [...]
}
```

#### Implementation
See [`test_coingecko.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/test_coingecko.py) for working example.

#### Best Practices
- **Daily data only** for long-term historical analysis
- **Monitor rate limits** - watch for 429 errors
- **Use coin_id not ticker** (e.g., "bitcoin" not "BTC")
- **Cache responses** when possible to preserve API calls

---

## Other Public APIs (Not Tested)

### Kraken API
- **Public endpoints** available
- **Rate limits**: Varies by tier
- **Good for**: Historical OHLC data
- **URL**: https://api.kraken.com

### CryptoCompare
- **Free tier** available with API key
- **Good for**: Aggregated price data
- **Requires**: API key registration
- **URL**: https://min-api.cryptocompare.com

---

## Data Collection Best Practices

### 1. Choose the Right API for Your Needs

| Use Case | Recommended API | Why |
|----------|----------------|-----|
| **Backtesting (OHLCV)** | Coinbase Exchange | Clean candle data, long history |
| **Recent data (<1 year)** | Hyperliquid | Fast, unlimited, modern |
| **Price monitoring** | CoinGecko | Broad coverage, simple API |
| **Multiple exchanges** | CoinGecko | Aggregated data from all exchanges |
| **Specific exchange** | Coinbase/Hyperliquid | Direct exchange data |

### 2. Data Quality Considerations

**Survivorship Bias:**
- ⚠ Crypto data naturally survives (delisted coins often still tradeable)
- ✅ Focus on established coins for reliable backtests

**Data Gaps:**
- Check for missing timestamps in 24/7 markets
- Newer coins have limited historical data
- Some exchanges list coins later than others

**Price Variations:**
- Different exchanges = different prices
- Use single exchange (Coinbase) for consistency
- Or use aggregated data (CoinGecko) for market average

### 3. Granularity Selection

| Interval | Use Case | Data Size | Recommended API |
|----------|----------|-----------|----------------|
| **1 minute** | High-frequency trading, scalping | Very large | Hyperliquid |
| **5-15 min** | Day trading strategies | Large | Hyperliquid |
| **1 hour** | Swing trading | Moderate | Coinbase |
| **6 hour** | Position trading | Small | Coinbase |
| **1 day** | Long-term strategies, analysis | Very small | CoinGecko/Coinbase |

### 4. Historical Data Limits

**By Cryptocurrency:**
- **BTC**: Data back to 2016-2017 on major exchanges
- **ETH**: Data back to 2016-2017
- **Altcoins**: Typically 2019-2022 onwards
- **Newer coins**: Limited to listing date

**By API:**
- **Coinbase**: ~9.6 years for BTC/ETH (2016-)
- **Hyperliquid**: Since launch (~2023-)
- **CoinGecko**: Varies by coin, daily data available

### 5. Rate Limiting Strategy

**Implement Delays:**
```python
import time

for symbol in symbols:
    fetch_data(symbol)
    time.sleep(0.3)  # 300ms delay
```

**Pagination for Large Requests:**
```python
# Coinbase: 300 candles per request
chunks = total_candles // 300
for chunk in range(chunks):
    start_time = calculate_chunk_start()
    end_time = calculate_chunk_end()
    data = fetch_candles(start_time, end_time)
    time.sleep(0.3)
```

**Retry Logic:**
```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retries = Retry(total=3, backoff_factor=1)
session.mount('https://', HTTPAdapter(max_retries=retries))
```

### 6. Data Validation

**Check OHLC Relationships:**
```python
# High should be >= all other prices
assert (df['high'] >= df['low']).all()
assert (df['high'] >= df['open']).all()
assert (df['high'] >= df['close']).all()

# Low should be <= all other prices
assert (df['low'] <= df['open']).all()
assert (df['low'] <= df['close']).all()
```

**Check for Gaps:**
```python
# For 6-hour data
expected_interval = pd.Timedelta(hours=6)
actual_intervals = df['timestamp'].diff()
gaps = actual_intervals[actual_intervals > expected_interval * 1.5]

if len(gaps) > 0:
    print(f"Found {len(gaps)} data gaps")
```

**Validate Prices:**
```python
# Remove invalid prices
df = df[(df['close'] > 0) & (df['volume'] >= 0)]

# Check for extreme outliers (optional)
# Use z-score or IQR method
```

---

## Implementation Examples

### Coinbase Collection Script

Our implementation collected **55,200 rows** across 6 cryptocurrencies:

```python
from coinbase_collector import CoinbaseCollector

collector = CoinbaseCollector()

# Collect 500 weeks of 6-hour data
data = collector.collect_historical_data(
    product_id='BTC-USD',
    weeks=500,
    granularity='6h'
)

# Validate and save
validation = collector.validate_data(data)
collector.save_data(data, 'BTC-6h-500wks-data.csv')
```

**Results:**
- BTC: 13,999 candles (2016-2026)
- ETH: 14,000 candles (2016-2026)
- Total: 55,200 validated rows
- File size: ~4 MB total

Full implementation: [`coinbase_collector.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/coinbase_collector.py)

### Hyperliquid Example

```python
import requests

url = "https://api.hyperliquid.xyz/info"

# Get candle data
payload = {
    "type": "candleSnapshot",
    "req": {
        "coin": "BTC",
        "interval": "1h",
        "startTime": 1706832000000,  # milliseconds
        "endTime": 1769925600000
    }
}

response = requests.post(url, json=payload)
candles = response.json()

# Process candles
for candle in candles:
    timestamp = candle['t']
    open_price = float(candle['o'])
    high = float(candle['h'])
    low = float(candle['l'])
    close = float(candle['c'])
    volume = float(candle['v'])
```

Full test: [`test_hyperliquid.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/test_hyperliquid.py)

### CoinGecko Example

```python
import requests

# Get current price
url = "https://api.coingecko.com/api/v3/simple/price"
params = {
    "ids": "bitcoin,ethereum,solana",
    "vs_currencies": "usd",
    "include_24hr_vol": "true"
}

response = requests.get(url, params=params)
prices = response.json()

print(f"BTC: ${prices['bitcoin']['usd']:,.2f}")
print(f"ETH: ${prices['ethereum']['usd']:,.2f}")
```

Full test: [`test_coingecko.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/test_coingecko.py)

---

## Comparison Matrix

| Feature | Coinbase Exchange | Hyperliquid | CoinGecko |
|---------|------------------|-------------|-----------|
| **Authentication** | None | None | None (free tier) |
| **Rate Limits** | 300 candles/req | Unlimited | 30/min, 10k/month |
| **Historical Data** | 9+ years | Since 2023 | Varies by coin |
| **Granularity** | 1m - 1d | 1m - 1d | Daily only (free) |
| **Data Type** | OHLCV candles | OHLCV candles | Price, market data |
| **Cryptocurrencies** | 100+ pairs | 228+ pairs | 14,000+ coins |
| **Best For** | Backtesting | Recent data | Price monitoring |
| **Reliability** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Data Quality** | Excellent | Excellent | Good |
| **Setup Complexity** | Low | Low | Very Low |

---

## Common Issues and Solutions

### Issue: "No data returned"
**Solution:** 
- Check if coin exists on that exchange
- Verify date range (coin may not have been listed yet)
- Check symbol format (BTC-USD vs BTCUSD vs bitcoin)

### Issue: "Rate limit exceeded"
**Solution:**
- Add delays between requests (0.3-1.0 seconds)
- Reduce batch size
- Implement exponential backoff
- Consider paid tier for higher limits

### Issue: "Data gaps in results"
**Solution:**
- Check for exchange maintenance periods
- Verify timestamp calculations
- Some coins have natural gaps during low liquidity
- Use fill methods (forward fill) with caution

### Issue: "Different prices across APIs"
**Solution:**
- This is normal - each exchange has different prices
- Use single exchange data for consistency
- Or explain variance in your analysis
- CoinGecko provides aggregated "average" prices

---

## Next Steps

1. **Test API Access**: Run the test scripts in [`crypto/`](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto)
2. **Choose Your API**: Based on your needs (see comparison matrix)
3. **Implement Collector**: Use or adapt the [`coinbase_collector.py`](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/coinbase_collector.py)
4. **Validate Data**: Always validate OHLCV relationships and check for gaps
5. **Start Backtesting**: Load data into your backtesting framework

---

## Additional Resources

**Test Scripts:**
- [test_hyperliquid.py](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/test_hyperliquid.py) - Hyperliquid API verification
- [test_coingecko.py](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/test_coingecko.py) - CoinGecko API verification

**Implementation:**
- [coinbase_collector.py](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/coinbase_collector.py) - Full Coinbase collector class
- [collect_crypto_coinbase.py](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/collect_crypto_coinbase.py) - Collection script for 6 cryptos
- [verify_crypto_data.py](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/Backtest/datasets/crypto/verify_crypto_data.py) - Data validation script

**Documentation:**
- [Hyperliquid API Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/)
- [CoinGecko API Docs](https://www.coingecko.com/api/documentation)
- [Coinbase Exchange API Docs](https://docs.cloud.coinbase.com/exchange/reference)

---

## Summary

For **backtesting** algorithmic trading strategies with crypto:
- ✅ **Use Coinbase Exchange API** for reliable historical OHLCV data
- ✅ **Use Hyperliquid** for recent data and broader coverage
- ✅ **Use CoinGecko** for price monitoring and market metrics

All three verified APIs are **free, require no authentication**, and provide high-quality data suitable for professional backtesting.
