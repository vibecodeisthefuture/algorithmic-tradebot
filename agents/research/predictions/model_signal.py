"""
ModelSignal — Shared Data Contract for the Predictions Agent

Every forecasting model in this agent produces a ModelSignal as its output.
The ensemble layer (ensemble.py) consumes a list of ModelSignals and produces
the final weighted result written to the predictions table.

Design rule: all fields are lightweight Python primitives / strings.
No numpy arrays, no DataFrames, no model objects — keep this dataclass
serializable and dependency-free so it can be logged, printed, and stored
as JSON without extra scaffolding.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class ModelSignal:
    """
    Unified output contract for all Predictions Agent forecasting models.

    Attributes
    ----------
    name : str
        Unique model identifier, e.g. "monte_carlo", "lgbm", "hmm".
        Used as the key in the model_breakdown JSON stored in tradebot.db.

    signal : str
        Directional signal: "BUY" | "SELL" | "HOLD".
        - BUY  : model expects price to rise over the forecast horizon
        - SELL : model expects price to fall
        - HOLD : model has insufficient conviction (< threshold)

    confidence : float
        Model-specific confidence in [0.0, 1.0].
        Interpretation varies by model:
          monte_carlo → normalized distance of P50 from current price
          lgbm        → probability of upward move (prob_up or 1-prob_up)
          arima       → 1 - (CI width / forecast value) normalised
          prophet     → 1 - uncertainty_band_width (capped 0–1)
          lstm        → heuristic based on prediction magnitude
          tft         → P50 distance normalized by P10–P90 band width
          hmm         → N/A; regime detector always confidence=1.0
          ensemble    → softmax-weighted vote score (final arbiter)

    pred_price : float
        Model's point estimate of the forecasted price at horizon end.
        Set to current price for models that don't produce price targets
        (e.g., pure classifiers like LightGBM — use current close as fallback).

    meta : dict
        Optional model-specific extras stored in model_breakdown JSON.
        Examples:
          monte_carlo → {"p05": ..., "p50": ..., "p95": ...}
          lgbm        → {"prob_up": 0.61, "top_features": ["rsi_14", "macd"]}
          arima       → {"ci_lo": ..., "ci_hi": ...}
          prophet     → {"yhat_lo": ..., "yhat_hi": ..., "uncertainty": ...}
          tft         → {"p10": ..., "p90": ..., "h1": ..., "h6": ..., "h14": ...}
        Keep values scalar — no arrays.
    """

    name: str
    signal: str          # "BUY" | "SELL" | "HOLD"
    confidence: float    # 0.0–1.0
    pred_price: float
    meta: dict = field(default_factory=dict)

    # -----------------------------------------------------------------------
    # Validation helpers
    # -----------------------------------------------------------------------

    def __post_init__(self):
        if self.signal not in ("BUY", "SELL", "HOLD"):
            raise ValueError(
                f"ModelSignal.signal must be 'BUY', 'SELL', or 'HOLD' — got {self.signal!r}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"ModelSignal.confidence must be in [0.0, 1.0] — got {self.confidence}"
            )

    # -----------------------------------------------------------------------
    # Serialization helpers (used by output_writer.py)
    # -----------------------------------------------------------------------

    def to_breakdown_entry(self, weight: Optional[float] = None) -> dict:
        """
        Compact dict representation for inclusion in model_breakdown JSON.
        Only scalar values — never arrays or nested objects.

        Example output (lgbm):
            {"signal": "BUY", "confidence": 0.61, "pred_price": 45200,
             "weight": 0.30, "prob_up": 0.61, "top_features": ["rsi_14"]}
        """
        entry = {
            "signal": self.signal,
            "confidence": round(self.confidence, 4),
            "pred_price": round(self.pred_price, 4),
        }
        if weight is not None:
            entry["weight"] = round(weight, 4)
        entry.update(self.meta)
        return entry

    def __repr__(self) -> str:
        return (
            f"<ModelSignal name={self.name!r} signal={self.signal} "
            f"conf={self.confidence:.3f} price={self.pred_price:.2f}>"
        )
