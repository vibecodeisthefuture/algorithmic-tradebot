"""
OKX Order History Logger Module

Logs all OKX trading orders to the shared SQLite database (data/tradebot.db)
using the Trade ORM model for unified order tracking across all brokers.

Database Table: trades
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger("okx.order_logger")


def _map_okx_status(status_str: str) -> str:
    """Map OKX state strings to TradeStatus enum values."""
    mapping = {
        "live": "SUBMITTED",
        "partially_filled": "PARTIAL",
        "filled": "FILLED",
        "canceled": "CANCELLED",
        "cancelled": "CANCELLED",
        "mmp_canceled": "CANCELLED",
    }
    return mapping.get(status_str.lower(), "SUBMITTED")


def _map_okx_side(side_str: str) -> str:
    """Map OKX side strings to TradeSide enum values."""
    return "BUY" if "buy" in side_str.lower() else "SELL"


def _map_okx_order_type(ord_type: str) -> str:
    """Map OKX order type strings to OrderType enum values."""
    mapping = {
        "market": "MARKET",
        "limit": "LIMIT",
        "post_only": "LIMIT",
        "fok": "MARKET",
        "ioc": "MARKET",
        "optimal_limit_ioc": "LIMIT",
    }
    return mapping.get(ord_type.lower(), "MARKET")


class OKXOrderLogger:
    """
    Logs OKX trading orders to the shared trades DB table.

    Replaces the previous CSV-based logging with database-only persistence.
    """

    def log_order(self, order_data: Dict[str, Any], order_request: Dict[str, Any] = None):
        """
        Log an order to the trades table.

        Args:
            order_data: OKX order response data
            order_request: Original order request parameters (optional)
        """
        try:
            from agents.common.database import get_db_session
            from agents.common.models import Trade
            from agents.common.enums import TradeSide, TradeStatus, OrderType, BrokerName

            order_id = order_data.get("ordId", "")
            if not order_id:
                logger.warning("No ordId in OKX response, skipping log")
                return

            inst_id = order_request.get("instId", "") if order_request else ""
            side = order_request.get("side", "buy") if order_request else "buy"
            ord_type = order_request.get("ordType", "market") if order_request else "market"
            sz = order_request.get("sz", "0") if order_request else "0"
            px = order_request.get("px", "") if order_request else ""

            # Status from response
            is_ok = order_data.get("sCode") == "0"
            status_val = "SUBMITTED" if is_ok else "FAILED"

            qty = float(sz) if sz else 0.0
            limit_price = float(px) if px else None

            with get_db_session() as session:
                existing = session.query(Trade).filter_by(id=order_id).first()
                if existing:
                    existing.status = TradeStatus(status_val)
                    logger.info("Updated trade %s in DB", order_id)
                else:
                    trade = Trade(
                        id=order_id,
                        symbol=inst_id,
                        side=TradeSide(_map_okx_side(side)),
                        qty=qty,
                        order_type=OrderType(_map_okx_order_type(ord_type)),
                        limit_price=limit_price,
                        status=TradeStatus(status_val),
                        broker=BrokerName.OKX,
                        notes=f"sMsg={order_data.get('sMsg', '')}",
                    )
                    session.add(trade)
                    logger.info("Logged trade %s to DB", order_id)

            print("✓ Order logged to database (trades table)")

        except Exception as e:
            logger.error("Failed to log order to DB: %s", e)
            print(f"Warning: Failed to log order to DB: {str(e)}")

    def log_order_details(self, order_details: Dict[str, Any]):
        """
        Update an existing trade record with filled order details.

        Args:
            order_details: Full order details from OKX get_order_details API
        """
        try:
            from agents.common.database import get_db_session
            from agents.common.models import Trade
            from agents.common.enums import TradeSide, TradeStatus, OrderType, BrokerName

            data = order_details.get("data", [{}])[0] if order_details.get("data") else {}

            order_id = data.get("ordId", "")
            if not order_id:
                return

            avg_px = data.get("avgPx", "")
            filled_sz = data.get("accFillSz", "")
            state = data.get("state", "")
            fee = data.get("fee", "")

            filled_price = float(avg_px) if avg_px else None
            filled_qty = float(filled_sz) if filled_sz else None
            commission = abs(float(fee)) if fee else None

            # Calculate slippage
            slippage_pct = None

            with get_db_session() as session:
                existing = session.query(Trade).filter_by(id=order_id).first()
                if existing:
                    existing.filled_price = filled_price
                    existing.filled_qty = filled_qty
                    existing.status = TradeStatus(_map_okx_status(state)) if state else existing.status
                    if commission is not None:
                        existing.commission = commission
                    if existing.limit_price and filled_price and existing.limit_price > 0:
                        existing.slippage_pct = ((filled_price - existing.limit_price) / existing.limit_price) * 100
                    logger.info("Updated trade details %s in DB", order_id)
                else:
                    # If we somehow missed the initial log, create a new record
                    inst_id = data.get("instId", "")
                    side = data.get("side", "buy")
                    ord_type = data.get("ordType", "market")
                    sz = data.get("sz", "0")
                    px = data.get("px", "")

                    trade = Trade(
                        id=order_id,
                        symbol=inst_id,
                        side=TradeSide(_map_okx_side(side)),
                        qty=float(sz) if sz else 0.0,
                        order_type=OrderType(_map_okx_order_type(ord_type)),
                        limit_price=float(px) if px else None,
                        filled_qty=filled_qty,
                        filled_price=filled_price,
                        status=TradeStatus(_map_okx_status(state)) if state else TradeStatus.FILLED,
                        broker=BrokerName.OKX,
                        commission=commission,
                    )
                    session.add(trade)
                    logger.info("Created trade %s from details in DB", order_id)

            print("✓ Order details logged to database (trades table)")

        except Exception as e:
            logger.error("Failed to log order details to DB: %s", e)
            print(f"Warning: Failed to log order details: {str(e)}")

    def get_order_history(self, limit: Optional[int] = None):
        """
        Read OKX order history from the trades table.

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
                    .filter_by(broker=BrokerName.OKX)
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
        print(f" OKX RECENT ORDERS (Last {min(limit, len(orders))})")
        print("=" * 100)

        for order in orders:
            print(f"\n[{order.timestamp}]")
            print(f"  {order.side.value} {order.symbol}")
            print(f"  Type: {order.order_type.value if order.order_type else 'N/A'} | Status: {order.status.value}")

            if order.qty:
                print(f"  Quantity: {order.qty}")
            if order.limit_price:
                print(f"  Limit Price: ${order.limit_price}")
            if order.filled_price:
                print(f"  Avg Fill Price: ${order.filled_price}")
            if order.filled_qty and order.filled_price:
                print(f"  Order Value: ${order.filled_qty * order.filled_price:,.2f}")
            if order.commission:
                print(f"  Fee: {order.commission}")

            print(f"  Order ID: {order.id}")

        print("\n" + "=" * 100 + "\n")

    def get_statistics(self):
        """Get order statistics from the trades table."""
        orders = self.get_order_history()

        if not orders:
            return {
                "total_orders": 0,
                "total_value": 0.0,
                "by_instrument": {},
                "by_action": {},
                "by_status": {},
            }

        from collections import defaultdict
        instruments = defaultdict(int)
        actions = defaultdict(int)
        statuses = defaultdict(int)
        total_value = 0.0

        for order in orders:
            instruments[order.symbol] += 1
            actions[order.side.value] += 1
            statuses[order.status.value] += 1
            if order.filled_qty and order.filled_price:
                total_value += order.filled_qty * order.filled_price

        return {
            "total_orders": len(orders),
            "total_value": total_value,
            "by_instrument": dict(sorted(instruments.items(), key=lambda x: x[1], reverse=True)),
            "by_action": dict(actions),
            "by_status": dict(statuses),
        }

    def analyze(self):
        """Print full order history analysis."""
        print("\n" + "=" * 70)
        print(" OKX ORDER HISTORY ANALYSIS")
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

        print(f"\n📈 BY INSTRUMENT")
        print("-" * 70)
        for inst, count in stats["by_instrument"].items():
            print(f"{inst}: {count} orders")

        print(f"\n💹 BY ACTION")
        print("-" * 70)
        for action, count in stats["by_action"].items():
            print(f"{action}: {count} orders")

        print(f"\n📋 BY STATUS")
        print("-" * 70)
        for status, count in stats["by_status"].items():
            print(f"{status}: {count} orders")

        print("\n" + "=" * 70 + "\n")


def main():
    """Test the order logger."""
    the_logger = OKXOrderLogger()
    the_logger.print_recent_orders(limit=10)
    the_logger.analyze()


if __name__ == "__main__":
    main()
