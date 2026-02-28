# Scripts Directory

## Overview

This directory contains utility scripts for maintaining data quality, validating schemas, and automating common tasks in the TradeBot system.

---

## Available Scripts

### 1. validate_schemas.py

**Purpose**: Validate all database tables and data files against schemas defined in [docs/DATA_SCHEMAS.md](../docs/DATA_SCHEMAS.md).

**When to Use**:
- Before committing changes to data files
- After manual database edits
- As part of CI/CD pipeline
- Weekly as part of Manager review

**Usage**:
```bash
# Validate all database tables
python scripts/validate_schemas.py

# Validate specific table
python scripts/validate_schemas.py --table strategies

# Show detailed errors
python scripts/validate_schemas.py --verbose
```

**What It Checks**:
- ✅ Required columns are present
- ✅ Enum values are valid (e.g., Status, Priority, Alert Level)
- ✅ Date formats are correct
- ✅ ID formats follow convention (e.g., `ti-001`, `na-002`)
- ✅ Numeric ranges are within bounds
- ✅ JSON structure matches expected schema

**Example Output**:
```
TradeBot Schema Validation

✓ strategies table (12 rows)
✓ market_news table (8 rows)
✗ trades table
  - Row 5, column 'status': Invalid value 'pending_fill'. Must be one of: filled, partially_filled, cancelled, rejected, pending

Results:
  Total tables: 8
  Passed: 7
  Failed: 1
```

---

### 2. check_data_quality.py

**Purpose**: Perform quality checks on historical data files (OHLCV data) used for backtesting.

**When to Use**:
- After downloading new historical data
- Before starting a backtest
- After data collection scripts run
- Weekly to check data freshness

**Usage**:
```bash
# Check all datasets
python scripts/check_data_quality.py

# Check specific asset
python scripts/check_data_quality.py --asset BTC

# Check specific timeframe
python scripts/check_data_quality.py --timeframe 6h

# Show detailed information
python scripts/check_data_quality.py --verbose
```

**What It Checks**:
- ✅ Required columns present (timestamp, OHLCV)
- ✅ No missing values
- ✅ No negative or zero prices
- ✅ Valid OHLC relationships (low ≤ open/close ≤ high)
- ✅ No duplicate timestamps
- ✅ No gaps in time series
- ✅ Data freshness (crypto <12h, stocks <48h)

**Example Output**:
```
TradeBot Data Quality Check

✓ data/datasets/crypto/BTC-6h-500wks-data.csv
  Info:
    - total_rows: 2016
    - first_date: 2019-01-01 00:00:00
    - last_date: 2026-02-02 18:00:00
    - data_age_hours: 8.5

⚠ data/datasets/crypto/ETH-1d-500wks-data.csv
  Info:
    - total_rows: 500
    - data_age_hours: 15.2
  Warnings:
    - Crypto data is 15.2 hours old (expected <12h)
    - 3 gaps detected in time series

Summary:
  Total files checked: 6
  Passed: 5
  Warnings: 1
  Errors: 0
```

---

### 3. auto_backup.py

**Purpose**: Automated incremental backup system for the database and critical data files with retention management.

**When to Use**:
- Daily automated backups (via scheduler)
- Before major system changes
- After manual data edits
- For disaster recovery preparation

**Usage**:
```bash
# Create incremental backup (only changed files)
python scripts/auto_backup.py

# Force full backup (all files)
python scripts/auto_backup.py --force-full

# Preview what would be backed up
python scripts/auto_backup.py --dry-run

# List all available backups
python scripts/auto_backup.py --list

# Restore from latest backup
python scripts/auto_backup.py --restore latest

# Restore from specific backup
python scripts/auto_backup.py --restore 20260203_143000

# Clean old backups only (no new backup)
python scripts/auto_backup.py --clean
```

**Features**:
- ✅ MD5 hash-based change detection (only backs up changed files)
- ✅ 30-day automatic retention with cleanup
- ✅ Backup manifest tracks all backups and file history
- ✅ Restore capability to rollback changes
- ✅ Dry-run mode for testing
- ✅ Comprehensive logging to logs/backup.log

**Backup Sources**:
- `agents/manager/` - Manager data and documentation
- `agents/research/` - Trade ideas and research agents
- `agents/backtest/` - Backtest agent and documentation
- `agents/brokers/` - Broker integrations (Alpaca, IBKR, OKX)
- `agents/portfolio_tracker/` - Portfolio tracking agent
- `agents/analytics/` - Analytics agent and scripts
- `data/tradebot.db` - SQLite database (all tables)
- `data/datasets/data_tables/` - Historical market data
- `data/state/` - Runtime state files
- `config/` - System configuration

