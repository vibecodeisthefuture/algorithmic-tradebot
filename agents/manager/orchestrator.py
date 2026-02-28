#!/usr/bin/env python3
"""
Manager Orchestrator — The Conductor of the Blackboard

This is the Project Manager Agent's main loop.  It polls the SQLite
database (the "Blackboard") for state changes and manages the lifecycle
of strategies, news events, risk policies, and inter-agent events.

When run in ``--loop`` mode, the Orchestrator subscribes to the ZeroMQ
event bus so it wakes up **instantly** on new events (liquidation
cascades, circuit breakers, etc.) instead of sleeping the full poll
interval.  The DB sweep still runs every iteration as a safety net.

Usage:
    py agents/manager/orchestrator.py            # single sweep
    py agents/manager/orchestrator.py --loop 60  # poll every 60 s
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.common.database import get_db_session, init_db
from agents.common.models import (
    SystemState,
    MarketNews,
    Strategy,
    BacktestResult,
    EventLog,
    PolicyHistory,
)
from agents.common.enums import (
    StrategyStatus,
    ImpactRating,
    EventType,
    EventUrgency,
    RiskPolicy,
    PolicyTrigger,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MANAGER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("orchestrator")


# ---------------------------------------------------------------------------
# Helper: read / write system_state
# ---------------------------------------------------------------------------


def get_state(session, key: str, default: str = "") -> str:
    """Read a key from system_state, returning *default* if missing."""
    row = session.query(SystemState).filter_by(key=key).first()
    return row.value if row else default


def set_state(session, key: str, value: str) -> None:
    """Upsert a key in system_state."""
    row = session.query(SystemState).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        session.add(SystemState(key=key, value=value))


# ---------------------------------------------------------------------------
# Sweep functions — one per responsibility
# ---------------------------------------------------------------------------


def process_unread_news(session) -> int:
    """
    Poll market_news WHERE processed_by_manager = False.

    For HIGH / CRITICAL news: flip system risk_mode if warranted.
    Marks rows as processed.
    """
    unprocessed = (
        session.query(MarketNews)
        .filter_by(processed_by_manager=False)
        .order_by(MarketNews.discovered_at)
        .all()
    )

    if not unprocessed:
        return 0

    log.info(f"Found {len(unprocessed)} unprocessed news event(s)")

    for news in unprocessed:
        log.info(f"  → [{news.impact_rating.value}] {news.headline[:60]}")

        # CRITICAL or HIGH impact → consider risk mode change
        if news.impact_rating in (ImpactRating.HIGH, ImpactRating.CRITICAL):
            current_mode = get_state(session, "risk_mode", "HIGH")
            if current_mode in ("HIGH", "MODERATE_AGGRESSIVE"):
                log.warning(
                    f"  ⚠ High-impact news detected. "
                    f"Current risk_mode={current_mode}. "
                    f"Recommendation: review for potential downshift."
                )
                # Emit event for audit trail (actual policy change requires
                # explicit Manager decision — we just flag it here).
                session.add(
                    EventLog(
                        event_type=EventType.NEWS_CRITICAL,
                        urgency=EventUrgency.URGENT,
                        source_agent="manager_orchestrator",
                        target_agent="manager",
                        summary=f"High-impact news: {news.headline[:80]}",
                        details={
                            "news_id": news.id,
                            "impact": news.impact_rating.value,
                            "opportunities": news.opportunities_identified,
                        },
                    )
                )

        news.processed_by_manager = True

    return len(unprocessed)


def review_new_strategies(session) -> int:
    """
    Poll strategies WHERE status = NEW.

    Auto-promotes strategies that have a non-empty `parameters` field
    to READY_FOR_BACKTEST.  Strategies without parameters are flagged
    for human review.
    """
    new_strategies = (
        session.query(Strategy)
        .filter_by(status=StrategyStatus.NEW)
        .order_by(Strategy.created_at)
        .all()
    )

    if not new_strategies:
        return 0

    log.info(f"Found {len(new_strategies)} new strateg(y/ies)")
    promoted = 0

    for strat in new_strategies:
        # Basic validation: must have a name and some content
        if strat.parameters or strat.notes:
            strat.status = StrategyStatus.READY_FOR_BACKTEST
            log.info(f"  ✓ Promoted '{strat.name}' → READY_FOR_BACKTEST")
            session.add(
                EventLog(
                    event_type=EventType.STRATEGY_VALIDATED,
                    urgency=EventUrgency.INFO,
                    source_agent="manager_orchestrator",
                    summary=f"Strategy '{strat.name}' promoted to READY_FOR_BACKTEST",
                    details={"strategy_id": strat.id, "name": strat.name},
                )
            )
            promoted += 1
        else:
            log.warning(
                f"  ⚠ Strategy '{strat.name}' has no parameters/notes — needs review"
            )

    return promoted


def review_completed_backtests(session) -> int:
    """
    Poll strategies WHERE status = BACKTEST_COMPLETE.

    Checks backtest_results for that strategy.  If Sharpe ≥ 0.8 and
    max_drawdown ≤ 30%, promotes to LIVE_PAPER.  Otherwise rejects.
    """
    completed = (
        session.query(Strategy)
        .filter_by(status=StrategyStatus.BACKTEST_COMPLETE)
        .all()
    )

    if not completed:
        return 0

    log.info(f"Found {len(completed)} backtest-complete strateg(y/ies)")
    reviewed = 0

    for strat in completed:
        # Get the latest backtest result
        result = (
            session.query(BacktestResult)
            .filter_by(strategy_id=strat.id)
            .order_by(BacktestResult.run_at.desc())
            .first()
        )

        if not result:
            log.warning(f"  ⚠ '{strat.name}' marked BACKTEST_COMPLETE but no results found")
            continue

        sharpe = result.sharpe_ratio or 0
        drawdown = result.max_drawdown or 100

        if sharpe >= 0.8 and drawdown <= 30:
            strat.status = StrategyStatus.LIVE_PAPER
            log.info(
                f"  ✓ '{strat.name}' APPROVED → LIVE_PAPER "
                f"(Sharpe={sharpe:.2f}, DD={drawdown:.1f}%)"
            )
            session.add(
                EventLog(
                    event_type=EventType.STRATEGY_VALIDATED,
                    urgency=EventUrgency.INFO,
                    source_agent="manager_orchestrator",
                    summary=f"Strategy '{strat.name}' approved for paper trading",
                    details={
                        "strategy_id": strat.id,
                        "sharpe": sharpe,
                        "max_drawdown": drawdown,
                    },
                )
            )
        else:
            strat.status = StrategyStatus.RETIRED
            reason = []
            if sharpe < 0.8:
                reason.append(f"Sharpe {sharpe:.2f} < 0.8")
            if drawdown > 30:
                reason.append(f"Drawdown {drawdown:.1f}% > 30%")
            log.info(
                f"  ✗ '{strat.name}' REJECTED → RETIRED ({'; '.join(reason)})"
            )
            session.add(
                EventLog(
                    event_type=EventType.STRATEGY_REJECTED,
                    urgency=EventUrgency.CAUTION,
                    source_agent="manager_orchestrator",
                    summary=f"Strategy '{strat.name}' rejected: {'; '.join(reason)}",
                    details={
                        "strategy_id": strat.id,
                        "sharpe": sharpe,
                        "max_drawdown": drawdown,
                    },
                )
            )

        reviewed += 1

    return reviewed


def process_pending_events(session) -> int:
    """
    Poll event_log WHERE acknowledged = False.

    Logs them and marks as acknowledged by the Manager.
    Circuit-breaker and critical events get special handling.
    """
    pending = (
        session.query(EventLog)
        .filter_by(acknowledged=False)
        .order_by(EventLog.created_at)
        .all()
    )

    if not pending:
        return 0

    log.info(f"Found {len(pending)} unacknowledged event(s)")

    for evt in pending:
        icon = {
            EventUrgency.INFO: "ℹ",
            EventUrgency.CAUTION: "⚠",
            EventUrgency.URGENT: "🔶",
            EventUrgency.CRITICAL: "🔴",
        }.get(evt.urgency, "•")

        log.info(f"  {icon} [{evt.event_type.value}] {evt.summary[:80]}")

        # Auto-acknowledge INFO and CAUTION
        evt.acknowledged = True
        evt.acknowledged_by = "manager_orchestrator"
        evt.acknowledged_at = datetime.now(timezone.utc)

        # CRITICAL events → flag for human review
        if evt.urgency == EventUrgency.CRITICAL:
            evt.response = "AUTO-FLAGGED for human review"
            log.warning(f"    → CRITICAL event flagged for human review")

    return len(pending)

# ---------------------------------------------------------------------------
# Retention: prune old acknowledged events
# ---------------------------------------------------------------------------

EVENT_RETENTION_DAYS = 30


def prune_old_events(session) -> int:
    """
    Delete acknowledged event_log rows older than EVENT_RETENTION_DAYS.

    Unacknowledged events are never pruned (they may still need attention).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=EVENT_RETENTION_DAYS)
    deleted = (
        session.query(EventLog)
        .filter(
            EventLog.acknowledged == True,
            EventLog.created_at < cutoff,
        )
        .delete()
    )
    if deleted:
        log.info(f"Pruned {deleted} acknowledged event(s) older than {EVENT_RETENTION_DAYS} days")
    return deleted


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------


