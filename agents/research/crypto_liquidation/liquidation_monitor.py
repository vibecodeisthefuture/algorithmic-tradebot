"""
Liquidation Monitor

Receives raw trade events from the Hyperliquid WebSocket stream and provides:
    1. Real-time liquidation aggregation (rolling window)
    2. Cascade detection (configurable $ threshold within time window)
    3. Price-level liquidation density (heatmap data)

Used by the agent coordinator (agent.py) to generate alerts.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("crypto_liquidation.monitor")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class LiquidationEvent:
    """Single parsed liquidation event (from Hyperliquid or CoinGlass)."""

    symbol: str
    side: str          # "Buy" or "Sell" (the liquidated direction)
    price: float
    qty: float
    usd_value: float   # qty * price
    timestamp: float   # epoch seconds


@dataclass
class CascadeAlert:
    """Emitted when a liquidation cascade is detected."""

    symbol: str
    side: str                           # dominant direction
    total_usd: float                    # cumulative $ liquidated
    event_count: int                    # number of liquidation events
    window_seconds: float               # the time window that triggered
    start_ts: float
    end_ts: float
    price_range: tuple[float, float]    # (min_price, max_price)


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class LiquidationMonitor:
    """
    Buffers incoming liquidation events and detects cascades.

    Parameters
    ----------
    cascade_usd_threshold : float
        Minimum cumulative $ volume within ``cascade_window_seconds`` to
        trigger a cascade alert.  Default: $50,000,000 (50M).
    cascade_window_seconds : float
        Rolling window for cascade detection.  Default: 300 (5 minutes).
    history_window_seconds : float
        How long to keep liquidation events in the rolling buffer for
        heatmap / analysis.  Default: 3600 (1 hour).
    """

    def __init__(
        self,
        cascade_usd_threshold: float = 50_000_000,
        cascade_window_seconds: float = 300,
        history_window_seconds: float = 3600,
    ):
        self.cascade_usd_threshold = cascade_usd_threshold
        self.cascade_window_seconds = cascade_window_seconds
        self.history_window_seconds = history_window_seconds

        # Rolling event buffer (newest at right)
        self._events: deque[LiquidationEvent] = deque()

        # Track last cascade alert per symbol to avoid duplicates
        self._last_cascade_ts: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, raw: dict) -> Optional[CascadeAlert]:
        """
        Parse a raw Hyperliquid trade message and check for cascade.

        Returns a CascadeAlert if a new cascade is detected, else None.
        """
        event = self._parse(raw)
        if event is None:
            return None

        self._events.append(event)
        self._prune()

        return self._check_cascade(event.symbol)

    def get_heatmap_data(self, symbol: str, bucket_usd: float = 100.0) -> dict[float, float]:
        """
        Return a dict of {price_bucket: total_usd_liquidated} for the
        events currently in the buffer.  Useful for building a simple
        liquidation heatmap.
        """
        now = time.time()
        buckets: dict[float, float] = {}
        for ev in self._events:
            if ev.symbol != symbol:
                continue
            if (now - ev.timestamp) > self.history_window_seconds:
                continue
            bucket = round(ev.price / bucket_usd) * bucket_usd
            buckets[bucket] = buckets.get(bucket, 0.0) + ev.usd_value
        return dict(sorted(buckets.items()))

    def get_rolling_stats(self, symbol: str, window_seconds: float = 60) -> dict:
        """
        Quick stats for the last ``window_seconds``:
            total_usd, count, long_usd, short_usd
        """
        now = time.time()
        cutoff = now - window_seconds
        total_usd = 0.0
        long_usd = 0.0
        short_usd = 0.0
        count = 0
        for ev in reversed(self._events):
            if ev.timestamp < cutoff:
                break
            if ev.symbol != symbol:
                continue
            total_usd += ev.usd_value
            count += 1
            if ev.side == "Sell":  # Sell liquidation → longs were liquidated
                long_usd += ev.usd_value
            else:
                short_usd += ev.usd_value
        return {
            "total_usd": total_usd,
            "count": count,
            "long_usd": long_usd,
            "short_usd": short_usd,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse(self, raw: dict) -> Optional[LiquidationEvent]:
        """Parse a raw Hyperliquid trade dict into a LiquidationEvent."""
        try:
            price = float(raw["px"])
            qty = float(raw["sz"])
            side_raw = raw.get("side", "")
            side = "Buy" if side_raw == "B" else "Sell"
            coin = raw.get("coin", "")
            return LiquidationEvent(
                symbol=f"{coin}USDT" if coin and not coin.endswith("USDT") else coin,
                side=side,
                price=price,
                qty=qty,
                usd_value=price * qty,
                timestamp=float(raw.get("time", time.time() * 1000)) / 1000,
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Failed to parse liquidation event: %s — %s", raw, exc)
            return None

    def _prune(self):
        """Remove events older than history_window_seconds."""
        cutoff = time.time() - self.history_window_seconds
        while self._events and self._events[0].timestamp < cutoff:
            self._events.popleft()

    def _check_cascade(self, symbol: str) -> Optional[CascadeAlert]:
        """Check if liquidations in the cascade window exceed the threshold."""
        now = time.time()
        cutoff = now - self.cascade_window_seconds

        total = 0.0
        count = 0
        min_price = float("inf")
        max_price = 0.0
        start_ts = now
        sides: dict[str, float] = {}

        for ev in reversed(self._events):
            if ev.timestamp < cutoff:
                break
            if ev.symbol != symbol:
                continue
            total += ev.usd_value
            count += 1
            min_price = min(min_price, ev.price)
            max_price = max(max_price, ev.price)
            start_ts = ev.timestamp
            sides[ev.side] = sides.get(ev.side, 0.0) + ev.usd_value

        if total < self.cascade_usd_threshold:
            return None

        # Deduplicate: don't fire if we already alerted within this window
        last = self._last_cascade_ts.get(symbol, 0.0)
        if (now - last) < self.cascade_window_seconds:
            return None

        self._last_cascade_ts[symbol] = now
        dominant_side = max(sides, key=sides.get) if sides else "unknown"

        alert = CascadeAlert(
            symbol=symbol,
            side=dominant_side,
            total_usd=total,
            event_count=count,
            window_seconds=self.cascade_window_seconds,
            start_ts=start_ts,
            end_ts=now,
            price_range=(min_price, max_price),
        )
        logger.warning("🔴 CASCADE DETECTED: %s", alert)
        return alert
