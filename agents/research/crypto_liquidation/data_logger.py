"""
Data Logger for the Crypto Liquidation Agent

Handles persisting liquidation events, whale trades, and alerts to
the shared SQLite database (data/tradebot.db).

Optimizations:
    1. $10,000 minimum USD threshold — small liquidations are only
       processed in-memory for cascade detection, not written to DB.
    2. Batch inserts — events are buffered and flushed every 5 seconds
       to reduce SQLite write pressure.
    3. Aggregation — hourly roll-up into crypto_liquidation_summary
       before raw rows are pruned.
    4. 7-day retention — raw rows older than 7 days are deleted after
       aggregation preserves the historical stats.

Tables written to:
    - crypto_liquidations          → individual events (≥ $10K only)
    - whale_trades                 → individual whale trades (≥ $1M)
    - crypto_liquidation_summary   → hourly aggregated stats (permanent)
    - event_log                    → cascade / cluster alerts → Manager
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, and_, extract

logger = logging.getLogger("crypto_liquidation.data_logger")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum USD value for a liquidation event to be logged to the DB.
# Smaller events are still processed in-memory for cascade detection.
LIQUIDATION_LOG_THRESHOLD_USD = 10_000

# Batch flush interval in seconds.
BATCH_FLUSH_INTERVAL = 5.0

# Retention period for raw event data.
RETENTION_DAYS = 7


def _epoch_to_dt(epoch: float) -> datetime:
    """Convert epoch seconds to timezone-aware datetime."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# ---------------------------------------------------------------------------
# Database Writer
# ---------------------------------------------------------------------------


