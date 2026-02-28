"""
Alpaca Trading API Connection Module

This module handles the connection and authentication to Alpaca's Paper Trading API.
NOTE: This project is configured for paper trading only.

Documentation: https://docs.alpaca.markets/docs/getting-started-with-trading-api
"""

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
import os
from typing import Optional


class AlpacaConnection:
    """
    Manages connection to Alpaca Paper Trading API

    NOTE: This project is configured for paper trading only.

    Attributes:
        api_key (str): Your Alpaca API key
        api_secret (str): Your Alpaca API secret
        trading_client (TradingClient): Client for trading operations
        stock_data_client (StockHistoricalDataClient): Client for stock market data
        crypto_data_client (CryptoHistoricalDataClient): Client for crypto market data
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Alpaca paper trading connection

        Args:
            api_key: Alpaca API key (if None, will use environment variable)
            api_secret: Alpaca API secret (if None, will use environment variable)

        Environment Variables:
            ALPACA_API_KEY, ALPACA_API_SECRET
        """
        # Paper trading only
        self.paper = True

        # Get credentials from params or environment
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            self.api_key = os.getenv('ALPACA_API_KEY')
            self.api_secret = os.getenv('ALPACA_API_SECRET')

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "API credentials not provided for paper trading. "
                "Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables, "
                "or pass credentials directly."
            )
        
        # Initialize trading client
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.api_secret,
            paper=self.paper
        )
        
        # Initialize market data clients
        # Stock data requires API keys
        self.stock_data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.api_secret
        )
        
        # Crypto data does NOT require API keys
        self.crypto_data_client = CryptoHistoricalDataClient()
    
    def get_account(self):
        """
        Get account information
        
        Returns:
            Account object with account details (balance, buying power, etc.)
        """
        return self.trading_client.get_account()
    
    def get_positions(self):
        """
        Get all current positions
        
        Returns:
            List of Position objects
        """
        return self.trading_client.get_all_positions()
    
    def get_orders(self, status: Optional[str] = None):
        """
        Get orders
        
        Args:
            status: Filter by order status ('open', 'closed', 'all'). Default is 'open'
            
        Returns:
            List of Order objects
        """
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        
        if status == 'all':
            request = GetOrdersRequest(status=QueryOrderStatus.ALL)
        elif status == 'closed':
            request = GetOrdersRequest(status=QueryOrderStatus.CLOSED)
        else:  # default to open
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        
        return self.trading_client.get_orders(filter=request)
    
    def test_connection(self):
        """
        Test the API connection and print account information
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            account = self.get_account()
            print("✓ Connection successful!")
            print(f"\n{'='*50}")
            print("Account Information (PAPER Trading)")
            print(f"{'='*50}")
            print(f"Account Number: {account.account_number}")
            print(f"Status: {account.status}")
            print(f"Cash: ${float(account.cash):,.2f}")
            print(f"Buying Power: ${float(account.buying_power):,.2f}")
            print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
            print(f"Equity: ${float(account.equity):,.2f}")
            print(f"Pattern Day Trader: {account.pattern_day_trader}")
            print(f"Trading Blocked: {account.trading_blocked}")
            print(f"Account Blocked: {account.account_blocked}")
            print(f"{'='*50}\n")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {str(e)}")
            return False
    
    def print_account_summary(self):
        """Print account balance summary"""
        account = self.get_account()
        print(f"\n{'='*70}")
        print(" ACCOUNT SUMMARY")
        print(f"{'='*70}")
        print(f"  Cash: ${float(account.cash):,.2f}")
        print(f"  Portfolio Value: ${float(account.portfolio_value):,.2f}")
        print(f"  Equity: ${float(account.equity):,.2f}")
        print(f"  Buying Power: ${float(account.buying_power):,.2f}")
        print(f"{'='*70}\n")
    
    def print_positions(self):
        """Print all current positions with P&L"""
        positions = self.get_positions()
        print(f"\n{'-'*70}")
        print(" POSITIONS")
        print(f"{'-'*70}")
        print(f"\nTotal Positions: {len(positions)}")
        
        if positions:
            for pos in positions:
                print(f"\n{pos.symbol}:")
                print(f"  Quantity: {pos.qty}")
                print(f"  Entry Price: ${float(pos.avg_entry_price):,.2f}")
                print(f"  Current Price: ${float(pos.current_price):,.2f}")
                print(f"  Market Value: ${float(pos.market_value):,.2f}")
                pnl = float(pos.unrealized_pl)
                pnl_pct = float(pos.unrealized_plpc) * 100
                pnl_symbol = "+" if pnl >= 0 else ""
                print(f"  Unrealized P&L: {pnl_symbol}${pnl:,.2f} ({pnl_symbol}{pnl_pct:.2f}%)")
        else:
            print("  No positions")
        print()
    
    def print_open_orders(self):
        """Print all open orders"""
        orders = self.get_orders(status='open')
        print(f"\n{'-'*70}")
        print(" OPEN ORDERS")
        print(f"{'-'*70}")
        print(f"\nOpen Orders: {len(orders)}")
        
        if orders:
            for order in orders:
                print(f"\n{order.symbol}:")
                print(f"  Side: {order.side}")
                print(f"  Type: {order.type}")
                print(f"  Qty: {order.qty}")
                print(f"  Status: {order.status}")
                print(f"  Order ID: {order.id}")
        else:
            print("  No open orders")
        print()
    
    def print_full_status(self):
        """Print complete account status: balance, positions, and orders"""
        self.print_account_summary()
        self.print_positions()
        self.print_open_orders()


def main():
    """
    Test the Alpaca connection
    """
    print("Alpaca Trading API Connection Test")
    print("="*50)
    
    # Try to connect using environment variables
    try:
        conn = AlpacaConnection()
        conn.test_connection()
    except ValueError as e:
        print(f"\n{str(e)}")
        print("\nPlease provide your API credentials:")
        print("1. Set environment variables ALPACA_API_KEY and ALPACA_API_SECRET, or")
        print("2. Pass them directly when creating AlpacaConnection object")
        return False


if __name__ == "__main__":
    main()
