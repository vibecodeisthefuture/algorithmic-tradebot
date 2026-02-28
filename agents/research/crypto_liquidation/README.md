# Crypto Liquidation Agent

## Status: Active Development

Real-time crypto liquidation monitoring and whale tracking agent powered by the **Hyperliquid API** (primary) and **CoinGlass API** (supplemental liquidation data).

## Architecture

```yaml
crypto_liquidation_agent:
  purpose: Monitor crypto liquidations and whale movements for trading signals

  workflows:
    - liquidation_monitoring: Real-time cascade detection via trade inference
    - whale_tracking: Large trade detection (≥ $1,000,000 threshold)
    - funding_rate_monitoring: Overleverage signal detection
    - open_interest_tracking: Position build-up / unwind analysis

  integrations:
    receive_from: [market_news_agent]
    push_to: [manager_agent, strategy_research_agent]
    alert_channel: event_log table + ZeroMQ (LIQUIDATION.CASCADE, WHALE.CLUSTER)

  data_sources:
    primary: Hyperliquid API (WebSocket + REST, free, US-accessible)
    supplemental: CoinGlass API (REST, paid, dedicated liquidation data)
    ws_topics:
      - trades.{coin}            # Real-time public trades (whale + liq detection)
    rest_endpoints:
      - POST /info {type: metaAndAssetCtxs}    # OI, funding, prices
      - POST /info {type: fundingHistory}       # Funding rate history
      - GET /futures/liquidation/v2/history      # CoinGlass (paid)

  data_storage:
    database: data/tradebot.db
    tables:
      - crypto_liquidations   # Liquidation-proxy events (≥ $10K)
      - whale_trades           # Every whale trade (≥ $1M)
      - event_log              # Cascade + cluster alerts → Manager
```

## Query Intervals

```yaml
query_cycles:
  public_trade_stream: real-time  # Hyperliquid WS
  funding_rates_rest: 5min        # REST polling
  open_interest_rest: 5min        # REST polling
  coinglass_liqs: 10min           # CoinGlass polling (if API key set)
  console_stats: 1min             # Rolling summary to console
```

## Source Files

| File | Purpose |
|------|---------|
| `hyperliquid_client.py` | Async WS + REST client (exponential backoff) |
| `coinglass_client.py` | CoinGlass REST framework (liquidation endpoints, requires API key) |
| `liquidation_monitor.py` | Cascade detection ($50M / 5min), heatmap data |
| `whale_watcher.py` | Whale trade filtering ($1M threshold), cluster detection |
| `data_logger.py` | Database persistence (crypto_liquidations, whale_trades, event_log) |
| `agent.py` | Main coordinator (entry point) |
| `SKILL.md` | Agent capability documentation |

## Running

```bash
# Default (BTC, ETH)
py -m agents.research.crypto_liquidation.agent

# Custom coins
py -m agents.research.crypto_liquidation.agent --coins BTC ETH SOL
```

## Risk Integration

Must align with Portfolio Tracker risk policies:
- HIGH: 3x max leverage, 22% circuit breaker
- MODERATE: 2x max leverage, 18% circuit breaker
- LOW: 1.2x max leverage, 12% circuit breaker

---

*See [SKILL.md](./SKILL.md) for detailed capability docs.*
*See [CRYPTO_INVESTING_GUIDE.md](../strategy/CRYPTO_INVESTING_GUIDE.md) for strategy research methods.*