class DataLogger:
    """
    Writes liquidation and whale data to the shared TradeBot database.

    Features:
        - Threshold filtering: only liquidation events ≥ $10K are persisted.
        - Batch buffering: rows are queued in memory and flushed every 5s.
        - Aggregation + pruning: hourly roll-ups, 7-day raw retention.
        - Alert publishing: cascade / cluster alerts → event_log table.
    """

    def __init__(self):
        # Batch buffers (protected by a lock for thread safety)
        self._lock = threading.Lock()
        self._liq_buffer: list[dict] = []
        self._whale_buffer: list[dict] = []
        self._last_flush = time.monotonic()

    # ------------------------------------------------------------------
    # Liquidation Events → crypto_liquidations table (≥ $10K only)
    # ------------------------------------------------------------------

    def log_liquidation(self, event, is_cascade: bool = False):
        """
        Buffer a LiquidationEvent for batch insert.

        Events below $10,000 USD are silently skipped (they are still
        processed in-memory by the LiquidationMonitor for cascade
        detection — only the DB write is skipped).
        """
        if event.usd_value < LIQUIDATION_LOG_THRESHOLD_USD:
            return

        row = {
            "timestamp": _epoch_to_dt(event.timestamp),
            "symbol": event.symbol,
            "side": event.side,
            "price": event.price,
            "qty": event.qty,
            "usd_value": event.usd_value,
            "is_cascade": is_cascade,
        }
        with self._lock:
            self._liq_buffer.append(row)

        self._maybe_flush()

    # ------------------------------------------------------------------
    # Whale Trades → whale_trades table
    # ------------------------------------------------------------------

    def log_whale_trade(self, trade, is_cluster: bool = False):
        """Buffer a WhaleTrade for batch insert."""
        row = {
            "timestamp": _epoch_to_dt(trade.timestamp),
            "symbol": trade.symbol,
            "side": trade.side,
            "price": trade.price,
            "qty": trade.qty,
            "usd_value": trade.usd_value,
            "is_cluster": is_cluster,
        }
        with self._lock:
            self._whale_buffer.append(row)

        self._maybe_flush()

    # ------------------------------------------------------------------
    # Batch Flush
    # ------------------------------------------------------------------

    def _maybe_flush(self):
        """Flush buffers if enough time has passed since the last flush."""
        now = time.monotonic()
        if (now - self._last_flush) < BATCH_FLUSH_INTERVAL:
            return
        self.flush()

    def flush(self):
        """
        Write all buffered rows to the database in a single transaction.
        Called automatically every BATCH_FLUSH_INTERVAL seconds, and can
        be called manually (e.g., on shutdown).
        """
        with self._lock:
            liq_rows = self._liq_buffer[:]
            whale_rows = self._whale_buffer[:]
            self._liq_buffer.clear()
            self._whale_buffer.clear()
            self._last_flush = time.monotonic()

        if not liq_rows and not whale_rows:
            return

        try:
            from agents.common.database import get_db_session
            from agents.common.models import CryptoLiquidation, WhaleTrade

            with get_db_session() as session:
                if liq_rows:
                    session.bulk_insert_mappings(CryptoLiquidation, liq_rows)
                if whale_rows:
                    session.bulk_insert_mappings(WhaleTrade, whale_rows)

            logger.debug(
                "Flushed %d liquidations + %d whale trades to DB.",
                len(liq_rows), len(whale_rows),
            )
        except Exception as exc:
            logger.error("Batch flush failed: %s", exc)

    # ------------------------------------------------------------------
    # Aggregation + Pruning (called periodically by agent.py)
    # ------------------------------------------------------------------

    def aggregate_and_prune(self):
        """
        1. Roll up raw rows older than RETENTION_DAYS into hourly summaries
           in the crypto_liquidation_summary table.
        2. Delete the raw rows that were just aggregated.

        This should be called once per day (or on agent startup).
        """
        try:
            from agents.common.database import get_db_session
            from agents.common.models import (
                CryptoLiquidation,
                WhaleTrade,
                CryptoLiquidationSummary,
            )

            cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

            with get_db_session() as session:
                # --- Aggregate liquidations ---
                liq_rows = (
                    session.query(
                        func.strftime("%Y-%m-%d %H:00:00", CryptoLiquidation.timestamp).label("hour"),
                        CryptoLiquidation.symbol,
                        func.count().label("liq_count"),
                        func.sum(CryptoLiquidation.usd_value).label("liq_total_usd"),
                        func.sum(
                            func.iif(CryptoLiquidation.side == "Sell", CryptoLiquidation.usd_value, 0)
                        ).label("liq_long_usd"),
                        func.sum(
                            func.iif(CryptoLiquidation.side == "Buy", CryptoLiquidation.usd_value, 0)
                        ).label("liq_short_usd"),
                        func.max(CryptoLiquidation.usd_value).label("liq_max_single_usd"),
                        func.sum(func.iif(CryptoLiquidation.is_cascade, 1, 0)).label("cascade_count"),
                    )
                    .filter(CryptoLiquidation.timestamp < cutoff)
                    .group_by("hour", CryptoLiquidation.symbol)
                    .all()
                )

                # --- Aggregate whale trades ---
                whale_rows = (
                    session.query(
                        func.strftime("%Y-%m-%d %H:00:00", WhaleTrade.timestamp).label("hour"),
                        WhaleTrade.symbol,
                        func.count().label("whale_count"),
                        func.sum(WhaleTrade.usd_value).label("whale_total_usd"),
                        func.sum(
                            func.iif(WhaleTrade.side == "Buy", WhaleTrade.usd_value, 0)
                        ).label("whale_buy_usd"),
                        func.sum(
                            func.iif(WhaleTrade.side == "Sell", WhaleTrade.usd_value, 0)
                        ).label("whale_sell_usd"),
                        func.sum(func.iif(WhaleTrade.is_cluster, 1, 0)).label("cluster_count"),
                    )
                    .filter(WhaleTrade.timestamp < cutoff)
                    .group_by("hour", WhaleTrade.symbol)
                    .all()
                )

                # --- Merge into summary table ---
                # Build a lookup of whale data keyed by (hour, symbol)
                whale_lookup: dict[tuple, dict] = {}
                for wr in whale_rows:
                    key = (wr.hour, wr.symbol)
                    whale_lookup[key] = {
                        "whale_count": wr.whale_count or 0,
                        "whale_total_usd": wr.whale_total_usd or 0.0,
                        "whale_buy_usd": wr.whale_buy_usd or 0.0,
                        "whale_sell_usd": wr.whale_sell_usd or 0.0,
                        "cluster_count": wr.cluster_count or 0,
                    }

                # Collect all unique (hour, symbol) keys
                all_keys = set()
                for lr in liq_rows:
                    all_keys.add((lr.hour, lr.symbol))
                for key in whale_lookup:
                    all_keys.add(key)

                inserted = 0
                for key in all_keys:
                    hour_str, symbol = key
                    hour_dt = datetime.strptime(hour_str, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )

                    # Check if summary already exists (idempotent re-runs)
                    existing = (
                        session.query(CryptoLiquidationSummary)
                        .filter_by(hour=hour_dt, symbol=symbol)
                        .first()
                    )
                    if existing:
                        continue

                    # Get liq data for this key
                    liq_data = next(
                        (lr for lr in liq_rows if (lr.hour, lr.symbol) == key),
                        None,
                    )
                    w = whale_lookup.get(key, {})

                    summary = CryptoLiquidationSummary(
                        hour=hour_dt,
                        symbol=symbol,
                        liq_count=liq_data.liq_count if liq_data else 0,
                        liq_total_usd=liq_data.liq_total_usd if liq_data else 0.0,
                        liq_long_usd=liq_data.liq_long_usd if liq_data else 0.0,
                        liq_short_usd=liq_data.liq_short_usd if liq_data else 0.0,
                        liq_max_single_usd=liq_data.liq_max_single_usd if liq_data else 0.0,
                        cascade_count=liq_data.cascade_count if liq_data else 0,
                        whale_count=w.get("whale_count", 0),
                        whale_total_usd=w.get("whale_total_usd", 0.0),
                        whale_buy_usd=w.get("whale_buy_usd", 0.0),
                        whale_sell_usd=w.get("whale_sell_usd", 0.0),
                        cluster_count=w.get("cluster_count", 0),
                    )
                    session.add(summary)
                    inserted += 1

                # --- Delete old raw rows ---
                liq_deleted = (
                    session.query(CryptoLiquidation)
                    .filter(CryptoLiquidation.timestamp < cutoff)
                    .delete()
                )
                whale_deleted = (
                    session.query(WhaleTrade)
                    .filter(WhaleTrade.timestamp < cutoff)
                    .delete()
                )

            logger.info(
                "Aggregation complete: %d summary rows inserted, "
                "%d liquidations pruned, %d whale trades pruned.",
                inserted, liq_deleted, whale_deleted,
            )
        except Exception as exc:
            logger.error("Aggregation/pruning failed: %s", exc)

    # ------------------------------------------------------------------
    # Cascade Alert → event_log table
    # ------------------------------------------------------------------

    def publish_cascade_alert(self, alert):
        """Write a CascadeAlert to the shared event_log table."""
        try:
            from agents.common.database import get_db_session
            from agents.common.models import EventLog
            from agents.common.enums import EventType, EventUrgency

            with get_db_session() as session:
                event = EventLog(
                    event_type=EventType.LIQUIDATION_CASCADE,
                    urgency=EventUrgency.CRITICAL,
                    source_agent="crypto_liquidation",
                    target_agent="manager",
                    summary=(
                        f"🔴 LIQUIDATION CASCADE: {alert.symbol} "
                        f"${alert.total_usd:,.0f} in {alert.window_seconds:.0f}s "
                        f"({alert.event_count} events, dominant side: {alert.side})"
                    ),
                    details={
                        "type": "cascade",
                        "symbol": alert.symbol,
                        "side": alert.side,
                        "total_usd": alert.total_usd,
                        "event_count": alert.event_count,
                        "window_seconds": alert.window_seconds,
                        "price_low": alert.price_range[0],
                        "price_high": alert.price_range[1],
                    },
                )
                session.add(event)
            logger.info("Published cascade alert to event_log for %s", alert.symbol)
        except Exception as exc:
            logger.error("Failed to publish cascade alert to DB: %s", exc)

        # Real-time ZeroMQ notification (non-blocking, best-effort)
        try:
            from agents.common.event_bus import EventPublisher, TOPIC_LIQUIDATION_CASCADE

            pub = EventPublisher()
            pub.publish(TOPIC_LIQUIDATION_CASCADE, {
                "symbol": alert.symbol,
                "side": alert.side,
                "total_usd": alert.total_usd,
                "event_count": alert.event_count,
                "window_seconds": alert.window_seconds,
            })
            pub.close()
        except Exception as exc:
            logger.debug("ZeroMQ cascade notification skipped: %s", exc)

    # ------------------------------------------------------------------
    # Whale Cluster Alert → event_log table
    # ------------------------------------------------------------------

    def publish_whale_cluster_alert(self, alert):
        """Write a WhaleClusterAlert to the shared event_log table."""
        try:
            from agents.common.database import get_db_session
            from agents.common.models import EventLog
            from agents.common.enums import EventType, EventUrgency

            with get_db_session() as session:
                event = EventLog(
                    event_type=EventType.WHALE_CLUSTER,
                    urgency=EventUrgency.URGENT,
                    source_agent="crypto_liquidation",
                    target_agent="manager",
                    summary=(
                        f"🐋 WHALE CLUSTER: {alert.symbol} "
                        f"${alert.total_usd:,.0f} across {alert.trade_count} trades "
                        f"in {alert.window_seconds:.0f}s (dominant: {alert.dominant_side})"
                    ),
                    details={
                        "type": "whale_cluster",
                        "symbol": alert.symbol,
                        "dominant_side": alert.dominant_side,
                        "total_usd": alert.total_usd,
                        "trade_count": alert.trade_count,
                        "window_seconds": alert.window_seconds,
                    },
                )
                session.add(event)
            logger.info("Published whale cluster alert to event_log for %s", alert.symbol)
        except Exception as exc:
            logger.error("Failed to publish whale cluster alert to DB: %s", exc)

        # Real-time ZeroMQ notification (non-blocking, best-effort)
        try:
            from agents.common.event_bus import EventPublisher, TOPIC_WHALE_CLUSTER

            pub = EventPublisher()
            pub.publish(TOPIC_WHALE_CLUSTER, {
                "symbol": alert.symbol,
                "dominant_side": alert.dominant_side,
                "total_usd": alert.total_usd,
                "trade_count": alert.trade_count,
                "window_seconds": alert.window_seconds,
            })
            pub.close()
        except Exception as exc:
            logger.debug("ZeroMQ whale cluster notification skipped: %s", exc)
