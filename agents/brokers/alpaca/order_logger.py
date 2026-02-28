"""
Order History Logger Module (Alpaca)

Logs all trading orders to the shared SQLite database (data/tradebot.db)
using the Trade ORM model for unified order tracking across all brokers.

Database Table: trades
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("alpaca.order_logger")


def _map_status(status_str: str) -> str:
    """Map Alpaca status strings to TradeStatus enum values."""
    mapping = {
        "filled": "FILLED",
        "partially_filled": "PARTIAL",
        "canceled": "CANCELLED",
        "cancelled": "CANCELLED",
        "expired": "CANCELLED",
        "rejected": "REJECTED",
        "pending_new": "SUBMITTED",
        "accepted": "SUBMITTED",
        "new": "SUBMITTED",
    }
    return mapping.get(status_str.lower(), "SUBMITTED")


def _map_side(side_str: str) -> str:
    """Map Alpaca side strings to TradeSide enum values."""
    return "BUY" if "buy" in side_str.lower() else "SELL"


def _map_order_type(order_type_str: str) -> str:
    """Map Alpaca order type strings to OrderType enum values."""
    mapping = {
        "market": "MARKET",
        "limit": "LIMIT",
        "stop": "STOP",
        "stop_limit": "STOP",
        "trailing_stop": "STOP",
        "bracket": "BRACKET",
    }
    return mapping.get(order_type_str.lower(), "MARKET")


class OrderLogger:
    """
    Logs Alpaca trading orders to the shared trades DB table.

    Replaces the previous CSV-based logging with database-only persistence.
    """

    def log_order(self, order, asset_type: str = "Stock"):
        """
        Log an Alpaca Order to the trades table.

        Args:
            order: Alpaca Order object
            asset_type: Type of asset (Stock, Crypto, ETF) — stored in notes
        """
        try:
            from agents.common.database import get_db_session
            from agents.common.models import Trade
            from agents.common.enums import TradeSide, TradeStatus, OrderType, BrokerName

            order_id = str(order.id)
            symbol = order.symbol
            side_str = str(order.side).split(".")[-1].lower()
            order_type_str = str(order.type).split(".")[-1].lower()
            status_str = str(order.status).split(".")[-1].lower()

            qty = float(order.qty) if order.qty else 0.0
            filled_qty = float(order.filled_qty) if order.filled_qty else None
            filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
            limit_price = float(order.limit_price) if order.limit_price else None
            commission = 0.0  # Alpaca doesn't charge commission

            # Calculate slippage if we have both a limit price and fill
            slippage_pct = None
            if limit_price and filled_price and limit_price > 0:
                slippage_pct = ((filled_price - limit_price) / limit_price) * 100

            with get_db_session() as session:
                # Check if this order already exists (update if so)
                existing = session.query(Trade).filter_by(id=order_id).first()
                if existing:
                    existing.status = TradeStatus(_map_status(status_str))
                    existing.filled_qty = filled_qty
                    existing.filled_price = filled_price
                    existing.slippage_pct = slippage_pct
                    logger.info("Updated trade %s in DB", order_id)
                else:
                    trade = Trade(
                        id=order_id,
                        symbol=symbol,
                        side=TradeSide(_map_side(side_str)),
                        qty=qty,
                        order_type=OrderType(_map_order_type(order_type_str)),
                        limit_price=limit_price,
                        filled_qty=filled_qty,
                        filled_price=filled_price,
                        status=TradeStatus(_map_status(status_str)),
                        broker=BrokerName.ALPACA,
                        commission=commission,
                        slippage_pct=slippage_pct,
                        notes=f"asset_type={asset_type}",
                    )
                    session.add(trade)
                    logger.info("Logged trade %s to DB", order_id)

            print(f"✓ Order logged to database (trades table)")

            # Real-time ZeroMQ notification (best-effort)
            try:
                from agents.common.event_bus import (
                    EventPublisher,
                    TOPIC_TRADE_EXECUTED,
                    TOPIC_TRADE_FAILED,
                )

                pub = EventPublisher()
                topic = (
                    TOPIC_TRADE_EXECUTED
                    if status_str in ("filled", "partially_filled")
                    else TOPIC_TRADE_FAILED
                )
                pub.publish(topic, {
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": _map_side(side_str),
                    "qty": qty,
                    "filled_price": filled_price,
                    "status": _map_status(status_str),
                    "broker": "ALPACA",
                    "asset_type": asset_type,
                })
                pub.close()
            except Exception:
                pass  # ZeroMQ is best-effort; DB is the source of truth

        except Exception as e:
            logger.error("Failed to log order to DB: %s", e)
            print(f"Warning: Failed to log order to DB: {str(e)}")

    def get_order_history(self, limit: Optional[int] = None):
        """
        Read order history from the trades table.

        Args:
            limit: Maximum number of recent orders to return

        Returns:
            List of Trade ORM objects (most recent first)
        """
        try:
            from agents.common.database import get_db_session
            from agents.common.models import Trade
            from agents.common.enums import BrokerName

            with get_db_session() as session:
                query = (
                    session.query(Trade)
                    .filter_by(broker=BrokerName.ALPACA)
                    .order_by(Trade.timestamp.desc())
                )
                if limit:
                    query = query.limit(limit)
                return query.all()

        except Exception as e:
            logger.error("Failed to read order history: %s", e)
            return []

    def print_recent_orders(self, limit: int = 10):
        """Print recent orders in formatted table."""
        orders = self.get_order_history(limit=limit)

        if not orders:
            print("No order history found.")
            return

        print("\n" + "=" * 100)
        print(f" RECENT ORDERS (Last {min(limit, len(orders))})")
        print("=" * 100)

        for order in orders:
            print(f"\n[{order.timestamp}]")
            print(f"  {order.side.value} {order.symbol}")
            print(f"  Type: {order.order_type.value if order.order_type else 'N/A'} | Status: {order.status.value}")

            if order.qty:
                print(f"  Quantity: {order.qty}")
            if order.filled_price:
                print(f"  Avg Fill Price: ${order.filled_price}")
            if order.filled_qty and order.filled_price:
                print(f"  Order Value: ${order.filled_qty * order.filled_price:,.2f}")

            print(f"  Order ID: {order.id}")

        print("\n" + "=" * 100 + "\n")

    def get_statistics(self):
        """Get order statistics from the trades table."""
        orders = self.get_order_history()

        if not orders:
            return {
                "total_orders": 0,
                "total_value": 0.0,
                "by_action": {},
                "by_symbol": {},
            }

        from collections import defaultdict
        actions = defaultdict(int)
        symbols = defaultdict(int)
        total_value = 0.0

        for order in orders:
            actions[order.side.value] += 1
            symbols[order.symbol] += 1
            if order.filled_qty and order.filled_price:
                total_value += order.filled_qty * order.filled_price

        return {
            "total_orders": len(orders),
            "total_value": total_value,
            "by_action": dict(actions),
            "by_symbol": dict(sorted(symbols.items(), key=lambda x: x[1], reverse=True)),
        }

    def analyze(self):
        """Print full order history analysis."""
        print("\n" + "=" * 70)
        print(" ORDER HISTORY ANALYSIS")
        print("=" * 70)

        orders = self.get_order_history()
        if not orders:
            print("\nNo order history found.")
            return

        stats = self.get_statistics()

        print(f"\n📊 SUMMARY")
        print("-" * 70)
        print(f"Total Orders: {stats['total_orders']}")
        print(f"Total Order Value: ${stats['total_value']:,.2f}")
        print(f"First Order: {orders[-1].timestamp}")
        print(f"Latest Order: {orders[0].timestamp}")

        print(f"\n💹 BY ACTION")
        print("-" * 70)
        for action, count in stats["by_action"].items():
            print(f"{action}: {count} orders")

        print(f"\n🎯 TOP SYMBOLS")
        print("-" * 70)
        for i, (symbol, count) in enumerate(stats["by_symbol"].items()):
            if i >= 10:
                break
            print(f"{symbol}: {count} orders")

        print("\n" + "=" * 70 + "\n")


def main():
    """Test the order logger."""
    the_logger = OrderLogger()
    the_logger.print_recent_orders(limit=10)
    the_logger.analyze()


if __name__ == "__main__":
    main()
