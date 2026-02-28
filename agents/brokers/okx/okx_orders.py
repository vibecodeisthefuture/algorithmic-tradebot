"""
OKX Order Submission Module

Unified module for submitting cryptocurrency orders via OKX's Trading API.

Documentation: https://www.okx.com/docs-v5/en/#order-book-trading-trade

WARNING: This is configured for PRODUCTION trading with real funds.
"""

import okx.Trade as Trade
import okx.Account as Account
from typing import Optional
from okx_order_logger import OKXOrderLogger
import uuid


class OKXOrderManager:
    """
    Order manager for OKX cryptocurrency trading

    WARNING: This executes REAL trades with REAL funds.
    """

    def __init__(
        self,
        trade_api: Trade.TradeAPI,
        account_api: Account.AccountAPI = None,
        csv_path: str = "okx_order_history.csv"
    ):
        """
        Initialize OKX Order Manager

        Args:
            trade_api: Authenticated TradeAPI instance
            account_api: Optional AccountAPI for position queries
            csv_path: Path to order history CSV file
        """
        self.trade_api = trade_api
        self.account_api = account_api
        self.logger = OKXOrderLogger(csv_path)

    def _generate_client_order_id(self) -> str:
        """Generate unique client order ID"""
        return f"bot_{uuid.uuid4().hex[:16]}"

    def submit_market_order(
        self,
        inst_id: str,
        side: str,
        sz: str,
        tdMode: str = "cash"
    ):
        """
        Submit a market order

        Args:
            inst_id: Instrument ID (e.g., 'BTC-USDT', 'ETH-USDT')
            side: 'buy' or 'sell'
            sz: Order size (quantity)
            tdMode: Trade mode - 'cash' for spot trading

        Returns:
            dict: Order response
        """
        print(f"\n🔴 PLACING MARKET ORDER (REAL FUNDS)")
        print(f"   {side.upper()} {sz} {inst_id}")

        client_order_id = self._generate_client_order_id()

        order_request = {
            'instId': inst_id,
            'tdMode': tdMode,
            'side': side,
            'ordType': 'market',
            'sz': sz,
            'clOrdId': client_order_id
        }

        result = self.trade_api.place_order(
            instId=inst_id,
            tdMode=tdMode,
            side=side,
            ordType='market',
            sz=sz,
            clOrdId=client_order_id
        )

        self._handle_order_response(result, order_request)
        return result

    def submit_limit_order(
        self,
        inst_id: str,
        side: str,
        sz: str,
        px: str,
        tdMode: str = "cash"
    ):
        """
        Submit a limit order

        Args:
            inst_id: Instrument ID (e.g., 'BTC-USDT', 'ETH-USDT')
            side: 'buy' or 'sell'
            sz: Order size (quantity)
            px: Limit price
            tdMode: Trade mode - 'cash' for spot trading

        Returns:
            dict: Order response
        """
        print(f"\n🔴 PLACING LIMIT ORDER (REAL FUNDS)")
        print(f"   {side.upper()} {sz} {inst_id} @ ${px}")

        client_order_id = self._generate_client_order_id()

        order_request = {
            'instId': inst_id,
            'tdMode': tdMode,
            'side': side,
            'ordType': 'limit',
            'sz': sz,
            'px': px,
            'clOrdId': client_order_id
        }

        result = self.trade_api.place_order(
            instId=inst_id,
            tdMode=tdMode,
            side=side,
            ordType='limit',
            sz=sz,
            px=px,
            clOrdId=client_order_id
        )

        self._handle_order_response(result, order_request)
        return result

    def _handle_order_response(self, result: dict, order_request: dict):
        """Handle order response and log"""
        if result.get('code') == '0':
            data = result.get('data', [{}])[0]
            if data.get('sCode') == '0':
                print(f"✓ Order placed successfully!")
                print(f"  Order ID: {data.get('ordId')}")
                print(f"  Client ID: {data.get('clOrdId')}")
                self.logger.log_order(data, order_request)
            else:
                print(f"✗ Order failed: {data.get('sMsg')}")
                self.logger.log_order(data, order_request)
        else:
            print(f"✗ API Error: {result.get('msg')}")

    def cancel_order(self, inst_id: str, ord_id: str = None, cl_ord_id: str = None):
        """
        Cancel an order

        Args:
            inst_id: Instrument ID
            ord_id: Order ID (use ordId OR clOrdId)
            cl_ord_id: Client order ID

        Returns:
            dict: Cancel response
        """
        print(f"\n⚠️ Cancelling order...")

        if ord_id:
            result = self.trade_api.cancel_order(instId=inst_id, ordId=ord_id)
        elif cl_ord_id:
            result = self.trade_api.cancel_order(instId=inst_id, clOrdId=cl_ord_id)
        else:
            print("Error: Must provide ordId or clOrdId")
            return None

        if result.get('code') == '0':
            print("✓ Order cancelled")
        else:
            print(f"✗ Cancel failed: {result.get('msg')}")

        return result

    def cancel_all_orders(self, inst_id: str = None):
        """
        Cancel all pending orders

        Args:
            inst_id: Optional instrument ID to filter by

        Returns:
            dict: Cancel response
        """
        print("\n⚠️ Cancelling all orders...")

        # Get open orders first
        open_orders = self.get_open_orders(inst_id=inst_id)

        if open_orders.get('code') != '0':
            print(f"Error getting orders: {open_orders.get('msg')}")
            return open_orders

        orders = open_orders.get('data', [])

        if not orders:
            print("No open orders to cancel")
            return open_orders

        cancelled = 0
        for order in orders:
            result = self.cancel_order(
                inst_id=order.get('instId'),
                ord_id=order.get('ordId')
            )
            if result and result.get('code') == '0':
                cancelled += 1

        print(f"✓ Cancelled {cancelled} orders")
        return {'cancelled': cancelled}

    def get_order_details(self, inst_id: str, ord_id: str = None, cl_ord_id: str = None):
        """
        Get order details

        Args:
            inst_id: Instrument ID
            ord_id: Order ID
            cl_ord_id: Client order ID

        Returns:
            dict: Order details
        """
        if ord_id:
            return self.trade_api.get_order(instId=inst_id, ordId=ord_id)
        elif cl_ord_id:
            return self.trade_api.get_order(instId=inst_id, clOrdId=cl_ord_id)
        else:
            print("Error: Must provide ordId or clOrdId")
            return None

    def get_open_orders(self, inst_id: str = None):
        """
        Get all open orders

        Args:
            inst_id: Optional instrument ID to filter

        Returns:
            dict: List of open orders
        """
        if inst_id:
            return self.trade_api.get_order_list(instId=inst_id)
        return self.trade_api.get_order_list()

    def get_order_history(self, inst_id: str = None, limit: str = "100"):
        """
        Get order history (last 7 days)

        Args:
            inst_id: Optional instrument ID to filter
            limit: Maximum number of orders to return

        Returns:
            dict: Order history
        """
        params = {'instType': 'SPOT', 'limit': limit}
        if inst_id:
            params['instId'] = inst_id
        return self.trade_api.get_orders_history(**params)

    def print_open_orders(self):
        """Print all open orders"""
        result = self.get_open_orders()

        if result.get('code') != '0':
            print(f"Error: {result.get('msg')}")
            return

        orders = result.get('data', [])

        print(f"\n{'-'*70}")
        print(" OKX OPEN ORDERS")
        print(f"{'-'*70}")
        print(f"\nOpen Orders: {len(orders)}")

        if orders:
            for order in orders:
                inst_id = order.get('instId', '')
                side = order.get('side', '')
                sz = order.get('sz', '')
                px = order.get('px', '')
                ord_type = order.get('ordType', '')
                state = order.get('state', '')

                print(f"\n{inst_id}:")
                print(f"  Side: {side.upper()}")
                print(f"  Type: {ord_type}")
                print(f"  Size: {sz}")
                if px:
                    print(f"  Price: ${px}")
                print(f"  Status: {state}")
                print(f"  Order ID: {order.get('ordId')}")
        else:
            print("  No open orders")
        print()


def main():
    """Example usage"""
    from okx_connection import OKXConnection

    print("OKX Order Manager - Example Usage")
    print("🔴 WARNING: PRODUCTION MODE - REAL FUNDS")
    print("=" * 50)

    try:
        # Connect to OKX
        conn = OKXConnection()
        conn.test_connection()

        # Initialize order manager
        order_mgr = OKXOrderManager(
            trade_api=conn.trade_api,
            account_api=conn.account_api
        )

        # Show open orders
        order_mgr.print_open_orders()

        print("\n" + "=" * 50)
        print("To place orders, use:")
        print("  order_mgr.submit_market_order('BTC-USDT', 'buy', '0.001')")
        print("  order_mgr.submit_limit_order('BTC-USDT', 'buy', '0.001', '40000')")
        print("=" * 50)

    except ValueError as e:
        print(f"\n{str(e)}")
        return False


if __name__ == "__main__":
    main()
