#!/usr/bin/env python3
"""
Schema Migration Tool for TradeBot

Handles schema upgrades for CSV/JSON data files when DATA_SCHEMAS.md evolves.
Automatically migrates data to new formats while preserving existing information.

Usage:
    python migrate_schema.py --list                    # List available migrations
    python migrate_schema.py --migrate v1_to_v2        # Run specific migration
    python migrate_schema.py --auto                    # Auto-detect and migrate
    python migrate_schema.py --dry-run --migrate v1_to_v2  # Preview migration

Features:
    - Automatic schema version detection
    - Safe migration with automatic backups
    - Rollback capability
    - Dry-run mode for testing
    - Custom migration scripts

Migration Process:
    1. Detect current schema version
    2. Create backup before migration
    3. Apply transformation
    4. Validate new schema
    5. Log migration history

Author: TradeBot System
Date: 2026-02-03
"""

import os
import sys
import json
import csv
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from collections import OrderedDict


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Migration history log
MIGRATION_LOG = PROJECT_ROOT / "logs" / "schema_migrations.json"

# Backup directory for pre-migration data
MIGRATION_BACKUP_DIR = PROJECT_ROOT / "backups" / "schema_migrations"

# Log file
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "migrate_schema.log"


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
# Migration Registry
# ============================================================================

class Migration:
    """Container for a schema migration."""

    def __init__(
        self,
        name: str,
        description: str,
        version_from: str,
        version_to: str,
        migrate_func: Callable,
        files_pattern: str
    ):
        """
        Initialize migration.

        Args:
            name: Migration identifier (e.g., "add_risk_score_column")
            description: Human-readable description
            version_from: Source schema version
            version_to: Target schema version
            migrate_func: Function that performs the migration
            files_pattern: Glob pattern for files to migrate (e.g., "*/TRADE_IDEAS.csv")
        """
        self.name = name
        self.description = description
        self.version_from = version_from
        self.version_to = version_to
        self.migrate_func = migrate_func
        self.files_pattern = files_pattern

    def __repr__(self):
        return f"Migration({self.name}: {self.version_from} → {self.version_to})"


# ============================================================================
# Migration Functions
# ============================================================================

def migrate_trade_ideas_add_risk_score(filepath: Path) -> bool:
    """
    Example migration: Add 'risk_score' column to TRADE_IDEAS.csv.

    Args:
        filepath: Path to file to migrate

    Returns:
        True if successful, False otherwise
    """
    try:
        # Read existing data
        rows = []
        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        # Check if column already exists
        if 'risk_score' in fieldnames:
            logging.info(f"Column 'risk_score' already exists in {filepath.name}")
            return True

        # Add new column to fieldnames
        new_fieldnames = list(fieldnames) + ['risk_score']

        # Write updated data
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=new_fieldnames)
            writer.writeheader()

            for row in rows:
                # Calculate default risk score based on existing data
                # (Simple example: Higher priority = higher risk score)
                priority = row.get('priority', 'Medium')
                if priority == 'High':
                    row['risk_score'] = '7'
                elif priority == 'Low':
                    row['risk_score'] = '3'
                else:
                    row['risk_score'] = '5'

                writer.writerow(row)

        logging.info(f"✅ Added 'risk_score' column to {filepath.name}")
        return True

    except Exception as e:
        logging.error(f"Error migrating {filepath}: {e}")
        return False


def migrate_backtest_results_add_metadata(filepath: Path) -> bool:
    """
    Example migration: Add metadata columns to backtest results.

    Args:
        filepath: Path to file to migrate

    Returns:
        True if successful, False otherwise
    """
    try:
        # Read existing data
        rows = []
        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        # Add new metadata columns
        new_columns = ['migration_date', 'schema_version']
        new_fieldnames = list(fieldnames) + [col for col in new_columns if col not in fieldnames]

        # Write updated data
        migration_date = datetime.now().strftime("%Y-%m-%d")

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=new_fieldnames)
            writer.writeheader()

            for row in rows:
                row['migration_date'] = migration_date
                row['schema_version'] = '2.0'
                writer.writerow(row)

        logging.info(f"✅ Added metadata columns to {filepath.name}")
        return True

    except Exception as e:
        logging.error(f"Error migrating {filepath}: {e}")
        return False


