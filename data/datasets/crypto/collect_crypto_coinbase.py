"""
Main Crypto Data Collection Script using Coinbase API

Collects 500 weeks of 6-hour interval data for:
- BTC-USD (Bitcoin)
- ETH-USD (Ethereum)
- SOL-USD (Solana)
- XRP-USD (Ripple)
- DOGE-USD (Dogecoin)
- ADA-USD (Cardano)

Usage:
    python collect_crypto_coinbase.py
"""

from coinbase_collector import CoinbaseCollector
from datetime import datetime
import os

# Configuration
CRYPTO_PAIRS = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'SOL': 'SOL-USD',
    'XRP': 'XRP-USD',
    'DOGE': 'DOGE-USD',
    'ADA': 'ADA-USD'
}

WEEKS = 500
GRANULARITY = '6h'
OUTPUT_DIR = '.'  # Current directory (crypto folder)

def main():
    """Main collection function"""
    
    print("=" * 80)
    print("COINBASE CRYPTOCURRENCY DATA COLLECTION")
    print("=" * 80)
    print(f"Collecting {WEEKS} weeks of {GRANULARITY} interval data")
    print(f"Cryptocurrencies: {', '.join(CRYPTO_PAIRS.keys())}")
    print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 80)
    print()
    
    # Initialize collector
    collector = CoinbaseCollector(rate_limit_delay=0.3)
    
    results = []
    
    for symbol, product_id in CRYPTO_PAIRS.items():
        print(f"\n{'=' * 80}")
        print(f"[{symbol}] Starting collection for {product_id}")
        print(f"{'=' * 80}")
        
        try:
            # Collect data
            df = collector.collect_historical_data(
                product_id=product_id,
                weeks=WEEKS,
                granularity=GRANULARITY
            )
            
            if df.empty:
                print(f"[{symbol}] ⚠ No data collected")
                results.append({
                    'symbol': symbol,
                    'status': 'NO_DATA',
                    'message': 'No data returned from API'
                })
                continue
            
            # Validate data
            print(f"\n[{symbol}] Validating data...")
            validation = collector.validate_data(df)
            
            # Save data
            output_file = os.path.join(OUTPUT_DIR, f'{symbol}-6h-500wks-data.csv')
            collector.save_data(df, output_file, include_metadata=True)
            
            # Calculate statistics
            date_range = f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}"
            
            results.append({
                'symbol': symbol,
                'product_id': product_id,
                'status': 'SUCCESS',
                'rows': len(df),
                'date_range': date_range,
                'issues': len(validation['issues']),
                'file': output_file
            })
            
            print(f"\n[{symbol}] ✓ COMPLETE")
            print(f"  - Rows: {len(df):,}")
            print(f"  - Date Range: {date_range}")
            print(f"  - Issues: {len(validation['issues'])}")
            print(f"  - File: {output_file}")
            
        except Exception as e:
            print(f"\n[{symbol}] ✗ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            
            results.append({
                'symbol': symbol,
                'product_id': product_id,
                'status': 'FAILED',
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 80)
    print("COLLECTION SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if r['status'] == 'SUCCESS']
    failed = [r for r in results if r['status'] == 'FAILED']
    no_data = [r for r in results if r['status'] == 'NO_DATA']
    
    print(f"\nSuccessful: {len(successful)}/{len(CRYPTO_PAIRS)}")
    print()
    
    for result in successful:
        print(f"✓ {result['symbol']:6s} | {result['rows']:5,d} rows | {result['date_range']}")
    
    if no_data:
        print("\nNo Data:")
        for result in no_data:
            print(f"⚠ {result['symbol']:6s} | {result['message']}")
    
    if failed:
        print("\nFailed:")
        for result in failed:
            print(f"✗ {result['symbol']:6s} | {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 80)
    print(f"Total rows collected: {sum(r['rows'] for r in successful):,}")
    print(f"Files saved to: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
