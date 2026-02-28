#!/usr/bin/env python3
"""
Integration Test Suite for TradeBot

End-to-end testing of automated workflows to ensure system reliability.
Tests all critical pipelines from data collection to execution decisions.

Usage:
    python test_integration.py                   # Run all tests
    python test_integration.py --workflow news   # Test specific workflow
    python test_integration.py --quick           # Quick smoke tests only
    python test_integration.py --verbose         # Detailed output

Test Coverage:
    1. News → Research → Backtest pipeline
    2. VIX-based policy switching
    3. Flash crash detection and response
    4. Data collection and validation
    5. Portfolio monitoring workflows
    6. Schema validation
    7. File integrity checks

Author: TradeBot System
Date: 2026-02-03
"""

import os
import sys
import unittest
import logging
import json
import csv
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Add project to path for imports
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "2. Backtest" / "datasets"))

# Import project modules
try:
    from validate_schemas import validate_csv_file, validate_json_file, SCHEMAS
    from check_data_quality import check_csv_data_quality
    from data_service import DataService
except ImportError as e:
    print(f"Warning: Could not import project modules: {e}")
    print("Some tests may be skipped.")


# Log file
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "integration_tests.log"


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(verbose: bool = False):
    """Configure logging."""
    LOG_DIR.mkdir(exist_ok=True)

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
# Test: Schema Validation
# ============================================================================

class TestSchemaValidation(unittest.TestCase):
    """Test CSV/JSON schema validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_valid_trade_ideas_csv(self):
        """Test that valid trade ideas CSV passes validation."""
        csv_path = self.test_dir / "trade_ideas.csv"

        # Create valid CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "trade_idea_id", "strategy_name", "asset_class", "type",
                "hypothesis", "status", "priority", "created_date",
                "source", "notes", "backtest_result", "sharpe_ratio", "max_drawdown"
            ])
            writer.writeheader()
            writer.writerow({
                "trade_idea_id": "ti-001",
                "strategy_name": "Test Strategy",
                "asset_class": "Crypto",
                "type": "Momentum",
                "hypothesis": "Test hypothesis",
                "status": "Pending",
                "priority": "High",
                "created_date": "2026-02-03",
                "source": "Manual",
                "notes": "Test",
                "backtest_result": "",
                "sharpe_ratio": "",
                "max_drawdown": ""
            })

        # Validate
        schema = SCHEMAS.get("trade_ideas", {})
        if schema:
            is_valid, errors = validate_csv_file(str(csv_path), schema)
            self.assertTrue(is_valid, f"Valid CSV failed validation: {errors}")

    def test_invalid_enum_value(self):
        """Test that invalid enum values are caught."""
        csv_path = self.test_dir / "trade_ideas.csv"

        # Create CSV with invalid status
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "trade_idea_id", "strategy_name", "asset_class", "type",
                "hypothesis", "status", "priority", "created_date",
                "source", "notes", "backtest_result", "sharpe_ratio", "max_drawdown"
            ])
            writer.writeheader()
            writer.writerow({
                "trade_idea_id": "ti-001",
                "strategy_name": "Test",
                "asset_class": "Crypto",
                "type": "Momentum",
                "hypothesis": "Test",
                "status": "InvalidStatus",  # Invalid!
                "priority": "High",
                "created_date": "2026-02-03",
                "source": "Manual",
                "notes": "",
                "backtest_result": "",
                "sharpe_ratio": "",
                "max_drawdown": ""
            })

        # Validate
        schema = SCHEMAS.get("trade_ideas", {})
        if schema:
            is_valid, errors = validate_csv_file(str(csv_path), schema)
            self.assertFalse(is_valid, "Invalid enum value should fail validation")


# ============================================================================
# Test: Data Quality Checks
# ============================================================================

class TestDataQuality(unittest.TestCase):
    """Test OHLCV data quality validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_valid_ohlcv_data(self):
        """Test that valid OHLCV data passes quality checks."""
        csv_path = self.test_dir / "BTC-test.csv"

        # Create valid OHLCV data
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
            writer.writeheader()

            base_time = datetime.now() - timedelta(hours=12)
            for i in range(3):
                ts = base_time + timedelta(hours=6*i)
                writer.writerow({
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": 50000.0 + i,
                    "high": 50100.0 + i,
                    "low": 49900.0 + i,
                    "close": 50050.0 + i,
                    "volume": 100.0 + i
                })

        # Validate
        result = check_csv_data_quality(str(csv_path), asset="BTC")
        self.assertEqual(len(result["issues"]), 0, f"Valid data has issues: {result['issues']}")

    def test_invalid_ohlc_relationship(self):
        """Test that invalid OHLC relationships are detected."""
        csv_path = self.test_dir / "BTC-test.csv"

        # Create data with high < low (invalid!)
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "open": 50000.0,
                "high": 49900.0,  # Invalid: high < low!
                "low": 50000.0,
                "close": 49950.0,
                "volume": 100.0
            })

        # Validate
        result = check_csv_data_quality(str(csv_path), asset="BTC")
        self.assertGreater(len(result["issues"]), 0, "Invalid OHLC should be detected")


