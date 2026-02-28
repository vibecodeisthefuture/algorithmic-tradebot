"""
Crypto Liquidation Agent

Coordinates the Hyperliquid WebSocket streams, Liquidation Monitor, Whale Watcher,
and Data Logger.  Optionally integrates CoinGlass for dedicated liquidation data.

Usage:
    py -m agents.research.crypto_liquidation.agent
    py -m agents.research.crypto_liquidation.agent --coins BTC ETH SOL
"""

import argparse
import asyncio
import logging
import signal
import time

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

logger = logging.getLogger("crypto_liquidation.agent")

# ---------------------------------------------------------------------------
# Default Configuration
# ---------------------------------------------------------------------------

DEFAULT_COINS = ["BTC", "ETH"]
REST_POLL_INTERVAL = 300  # 5 minutes for funding rate / OI polling
COINGLASS_POLL_INTERVAL = 600  # 10 minutes for CoinGlass liquidation data
STATS_PRINT_INTERVAL = 60  # 1 minute between console stat summaries
PRUNE_INTERVAL = 86400  # 24 hours between aggregation / pruning runs

# Whale-sized trades on Hyperliquid that may indicate forced liquidation
# (Hyperliquid has no dedicated liquidation stream, so large trades from
# the protocol or liquidation engine addresses are used as a proxy.)
LIQUIDATION_PROXY_THRESHOLD_USD = 50_000


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class CryptoLiquidationAgent:
    """
    Orchestrates liquidation monitoring and whale tracking.

    Lifecycle:
        1. Start WebSocket streams (Hyperliquid trades).
        2. Incoming public trades → WhaleWatcher → DataLogger.
        3. Large trades above proxy threshold → LiquidationMonitor → DataLogger.
        4. Every 5 min, poll REST for funding rates + open interest.
        5. Optionally, poll CoinGlass for dedicated liquidation data.
        6. Cascade / Whale Cluster alerts → event_log DB → Manager Agent.
    """

    def __init__(self, coins: list[str]):
        self.coins = [c.upper() for c in coins]

        # Sub-components
        self.monitor = LiquidationMonitor()
        self.watcher = WhaleWatcher()
        self.data_logger = DataLogger()
        self.rest = HyperliquidREST()
        self.coinglass = CoinGlassREST()

        # WS callbacks are bound methods
        self.ws = HyperliquidWS(
            coins=self.coins,
            on_public_trade=self._handle_trade,
        )

        self._running = False

    # ------------------------------------------------------------------
    # Callbacks (invoked by HyperliquidWS)
    # ------------------------------------------------------------------

    def _handle_trade(self, raw: dict):
        """
        Process a single raw Hyperliquid trade message.

        Every trade is evaluated for whale detection.  Additionally, large
        trades above the proxy threshold are forwarded to the liquidation
        monitor as likely forced-liquidation events.
        """
        # Whale detection
        whale_trade, cluster_alert = self.watcher.ingest(raw)

        if whale_trade:
            self.data_logger.log_whale_trade(
                whale_trade, is_cluster=cluster_alert is not None
            )

        if cluster_alert:
            self.data_logger.publish_whale_cluster_alert(cluster_alert)

        # Liquidation proxy — large trades treated as potential liquidation events
        try:
            px = float(raw.get("px", 0))
            sz = float(raw.get("sz", 0))
            usd_value = px * sz
        except (ValueError, TypeError):
            return

        if usd_value >= LIQUIDATION_PROXY_THRESHOLD_USD:
            cascade_alert = self.monitor.ingest(raw)

            from agents.research.crypto_liquidation.liquidation_monitor import LiquidationEvent
            side_raw = raw.get("side", "")
            side = "Buy" if side_raw == "B" else "Sell"
            coin = raw.get("coin", "")
            event = LiquidationEvent(
                symbol=f"{coin}USDT" if coin and not coin.endswith("USDT") else coin,
                side=side,
                price=px,
                qty=sz,
                usd_value=usd_value,
                timestamp=float(raw.get("time", time.time() * 1000)) / 1000,
            )
            self.data_logger.log_liquidation(event, is_cascade=cascade_alert is not None)

            if cascade_alert:
                self.data_logger.publish_cascade_alert(cascade_alert)

    # ------------------------------------------------------------------
    # Periodic REST polling (Hyperliquid)
    # ------------------------------------------------------------------

    async def _poll_rest(self):
        """Periodically fetch funding rates & open interest via REST."""
        while self._running:
            for coin in self.coins:
                try:
                    ticker = await self.rest.get_ticker(coin)
                    funding = ticker.get("funding", "N/A")
                    oi = ticker.get("openInterest", "N/A")
                    mark_px = ticker.get("markPx", "N/A")
                    logger.info(
                        "📊 %s  Funding: %s  OI: %s  MarkPx: %s",
                        coin, funding, oi, mark_px,
                    )
                except Exception as exc:
                    logger.error("REST poll error for %s: %s", coin, exc)
            await asyncio.sleep(REST_POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Periodic CoinGlass polling (optional, requires API key)
    # ------------------------------------------------------------------

    async def _poll_coinglass(self):
        """Periodically fetch liquidation data from CoinGlass (if configured)."""
        if not self.coinglass.is_configured:
            logger.info(
                "CoinGlass API key not set — skipping liquidation polling. "
                "Set COINGLASS_API_KEY to enable."
            )
            return

        logger.info("CoinGlass API key detected — liquidation polling active.")

        while self._running:
            for coin in self.coins:
                try:
                    history = await self.coinglass.get_liquidation_history(coin)
                    if history:
                        logger.info(
                            "🔻 CoinGlass %s: %d liquidation records fetched",
                            coin, len(history),
                        )
                except CoinGlassNotConfigured:
                    return  # Key removed at runtime
                except Exception as exc:
                    logger.error("CoinGlass poll error for %s: %s", coin, exc)
            await asyncio.sleep(COINGLASS_POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Periodic stats summary
    # ------------------------------------------------------------------

    async def _print_stats(self):
        """Print a rolling stats summary to console every minute."""
        while self._running:
            await asyncio.sleep(STATS_PRINT_INTERVAL)
            for coin in self.coins:
                symbol = f"{coin}USDT"
                liq = self.monitor.get_rolling_stats(symbol, window_seconds=60)
                whale = self.watcher.get_rolling_pressure(symbol, window_seconds=300)
                logger.info(
                    "📈 %s  LIQ(1m): $%.0f (%d events, L:$%.0f S:$%.0f) | "
                    "WHALE(5m): Buy $%.0f (%d) Sell $%.0f (%d) Net $%.0f",
                    symbol,
                    liq["total_usd"], liq["count"], liq["long_usd"], liq["short_usd"],
                    whale["buy_usd"], whale["buy_count"],
                    whale["sell_usd"], whale["sell_count"],
                    whale["net_usd"],
                )

    # ------------------------------------------------------------------
    # Periodic aggregation + pruning (runs daily)
    # ------------------------------------------------------------------

    async def _run_aggregation(self):
        """Run aggregation/pruning once on startup, then every 24h."""
        # Run once on startup to catch up
        logger.info("Running startup aggregation/pruning …")
        self.data_logger.aggregate_and_prune()

        while self._running:
            await asyncio.sleep(PRUNE_INTERVAL)
            logger.info("Running scheduled aggregation/pruning …")
            self.data_logger.aggregate_and_prune()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Start all tasks and run until interrupted."""
        self._running = True
        logger.info("=" * 60)
        logger.info("  Crypto Liquidation Agent starting")
        logger.info("  Coins: %s", ", ".join(self.coins))
        logger.info("  Data source: Hyperliquid (real-time trades)")
        logger.info("  CoinGlass: %s", "active" if self.coinglass.is_configured else "inactive (no API key)")
        logger.info("  Whale threshold: $1,000,000")
        logger.info("  Liquidation proxy threshold: $%s", f"{LIQUIDATION_PROXY_THRESHOLD_USD:,}")
        logger.info("  Liquidation log threshold: $10,000")
        logger.info("  Batch flush interval: 5s")
        logger.info("  Data retention: 7 days (then aggregated)")
        logger.info("  REST poll interval: %ss", REST_POLL_INTERVAL)
        logger.info("=" * 60)

        tasks = [
            asyncio.create_task(self.ws.start(), name="ws_stream"),
            asyncio.create_task(self._poll_rest(), name="rest_poll"),
            asyncio.create_task(self._poll_coinglass(), name="coinglass_poll"),
            asyncio.create_task(self._print_stats(), name="stats"),
            asyncio.create_task(self._run_aggregation(), name="aggregation"),
        ]

        # Handle graceful shutdown
        loop = asyncio.get_running_loop()
        for sig_name in ("SIGINT", "SIGTERM"):
            try:
                loop.add_signal_handler(
                    getattr(signal, sig_name),
                    lambda: asyncio.create_task(self.shutdown(tasks)),
                )
            except (NotImplementedError, AttributeError):
                # Windows doesn't support add_signal_handler
                pass

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            # Flush any remaining buffered rows before exit
            self.data_logger.flush()
            await self.rest.close()
            await self.coinglass.close()
            logger.info("Crypto Liquidation Agent shut down.")

    async def shutdown(self, tasks):
        """Cancel all tasks and stop WS."""
        logger.info("Shutting down …")
        self._running = False
        await self.ws.stop()
        for task in tasks:
            task.cancel()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Liquidation Agent — Hyperliquid real-time monitor"
    )
    parser.add_argument(
        "--coins",
        nargs="+",
        default=DEFAULT_COINS,
        help="Coins to monitor (default: BTC ETH)",
    )
    args = parser.parse_args()

    agent = CryptoLiquidationAgent(coins=args.coins)

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")


if __name__ == "__main__":
    main()
