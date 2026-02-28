"""
Unified Data Service for TradeBot

Provides a single API for accessing crypto and stock historical data from multiple sources.
Handles automatic fallback, caching, and data quality validation.

Usage:
    from data_service import DataService

    service = DataService()

    # Get crypto data (auto-selects best source)
    btc_data = service.get_crypto_data('BTC', timeframe='6h', weeks=500)

    # Get stock data
    aapl_data = service.get_stock_data('AAPL', start_date='2020-01-01')

    # Get current prices
    prices = service.get_current_prices(['BTC', 'ETH', 'SOL'])
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import time

# Add crypto directory to path
sys.path.append(str(Path(__file__).parent / "crypto"))


class DataService:
    """
    Unified data service providing access to all data sources.

    Hierarchy for crypto data:
    1. Local cache (if exists and fresh)
    2. Coinbase Exchange (historical OHLCV)
    3. Hyperliquid (recent data)
    4. CoinGecko (price monitoring)
    """

    def __init__(self, cache_dir: Optional[str] = None, verbose: bool = False):
        """
        Initialize the data service.

        Args:
            cache_dir: Directory for cached data (default: datasets/data_tables/)
            verbose: Print detailed logging
        """
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent.parent
        self.cache_dir = Path(cache_dir) if cache_dir else (
            self.project_root / "data" / "datasets" / "data_tables"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize collectors lazily
        self._coinbase_collector = None
        self._hyperliquid_available = False
        self._coingecko_available = False

        self._log("DataService initialized")

    def _log(self, message: str):
        """Print log message if verbose mode enabled."""
        if self.verbose:
            print(f"[DataService] {message}")

    @property
    def coinbase_collector(self):
        """Lazy load Coinbase collector."""
        if self._coinbase_collector is None:
            try:
                from coinbase_collector import CoinbaseCollector
                self._coinbase_collector = CoinbaseCollector()
                self._log("Coinbase collector loaded")
            except ImportError as e:
                self._log(f"Coinbase collector not available: {e}")
        return self._coinbase_collector

    def _check_hyperliquid(self) -> bool:
        """Check if Hyperliquid API is available."""
        try:
            import requests
            response = requests.post(
                "https://api.hyperliquid.xyz/info",
                json={"type": "meta"},
                timeout=5
            )
            self._hyperliquid_available = response.status_code == 200
            self._log(f"Hyperliquid available: {self._hyperliquid_available}")
            return self._hyperliquid_available
        except Exception as e:
            self._log(f"Hyperliquid not available: {e}")
            self._hyperliquid_available = False
            return False

    def _check_coingecko(self) -> bool:
        """Check if CoinGecko API is available."""
        try:
            import requests
            response = requests.get(
                "https://api.coingecko.com/api/v3/ping",
                timeout=5
            )
            self._coingecko_available = response.status_code == 200
            self._log(f"CoinGecko available: {self._coingecko_available}")
            return self._coingecko_available
        except Exception as e:
            self._log(f"CoinGecko not available: {e}")
            self._coingecko_available = False
            return False

    def _get_cache_path(self, asset: str, timeframe: str, source: str = "auto") -> Path:
        """Generate cache file path."""
        filename = f"{asset.upper()}-{timeframe}-{source}-data.csv"
        return self.cache_dir / filename

    def _is_cache_fresh(self, cache_path: Path, max_age_hours: int = 24) -> bool:
        """Check if cached data is fresh enough."""
        if not cache_path.exists():
            return False

        file_age = time.time() - cache_path.stat().st_mtime
        age_hours = file_age / 3600

        is_fresh = age_hours < max_age_hours
        self._log(f"Cache age: {age_hours:.1f}h, fresh: {is_fresh}")
        return is_fresh

    def get_crypto_data(
        self,
        symbol: str,
        timeframe: str = '6h',
        weeks: int = 500,
        force_refresh: bool = False,
        source: str = 'auto'
    ) -> Optional[pd.DataFrame]:
        """
        Get cryptocurrency historical data.

        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'ETH')
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '6h', '1d')
            weeks: Number of weeks of historical data
            force_refresh: Bypass cache and fetch fresh data
            source: Data source ('auto', 'coinbase', 'hyperliquid', 'coingecko')

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        self._log(f"Requesting {symbol} {timeframe} data ({weeks} weeks)")

        # Check cache first (unless force_refresh)
        if not force_refresh:
            cache_path = self._get_cache_path(symbol, timeframe, source)
            if self._is_cache_fresh(cache_path, max_age_hours=12):  # 12h for crypto
                self._log(f"Loading from cache: {cache_path}")
                try:
                    return pd.read_csv(cache_path)
                except Exception as e:
                    self._log(f"Cache read failed: {e}")

        # Try data sources in order
        data = None

        if source == 'auto' or source == 'coinbase':
            data = self._get_crypto_from_coinbase(symbol, timeframe, weeks)
            if data is not None:
                source = 'coinbase'

        if data is None and (source == 'auto' or source == 'hyperliquid'):
            data = self._get_crypto_from_hyperliquid(symbol, timeframe, weeks)
            if data is not None:
                source = 'hyperliquid'

        if data is None and (source == 'auto' or source == 'coingecko'):
            data = self._get_crypto_from_coingecko(symbol, weeks)
            if data is not None:
                source = 'coingecko'

        # Cache the data
        if data is not None:
            cache_path = self._get_cache_path(symbol, timeframe, source)
            try:
                data.to_csv(cache_path, index=False)
                self._log(f"Data cached to: {cache_path}")
            except Exception as e:
                self._log(f"Cache write failed: {e}")

        return data

    def _get_crypto_from_coinbase(
        self,
        symbol: str,
        timeframe: str,
        weeks: int
    ) -> Optional[pd.DataFrame]:
        """Get crypto data from Coinbase Exchange."""
        self._log(f"Trying Coinbase for {symbol}")

        if self.coinbase_collector is None:
            return None

        try:
            product_id = f"{symbol.upper()}-USD"
            data = self.coinbase_collector.collect_historical_data(
                product_id=product_id,
                weeks=weeks,
                granularity=timeframe
            )

            if data is not None and len(data) > 0:
                self._log(f"Coinbase: Got {len(data)} rows")
                return data
            else:
                self._log("Coinbase: No data returned")
                return None

        except Exception as e:
            self._log(f"Coinbase failed: {e}")
            return None

    def _get_crypto_from_hyperliquid(
        self,
        symbol: str,
        timeframe: str,
        weeks: int
    ) -> Optional[pd.DataFrame]:
        """Get crypto data from Hyperliquid."""
        self._log(f"Trying Hyperliquid for {symbol}")

        if not self._check_hyperliquid():
            return None

        try:
            import requests

            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(weeks=weeks)

            # Map timeframe to Hyperliquid interval
            interval_map = {
                '1m': '1m', '5m': '5m', '15m': '15m',
                '1h': '1h', '6h': '6h', '1d': '1d'
            }
            interval = interval_map.get(timeframe, '6h')

            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol.upper(),
                    "interval": interval,
                    "startTime": int(start_time.timestamp() * 1000),
                    "endTime": int(end_time.timestamp() * 1000)
                }
            }

            response = requests.post(
                "https://api.hyperliquid.xyz/info",
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                self._log(f"Hyperliquid HTTP {response.status_code}")
                return None

            candles = response.json()

            if not candles:
                self._log("Hyperliquid: No data returned")
                return None

            # Convert to DataFrame
            data = []
            for candle in candles:
                data.append({
                    'timestamp': datetime.fromtimestamp(candle['t'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(candle['o']),
                    'high': float(candle['h']),
                    'low': float(candle['l']),
                    'close': float(candle['c']),
                    'volume': float(candle['v'])
                })

            df = pd.DataFrame(data)
            self._log(f"Hyperliquid: Got {len(df)} rows")
            return df

        except Exception as e:
            self._log(f"Hyperliquid failed: {e}")
            return None

    def _get_crypto_from_coingecko(
        self,
        symbol: str,
        weeks: int
    ) -> Optional[pd.DataFrame]:
        """Get crypto price data from CoinGecko (daily only)."""
        self._log(f"Trying CoinGecko for {symbol}")

        if not self._check_coingecko():
            return None

        try:
            import requests

            # Map symbol to CoinGecko ID
            symbol_map = {
                'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
                'ADA': 'cardano', 'XRP': 'ripple', 'DOGE': 'dogecoin'
            }
            coin_id = symbol_map.get(symbol.upper(), symbol.lower())

            days = weeks * 7

            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": min(days, 365),  # CoinGecko free tier limit
                "interval": "daily"
            }

            response = requests.get(url, params=params, timeout=30)

            if response.status_code != 200:
                self._log(f"CoinGecko HTTP {response.status_code}")
                return None

            data_json = response.json()

            if 'prices' not in data_json or not data_json['prices']:
                self._log("CoinGecko: No price data")
                return None

            # Convert to DataFrame (daily data only, so O=H=L=C=price)
            data = []
            prices = data_json['prices']
            volumes = data_json.get('total_volumes', [[ts, 0] for ts, _ in prices])

            for (ts, price), (_, volume) in zip(prices, volumes):
                data.append({
                    'timestamp': datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                })

            df = pd.DataFrame(data)
            self._log(f"CoinGecko: Got {len(df)} rows (daily)")
            return df

        except Exception as e:
            self._log(f"CoinGecko failed: {e}")
            return None

    def get_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Get stock historical data using yfinance.

        Args:
            symbol: Stock ticker (e.g., 'AAPL', 'MSFT')
            start_date: Start date (YYYY-MM-DD), default 5 years ago
            end_date: End date (YYYY-MM-DD), default today
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        self._log(f"Requesting {symbol} stock data")

        # Check cache first
        if not force_refresh:
            cache_path = self._get_cache_path(symbol, '1d', 'yfinance')
            if self._is_cache_fresh(cache_path, max_age_hours=48):  # 48h for stocks
                self._log(f"Loading from cache: {cache_path}")
                try:
                    return pd.read_csv(cache_path)
                except Exception as e:
                    self._log(f"Cache read failed: {e}")

        try:
            import yfinance as yf

            # Default date range
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')

            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                self._log(f"No data for {symbol}")
                return None

            # Standardize column names
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Keep only required columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

            self._log(f"yfinance: Got {len(df)} rows")

            # Cache the data
            cache_path = self._get_cache_path(symbol, '1d', 'yfinance')
            try:
                df.to_csv(cache_path, index=False)
                self._log(f"Data cached to: {cache_path}")
            except Exception as e:
                self._log(f"Cache write failed: {e}")

            return df

        except Exception as e:
            self._log(f"yfinance failed: {e}")
            return None

    def get_current_prices(
        self,
        symbols: List[str],
        asset_type: str = 'crypto'
    ) -> Dict[str, float]:
        """
        Get current prices for multiple assets.

        Args:
            symbols: List of symbols (e.g., ['BTC', 'ETH', 'SOL'])
            asset_type: 'crypto' or 'stock'

        Returns:
            Dictionary mapping symbol to current price
        """
        self._log(f"Getting current prices for {symbols}")

        prices = {}

        if asset_type == 'crypto':
            # Use CoinGecko for current prices
            if self._check_coingecko():
                try:
                    import requests

                    symbol_map = {
                        'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
                        'ADA': 'cardano', 'XRP': 'ripple', 'DOGE': 'dogecoin'
                    }

                    coin_ids = [symbol_map.get(s.upper(), s.lower()) for s in symbols]

                    url = "https://api.coingecko.com/api/v3/simple/price"
                    params = {
                        "ids": ",".join(coin_ids),
                        "vs_currencies": "usd"
                    }

                    response = requests.get(url, params=params, timeout=10)

                    if response.status_code == 200:
                        data = response.json()
                        for symbol in symbols:
                            coin_id = symbol_map.get(symbol.upper(), symbol.lower())
                            if coin_id in data and 'usd' in data[coin_id]:
                                prices[symbol.upper()] = data[coin_id]['usd']

                except Exception as e:
                    self._log(f"Current price fetch failed: {e}")

        elif asset_type == 'stock':
            # Use yfinance for current stock prices
            try:
                import yfinance as yf

                for symbol in symbols:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    if 'currentPrice' in info:
                        prices[symbol.upper()] = info['currentPrice']
                    elif 'regularMarketPrice' in info:
                        prices[symbol.upper()] = info['regularMarketPrice']

            except Exception as e:
                self._log(f"Current price fetch failed: {e}")

        self._log(f"Got prices: {prices}")
        return prices

    def validate_data(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Validate OHLCV data quality.

        Returns:
            Dictionary with validation results and issues found
        """
        issues = []
        warnings = []

        # Check required columns
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            issues.append(f"Missing columns: {missing_cols}")
            return {"valid": False, "issues": issues, "warnings": warnings}

        # Check for missing values
        for col in required_cols:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                issues.append(f"{missing_count} missing values in '{col}'")

        # Check OHLC relationships
        invalid_ohlc = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ).sum()

        if invalid_ohlc > 0:
            issues.append(f"{invalid_ohlc} rows with invalid OHLC relationships")

        # Check for negative prices
        negative_prices = (
            (df['open'] <= 0) |
            (df['high'] <= 0) |
            (df['low'] <= 0) |
            (df['close'] <= 0)
        ).sum()

        if negative_prices > 0:
            issues.append(f"{negative_prices} rows with negative or zero prices")

        # Check for zero volume (warning only)
        zero_volume = (df['volume'] == 0).sum()
        if zero_volume > 0:
            warnings.append(f"{zero_volume} rows with zero volume")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "total_rows": len(df)
        }


# Convenience functions
def get_crypto_data(symbol: str, timeframe: str = '6h', weeks: int = 500, **kwargs) -> Optional[pd.DataFrame]:
    """Quick function to get crypto data."""
    service = DataService(verbose=kwargs.get('verbose', False))
    return service.get_crypto_data(symbol, timeframe, weeks, **kwargs)


def get_stock_data(symbol: str, start_date: Optional[str] = None, **kwargs) -> Optional[pd.DataFrame]:
    """Quick function to get stock data."""
    service = DataService(verbose=kwargs.get('verbose', False))
    return service.get_stock_data(symbol, start_date, **kwargs)


def get_current_prices(symbols: List[str], asset_type: str = 'crypto', **kwargs) -> Dict[str, float]:
    """Quick function to get current prices."""
    service = DataService(verbose=kwargs.get('verbose', False))
    return service.get_current_prices(symbols, asset_type, **kwargs)


if __name__ == "__main__":
    # Test the service
    print("Testing DataService...")

    service = DataService(verbose=True)

    # Test crypto data
    print("\n1. Testing Crypto Data (BTC):")
    btc_data = service.get_crypto_data('BTC', timeframe='6h', weeks=10)
    if btc_data is not None:
        print(f"   Got {len(btc_data)} rows")
        print(f"   Date range: {btc_data['timestamp'].iloc[0]} to {btc_data['timestamp'].iloc[-1]}")
        validation = service.validate_data(btc_data)
        print(f"   Valid: {validation['valid']}")
        if validation['issues']:
            print(f"   Issues: {validation['issues']}")

    # Test stock data
    print("\n2. Testing Stock Data (AAPL):")
    aapl_data = service.get_stock_data('AAPL', start_date='2024-01-01')
    if aapl_data is not None:
        print(f"   Got {len(aapl_data)} rows")
        print(f"   Date range: {aapl_data['timestamp'].iloc[0]} to {aapl_data['timestamp'].iloc[-1]}")

    # Test current prices
    print("\n3. Testing Current Prices:")
    prices = service.get_current_prices(['BTC', 'ETH', 'SOL'], asset_type='crypto')
    for symbol, price in prices.items():
        print(f"   {symbol}: ${price:,.2f}")

    print("\nDataService test complete!")
