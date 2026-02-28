"""
Quick test script to diagnose Coinbase API endpoint
"""
import requests
import json
from datetime import datetime, timedelta

# Test different potential endpoints
endpoints_to_test = [
    "https://api.coinbase.com/api/v3/brokerage/public/products/BTC-USD/candles",
    "https://api.coinbase.com/api/v3/brokerage/products/BTC-USD/candles",
    "https://api.exchange.coinbase.com/products/BTC-USD/candles",
    "https://api.pro.coinbase.com/products/BTC-USD/candles"
]

# Calculate recent time range
end_time = int(datetime.now().timestamp())
start_time = int((datetime.now() - timedelta(days=7)).timestamp())

for endpoint in endpoints_to_test:
    print(f"\nTesting: {endpoint}")
    print("=" * 80)
    
    params_list = [
        {'start': str(start_time), 'end': str(end_time), 'granularity': 'SIX_HOUR'},
        {'start': str(start_time), 'end': str(end_time), 'granularity': '21600'},
    ]
    
    for params in params_list:
        try:
            print(f"Params: {params}")
            response = requests.get(endpoint, params=params, timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Got data: {json.dumps(data, indent=2)[:500]}...")
                break
            else:
                print(f"Response: {response.text[:200]}")
        except Exception as e:
            print(f"Error: {str(e)}")
        print()
