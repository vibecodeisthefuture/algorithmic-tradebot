"""
Test script for Hyperliquid public API
Tests access to historical candle data

Hyperliquid API Documentation: https://hyperliquid.gitbook.io/hyperliquid-docs/
No authentication required for public market data
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://api.hyperliquid.xyz/info"

def test_hyperliquid_meta():
    """Test basic meta info endpoint"""
    print("=" * 80)
    print("TESTING HYPERLIQUID META INFO")
    print("=" * 80)
    
    payload = {
        "type": "meta"
    }
    
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ SUCCESS - Got metadata for {len(data['universe'])} trading pairs")
        print(f"\nFirst 5 pairs:")
        for asset in data['universe'][:5]:
            print(f"  - {asset['name']}: {asset.get('szDecimals', 'N/A')} decimals")
        
        return True
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        return False


def test_hyperliquid_candles(coin="BTC"):
    """Test candle data endpoint"""
    print(f"\n{'=' * 80}")
    print(f"TESTING HYPERLIQUID CANDLE DATA FOR {coin}")
    print("=" * 80)
    
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": "1h",
            "startTime": int((datetime.now().timestamp() - 86400 * 7) * 1000),  # 7 days ago in ms
            "endTime": int(datetime.now().timestamp() * 1000)  # now in ms
        }
    }
    
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            print(f"✓ SUCCESS - Got {len(data)} candles")
            print(f"\nFirst candle: {data[0]}")
            print(f"Last candle: {data[-1]}")
            
            # Parse candle format: [timestamp, open, high, low, close, volume]
            if len(data[0]) >= 6:
                print(f"\nCandle structure:")
                print(f"  Time: {datetime.fromtimestamp(data[0]['t']/1000)}")
                print(f"  Open: ${data[0]['o']}")
                print(f"  High: ${data[0]['h']}")
                print(f"  Low: ${data[0]['l']}")
                print(f"  Close: ${data[0]['c']}")
                print(f"  Volume: {data[0]['v']}")
            
            return True
        else:
            print(f"⚠ WARNING - No candle data returned")
            print(f"Response: {data}")
            return False
            
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:200]}")
        return False


if __name__ == "__main__":
    print("Testing Hyperliquid Public API\n")
    
    meta_success = test_hyperliquid_meta()
    candles_success = test_hyperliquid_candles("BTC")
    
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"Meta Info: {'✓ PASS' if meta_success else '✗ FAIL'}")
    print(f"Candle Data: {'✓ PASS' if candles_success else '✗ FAIL'}")
    print(f"\nOverall: {'✓ API ACCESS VERIFIED' if meta_success and candles_success else '✗ ACCESS FAILED'}")
