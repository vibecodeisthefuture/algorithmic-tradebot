"""
ProphetForecaster — Facebook Prophet Seasonality & Trend Model

PRIMARY USE CASE
----------------
Multi-period seasonality decomposition and trend confirmation.
Answers: "Does the price exhibit weekly/daily cyclical patterns, and is
the current trend structurally supported?"

Best used as a TREND FILTER alongside LightGBM, not as a precision entry
signal. In BULL regimes, a Prophet BUY confirmation increases ensemble
confidence in LightGBM's BUY signal.

WHEN TO ACTIVATE
----------------
BULL or NEUTRAL regime. Most effective on crypto assets (BTC, ETH) where
weekly/daily cycles are historically strong. Low signal value in BEAR
regimes where breakdowns disrupt seasonal structure.
Runs on the 6h/daily scheduled tick — NOT every cycle.

LIMITATIONS
-----------
- Assumes TREND CONTINUITY — financial markets gap violently. Sudden
  breakdowns confuse the trend changepoint detector.
- `changepoint_prior_scale=0.05` is conservative (fewer changepoints).
  Higher values overfit to noise. Tune per asset if accuracy is poor.
- Volume regressor requires non-null volume. If unavailable, regressor
  is disabled automatically (see _add_volume_regressor flag below).
- Uncertainty bands widen rapidly beyond 7 candles. For >14-candle
  horizons, treat output as directional only — not as price targets.
- Prophet is slow (~5–30s per fit on 3000+ rows). Run on 6h schedule only.

DB FOOTPRINT
------------
Stores only: yhat (final candle), yhat_lo, yhat_hi, uncertainty scalar.
Does NOT store all 14 intermediate forecast rows.
"""

import logging

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)


class ProphetForecaster(BaseForecaster):
    """
    Facebook Prophet trend + seasonality forecaster with optional volume regressor.

    Parameters
    ----------
    asset : str
        Asset identifier.
    forecast_horizon : int
        Candles ahead. Default: 14.
    freq : str
        Pandas frequency string for the candle interval.
        '6h' for crypto 6h candles, '1d' for stocks.
    changepoint_prior_scale : float
        Flexibility of trend changepoints. Lower = more conservative.
        Default: 0.05. Range typically 0.001–0.5.
    lookback : int
        Number of recent rows to fit on. Default: 3000 (~2 years of 6h).
    """

    def __init__(
        self,
        asset: str,
        forecast_horizon: int = 14,
        freq: str = "6h",
        changepoint_prior_scale: float = 0.05,
        lookback: int = 3000,
    ):
        super().__init__(asset=asset, forecast_horizon=forecast_horizon)
        self.freq = freq
        self.changepoint_prior_scale = changepoint_prior_scale
        self.lookback = lookback

        self._model = None
        self._last_actual: float = 0.0
        self._has_volume: bool = False

    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """Fit Prophet model on recent price history."""
        try:
            from prophet import Prophet
        except ImportError:
            raise ImportError(
                "prophet is required for ProphetForecaster. "
                "Install with: pip install prophet"
            )

        self.validate_input(df)
        df_fit = df.tail(self.lookback).copy()
        self._last_actual = float(df_fit["close"].iloc[-1])

        prophet_df = df_fit[["timestamp", "close"]].rename(
            columns={"timestamp": "ds", "close": "y"}
        )
        self._has_volume = (
            "volume" in df_fit.columns
            and df_fit["volume"].notna().all()
            and df_fit["volume"].gt(0).all()
        )

        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,    # Crypto lacks stable yearly seasonality
            interval_width=0.95,
            changepoint_prior_scale=self.changepoint_prior_scale,
        )

        if self._has_volume:
            model.add_regressor("volume")
            prophet_df["volume"] = df_fit["volume"].values

        model.fit(prophet_df)
        self._model = model
        self._is_fitted = True
        logger.debug("[%s] Prophet fit complete (volume_regressor=%s)", self.asset, self._has_volume)

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """Generate Prophet forecast and extract terminal candle statistics."""
        if not self._is_fitted:
            self.fit(df)

        future = self._model.make_future_dataframe(periods=self.forecast_horizon, freq=self.freq)

        if self._has_volume:
            # Extend volume with rolling mean estimate (last 14 candles)
            recent_vol = float(df["volume"].rolling(14).mean().iloc[-1])
            future["volume"] = recent_vol

        forecast = self._model.predict(future)
        last_fc  = forecast.iloc[-1]

        yhat    = float(last_fc["yhat"])
        yhat_lo = float(last_fc["yhat_lower"])
        yhat_hi = float(last_fc["yhat_upper"])

        # Uncertainty: relative band width (lower = more confident)
        uncertainty = float((yhat_hi - yhat_lo) / (abs(yhat) + 1e-9))

        # Signal: compare terminal forecast vs last actual price
        if yhat > self._last_actual * 1.01:
            signal = "BUY"
        elif yhat < self._last_actual * 0.99:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Confidence: 1 - uncertainty (capped at 0.80 — Prophet is optimistic)
        confidence = float(min(max(1.0 - uncertainty, 0.0), 0.80))

        logger.debug(
            "[%s] Prophet: yhat=%.4f uncertainty=%.3f → %s (conf=%.3f)",
            self.asset, yhat, uncertainty, signal, confidence,
        )

        return ModelSignal(
            name=self.model_name,
            signal=signal,
            confidence=confidence,
            pred_price=round(yhat, 4),
            meta={
                "yhat_lo":     round(yhat_lo, 4),
                "yhat_hi":     round(yhat_hi, 4),
                "uncertainty": round(uncertainty, 4),
            },
        )

    @property
    def model_name(self) -> str:
        return "prophet"