def run_sweep():
    """Execute one complete sweep of all Blackboard tables."""
    log.info("─" * 50)
    log.info("Starting Manager sweep")
    log.info("─" * 50)

    with get_db_session() as session:
        n_news = process_unread_news(session)
        n_strat = review_new_strategies(session)
        n_bt = review_completed_backtests(session)
        n_evt = process_pending_events(session)
        n_pruned = prune_old_events(session)

    total = n_news + n_strat + n_bt + n_evt
    if total:
        log.info(f"Sweep complete: {total} item(s) processed")
    else:
        log.info("Sweep complete: nothing pending")

    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Manager Orchestrator")
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECS",
        help="Poll interval in seconds (0 = single sweep)",
    )
    args = parser.parse_args()

    # Ensure DB exists
    init_db()

    if args.loop > 0:
        # ── Set up ZeroMQ subscriber (optional) ──────────────────────
        subscriber = None
        try:
            from agents.common.event_bus import EventSubscriber

            subscriber = EventSubscriber(topics=[""])  # subscribe to all
            log.info("ZeroMQ event bus connected — will wake on events")
        except Exception:
            log.info("ZeroMQ unavailable — falling back to timed polling")

        log.info(
            "Starting continuous polling (every %ds, "
            "with instant ZeroMQ wake-up). Ctrl+C to stop.",
            args.loop,
        )
        try:
            while True:
                # 1) Drain any queued ZeroMQ events
                if subscriber is not None:
                    events = subscriber.drain()
                    for topic, payload in events:
                        log.info("⚡ Event received [%s]: %s", topic, payload)

                # 2) Run the full DB sweep (always — safety net)
                run_sweep()

                # 3) Wait for next event OR timeout
                if subscriber is not None:
                    msg = subscriber.listen_sync(
                        timeout_ms=args.loop * 1000,
                    )
                    if msg:
                        topic, payload = msg
                        log.info("⚡ Woke on event [%s]: %s", topic, payload)
                else:
                    time.sleep(args.loop)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
        finally:
            if subscriber is not None:
                subscriber.close()
    else:
        run_sweep()


if __name__ == "__main__":
    main()
