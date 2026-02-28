"""
Schema Validation Script for TradeBot Data Files

Validates all CSV and JSON files against schemas defined in docs/DATA_SCHEMAS.md
Run this script before commits or as part of CI/CD pipeline.

Usage:
    python scripts/validate_schemas.py [--file FILE] [--verbose]

Examples:
    python scripts/validate_schemas.py  # Validate all files
    python scripts/validate_schemas.py --file "1. Research/trade_ideas_log.csv"
    python scripts/validate_schemas.py --verbose
"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
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


# Schema Definitions (from docs/DATA_SCHEMAS.md)

TRADE_IDEAS_SCHEMA = {
    "required_columns": [
        "trade_idea_id", "strategy_name", "asset_class", "type",
        "hypothesis", "status", "priority", "created_date",
        "source", "notes", "backtest_result", "sharpe_ratio", "max_drawdown"
    ],
    "enums": {
        "status": ["Pending", "In Research", "Ready for Backtest", "In Backtest",
                   "Completed - Pass", "Completed - Fail", "Archived"],
        "asset_class": ["Crypto", "Stocks", "Options", "Forex", "Commodities"],
        "type": ["Momentum", "Mean Reversion", "Breakout", "Income", "Volatility", "Arbitrage"],
        "priority": ["High", "Medium", "Low"]
    },
    "formats": {
        "trade_idea_id": r"^ti-\d{3}$",  # ti-001, ti-002
        "created_date": "%Y-%m-%d"
    }
}

NEWS_ASSESSMENTS_SCHEMA = {
    "required_columns": [
        "assessment_id", "timestamp", "source", "headline", "category",
        "impact_score", "trade_idea_generated", "trade_idea_id",
        "asset_class", "notes", "manager_reviewed", "manager_decision"
    ],
    "enums": {
        "category": ["Earnings", "Economic Data", "Fed Policy", "Geopolitical",
                     "Regulatory", "Technical", "Sentiment", "Black Swan"],
        "asset_class": ["Crypto", "Stocks", "Options", "Forex", "Commodities"],
        "trade_idea_generated": ["Yes", "No"],
        "manager_reviewed": ["Yes", "No", "Pending"],
        "manager_decision": ["Approved", "Rejected", "Pending", "N/A"]
    },
    "ranges": {
        "impact_score": (1, 10)
    },
    "formats": {
        "assessment_id": r"^na-\d{3}$",  # na-001, na-002
        "timestamp": "%Y-%m-%d %H:%M:%S"
    }
}

ORDER_HISTORY_SCHEMA = {
    "required_columns": [
        "order_id", "timestamp", "symbol", "asset_type", "side", "qty",
        "order_type", "limit_price", "stop_price", "time_in_force",
        "status", "filled_qty", "filled_avg_price", "commission", "environment", "notes"
    ],
    "enums": {
        "asset_type": ["stock", "crypto"],
        "side": ["buy", "sell"],
        "order_type": ["market", "limit", "stop", "stop_limit", "trailing_stop"],
        "time_in_force": ["day", "gtc", "ioc", "fok"],
        "status": ["filled", "partially_filled", "cancelled", "rejected", "pending"],
        "environment": ["paper", "live"]
    }
}

ALERTS_LOG_SCHEMA = {
    "required_columns": [
        "alert_id", "timestamp", "alert_level", "alert_type", "asset_class",
        "message", "portfolio_value", "current_drawdown", "action_taken",
        "manager_notified", "notes"
    ],
    "enums": {
        "alert_level": ["INFO", "CAUTION", "URGENT", "CRITICAL"],
        "alert_type": ["Position Limit", "Drawdown", "VIX Spike", "Circuit Breaker",
                       "Flash Crash", "Liquidation Risk", "Policy Change"],
        "asset_class": ["Crypto", "Stocks", "Options", "Portfolio-Wide"],
        "manager_notified": ["Yes", "No"]
    },
    "formats": {
        "alert_id": r"^alert-\d{4}$",  # alert-0001
        "timestamp": "%Y-%m-%d %H:%M:%S"
    }
}

POLICY_CHANGE_SCHEMA = {
    "required_columns": [
        "timestamp", "old_policy", "new_policy", "trigger_type",
        "trigger_value", "reason", "manager_decision", "notes"
    ],
    "enums": {
        "old_policy": ["HIGH", "MODERATE", "LOW"],
        "new_policy": ["HIGH", "MODERATE", "LOW"],
        "trigger_type": ["VIX", "Drawdown", "Manual", "Circuit Breaker"],
        "manager_decision": ["Approved", "Overridden", "Auto-Approved"]
    },
    "formats": {
        "timestamp": "%Y-%m-%d %H:%M:%S"
    }
}


def validate_csv_file(filepath: str, schema: Dict, verbose: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate a CSV file against a schema definition.

    Returns:
        (is_valid, errors): Tuple of validation status and list of error messages
    """
    errors = []

    if not os.path.exists(filepath):
        errors.append(f"File not found: {filepath}")
        return False, errors

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            # Check required columns
            if headers is None:
                errors.append("CSV file is empty or has no headers")
                return False, errors

            missing_cols = set(schema["required_columns"]) - set(headers)
            if missing_cols:
                errors.append(f"Missing required columns: {', '.join(missing_cols)}")

            extra_cols = set(headers) - set(schema["required_columns"])
            if extra_cols and verbose:
                print_warning(f"Extra columns found: {', '.join(extra_cols)}")

            # Validate each row
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                # Check enum values
                if "enums" in schema:
                    for col, valid_values in schema["enums"].items():
                        if col in row and row[col] and row[col] not in valid_values:
                            errors.append(
                                f"Row {row_num}, column '{col}': Invalid value '{row[col]}'. "
                                f"Must be one of: {', '.join(valid_values)}"
                            )

                # Check ranges
                if "ranges" in schema:
                    for col, (min_val, max_val) in schema["ranges"].items():
                        if col in row and row[col]:
                            try:
                                val = float(row[col])
                                if not (min_val <= val <= max_val):
                                    errors.append(
                                        f"Row {row_num}, column '{col}': Value {val} out of range "
                                        f"[{min_val}, {max_val}]"
                                    )
                            except ValueError:
                                errors.append(
                                    f"Row {row_num}, column '{col}': '{row[col]}' is not a valid number"
                                )

                # Check date formats
                if "formats" in schema:
                    for col, fmt in schema["formats"].items():
                        if col in row and row[col]:
                            # Check regex patterns
                            if fmt.startswith("^"):
                                import re
                                if not re.match(fmt, row[col]):
                                    errors.append(
                                        f"Row {row_num}, column '{col}': '{row[col]}' doesn't match "
                                        f"expected format"
                                    )
                            # Check date formats
                            elif "%" in fmt:
                                try:
                                    datetime.strptime(row[col], fmt)
                                except ValueError:
                                    errors.append(
                                        f"Row {row_num}, column '{col}': '{row[col]}' doesn't match "
                                        f"date format '{fmt}'"
                                    )

    except Exception as e:
        errors.append(f"Error reading CSV: {str(e)}")
        return False, errors

    return len(errors) == 0, errors


