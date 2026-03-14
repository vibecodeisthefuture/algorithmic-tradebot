"""
EnsembleForecaster — Adaptive Weighted Signal Aggregator

PRIMARY USE CASE
----------------
Final synthesis layer. Takes ModelSignal outputs from all active models and
produces a single confidence-weighted BUY/SELL/HOLD decision. This is the
ONLY signal that consumers (Strategy Agent, Portfolio Tracker) should act on.
Never use individual model signals downstream — always use the ensemble output.

WHY AN ENSEMBLE?
----------------
No single forecasting model dominates across all market conditions:
  - GBM (Monte Carlo) underestimates tails but is reliable for risk bands
  - ARIMA excels in mean-reverting conditions, fails in trends
  - LightGBM is the best directional classifier but needs regime gating
  - Prophet captures seasonality that other models miss
  - LSTM learns nonlinear patterns invisible to linear models
  - TFT provides the richest multi-horizon uncertainty quantification

Combining them via adaptive weights reduces variance and improves robustness
compared to any single model — at the cost of losing model-specific precision.

DB FOOTPRINT
------------
The ensemble writes a SINGLE predictions row per asset per cycle.
All per-model summaries are packed into the model_breakdown JSON column.
No separate per-model DB rows are ever written.
Only rows with confidence >= CONFIDENCE_THRESHOLD (0.60) are passed to
output_writer.py for DB persistence — lower-confidence cycles are discarded.
"""

import logging
from collections import deque
from typing import Optional

import numpy as np

from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)

# Only pass ensemble signal downstream if confidence meets this threshold
CONFIDENCE_THRESHOLD = 0.60

# Softmax temperature — higher = more uniform weights, lower = more winner-takes-all
SOFTMAX_TEMP = 1.0