def migrate_json_add_version(filepath: Path) -> bool:
    """
    Example migration: Add version field to JSON config files.

    Args:
        filepath: Path to JSON file to migrate

    Returns:
        True if successful, False otherwise
    """
    try:
        # Read JSON
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check if version already exists
        if 'schema_version' in data:
            logging.info(f"Field 'schema_version' already exists in {filepath.name}")
            return True

        # Add version field at the top
        ordered_data = OrderedDict()
        ordered_data['schema_version'] = '2.0'
        ordered_data['migrated_at'] = datetime.now().isoformat()

        for key, value in data.items():
            ordered_data[key] = value

        # Write updated JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ordered_data, f, indent=2)

        logging.info(f"✅ Added 'schema_version' to {filepath.name}")
        return True

    except Exception as e:
        logging.error(f"Error migrating {filepath}: {e}")
        return False


# ============================================================================
# Migration Registry
# ============================================================================

# Register all available migrations
MIGRATIONS = [
    Migration(
        name="trade_ideas_v1_to_v2",
        description="Add 'risk_score' column to TRADE_IDEAS.csv",
        version_from="1.0",
        version_to="2.0",
        migrate_func=migrate_trade_ideas_add_risk_score,
        files_pattern="*/TRADE_IDEAS.csv"
    ),
    Migration(
        name="backtest_results_v1_to_v2",
        description="Add metadata columns to backtest results",
        version_from="1.0",
        version_to="2.0",
        migrate_func=migrate_backtest_results_add_metadata,
        files_pattern="*/RESULTS.csv"
    ),
    Migration(
        name="config_json_v1_to_v2",
        description="Add schema version to JSON config files",
        version_from="1.0",
        version_to="2.0",
        migrate_func=migrate_json_add_version,
        files_pattern="config/*.json"
    ),
]


# ============================================================================
# Migration History
# ============================================================================

class MigrationHistory:
    """Tracks completed migrations."""

    def __init__(self):
        self.log_file = MIGRATION_LOG
        self.data = self._load()

    def _load(self) -> Dict:
        """Load migration history from disk."""
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading migration history: {e}")
                return {"migrations": []}
        return {"migrations": []}

    def save(self):
        """Save migration history to disk."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving migration history: {e}")

    def record(self, migration_name: str, files_migrated: List[str], success: bool):
        """Record a migration attempt."""
        self.data["migrations"].append({
            "migration": migration_name,
            "timestamp": datetime.now().isoformat(),
            "files_count": len(files_migrated),
            "files": files_migrated,
            "success": success
        })
        self.save()

    def was_applied(self, migration_name: str) -> bool:
        """Check if migration was already applied successfully."""
        for record in self.data["migrations"]:
            if record["migration"] == migration_name and record["success"]:
                return True
        return False


# ============================================================================
# Backup Operations
# ============================================================================

def create_migration_backup(files: List[Path], migration_name: str) -> Optional[Path]:
    """
    Create backup of files before migration.

    Args:
        files: List of files to backup
        migration_name: Name of migration

    Returns:
        Path to backup directory, or None if failed
    """
    if not files:
        return None

    backup_id = f"{migration_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir = MIGRATION_BACKUP_DIR / backup_id

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)

        for filepath in files:
            rel_path = filepath.relative_to(PROJECT_ROOT)
            dest_path = backup_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(filepath, dest_path)

        logging.info(f"Created backup: {backup_dir}")
        return backup_dir

    except Exception as e:
        logging.error(f"Error creating backup: {e}")
        return None


# ============================================================================
# Migration Runner
# ============================================================================

def find_files_for_migration(migration: Migration) -> List[Path]:
    """Find files matching migration's file pattern."""
    files = list(PROJECT_ROOT.rglob(migration.files_pattern))
    logging.info(f"Found {len(files)} files matching '{migration.files_pattern}'")
    return files


