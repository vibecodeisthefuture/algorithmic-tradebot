#!/usr/bin/env python3
"""
System Health Check for TradeBot

Monitors system health and data quality to ensure reliable trading operations.
Designed to run periodically via scheduler for proactive issue detection.

Usage:
    python health_check.py                    # Run all health checks
    python health_check.py --critical-only    # Only critical checks
    python health_check.py --log-alerts       # Log alerts to alerts_log.csv
    python health_check.py --json             # Output as JSON

Health Checks:
    1. Data freshness (crypto < 12h, stocks < 24h)
    2. Disk space availability (> 10% free)
    3. File integrity (critical files exist)
    4. Schema compliance (CSV/JSON validation)
    5. Log file analysis (recent errors)
    6. Backup status (last backup < 2 days)
    7. Portfolio data consistency

Alert Levels:
    INFO     - Informational, no action needed
    CAUTION  - Minor issue, monitor
    URGENT   - Requires attention soon
    CRITICAL - Immediate action required

Author: TradeBot System
Date: 2026-02-03
"""

import os
import sys
import json
import csv
import logging
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Add project to path
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Health check thresholds
THRESHOLDS = {
    "crypto_data_max_age_hours": 12,
    "stock_data_max_age_hours": 24,
    "min_disk_space_pct": 10.0,
    "max_log_errors_per_day": 50,
    "max_backup_age_days": 2,
    "min_portfolio_update_hours": 4,
}

# Critical files that must exist
CRITICAL_FILES = [
    "docs/DELEGATION_RULES.md",
    "docs/RISK_POLICY_FRAMEWORK.md",
    "docs/STRATEGY_REGISTRY.md",
    "docs/DATA_SCHEMAS.md",
    "config/system_config.yaml",
    "2. Backtest/TEST_INDEX.md",
]

# Directories to check
DATA_DIRS = {
    "crypto_cache": PROJECT_ROOT / "2. Backtest" / "datasets" / "data_tables",
    "backups": PROJECT_ROOT / "backups",
    "logs": PROJECT_ROOT / "logs",
    "portfolio": PROJECT_ROOT / "3. Implement" / "PortfolioTracker",
}

# Alerts log
ALERTS_LOG = PROJECT_ROOT / "logs" / "alerts_log.csv"

# Log file
LOG_FILE = PROJECT_ROOT / "logs" / "health_check.log"


# ============================================================================
# Alert Levels
# ============================================================================

class AlertLevel:
    """Alert severity levels."""
    INFO = "INFO"
    CAUTION = "CAUTION"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


# ============================================================================
# Health Check Result
# ============================================================================