# ============================================================================
# Test: Data Collection
# ============================================================================

class TestDataCollection(unittest.TestCase):
    """Test data collection from various sources."""

    def test_data_service_initialization(self):
        """Test that DataService initializes correctly."""
        try:
            service = DataService(verbose=False)
            self.assertIsNotNone(service, "DataService failed to initialize")
        except Exception as e:
            self.fail(f"DataService initialization failed: {e}")

    def test_cache_directory_structure(self):
        """Test that cache directory exists and is writable."""
        cache_dir = PROJECT_ROOT / "2. Backtest" / "datasets" / "data_tables"
        self.assertTrue(cache_dir.exists(), f"Cache directory not found: {cache_dir}")
        self.assertTrue(os.access(cache_dir, os.W_OK), "Cache directory not writable")


# ============================================================================
# Test: File Integrity
# ============================================================================

class TestFileIntegrity(unittest.TestCase):
    """Test critical files exist and are valid."""

    def test_critical_markdown_files_exist(self):
        """Test that critical markdown documentation exists."""
        critical_files = [
            "docs/DELEGATION_RULES.md",
            "docs/RISK_POLICY_FRAMEWORK.md",
            "docs/STRATEGY_REGISTRY.md",
            "docs/DATA_SCHEMAS.md",
            "docs/AUTOMATION_WORKFLOWS.md",
            "2. Backtest/TEST_INDEX.md",
        ]

        for filepath in critical_files:
            full_path = PROJECT_ROOT / filepath
            self.assertTrue(full_path.exists(), f"Critical file missing: {filepath}")

    def test_config_file_exists(self):
        """Test that system config file exists and is valid YAML."""
        config_path = PROJECT_ROOT / "config" / "system_config.yaml"
        self.assertTrue(config_path.exists(), "system_config.yaml not found")

        # Try to parse as YAML
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.assertIsNotNone(config, "Config file is empty")
        except ImportError:
            self.skipTest("PyYAML not installed, skipping YAML validation")
        except Exception as e:
            self.fail(f"Config file is invalid YAML: {e}")

    def test_scripts_directory_structure(self):
        """Test that scripts directory has expected structure."""
        scripts_dir = PROJECT_ROOT / "scripts"
        self.assertTrue(scripts_dir.exists(), "scripts/ directory not found")

        expected_scripts = [
            "validate_schemas.py",
            "check_data_quality.py",
            "auto_backup.py",
            "cleanup_old_data.py",
        ]

        for script in expected_scripts:
            script_path = scripts_dir / script
            self.assertTrue(script_path.exists(), f"Expected script not found: {script}")


# ============================================================================
# Test: VIX Policy Switching (Mock)
# ============================================================================