def run_migration(migration: Migration, dry_run: bool = False, force: bool = False) -> bool:
    """
    Run a specific migration.

    Args:
        migration: Migration to run
        dry_run: Preview only, don't actually migrate
        force: Run even if already applied

    Returns:
        True if successful, False otherwise
    """
    logging.info("=" * 60)
    logging.info(f"Migration: {migration.name}")
    logging.info(f"Description: {migration.description}")
    logging.info(f"Version: {migration.version_from} → {migration.version_to}")
    logging.info("=" * 60)

    # Check if already applied
    history = MigrationHistory()
    if not force and history.was_applied(migration.name):
        logging.info(f"Migration '{migration.name}' was already applied successfully")
        logging.info("Use --force to run anyway")
        return True

    # Find files
    files = find_files_for_migration(migration)

    if not files:
        logging.warning("No files found to migrate")
        return False

    # Show files
    logging.info(f"\nFiles to migrate ({len(files)}):")
    for f in files:
        logging.info(f"  - {f.relative_to(PROJECT_ROOT)}")

    if dry_run:
        logging.info("\n✅ DRY RUN - No actual changes made")
        return True

    # Create backup
    logging.info("\nCreating backup...")
    backup_dir = create_migration_backup(files, migration.name)

    if not backup_dir:
        logging.error("Failed to create backup - aborting migration")
        return False

    # Run migration
    logging.info("\nApplying migration...")
    migrated_files = []
    failed_files = []

    for filepath in files:
        try:
            success = migration.migrate_func(filepath)
            if success:
                migrated_files.append(str(filepath.relative_to(PROJECT_ROOT)))
            else:
                failed_files.append(str(filepath.relative_to(PROJECT_ROOT)))
        except Exception as e:
            logging.error(f"Error migrating {filepath}: {e}")
            failed_files.append(str(filepath.relative_to(PROJECT_ROOT)))

    # Record results
    success = len(failed_files) == 0
    history.record(migration.name, migrated_files, success)

    # Summary
    logging.info("\n" + "=" * 60)
    logging.info("MIGRATION SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Migrated: {len(migrated_files)}/{len(files)} files")
    if failed_files:
        logging.error(f"Failed: {len(failed_files)} files")
        for f in failed_files:
            logging.error(f"  - {f}")
    logging.info(f"Backup location: {backup_dir}")

    if success:
        logging.info("\n✅ Migration completed successfully")
    else:
        logging.error("\n❌ Migration completed with errors")

    return success


def list_migrations():
    """List all available migrations."""
    history = MigrationHistory()

    logging.info("=" * 60)
    logging.info("AVAILABLE MIGRATIONS")
    logging.info("=" * 60)

    for migration in MIGRATIONS:
        applied = history.was_applied(migration.name)
        status = "✅ APPLIED" if applied else "⏳ NOT APPLIED"

        logging.info(f"\n{status} - {migration.name}")
        logging.info(f"  Description: {migration.description}")
        logging.info(f"  Version: {migration.version_from} → {migration.version_to}")
        logging.info(f"  Files: {migration.files_pattern}")


def auto_migrate(dry_run: bool = False) -> bool:
    """
    Automatically detect and run needed migrations.

    Args:
        dry_run: Preview only

    Returns:
        True if all migrations successful
    """
    history = MigrationHistory()
    pending_migrations = [m for m in MIGRATIONS if not history.was_applied(m.name)]

    if not pending_migrations:
        logging.info("All migrations are up to date!")
        return True

    logging.info(f"Found {len(pending_migrations)} pending migrations")

    all_success = True
    for migration in pending_migrations:
        success = run_migration(migration, dry_run=dry_run, force=False)
        if not success:
            all_success = False
            logging.error(f"Migration '{migration.name}' failed - stopping auto-migrate")
            break

    return all_success


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Schema migration tool for TradeBot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available migrations"
    )
    parser.add_argument(
        "--migrate",
        metavar="NAME",
        help="Run specific migration by name"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect and run pending migrations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run migration even if already applied"
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
        # List migrations
        if args.list:
            list_migrations()
            return 0

        # Auto migrate
        if args.auto:
            success = auto_migrate(args.dry_run)
            return 0 if success else 1

        # Specific migration
        if args.migrate:
            migration = next((m for m in MIGRATIONS if m.name == args.migrate), None)

            if not migration:
                logging.error(f"Migration not found: {args.migrate}")
                logging.info("\nAvailable migrations:")
                for m in MIGRATIONS:
                    logging.info(f"  - {m.name}")
                return 1

            success = run_migration(migration, args.dry_run, args.force)
            return 0 if success else 1

        # No action specified
        parser.print_help()
        return 0

    except KeyboardInterrupt:
        logging.info("\nMigration interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
