#!/usr/bin/env python3
"""
Automated Backup System for TradeBot

Creates incremental backups of critical CSV/JSON data files with automatic
retention management. Designed to run daily via scheduler or cron.

Usage:
    python auto_backup.py                    # Create backup
    python auto_backup.py --restore latest   # Restore from latest backup
    python auto_backup.py --list             # List all backups
    python auto_backup.py --dry-run          # Preview what would be backed up
    python auto_backup.py --clean            # Clean old backups only

Configuration:
    - Backs up CSV/JSON files from critical directories
    - Keeps last 30 days of backups (configurable)
    - Only backs up changed files (incremental)
    - Stores in backups/ directory with timestamps
    - Logs all operations to logs/backup.log

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
import hashlib


# ============================================================================
# Configuration
# ============================================================================

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Directories to back up (relative to project root)
BACKUP_SOURCES = [
    "agents/manager",
    "agents/research",
    "agents/backtest",
    "agents/brokers",
    "agents/portfolio_tracker",
    "agents/analytics",
    "data/logs",
    "data/datasets/data_tables",
    "data/state",
    "config",
]

# File patterns to back up
BACKUP_PATTERNS = ["*.csv", "*.json", "*.yaml", "*.yml"]

# Backup destination
BACKUP_DIR = PROJECT_ROOT / "backups"

# Retention period (days)
RETENTION_DAYS = 30

# Manifest file to track backups
BACKUP_MANIFEST = "backup_manifest.json"

# Log file
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "backup.log"


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
# File Hashing (for change detection)
# ============================================================================

def calculate_file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of file contents for change detection."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logging.error(f"Error hashing {filepath}: {e}")
        return ""


def get_file_metadata(filepath: Path) -> Dict:
    """Get file metadata for change tracking."""
    try:
        stat = filepath.stat()
        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "hash": calculate_file_hash(filepath)
        }
    except Exception as e:
        logging.error(f"Error getting metadata for {filepath}: {e}")
        return {}


# ============================================================================
# Backup Manifest Management
# ============================================================================

class BackupManifest:
    """Manages backup metadata and history."""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.manifest_path = backup_dir / BACKUP_MANIFEST
        self.data = self._load()

    def _load(self) -> Dict:
        """Load manifest from disk."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading manifest: {e}")
                return {"backups": [], "file_history": {}}
        return {"backups": [], "file_history": {}}

    def save(self):
        """Save manifest to disk."""
        try:
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving manifest: {e}")

    def add_backup(self, backup_id: str, files: List[Dict]):
        """Record a new backup."""
        self.data["backups"].append({
            "id": backup_id,
            "timestamp": datetime.now().isoformat(),
            "file_count": len(files),
            "files": files
        })
        self.save()

    def update_file_history(self, filepath: str, metadata: Dict):
        """Update file history with latest metadata."""
        self.data["file_history"][filepath] = metadata
        self.save()

    def get_file_history(self, filepath: str) -> Optional[Dict]:
        """Get last known metadata for a file."""
        return self.data["file_history"].get(filepath)

    def get_backups(self) -> List[Dict]:
        """Get list of all backups."""
        return self.data["backups"]

    def remove_backup(self, backup_id: str):
        """Remove backup from manifest."""
        self.data["backups"] = [
            b for b in self.data["backups"] if b["id"] != backup_id
        ]
        self.save()


# ============================================================================
# File Discovery
# ============================================================================

def find_backup_files() -> List[Path]:
    """Find all files matching backup patterns in source directories."""
    files = []

    for source_dir in BACKUP_SOURCES:
        source_path = PROJECT_ROOT / source_dir

        if not source_path.exists():
            logging.warning(f"Source directory not found: {source_dir}")
            continue

        for pattern in BACKUP_PATTERNS:
            matches = list(source_path.rglob(pattern))
            files.extend(matches)
            logging.debug(f"Found {len(matches)} {pattern} files in {source_dir}")

    # Remove duplicates and sort
    files = sorted(set(files))
    logging.info(f"Found {len(files)} total files to consider for backup")

    return files


