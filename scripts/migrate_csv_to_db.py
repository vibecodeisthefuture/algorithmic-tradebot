#!/usr/bin/env python3
"""
Migrate CSV Data to SQLite Database

Reads existing CSV log files and inserts them into the Blackboard DB.
After migration, original CSVs are moved to data/archive/ (not deleted).

Usage:
    py scripts/migrate_csv_to_db.py            # run migration
    py scripts/migrate_csv_to_db.py --dry-run   # preview only
"""

import argparse
import csv
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.common.database import get_db_session, init_db
from agents.common.models import Strategy, Trade, MarketNews
from agents.common.enums import (
    StrategyStatus,
    TradeSide,
    TradeStatus,
    ImpactRating,
)

LOGS_DIR = PROJECT_ROOT / "data" / "logs"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"

# ---------------------------------------------------------------------------
# Column mapping: CSV column → ORM field
# ---------------------------------------------------------------------------

# trade_ideas_log.csv Status → StrategyStatus
_STATUS_MAP = {
    "Not Started": StrategyStatus.NEW,
    "New": StrategyStatus.NEW,
    "Ready": StrategyStatus.READY_FOR_BACKTEST,
    "Backtesting": StrategyStatus.BACKTESTING,
    "Backtest Complete": StrategyStatus.BACKTEST_COMPLETE,
    "Paper": StrategyStatus.LIVE_PAPER,
    "Live": StrategyStatus.LIVE_REAL,
    "Paused": StrategyStatus.PAUSED,
    "Retired": StrategyStatus.RETIRED,
}

_IMPACT_MAP = {
    "LOW": ImpactRating.LOW,
    "Low": ImpactRating.LOW,
    "MED": ImpactRating.MED,
    "MEDIUM": ImpactRating.MED,
    "Medium": ImpactRating.MED,
    "HIGH": ImpactRating.HIGH,
    "High": ImpactRating.HIGH,
    "CRITICAL": ImpactRating.CRITICAL,
    "Critical": ImpactRating.CRITICAL,
}


def _parse_datetime(s: str) -> datetime | None:
    """Try multiple datetime formats."""
    if not s:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _safe_float(s: str) -> float | None:
    try:
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------


def migrate_trade_ideas(session, dry_run: bool) -> int:
    """trade_ideas_log.csv → strategies table."""
    csv_path = LOGS_DIR / "trade_ideas_log.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path.name} not found")
        return 0

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    print(f"  [READ] {csv_path.name}: {len(rows)} row(s)")

    for row in rows:
        status = _STATUS_MAP.get(row.get("Status", ""), StrategyStatus.NEW)
        strategy = Strategy(
            name=row.get("Name", "Unnamed"),
            asset_class=row.get("Asset_Class"),
            strategy_type=row.get("Type"),
            status=status,
            priority=row.get("Priority", "Medium"),
            parameters={"expected_sharpe": row.get("Expected_Sharpe"),
                         "max_drawdown": row.get("Max_Drawdown")},
            source=row.get("Source", "CSV Migration"),
            notes=row.get("Notes"),
            created_at=_parse_datetime(row.get("Date_Added")) or datetime.now(timezone.utc),
        )
        if not dry_run:
            session.add(strategy)
        print(f"    → Strategy '{strategy.name}' [{status.value}]")

    return len(rows)


def migrate_orders(session, dry_run: bool) -> int:
    """order_history.csv → trades table."""
    csv_path = LOGS_DIR / "order_history.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path.name} not found")
        return 0

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    print(f"  [READ] {csv_path.name}: {len(rows)} row(s)")

    for row in rows:
        side_raw = row.get("action", "BUY").upper()
        side = TradeSide.BUY if side_raw == "BUY" else TradeSide.SELL

        status_raw = row.get("status", "").lower()
        if "fill" in status_raw:
            status = TradeStatus.FILLED
        elif "partial" in status_raw:
            status = TradeStatus.PARTIAL
        elif "cancel" in status_raw:
            status = TradeStatus.CANCELLED
        else:
            status = TradeStatus.FILLED  # default for imported data

        trade = Trade(
            id=row.get("orderID", f"migrated-{hash(str(row))}"),
            symbol=row.get("tickerSymbol", "UNKNOWN"),
            side=side,
            qty=_safe_float(row.get("qty")) or 0,
            filled_qty=_safe_float(row.get("filledQty")),
            filled_price=_safe_float(row.get("avgFillPrice")),
            status=status,
            commission=_safe_float(row.get("commission")),
            timestamp=_parse_datetime(row.get("timestamp")),
        )
        if not dry_run:
            session.add(trade)
        print(f"    → Trade {trade.id[:20]}... {trade.side.value} {trade.qty} {trade.symbol}")

    return len(rows)


def migrate_news(session, dry_run: bool) -> int:
    """news_assessments_log.csv → market_news table."""
    csv_path = LOGS_DIR / "news_assessments_log.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path.name} not found")
        return 0

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    print(f"  [READ] {csv_path.name}: {len(rows)} row(s)")

    for row in rows:
        severity_raw = row.get("Severity", "LOW").upper()
        impact = _IMPACT_MAP.get(severity_raw, ImpactRating.LOW)

        news = MarketNews(
            source=row.get("Data_Sources", "CSV Migration"),
            headline=row.get("Event_Name", "Untitled"),
            content=row.get("Assessment_Text"),
            impact_rating=impact,
            affected_assets=row.get("Affected_Sectors"),
            opportunities_identified=row.get("Strategy_Implications"),
            discovered_at=_parse_datetime(row.get("Timestamp")),
            processed_by_manager=True,  # already reviewed if in CSV
        )
        if not dry_run:
            session.add(news)
        print(f"    → News [{impact.value}] {news.headline[:50]}")

    return len(rows)


def archive_csv(csv_name: str, dry_run: bool):
    """Move a CSV file to data/archive/."""
    src = LOGS_DIR / csv_name
    if not src.exists():
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    dst = ARCHIVE_DIR / csv_name
    if dry_run:
        print(f"  [DRY-RUN] Would move {src} → {dst}")
    else:
        shutil.move(str(src), str(dst))
        print(f"  [ARCHIVED] {src.name} → archive/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Migrate CSV data to SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    mode_label = "[DRY-RUN]" if args.dry_run else "[LIVE]"
    print(f"{'=' * 60}")
    print(f" CSV → SQLite Migration {mode_label}")
    print(f"{'=' * 60}")

    init_db()

    total = 0
    with get_db_session() as session:
        print("\n[1/3] Migrating trade_ideas_log.csv → strategies")
        total += migrate_trade_ideas(session, args.dry_run)

        print("\n[2/3] Migrating order_history.csv → trades")
        total += migrate_orders(session, args.dry_run)

        print("\n[3/3] Migrating news_assessments_log.csv → market_news")
        total += migrate_news(session, args.dry_run)

    print(f"\n{'─' * 60}")
    print(f"Total rows migrated: {total}")

    if not args.dry_run and total > 0:
        print("\n[4] Archiving original CSV files...")
        archive_csv("trade_ideas_log.csv", args.dry_run)
        archive_csv("order_history.csv", args.dry_run)
        archive_csv("news_assessments_log.csv", args.dry_run)
        print("\n✅ Migration complete! CSVs archived to data/archive/")
    elif args.dry_run:
        print("\n📋 Dry-run complete. No changes written.")
    else:
        print("\n⚠ No data to migrate.")


if __name__ == "__main__":
    main()
