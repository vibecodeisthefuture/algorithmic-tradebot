"""
Hyperliquid API Integration Tests

Tests all crypto liquidation agent components against the live Hyperliquid API.
Uses only public endpoints — no API keys required.
CoinGlass tests are skipped unless COINGLASS_API_KEY is set.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))

from agents.research.crypto_liquidation.hyperliquid_client import (
    HyperliquidWS,
    HyperliquidREST,
)
from agents.research.crypto_liquidation.coinglass_client import (
    CoinGlassREST,
    CoinGlassNotConfigured,
)
from agents.research.crypto_liquidation.liquidation_monitor import LiquidationMonitor
from agents.research.crypto_liquidation.whale_watcher import WhaleWatcher
from agents.research.crypto_liquidation.data_logger import DataLogger
from agents.common.database import init_db

PASS = 0
FAIL = 0
SKIP = 0


def report(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f" -- {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f" -- {detail}" if detail else ""))


def skip(name, reason=""):
    global SKIP
    SKIP += 1
    print(f"  SKIP  {name}" + (f" -- {reason}" if reason else ""))


# =========================================================================
# Test 1: HyperliquidREST.get_ticker
# =========================================================================
async def test_rest_ticker():
    client = HyperliquidREST()
    try:
        ticker = await client.get_ticker("BTC")
        ok = isinstance(ticker, dict) and len(ticker) > 0
        detail = ""
        if ok:
            detail = "coin=%s, markPx=%s, OI=%s" % (
                ticker.get("coin"), ticker.get("markPx"), ticker.get("openInterest")
            )
        report("REST get_ticker(BTC)", ok, detail)
    except Exception as e:
        report("REST get_ticker(BTC)", False, str(e))
    finally:
        await client.close()


# =========================================================================
# Test 2: HyperliquidREST.get_funding_history
# =========================================================================
async def test_rest_funding():
    client = HyperliquidREST()
    try:
        funding = await client.get_funding_history("BTC", limit=5)
        ok = isinstance(funding, list) and len(funding) > 0
        detail = ""
        if ok:
            detail = "entries=%d, latest_rate=%s" % (
                len(funding), funding[-1].get("fundingRate", "N/A")
            )
        report("REST get_funding_history(BTC)", ok, detail)
    except Exception as e:
        report("REST get_funding_history(BTC)", False, str(e))
    finally:
        await client.close()


# =========================================================================
# Test 3: HyperliquidREST.get_open_interest
# =========================================================================
async def test_rest_open_interest():
    client = HyperliquidREST()
    try:
        oi = await client.get_open_interest("BTC")
        ok = isinstance(oi, str) and len(oi) > 0
        report("REST get_open_interest(BTC)", ok, "OI=%s" % oi)
    except Exception as e:
        report("REST get_open_interest(BTC)", False, str(e))
    finally:
        await client.close()


# =========================================================================
# Test 4: HyperliquidREST.get_recent_trades
# =========================================================================
async def test_rest_recent_trades():
    client = HyperliquidREST()
    try:
        trades = await client.get_recent_trades("BTC")
        ok = isinstance(trades, list) and len(trades) > 0
        detail = ""
        if ok:
            detail = "count=%d, first_trade=%s %s @ %s" % (
                len(trades), trades[0].get("coin"), trades[0].get("side"),
                trades[0].get("px")
            )
        report("REST get_recent_trades(BTC)", ok, detail)
    except Exception as e:
        report("REST get_recent_trades(BTC)", False, str(e))
    finally:
        await client.close()


# =========================================================================
# Test 5: LiquidationMonitor.ingest — synthetic event (Hyperliquid format)
# =========================================================================
def test_liquidation_monitor():
    monitor = LiquidationMonitor()
    now_ms = int(time.time() * 1000)

    # Feed a synthetic trade in Hyperliquid format
    raw_event = {
        "coin": "BTC",
        "side": "A",  # "A" = sell/ask
        "px": "50000.0",
        "sz": "1.5",
        "time": now_ms,
    }
    result = monitor.ingest(raw_event)
    report(
        "LiquidationMonitor.ingest (single event)",
        result is None,
        "no cascade (expected)"
    )

    # Check rolling stats (symbol stored as BTCUSDT)
    stats = monitor.get_rolling_stats("BTCUSDT")
    ok = stats["count"] == 1 and stats["total_usd"] > 0
    report(
        "LiquidationMonitor.get_rolling_stats",
        ok,
        "count=%d, total_usd=$%.0f" % (stats["count"], stats["total_usd"])
    )

    # Check heatmap
    heatmap = monitor.get_heatmap_data("BTCUSDT")
    ok2 = isinstance(heatmap, dict) and len(heatmap) > 0
    report(
        "LiquidationMonitor.get_heatmap_data",
        ok2,
        "buckets=%d" % len(heatmap)
    )


# =========================================================================
# Test 6: WhaleWatcher.ingest — synthetic trades (Hyperliquid format)
# =========================================================================
def test_whale_watcher():
    watcher = WhaleWatcher(threshold_usd=100_000)
    now_ms = int(time.time() * 1000)

    # Feed a trade above threshold ($250,000)
    big_trade = {
        "coin": "BTC",
        "side": "B",  # "B" = buy
        "px": "50000.0",
        "sz": "5.0",
        "time": now_ms,
    }
    whale, cluster = watcher.ingest(big_trade)
    ok = whale is not None and whale.usd_value == 250_000
    report(
        "WhaleWatcher.ingest (above threshold)",
        ok,
        "usd_value=$%.0f, symbol=%s" % (whale.usd_value if whale else 0, whale.symbol if whale else "")
    )

    # Verify symbol normalization
    if whale:
        ok_sym = whale.symbol == "BTCUSDT"
        report("WhaleWatcher symbol normalization", ok_sym, "coin=BTC → symbol=BTCUSDT")

    # Feed a trade below threshold ($3,000)
    small_trade = {
        "coin": "ETH",
        "side": "A",
        "px": "3000.0",
        "sz": "1.0",
        "time": now_ms,
    }
    whale2, cluster2 = watcher.ingest(small_trade)
    ok2 = whale2 is None
    report("WhaleWatcher.ingest (below threshold)", ok2, "correctly filtered")

    # Check rolling pressure
    pressure = watcher.get_rolling_pressure("BTCUSDT")
    ok3 = pressure["buy_count"] == 1 and pressure["buy_usd"] == 250_000
    report(
        "WhaleWatcher.get_rolling_pressure",
        ok3,
        "buy=$%.0f, sell=$%.0f" % (pressure["buy_usd"], pressure["sell_usd"])
    )


# =========================================================================
# Test 7: DataLogger — DB integration (synthetic data)
# =========================================================================
def test_data_logger():
    from agents.research.crypto_liquidation.liquidation_monitor import LiquidationEvent
    from agents.research.crypto_liquidation.whale_watcher import WhaleTrade

    init_db()
    dl = DataLogger()
    now = time.time()

    # Test logging a liquidation event above $10K threshold
    liq_event = LiquidationEvent(
        symbol="BTCUSDT",
        side="Sell",
        price=50000.0,
        qty=0.5,
        usd_value=25000.0,
        timestamp=now,
    )
    try:
        dl.log_liquidation(liq_event)
        report("DataLogger.log_liquidation (above threshold)", True, "usd_value=$25,000")
    except Exception as e:
        report("DataLogger.log_liquidation (above threshold)", False, str(e))

    # Test that small events are filtered (below $10K)
    small_event = LiquidationEvent(
        symbol="ETHUSDT",
        side="Buy",
        price=3000.0,
        qty=1.0,
        usd_value=3000.0,
        timestamp=now,
    )
    try:
        before_len = len(dl._liq_buffer)
        dl.log_liquidation(small_event)
        after_len = len(dl._liq_buffer)
        ok = after_len == before_len
        report("DataLogger.log_liquidation (below threshold)", ok, "filtered correctly")
    except Exception as e:
        report("DataLogger.log_liquidation (below threshold)", False, str(e))

    # Test whale trade logging
    whale = WhaleTrade(
        symbol="BTCUSDT",
        side="Buy",
        price=50000.0,
        qty=5.0,
        usd_value=250000.0,
        timestamp=now,
    )
    try:
        dl.log_whale_trade(whale)
        report("DataLogger.log_whale_trade", True, "usd_value=$250,000")
    except Exception as e:
        report("DataLogger.log_whale_trade", False, str(e))

    # Flush buffers to DB
    try:
        dl.flush()
        report("DataLogger.flush()", True)
    except Exception as e:
        report("DataLogger.flush()", False, str(e))


# =========================================================================
# Test 8: CoinGlass framework (no API key expected)
# =========================================================================
async def test_coinglass():
    client = CoinGlassREST()
    if client.is_configured:
        try:
            history = await client.get_liquidation_history("BTC")
            ok = isinstance(history, list)
            report("CoinGlass get_liquidation_history(BTC)", ok, "records=%d" % len(history))
        except Exception as e:
            report("CoinGlass get_liquidation_history(BTC)", False, str(e))
        finally:
            await client.close()
    else:
        # Verify it raises correctly when no key
        try:
            await client.get_liquidation_history("BTC")
            report("CoinGlass guard (no key)", False, "should have raised")
        except CoinGlassNotConfigured:
            report("CoinGlass guard (no key)", True, "CoinGlassNotConfigured raised")
        except Exception as e:
            report("CoinGlass guard (no key)", False, str(e))


# =========================================================================
# Test 9: HyperliquidWS — connection test (live, 15 second window)
# =========================================================================
async def test_websocket():
    messages = []

    def on_trade(msg):
        messages.append(msg)

    ws = HyperliquidWS(
        coins=["BTC"],
        on_public_trade=on_trade,
    )

    try:
        task = asyncio.create_task(ws.start())

        deadline = time.time() + 15
        while time.time() < deadline:
            await asyncio.sleep(0.5)
            if len(messages) > 0:
                break

        report(
            "WebSocket BTC trades (15s)",
            len(messages) > 0,
            "trades_received=%d" % len(messages)
        )

        # Check trade format
        if messages:
            t = messages[0]
            has_fields = all(k in t for k in ("coin", "side", "px", "sz", "time"))
            report(
                "WebSocket trade format",
                has_fields,
                "fields=%s" % list(t.keys())
            )
    except Exception as e:
        report("WebSocket BTC", False, str(e))
    finally:
        await ws.stop()


# =========================================================================
# Main
# =========================================================================
async def main():
    print("=" * 60)
    print(" Hyperliquid API Integration Tests")
    print("=" * 60)

    # REST tests (live network)
    print("\n--- REST API Tests (Live, Hyperliquid) ---")
    await test_rest_ticker()
    await test_rest_funding()
    await test_rest_open_interest()
    await test_rest_recent_trades()

    # Unit tests (no network)
    print("\n--- Component Unit Tests (Offline) ---")
    test_liquidation_monitor()
    test_whale_watcher()
    test_data_logger()

    # CoinGlass framework test
    print("\n--- CoinGlass Framework Test ---")
    await test_coinglass()

    # WebSocket test (live network)
    print("\n--- WebSocket Live Test ---")
    await test_websocket()

    # Summary
    print("\n" + "=" * 60)
    print(" Results: %d passed, %d failed, %d skipped (total %d)" % (
        PASS, FAIL, SKIP, PASS + FAIL + SKIP
    ))
    print("=" * 60)

    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
