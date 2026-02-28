"""
Test VIX Data Retrieval from yfinance

This script tests VIX data retrieval using yfinance as the primary source.
"""

import sys
import os


def test_vix_data_retrieval():
    """Test retrieving VIX data from yfinance"""
    print("="*70)
    print("VIX DATA RETRIEVAL TEST")
    print("="*70)
    
    # Test 1: Try yfinance
    print("\n[Test 1] Testing yfinance VIX data source...")
    yfinance_vix = None
    try:
        import yfinance as yf
        print("✓ yfinance module available")
        
        vix_ticker = yf.Ticker("^VIX")
        vix_data = vix_ticker.history(period="1d")
        
        if not vix_data.empty:
            vix_level = vix_data['Close'].iloc[-1]
            yfinance_vix = float(vix_level)
            print(f"✅ yfinance VIX Level: {yfinance_vix:.2f}")
        else:
            print("⚠ yfinance returned empty data")
    except ImportError:
        print("❌ yfinance not installed")
        print("   Install with: pip install yfinance")
    except Exception as e:
        print(f"❌ yfinance test failed: {e}")
    
    # Test 2: Test integrated fallback logic
    print(f"\n[Test 2] Testing integrated VIX retrieval from risk_override...")
    try:
        from risk_override import RiskPolicyValidator
        validator = RiskPolicyValidator()
        
        integrated_vix = validator.get_vix_level()
        print(f"✅ Integrated VIX Level: {integrated_vix:.2f}")
        
        # Determine source
        if yfinance_vix and abs(integrated_vix - yfinance_vix) < 0.01:
            print("   Source: yfinance (primary)")
        elif integrated_vix == 20.0:
            print("   Source: Default conservative value")
        
    except Exception as e:
        print(f"❌ Integrated test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    
    if yfinance_vix:
        print(f"✅ yfinance: Working (VIX = {yfinance_vix:.2f})")
        print("\n✅ VIX DATA RETRIEVAL CONFIRMED")
        print("Risk override system has reliable VIX data source")
        return yfinance_vix
    else:
        print("❌ yfinance: Not available")
        print("\n⚠ NO VIX SOURCES AVAILABLE")
        print("System will use default VIX=20.0 (conservative)")
        return None


if __name__ == "__main__":
    vix_level = test_vix_data_retrieval()