def filter_changed_files(files: List[Path], manifest: BackupManifest) -> List[Path]:
    """Filter files that have changed since last backup."""
    changed = []

    for filepath in files:
        rel_path = str(filepath.relative_to(PROJECT_ROOT))
        current_metadata = get_file_metadata(filepath)
        previous_metadata = manifest.get_file_history(rel_path)

        # First backup or file changed
        if previous_metadata is None:
            changed.append(filepath)
            logging.debug(f"New file: {rel_path}")
        elif current_metadata.get("hash") != previous_metadata.get("hash"):
            changed.append(filepath)
            logging.debug(f"Changed file: {rel_path}")

    logging.info(f"{len(changed)} files have changed since last backup")
    return changed


# ============================================================================
# Backup Operations
# ============================================================================

def create_backup(dry_run: bool = False, force_full: bool = False) -> Optional[str]:
    """
    Create incremental backup of changed files.

    Args:
        dry_run: Preview only, don't actually backup
        force_full: Backup all files regardless of changes

    Returns:
        Backup ID if successful, None otherwise
    """
    logging.info("=" * 60)
    logging.info("Starting backup process...")

    # Create backup directory
    BACKUP_DIR.mkdir(exist_ok=True)

    # Load manifest
    manifest = BackupManifest(BACKUP_DIR)

    # Find all eligible files
    all_files = find_backup_files()

    if not all_files:
        logging.warning("No files found to backup")
        return None

    # Filter to changed files (unless force_full)
    if force_full:
        files_to_backup = all_files
        logging.info("Force full backup - backing up all files")
    else:
        files_to_backup = filter_changed_files(all_files, manifest)

    if not files_to_backup:
        logging.info("No changed files to backup - system is up to date")
        return None

    # Create backup ID (timestamp)
    backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / backup_id

    if dry_run:
        logging.info(f"DRY RUN - Would create backup: {backup_id}")
        logging.info(f"DRY RUN - Would backup {len(files_to_backup)} files:")
        for f in files_to_backup[:10]:  # Show first 10
            rel_path = f.relative_to(PROJECT_ROOT)
            size_kb = f.stat().st_size / 1024
            logging.info(f"  - {rel_path} ({size_kb:.1f} KB)")
        if len(files_to_backup) > 10:
            logging.info(f"  ... and {len(files_to_backup) - 10} more files")
        return None

    # Create backup directory
    backup_path.mkdir(exist_ok=True)
    logging.info(f"Creating backup: {backup_id}")

    # Copy files
    backed_up_files = []
    total_size = 0

    for filepath in files_to_backup:
        try:
            # Get relative path to maintain directory structure
            rel_path = filepath.relative_to(PROJECT_ROOT)
            dest_path = backup_path / rel_path

            # Create parent directories
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(filepath, dest_path)

            # Record metadata
            metadata = get_file_metadata(filepath)
            backed_up_files.append({
                "path": str(rel_path),
                "size": metadata["size"],
                "hash": metadata["hash"]
            })
            total_size += metadata["size"]

            # Update file history
            manifest.update_file_history(str(rel_path), metadata)

            logging.debug(f"Backed up: {rel_path}")

        except Exception as e:
            logging.error(f"Error backing up {filepath}: {e}")

    # Add backup to manifest
    manifest.add_backup(backup_id, backed_up_files)

    # Summary
    total_mb = total_size / (1024 * 1024)
    logging.info(f"✅ Backup complete: {backup_id}")
    logging.info(f"   Files backed up: {len(backed_up_files)}")
    logging.info(f"   Total size: {total_mb:.2f} MB")
    logging.info(f"   Location: {backup_path}")

    return backup_id


# ============================================================================
# Restore Operations
# ============================================================================

def list_backups() -> List[Dict]:
    """List all available backups."""
    manifest = BackupManifest(BACKUP_DIR)
    backups = manifest.get_backups()

    if not backups:
        logging.info("No backups found")
        return []

    logging.info(f"Available backups ({len(backups)}):")
    logging.info("=" * 60)

    for backup in reversed(backups):  # Most recent first
        timestamp = datetime.fromisoformat(backup["timestamp"])
        age_days = (datetime.now() - timestamp).days

        logging.info(f"ID: {backup['id']}")
        logging.info(f"   Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({age_days} days ago)")
        logging.info(f"   Files: {backup['file_count']}")
        logging.info("")

    return backups