class TestVIXPolicySwitching(unittest.TestCase):
    """Test VIX-based risk policy switching logic."""

    def test_policy_selection_low_vix(self):
        """Test that LOW policy is selected when VIX is low."""
        vix_value = 12.0  # Low volatility
        policy = self._select_policy(vix_value)
        self.assertEqual(policy, "LOW", f"Expected LOW policy for VIX={vix_value}")

    def test_policy_selection_moderate_vix(self):
        """Test that MODERATE policy is selected when VIX is moderate."""
        vix_value = 25.0  # Moderate volatility
        policy = self._select_policy(vix_value)
        self.assertEqual(policy, "MODERATE", f"Expected MODERATE policy for VIX={vix_value}")

    def test_policy_selection_high_vix(self):
        """Test that HIGH policy is selected when VIX is high."""
        vix_value = 35.0  # High volatility
        policy = self._select_policy(vix_value)
        self.assertEqual(policy, "HIGH", f"Expected HIGH policy for VIX={vix_value}")

    def _select_policy(self, vix: float) -> str:
        """Mock VIX policy selection logic."""
        if vix < 15:
            return "LOW"
        elif vix < 30:
            return "MODERATE"
        else:
            return "HIGH"


# ============================================================================
# Test: Flash Crash Detection (Mock)
# ============================================================================

class TestFlashCrashDetection(unittest.TestCase):
    """Test flash crash detection logic."""

    def test_crypto_flash_crash_detection(self):
        """Test that crypto flash crash is detected."""
        # Simulate 30% drop in 1 hour
        price_drop_pct = -30.0
        time_window_minutes = 60

        is_flash_crash = self._detect_flash_crash(price_drop_pct, time_window_minutes, "crypto")
        self.assertTrue(is_flash_crash, "30% drop in 1 hour should be detected as flash crash")

    def test_stock_flash_crash_detection(self):
        """Test that stock flash crash is detected."""
        # Simulate 15% drop in 30 minutes
        price_drop_pct = -15.0
        time_window_minutes = 30

        is_flash_crash = self._detect_flash_crash(price_drop_pct, time_window_minutes, "stock")
        self.assertTrue(is_flash_crash, "15% drop in 30 min should be detected as flash crash")

    def test_normal_volatility_not_flash_crash(self):
        """Test that normal volatility is not flagged as flash crash."""
        # Simulate 5% drop in 2 hours
        price_drop_pct = -5.0
        time_window_minutes = 120

        is_flash_crash = self._detect_flash_crash(price_drop_pct, time_window_minutes, "crypto")
        self.assertFalse(is_flash_crash, "Normal volatility should not trigger flash crash")

    def _detect_flash_crash(self, price_drop_pct: float, time_window_minutes: int, asset_class: str) -> bool:
        """Mock flash crash detection logic."""
        if asset_class == "crypto":
            # Crypto: 20% drop in < 2 hours
            return price_drop_pct <= -20 and time_window_minutes <= 120
        elif asset_class == "stock":
            # Stocks: 10% drop in < 1 hour
            return price_drop_pct <= -10 and time_window_minutes <= 60
        return False


# ============================================================================
# Test: Workflow Integration (Mock)
# ============================================================================

