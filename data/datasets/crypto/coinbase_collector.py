"""
Coinbase Crypto Data Collector

Collects historical cryptocurrency data from Coinbase's public Advanced Trade API.
No authentication required for public candle data.

Features:
- Public API access (no API keys needed)
- Automatic pagination handling (300 candle limit per request)
- 6-hour granularity support
- Data validation and quality checks
- CSV export with metadata

Coinbase API Documentation:
https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getpubliccandles
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CoinbaseCollector:
    """
    Collector for Coinbase cryptocurrency historical data.
    
    Uses Coinbase Advanced Trade API's public endpoints.
    """
    
    BASE_URL = "https://api.exchange.coinbase.com/products"
    MAX_CANDLES_PER_REQUEST = 300  # Coinbase API limit
    
    # Granularity mappings (in seconds for Exchange API)
    GRANULARITIES = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        '6h': 21600,
        '1d': 86400
    }
    
    def __init__(self, rate_limit_delay: float = 0.3):
        """
        Initialize Coinbase collector.
        
        Args:
            rate_limit_delay: Delay between API requests in seconds (default 0.3s)
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TradeBot-Crypto-Collector/1.0',
            'Accept': 'application/json'
        })
        logger.info("CoinbaseCollector initialized (using Exchange API)")
    
    def fetch_candles(
        self,
        product_id: str,
        start_time: int,
        end_time: int,
        granularity: str = '6h'
    ) -> List[Dict]:
        """
        Fetch candle data from Coinbase Exchange API.
        
        Args:
            product_id: Trading pair (e.g., 'BTC-USD')
            start_time: Start timestamp (Unix seconds)
            end_time: End timestamp (Unix seconds)
            granularity: Candle interval ('1m', '5m', '15m', '1h', '6h', '1d')
        
        Returns:
            List of candle dictionaries
        """
        if granularity not in self.GRANULARITIES:
            raise ValueError(f"Invalid granularity. Must be one of: {list(self.GRANULARITIES.keys())}")
        
        granularity_seconds = self.GRANULARITIES[granularity]
        url = f"{self.BASE_URL}/{product_id}/candles"
        
        # Exchange API uses ISO 8601 format for dates
        start_iso = datetime.fromtimestamp(start_time).isoformat()
        end_iso = datetime.fromtimestamp(end_time).isoformat()
        
        params = {
            'start': start_iso,
            'end': end_iso,
            'granularity': str(granularity_seconds)
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Exchange API returns array: [time, low, high, open, close, volume]
            if isinstance(data, list) and len(data) > 0:
                candles = []
                for candle in data:
                    if len(candle) >= 6:
                        candles.append({
                            'start': str(int(candle[0])),
                            'low': str(candle[1]),
                            'high': str(candle[2]),
                            'open': str(candle[3]),
                            'close': str(candle[4]),
                            'volume': str(candle[5])
                        })
                logger.info(f"Fetched {len(candles)} candles for {product_id}")
                return candles
            else:
                logger.warning(f"No candles in response for {product_id}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {product_id}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text[:200]}")
            raise
    
    def collect_historical_data(
        self,
        product_id: str,
        weeks: int = 500,
        granularity: str = '6h'
    ) -> pd.DataFrame:
        """
        Collect historical data with automatic pagination.
        
        Args:
            product_id: Trading pair (e.g., 'BTC-USD')
            weeks: Number of weeks of historical data
            granularity: Candle interval
        
        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Starting collection for {product_id}: {weeks} weeks at {granularity} intervals")
        
        # Calculate time range
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(weeks=weeks)).timestamp())
        granularity_seconds = self.GRANULARITIES[granularity]
        
        # Calculate total candles needed
        total_duration = end_time - start_time
        total_candles = total_duration // granularity_seconds
        
        logger.info(f"Expected ~{total_candles} candles over {weeks} weeks")
        
        # Collect data in chunks
        all_candles = []
        current_end = end_time
        request_count = 0
        
        while current_end > start_time:
            # Calculate chunk start time (300 candles back)
            chunk_duration = self.MAX_CANDLES_PER_REQUEST * granularity_seconds
            current_start = max(start_time, current_end - chunk_duration)
            
            logger.info(f"Request {request_count + 1}: Fetching from {datetime.fromtimestamp(current_start)} to {datetime.fromtimestamp(current_end)}")
            
            try:
                candles = self.fetch_candles(
                    product_id=product_id,
                    start_time=current_start,
                    end_time=current_end,
                    granularity=granularity
                )
                
                all_candles.extend(candles)
                request_count += 1
                
                # Move to next chunk
                current_end = current_start
                
                # Rate limiting
                if current_end > start_time:
                    time.sleep(self.rate_limit_delay)
                    
            except Exception as e:
                logger.error(f"Error during collection: {str(e)}")
                break
        
        logger.info(f"Collected {len(all_candles)} total candles in {request_count} requests")
        
        # Convert to DataFrame
        if not all_candles:
            logger.warning(f"No data collected for {product_id}")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_candles)
        
        # Convert timestamp to datetime
        df['start'] = pd.to_datetime(df['start'].astype(int), unit='s')
        df.rename(columns={'start': 'date'}, inplace=True)
        
        # Convert numeric columns
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Sort by date
        df.sort_values('date', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        # Add metadata
        df['symbol'] = product_id
        df['granularity'] = granularity
        
        logger.info(f"Data collection complete for {product_id}: {len(df)} records")
        return df
    
    def validate_data(self, df: pd.DataFrame) -> Dict:
        """
        Validate collected data quality.
        
        Args:
            df: DataFrame to validate
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            'total_rows': len(df),
            'date_range': (df['date'].min(), df['date'].max()) if len(df) > 0 else None,
            'issues': []
        }
        
        if df.empty:
            validation['issues'].append({'type': 'empty_dataframe', 'severity': 'critical'})
            return validation
        
        # Check for missing values
        missing = df.isnull().sum()
        if missing.any():
            validation['issues'].append({
                'type': 'missing_values',
                'severity': 'warning',
                'details': missing[missing > 0].to_dict()
            })
        
        # Check OHLC relationships
        invalid_ohlc = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ).sum()
        
        if invalid_ohlc > 0:
            validation['issues'].append({
                'type': 'invalid_ohlc',
                'severity': 'error',
                'count': invalid_ohlc
            })
        
        # Check for negative values
        for col in ['open', 'high', 'low', 'close', 'volume']:
            negative_count = (df[col] <= 0).sum()
            if negative_count > 0:
                validation['issues'].append({
                    'type': f'negative_{col}',
                    'severity': 'error',
                    'count': negative_count
                })
        
        # Check for duplicate timestamps
        duplicates = df['date'].duplicated().sum()
        if duplicates > 0:
            validation['issues'].append({
                'type': 'duplicate_timestamps',
                'severity': 'warning',
                'count': duplicates
            })
        
        if not validation['issues']:
            logger.info("✓ Data validation passed")
        else:
            logger.warning(f"⚠ Found {len(validation['issues'])} validation issues")
        
        return validation
    
    def save_data(
        self,
        df: pd.DataFrame,
        filename: str,
        include_metadata: bool = True
    ):
        """
        Save data to CSV with optional metadata.
        
        Args:
            df: DataFrame to save
            filename: Output filename
            include_metadata: Whether to save metadata JSON
        """
        logger.info(f"Saving data to {filename}...")
        
        # Save CSV
        df.to_csv(filename, index=False)
        logger.info(f"✓ Saved {len(df)} rows to {filename}")
        
        # Save metadata
        if include_metadata:
            metadata_file = filename.rsplit('.', 1)[0] + '_metadata.json'
            metadata = {
                'collection_date': datetime.now().isoformat(),
                'source': 'Coinbase Advanced Trade API',
                'symbol': df['symbol'].iloc[0] if 'symbol' in df.columns else None,
                'granularity': df['granularity'].iloc[0] if 'granularity' in df.columns else None,
                'rows': len(df),
                'date_range': {
                    'start': df['date'].min().isoformat() if len(df) > 0 else None,
                    'end': df['date'].max().isoformat() if len(df) > 0 else None
                },
                'columns': list(df.columns)
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"✓ Metadata saved to {metadata_file}")


# Example usage
if __name__ == "__main__":
    collector = CoinbaseCollector()
    
    # Test with BTC
    print("Testing Coinbase collector with BTC-USD...")
    df = collector.collect_historical_data(
        product_id='BTC-USD',
        weeks=4,  # Test with 4 weeks
        granularity='6h'
    )
    
    print(f"\nCollected {len(df)} records")
    print(f"\nFirst few rows:\n{df.head()}")
    print(f"\nLast few rows:\n{df.tail()}")
    
    # Validate
    validation = collector.validate_data(df)
    print(f"\nValidation results: {validation}")
    
    # Save (optional)
    # collector.save_data(df, 'test_btc_data.csv')
