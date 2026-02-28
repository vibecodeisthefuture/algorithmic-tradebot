"""
OKX Connection Module

Manages API connection and account status for OKX cryptocurrency trading.
Uses the US REST endpoint (us.okx.com) for US-based access.

Documentation: https://us.okx.com/docs-v5/en/

WARNING: This is configured for PRODUCTION trading with real funds.
"""

import os
import okx.Trade as Trade
import okx.Account as Account
import okx.MarketData as MarketData


# US domain for OKX API
OKX_US_DOMAIN = "https://us.okx.com"


def _load_env_file():
    """Load environment variables from config/.env if they aren't already set"""
    env_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'config', '.env'
    )
    env_path = os.path.normpath(env_path)

    if not os.path.exists(env_path):
        return

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Only set if not already in environment
                if not os.environ.get(key):
                    os.environ[key] = value


class OKXConnection:
    """
    OKX API connection manager

    Reads credentials from environment variables (or config/.env fallback)
    and initializes authenticated API clients pointing at the US endpoint.

    WARNING: flag='0' = LIVE trading with real funds.
    """

    def __init__(self):
        """
        Initialize OKX connection using environment variables.

        Credentials are loaded from:
          1. Environment variables (if set)
          2. config/.env file (fallback)

        Required:
            OKX_API_KEY: API key from OKX
            OKX_SECRET_KEY: API secret key
            OKX_PASSPHRASE: API passphrase
        """
        # Load from .env file if env vars aren't set
        _load_env_file()

        api_key = os.environ.get("OKX_API_KEY", "")
        secret_key = os.environ.get("OKX_SECRET_KEY", "")
        passphrase = os.environ.get("OKX_PASSPHRASE", "")

        if not all([api_key, secret_key, passphrase]):
            raise ValueError(
                "API credentials not provided. Set environment variables:\n"
                "  OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE"
            )

        # flag='0' = live trading, '1' = demo trading
        self.trade_api = Trade.TradeAPI(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase,
            flag='0',
            domain=OKX_US_DOMAIN,
            debug=False
        )

        self.account_api = Account.AccountAPI(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase,
            flag='0',
            domain=OKX_US_DOMAIN,
            debug=False
        )

        self.market_api = MarketData.MarketAPI(
            api_key=api_key,
            api_secret_key=secret_key,
            passphrase=passphrase,
            flag='0',
            domain=OKX_US_DOMAIN,
            debug=False
        )

        print(f"OKX connection initialized (US endpoint: {OKX_US_DOMAIN})")

    def test_connection(self):
        """Test the API connection by fetching account balance"""
        print("\nTesting OKX connection...")
        try:
            result = self.get_account_balance()
            if result.get('code') == '0':
                data = result.get('data', [{}])[0]
                total_eq = data.get('totalEq', '0')
                print(f"✓ Connection successful!")
                print(f"  Total Equity: ${float(total_eq):,.2f}")
                return True
            else:
                print(f"✗ Connection failed: {result.get('msg', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False

    def get_account_balance(self):
        """Get account balance information"""
        return self.account_api.get_account_balance()

    def get_account_config(self):
        """Get account configuration"""
        return self.account_api.get_account_config()

    def print_full_status(self):
        """Print complete account status"""
        print("\n" + "=" * 60)
        print(" OKX ACCOUNT STATUS")
        print("=" * 60)
        self.print_account_summary()
        self.print_balances()
        self.print_positions()
        print("=" * 60 + "\n")

    def print_account_summary(self):
        """Print account equity summary"""
        try:
            result = self.get_account_balance()
            if result.get('code') == '0':
                data = result.get('data', [{}])[0]
                total_eq = float(data.get('totalEq', 0))
                adj_eq = float(data.get('adjEq', 0) or 0)
                iso_eq = float(data.get('isoEq', 0) or 0)

                print(f"\n{'─'*40}")
                print(f" ACCOUNT SUMMARY")
                print(f"{'─'*40}")
                print(f"  Total Equity:    ${total_eq:,.2f}")
                if adj_eq:
                    print(f"  Adjusted Equity: ${adj_eq:,.2f}")
                if iso_eq:
                    print(f"  Isolated Equity: ${iso_eq:,.2f}")
            else:
                print(f"  Error: {result.get('msg')}")
        except Exception as e:
            print(f"  Error getting summary: {e}")

    def print_balances(self):
        """Print all currency balances"""
        try:
            result = self.get_account_balance()
            if result.get('code') == '0':
                data = result.get('data', [{}])[0]
                details = data.get('details', [])

                print(f"\n{'─'*40}")
                print(f" CURRENCY BALANCES")
                print(f"{'─'*40}")

                if not details:
                    print("  No balances found")
                    return

                for detail in details:
                    ccy = detail.get('ccy', '')
                    avail_bal = float(detail.get('availBal', 0))
                    frozen_bal = float(detail.get('frozenBal', 0))
                    eq = float(detail.get('eq', 0) or 0)

                    if avail_bal > 0 or frozen_bal > 0:
                        print(f"\n  {ccy}:")
                        print(f"    Available: {avail_bal}")
                        if frozen_bal > 0:
                            print(f"    Frozen:    {frozen_bal}")
                        if eq > 0:
                            print(f"    Equity:    ${eq:,.2f}")
            else:
                print(f"  Error: {result.get('msg')}")
        except Exception as e:
            print(f"  Error getting balances: {e}")

    def print_positions(self):
        """Print open positions"""
        try:
            result = self.account_api.get_positions()
            if result.get('code') == '0':
                positions = result.get('data', [])

                print(f"\n{'─'*40}")
                print(f" OPEN POSITIONS")
                print(f"{'─'*40}")

                if not positions:
                    print("  No open positions")
                    return

                for pos in positions:
                    inst_id = pos.get('instId', '')
                    pos_side = pos.get('posSide', '')
                    pos_sz = pos.get('pos', '0')
                    avg_px = pos.get('avgPx', '0')
                    upl = float(pos.get('upl', 0) or 0)

                    print(f"\n  {inst_id}:")
                    print(f"    Side: {pos_side}")
                    print(f"    Size: {pos_sz}")
                    print(f"    Avg Price: ${float(avg_px):,.2f}")
                    print(f"    Unrealized P/L: ${upl:,.2f}")
            else:
                print(f"  Error: {result.get('msg')}")
        except Exception as e:
            print(f"  Error getting positions: {e}")


def main():
    """Test OKX connection"""
    print("OKX Connection Test")
    print("🔴 WARNING: PRODUCTION MODE - US ENDPOINT")
    print("=" * 50)

    try:
        conn = OKXConnection()
        success = conn.test_connection()

        if success:
            conn.print_full_status()
        else:
            print("\nConnection test failed. Check credentials and network.")
            return False

    except ValueError as e:
        print(f"\n{str(e)}")
        return False

    return True


if __name__ == "__main__":
    main()
