"""
run_predictions.py — Predictions Agent Main Entry Point

Orchestrates the full forecasting pipeline for one or all supported assets:

  1. Run HMM regime detector (always, gates all other models)
  2. Activate models appropriate for the detected regime
  3. Collect ModelSignal outputs from all active models
  4. Pass signals to the Ensemble layer
  5. Write result to predictions table (if confidence >= 0.6)
  6. Prune old predictions rows (TTL = 90 days)

Run schedule (managed externally by cron / Kubernetes CronJob):
  - Every 6h (crypto) or daily (stocks) for full pipeline
  - HMM + Monte Carlo + ARIMA + LightGBM run every cycle
  - Prophet + LSTM + TFT run on the 6h/daily scheduled tick only

Usage
-----
    # Single asset, dry run (no DB write):
    python agents/research/predictions/run_predictions.py --asset BTC/USD --dry-run

    # All assets:
    python agents/research/predictions/run_predictions.py --all-assets

    # Force retrain slow models:
    python agents/research/predictions/run_predictions.py --asset BTC/USD --force-retrain

    # Specific model only (debugging):
    python agents/research/predictions/run_predictions.py --asset BTC/USD --model lgbm
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

import pandas as pd

from agents.common.database import init_db
from agents.common.enums import MarketRegime
from agents.research.predictions.data_loader import load_ohlcv, list_supported_assets
from agents.research.predictions.output_writer import write_prediction, prune_old_predictions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slow-model flag: set True when running on the 6h/daily scheduled tick
# Fast-model flag: always True (run HMM, MC, ARIMA, LGBM every cycle)
# ---------------------------------------------------------------------------
_SLOW_MODELS_ENABLED_BY_DEFAULT = True   # flip to False for fast cycles only


# ---------------------------------------------------------------------------
# Model activation table (per regime)
# ---------------------------------------------------------------------------

# Maps regime → set of model names that should be activated.
# HMM and Monte Carlo always run (they are regime-agnostic infrastructure).
# ARIMA is active in BEAR/NEUTRAL (mean-reversion signal).
# LightGBM, Prophet, LSTM are active in BULL/NEUTRAL (momentum/trend signals).
# TFT is always potentially active (regime-neutral multi-horizon model).

_REGIME_ACTIVATION: dict[str, set[str]] = {
    MarketRegime.BULL.value: {
        "hmm", "monte_carlo", "lgbm", "prophet", "lstm", "tft",
    },
    MarketRegime.NEUTRAL.value: {
        "hmm", "monte_carlo", "arima", "lgbm", "prophet", "lstm", "tft",
    },
    MarketRegime.BEAR.value: {
        "hmm", "monte_carlo", "arima",
    },
}

# Slow models (expensive / infrequent) — only run when --slow-models flag passed
_SLOW_MODEL_NAMES = {"prophet", "lstm", "tft"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_asset(
    asset: str,
    dry_run: bool = False,
    force_retrain: bool = False,
    model_filter: str | None = None,
    run_slow_models: bool = _SLOW_MODELS_ENABLED_BY_DEFAULT,
) -> dict:
    """
    Run the full prediction pipeline for a single asset.

    Returns a summary dict with the ensemble result (or None if below threshold).
    """
    logger.info("=" * 60)
    logger.info("Running predictions for: %s", asset)

    # --- Load data ---
    df = load_ohlcv(asset, min_rows=100)
    logger.info("[%s] Loaded %d rows (latest: %s)", asset, len(df), df["timestamp"].iloc[-1])

    # --- Step 1: Always run HMM first to determine regime ---
    from agents.research.predictions.models.hmm_regime import HMMRegimeDetector
    hmm = HMMRegimeDetector(asset=asset)
    hmm.fit(df)
    hmm_signal = hmm.predict(df)
    regime = hmm_signal.meta.get("regime", "NEUTRAL")
    logger.info("[%s] Regime detected: %s", asset, regime)

    # --- Step 2: Determine which models to activate ---
    active_model_names = _REGIME_ACTIVATION.get(regime, _REGIME_ACTIVATION[MarketRegime.NEUTRAL.value])

    if not run_slow_models:
        active_model_names = active_model_names - _SLOW_MODEL_NAMES

    if model_filter:
        # Single-model debug mode
        active_model_names = {model_filter} | {"hmm"}

    logger.info("[%s] Active models: %s", asset, sorted(active_model_names))

    # --- Step 3: Run each active model ---
    signals = [hmm_signal]  # HMM always included

    model_runners = _get_model_runners(asset)

    for model_name, model_factory in model_runners.items():
        if model_name not in active_model_names or model_name == "hmm":
            continue
        try:
            model = model_factory()
            model.fit(df, force_retrain=force_retrain)
            sig = model.predict(df)
            signals.append(sig)
            logger.info(
                "[%s] %s → %s (conf=%.3f)", asset, model_name, sig.signal, sig.confidence
            )
        except ImportError as exc:
            logger.warning(
                "[%s] Skipping %s — dependency not installed: %s", asset, model_name, exc
            )
        except Exception as exc:
            logger.error("[%s] Model %s failed: %s", asset, model_name, exc, exc_info=True)

    # --- Step 4: Ensemble ---
    from agents.research.predictions.models.ensemble import EnsembleForecaster
    ensemble = EnsembleForecaster()
    result = ensemble.aggregate(signals)
    result["regime"] = regime
    result["forecast_horizon"] = 14

    candle_ts = df["timestamp"].iloc[-1]
    if isinstance(candle_ts, pd.Timestamp):
        candle_ts = candle_ts.to_pydatetime()

    logger.info(
        "[%s] Ensemble → %s conf=%.3f (regime=%s)",
        asset, result["signal"], result["confidence"], regime,
    )

    # --- Step 5: Write to DB ---
    written = write_prediction(
        asset=asset,
        candle_timestamp=candle_ts,
        ensemble_result=result,
        dry_run=dry_run,
    )

    return {"asset": asset, "result": result, "written": written is not None}


def _get_model_runners(asset: str) -> dict:
    """
    Returns a dict of {model_name: factory_fn} for all supported models.
    Each factory_fn is a zero-arg callable that returns a fitted-ready model instance.
    Models with missing dependencies will log a warning and be skipped at runtime.
    """
    from agents.research.predictions.models.monte_carlo import MonteCarloForecaster
    from agents.research.predictions.models.arima_forecaster import ARIMAForecaster
    from agents.research.predictions.models.lgbm_forecaster import LGBMForecaster

    runners = {
        "monte_carlo": lambda: MonteCarloForecaster(asset=asset),
        "arima":       lambda: ARIMAForecaster(asset=asset),
        "lgbm":        lambda: LGBMForecaster(asset=asset),
    }

    # Slow models — imported lazily; ImportError caught in run_asset
    def _prophet():
        from agents.research.predictions.models.prophet_forecaster import ProphetForecaster
        return ProphetForecaster(asset=asset)

    def _lstm():
        from agents.research.predictions.models.lstm_forecaster import LSTMForecaster
        return LSTMForecaster(asset=asset)

    def _tft():
        from agents.research.predictions.models.tft_forecaster import TFTForecaster
        return TFTForecaster(asset=asset)

    runners["prophet"] = _prophet
    runners["lstm"]    = _lstm
    runners["tft"]     = _tft

    return runners


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="TradeBot Predictions Agent — generates ML forecast signals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--asset", help="Single asset to forecast, e.g. BTC/USD")
    group.add_argument("--all-assets", action="store_true", help="Run all supported assets")

    p.add_argument("--dry-run",        action="store_true", help="Skip DB write; log only")
    p.add_argument("--force-retrain",  action="store_true", help="Force retrain all models")
    p.add_argument("--slow-models",    action="store_true", default=True,
                   help="Include slow models (Prophet/LSTM/TFT). Default: True")
    p.add_argument("--model",          help="Run a single model only (debug)")
    p.add_argument("--log-level",      default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def main():
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # Ensure predictions table exists
    init_db()

    if args.all_assets:
        assets = list(list_supported_assets().keys())
    else:
        assets = [args.asset]

    results = []
    for asset in assets:
        try:
            r = run_asset(
                asset=asset,
                dry_run=args.dry_run,
                force_retrain=args.force_retrain,
                model_filter=args.model,
                run_slow_models=args.slow_models,
            )
            results.append(r)
        except Exception as exc:
            logger.error("Asset %s failed: %s", asset, exc, exc_info=True)

    # Prune old rows (DB footprint rule #4: 90-day TTL)
    if not args.dry_run:
        pruned = prune_old_predictions()
        if pruned:
            logger.info("Pruned %d old prediction rows (TTL=90d)", pruned)

    # Summary
    written_count = sum(1 for r in results if r.get("written"))
    logger.info(
        "Done — %d/%d assets produced actionable signals (written to DB)",
        written_count, len(results),
    )


if __name__ == "__main__":
    main()
