"""
Alpaca Order Submission Module

Unified module for submitting stock and cryptocurrency orders
via Alpaca's Trading API.

Documentation: https://docs.alpaca.markets/docs/getting-started-with-trading-api
"""

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopOrderRequest,
    StopLimitOrderRequest,
    TrailingStopOrderRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from typing import Optional
from order_logger import OrderLogger


class OrderManager:
    """
    Unified order manager for stocks and cryptocurrencies
    """
    
    def __init__(self, trading_client: TradingClient, csv_path: str = "order_history.csv"):
        """
        Initialize Order Manager
        
        Args:
            trading_client: Authenticated TradingClient instance
            csv_path: Path to order history CSV file
        """
        self.client = trading_client
        self.logger = OrderLogger(csv_path=csv_path)
    
    # =========================================================================
    # STOCK ORDERS
    # =========================================================================
    
    def submit_stock_order(
        self,
        symbol: str,
        qty: Optional[float] = None,
        notional: Optional[float] = None,
        side: str = "buy",
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None
    ):
        """
        Submit a stock order
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'TSLA')
            qty: Number of shares (use qty OR notional)
            notional: Dollar amount (use qty OR notional)
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'bracket'
            time_in_force: 'day', 'gtc', 'ioc', 'fok'
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            take_profit: Take profit price (for bracket orders)
            stop_loss: Stop loss price (for bracket orders)
            
        Returns:
            Order object
        """
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        
        tif_map = {
            'day': TimeInForce.DAY,
            'gtc': TimeInForce.GTC,
            'ioc': TimeInForce.IOC,
            'fok': TimeInForce.FOK
        }
        tif = tif_map.get(time_in_force.lower(), TimeInForce.DAY)
        
        # Create order based on type
        if order_type.lower() == "bracket":
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit={"limit_price": take_profit} if take_profit else None,
                stop_loss={"stop_price": stop_loss} if stop_loss else None
            )
        elif order_type.lower() == "limit":
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                limit_price=limit_price,
                side=order_side,
                time_in_force=tif
            )
        elif order_type.lower() == "stop":
            order_data = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                stop_price=stop_price,
                side=order_side,
                time_in_force=tif
            )
        else:  # market order
            if qty is not None:
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif
                )
            elif notional is not None:
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    notional=notional,
                    side=order_side,
                    time_in_force=tif
                )
            else:
                raise ValueError("Must specify either qty or notional")
        
        # Submit order
        order = self.client.submit_order(order_data=order_data)
        
        print(f"✓ Stock Order Submitted:")
        print(f"  Symbol: {order.symbol}")
        print(f"  Side: {order.side}")
        print(f"  Type: {order_type}")
        if order.qty:
            print(f"  Qty: {order.qty}")
        if order.notional:
            print(f"  Notional: ${order.notional}")
        if limit_price:
            print(f"  Limit Price: ${limit_price}")
        if stop_price:
            print(f"  Stop Price: ${stop_price}")
        print(f"  Order ID: {order.id}")
        print(f"  Status: {order.status}")
        
        # Log order to CSV
        self.logger.log_order(order, asset_type="Stock")
        
        return order
    
    # =========================================================================
    # CRYPTO ORDERS
    # =========================================================================
    
    def submit_crypto_order(
        self,
        symbol: str,
        qty: Optional[float] = None,
        notional: Optional[float] = None,
        side: str = "buy",
        limit_price: Optional[float] = None
    ):
        """
        Submit a cryptocurrency order
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC/USD', 'ETH/USD')
            qty: Amount of crypto (use qty OR notional)
            notional: Dollar amount (use qty OR notional)
            side: 'buy' or 'sell'
            limit_price: Limit price (optional, makes it a limit order)
            
        Returns:
            Order object
        """
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        
        # Crypto uses GTC since markets are 24/7
        if limit_price is not None:
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                limit_price=limit_price,
                side=order_side,
                time_in_force=TimeInForce.GTC
            )
        elif qty is not None:
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.GTC
            )
        elif notional is not None:
            order_data = MarketOrderRequest(
                symbol=symbol,
                notional=notional,
                side=order_side,
                time_in_force=TimeInForce.GTC
            )
        else:
            raise ValueError("Must specify either qty or notional")
        
        order = self.client.submit_order(order_data=order_data)
        
        order_type = "Limit" if limit_price else "Market"
        print(f"✓ Crypto {order_type} Order Submitted:")
        print(f"  Symbol: {order.symbol}")
        print(f"  Side: {order.side}")
        if order.qty:
            print(f"  Qty: {order.qty}")
        if order.notional:
            print(f"  Notional: ${order.notional}")
        if limit_price:
            print(f"  Limit Price: ${limit_price}")
        print(f"  Order ID: {order.id}")
        print(f"  Status: {order.status}")
        
        # Log order to CSV
        self.logger.log_order(order, asset_type="Crypto")
        
        return order
    
    def sell_all_crypto(self, symbol: str):
        """
        Sell all holdings of a specific cryptocurrency
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC/USD')
            
        Returns:
            Order object or None if no position
        """
        try:
            position = self.client.get_open_position(symbol)
            
            if position:
                qty = float(position.qty)
                return self.submit_crypto_order(
                    symbol=symbol,
                    qty=qty,
                    side="sell"
                )
            else:
                print(f"No position found for {symbol}")
                return None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    def cancel_order(self, order_id: str):
        """Cancel a specific order"""
        self.client.cancel_order_by_id(order_id)
        print(f"✓ Order {order_id} cancelled")
    
    def cancel_all_orders(self):
        """Cancel all open orders"""
        self.client.cancel_orders()
        print("✓ All orders cancelled")


def main():
    """Example usage"""
    from alpaca_connection import AlpacaConnection

    conn = AlpacaConnection()
    order_mgr = OrderManager(conn.trading_client)
    
    print("\nOrder Manager Examples:")
    print("=" * 50)
    print("\nStock Orders:")
    print("  order_mgr.submit_stock_order('AAPL', qty=10, side='buy')")
    print("  order_mgr.submit_stock_order('TSLA', notional=500, side='buy')")
    print("\nCrypto Orders:")
    print("  order_mgr.submit_crypto_order('BTC/USD', notional=100, side='buy')")
    print("  order_mgr.submit_crypto_order('ETH/USD', qty=0.5, side='buy')")
    print("\nOrder Management:")
    print("  order_mgr.cancel_order(order_id='...')")
    print("  order_mgr.cancel_all_orders()")


if __name__ == "__main__":
    main()
