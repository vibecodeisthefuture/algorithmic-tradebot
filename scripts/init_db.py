#!/usr/bin/env python3
"""
Initialize the TradeBot SQLite Database

Creates all tables and seeds system_state with defaults from existing
JSON state files (active_policy.json, portfolio_health.json).

Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.

Usage:
    py scripts/init_db.py
"""

import json
import sys
from pathlib import Path

# Add project root to path so agents.common is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.common.database import init_db, get_db_session, get_db_path
from agents.common.models import SystemState


def _seed_from_json(json_path: Path, prefix: str = ""):
    """Read a JSON file and insert each key-value pair into system_state."""
    if not json_path.exists():
        print(f"  [SKIP] {json_path.name} not found")
        return 0

    with open(json_path, "r") as f:
        data = json.load(f)

    count = 0
    with get_db_session() as session:
        for key, value in data.items():
            full_key = f"{prefix}{key}" if prefix else key
            # Check if key already exists
            existing = session.query(SystemState).filter_by(key=full_key).first()
            if existing:
                print(f"  [EXISTS] {full_key} = {existing.value}")
                continue
            # Serialize non-string values to JSON
            if not isinstance(value, str):
                value = json.dumps(value)
            session.add(SystemState(key=full_key, value=str(value)))
            print(f"  [SEEDED] {full_key} = {value}")
            count += 1
    return count


def main():
    print("=" * 60)
    print(" TradeBot Database Initialization")
    print("=" * 60)

    # 1. Create all tables
    print(f"\n[1] Creating tables at: {get_db_path()}")
    init_db()
    print("    All tables created successfully.")

    # 2. Verify tables exist
    from sqlalchemy import inspect
    from agents.common.database import engine

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n[2] Tables in database ({len(tables)}):")
    for t in sorted(tables):
        columns = inspector.get_columns(t)
        print(f"    {t} ({len(columns)} columns)")

    # 3. Seed system_state from existing JSON files
    state_dir = PROJECT_ROOT / "data" / "state"
    print(f"\n[3] Seeding system_state from {state_dir}/...")
    total_seeded = 0
    total_seeded += _seed_from_json(state_dir / "active_policy.json", prefix="policy_")
    total_seeded += _seed_from_json(state_dir / "portfolio_health.json", prefix="health_")
    print(f"    Total keys seeded: {total_seeded}")

    # 4. Verify WAL mode
    print("\n[4] Verifying WAL mode...")
    import sqlite3
    db_conn = sqlite3.connect(str(get_db_path()))
    journal_mode = db_conn.execute("PRAGMA journal_mode").fetchone()[0]
    db_conn.close()
    print(f"    Journal mode: {journal_mode.upper()}")

    print("\n" + "=" * 60)
    print(" ✅ Database initialization complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