def restore_backup(backup_id: str, dry_run: bool = False) -> bool:
    """
    Restore files from a backup.

    Args:
        backup_id: Backup ID to restore, or 'latest'
        dry_run: Preview only, don't actually restore

    Returns:
        True if successful, False otherwise
    """
    manifest = BackupManifest(BACKUP_DIR)
    backups = manifest.get_backups()

    if not backups:
        logging.error("No backups available to restore")
        return False

    # Find backup
    if backup_id == "latest":
        backup = backups[-1]  # Most recent
        backup_id = backup["id"]
        logging.info(f"Using latest backup: {backup_id}")
    else:
        backup = next((b for b in backups if b["id"] == backup_id), None)
        if not backup:
            logging.error(f"Backup not found: {backup_id}")
            return False

    backup_path = BACKUP_DIR / backup_id

    if not backup_path.exists():
        logging.error(f"Backup directory not found: {backup_path}")
        return False

    logging.info(f"Restoring backup: {backup_id}")
    logging.info(f"Files to restore: {backup['file_count']}")

    if dry_run:
        logging.info("DRY RUN - Would restore the following files:")
        for file_info in backup["files"][:10]:
            logging.info(f"  - {file_info['path']}")
        if backup['file_count'] > 10:
            logging.info(f"  ... and {backup['file_count'] - 10} more files")
        return True

    # Restore files
    restored_count = 0

    for file_info in backup["files"]:
        source_path = backup_path / file_info["path"]
        dest_path = PROJECT_ROOT / file_info["path"]

        try:
            # Create parent directories
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source_path, dest_path)
            restored_count += 1
            logging.debug(f"Restored: {file_info['path']}")

        except Exception as e:
            logging.error(f"Error restoring {file_info['path']}: {e}")

    logging.info(f"✅ Restore complete: {restored_count}/{backup['file_count']} files restored")
    return True


# ============================================================================
# Cleanup Operations
# ============================================================================

def clean_old_backups(retention_days: int = RETENTION_DAYS, dry_run: bool = False) -> int:
    """
    Remove backups older than retention period.

    Args:
        retention_days: Number of days to keep backups
        dry_run: Preview only, don't actually delete

    Returns:
        Number of backups removed
    """
    logging.info(f"Cleaning backups older than {retention_days} days...")

    manifest = BackupManifest(BACKUP_DIR)
    backups = manifest.get_backups()

    if not backups:
        logging.info("No backups to clean")
        return 0

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    to_remove = []

    for backup in backups:
        timestamp = datetime.fromisoformat(backup["timestamp"])
        if timestamp < cutoff_date:
            to_remove.append(backup)

    if not to_remove:
        logging.info("No old backups to remove")
        return 0

    logging.info(f"Found {len(to_remove)} old backups to remove")

    if dry_run:
        logging.info("DRY RUN - Would remove:")
        for backup in to_remove:
            timestamp = datetime.fromisoformat(backup["timestamp"])
            age_days = (datetime.now() - timestamp).days
            logging.info(f"  - {backup['id']} ({age_days} days old)")
        return len(to_remove)

    # Remove old backups
    removed_count = 0

    for backup in to_remove:
        backup_path = BACKUP_DIR / backup["id"]
        try:
            if backup_path.exists():
                shutil.rmtree(backup_path)
                logging.debug(f"Removed backup directory: {backup['id']}")

            manifest.remove_backup(backup["id"])
            removed_count += 1

        except Exception as e:
            logging.error(f"Error removing backup {backup['id']}: {e}")

    logging.info(f"✅ Cleanup complete: {removed_count} backups removed")
    return removed_count


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automated backup system for TradeBot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--restore",
        metavar="BACKUP_ID",
        help="Restore from backup (use 'latest' for most recent)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available backups"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean old backups only (no new backup)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without making changes"
    )
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Backup all files regardless of changes"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=RETENTION_DAYS,
        help=f"Backup retention period in days (default: {RETENTION_DAYS})"
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
        # List backups
        if args.list:
            list_backups()
            return 0

        # Restore backup
        if args.restore:
            success = restore_backup(args.restore, args.dry_run)
            return 0 if success else 1

        # Clean only
        if args.clean:
            clean_old_backups(args.retention_days, args.dry_run)
            return 0

        # Create backup (default action)
        backup_id = create_backup(args.dry_run, args.force_full)

        # Also clean old backups after successful backup
        if backup_id:
            clean_old_backups(args.retention_days, args.dry_run)

        return 0

    except KeyboardInterrupt:
        logging.info("\nBackup interrupted by user")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
