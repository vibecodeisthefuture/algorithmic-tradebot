#!/usr/bin/env python3
"""
Unit Tests for the TradeBot Database Layer

Tests all tables, the session context manager, WAL mode,
enum persistence, and CRUD operations.

Usage:
    py -m pytest agents/common/test_database.py -v
    py agents/common/test_database.py           # fallback
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use a temporary database for testing
_TEST_DB = tempfile.mktemp(suffix=".db", prefix="tradebot_test_")
os.environ["TRADEBOT_DB_PATH"] = _TEST_DB

# Import AFTER setting the env var so the engine uses the test DB
from agents.common.database import get_db_session, init_db, engine, get_db_path
from agents.common.models import (
    Base,
    SystemState,
    MarketNews,
    Strategy,
    BacktestResult,
    Trade,
    PortfolioSnapshot,
    EventLog,
    PolicyHistory,
)
from agents.common.enums import (
    StrategyStatus,
    RiskPolicy,
    ImpactRating,
    TradeSide,
    TradeStatus,
    EventType,
    EventUrgency,
    PolicyTrigger,
)


class TestDatabaseSetup(unittest.TestCase):
    """Test engine configuration and table creation."""

    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        # Clean up test database
        try:
            os.unlink(_TEST_DB)
        except OSError:
            pass
        # Also clean up WAL and SHM files
        for suffix in ("-wal", "-shm"):
            try:
                os.unlink(_TEST_DB + suffix)
            except OSError:
                pass

    def test_db_path_uses_env_var(self):
        """DB path should respect TRADEBOT_DB_PATH env var."""
        self.assertEqual(str(get_db_path()), _TEST_DB)

    def test_wal_mode_enabled(self):
        """SQLite should be in WAL journal mode."""
        import sqlite3
        conn = sqlite3.connect(_TEST_DB)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        self.assertEqual(mode.upper(), "WAL")

    def test_all_tables_created(self):
        """All 8 tables should exist."""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "system_state",
            "market_news",
            "strategies",
            "backtest_results",
            "trades",
            "portfolio_snapshots",
            "event_log",
            "policy_history",
        }
        self.assertTrue(expected.issubset(tables), f"Missing: {expected - tables}")

    def test_foreign_keys_enabled(self):
        """PRAGMA foreign_keys should be ON."""
        import sqlite3
        conn = sqlite3.connect(_TEST_DB)
        # Need to enable via our engine to test; direct sqlite3 won't have it
        conn.close()
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA foreign_keys").fetchone()
            self.assertEqual(result[0], 1)


class TestSessionManager(unittest.TestCase):
    """Test get_db_session() context manager behavior."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_auto_commit_on_success(self):
        """Session should auto-commit when context exits cleanly."""
        with get_db_session() as session:
            session.add(SystemState(key="test_commit", value="works"))

        # Verify in a new session
        with get_db_session() as session:
            row = session.query(SystemState).filter_by(key="test_commit").first()
            self.assertIsNotNone(row)
            self.assertEqual(row.value, "works")

    def test_auto_rollback_on_exception(self):
        """Session should rollback on exception and re-raise."""
        try:
            with get_db_session() as session:
                session.add(SystemState(key="test_rollback", value="should_not_persist"))
                raise ValueError("deliberate error")
        except ValueError:
            pass

        with get_db_session() as session:
            row = session.query(SystemState).filter_by(key="test_rollback").first()
            self.assertIsNone(row)

    def test_cleanup(self):
        """Clean up test_commit key."""
        with get_db_session() as session:
            session.query(SystemState).filter_by(key="test_commit").delete()


