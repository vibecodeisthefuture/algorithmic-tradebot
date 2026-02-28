"""
Script to collect S&P 500 Index data for 1000 weeks
Ticker: ^GSPC (S&P 500 Index)
"""
from data_collection import DataCollector
from datetime import datetime, timedelta

# Initialize collector
collector = DataCollector(source='yahoo')

# Calculate dates for 1000 weeks
end_date = datetime.now()
start_date = end_date - timedelta(weeks=1000)

print(f"Collecting S&P 500 Index (^GSPC) data")
print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (1000 weeks)")
print("=" * 80)

try:
    # Fetch data
    data = collector.fetch_data(
        symbols='^GSPC',
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        interval='1d'
    )
    
    print(f"\nData shape: {data.shape}")
    print(f"\nFirst few rows:\n{data.head()}")
    print(f"\nLast few rows:\n{data.tail()}")
    
    # Validate data
    print("\nValidating data...")
    validation_results = collector.validate_data(data)
    print(f"Validation results: {validation_results}")
    
    # Save data
    output_file = 'data_tables/SP500-1d-1000wks-data.csv'
    collector.save_data(data, output_file, format='csv')
    print(f"\n✓ Data saved to {output_file}")
    print(f"✓ Total rows collected: {len(data)}")
    
except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    print("\nNote: S&P 500 ticker is ^GSPC on Yahoo Finance")
