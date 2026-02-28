#!/usr/bin/env python3
"""
Data Cleanup & Archival System for TradeBot

Archives old backtest results and cleans cached data to maintain manageable
directory sizes and system performance.

Usage:
    python cleanup_old_data.py                     # Interactive cleanup
    python cleanup_old_data.py --dry-run           # Preview actions
    python cleanup_old_data.py --auto              # Auto-confirm (for automation)
    python cleanup_old_data.py --backtests-only    # Only archive backtests
    python cleanup_old_data.py --cache-only        # Only clean cache

Cleanup Policy (Minimal):
    - Archive backtests older than 12 months
    - Clean cached data older than 30 days
    - Move to _archive/ directory with index
    - Preserve TEST_INDEX.md references

Configuration:
    Adjust BACKTEST_AGE_MONTHS and CACHE_AGE_DAYS for different policies.

Author: TradeBot System
Date: 2026-02-03
"""

import os
import sys
import shutil
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
import csv
import re


# ============================================================================
# Configuration
# ============================================================================

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Cleanup policy (Minimal)
BACKTEST_AGE_MONTHS = 12  # Archive backtests older than 12 months
CACHE_AGE_DAYS = 30        # Clean cache older than 30 days

# Directories
BACKTEST_DIR = PROJECT_ROOT / "2. Backtest"
CACHE_DIR = BACKTEST_DIR / "datasets" / "data_tables"
ARCHIVE_DIR = PROJECT_ROOT / "_archive"
ARCHIVE_INDEX_FILE = ARCHIVE_DIR / "ARCHIVE_INDEX.md"

# Log file
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "cleanup.log"