class TestSystemState(unittest.TestCase):
    """Test system_state CRUD."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_insert_and_query(self):
        with get_db_session() as session:
            session.add(SystemState(key="risk_mode", value="HIGH"))
        with get_db_session() as session:
            row = session.query(SystemState).filter_by(key="risk_mode").first()
            self.assertEqual(row.value, "HIGH")

    def test_upsert(self):
        with get_db_session() as session:
            row = session.query(SystemState).filter_by(key="risk_mode").first()
            row.value = "LOW"
        with get_db_session() as session:
            row = session.query(SystemState).filter_by(key="risk_mode").first()
            self.assertEqual(row.value, "LOW")

    def test_cleanup(self):
        with get_db_session() as session:
            session.query(SystemState).filter_by(key="risk_mode").delete()


class TestStrategyLifecycle(unittest.TestCase):
    """Test the core Strategy + BacktestResult tables."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_create_strategy(self):
        with get_db_session() as session:
            strat = Strategy(
                name="Test Strategy",
                asset_class="Crypto",
                strategy_type="Breakout",
                status=StrategyStatus.NEW,
                parameters={"timeframe": "1h", "threshold": 0.02},
            )
            session.add(strat)

    def test_02_query_and_update_status(self):
        with get_db_session() as session:
            strat = session.query(Strategy).filter_by(name="Test Strategy").first()
            self.assertIsNotNone(strat)
            self.assertEqual(strat.status, StrategyStatus.NEW)
            strat.status = StrategyStatus.READY_FOR_BACKTEST

        with get_db_session() as session:
            strat = session.query(Strategy).filter_by(name="Test Strategy").first()
            self.assertEqual(strat.status, StrategyStatus.READY_FOR_BACKTEST)

    def test_03_add_backtest_result(self):
        with get_db_session() as session:
            strat = session.query(Strategy).filter_by(name="Test Strategy").first()
            result = BacktestResult(
                strategy_id=strat.id,
                sharpe_ratio=1.8,
                max_drawdown=12.5,
                win_rate=0.55,
                profit_factor=1.4,
                trades_count=120,
                total_return_pct=25.3,
            )
            session.add(result)

    def test_04_relationship_works(self):
        with get_db_session() as session:
            strat = session.query(Strategy).filter_by(name="Test Strategy").first()
            self.assertEqual(len(strat.backtest_results), 1)
            self.assertAlmostEqual(strat.backtest_results[0].sharpe_ratio, 1.8)

    def test_99_cleanup(self):
        with get_db_session() as session:
            strat = session.query(Strategy).filter_by(name="Test Strategy").first()
            if strat:
                session.query(BacktestResult).filter_by(strategy_id=strat.id).delete()
                session.delete(strat)


class TestTradeTable(unittest.TestCase):
    """Test trades table CRUD and enum persistence."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_insert_trade(self):
        with get_db_session() as session:
            trade = Trade(
                id="test-order-001",
                symbol="AAPL",
                side=TradeSide.BUY,
                qty=10.0,
                filled_qty=10.0,
                filled_price=175.50,
                status=TradeStatus.FILLED,
                commission=0.0,
            )
            session.add(trade)

    def test_02_query_trade(self):
        with get_db_session() as session:
            trade = session.query(Trade).filter_by(id="test-order-001").first()
            self.assertIsNotNone(trade)
            self.assertEqual(trade.symbol, "AAPL")
            self.assertEqual(trade.side, TradeSide.BUY)
            self.assertEqual(trade.status, TradeStatus.FILLED)
            self.assertAlmostEqual(trade.filled_price, 175.50)

    def test_99_cleanup(self):
        with get_db_session() as session:
            session.query(Trade).filter_by(id="test-order-001").delete()


class TestEventLog(unittest.TestCase):
    """Test the inter-agent event_log table."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_emit_event(self):
        with get_db_session() as session:
            event = EventLog(
                event_type=EventType.CIRCUIT_BREAKER,
                urgency=EventUrgency.CRITICAL,
                source_agent="portfolio_tracker",
                target_agent="manager",
                summary="Drawdown exceeded 22% threshold",
                details={"drawdown_pct": 23.1, "threshold": 22.0},
            )
            session.add(event)

    def test_02_query_unacknowledged(self):
        with get_db_session() as session:
            pending = (
                session.query(EventLog)
                .filter_by(acknowledged=False)
                .filter_by(event_type=EventType.CIRCUIT_BREAKER)
                .all()
            )
            self.assertGreaterEqual(len(pending), 1)
            evt = pending[0]
            self.assertEqual(evt.urgency, EventUrgency.CRITICAL)
            self.assertEqual(evt.source_agent, "portfolio_tracker")

    def test_03_acknowledge_event(self):
        with get_db_session() as session:
            evt = (
                session.query(EventLog)
                .filter_by(event_type=EventType.CIRCUIT_BREAKER, acknowledged=False)
                .first()
            )
            evt.acknowledged = True
            evt.acknowledged_by = "manager"
            evt.acknowledged_at = datetime.now(timezone.utc)
            evt.response = "Switching to LOW risk mode"

        with get_db_session() as session:
            evt = (
                session.query(EventLog)
                .filter_by(event_type=EventType.CIRCUIT_BREAKER, acknowledged=True)
                .first()
            )
            self.assertIsNotNone(evt)
            self.assertEqual(evt.acknowledged_by, "manager")

    def test_99_cleanup(self):
        with get_db_session() as session:
            session.query(EventLog).filter(
                EventLog.event_type == EventType.CIRCUIT_BREAKER
            ).delete()


