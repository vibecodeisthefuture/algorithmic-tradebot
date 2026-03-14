"""
BaseForecaster — Abstract Base Class for All Predictions Agent Models

Every forecasting model in this agent (Monte Carlo, ARIMA, LightGBM, HMM,
Prophet, LSTM, TFT) must subclass BaseForecaster and implement fit() and
predict(). This contract ensures:

  1. The ensemble layer can call any model through the same interface.
  2. The walk-forward harness can retrain any model without special casing.
  3. All models produce a ModelSignal — the canonical output type.

Usage pattern (inside run_predictions.py):
    model = LGBMForecaster(asset="BTC/USD")
    model.fit(df)
    signal = model.predict(df)
"""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from agents.research.predictions.model_signal import ModelSignal


class BaseForecaster(ABC):
    """
    Abstract interface all Predictions Agent models must implement.

    Subclass responsibilities
    -------------------------
    fit(df)     : Train or refit the model on the provided OHLCV DataFrame.
                  Models that are stateless (Monte Carlo, ARIMA) refit on
                  every call. Stateful models (LSTM, TFT, LightGBM) cache
                  trained weights and skip refit unless `force_retrain=True`.

    predict(df) : Generate a ModelSignal from the most recent data window.
                  Must NOT use any rows beyond the last row of df (no leakage).
                  Returns a ModelSignal with signal, confidence, pred_price.

    Regime gating
    -------------
    Before calling fit() or predict(), run_predictions.py checks the current
    MarketRegime and decides whether to invoke this model at all. The model
    itself is NOT responsible for regime gating — it always predicts if called.

    DB footprint
    ------------
    Models must NOT write directly to tradebot.db. Only output_writer.py
    writes to the predictions table, after the ensemble aggregates all signals.
    """

    def __init__(self, asset: str, forecast_horizon: int = 14):
        """
        Parameters
        ----------
        asset : str
            Ticker identifier, e.g. "BTC/USD" or "AAPL".
        forecast_horizon : int
            Number of candles ahead to forecast. Default: 14 (≈3.5 days on 6h).
        """
        self.asset = asset
        self.forecast_horizon = forecast_horizon
        self._is_fitted: bool = False

    # -----------------------------------------------------------------------
    # Required interface
    # -----------------------------------------------------------------------

    @abstractmethod
    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """
        Train or refit the model.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame with columns [timestamp, open, high, low, close, volume].
            Sorted ascending by timestamp. No future data beyond the last row.
        force_retrain : bool
            If True, retrain even if the model is already fitted.
            Used by the 4-week scheduled retrain job.
        """
        ...

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        Generate a forecast signal from the most recent window.

        Parameters
        ----------
        df : pd.DataFrame
            Same format as fit(). predict() uses only the latest window
            (e.g. last 60 rows for LSTM, last 500 for HMM).

        Returns
        -------
        ModelSignal
            signal     : "BUY" | "SELL" | "HOLD"
            confidence : 0.0–1.0
            pred_price : float (price forecast or current close as fallback)
            meta       : model-specific scalars for model_breakdown JSON
        """
        ...

    # -----------------------------------------------------------------------
    # Optional hooks (override as needed)
    # -----------------------------------------------------------------------

    def validate_input(self, df: pd.DataFrame) -> None:
        """
        Basic sanity check before fit/predict.
        Raises ValueError if required columns are missing or df is too short.
        Subclasses can extend this for model-specific requirements.
        """
        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"[{self.asset}] Missing columns: {missing}")
        if df.empty:
            raise ValueError(f"[{self.asset}] DataFrame is empty.")

    @property
    def is_fitted(self) -> bool:
        """True if fit() has been called at least once successfully."""
        return self._is_fitted

    @property
    def model_name(self) -> str:
        """
        Short identifier used as the model_breakdown JSON key.
        Defaults to the lowercase class name. Override if needed.
        """
        return type(self).__name__.lower().replace("forecaster", "").replace("detector", "")

    def __repr__(self) -> str:
        fitted_str = "fitted" if self._is_fitted else "unfitted"
        return f"<{type(self).__name__} asset={self.asset!r} horizon={self.forecast_horizon} [{fitted_str}]>"