def validate_json_file(filepath: str, expected_structure: Dict, verbose: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate a JSON file against expected structure.

    Returns:
        (is_valid, errors): Tuple of validation status and list of error messages
    """
    errors = []

    if not os.path.exists(filepath):
        errors.append(f"File not found: {filepath}")
        return False, errors

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check required keys
        if "required_keys" in expected_structure:
            for key in expected_structure["required_keys"]:
                if key not in data:
                    errors.append(f"Missing required key: '{key}'")

        # Check enum values
        if "enums" in expected_structure:
            for key, valid_values in expected_structure["enums"].items():
                if key in data and data[key] not in valid_values:
                    errors.append(
                        f"Key '{key}': Invalid value '{data[key]}'. "
                        f"Must be one of: {', '.join(valid_values)}"
                    )

        # Check types
        if "types" in expected_structure:
            for key, expected_type in expected_structure["types"].items():
                if key in data:
                    if expected_type == "number" and not isinstance(data[key], (int, float)):
                        errors.append(f"Key '{key}': Expected number, got {type(data[key]).__name__}")
                    elif expected_type == "string" and not isinstance(data[key], str):
                        errors.append(f"Key '{key}': Expected string, got {type(data[key]).__name__}")
                    elif expected_type == "array" and not isinstance(data[key], list):
                        errors.append(f"Key '{key}': Expected array, got {type(data[key]).__name__}")
                    elif expected_type == "object" and not isinstance(data[key], dict):
                        errors.append(f"Key '{key}': Expected object, got {type(data[key]).__name__}")

    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {str(e)}")
        return False, errors
    except Exception as e:
        errors.append(f"Error reading JSON: {str(e)}")
        return False, errors

    return len(errors) == 0, errors


# JSON schema definitions
ACTIVE_POLICY_STRUCTURE = {
    "required_keys": ["policy", "timestamp", "reason"],
    "enums": {
        "policy": ["HIGH", "MODERATE", "LOW"]
    }
}

PORTFOLIO_HEALTH_STRUCTURE = {
    "required_keys": ["timestamp", "total_value", "peak_value", "drawdown_pct"],
    "types": {
        "total_value": "number",
        "peak_value": "number",
        "drawdown_pct": "number",
        "positions": "array"
    }
}


def validate_all_files(verbose: bool = False) -> Dict[str, Tuple[bool, List[str]]]:
    """
    Validate all known data files in the TradeBot project.

    Returns:
        Dictionary mapping filepath to (is_valid, errors)
    """
    project_root = Path(__file__).parent.parent

    files_to_validate = {
        # CSV files
        "data/logs/trade_ideas_log.csv": TRADE_IDEAS_SCHEMA,
        "data/logs/news_assessments_log.csv": NEWS_ASSESSMENTS_SCHEMA,
        "data/logs/order_history.csv": ORDER_HISTORY_SCHEMA,
        "data/logs/alerts_log.csv": ALERTS_LOG_SCHEMA,
        "data/logs/policy_change_history.csv": POLICY_CHANGE_SCHEMA,
    }

    json_files = {
        "data/state/active_policy.json": ACTIVE_POLICY_STRUCTURE,
        "data/state/portfolio_health.json": PORTFOLIO_HEALTH_STRUCTURE,
    }

    results = {}

    # Validate CSV files
    for rel_path, schema in files_to_validate.items():
        filepath = project_root / rel_path
        if verbose:
            print_info(f"Validating CSV: {rel_path}")

        is_valid, errors = validate_csv_file(str(filepath), schema, verbose)
        results[rel_path] = (is_valid, errors)

    # Validate JSON files
    for rel_path, structure in json_files.items():
        filepath = project_root / rel_path
        if verbose:
            print_info(f"Validating JSON: {rel_path}")

        is_valid, errors = validate_json_file(str(filepath), structure, verbose)
        results[rel_path] = (is_valid, errors)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate TradeBot data files against schemas"
    )
    parser.add_argument(
        "--file",
        help="Validate a specific file instead of all files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed validation information"
    )

    args = parser.parse_args()

    print(f"\n{Colors.BOLD}TradeBot Schema Validation{Colors.RESET}\n")

    if args.file:
        # Validate single file
        if args.file.endswith('.csv'):
            # Determine schema based on filename
            if "trade_ideas_log" in args.file:
                schema = TRADE_IDEAS_SCHEMA
            elif "news_assessments" in args.file:
                schema = NEWS_ASSESSMENTS_SCHEMA
            elif "order_history" in args.file:
                schema = ORDER_HISTORY_SCHEMA
            elif "alerts_log" in args.file:
                schema = ALERTS_LOG_SCHEMA
            elif "policy_change" in args.file:
                schema = POLICY_CHANGE_SCHEMA
            else:
                print_error(f"Unknown CSV file type: {args.file}")
                return 1

            is_valid, errors = validate_csv_file(args.file, schema, args.verbose)

        elif args.file.endswith('.json'):
            if "active_policy" in args.file:
                structure = ACTIVE_POLICY_STRUCTURE
            elif "portfolio_health" in args.file:
                structure = PORTFOLIO_HEALTH_STRUCTURE
            else:
                print_error(f"Unknown JSON file type: {args.file}")
                return 1

            is_valid, errors = validate_json_file(args.file, structure, args.verbose)

        else:
            print_error(f"Unsupported file type: {args.file}")
            return 1

        if is_valid:
            print_success(f"Validation passed: {args.file}")
            return 0
        else:
            print_error(f"Validation failed: {args.file}")
            for error in errors:
                print(f"  - {error}")
            return 1

    else:
        # Validate all files
        results = validate_all_files(args.verbose)

        total_files = len(results)
        passed = sum(1 for is_valid, _ in results.values() if is_valid)
        failed = total_files - passed

        print(f"\n{Colors.BOLD}Validation Summary:{Colors.RESET}\n")

        for filepath, (is_valid, errors) in results.items():
            if is_valid:
                print_success(f"{filepath}")
            else:
                print_error(f"{filepath}")
                if args.verbose:
                    for error in errors:
                        print(f"    - {error}")

        print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
        print(f"  Total files: {total_files}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {failed}{Colors.RESET}")

        if failed > 0:
            print(f"\n{Colors.YELLOW}Run with --verbose to see detailed errors{Colors.RESET}")
            return 1
        else:
            print(f"\n{Colors.GREEN}All validations passed!{Colors.RESET}")
            return 0


if __name__ == "__main__":
    sys.exit(main())
