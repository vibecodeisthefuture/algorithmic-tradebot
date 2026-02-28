# Crypto Liquidation Agent — SKILL

## Purpose

Real-time monitor for **crypto liquidation events** and **whale trades** using
the Hyperliquid API (primary) and CoinGlass API (supplemental).  Provides
cascade detection, whale cluster alerts, and market health metrics (funding
rates, open interest) to the Manager Agent.

## Data Streams

| Data Type | Source | Method | Interval |
|-----------|--------|--------|----------|
| Public Trades | Hyperliquid `trades.{coin}` | WebSocket | Real-time |
| Liquidation Proxy | Hyperliquid trades ≥ $50K | WebSocket (inferred) | Real-time |
| Open Interest | Hyperliquid `metaAndAssetCtxs` | REST | 5 min |
| Funding Rate | Hyperliquid `fundingHistory` | REST | 5 min |
| Ticker / Mark Price | Hyperliquid `metaAndAssetCtxs` | REST | 5 min |
| Liquidation History | CoinGlass `/futures/liquidation/v2/history` | REST (paid) | 10 min |

## Core Capabilities

### 1. Liquidation Cascade Detection
- Infers liquidation events from large Hyperliquid trades (≥ $50K).
- Rolling window aggregation of liquidation-proxy events.
- **Alert** when cumulative USD volume exceeds $50M within 5 minutes.
- Publishes `LIQUIDATION_CASCADE` → `event_log` table → Manager Agent.
- **CoinGlass upgrade**: When API key is set, uses dedicated cross-exchange liquidation data for higher accuracy.

### 2. Whale Trade Detection
- Filters trades with notional value ≥ **$1,000,000 USD**.
- **Cluster Alert** when ≥ 3 whale trades appear within 2 minutes.
- Classifies buy vs sell pressure with rolling summaries.

### 3. Market Health Polling
- Funding rate monitoring (extreme rates signal overleverage).
- Open interest tracking (position build-up / unwind).

## Data Sources

### Hyperliquid (Primary — Free, US-Accessible)
- **WebSocket**: `wss://api.hyperliquid.xyz/ws`
  - Subscribe: `{type: "trades", coin: "<COIN>"}`
  - Trade format: `{coin, side("B"/"A"), px, sz, time, tid, hash, users}`
- **REST**: POST `https://api.hyperliquid.xyz/info`
  - `{type: "metaAndAssetCtxs"}` → OI, funding, mark price
  - `{type: "fundingHistory", coin, startTime}` → funding rate records
- **No API key required** for public data
- **Documentation**: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api

### CoinGlass (Supplemental — Paid, $29/month Hobbyist)
- **REST**: `https://open-api-v3.coinglass.com/api`
  - `/futures/liquidation/v2/history` → historical liquidation data
  - `/futures/liquidation/heatmap` → liquidation price levels
  - `/futures/liquidation/order` → recent liquidation orders (7 days)
- **Requires**: `COINGLASS_API_KEY` environment variable
- **Status**: Framework ready, activates when API key is set
- **Documentation**: https://coinglass.com/pricing

## Data Storage

All data persisted to `data/tradebot.db`:

| Table | Contents | Retention |
|-------|----------|-----------|
| `crypto_liquidations` | Events ≥ $10K (smaller events processed in-memory only) | **7 days** (then aggregated) |
| `whale_trades` | Whale trades ≥ $1M | **7 days** (then aggregated) |
| `crypto_liquidation_summary` | Hourly aggregated stats | **Permanent** |
| `event_log` | Cascade + cluster alerts → Manager | Per system policy |

### Storage Optimizations
- **$10K threshold**: only significant liquidations are persisted; small events are still processed in-memory for cascade detection.
- **Batch inserts**: rows buffered in memory and flushed every 5 seconds.
- **Hourly aggregation**: before pruning, raw data is rolled up into `crypto_liquidation_summary` (one row per symbol per hour).
- **7-day retention**: raw rows older than 7 days are deleted daily after aggregation.

## Integration

The agent communicates via two channels:

1. **SQLite Blackboard** (source of truth) — all events are persisted to the `event_log` table
2. **ZeroMQ Event Bus** (real-time notifications) — critical alerts are also pushed to the ZeroMQ proxy so the Manager Orchestrator wakes up instantly

```yaml
receive_from: [market_news_agent]
push_to: [manager_agent, strategy_research_agent]
alert_channel:
  db: event_log table (LIQUIDATION_CASCADE, WHALE_CLUSTER)
  zmq: LIQUIDATION.CASCADE, WHALE.CLUSTER topics
```

**ZeroMQ topics published**:

| Topic | Trigger | Payload |
|-------|---------|--------|
| `LIQUIDATION.CASCADE` | Cascade alert detected | `{symbol, side, total_usd, event_count, window_seconds}` |
| `WHALE.CLUSTER` | Whale cluster alert | `{symbol, dominant_side, total_usd, trade_count, window_seconds}` |

> If the ZeroMQ proxy is not running, the agent continues operating normally — DB writes are primary, ZeroMQ is best-effort.

## Running

```bash
# Default coins (BTC, ETH)
py -m agents.research.crypto_liquidation.agent

# Custom coins
py -m agents.research.crypto_liquidation.agent --coins BTC ETH SOL
```

## Dependencies

- `aiohttp` — async HTTP / WebSocket client
- `pyzmq` — ZeroMQ bindings for real-time event publishing (optional, graceful fallback)
- `agents.common` — shared database, models, enums, event bus

## Configuration

Hyperliquid config lives in `config/system_config.yaml` under `brokers.crypto_data`.
CoinGlass API key (optional) goes in `config/.env`:

```
COINGLASS_API_KEY=your_key_here
```
