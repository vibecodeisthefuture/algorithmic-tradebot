"""
OutputWriter — Writes Ensemble Predictions to tradebot.db

This is the ONLY module that writes to the predictions table.
Individual models never write directly to the database.

DB Footprint Rules Enforced Here
---------------------------------
1. One row per asset per cycle (ensemble output only).
2. model_breakdown is a compact JSON summary — no raw arrays.
3. Rows with confidence < CONFIDENCE_THRESHOLD are silently discarded.
4. A pruning call removes rows older than TTL_DAYS on each write cycle.

Usage
-----
    from agents.research.predictions.output_writer import write_prediction, prune_old_predictions

    write_prediction(
        asset="BTC/USD",
        candle_timestamp=df["timestamp"].iloc[-1],
        ensemble_result={
            "signal": "BUY",
            "confidence": 0.71,
            "estimated_price": 45200.0,
            "regime": "BULL",
            "model_breakdown": { ... },
            "forecast_horizon": 14,
        }
    )
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from agents.common.database import get_db_session
from agents.common.models import Prediction
from agents.common.enums import PredictionSignal, MarketRegime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Only write to DB if ensemble confidence meets this threshold.
# Signals below this are too uncertain to be actionable.
CONFIDENCE_THRESHOLD = 0.60

# Rows older than this are pruned to prevent DB bloat.
TTL_DAYS = 90


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_prediction(
    asset: str,
    candle_timestamp: datetime,
    ensemble_result: dict,
    dry_run: bool = False,
) -> Optional[Prediction]:
    """
    Write an ensemble prediction row to the predictions table in tradebot.db.

    Enforces the confidence gate — rows below CONFIDENCE_THRESHOLD (0.60)
    are discarded and not written to the database. Consumers (Strategy Agent,
    Portfolio Tracker) should therefore always be able to trust that any row
    in the predictions table is actionable.

    Parameters
    ----------
    asset : str
        Ticker identifier, e.g. "BTC/USD".
    candle_timestamp : datetime
        The candle bar's timestamp that the signal is based on.
        This is NOT the current wall-clock time — it's the data timestamp.
    ensemble_result : dict
        Output dict from EnsembleForecaster.aggregate(). Expected keys:
            signal          : "BUY" | "SELL" | "HOLD"
            confidence      : float 0.0–1.0
            estimated_price : float (weighted avg price from all models)
            regime          : "BULL" | "NEUTRAL" | "BEAR" (from HMM)
            model_breakdown : dict  (compact per-model summaries)
            forecast_horizon: int   (candles ahead, default 14)
    dry_run : bool
        If True, log what would be written but skip the actual DB write.

    Returns
    -------
    Prediction or None
        The written ORM row, or None if the signal was below threshold.
    """
    confidence = ensemble_result.get("confidence", 0.0)
    signal_str = ensemble_result.get("signal", "HOLD")

    # --- Confidence gate (DB footprint rule #3) ---
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(
            "[%s] Signal %s discarded — confidence %.3f < %.2f threshold",
            asset, signal_str, confidence, CONFIDENCE_THRESHOLD,
        )
        return None

    # --- Map string values to enums ---
    try:
        signal_enum = PredictionSignal(signal_str)
    except ValueError:
        logger.error("[%s] Invalid signal value %r — skipping write", asset, signal_str)
        return None

    regime_str = ensemble_result.get("regime", "NEUTRAL")
    try:
        regime_enum = MarketRegime(regime_str)
    except ValueError:
        logger.warning("[%s] Unknown regime %r — defaulting to NEUTRAL", asset, regime_str)
        regime_enum = MarketRegime.NEUTRAL

    # --- Build ORM row ---
    row = Prediction(
        timestamp=candle_timestamp,
        asset=asset,
        signal=signal_enum,
        confidence=round(confidence, 4),
        forecast_horizon=ensemble_result.get("forecast_horizon", 14),
        regime=regime_enum,
        model_breakdown=ensemble_result.get("model_breakdown"),
    )

    if dry_run:
        logger.info("[DRY RUN] Would write: %s", row)
        return row

    # --- Write to DB ---
    with get_db_session() as session:
        session.add(row)

    logger.info(
        "[%s] Prediction written: %s conf=%.3f regime=%s",
        asset, signal_enum.value, confidence, regime_enum.value,
    )
    return row


def prune_old_predictions(ttl_days: int = TTL_DAYS, dry_run: bool = False) -> int:
    """
    Delete predictions rows older than ttl_days to prevent DB bloat.

    Should be called once per run cycle (at the end of run_predictions.py).
    Default TTL is 90 days — sufficient for the Analytics Agent's rolling
    accuracy window.

    Parameters
    ----------
    ttl_days : int
        Rows created before now - ttl_days are deleted.
    dry_run : bool
        If True, count matching rows but do not delete.

    Returns
    -------
    int
        Number of rows deleted (or that would be deleted in dry_run).
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=ttl_days)

    with get_db_session() as session:
        query = session.query(Prediction).filter(Prediction.created_at < cutoff)
        count = query.count()

        if dry_run:
            logger.info("[DRY RUN] Would prune %d rows older than %d days", count, ttl_days)
        elif count > 0:
            query.delete(synchronize_session=False)
            logger.info("Pruned %d predictions rows older than %d days", count, ttl_days)

    return count