**Automated Scheduling** (recommended):
```bash
# Windows Task Scheduler - Daily at 2 AM
schtasks /create /tn "TradeBot Backup" /tr "python C:\path\to\TradeBot\scripts\auto_backup.py" /sc daily /st 02:00

# Linux/Mac cron - Daily at 2 AM
0 2 * * * cd /path/to/TradeBot && python scripts/auto_backup.py
```

---

### 4. cleanup_old_data.py

**Purpose**: Archive old backtest results and clean cached data to maintain disk space and system performance.

**When to Use**:
- Monthly cleanup (via scheduler)
- Before running resource-intensive tasks
- When disk space is low
- For archival and organization

**Usage**:
```bash
# Interactive cleanup (prompts for confirmation)
python scripts/cleanup_old_data.py

# Preview what would be cleaned
python scripts/cleanup_old_data.py --dry-run

# Auto-confirm all actions (for automation)
python scripts/cleanup_old_data.py --auto

# Only archive old backtests
python scripts/cleanup_old_data.py --backtests-only

# Only clean cache files
python scripts/cleanup_old_data.py --cache-only

# Custom retention periods
python scripts/cleanup_old_data.py --backtest-age-months 6 --cache-age-days 30
```

**Cleanup Policy** (Minimal - configurable):
- Archive backtests older than **12 months** to `_archive/backtests/YYYY-MM/`
- Delete cache files older than **60 days**
- Preserves critical files (README.md, TEST_INDEX.md, etc.)
- Creates ARCHIVE_INDEX.md for archived test tracking

**What Gets Archived**:
- Backtest directories (`data/backtests/test*`)
- Organized by month in `_archive/backtests/YYYY-MM/`
- Automatic index generation with test dates

**What Gets Deleted**:
- Cached OHLCV data files (`*.csv`, `*.json` in cache directory)
- Files not accessed in 60+ days
- Preserves any files in PRESERVE_FILES list

**Automated Scheduling** (recommended):
```bash
# Monthly cleanup - First day of month at 3 AM
0 3 1 * * cd /path/to/TradeBot && python scripts/cleanup_old_data.py --auto
```

---

### 5. test_integration.py

**Purpose**: End-to-end integration testing of automated workflows and system components.

**When to Use**:
- After code changes to critical systems
- Before deploying new strategies
- Weekly as part of system health check
- As part of CI/CD pipeline

**Usage**:
```bash
# Run all integration tests
python scripts/test_integration.py

# Quick smoke tests only (fast)
python scripts/test_integration.py --quick

# Test specific workflow
python scripts/test_integration.py --workflow schema
python scripts/test_integration.py --workflow vix
python scripts/test_integration.py --workflow flash

# Verbose output
python scripts/test_integration.py --verbose
```

**Test Coverage**:
- ✅ Schema validation (database table compliance)
- ✅ Data quality checks (OHLCV validation)
- ✅ Data collection (DataService initialization)
- ✅ File integrity (critical files exist)
- ✅ VIX policy switching logic
- ✅ Flash crash detection (crypto & stocks)
- ✅ Workflow integration (news→research→backtest)

**Workflow Tests**:
```bash
--workflow schema      # Schema validation tests
--workflow data        # OHLCV data quality tests
--workflow collection  # Data collection tests
--workflow files       # File integrity tests
--workflow vix         # VIX policy switching tests
--workflow flash       # Flash crash detection tests
--workflow workflow    # End-to-end pipeline tests
```

**Example Output**:
```
TradeBot Integration Test Suite
============================================================
test_valid_ohlcv_data (__main__.TestDataQuality) ... ok
test_policy_selection_moderate_vix (__main__.TestVIXPolicySwitching) ... ok
test_critical_markdown_files_exist (__main__.TestFileIntegrity) ... ok

----------------------------------------------------------------------
Ran 18 tests in 2.543s

OK (skipped=2)

✅ All tests passed!
```

**CI/CD Integration**:
```yaml
# .github/workflows/integration-tests.yml
- name: Run integration tests
  run: python scripts/test_integration.py --verbose
```

---

### 6. health_check.py

**Purpose**: Monitor system health and data quality for proactive issue detection and alerting.

**When to Use**:
- Hourly automated health checks (via scheduler)
- Before starting trading operations
- After system updates or changes
- For troubleshooting issues

**Usage**:
```bash
# Run all health checks
python scripts/health_check.py

# Only critical checks (faster)
python scripts/health_check.py --critical-only

# Log alerts to CSV for AI Manager review
python scripts/health_check.py --log-alerts

# JSON output for programmatic use
python scripts/health_check.py --json

# Verbose output
python scripts/health_check.py --verbose
```

