"""
Script to collect multiple stock tickers data for 1000 weeks
Tickers: AAPL, ASTS, NFLX, NVDA, META
"""
from data_collection import DataCollector
from datetime import datetime, timedelta

# Initialize collector
collector = DataCollector(source='yahoo')

# Define tickers to collect
tickers = ['AAPL', 'ASTS', 'NFLX', 'NVDA', 'META']

# Calculate dates for 1000 weeks
end_date = datetime.now()
start_date = end_date - timedelta(weeks=1000)

print(f"Collecting data for {len(tickers)} tickers: {', '.join(tickers)}")
print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (1000 weeks)")
print("=" * 80)

results = []

for ticker in tickers:
    print(f"\n[{ticker}] Starting collection...")
    
    try:
        # Fetch data
        data = collector.fetch_data(
            symbols=ticker,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            interval='1d'
        )
        
        print(f"[{ticker}] Data shape: {data.shape}")
        
        # Validate data
        validation_results = collector.validate_data(data)
        
        # Save data
        output_file = f'data_tables/{ticker}-1d-1000wks-data.csv'
        collector.save_data(data, output_file, format='csv')
        
        results.append({
            'ticker': ticker,
            'rows': len(data),
            'file': output_file,
            'status': 'SUCCESS',
            'issues': len(validation_results.get('issues', []))
        })
        
        print(f"[{ticker}] ✓ Complete - {len(data)} rows saved to {output_file}")
        
    except Exception as e:
        print(f"[{ticker}] ✗ ERROR: {str(e)}")
        results.append({
            'ticker': ticker,
            'status': 'FAILED',
            'error': str(e)
        })

# Summary
print("\n" + "=" * 80)
print("COLLECTION SUMMARY")
print("=" * 80)
for result in results:
    if result['status'] == 'SUCCESS':
        print(f"✓ {result['ticker']}: {result['rows']:,} rows | {result['issues']} issues | {result['file']}")
    else:
        print(f"✗ {result['ticker']}: FAILED - {result.get('error', 'Unknown error')}")

successful = sum(1 for r in results if r['status'] == 'SUCCESS')
print(f"\nTotal: {successful}/{len(tickers)} successful")
