"""
Test script for CoinGecko public API
Tests access to price and market data

CoinGecko API: https://www.coingecko.com/api/documentation
Free tier: 10,000 calls/month, ~30 calls/minute
No API key required for free tier
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://api.coingecko.com/api/v3"

def test_coingecko_ping():
    """Test API connectivity"""
    print("=" * 80)
    print("TESTING COINGECKO PING")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/ping", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ SUCCESS - API is online")
        print(f"Response: {data}")
        return True
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        return False


def test_coingecko_price(coin_id="bitcoin"):
    """Test current price data"""
    print(f"\n{'=' * 80}")
    print(f"TESTING COINGECKO PRICE DATA FOR {coin_id.upper()}")
    print("=" * 80)
    
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true"
    }
    
    try:
        response = requests.get(f"{BASE_URL}/simple/price", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if coin_id in data:
            coin_data = data[coin_id]
            print(f"✓ SUCCESS - Got price data for {coin_id}")
            print(f"\n  Price: ${coin_data.get('usd', 'N/A'):,.2f}")
            print(f"  Market Cap: ${coin_data.get('usd_market_cap', 0):,.0f}")
            print(f"  24h Volume: ${coin_data.get('usd_24h_vol', 0):,.0f}")
            print(f"  24h Change: {coin_data.get('usd_24h_change', 0):.2f}%")
            return True
        else:
            print(f"⚠ WARNING - No data for {coin_id}")
            return False
            
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:200]}")
        return False


def test_coingecko_market_chart(coin_id="bitcoin", days=7):
    """Test historical market chart data"""
    print(f"\n{'=' * 80}")
    print(f"TESTING COINGECKO MARKET CHART FOR {coin_id.upper()} ({days} days)")
    print("=" * 80)
    
    params = {
        "vs_currency": "usd",
        "days": str(days),
        "interval": "daily"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/coins/{coin_id}/market_chart",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if "prices" in data:
            prices = data["prices"]
            print(f"✓ SUCCESS - Got {len(prices)} price data points")
            
            # Show first and last data points
            if len(prices) > 0:
                first_ts, first_price = prices[0]
                last_ts, last_price = prices[-1]
                
                print(f"\n  First: {datetime.fromtimestamp(first_ts/1000).strftime('%Y-%m-%d')} - ${first_price:,.2f}")
                print(f"  Last:  {datetime.fromtimestamp(last_ts/1000).strftime('%Y-%m-%d')} - ${last_price:,.2f}")
            
            return True
        else:
            print(f"⚠ WARNING - No price data")
            return False
            
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:200]}")
        return False


if __name__ == "__main__":
    print("Testing CoinGecko Public API\n")
    
    ping_success = test_coingecko_ping()
    price_success = test_coingecko_price("bitcoin")
    chart_success = test_coingecko_market_chart("bitcoin", days=7)
    
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"Ping: {'✓ PASS' if ping_success else '✗ FAIL'}")
    print(f"Price Data: {'✓ PASS' if price_success else '✗ FAIL'}")
    print(f"Chart Data: {'✓ PASS' if chart_success else '✗ FAIL'}")
    print(f"\nOverall: {'✓ API ACCESS VERIFIED' if all([ping_success, price_success, chart_success]) else '✗ ACCESS FAILED'}")
    print(f"\nRate Limits: Free tier = 10,000 calls/month, ~30 calls/minute")