**Health Checks**:
1. **Data Freshness** - Crypto < 12h, Stocks < 24h old
2. **Disk Space** - > 10% free space available
3. **Critical Files** - All required documentation exists
4. **Backup Status** - Last backup < 2 days ago
5. **Log Analysis** - Recent error count < 50/day
6. **Directory Structure** - Required directories exist
7. **Schema Compliance** - Key files validate against schemas

**Alert Levels**:
- `INFO` - Informational, no action needed
- `CAUTION` - Minor issue, monitor
- `URGENT` - Requires attention soon
- `CRITICAL` - Immediate action required

**Example Output**:
```
HEALTH CHECK RESULTS
============================================================
Checks: 7/7 passed

⚠️  URGENT alerts: 1

------------------------------------------------------------
CHECK DETAILS
------------------------------------------------------------

✅ Data Freshness: PASS
   All 6 crypto data files fresh

⚠️  Backup Status: WARN
   Last backup 3.2 days ago (expected < 2d)
   Alert Level: URGENT

✅ Disk Space: PASS
   Disk space OK: 45.3% free (127.8 GB)

============================================================
⚠️  SYSTEM STATUS: DEGRADED - Action recommended
============================================================
```

**Automated Scheduling** (recommended):
```bash
# Every hour
0 * * * * cd /path/to/TradeBot && python scripts/health_check.py --log-alerts

# Critical checks every 15 minutes
*/15 * * * * cd /path/to/TradeBot && python scripts/health_check.py --critical-only --log-alerts
```

**Exit Codes**:
- `0` - All checks passed
- `1` - Warnings present
- `2` - Critical failures

---

### 7. migrate_schema.py

**Purpose**: Handle schema version upgrades when DATA_SCHEMAS.md evolves, safely migrating existing data to new formats.

**When to Use**:
- After updating DATA_SCHEMAS.md
- Before deploying schema-dependent changes
- For adding new required columns
- For format migrations

**Usage**:
```bash
# List all available migrations
python scripts/migrate_schema.py --list

# Auto-detect and run pending migrations
python scripts/migrate_schema.py --auto

# Preview migration without changes
python scripts/migrate_schema.py --migrate trade_ideas_v1_to_v2 --dry-run

# Run specific migration
python scripts/migrate_schema.py --migrate trade_ideas_v1_to_v2

# Force re-run already applied migration
python scripts/migrate_schema.py --migrate trade_ideas_v1_to_v2 --force
```

**Built-in Migrations**:
1. `trade_ideas_v1_to_v2` - Add 'risk_score' column to TRADE_IDEAS.csv
2. `backtest_results_v1_to_v2` - Add metadata columns to backtest results
3. `config_json_v1_to_v2` - Add schema version to JSON config files

**Features**:
- ✅ Automatic backup before migration
- ✅ Migration history tracking
- ✅ Rollback capability via backups
- ✅ Dry-run mode for testing
- ✅ Custom migration functions

**Migration Process**:
1. Detects current schema version
2. Creates automatic backup in `backups/schema_migrations/`
3. Applies transformation
4. Validates new schema
5. Records migration in `logs/schema_migrations.json`

**Example Output**:
```
Migration: trade_ideas_v1_to_v2
Description: Add 'risk_score' column to TRADE_IDEAS.csv
Version: 1.0 → 2.0
============================================================

Tables to migrate (1):
  - strategies

Creating backup...
Created backup: backups/schema_migrations/trade_ideas_v1_to_v2_20260203_153045

Applying migration...
✅ Added 'risk_score' column to TRADE_IDEAS.csv

============================================================
MIGRATION SUMMARY
============================================================
Migrated: 1/1 files
Backup location: backups/schema_migrations/trade_ideas_v1_to_v2_20260203_153045

✅ Migration completed successfully
```

**Adding Custom Migrations**:

Edit `scripts/migrate_schema.py` and add to `MIGRATIONS`:

```python
def my_custom_migration(filepath: Path) -> bool:
    # Your migration logic here
    return True

MIGRATIONS.append(
    Migration(
        name="my_migration_v2_to_v3",
        description="My custom migration",
        version_from="2.0",
        version_to="3.0",
        migrate_func=my_custom_migration,
        files_pattern="*/MY_FILE.csv"
    )
)
```

---

## Integration with CI/CD

### Pre-Commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running schema validation..."
python scripts/validate_schemas.py

if [ $? -ne 0 ]; then
    echo "Schema validation failed. Commit aborted."
    exit 1
fi

echo "Schema validation passed!"
exit 0
```

### GitHub Actions Workflow

Create `.github/workflows/data-validation.yml`:

```yaml
name: Data Validation

