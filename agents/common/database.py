"""
Database Engine & Session Management

Provides a SQLite-backed database with WAL mode for concurrent reads.
All agents import `get_db_session()` to interact with the Blackboard.

Usage:
    from agents.common.database import get_db_session

    with get_db_session() as session:
        session.add(Strategy(name="My Strategy", status=StrategyStatus.NEW))
        # auto-commits on exit, auto-rollbacks on exception
"""

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Database path resolution
# ---------------------------------------------------------------------------

# Resolve project root (TradeBot/) from this file's location
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "tradebot.db"

# Allow override via environment variable
_DB_PATH = Path(os.environ.get("TRADEBOT_DB_PATH", str(_DB_PATH)))

# Ensure the data directory exists
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DATABASE_URL = f"sqlite:///{_DB_PATH}"

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

engine = create_engine(
    _DATABASE_URL,
    echo=False,  # Set True for SQL debugging
    connect_args={
        "check_same_thread": False,  # Required for SQLite + multi-thread
        "timeout": 30,               # Wait up to 30s for locks
    },
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode and other SQLite performance pragmas on every connect."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")   # 64MB cache
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout
    cursor.close()


_SessionFactory = sessionmaker(bind=engine)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextmanager
def get_db_session() -> Session:
    """
    Context manager that yields a SQLAlchemy session.

    - Auto-commits on clean exit.
    - Auto-rollbacks on exception, then re-raises.
    - Always closes the session.

    Usage:
        with get_db_session() as session:
            session.add(obj)
    """
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Create all tables defined in models.py.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    """
    from agents.common.models import Base  # noqa: F811 — deferred import
    Base.metadata.create_all(engine)


def get_db_path() -> Path:
    """Return the resolved path to the SQLite database file."""
    return _DB_PATH
