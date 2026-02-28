"""
IBKR Order Submission Module

Order submission for stocks, options, and futures via IBKR Client Portal Gateway API.
NOTE: This is for LIVE trading only. No crypto support - use OKX for crypto.

Broker Architecture:
- Alpaca: Paper trading ONLY (for testing all order types before live execution)
- IBKR: Live trading for stocks, options, futures (everything except crypto)
- OKX: Live crypto trading only (future implementation)

Documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ibkr_connection import IBKRConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IBKROrderLogger:
    """
    Logs IBKR orders to the shared trades DB table.
    Replaces the previous CSV-based logging with database-only persistence.
    """

    def _map_status(self, status_str: str) -> str:
        """Map IBKR status strings to TradeStatus enum values."""
        mapping = {
            "submitted": "SUBMITTED",
            "confirmed": "SUBMITTED",
            "presubmitted": "SUBMITTED",
            "filled": "FILLED",
            "partially_filled": "PARTIAL",
            "cancelled": "CANCELLED",
            "inactive": "CANCELLED",
        }
        return mapping.get(status_str.lower(), "SUBMITTED")

    def _map_order_type(self, order_type_str: str) -> str:
        """Map IBKR order type strings to OrderType enum values."""
        mapping = {
            "mkt": "MARKET",
            "lmt": "LIMIT",
            "stp": "STOP",
            "stop_limit": "STOP",
        }
        return mapping.get(order_type_str.lower(), "MARKET")

    def log_order(self, order: Dict[str, Any], asset_type: str = "Stock"):
        """
        Log an IBKR order to the trades table.

        Args:
            order: IBKR order dictionary
            asset_type: Type of asset (Stock, Option, Future, etc.)
        """
        try:
            from agents.common.database import get_db_session
            from agents.common.models import Trade
            from agents.common.enums import TradeSide, TradeStatus, OrderType, BrokerName

            order_id = str(order.get("orderId", order.get("order_id", "UNKNOWN")))
            symbol = order.get("ticker", order.get("symbol", "UNKNOWN"))
            side_str = order.get("side", "BUY").upper()
            order_type_str = order.get("orderType", "MKT")
            status_str = order.get("status", "submitted")

            qty = float(order.get("quantity", order.get("totalSize", 0)))
            limit_price = None
            px = order.get("price", order.get("limitPrice", ""))
            if px:
                try:
                    limit_price = float(px)
                except (ValueError, TypeError):
                    pass

            avg_px = order.get("avgPrice", order.get("filledPrice", ""))
            filled_price = float(avg_px) if avg_px else None

            filled_sz = order.get("filledQuantity", order.get("filled", ""))
            filled_qty = float(filled_sz) if filled_sz else None

            commission = float(order.get("commission", 0)) if order.get("commission") else 0.0

            slippage_pct = None
            if limit_price and filled_price and limit_price > 0:
                slippage_pct = ((filled_price - limit_price) / limit_price) * 100

            trade_side = TradeSide.BUY if "BUY" in side_str else TradeSide.SELL

            with get_db_session() as session:
                existing = session.query(Trade).filter_by(id=order_id).first()
                if existing:
                    existing.status = TradeStatus(self._map_status(status_str))
                    existing.filled_qty = filled_qty
                    existing.filled_price = filled_price
                    existing.slippage_pct = slippage_pct
                    existing.commission = commission
                    logger.info("Updated trade %s in DB", order_id)
                else:
                    trade = Trade(
                        id=order_id,
                        symbol=symbol,
                        side=trade_side,
                        qty=qty,
                        order_type=OrderType(self._map_order_type(order_type_str)),
                        limit_price=limit_price,
                        filled_qty=filled_qty,
                        filled_price=filled_price,
                        status=TradeStatus(self._map_status(status_str)),
                        broker=BrokerName.IBKR,
                        commission=commission,
                        slippage_pct=slippage_pct,
                        notes=f"asset_type={asset_type}",
                    )
                    session.add(trade)
                    logger.info("Logged trade %s to DB", order_id)

            print("  Logged to database (trades table)")

        except Exception as e:
            logger.warning("Failed to log order to DB: %s", e)
            # Don't raise - logging failure shouldn't stop trading


class IBKROrderManager:
    """
    Order management for IBKR Client Portal Gateway API

    Supports: Stocks, Options, Futures
    Does NOT support: Crypto (use OKX for crypto trading)
    """

    def __init__(self, connection: IBKRConnection):
        """
        Initialize IBKR Order Manager

        Args:
            connection: Authenticated IBKRConnection instance
        """
        self.conn = connection
        self.logger = IBKROrderLogger()
        self._account_id = None

    @property
    def account_id(self) -> str:
        """Get cached account ID"""
        if not self._account_id:
            self._account_id = self.conn.get_account_id()
        return self._account_id

    def _get_conid(self, symbol: str) -> Optional[int]:
        """
        Get contract ID for a symbol

        Args:
            symbol: Stock/contract symbol

        Returns:
            Contract ID (conid) or None
        """
        conid = self.conn.get_conid(symbol)
        if not conid:
            logger.error(f"Could not find conid for symbol: {symbol}")
        return conid

    def _confirm_order(self, reply_id: str) -> Optional[str]:
        """
        Handle IBKR order confirmation flow

        IBKR requires explicit confirmation for most orders.
        This posts to /iserver/reply/{replyId} with confirmation.

        Args:
            reply_id: Reply ID from initial order submission

        Returns:
            Order ID if successful, None otherwise
        """
        endpoint = f"/iserver/reply/{reply_id}"
        result = self.conn._request('POST', endpoint, data={'confirmed': True})

        if result:
            # Check if we got an order ID
            if isinstance(result, list) and len(result) > 0:
                order_id = result[0].get('order_id') or result[0].get('orderId')
                if order_id:
                    logger.info(f"Order confirmed: {order_id}")
                    return str(order_id)

            # Check for nested confirmation requirement
            if 'id' in result:
                # Recursive confirmation (sometimes needed)
                return self._confirm_order(result['id'])

        logger.error("Order confirmation failed")
        return None

    def submit_stock_order(
        self,
        symbol: str,
        qty: int,
        side: str = "BUY",
        order_type: str = "MKT",
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        tif: str = "DAY"
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a stock order

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'TSLA')
            qty: Number of shares
            side: 'BUY' or 'SELL'
            order_type: 'MKT', 'LMT', 'STP', 'STOP_LIMIT'
            price: Limit price (required for LMT and STOP_LIMIT)
            stop_price: Stop price (required for STP and STOP_LIMIT)
            tif: Time in force - 'DAY', 'GTC', 'IOC'

        Returns:
            Order result dictionary or None if failed
        """
        # Get contract ID
        conid = self._get_conid(symbol)
        if not conid:
            print(f"  Failed to find contract for {symbol}")
            return None

        # Build order payload
        order_data = {
            'acctId': self.account_id,
            'conid': conid,
            'secType': f'{conid}@STK',
            'orderType': order_type.upper(),
            'side': side.upper(),
            'quantity': qty,
            'tif': tif.upper()
        }

        # Add price for limit orders
        if order_type.upper() in ['LMT', 'STOP_LIMIT'] and price:
            order_data['price'] = price

        # Add stop price for stop orders
        if order_type.upper() in ['STP', 'STOP_LIMIT'] and stop_price:
            order_data['auxPrice'] = stop_price

        # Submit order
        print(f"\n{'='*60}")
        print(f" IBKR STOCK ORDER - LIVE")
        print(f"{'='*60}")
        print(f"  Symbol: {symbol}")
        print(f"  Side: {side.upper()}")
        print(f"  Quantity: {qty}")
        print(f"  Type: {order_type.upper()}")
        if price:
            print(f"  Limit Price: ${price:.2f}")
        if stop_price:
            print(f"  Stop Price: ${stop_price:.2f}")
        print(f"  Time in Force: {tif.upper()}")
        print(f"{'='*60}")

        endpoint = f"/iserver/account/{self.account_id}/orders"
        result = self.conn._request('POST', endpoint, data={'orders': [order_data]})

        if not result:
            print("  Order submission failed - no response")
            return None

        # Handle confirmation flow
        if isinstance(result, list) and len(result) > 0:
            first_result = result[0]

            # Check if order was accepted immediately
            if 'order_id' in first_result or 'orderId' in first_result:
                order_id = first_result.get('order_id') or first_result.get('orderId')
                print(f"  Order ID: {order_id}")
                print(f"  Status: Submitted")

                # Log to DB
                order_result = {
                    'orderId': order_id,
                    'ticker': symbol,
                    'side': side,
                    'orderType': order_type,
                    'quantity': qty,
                    'price': price,
                    'tif': tif,
                    'status': 'submitted'
                }
                self.logger.log_order(order_result, asset_type="Stock")

                print(f"{'='*60}\n")
                return order_result

            # Check if confirmation is required
            if 'id' in first_result:
                reply_id = first_result['id']
                print(f"  Confirmation required (reply_id: {reply_id})")

                order_id = self._confirm_order(reply_id)
                if order_id:
                    print(f"  Order ID: {order_id}")
                    print(f"  Status: Confirmed")

                    order_result = {
                        'orderId': order_id,
                        'ticker': symbol,
                        'side': side,
                        'orderType': order_type,
                        'quantity': qty,
                        'price': price,
                        'tif': tif,
                        'status': 'confirmed'
                    }
                    self.logger.log_order(order_result, asset_type="Stock")

                    print(f"{'='*60}\n")
                    return order_result
                else:
                    print("  Order confirmation failed")

            # Check for error message
            if 'error' in first_result:
                print(f"  Error: {first_result['error']}")

        print(f"{'='*60}\n")
        return None

    def submit_limit_order(
        self,
        symbol: str,
        qty: int,
        price: float,
        side: str = "BUY",
        tif: str = "DAY"
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a limit order (convenience method)

        Args:
            symbol: Stock symbol
            qty: Number of shares
            price: Limit price
            side: 'BUY' or 'SELL'
            tif: Time in force

        Returns:
            Order result or None
        """
        return self.submit_stock_order(
            symbol=symbol,
            qty=qty,
            side=side,
            order_type='LMT',
            price=price,
            tif=tif
        )

    def submit_market_order(
        self,
        symbol: str,
        qty: int,
        side: str = "BUY"
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a market order (convenience method)

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'BUY' or 'SELL'

        Returns:
            Order result or None
        """
        return self.submit_stock_order(
            symbol=symbol,
            qty=qty,
            side=side,
            order_type='MKT',
            tif='DAY'
        )

    def submit_stop_order(
        self,
        symbol: str,
        qty: int,
        stop_price: float,
        side: str = "SELL",
        tif: str = "GTC"
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a stop order (convenience method)

        Args:
            symbol: Stock symbol
            qty: Number of shares
            stop_price: Stop trigger price
            side: 'BUY' or 'SELL'
            tif: Time in force

        Returns:
            Order result or None
        """
        return self.submit_stock_order(
            symbol=symbol,
            qty=qty,
            side=side,
            order_type='STP',
            stop_price=stop_price,
            tif=tif
        )

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific order

        Args:
            order_id: IBKR order ID

        Returns:
            Order status dictionary or None
        """
        orders = self.conn.get_orders(status='all')
        for order in orders:
            if str(order.get('orderId')) == str(order_id):
                return order
        return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order

        Args:
            order_id: IBKR order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        endpoint = f"/iserver/account/{self.account_id}/order/{order_id}"
        result = self.conn._request('DELETE', endpoint)

        if result is not None:
            print(f"  Order {order_id} cancelled")
            logger.info(f"Order {order_id} cancelled")
            return True

        print(f"  Failed to cancel order {order_id}")
        return False

    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders

        Returns:
            True if successful, False otherwise
        """
        orders = self.conn.get_orders(status='open')

        if not orders:
            print("  No open orders to cancel")
            return True

        success = True
        for order in orders:
            order_id = order.get('orderId')
            if order_id:
                if not self.cancel_order(str(order_id)):
                    success = False

        return success

    def get_live_orders(self) -> List[Dict[str, Any]]:
        """Get all live/open orders"""
        return self.conn.get_orders(status='open')

    def print_order_status(self, order_id: str):
        """Print detailed status of an order"""
        order = self.get_order_status(order_id)

        if not order:
            print(f"Order {order_id} not found")
            return

        print(f"\n{'-'*60}")
        print(f" ORDER STATUS: {order_id}")
        print(f"{'-'*60}")
        print(f"  Symbol: {order.get('ticker', 'N/A')}")
        print(f"  Side: {order.get('side', 'N/A')}")
        print(f"  Type: {order.get('orderType', 'N/A')}")
        print(f"  Quantity: {order.get('totalSize', 'N/A')}")
        print(f"  Filled: {order.get('filledQuantity', 0)}")
        print(f"  Remaining: {order.get('remainingQuantity', 'N/A')}")
        print(f"  Status: {order.get('status', 'N/A')}")
        print(f"  Price: {order.get('price', 'N/A')}")
        if order.get('avgPrice'):
            print(f"  Avg Fill Price: ${order.get('avgPrice'):.2f}")
        print(f"{'-'*60}\n")


def main():
    """Example usage and test"""
    print("\n" + "="*60)
    print(" IBKR Order Manager - Example Usage")
    print("="*60)

    print("\nInitializing connection...")
    conn = IBKRConnection()

    if not conn.is_authenticated():
        print("\n  Not authenticated. Please:")
        print("  1. Start gateway: bin\\run.bat root\\conf.yaml")
        print("  2. Login at: https://localhost:5000")
        return

    order_mgr = IBKROrderManager(conn)

    print("\n" + "-"*60)
    print(" Available Commands:")
    print("-"*60)
    print("\n# Market Order")
    print("  order_mgr.submit_market_order('AAPL', 10, side='BUY')")
    print("\n# Limit Order")
    print("  order_mgr.submit_limit_order('AAPL', 10, price=150.00, side='BUY')")
    print("\n# Stop Order")
    print("  order_mgr.submit_stop_order('AAPL', 10, stop_price=140.00, side='SELL')")
    print("\n# Cancel Order")
    print("  order_mgr.cancel_order('order_id')")
    print("\n# Get Open Orders")
    print("  order_mgr.get_live_orders()")
    print("\n# Cancel All Orders")
    print("  order_mgr.cancel_all_orders()")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()