on:
  push:
    paths:
      - '**.csv'
      - '**.json'
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Validate schemas
        run: python scripts/validate_schemas.py --verbose

      - name: Check data quality
        run: python scripts/check_data_quality.py --verbose
```

---

## Scheduled Tasks

### Weekly Data Quality Check

Add to cron (Linux/Mac) or Task Scheduler (Windows):

```bash
# Every Monday at 9 AM
0 9 * * 1 cd /path/to/TradeBot && python scripts/check_data_quality.py --verbose
```

### Daily Schema Validation

```bash
# Every day at midnight
0 0 * * * cd /path/to/TradeBot && python scripts/validate_schemas.py
```

---

## Adding New Validation Rules

### For CSV Files

Edit `scripts/validate_schemas.py` and add to the schema dictionary:

```python
MY_NEW_CSV_SCHEMA = {
    "required_columns": ["col1", "col2", "col3"],
    "enums": {
        "col1": ["value1", "value2", "value3"]
    },
    "ranges": {
        "col2": (0, 100)  # Min 0, Max 100
    },
    "formats": {
        "col3": r"^[A-Z]{3}-\d{3}$"  # Regex pattern
    }
}
```

Then add to `files_to_validate` dictionary:

```python
files_to_validate = {
    "path/to/file.csv": MY_NEW_CSV_SCHEMA,
    # ... existing files
}
```

### For JSON Files

Define structure:

```python
MY_JSON_STRUCTURE = {
    "required_keys": ["key1", "key2"],
    "enums": {
        "key1": ["option1", "option2"]
    },
    "types": {
        "key2": "number"  # string, number, array, object
    }
}
```

Add to `json_files` dictionary:

```python
json_files = {
    "path/to/file.json": MY_JSON_STRUCTURE,
    # ... existing files
}
```

---

## Troubleshooting

### "File not found" errors

Make sure you're running the scripts from the project root:

```bash
cd .
python scripts/validate_schemas.py
```

### "Permission denied" errors

On Windows, you may need to run as administrator:

```powershell
# Run PowerShell as Administrator
python scripts/validate_schemas.py
```

### "Module not found" errors

The scripts use only Python standard library modules. If you get import errors, check your Python version:

```bash
python --version  # Should be Python 3.7+
```

---

## Complete Script Summary

| Script | Purpose | Frequency | Critical |
|--------|---------|-----------|----------|
| validate_schemas.py | Schema validation | Daily/Pre-commit | ✅ |
| check_data_quality.py | Data quality checks | Daily | ✅ |
| auto_backup.py | Incremental backups | Daily | ✅ |
| cleanup_old_data.py | Archive & cleanup | Monthly | ⚡ |
| test_integration.py | Integration testing | Weekly/CI | ✅ |
| health_check.py | System health monitoring | Hourly | ✅ |
| migrate_schema.py | Schema migrations | As needed | ⚡ |

**Legend**: ✅ Critical, ⚡ Important

---

## Recommended Automation Schedule

```bash
# === DAILY ===
# 2:00 AM - Automated backup
0 2 * * * cd /path/to/TradeBot && python scripts/auto_backup.py

# Midnight - Schema validation
0 0 * * * cd /path/to/TradeBot && python scripts/validate_schemas.py

# 6:00 AM - Data quality check
0 6 * * * cd /path/to/TradeBot && python scripts/check_data_quality.py

# === HOURLY ===
# Every hour - Health checks with alert logging
0 * * * * cd /path/to/TradeBot && python scripts/health_check.py --log-alerts

# === WEEKLY ===
# Monday 9:00 AM - Integration tests
0 9 * * 1 cd /path/to/TradeBot && python scripts/test_integration.py

# === MONTHLY ===
# 1st day at 3:00 AM - Cleanup old data
0 3 1 * * cd /path/to/TradeBot && python scripts/cleanup_old_data.py --auto
```

---

## Related Documentation

- [docs/DATA_SCHEMAS.md](../docs/DATA_SCHEMAS.md) - Complete schema definitions
- [docs/AUTOMATION_WORKFLOWS.md](../docs/AUTOMATION_WORKFLOWS.md) - Automated pipeline descriptions
- [docs/RISK_POLICY_FRAMEWORK.md](../docs/RISK_POLICY_FRAMEWORK.md) - Risk management policies
- [docs/PHASE_3_PLAN.md](../docs/PHASE_3_PLAN.md) - Phase 3 implementation details
- [config/system_config.yaml](../config/system_config.yaml) - System configuration

---

**Maintained by AI Manager | Last Updated: 2026-02-04 | Phase 3 Complete**
