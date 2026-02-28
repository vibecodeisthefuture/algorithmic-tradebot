"""
Broker Interface - Unified Abstraction Layer

This module provides a unified interface for interacting with different brokers.
It allows the PortfolioTracker and other components to work seamlessly with
any supported broker without knowing the implementation details.

Broker Architecture:
- Alpaca: Paper trading ONLY (for testing all order types before live execution)
- IBKR: Live trading for stocks, options, futures (everything except crypto)
- OKX: Live crypto trading only (US endpoint: us.okx.com)

Usage:
    # Get the paper trading broker (Alpaca)
    paper_broker = BrokerFactory.get_paper_broker()

    # Get the live trading broker (IBKR)
    live_broker = BrokerFactory.get_live_broker()

    # Use unified interface
    value = broker.get_portfolio_value()
    positions = broker.get_positions()
"""

import sys
import os
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BrokerType(Enum):
    """Supported broker types"""
    ALPACA = "ALPACA"  # Paper trading only
    IBKR = "IBKR"      # Live trading (stocks, options, futures)
    OKX = "OKX"        # Live crypto trading (US endpoint)


class TradingMode(Enum):
    """Trading mode"""
    PAPER = "PAPER"    # Testing/simulation
    LIVE = "LIVE"      # Real money


@dataclass
class NormalizedPosition:
    """Standardized position format across all brokers"""
    symbol: str
    qty: float
    market_value: float
    cost_basis: float
    avg_entry_price: float
    unrealized_pl: float
    realized_pl: float = 0.0
    side: str = "long"  # long or short
    asset_type: str = "STK"  # STK, OPT, FUT, CRYPTO


@dataclass
class NormalizedAccount:
    """Standardized account format across all brokers"""
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    broker: str
    mode: str  # PAPER or LIVE