class HealthCheckResult:
    """Container for health check results."""

    def __init__(self):
        self.checks = []
        self.alerts = []
        self.timestamp = datetime.now()

    def add_check(self, name: str, status: str, message: str, alert_level: str = AlertLevel.INFO):
        """
        Add a health check result.

        Args:
            name: Check name
            status: PASS, WARN, or FAIL
            message: Description
            alert_level: Alert severity
        """
        self.checks.append({
            "name": name,
            "status": status,
            "message": message,
            "alert_level": alert_level,
            "timestamp": self.timestamp.isoformat()
        })

        # Add to alerts if not INFO
        if alert_level != AlertLevel.INFO and status in ["WARN", "FAIL"]:
            self.alerts.append({
                "check": name,
                "level": alert_level,
                "message": message,
                "timestamp": self.timestamp.isoformat()
            })

    def get_summary(self) -> Dict:
        """Get summary statistics."""
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["status"] == "PASS")
        warned = sum(1 for c in self.checks if c["status"] == "WARN")
        failed = sum(1 for c in self.checks if c["status"] == "FAIL")

        alert_counts = defaultdict(int)
        for alert in self.alerts:
            alert_counts[alert["level"]] += 1

        return {
            "total_checks": total,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "alerts_critical": alert_counts[AlertLevel.CRITICAL],
            "alerts_urgent": alert_counts[AlertLevel.URGENT],
            "alerts_caution": alert_counts[AlertLevel.CAUTION],
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(verbose: bool = False):
    """Configure logging."""
    LOG_FILE.parent.mkdir(exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


# ============================================================================
# Health Checks
# ============================================================================

def check_data_freshness(result: HealthCheckResult):
    """Check if market data is up to date."""
    cache_dir = DATA_DIRS["crypto_cache"]

    if not cache_dir.exists():
        result.add_check(
            "Data Freshness",
            "FAIL",
            f"Cache directory not found: {cache_dir}",
            AlertLevel.CRITICAL
        )
        return

    # Check crypto data files
    crypto_files = list(cache_dir.glob("*-*-*.csv"))  # e.g., BTC-1h-1000wks-data.csv

    if not crypto_files:
        result.add_check(
            "Data Freshness",
            "WARN",
            "No crypto data files found in cache",
            AlertLevel.CAUTION
        )
        return

    now = datetime.now()
    stale_files = []

    for filepath in crypto_files:
        try:
            stat = filepath.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age_hours = (now - mtime).total_seconds() / 3600

            # Crypto data should be < 12 hours old
            if age_hours > THRESHOLDS["crypto_data_max_age_hours"]:
                stale_files.append(f"{filepath.name} ({age_hours:.1f}h old)")

        except Exception as e:
            logging.error(f"Error checking {filepath}: {e}")

    if stale_files:
        alert_level = AlertLevel.URGENT if len(stale_files) > 3 else AlertLevel.CAUTION
        result.add_check(
            "Data Freshness",
            "WARN",
            f"{len(stale_files)} files stale: {', '.join(stale_files[:3])}",
            alert_level
        )
    else:
        result.add_check(
            "Data Freshness",
            "PASS",
            f"All {len(crypto_files)} crypto data files fresh",
            AlertLevel.INFO
        )


def check_disk_space(result: HealthCheckResult):
    """Check available disk space."""
    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        free_pct = (usage.free / usage.total) * 100
        free_gb = usage.free / (1024 ** 3)

        if free_pct < THRESHOLDS["min_disk_space_pct"]:
            result.add_check(
                "Disk Space",
                "FAIL",
                f"Low disk space: {free_pct:.1f}% free ({free_gb:.1f} GB)",
                AlertLevel.CRITICAL
            )
        elif free_pct < 20:
            result.add_check(
                "Disk Space",
                "WARN",
                f"Disk space getting low: {free_pct:.1f}% free ({free_gb:.1f} GB)",
                AlertLevel.CAUTION
            )
        else:
            result.add_check(
                "Disk Space",
                "PASS",
                f"Disk space OK: {free_pct:.1f}% free ({free_gb:.1f} GB)",
                AlertLevel.INFO
            )

    except Exception as e:
        result.add_check(
            "Disk Space",
            "FAIL",
            f"Error checking disk space: {e}",
            AlertLevel.URGENT
        )


def check_critical_files(result: HealthCheckResult):
    """Check that critical files exist."""
    missing_files = []

    for filepath in CRITICAL_FILES:
        full_path = PROJECT_ROOT / filepath
        if not full_path.exists():
            missing_files.append(filepath)

    if missing_files:
        result.add_check(
            "Critical Files",
            "FAIL",
            f"Missing files: {', '.join(missing_files)}",
            AlertLevel.CRITICAL
        )
    else:
        result.add_check(
            "Critical Files",
            "PASS",
            f"All {len(CRITICAL_FILES)} critical files present",
            AlertLevel.INFO
        )


def check_backup_status(result: HealthCheckResult):
    """Check last backup timestamp."""
    backup_dir = DATA_DIRS["backups"]
    manifest_file = backup_dir / "backup_manifest.json"

    if not manifest_file.exists():
        result.add_check(
            "Backup Status",
            "WARN",
            "No backup manifest found - backups may not be configured",
            AlertLevel.CAUTION
        )
        return

    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        backups = manifest.get("backups", [])

        if not backups:
            result.add_check(
                "Backup Status",
                "WARN",
                "No backups found in manifest",
                AlertLevel.CAUTION
            )
            return

        # Get most recent backup
        latest_backup = backups[-1]
        backup_time = datetime.fromisoformat(latest_backup["timestamp"])
        age_hours = (datetime.now() - backup_time).total_seconds() / 3600
        age_days = age_hours / 24

        if age_days > THRESHOLDS["max_backup_age_days"]:
            result.add_check(
                "Backup Status",
                "WARN",
                f"Last backup {age_days:.1f} days ago (expected < {THRESHOLDS['max_backup_age_days']}d)",
                AlertLevel.URGENT
            )
        else:
            result.add_check(
                "Backup Status",
                "PASS",
                f"Last backup {age_hours:.1f}h ago ({latest_backup['file_count']} files)",
                AlertLevel.INFO
            )

    except Exception as e:
        result.add_check(
            "Backup Status",
            "FAIL",
            f"Error checking backup status: {e}",
            AlertLevel.URGENT
        )


def check_log_errors(result: HealthCheckResult):
    """Check recent log files for errors."""
    log_dir = DATA_DIRS["logs"]

    if not log_dir.exists():
        result.add_check(
            "Log Analysis",
            "WARN",
            "Logs directory not found",
            AlertLevel.CAUTION
        )
        return

    # Analyze logs from last 24 hours
    cutoff_time = datetime.now() - timedelta(days=1)
    error_count = 0
    critical_errors = []

    log_files = list(log_dir.glob("*.log"))

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Simple error detection (lines containing ERROR or CRITICAL)
                    if 'ERROR' in line or 'CRITICAL' in line:
                        error_count += 1
                        if 'CRITICAL' in line:
                            critical_errors.append(line.strip()[:100])

        except Exception as e:
            logging.debug(f"Error reading {log_file}: {e}")

    if error_count > THRESHOLDS["max_log_errors_per_day"]:
        alert_level = AlertLevel.URGENT if critical_errors else AlertLevel.CAUTION
        result.add_check(
            "Log Analysis",
            "WARN",
            f"High error count in last 24h: {error_count} errors ({len(critical_errors)} critical)",
            alert_level
        )
    elif critical_errors:
        result.add_check(
            "Log Analysis",
            "WARN",
            f"Found {len(critical_errors)} critical errors in last 24h",
            AlertLevel.CAUTION
        )
    else:
        result.add_check(
            "Log Analysis",
            "PASS",
            f"Log health OK: {error_count} errors in last 24h",
            AlertLevel.INFO
        )


def check_directory_structure(result: HealthCheckResult):
    """Check that required directories exist."""
    missing_dirs = []

    for name, dirpath in DATA_DIRS.items():
        if not dirpath.exists():
            missing_dirs.append(f"{name} ({dirpath})")

    if missing_dirs:
        result.add_check(
            "Directory Structure",
            "WARN",
            f"Missing directories: {', '.join(missing_dirs)}",
            AlertLevel.CAUTION
        )
    else:
        result.add_check(
            "Directory Structure",
            "PASS",
            f"All {len(DATA_DIRS)} required directories present",
            AlertLevel.INFO
        )


def check_schema_compliance(result: HealthCheckResult):
    """Quick schema compliance check on key files."""
    try:
        # Import schema validator
        from validate_schemas import validate_csv_file, SCHEMAS

        # Check TRADE_IDEAS.csv if it exists
        trade_ideas_file = PROJECT_ROOT / "1. Research" / "TRADE_IDEAS.csv"

        if trade_ideas_file.exists():
            schema = SCHEMAS.get("trade_ideas", {})
            if schema:
                is_valid, errors = validate_csv_file(str(trade_ideas_file), schema, verbose=False)

                if not is_valid:
                    result.add_check(
                        "Schema Compliance",
                        "WARN",
                        f"TRADE_IDEAS.csv has {len(errors)} validation errors",
                        AlertLevel.CAUTION
                    )
                else:
                    result.add_check(
                        "Schema Compliance",
                        "PASS",
                        "TRADE_IDEAS.csv schema valid",
                        AlertLevel.INFO
                    )
            else:
                result.add_check(
                    "Schema Compliance",
                    "WARN",
                    "Trade ideas schema not found",
                    AlertLevel.CAUTION
                )
        else:
            result.add_check(
                "Schema Compliance",
                "PASS",
                "TRADE_IDEAS.csv not yet created (OK)",
                AlertLevel.INFO
            )

    except ImportError:
        result.add_check(
            "Schema Compliance",
            "WARN",
            "Schema validator not available",
            AlertLevel.CAUTION
        )
    except Exception as e:
        result.add_check(
            "Schema Compliance",
            "FAIL",
            f"Error validating schemas: {e}",
            AlertLevel.CAUTION
        )


# ============================================================================
# Alert Logging
# ============================================================================

def log_alerts_to_csv(alerts: List[Dict]):
    """
    Log alerts to alerts_log.csv for AI Manager review.

    Args:
        alerts: List of alert dictionaries
    """
    if not alerts:
        return

    ALERTS_LOG.parent.mkdir(exist_ok=True)

    # Check if file exists to determine if we need header
    file_exists = ALERTS_LOG.exists()

    try:
        with open(ALERTS_LOG, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ["timestamp", "level", "check", "message"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            for alert in alerts:
                writer.writerow({
                    "timestamp": alert["timestamp"],
                    "level": alert["level"],
                    "check": alert["check"],
                    "message": alert["message"]
                })

        logging.info(f"Logged {len(alerts)} alerts to {ALERTS_LOG}")

    except Exception as e:
        logging.error(f"Error logging alerts: {e}")


# ============================================================================
# Main Health Check Runner
# ============================================================================

def run_health_checks(critical_only: bool = False) -> HealthCheckResult:
    """
    Run all health checks.

    Args:
        critical_only: If True, only run critical checks

    Returns:
        HealthCheckResult object
    """
    result = HealthCheckResult()

    logging.info("=" * 60)
    logging.info("Starting health checks...")

    # Critical checks (always run)
    check_disk_space(result)
    check_critical_files(result)
    check_data_freshness(result)

    if not critical_only:
        # Non-critical checks
        check_backup_status(result)
        check_log_errors(result)
        check_directory_structure(result)
        check_schema_compliance(result)

    logging.info("Health checks complete")

    return result


# ============================================================================
# Output Formatting
# ============================================================================

def print_results(result: HealthCheckResult, json_output: bool = False):
    """Print health check results."""
    summary = result.get_summary()

    if json_output:
        # JSON output for programmatic use
        output = {
            "summary": summary,
            "checks": result.checks,
            "alerts": result.alerts
        }
        print(json.dumps(output, indent=2))
        return

    # Human-readable output
    print("\n" + "=" * 60)
    print("HEALTH CHECK RESULTS")
    print("=" * 60)

    # Summary
    print(f"\nChecks: {summary['passed']}/{summary['total_checks']} passed")
    if summary['warned'] > 0:
        print(f"Warnings: {summary['warned']}")
    if summary['failed'] > 0:
        print(f"Failures: {summary['failed']}")

    # Alerts by level
    if summary['alerts_critical'] > 0:
        print(f"\n❌ CRITICAL alerts: {summary['alerts_critical']}")
    if summary['alerts_urgent'] > 0:
        print(f"⚠️  URGENT alerts: {summary['alerts_urgent']}")
    if summary['alerts_caution'] > 0:
        print(f"⚡ CAUTION alerts: {summary['alerts_caution']}")

    # Details
    print("\n" + "-" * 60)
    print("CHECK DETAILS")
    print("-" * 60)

    for check in result.checks:
        status_icon = "✅" if check["status"] == "PASS" else "❌" if check["status"] == "FAIL" else "⚠️"
        print(f"\n{status_icon} {check['name']}: {check['status']}")
        print(f"   {check['message']}")
        if check['alert_level'] != AlertLevel.INFO:
            print(f"   Alert Level: {check['alert_level']}")

    # Overall status
    print("\n" + "=" * 60)
    if summary['failed'] > 0 or summary['alerts_critical'] > 0:
        print("❌ SYSTEM STATUS: UNHEALTHY - Immediate attention required")
    elif summary['warned'] > 0 or summary['alerts_urgent'] > 0:
        print("⚠️  SYSTEM STATUS: DEGRADED - Action recommended")
    else:
        print("✅ SYSTEM STATUS: HEALTHY")
    print("=" * 60)


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="System health check for TradeBot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Only run critical checks (faster)"
    )
    parser.add_argument(
        "--log-alerts",
        action="store_true",
        help="Log alerts to alerts_log.csv"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    try:
        # Run health checks
        result = run_health_checks(args.critical_only)

        # Log alerts if requested
        if args.log_alerts and result.alerts:
            log_alerts_to_csv(result.alerts)

        # Print results
        print_results(result, args.json)

        # Exit code based on health status
        summary = result.get_summary()
        if summary['failed'] > 0:
            return 2  # Critical failure
        elif summary['warned'] > 0:
            return 1  # Warnings
        else:
            return 0  # All good

    except KeyboardInterrupt:
        logging.info("\nHealth check interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