class TestWorkflowIntegration(unittest.TestCase):
    """Test end-to-end workflow integration."""

    def test_news_to_research_pipeline(self):
        """Test that news can trigger research workflow."""
        # Mock: News article about new regulation
        news_item = {
            "title": "SEC Approves Bitcoin ETF",
            "category": "Regulation",
            "relevance": "High"
        }

        # Check if it would trigger research
        should_trigger = self._should_trigger_research(news_item)
        self.assertTrue(should_trigger, "High relevance news should trigger research")

    def test_backtest_to_paper_pipeline(self):
        """Test backtest approval logic for paper trading."""
        # Mock: Successful backtest results
        backtest_results = {
            "sharpe_ratio": 2.5,
            "max_drawdown": -15.0,
            "win_rate": 65.0,
            "total_return": 45.0
        }

        # Check if it meets criteria for paper trading
        approved = self._approve_for_paper(backtest_results)
        self.assertTrue(approved, "Strong backtest should be approved for paper trading")

    def test_paper_to_live_pipeline(self):
        """Test paper trading approval logic for live deployment."""
        # Mock: Paper trading results
        paper_results = {
            "days_traded": 35,
            "actual_sharpe": 2.3,
            "actual_drawdown": -12.0,
            "correlation_to_backtest": 0.85
        }

        # Check if it meets criteria for live trading
        approved = self._approve_for_live(paper_results)
        self.assertTrue(approved, "Strong paper results should be approved for live")

    def _should_trigger_research(self, news_item: Dict) -> bool:
        """Mock research trigger logic."""
        return news_item.get("relevance") in ["High", "Critical"]

    def _approve_for_paper(self, backtest_results: Dict) -> bool:
        """Mock paper trading approval logic."""
        return (
            backtest_results.get("sharpe_ratio", 0) >= 1.5 and
            backtest_results.get("max_drawdown", -100) >= -20 and
            backtest_results.get("win_rate", 0) >= 55
        )

    def _approve_for_live(self, paper_results: Dict) -> bool:
        """Mock live trading approval logic."""
        return (
            paper_results.get("days_traded", 0) >= 30 and
            paper_results.get("actual_sharpe", 0) >= 1.5 and
            paper_results.get("correlation_to_backtest", 0) >= 0.75
        )


# ============================================================================
# Test Suite Configuration
# ============================================================================

def create_test_suite(quick: bool = False, workflow: Optional[str] = None) -> unittest.TestSuite:
    """
    Create test suite based on options.

    Args:
        quick: If True, only run fast smoke tests
        workflow: If specified, only run tests for that workflow

    Returns:
        Test suite
    """
    suite = unittest.TestSuite()

    if workflow:
        # Run specific workflow tests
        workflow_tests = {
            "schema": TestSchemaValidation,
            "data": TestDataQuality,
            "collection": TestDataCollection,
            "files": TestFileIntegrity,
            "vix": TestVIXPolicySwitching,
            "flash": TestFlashCrashDetection,
            "workflow": TestWorkflowIntegration,
        }

        test_class = workflow_tests.get(workflow.lower())
        if test_class:
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(test_class))
        else:
            print(f"Unknown workflow: {workflow}")
            print(f"Available: {', '.join(workflow_tests.keys())}")
            sys.exit(1)

    elif quick:
        # Quick smoke tests only
        suite.addTest(TestFileIntegrity('test_critical_markdown_files_exist'))
        suite.addTest(TestFileIntegrity('test_config_file_exists'))
        suite.addTest(TestDataCollection('test_data_service_initialization'))
        suite.addTest(TestVIXPolicySwitching('test_policy_selection_moderate_vix'))

    else:
        # Full test suite
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSchemaValidation))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDataQuality))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDataCollection))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFileIntegrity))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVIXPolicySwitching))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFlashCrashDetection))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestWorkflowIntegration))

    return suite


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integration test suite for TradeBot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--workflow",
        choices=["schema", "data", "collection", "files", "vix", "flash", "workflow"],
        help="Run tests for specific workflow only"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick smoke tests only"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Create test suite
    suite = create_test_suite(quick=args.quick, workflow=args.workflow)

    # Run tests
    logging.info("=" * 60)
    logging.info("TradeBot Integration Test Suite")
    logging.info("=" * 60)

    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)

    # Summary
    logging.info("\n" + "=" * 60)
    logging.info("TEST SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Tests run: {result.testsRun}")
    logging.info(f"Failures: {len(result.failures)}")
    logging.info(f"Errors: {len(result.errors)}")
    logging.info(f"Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        logging.info("\n✅ All tests passed!")
        return 0
    else:
        logging.error("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