class BrokerInterface(ABC):
    """
    Abstract interface for broker implementations.

    All broker implementations must provide these methods to ensure
    consistent behavior across the system.
    """

    @property
    @abstractmethod
    def broker_type(self) -> BrokerType:
        """Return the broker type"""
        pass

    @property
    @abstractmethod
    def trading_mode(self) -> TradingMode:
        """Return PAPER or LIVE trading mode"""
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if broker session is active and authenticated"""
        pass

    @abstractmethod
    def get_portfolio_value(self) -> float:
        """Get total portfolio equity value"""
        pass

    @abstractmethod
    def get_positions(self) -> List[NormalizedPosition]:
        """Get all positions in normalized format"""
        pass

    @abstractmethod
    def get_account(self) -> NormalizedAccount:
        """Get account summary in normalized format"""
        pass

    @abstractmethod
    def get_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """Get orders filtered by status"""
        pass

    def get_position_value(self, symbol: str) -> float:
        """Get market value of a specific position"""
        for pos in self.get_positions():
            if pos.symbol.upper() == symbol.upper():
                return pos.market_value
        return 0.0


class AlpacaBroker(BrokerInterface):
    """
    Alpaca broker implementation - PAPER TRADING ONLY

    Used for testing all order types before live execution.
    """

    def __init__(self):
        """Initialize Alpaca paper trading connection"""
        # Add Alpaca path
        alpaca_path = os.path.join(os.path.dirname(__file__), 'AlpacaAPI')
        if alpaca_path not in sys.path:
            sys.path.insert(0, alpaca_path)

        try:
            from alpaca_connection import AlpacaConnection
            self._conn = AlpacaConnection()
            logger.info("Alpaca broker initialized (PAPER mode)")
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca: {e}")
            raise

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.ALPACA

    @property
    def trading_mode(self) -> TradingMode:
        return TradingMode.PAPER

    def is_authenticated(self) -> bool:
        """Alpaca is always authenticated if credentials are valid"""
        try:
            self._conn.get_account()
            return True
        except Exception:
            return False

    def get_portfolio_value(self) -> float:
        """Get total portfolio equity"""
        try:
            account = self._conn.get_account()
            return float(account.equity)
        except Exception as e:
            logger.error(f"Failed to get Alpaca portfolio value: {e}")
            return 0.0

    def get_positions(self) -> List[NormalizedPosition]:
        """Get all positions in normalized format"""
        positions = []
        try:
            raw_positions = self._conn.get_positions()
            for pos in raw_positions:
                positions.append(NormalizedPosition(
                    symbol=pos.symbol,
                    qty=float(pos.qty),
                    market_value=float(pos.market_value),
                    cost_basis=float(pos.cost_basis),
                    avg_entry_price=float(pos.avg_entry_price),
                    unrealized_pl=float(pos.unrealized_pl),
                    side='long' if float(pos.qty) > 0 else 'short',
                    asset_type='STK' if '/' not in pos.symbol else 'CRYPTO'
                ))
        except Exception as e:
            logger.error(f"Failed to get Alpaca positions: {e}")
        return positions

    def get_account(self) -> NormalizedAccount:
        """Get account summary in normalized format"""
        try:
            acc = self._conn.get_account()
            return NormalizedAccount(
                equity=float(acc.equity),
                cash=float(acc.cash),
                buying_power=float(acc.buying_power),
                portfolio_value=float(acc.portfolio_value),
                broker="ALPACA",
                mode="PAPER"
            )
        except Exception as e:
            logger.error(f"Failed to get Alpaca account: {e}")
            return NormalizedAccount(
                equity=0.0, cash=0.0, buying_power=0.0,
                portfolio_value=0.0, broker="ALPACA", mode="PAPER"
            )

    def get_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """Get orders filtered by status"""
        try:
            orders = self._conn.get_orders(status=status)
            return [
                {
                    'order_id': str(o.id),
                    'symbol': o.symbol,
                    'side': str(o.side).split('.')[-1].lower(),
                    'qty': float(o.qty) if o.qty else 0,
                    'order_type': str(o.type).split('.')[-1].lower(),
                    'status': str(o.status).split('.')[-1].lower(),
                    'broker': 'ALPACA'
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Failed to get Alpaca orders: {e}")
            return []


class IBKRBroker(BrokerInterface):
    """
    IBKR broker implementation - LIVE TRADING

    Used for live trading of stocks, options, and futures.
    Does NOT support crypto - use OKX for crypto.
    """

    def __init__(self):
        """Initialize IBKR live trading connection"""
        # Add IBKR path
        ibkr_path = os.path.join(os.path.dirname(__file__), 'IBKR Client Portal API')
        if ibkr_path not in sys.path:
            sys.path.insert(0, ibkr_path)

        try:
            from ibkr_connection import IBKRConnection
            self._conn = IBKRConnection()
            logger.info("IBKR broker initialized (LIVE mode)")
        except Exception as e:
            logger.error(f"Failed to initialize IBKR: {e}")
            raise

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.IBKR

    @property
    def trading_mode(self) -> TradingMode:
        return TradingMode.LIVE

    def is_authenticated(self) -> bool:
        """Check if IBKR session is authenticated"""
        try:
            return self._conn.is_authenticated()
        except Exception:
            return False

    def get_portfolio_value(self) -> float:
        """Get total portfolio equity"""
        try:
            account = self._conn.get_account()
            if not account:
                return 0.0

            # Handle nested structure
            if 'BASE' in account:
                base = account['BASE']
                return float(base.get('netliquidation', {}).get('amount', 0))
            else:
                return float(account.get('netliquidation', 0))
        except Exception as e:
            logger.error(f"Failed to get IBKR portfolio value: {e}")
            return 0.0

    def get_positions(self) -> List[NormalizedPosition]:
        """Get all positions in normalized format"""
        positions = []
        try:
            raw_positions = self._conn.get_positions()
            for pos in raw_positions:
                positions.append(NormalizedPosition(
                    symbol=pos.get('symbol', 'UNKNOWN'),
                    qty=float(pos.get('qty', 0)),
                    market_value=float(pos.get('market_value', 0)),
                    cost_basis=float(pos.get('cost_basis', 0)),
                    avg_entry_price=float(pos.get('avg_entry_price', 0)),
                    unrealized_pl=float(pos.get('unrealized_pl', 0)),
                    realized_pl=float(pos.get('realized_pl', 0)),
                    side=pos.get('side', 'long'),
                    asset_type=pos.get('asset_type', 'STK')
                ))
        except Exception as e:
            logger.error(f"Failed to get IBKR positions: {e}")
        return positions

    def get_account(self) -> NormalizedAccount:
        """Get account summary in normalized format"""
        try:
            acc = self._conn.get_account()
            if not acc:
                raise ValueError("No account data")

            if 'BASE' in acc:
                base = acc['BASE']
                return NormalizedAccount(
                    equity=float(base.get('netliquidation', {}).get('amount', 0)),
                    cash=float(base.get('totalcashvalue', {}).get('amount', 0)),
                    buying_power=float(base.get('buyingpower', {}).get('amount', 0)),
                    portfolio_value=float(base.get('grosspositionvalue', {}).get('amount', 0)),
                    broker="IBKR",
                    mode="LIVE"
                )
            else:
                return NormalizedAccount(
                    equity=float(acc.get('netliquidation', 0)),
                    cash=float(acc.get('totalcashvalue', 0)),
                    buying_power=float(acc.get('buyingpower', 0)),
                    portfolio_value=float(acc.get('grosspositionvalue', 0)),
                    broker="IBKR",
                    mode="LIVE"
                )
        except Exception as e:
            logger.error(f"Failed to get IBKR account: {e}")
            return NormalizedAccount(
                equity=0.0, cash=0.0, buying_power=0.0,
                portfolio_value=0.0, broker="IBKR", mode="LIVE"
            )

    def get_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """Get orders filtered by status"""
        try:
            orders = self._conn.get_orders(status=status)
            return [
                {
                    'order_id': str(o.get('orderId', '')),
                    'symbol': o.get('ticker', o.get('symbol', 'UNKNOWN')),
                    'side': o.get('side', '').lower(),
                    'qty': float(o.get('totalSize', 0)),
                    'order_type': o.get('orderType', '').lower(),
                    'status': o.get('status', '').lower(),
                    'broker': 'IBKR'
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Failed to get IBKR orders: {e}")
            return []


class OKXBroker(BrokerInterface):
    """
    OKX broker implementation - LIVE CRYPTO TRADING

    Used for live cryptocurrency trading via the US endpoint (us.okx.com).
    """

    def __init__(self):
        """Initialize OKX live crypto trading connection"""
        # Add OKX path
        okx_path = os.path.join(os.path.dirname(__file__), 'okx')
        if okx_path not in sys.path:
            sys.path.insert(0, okx_path)

        try:
            from okx_connection import OKXConnection
            self._conn = OKXConnection()
            logger.info("OKX broker initialized (LIVE mode - US endpoint)")
        except Exception as e:
            logger.error(f"Failed to initialize OKX: {e}")
            raise

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.OKX

    @property
    def trading_mode(self) -> TradingMode:
        return TradingMode.LIVE

    def is_authenticated(self) -> bool:
        """Check if OKX connection is working"""
        try:
            return self._conn.test_connection()
        except Exception:
            return False

    def get_portfolio_value(self) -> float:
        """Get total portfolio equity"""
        try:
            result = self._conn.get_account_balance()
            if result.get('code') == '0':
                data = result.get('data', [{}])[0]
                return float(data.get('totalEq', 0))
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get OKX portfolio value: {e}")
            return 0.0

    def get_positions(self) -> List[NormalizedPosition]:
        """Get all positions in normalized format"""
        positions = []
        try:
            result = self._conn.account_api.get_positions()
            if result.get('code') == '0':
                for pos in result.get('data', []):
                    positions.append(NormalizedPosition(
                        symbol=pos.get('instId', 'UNKNOWN'),
                        qty=float(pos.get('pos', 0)),
                        market_value=float(pos.get('notionalUsd', 0) or 0),
                        cost_basis=0.0,
                        avg_entry_price=float(pos.get('avgPx', 0) or 0),
                        unrealized_pl=float(pos.get('upl', 0) or 0),
                        side=pos.get('posSide', 'long'),
                        asset_type='CRYPTO'
                    ))
        except Exception as e:
            logger.error(f"Failed to get OKX positions: {e}")
        return positions

    def get_account(self) -> NormalizedAccount:
        """Get account summary in normalized format"""
        try:
            result = self._conn.get_account_balance()
            if result.get('code') == '0':
                data = result.get('data', [{}])[0]
                total_eq = float(data.get('totalEq', 0))
                return NormalizedAccount(
                    equity=total_eq,
                    cash=total_eq,  # OKX reports total equity
                    buying_power=total_eq,
                    portfolio_value=total_eq,
                    broker="OKX",
                    mode="LIVE"
                )
        except Exception as e:
            logger.error(f"Failed to get OKX account: {e}")

        return NormalizedAccount(
            equity=0.0, cash=0.0, buying_power=0.0,
            portfolio_value=0.0, broker="OKX", mode="LIVE"
        )

    def get_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """Get orders filtered by status"""
        try:
            if status == 'open':
                result = self._conn.trade_api.get_order_list()
            else:
                result = self._conn.trade_api.get_orders_history(instType='SPOT')

            if result.get('code') != '0':
                return []

            return [
                {
                    'order_id': o.get('ordId', ''),
                    'symbol': o.get('instId', 'UNKNOWN'),
                    'side': o.get('side', '').lower(),
                    'qty': float(o.get('sz', 0)),
                    'order_type': o.get('ordType', '').lower(),
                    'status': o.get('state', '').lower(),
                    'broker': 'OKX'
                }
                for o in result.get('data', [])
            ]
        except Exception as e:
            logger.error(f"Failed to get OKX orders: {e}")
            return []


class BrokerFactory:
    """
    Factory for creating broker instances.

    Provides methods to get the appropriate broker based on trading mode.
    """

    _paper_broker: Optional[AlpacaBroker] = None
    _live_broker: Optional[IBKRBroker] = None
    _crypto_broker: Optional[OKXBroker] = None

    @classmethod
    def create(cls, broker_type: BrokerType) -> BrokerInterface:
        """
        Create a broker instance of the specified type

        Args:
            broker_type: Type of broker to create

        Returns:
            Broker instance implementing BrokerInterface
        """
        if broker_type == BrokerType.ALPACA:
            return AlpacaBroker()
        elif broker_type == BrokerType.IBKR:
            return IBKRBroker()
        elif broker_type == BrokerType.OKX:
            return OKXBroker()
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")

    @classmethod
    def get_paper_broker(cls) -> AlpacaBroker:
        """
        Get the paper trading broker (Alpaca)

        Returns cached instance if available.
        """
        if cls._paper_broker is None:
            cls._paper_broker = AlpacaBroker()
        return cls._paper_broker

    @classmethod
    def get_live_broker(cls) -> IBKRBroker:
        """
        Get the live trading broker (IBKR)

        Returns cached instance if available.
        """
        if cls._live_broker is None:
            cls._live_broker = IBKRBroker()
        return cls._live_broker

    @classmethod
    def get_broker_for_mode(cls, mode: TradingMode) -> BrokerInterface:
        """
        Get broker based on trading mode

        Args:
            mode: PAPER or LIVE trading mode

        Returns:
            Appropriate broker instance
        """
        if mode == TradingMode.PAPER:
            return cls.get_paper_broker()
        else:
            return cls.get_live_broker()

    @classmethod
    def get_crypto_broker(cls) -> OKXBroker:
        """
        Get the crypto trading broker (OKX)

        Returns cached instance if available.
        """
        if cls._crypto_broker is None:
            cls._crypto_broker = OKXBroker()
        return cls._crypto_broker

    @classmethod
    def reset(cls):
        """Reset cached broker instances (useful for testing)"""
        cls._paper_broker = None
        cls._live_broker = None
        cls._crypto_broker = None


def main():
    """Test broker interface"""
    print("\n" + "="*60)
    print(" BROKER INTERFACE TEST")
    print("="*60)

    print("\n[1] Testing Paper Broker (Alpaca)...")
    try:
        paper = BrokerFactory.get_paper_broker()
        print(f"    Type: {paper.broker_type.value}")
        print(f"    Mode: {paper.trading_mode.value}")
        print(f"    Authenticated: {paper.is_authenticated()}")

        if paper.is_authenticated():
            account = paper.get_account()
            print(f"    Portfolio Value: ${account.portfolio_value:,.2f}")
            print(f"    Cash: ${account.cash:,.2f}")
    except Exception as e:
        print(f"    Failed: {e}")

    print("\n[2] Testing Live Broker (IBKR)...")
    try:
        live = BrokerFactory.get_live_broker()
        print(f"    Type: {live.broker_type.value}")
        print(f"    Mode: {live.trading_mode.value}")
        print(f"    Authenticated: {live.is_authenticated()}")

        if live.is_authenticated():
            account = live.get_account()
            print(f"    Portfolio Value: ${account.portfolio_value:,.2f}")
            print(f"    Cash: ${account.cash:,.2f}")
    except Exception as e:
        print(f"    Failed: {e}")

    print("\n[3] Testing Crypto Broker (OKX)...")
    try:
        crypto = BrokerFactory.get_crypto_broker()
        print(f"    Type: {crypto.broker_type.value}")
        print(f"    Mode: {crypto.trading_mode.value}")
        print(f"    Authenticated: {crypto.is_authenticated()}")

        account = crypto.get_account()
        print(f"    Portfolio Value: ${account.portfolio_value:,.2f}")
        print(f"    Cash: ${account.cash:,.2f}")
    except Exception as e:
        print(f"    Failed: {e}")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()