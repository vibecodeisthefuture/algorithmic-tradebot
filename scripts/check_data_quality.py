"""
Data Quality Check Script for TradeBot

Performs quality checks on historical data files used for backtesting.
Checks for missing values, anomalies, gaps, and data freshness.

Usage:
    python scripts/check_data_quality.py [--asset ASSET] [--timeframe TIMEFRAME]

Examples:
    python scripts/check_data_quality.py  # Check all data
    python scripts/check_data_quality.py --asset BTC --timeframe 6h
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse


# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")


def check_csv_data_quality(filepath: str, asset: str = None) -> Dict:
    """
    Check data quality for a CSV file containing OHLCV data.

    Returns dictionary with quality metrics and issues.
    """
    issues = []
    warnings = []
    info = {}

    if not os.path.exists(filepath):
        return {
            "status": "error",
            "issues": [f"File not found: {filepath}"],
            "warnings": [],
            "info": {}
        }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            issues.append("File is empty")
            return {
                "status": "error",
                "issues": issues,
                "warnings": warnings,
                "info": info
            }

        info["total_rows"] = len(rows)
        info["first_date"] = rows[0].get("timestamp", rows[0].get("date", "Unknown"))
        info["last_date"] = rows[-1].get("timestamp", rows[-1].get("date", "Unknown"))

        # Check for required columns
        headers = list(rows[0].keys())
        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        alt_required_cols = ["date", "open", "high", "low", "close", "volume"]

        has_timestamp = "timestamp" in headers or "date" in headers
        has_ohlcv = all(col in headers for col in ["open", "high", "low", "close", "volume"])

        if not has_timestamp:
            issues.append("Missing timestamp/date column")
        if not has_ohlcv:
            missing = [col for col in ["open", "high", "low", "close", "volume"] if col not in headers]
            issues.append(f"Missing OHLCV columns: {', '.join(missing)}")

        if issues:
            return {
                "status": "error",
                "issues": issues,
                "warnings": warnings,
                "info": info
            }

        # Determine timestamp column
        ts_col = "timestamp" if "timestamp" in headers else "date"

        # Check for missing values
        missing_counts = {col: 0 for col in ["open", "high", "low", "close", "volume"]}
        zero_volume_count = 0
        negative_price_count = 0
        invalid_ohlc_count = 0  # Cases where high < low, etc.

        timestamps = []
        for row_num, row in enumerate(rows, start=2):
            # Check timestamp
            if row[ts_col]:
                timestamps.append(row[ts_col])
            else:
                issues.append(f"Row {row_num}: Missing timestamp")

            # Check for missing OHLCV values
            for col in ["open", "high", "low", "close", "volume"]:
                if not row.get(col) or row[col].strip() == "":
                    missing_counts[col] += 1

            # Check for zero/negative values
            try:
                open_price = float(row.get("open", 0))
                high_price = float(row.get("high", 0))
                low_price = float(row.get("low", 0))
                close_price = float(row.get("close", 0))
                volume = float(row.get("volume", 0))

                if volume == 0:
                    zero_volume_count += 1

                if any(p <= 0 for p in [open_price, high_price, low_price, close_price]):
                    negative_price_count += 1

                # Check OHLC consistency
                if not (low_price <= open_price <= high_price and
                        low_price <= close_price <= high_price):
                    invalid_ohlc_count += 1

            except (ValueError, TypeError):
                pass  # Will be caught by missing_counts check

        # Report missing values
        for col, count in missing_counts.items():
            if count > 0:
                pct = (count / len(rows)) * 100
                issues.append(f"{count} rows ({pct:.1f}%) missing '{col}' values")

        # Report quality issues
        if zero_volume_count > 0:
            pct = (zero_volume_count / len(rows)) * 100
            if pct > 5:
                warnings.append(f"{zero_volume_count} rows ({pct:.1f}%) have zero volume")
            else:
                info["zero_volume_rows"] = zero_volume_count

        if negative_price_count > 0:
            issues.append(f"{negative_price_count} rows have negative or zero prices")

        if invalid_ohlc_count > 0:
            warnings.append(f"{invalid_ohlc_count} rows have invalid OHLC relationships")

        # Check for duplicate timestamps
        if len(timestamps) != len(set(timestamps)):
            duplicates = len(timestamps) - len(set(timestamps))
            issues.append(f"{duplicates} duplicate timestamps found")

        # Check for gaps in time series
        try:
            # Parse timestamps
            dt_format = None
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S.%f"]:
                try:
                    datetime.strptime(timestamps[0], fmt)
                    dt_format = fmt
                    break
                except ValueError:
                    continue

            if dt_format:
                dts = [datetime.strptime(ts, dt_format) for ts in timestamps if ts]
                dts.sort()

                # Calculate expected interval
                if len(dts) >= 2:
                    intervals = [(dts[i+1] - dts[i]).total_seconds() for i in range(len(dts)-1)]
                    # Most common interval
                    from collections import Counter
                    interval_counts = Counter(intervals)
                    expected_interval = interval_counts.most_common(1)[0][0]

                    # Check for gaps
                    gaps = []
                    for i in range(len(dts)-1):
                        actual_interval = (dts[i+1] - dts[i]).total_seconds()
                        if actual_interval > expected_interval * 1.5:  # Allow 50% tolerance
                            gaps.append((dts[i], dts[i+1], actual_interval / 3600))

                    if gaps:
                        info["gaps_found"] = len(gaps)
                        if len(gaps) <= 3:
                            for start, end, hours in gaps:
                                warnings.append(
                                    f"Gap detected: {start.strftime('%Y-%m-%d %H:%M')} to "
                                    f"{end.strftime('%Y-%m-%d %H:%M')} ({hours:.1f} hours)"
                                )
                        else:
                            warnings.append(f"{len(gaps)} gaps detected in time series")

                    # Check data freshness
                    last_dt = dts[-1]
                    now = datetime.now()
                    age_hours = (now - last_dt).total_seconds() / 3600

                    info["data_age_hours"] = round(age_hours, 1)

                    # Determine if data is stale
                    if asset and asset.upper() in ["BTC", "ETH", "SOL", "ADA", "DOGE", "XRP"]:
                        # Crypto - should update every 6 hours
                        if age_hours > 12:
                            warnings.append(f"Crypto data is {age_hours:.1f} hours old (expected <12h)")
                    else:
                        # Stocks - should update daily
                        if age_hours > 48:
                            warnings.append(f"Stock data is {age_hours:.1f} hours old (expected <48h)")

        except Exception as e:
            warnings.append(f"Could not parse timestamps for gap analysis: {str(e)}")

        # Determine overall status
        if issues:
            status = "error"
        elif warnings:
            status = "warning"
        else:
            status = "pass"

        return {
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "info": info
        }

    except Exception as e:
        return {
            "status": "error",
            "issues": [f"Error reading file: {str(e)}"],
            "warnings": [],
            "info": {}
        }


def check_all_datasets(asset_filter: Optional[str] = None, timeframe_filter: Optional[str] = None) -> Dict:
    """
    Check data quality for all dataset files in the project.

    Returns dictionary mapping filepath to quality report.
    """
    project_root = Path(__file__).parent.parent
    datasets_dir = project_root / "2. Backtest" / "datasets"

    results = {}

    # Check crypto data
    crypto_dir = datasets_dir / "crypto"
    if crypto_dir.exists():
        for csv_file in crypto_dir.glob("*.csv"):
            filename = csv_file.name
            # Parse filename like "BTC-6h-500wks-data.csv"
            parts = filename.replace("-data.csv", "").split("-")
            if len(parts) >= 2:
                asset = parts[0]
                timeframe = parts[1]

                # Apply filters
                if asset_filter and asset != asset_filter.upper():
                    continue
                if timeframe_filter and timeframe != timeframe_filter:
                    continue

                print_info(f"Checking: {filename}")
                results[str(csv_file.relative_to(project_root))] = check_csv_data_quality(
                    str(csv_file), asset
                )

    # Check stock data
    stocks_dir = datasets_dir / "stocks"
    if stocks_dir.exists():
        for csv_file in stocks_dir.glob("*.csv"):
            filename = csv_file.name

            # Apply filters
            if asset_filter:
                asset = filename.replace(".csv", "").replace("-data", "")
                if asset.upper() != asset_filter.upper():
                    continue

            print_info(f"Checking: {filename}")
            results[str(csv_file.relative_to(project_root))] = check_csv_data_quality(
                str(csv_file)
            )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Check data quality for TradeBot datasets"
    )
    parser.add_argument(
        "--asset",
        help="Filter by asset (e.g., BTC, ETH, AAPL)"
    )
    parser.add_argument(
        "--timeframe",
        help="Filter by timeframe (e.g., 6h, 1d)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )

    args = parser.parse_args()

    print(f"\n{Colors.BOLD}TradeBot Data Quality Check{Colors.RESET}\n")

    results = check_all_datasets(args.asset, args.timeframe)

    if not results:
        print_warning("No data files found to check")
        return 0

    total_files = len(results)
    passed = sum(1 for r in results.values() if r["status"] == "pass")
    warnings = sum(1 for r in results.values() if r["status"] == "warning")
    errors = sum(1 for r in results.values() if r["status"] == "error")

    print(f"\n{Colors.BOLD}Quality Check Results:{Colors.RESET}\n")

    for filepath, report in results.items():
        status = report["status"]

        if status == "pass":
            print_success(f"{filepath}")
        elif status == "warning":
            print_warning(f"{filepath}")
        else:
            print_error(f"{filepath}")

        # Show details
        if args.verbose or status != "pass":
            if report["info"]:
                print(f"  Info:")
                for key, value in report["info"].items():
                    print(f"    - {key}: {value}")

            if report["warnings"]:
                print(f"  Warnings:")
                for warning in report["warnings"]:
                    print(f"    - {warning}")

            if report["issues"]:
                print(f"  Issues:")
                for issue in report["issues"]:
                    print(f"    - {issue}")

            print()

    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Total files checked: {total_files}")
    print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"  {Colors.YELLOW}Warnings: {warnings}{Colors.RESET}")
    print(f"  {Colors.RED}Errors: {errors}{Colors.RESET}")

    if errors > 0:
        print(f"\n{Colors.RED}Data quality issues detected. Fix errors before backtesting.{Colors.RESET}")
        return 1
    elif warnings > 0:
        print(f"\n{Colors.YELLOW}Data quality warnings detected. Review before backtesting.{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.GREEN}All data quality checks passed!{Colors.RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