# Files to preserve (never delete/archive)
PRESERVE_FILES = {
    "README.md",
    "TEST_INDEX.md",
    "CRYPTO_DATA_COLLECTION.md",
    "data_service.py",
    ".gitkeep"
}


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(verbose: bool = False):
    """Configure logging to file and console."""
    LOG_DIR.mkdir(exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO

    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ============================================================================
# Backtest Archive Discovery
# ============================================================================

def extract_backtest_date(test_dir: Path) -> Optional[datetime]:
    """
    Extract test date from TEST_INDEX.md or directory structure.

    Looks for:
    1. Date in RESULTS.md (if exists)
    2. Date in directory modification time
    3. Date pattern in directory name
    """
    # Try RESULTS.md first
    results_file = test_dir / "RESULTS.md"
    if results_file.exists():
        try:
            content = results_file.read_text(encoding='utf-8')
            # Look for date patterns like "Date: 2024-01-15" or "**Date**: 2024-01-15"
            date_match = re.search(r'\*?\*?Date\*?\*?:\s*(\d{4}-\d{2}-\d{2})', content)
            if date_match:
                return datetime.strptime(date_match.group(1), '%Y-%m-%d')
        except Exception as e:
            logging.debug(f"Could not parse RESULTS.md date: {e}")

    # Fall back to directory modification time
    try:
        stat = test_dir.stat()
        return datetime.fromtimestamp(stat.st_mtime)
    except Exception as e:
        logging.debug(f"Could not get directory mtime: {e}")

    # Last resort: check directory name for date pattern
    dir_name = test_dir.name
    date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', dir_name)
    if date_match:
        try:
            year, month, day = date_match.groups()
            return datetime(int(year), int(month), int(day))
        except Exception:
            pass

    return None


def find_old_backtests(age_months: int = BACKTEST_AGE_MONTHS) -> List[Tuple[Path, datetime]]:
    """
    Find backtest directories older than specified months.

    Returns:
        List of (directory_path, test_date) tuples
    """
    old_tests = []
    cutoff_date = datetime.now() - timedelta(days=age_months * 30)

    if not BACKTEST_DIR.exists():
        logging.warning(f"Backtest directory not found: {BACKTEST_DIR}")
        return []

    # Look for test* directories
    test_dirs = [d for d in BACKTEST_DIR.iterdir() if d.is_dir() and d.name.startswith("test")]

    logging.debug(f"Found {len(test_dirs)} test directories")

    for test_dir in test_dirs:
        test_date = extract_backtest_date(test_dir)

        if test_date is None:
            logging.debug(f"Could not determine date for {test_dir.name}, skipping")
            continue

        age_days = (datetime.now() - test_date).days

        if test_date < cutoff_date:
            old_tests.append((test_dir, test_date))
            logging.debug(f"Found old test: {test_dir.name} ({age_days} days old)")

    logging.info(f"Found {len(old_tests)} backtests older than {age_months} months")
    return old_tests


# ============================================================================
# Cache Data Discovery
# ============================================================================

def find_old_cache_files(age_days: int = CACHE_AGE_DAYS) -> List[Tuple[Path, datetime]]:
    """
    Find cached data files older than specified days.

    Returns:
        List of (file_path, modification_date) tuples
    """
    old_files = []
    cutoff_date = datetime.now() - timedelta(days=age_days)

    if not CACHE_DIR.exists():
        logging.warning(f"Cache directory not found: {CACHE_DIR}")
        return []

    # Find CSV/JSON files in cache directory
    cache_files = list(CACHE_DIR.glob("*.csv")) + list(CACHE_DIR.glob("*.json"))

    for filepath in cache_files:
        # Skip preserved files
        if filepath.name in PRESERVE_FILES:
            continue

        try:
            stat = filepath.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age = (datetime.now() - mtime).days

            if mtime < cutoff_date:
                old_files.append((filepath, mtime))
                logging.debug(f"Found old cache file: {filepath.name} ({age} days old)")

        except Exception as e:
            logging.error(f"Error checking {filepath}: {e}")

    logging.info(f"Found {len(old_files)} cache files older than {age_days} days")
    return old_files


# ============================================================================
# Archive Operations
# ============================================================================

def archive_backtest(test_dir: Path, test_date: datetime, dry_run: bool = False) -> bool:
    """
    Archive a backtest directory to _archive/.

    Args:
        test_dir: Path to test directory
        test_date: Date of the test
        dry_run: Preview only

    Returns:
        True if successful, False otherwise
    """
    # Create archive path with date prefix for organization
    date_prefix = test_date.strftime("%Y-%m")
    archive_subdir = ARCHIVE_DIR / "backtests" / date_prefix
    archive_path = archive_subdir / test_dir.name

    if dry_run:
        logging.info(f"Would archive: {test_dir.name} → {archive_path}")
        return True

    try:
        # Create archive directory
        archive_subdir.mkdir(parents=True, exist_ok=True)

        # Move directory
        shutil.move(str(test_dir), str(archive_path))
        logging.info(f"Archived: {test_dir.name} → {archive_path.relative_to(PROJECT_ROOT)}")
        return True

    except Exception as e:
        logging.error(f"Error archiving {test_dir.name}: {e}")
        return False


def delete_cache_file(filepath: Path, dry_run: bool = False) -> bool:
    """
    Delete an old cache file.

    Args:
        filepath: Path to cache file
        dry_run: Preview only

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        size_mb = filepath.stat().st_size / (1024 * 1024)
        logging.info(f"Would delete: {filepath.name} ({size_mb:.2f} MB)")
        return True

    try:
        filepath.unlink()
        logging.info(f"Deleted: {filepath.name}")
        return True

    except Exception as e:
        logging.error(f"Error deleting {filepath.name}: {e}")
        return False


# ============================================================================
# Archive Index Management
# ============================================================================

def update_archive_index(archived_tests: List[Tuple[Path, datetime]]):
    """
    Update ARCHIVE_INDEX.md with newly archived tests.

    Args:
        archived_tests: List of (test_dir, test_date) tuples that were archived
    """
    ARCHIVE_DIR.mkdir(exist_ok=True)

    # Load existing index or create header
    if ARCHIVE_INDEX_FILE.exists():
        content = ARCHIVE_INDEX_FILE.read_text(encoding='utf-8')
    else:
        content = """# Archive Index

This directory contains archived backtests and old data that are no longer actively used but preserved for historical reference.

## Organization

- `backtests/YYYY-MM/` - Archived backtest directories organized by month

## Archived Backtests

| Test Name | Archive Date | Original Test Date | Location |
|-----------|--------------|-------------------|----------|
"""

    # Append new entries
    now = datetime.now().strftime("%Y-%m-%d")

    for test_dir, test_date in archived_tests:
        date_prefix = test_date.strftime("%Y-%m")
        archive_location = f"backtests/{date_prefix}/{test_dir.name}"
        test_date_str = test_date.strftime("%Y-%m-%d")

        entry = f"| {test_dir.name} | {now} | {test_date_str} | {archive_location} |\n"
        content += entry

    # Save updated index
    ARCHIVE_INDEX_FILE.write_text(content, encoding='utf-8')
    logging.info(f"Updated archive index: {ARCHIVE_INDEX_FILE}")


# ============================================================================
# Interactive Confirmation
# ============================================================================

def confirm_action(message: str, auto_confirm: bool = False) -> bool:
    """
    Ask user for confirmation unless auto_confirm is True.

    Args:
        message: Confirmation message
        auto_confirm: Skip prompt and return True

    Returns:
        True if confirmed, False otherwise
    """
    if auto_confirm:
        return True

    response = input(f"{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']


# ============================================================================
# Main Cleanup Operations
# ============================================================================

def cleanup_backtests(age_months: int, dry_run: bool = False, auto_confirm: bool = False) -> Dict:
    """
    Archive old backtest directories.

    Returns:
        Dictionary with statistics
    """
    logging.info("=" * 60)
    logging.info(f"Scanning for backtests older than {age_months} months...")

    old_tests = find_old_backtests(age_months)

    if not old_tests:
        logging.info("No old backtests to archive")
        return {"found": 0, "archived": 0}

    # Calculate total size
    total_size = 0
    for test_dir, _ in old_tests:
        try:
            size = sum(f.stat().st_size for f in test_dir.rglob('*') if f.is_file())
            total_size += size
        except Exception:
            pass

    total_mb = total_size / (1024 * 1024)

    # Show summary
    logging.info(f"\nFound {len(old_tests)} old backtests:")
    for test_dir, test_date in old_tests:
        age_days = (datetime.now() - test_date).days
        logging.info(f"  - {test_dir.name} ({age_days} days old)")

    logging.info(f"\nTotal size: {total_mb:.2f} MB")

    if dry_run:
        logging.info("\nDRY RUN - No changes made")
        return {"found": len(old_tests), "archived": 0}

    # Confirm
    if not confirm_action(f"\nArchive {len(old_tests)} backtests?", auto_confirm):
        logging.info("Cancelled by user")
        return {"found": len(old_tests), "archived": 0}

    # Archive
    archived = []
    for test_dir, test_date in old_tests:
        if archive_backtest(test_dir, test_date, dry_run=False):
            archived.append((test_dir, test_date))

    # Update index
    if archived:
        update_archive_index(archived)

    logging.info(f"✅ Archived {len(archived)}/{len(old_tests)} backtests")

    return {"found": len(old_tests), "archived": len(archived)}


def cleanup_cache(age_days: int, dry_run: bool = False, auto_confirm: bool = False) -> Dict:
    """
    Delete old cached data files.

    Returns:
        Dictionary with statistics
    """
    logging.info("=" * 60)
    logging.info(f"Scanning for cache files older than {age_days} days...")

    old_files = find_old_cache_files(age_days)

    if not old_files:
        logging.info("No old cache files to delete")
        return {"found": 0, "deleted": 0, "freed_mb": 0}

    # Calculate total size
    total_size = sum(f.stat().st_size for f, _ in old_files)
    total_mb = total_size / (1024 * 1024)

    # Show summary
    logging.info(f"\nFound {len(old_files)} old cache files:")
    for filepath, mtime in old_files:
        age_days_file = (datetime.now() - mtime).days
        size_mb = filepath.stat().st_size / (1024 * 1024)
        logging.info(f"  - {filepath.name} ({age_days_file} days old, {size_mb:.2f} MB)")

    logging.info(f"\nTotal size: {total_mb:.2f} MB")

    if dry_run:
        logging.info("\nDRY RUN - No changes made")
        return {"found": len(old_files), "deleted": 0, "freed_mb": 0}

    # Confirm
    if not confirm_action(f"\nDelete {len(old_files)} cache files ({total_mb:.2f} MB)?", auto_confirm):
        logging.info("Cancelled by user")
        return {"found": len(old_files), "deleted": 0, "freed_mb": 0}

    # Delete
    deleted_count = 0
    for filepath, _ in old_files:
        if delete_cache_file(filepath, dry_run=False):
            deleted_count += 1

    logging.info(f"✅ Deleted {deleted_count}/{len(old_files)} cache files, freed {total_mb:.2f} MB")

    return {"found": len(old_files), "deleted": deleted_count, "freed_mb": total_mb}


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup and archival system for TradeBot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--backtests-only",
        action="store_true",
        help="Only archive old backtests"
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Only clean cache files"
    )
    parser.add_argument(
        "--backtest-age-months",
        type=int,
        default=BACKTEST_AGE_MONTHS,
        help=f"Archive backtests older than N months (default: {BACKTEST_AGE_MONTHS})"
    )
    parser.add_argument(
        "--cache-age-days",
        type=int,
        default=CACHE_AGE_DAYS,
        help=f"Delete cache older than N days (default: {CACHE_AGE_DAYS})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without making changes"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-confirm all actions (for automation)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    try:
        stats = {
            "backtests_found": 0,
            "backtests_archived": 0,
            "cache_found": 0,
            "cache_deleted": 0,
            "space_freed_mb": 0
        }

        # Determine what to clean
        clean_backtests = not args.cache_only
        clean_cache = not args.backtests_only

        # Clean backtests
        if clean_backtests:
            result = cleanup_backtests(args.backtest_age_months, args.dry_run, args.auto)
            stats["backtests_found"] = result["found"]
            stats["backtests_archived"] = result["archived"]

        # Clean cache
        if clean_cache:
            result = cleanup_cache(args.cache_age_days, args.dry_run, args.auto)
            stats["cache_found"] = result["found"]
            stats["cache_deleted"] = result["deleted"]
            stats["space_freed_mb"] = result["freed_mb"]

        # Summary
        logging.info("\n" + "=" * 60)
        logging.info("CLEANUP SUMMARY")
        logging.info("=" * 60)
        logging.info(f"Backtests: {stats['backtests_archived']}/{stats['backtests_found']} archived")
        logging.info(f"Cache: {stats['cache_deleted']}/{stats['cache_found']} deleted")
        logging.info(f"Space freed: {stats['space_freed_mb']:.2f} MB")

        if args.dry_run:
            logging.info("\n(DRY RUN - No actual changes made)")

        return 0

    except KeyboardInterrupt:
        logging.info("\nCleanup interrupted by user")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