class TestPolicyHistory(unittest.TestCase):
    """Test policy_history audit trail."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_record_policy_change(self):
        with get_db_session() as session:
            entry = PolicyHistory(
                old_policy=RiskPolicy.HIGH,
                new_policy=RiskPolicy.MODERATE,
                changed_by="manager",
                reason="VIX spike above 28",
                vix_level=28.5,
                drawdown_pct=14.2,
                trigger_type=PolicyTrigger.VIX,
            )
            session.add(entry)

    def test_02_query_history(self):
        with get_db_session() as session:
            history = session.query(PolicyHistory).order_by(PolicyHistory.timestamp.desc()).all()
            self.assertGreaterEqual(len(history), 1)
            latest = history[0]
            self.assertEqual(latest.old_policy, RiskPolicy.HIGH)
            self.assertEqual(latest.new_policy, RiskPolicy.MODERATE)
            self.assertEqual(latest.trigger_type, PolicyTrigger.VIX)

    def test_99_cleanup(self):
        with get_db_session() as session:
            session.query(PolicyHistory).delete()


class TestMarketNews(unittest.TestCase):
    """Test market_news table."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_insert_news(self):
        with get_db_session() as session:
            news = MarketNews(
                source="Reuters",
                headline="Fed raises rates by 50bps",
                impact_rating=ImpactRating.HIGH,
                affected_assets="SPY,QQQ,TLT",
                processed_by_manager=False,
            )
            session.add(news)

    def test_02_query_unprocessed(self):
        with get_db_session() as session:
            unprocessed = (
                session.query(MarketNews)
                .filter_by(processed_by_manager=False)
                .all()
            )
            self.assertGreaterEqual(len(unprocessed), 1)

    def test_99_cleanup(self):
        with get_db_session() as session:
            session.query(MarketNews).filter_by(headline="Fed raises rates by 50bps").delete()


class TestPortfolioSnapshot(unittest.TestCase):
    """Test portfolio_snapshots table."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_insert_snapshot(self):
        with get_db_session() as session:
            snap = PortfolioSnapshot(
                total_equity=125000.0,
                cash_balance=15000.0,
                daily_pnl=250.0,
                drawdown_pct=5.2,
                vix_level=18.5,
                positions_count=8,
                leverage=1.4,
                risk_policy=RiskPolicy.HIGH,
            )
            session.add(snap)

    def test_02_query_latest(self):
        with get_db_session() as session:
            latest = (
                session.query(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .first()
            )
            self.assertIsNotNone(latest)
            self.assertAlmostEqual(latest.total_equity, 125000.0)

    def test_99_cleanup(self):
        with get_db_session() as session:
            session.query(PortfolioSnapshot).delete()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Test DB: {_TEST_DB}")
    unittest.main(verbosity=2)
