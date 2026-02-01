"""
Data Collection Script for Algorithmic Trading Backtests

This script provides a robust framework for collecting, validating, and storing
historical market data from multiple sources. Quality data is the foundation 
of reliable backtesting.

Features:
- Multiple data source support (Yahoo Finance, Alpha Vantage, etc.)
- Data validation and quality checks
- Handling of missing data
- Corporate action adjustments (splits, dividends)
- Metadata logging for reproducibility
- Export to multiple formats (CSV, Parquet, HDF5)

Usage:
    from datasets.data_collection import DataCollector
    
    collector = DataCollector(source='yahoo')
    data = collector.fetch_data(
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        start_date='2010-01-01',
        end_date='2023-12-31',
        interval='1d'
    )
    collector.validate_data(data)
    collector.save_data(data, 'historical_prices.csv')
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import logging
import warnings

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataCollector:
    """
    Main class for collecting and managing market data for backtesting.
    
    Attributes:
        source (str): Data source ('yahoo', 'alphavantage', etc.)
        api_key (str): API key for paid sources
    """
    
    def __init__(self, source: str = 'yahoo', api_key: Optional[str] = None):
        """
        Initialize DataCollector.
        
        Args:
            source: Data source to use ('yahoo', 'alphavantage')
            api_key: API key for sources that require authentication
        """
        self.source = source.lower()
        self.api_key = api_key
        self.metadata = {
            'collection_date': datetime.now().isoformat(),
            'source': self.source,
            'version': '1.0'
        }
        
        logger.info(f"DataCollector initialized with source: {self.source}")
    
    def fetch_data(
        self,
        symbols: Union[str, List[str]],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Fetch historical market data for given symbols.
        
        Args:
            symbols: Single symbol or list of symbols (e.g., ['AAPL', 'MSFT'])
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            interval: Data interval ('1d', '1h', '1m', etc.)
        
        Returns:
            DataFrame with OHLCV data
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        logger.info(f"Fetching data for {len(symbols)} symbol(s) from {start_date} to {end_date}")
        
        if self.source == 'yahoo':
            return self._fetch_yahoo(symbols, start_date, end_date, interval)
        elif self.source == 'alphavantage':
            return self._fetch_alphavantage(symbols, start_date, end_date, interval)
        else:
            raise ValueError(f"Unsupported data source: {self.source}")
    
    def _fetch_yahoo(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from Yahoo Finance using yfinance."""
        data_frames = []
        
        for symbol in symbols:
            try:
                logger.info(f"Downloading {symbol}...")
                ticker = yf.Ticker(symbol)
                df = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    auto_adjust=True  # Adjust for splits and dividends
                )
                
                if df.empty:
                    logger.warning(f"No data returned for {symbol}")
                    continue
                
                # Add symbol column
                df['Symbol'] = symbol
                df.reset_index(inplace=True)
                
                # Standardize column names
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                
                data_frames.append(df)
                logger.info(f"Successfully downloaded {len(df)} rows for {symbol}")
                
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {str(e)}")
                continue
        
        if not data_frames:
            raise ValueError("No data was successfully fetched")
        
        # Combine all data
        combined_data = pd.concat(data_frames, ignore_index=True)
        
        # Store metadata
        self.metadata.update({
            'symbols': symbols,
            'start_date': start_date,
            'end_date': end_date,
            'interval': interval,
            'rows_collected': len(combined_data)
        })
        
        return combined_data
    
    def _fetch_alphavantage(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from Alpha Vantage (template - requires API key and implementation)."""
        raise NotImplementedError(
            "Alpha Vantage integration requires API key and additional dependencies. "
            "Install: pip install alpha-vantage"
        )
    
    def validate_data(self, data: pd.DataFrame) -> Dict[str, any]:
        """
        Validate data quality and check for common issues.
        
        Args:
            data: DataFrame to validate
        
        Returns:
            Dictionary with validation results
        """
        logger.info("Validating data quality...")
        
        validation_results = {
            'total_rows': len(data),
            'symbols': data['symbol'].nunique() if 'symbol' in data.columns else 1,
            'date_range': (data['date'].min(), data['date'].max()) if 'date' in data.columns else None,
            'issues': []
        }
        
        # Check for missing values
        missing_values = data.isnull().sum()
        if missing_values.any():
            validation_results['issues'].append({
                'type': 'missing_values',
                'details': missing_values[missing_values > 0].to_dict()
            })
            logger.warning(f"Missing values detected: {missing_values[missing_values > 0].to_dict()}")
        
        # Check for duplicate dates per symbol
        if 'date' in data.columns and 'symbol' in data.columns:
            duplicates = data.groupby('symbol')['date'].apply(
                lambda x: x.duplicated().sum()
            )
            if duplicates.any():
                validation_results['issues'].append({
                    'type': 'duplicate_dates',
                    'details': duplicates[duplicates > 0].to_dict()
                })
                logger.warning(f"Duplicate dates found: {duplicates[duplicates > 0].to_dict()}")
        
        # Check for zero/negative prices
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in data.columns:
                invalid_prices = (data[col] <= 0).sum()
                if invalid_prices > 0:
                    validation_results['issues'].append({
                        'type': f'invalid_{col}_prices',
                        'count': invalid_prices
                    })
                    logger.warning(f"Found {invalid_prices} invalid {col} prices (<= 0)")
        
        # Check OHLC relationships (High >= Low, High >= Open/Close, etc.)
        if all(col in data.columns for col in ['open', 'high', 'low', 'close']):
            invalid_ohlc = (
                (data['high'] < data['low']) |
                (data['high'] < data['open']) |
                (data['high'] < data['close']) |
                (data['low'] > data['open']) |
                (data['low'] > data['close'])
            ).sum()
            
            if invalid_ohlc > 0:
                validation_results['issues'].append({
                    'type': 'invalid_ohlc_relationships',
                    'count': invalid_ohlc
                })
                logger.warning(f"Found {invalid_ohlc} rows with invalid OHLC relationships")
        
        # Check for data gaps
        if 'date' in data.columns:
            data_sorted = data.sort_values('date')
            date_diffs = data_sorted['date'].diff()
            # Look for gaps > 7 days (for daily data)
            large_gaps = date_diffs[date_diffs > pd.Timedelta(days=7)]
            if len(large_gaps) > 0:
                validation_results['issues'].append({
                    'type': 'data_gaps',
                    'count': len(large_gaps),
                    'max_gap': str(large_gaps.max())
                })
                logger.warning(f"Found {len(large_gaps)} data gaps > 7 days")
        
        if not validation_results['issues']:
            logger.info("✓ Data validation passed with no issues")
        else:
            logger.warning(f"⚠ Data validation found {len(validation_results['issues'])} issue types")
        
        return validation_results
    
    def handle_missing_data(
        self,
        data: pd.DataFrame,
        method: str = 'forward_fill'
    ) -> pd.DataFrame:
        """
        Handle missing data using specified method.
        
        Args:
            data: DataFrame with potential missing values
            method: Method to use ('forward_fill', 'drop', 'interpolate')
        
        Returns:
            DataFrame with missing data handled
        """
        logger.info(f"Handling missing data using method: {method}")
        
        if method == 'forward_fill':
            return data.fillna(method='ffill')
        elif method == 'drop':
            return data.dropna()
        elif method == 'interpolate':
            return data.interpolate(method='linear')
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def save_data(
        self,
        data: pd.DataFrame,
        filename: str,
        format: str = 'csv',
        include_metadata: bool = True
    ):
        """
        Save data to file with optional metadata.
        
        Args:
            data: DataFrame to save
            filename: Output filename
            format: File format ('csv', 'parquet', 'hdf5')
            include_metadata: Whether to save metadata separately
        """
        logger.info(f"Saving data to {filename} in {format} format...")
        
        if format == 'csv':
            data.to_csv(filename, index=False)
        elif format == 'parquet':
            data.to_parquet(filename, index=False)
        elif format == 'hdf5':
            data.to_hdf(filename, key='data', mode='w')
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"✓ Data saved successfully: {len(data)} rows")
        
        # Save metadata
        if include_metadata:
            metadata_file = filename.rsplit('.', 1)[0] + '_metadata.json'
            import json
            with open(metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            logger.info(f"✓ Metadata saved to {metadata_file}")
    
    def load_data(self, filename: str, format: str = 'csv') -> pd.DataFrame:
        """
        Load previously saved data.
        
        Args:
            filename: Input filename
            format: File format ('csv', 'parquet', 'hdf5')
        
        Returns:
            Loaded DataFrame
        """
        logger.info(f"Loading data from {filename}...")
        
        if format == 'csv':
            data = pd.read_csv(filename)
        elif format == 'parquet':
            data = pd.read_parquet(filename)
        elif format == 'hdf5':
            data = pd.read_hdf(filename, key='data')
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Convert date column if present
        if 'date' in data.columns:
            data['date'] = pd.to_datetime(data['date'])
        
        logger.info(f"✓ Loaded {len(data)} rows")
        return data


# Example usage
if __name__ == "__main__":
    # Initialize collector
    collector = DataCollector(source='yahoo')
    
    # Fetch data for multiple symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    start_date = '2020-01-01'
    end_date = '2024-01-01'
    
    print(f"Collecting data for {symbols}...")
    data = collector.fetch_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        interval='1d'
    )
    
    print(f"\nData shape: {data.shape}")
    print(f"\nFirst few rows:\n{data.head()}")
    
    # Validate data
    print("\nValidating data...")
    validation_results = collector.validate_data(data)
    print(f"Validation results: {validation_results}")
    
    # Save data
    output_file = 'historical_data.csv'
    collector.save_data(data, output_file, format='csv')
    print(f"\n✓ Data saved to {output_file}")
    
    # Load data back
    loaded_data = collector.load_data(output_file, format='csv')
    print(f"\n✓ Successfully loaded data: {loaded_data.shape}")
