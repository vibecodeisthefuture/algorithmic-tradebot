"""
Whale Watcher

Filters real-time public trades from the Hyperliquid WebSocket stream for
"whale" activity — single trades with notional value ≥ $1,000,000 USD.

Provides:
    1. Whale trade alerts
    2. Rolling whale stats (buy vs sell pressure)
    3. Cluster detection (multiple whales in short window)
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("crypto_liquidation.whale_watcher")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class WhaleTrade:
    """A single trade that exceeds the whale threshold (from Hyperliquid)."""

    symbol: str
    side: str          # "Buy" or "Sell"
    price: float
    qty: float
    usd_value: float
    timestamp: float   # epoch seconds


@dataclass
class WhaleClusterAlert:
    """
    Emitted when multiple whale trades appear within a short window,
    indicating coordinated activity.
    """

    symbol: str
    dominant_side: str
    total_usd: float
    trade_count: int
    window_seconds: float
    start_ts: float
    end_ts: float


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------


WHALE_THRESHOLD_USD = 1_000_000  # $1M minimum for whale classification


class WhaleWatcher:
    """
    Processes incoming public trade events and identifies whales.

    Parameters
    ----------
    threshold_usd : float
        Minimum notional value for a trade to qualify as a "whale" trade.
        Default: $1,000,000.
    cluster_count : int
        Number of whale trades within ``cluster_window_seconds`` required
        to trigger a WhaleClusterAlert.  Default: 3.
    cluster_window_seconds : float
        Rolling window for cluster detection.  Default: 120 (2 minutes).
    history_window_seconds : float
        How long to retain whale trades in the buffer.  Default: 3600 (1 hour).
    """

    def __init__(
        self,
        threshold_usd: float = WHALE_THRESHOLD_USD,
        cluster_count: int = 3,
        cluster_window_seconds: float = 120,
        history_window_seconds: float = 3600,
    ):
        self.threshold_usd = threshold_usd
        self.cluster_count = cluster_count
        self.cluster_window_seconds = cluster_window_seconds
        self.history_window_seconds = history_window_seconds

        self._trades: deque[WhaleTrade] = deque()
        self._last_cluster_ts: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, raw: dict) -> tuple[Optional[WhaleTrade], Optional[WhaleClusterAlert]]:
        """
        Parse a raw Hyperliquid public trade message.

        Returns
        -------
        (WhaleTrade | None, WhaleClusterAlert | None)
            A whale trade if the threshold is met, and a cluster alert if
            enough whales appeared within the cluster window.
        """
        trade = self._parse(raw)
        if trade is None:
            return None, None

        # Not a whale — skip silently
        if trade.usd_value < self.threshold_usd:
            return None, None

        logger.info(
            "🐋 WHALE %s: %s %.4f @ $%.2f ($%.0f)",
            trade.side,
            trade.symbol,
            trade.qty,
            trade.price,
            trade.usd_value,
        )

        self._trades.append(trade)
        self._prune()

        cluster = self._check_cluster(trade.symbol)
        return trade, cluster

    def get_rolling_pressure(self, symbol: str, window_seconds: float = 300) -> dict:
        """
        Summarise buy vs sell whale pressure over a rolling window.

        Returns dict with keys: buy_usd, sell_usd, net_usd, buy_count, sell_count.
        """
        now = time.time()
        cutoff = now - window_seconds
        buy_usd = 0.0
        sell_usd = 0.0
        buy_count = 0
        sell_count = 0
        for wt in reversed(self._trades):
            if wt.timestamp < cutoff:
                break
            if wt.symbol != symbol:
                continue
            if wt.side == "Buy":
                buy_usd += wt.usd_value
                buy_count += 1
            else:
                sell_usd += wt.usd_value
                sell_count += 1
        return {
            "buy_usd": buy_usd,
            "sell_usd": sell_usd,
            "net_usd": buy_usd - sell_usd,
            "buy_count": buy_count,
            "sell_count": sell_count,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse(self, raw: dict) -> Optional[WhaleTrade]:
        """Parse a raw Hyperliquid trade dict into a WhaleTrade."""
        try:
            price = float(raw["px"])
            qty = float(raw["sz"])
            side_raw = raw.get("side", "")
            side = "Buy" if side_raw == "B" else "Sell"
            coin = raw.get("coin", "")
            return WhaleTrade(
                symbol=f"{coin}USDT" if coin and not coin.endswith("USDT") else coin,
                side=side,
                price=price,
                qty=qty,
                usd_value=price * qty,
                timestamp=float(raw.get("time", time.time() * 1000)) / 1000,
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.debug("Failed to parse trade: %s — %s", raw, exc)
            return None

    def _prune(self):
        cutoff = time.time() - self.history_window_seconds
        while self._trades and self._trades[0].timestamp < cutoff:
            self._trades.popleft()

    def _check_cluster(self, symbol: str) -> Optional[WhaleClusterAlert]:
        now = time.time()
        cutoff = now - self.cluster_window_seconds

        recent = [
            wt for wt in self._trades
            if wt.symbol == symbol and wt.timestamp >= cutoff
        ]
        if len(recent) < self.cluster_count:
            return None

        # Deduplicate per window
        last = self._last_cluster_ts.get(symbol, 0.0)
        if (now - last) < self.cluster_window_seconds:
            return None

        self._last_cluster_ts[symbol] = now

        total = sum(wt.usd_value for wt in recent)
        buy_usd = sum(wt.usd_value for wt in recent if wt.side == "Buy")
        sell_usd = total - buy_usd
        dominant = "Buy" if buy_usd >= sell_usd else "Sell"

        alert = WhaleClusterAlert(
            symbol=symbol,
            dominant_side=dominant,
            total_usd=total,
            trade_count=len(recent),
            window_seconds=self.cluster_window_seconds,
            start_ts=recent[0].timestamp,
            end_ts=recent[-1].timestamp,
        )
        logger.warning("🐋🐋 WHALE CLUSTER DETECTED: %s", alert)
        return alert
