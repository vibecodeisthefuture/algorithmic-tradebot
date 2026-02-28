"""
IBKR Client Portal Gateway API Connection Module

This module handles the connection to Interactive Brokers Client Portal Gateway API.
NOTE: This is for LIVE trading of stocks, options, and futures (NOT crypto).

Broker Architecture:
- Alpaca: Paper trading ONLY (for testing all order types before live execution)
- IBKR: Live trading for stocks, options, futures (everything except crypto)
- OKX: Live crypto trading only (future implementation)

Requirements:
- IBKR Client Portal Gateway running on localhost:5000
- Manual browser authentication at https://localhost:5000
- Python packages: requests, urllib3

Documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
"""

import requests
import urllib3
import logging
import time
from typing import Optional, Dict, List, Any

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IBKRConnection:
    """
    Manages connection to IBKR Client Portal Gateway API

    NOTE: This is for LIVE trading only.
    Requires manual browser authentication before API operations.

    Attributes:
        base_url (str): Gateway API base URL
        session (requests.Session): HTTP session with SSL verification disabled
        account_id (str): Cached account ID after first retrieval
    """

    BASE_URL = "https://localhost:5000/v1/api"
    TICKLE_INTERVAL = 180  # 3 minutes - sessions timeout at 10-15 min

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize IBKR Gateway connection

        Args:
            base_url: Gateway URL (default: https://localhost:5000/v1/api)

        Note:
            Gateway must be running and authenticated via browser before use.
        """
        self.base_url = base_url or self.BASE_URL
        self._account_id = None

        # Create session with SSL verification disabled (self-signed cert)
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        logger.info(f"IBKR Connection initialized: {self.base_url}")

    def _request(self, method: str, endpoint: str, data: Dict = None,
                 params: Dict = None, retries: int = 3) -> Optional[Dict]:
        """
        Make HTTP request to gateway with retry logic

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., '/tickle')
            data: JSON body for POST requests
            params: Query parameters
            retries: Number of retry attempts

        Returns:
            JSON response or None if failed
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, params=params, timeout=10)
                elif method == 'POST':
                    response = self.session.post(url, json=data, timeout=10)
                elif method == 'DELETE':
                    response = self.session.delete(url, timeout=10)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Check for empty response
                if response.status_code == 200:
                    if response.text:
                        return response.json()
                    return {}
                elif response.status_code == 401:
                    logger.error("Authentication required - please login via browser")
                    return None
                else:
                    logger.warning(f"Request failed: {response.status_code} - {response.text}")

            except requests.exceptions.ConnectionError:
                logger.error(f"Connection failed (attempt {attempt + 1}/{retries}) - is gateway running?")
                if attempt < retries - 1:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt < retries - 1:
                    time.sleep(1)

        return None

    def check_auth_status(self) -> Dict[str, Any]:
        """
        Check authentication status with gateway

        Returns:
            Dict with 'authenticated', 'connected', 'competing' flags
        """
        result = self._request('POST', '/iserver/auth/status')
        if result:
            logger.info(f"Auth status: authenticated={result.get('authenticated', False)}")
            return result
        return {'authenticated': False, 'connected': False}

    def is_authenticated(self) -> bool:
        """
        Check if session is authenticated

        Returns:
            True if authenticated, False otherwise
        """
        status = self.check_auth_status()
        return status.get('authenticated', False)

    def tickle_session(self) -> bool:
        """
        Keep session alive by calling /tickle endpoint

        Returns:
            True if successful, False otherwise
        """
        result = self._request('POST', '/tickle')
        if result is not None:
            logger.debug("Session tickled successfully")
            return True
        logger.warning("Session tickle failed")
        return False

    def reauthenticate(self) -> bool:
        """
        Attempt to reauthenticate the session

        Returns:
            True if successful, False otherwise
        """
        result = self._request('POST', '/iserver/reauthenticate')
        if result:
            logger.info("Reauthentication initiated")
            return True
        return False

    def get_account_id(self) -> Optional[str]:
        """
        Get the primary account ID

        Returns:
            Account ID string or None if failed
        """
        if self._account_id:
            return self._account_id

        result = self._request('GET', '/portfolio/accounts')
        if result and isinstance(result, list) and len(result) > 0:
            self._account_id = result[0].get('id') or result[0].get('accountId')
            logger.info(f"Account ID retrieved: {self._account_id}")
            return self._account_id

        logger.error("Failed to get account ID")
        return None

    def get_account(self) -> Optional[Dict[str, Any]]:
        """
        Get account summary information

        Returns:
            Dict with account details (cash, equity, buying power, etc.)
        """
        account_id = self.get_account_id()
        if not account_id:
            return None

        # Get account summary
        result = self._request('GET', f'/portfolio/{account_id}/summary')
        if result:
            return result

        # Fallback to ledger
        result = self._request('GET', f'/portfolio/{account_id}/ledger')
        return result

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all current positions

        Returns:
            List of position dictionaries with standardized format
        """
        account_id = self.get_account_id()
        if not account_id:
            return []

        result = self._request('GET', f'/portfolio/{account_id}/positions/0')
        if not result:
            return []

        # Normalize position format to match Alpaca structure
        positions = []
        for pos in result:
            positions.append({
                'symbol': pos.get('contractDesc', pos.get('ticker', 'UNKNOWN')),
                'conid': pos.get('conid'),
                'qty': float(pos.get('position', 0)),
                'market_value': float(pos.get('mktValue', 0)),
                'cost_basis': float(pos.get('avgCost', 0)) * float(pos.get('position', 0)),
                'avg_entry_price': float(pos.get('avgCost', 0)),
                'unrealized_pl': float(pos.get('unrealizedPnl', 0)),
                'realized_pl': float(pos.get('realizedPnl', 0)),
                'side': 'long' if float(pos.get('position', 0)) > 0 else 'short',
                'asset_type': pos.get('assetClass', 'STK')
            })

        return positions

    def get_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """
        Get orders

        Args:
            status: Filter by 'open', 'filled', or 'all'

        Returns:
            List of order dictionaries
        """
        result = self._request('GET', '/iserver/account/orders')
        if not result:
            return []

        orders = result.get('orders', result) if isinstance(result, dict) else result

        if status == 'all':
            return orders
        elif status == 'filled':
            return [o for o in orders if o.get('status', '').lower() == 'filled']
        else:  # open
            return [o for o in orders if o.get('status', '').lower() in
                    ['presubmitted', 'submitted', 'pendingsubmit']]

    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Get recent trade executions

        Returns:
            List of executed trades
        """
        result = self._request('GET', '/iserver/account/trades')
        return result if result else []

    def search_contract(self, symbol: str, sec_type: str = 'STK') -> Optional[Dict]:
        """
        Search for contract to get conid

        Args:
            symbol: Stock/contract symbol (e.g., 'AAPL')
            sec_type: Security type ('STK', 'OPT', 'FUT')

        Returns:
            Contract info with conid or None
        """
        result = self._request('GET', '/iserver/secdef/search',
                               params={'symbol': symbol})
        if result and isinstance(result, list) and len(result) > 0:
            # Find matching security type
            for contract in result:
                if contract.get('secType', '').upper() == sec_type.upper():
                    return contract
            # Return first match if no exact type match
            return result[0]
        return None

    def get_conid(self, symbol: str) -> Optional[int]:
        """
        Get contract ID for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Contract ID (conid) or None
        """
        contract = self.search_contract(symbol)
        if contract:
            return contract.get('conid')
        return None

    def test_connection(self) -> bool:
        """
        Test the gateway connection and print account information

        Returns:
            bool: True if connection successful, False otherwise
        """
        print("\n" + "="*60)
        print(" IBKR CLIENT PORTAL GATEWAY CONNECTION TEST")
        print("="*60)

        # Test gateway connectivity
        print("\n[1] Testing gateway connectivity...")
        try:
            response = self.session.get(f"{self.base_url}/tickle", timeout=5)
            if response.status_code == 200:
                print("    ✓ Gateway is reachable")
            else:
                print(f"    ✗ Gateway returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("    ✗ Cannot connect to gateway - is it running?")
            print("      Start gateway: bin\\run.bat root\\conf.yaml")
            return False

        # Test authentication
        print("\n[2] Checking authentication status...")
        auth_status = self.check_auth_status()
        if auth_status.get('authenticated'):
            print("    ✓ Session is authenticated")
        else:
            print("    ✗ Not authenticated - please login via browser")
            print("      Open: https://localhost:5000")
            return False

        # Get account info
        print("\n[3] Retrieving account information...")
        account_id = self.get_account_id()
        if not account_id:
            print("    ✗ Failed to get account ID")
            return False
        print(f"    ✓ Account ID: {account_id}")

        # Get account summary
        account = self.get_account()
        if account:
            print("\n" + "-"*60)
            print(" ACCOUNT SUMMARY (LIVE Trading)")
            print("-"*60)

            # Extract values from nested structure
            if 'BASE' in account:
                base = account['BASE']
                print(f"  Net Liquidation: ${float(base.get('netliquidation', {}).get('amount', 0)):,.2f}")
                print(f"  Total Cash: ${float(base.get('totalcashvalue', {}).get('amount', 0)):,.2f}")
                print(f"  Buying Power: ${float(base.get('buyingpower', {}).get('amount', 0)):,.2f}")
            else:
                # Flat structure
                print(f"  Net Liquidation: ${float(account.get('netliquidation', 0)):,.2f}")
                print(f"  Total Cash: ${float(account.get('totalcashvalue', 0)):,.2f}")

        # Get positions
        positions = self.get_positions()
        print(f"\n  Positions: {len(positions)}")

        # Get open orders
        orders = self.get_orders(status='open')
        print(f"  Open Orders: {len(orders)}")

        print("\n" + "="*60)
        print(" ✓ CONNECTION SUCCESSFUL - LIVE TRADING ENABLED")
        print("="*60 + "\n")

        return True

    def print_account_summary(self):
        """Print account balance summary"""
        account = self.get_account()
        if not account:
            print("Failed to retrieve account information")
            return

        print(f"\n{'='*70}")
        print(" IBKR ACCOUNT SUMMARY (LIVE)")
        print(f"{'='*70}")

        if 'BASE' in account:
            base = account['BASE']
            print(f"  Net Liquidation: ${float(base.get('netliquidation', {}).get('amount', 0)):,.2f}")
            print(f"  Total Cash: ${float(base.get('totalcashvalue', {}).get('amount', 0)):,.2f}")
            print(f"  Buying Power: ${float(base.get('buyingpower', {}).get('amount', 0)):,.2f}")
            print(f"  Gross Position Value: ${float(base.get('grosspositionvalue', {}).get('amount', 0)):,.2f}")
        else:
            for key, value in account.items():
                if isinstance(value, (int, float)):
                    print(f"  {key}: ${float(value):,.2f}")

        print(f"{'='*70}\n")

    def print_positions(self):
        """Print all current positions with P&L"""
        positions = self.get_positions()

        print(f"\n{'-'*70}")
        print(" IBKR POSITIONS (LIVE)")
        print(f"{'-'*70}")
        print(f"\nTotal Positions: {len(positions)}")

        if positions:
            for pos in positions:
                print(f"\n{pos['symbol']}:")
                print(f"  Quantity: {pos['qty']}")
                print(f"  Avg Entry Price: ${pos['avg_entry_price']:,.2f}")
                print(f"  Market Value: ${pos['market_value']:,.2f}")
                pnl = pos['unrealized_pl']
                pnl_symbol = "+" if pnl >= 0 else ""
                print(f"  Unrealized P&L: {pnl_symbol}${pnl:,.2f}")
                print(f"  Side: {pos['side']}")
        else:
            print("  No positions")
        print()

    def print_open_orders(self):
        """Print all open orders"""
        orders = self.get_orders(status='open')

        print(f"\n{'-'*70}")
        print(" IBKR OPEN ORDERS (LIVE)")
        print(f"{'-'*70}")
        print(f"\nOpen Orders: {len(orders)}")

        if orders:
            for order in orders:
                print(f"\n{order.get('ticker', order.get('symbol', 'UNKNOWN'))}:")
                print(f"  Side: {order.get('side', 'N/A')}")
                print(f"  Type: {order.get('orderType', 'N/A')}")
                print(f"  Qty: {order.get('remainingQuantity', order.get('totalSize', 'N/A'))}")
                print(f"  Status: {order.get('status', 'N/A')}")
                print(f"  Order ID: {order.get('orderId', 'N/A')}")
        else:
            print("  No open orders")
        print()

    def print_full_status(self):
        """Print complete account status: balance, positions, and orders"""
        self.print_account_summary()
        self.print_positions()
        self.print_open_orders()


def main():
    """Test the IBKR connection"""
    print("\n" + "="*60)
    print(" IBKR Client Portal API - Connection Test")
    print("="*60)
    print("\nNOTE: Gateway must be running and authenticated via browser.")
    print("Start gateway: bin\\run.bat root\\conf.yaml")
    print("Login at: https://localhost:5000\n")

    conn = IBKRConnection()
    success = conn.test_connection()

    if success:
        print("\nFull status:")
        conn.print_full_status()
    else:
        print("\nConnection test failed. Please ensure:")
        print("1. Gateway is running (bin\\run.bat root\\conf.yaml)")
        print("2. You have logged in via browser at https://localhost:5000")
        print("3. Two-factor authentication is complete")


if __name__ == "__main__":
    main()