class EnsembleForecaster:
    """
    Adaptive weighted ensemble using softmax over rolling directional accuracy.

    Weights are initialized equally. After each prediction cycle where ground
    truth becomes available, update_accuracy() updates the rolling accuracy
    window per model. Weights are recomputed as softmax over accuracy scores,
    so consistently accurate models receive higher weight over time.

    Parameters
    ----------
    window : int
        Rolling accuracy window (number of past predictions to track per model).
        Default: 50 candles — roughly 12 days on 6h candles.
    confidence_threshold : float
        Minimum ensemble confidence to pass signal downstream.
        Default: 0.60. Signals below this are discarded (not written to DB).
    """

    # Initial weights per model (equal on first run, before accuracy history)
    # Reflect relative expected reliability based on brainstorm design notes.
    # These are PRIOR weights only — they are overridden by rolling accuracy.
    _PRIOR_WEIGHTS: dict[str, float] = {
        "monte_carlo": 0.10,   # Weak directional signal; useful for risk bands
        "arima":       0.20,   # Statistical baseline; regime-dependent
        "lgbm":        0.30,   # Primary directional classifier; highest prior
        "prophet":     0.20,   # Seasonality; strong in BULL/NEUTRAL
        "lstm":        0.15,   # Nonlinear patterns; high variance
        "tft":         0.20,   # Multi-horizon; richest output
        "hmm":         0.00,   # Regime detector only — excluded from vote
    }

    def __init__(
        self,
        window: int = 50,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self.window = window
        self.confidence_threshold = confidence_threshold

        # Rolling accuracy deques per model: deque of {0, 1} (wrong/correct)
        self._accuracy_history: dict[str, deque] = {}
        # Computed weights (prior-based until enough accuracy history)
        self._weights: dict[str, float] = {}

    # -----------------------------------------------------------------------
    # Accuracy tracking (called after ground truth is known)
    # -----------------------------------------------------------------------

    def update_accuracy(self, model_name: str, was_correct: bool) -> None:
        """
        Record whether a model's last prediction was directionally correct.

        Call this from the Analytics Agent after the next candle closes:
            ensemble.update_accuracy("lgbm", actual_direction == predicted_direction)

        Parameters
        ----------
        model_name : str
            Model identifier (matches ModelSignal.name).
        was_correct : bool
            True if the model's directional signal matched the actual price move.
        """
        if model_name not in self._accuracy_history:
            self._accuracy_history[model_name] = deque(maxlen=self.window)
        self._accuracy_history[model_name].append(int(was_correct))
        self._recompute_weights()

    def _recompute_weights(self) -> None:
        """
        Recompute model weights as softmax over rolling accuracy scores.
        Falls back to prior weights for models with insufficient history (<5 records).
        """
        scores = {}
        for name, history in self._accuracy_history.items():
            if len(history) >= 5:
                scores[name] = np.mean(list(history))

        if not scores:
            self._weights = {}   # will use prior weights in aggregate()
            return

        # Softmax over accuracy scores
        vals = np.array(list(scores.values())) / SOFTMAX_TEMP
        exp_vals = np.exp(vals - vals.max())   # numerically stable
        softmax  = exp_vals / exp_vals.sum()

        self._weights = {name: float(w) for name, w in zip(scores.keys(), softmax)}
        logger.debug("Ensemble weights recomputed: %s", self._weights)

    # -----------------------------------------------------------------------
    # Aggregation
    # -----------------------------------------------------------------------

    def aggregate(self, signals: list[ModelSignal]) -> dict:
        """
        Aggregate a list of ModelSignals into a single ensemble result.

        Voting mechanism:
            - BUY  counts as +1 (weighted by signal confidence × model weight)
            - SELL counts as -1
            - HOLD counts as  0 (no contribution)
            - HMM signals are always excluded from voting (regime-only)

        Final signal classification:
            vote_score > +0.15  → BUY
            vote_score < -0.15  → SELL
            otherwise           → HOLD

        Parameters
        ----------
        signals : list[ModelSignal]
            Outputs from all active models in this cycle.

        Returns
        -------
        dict with keys:
            signal          : "BUY" | "SELL" | "HOLD"
            confidence      : float 0.0–1.0
            score           : raw vote score (positive = bullish)
            estimated_price : weighted average price estimate
            model_breakdown : compact dict for DB storage
            model_weights   : weights used in this cycle
        """
        # Filter out HMM — it is a regime detector, not a directional voter
        voting_signals = [s for s in signals if s.name != "hmm"]

        if not voting_signals:
            return self._neutral_result(signals)

        # Determine weights for this cycle
        weights = self._get_weights(voting_signals)

        vote_score    = 0.0
        total_weight  = 0.0
        price_terms   = []

        for sig in voting_signals:
            w = weights.get(sig.name, 1.0 / len(voting_signals))
            direction = (
                +1 if sig.signal == "BUY"  else
                -1 if sig.signal == "SELL" else
                 0   # HOLD — no vote contribution
            )
            vote_score   += direction * w * sig.confidence
            total_weight += w
            if sig.pred_price and sig.pred_price > 0:
                price_terms.append((sig.pred_price, w))

        # Normalize vote score
        final_score = vote_score / (total_weight + 1e-9)

        # Signal classification using ±0.15 threshold
        if final_score > 0.15:
            final_signal = "BUY"
        elif final_score < -0.15:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"

        # Confidence is the absolute normalized score, clipped [0, 1]
        confidence = float(min(abs(final_score), 1.0))

        # Weighted average price estimate (excludes models without price output)
        if price_terms:
            weighted_price = (
                sum(p * w for p, w in price_terms) / sum(w for _, w in price_terms)
            )
        else:
            weighted_price = 0.0

        # Build compact model_breakdown JSON
        breakdown = {}
        for sig in signals:
            w = weights.get(sig.name) if sig.name != "hmm" else None
            breakdown[sig.name] = sig.to_breakdown_entry(weight=w)

        logger.info(
            "Ensemble: %s conf=%.3f score=%.4f (models: %s)",
            final_signal, confidence, final_score,
            [f"{s.name}→{s.signal}" for s in signals],
        )

        return {
            "signal":           final_signal,
            "confidence":       round(confidence, 4),
            "score":            round(final_score, 4),
            "estimated_price":  round(weighted_price, 4),
            "model_breakdown":  breakdown,
            "model_weights":    {k: round(v, 4) for k, v in weights.items()},
        }

    def _get_weights(self, voting_signals: list[ModelSignal]) -> dict[str, float]:
        """
        Return per-model weights for this cycle.
        Uses learned rolling-accuracy weights if available; falls back to priors.
        """
        weights = {}
        for sig in voting_signals:
            if sig.name in self._weights:
                weights[sig.name] = self._weights[sig.name]
            else:
                # Prior weight — used until enough accuracy history exists
                weights[sig.name] = self._PRIOR_WEIGHTS.get(
                    sig.name, 1.0 / len(voting_signals)
                )

        # Normalize so weights sum to 1.0
        total = sum(weights.values()) or 1.0
        return {k: v / total for k, v in weights.items()}

    def _neutral_result(self, signals: list[ModelSignal]) -> dict:
        """Fallback result when no voting signals are available."""
        breakdown = {s.name: s.to_breakdown_entry() for s in signals}
        return {
            "signal":          "HOLD",
            "confidence":      0.0,
            "score":           0.0,
            "estimated_price": 0.0,
            "model_breakdown": breakdown,
            "model_weights":   {},
        }
