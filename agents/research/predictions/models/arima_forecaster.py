"""
ARIMAForecaster — SARIMA Statistical Time-Series Baseline

PRIMARY USE CASE
----------------
Mean-reversion detection and short-term statistical baseline.
Answers: "Does recent price action show autocorrelation consistent with
a return to mean?" Best used as a counterbalancing signal in BEAR/NEUTRAL
regimes where mean-reversion is more likely than momentum continuation.

WHEN TO ACTIVATE
----------------
BEAR or NEUTRAL regime. Especially valuable when HMM detects mean-reverting
conditions (low-volatility sideways markets). Also useful as a sanity check
against LightGBM's momentum bias. SUPPRESS in strong BULL trends — ARIMA
will incorrectly flag trending prices as "SELL" due to over-differencing.

LIMITATIONS
-----------
- STRICTLY LINEAR — cannot model nonlinear regime changes, leverage effects,
  or sudden breakdowns. ARIMA sees the world as a linear process.
- ADF stationarity test auto-selects differencing order `d`, but differencing
  discards trend information. Use d=1 max; d=2 almost always overfits.
- Seasonal period m=28 (≈1 week of 6h candles) is a heuristic. Actual weekly
  cycles may vary. A full AIC grid search over m values is expensive but ideal.
- cap lookback at 500 candles for production speed — SARIMA fitting is O(n^2).
- SARIMA can fail to converge on volatile assets. Wrap in try/except and fall
  back to HOLD on convergence failure (already implemented below).

DB FOOTPRINT
------------
Stores only: forecast_mean (1 float), ci_lo, ci_hi, signal.
ARIMA coefficients and the full scipy optimization trace are NOT persisted.
"""

import logging
import warnings

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

# Suppress verbose statsmodels convergence warnings in production
warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels")

logger = logging.getLogger(__name__)


class ARIMAForecaster(BaseForecaster):
    """
    SARIMA (Seasonal ARIMA) statistical forecaster.

    Automatically checks for stationarity using the ADF test and selects
    differencing order `d`. Defaults to order=(2,d,2) with seasonal component.

    Parameters
    ----------
    asset : str
        Asset identifier.
    order : tuple(int,int,int)
        (p, d, q) — AR lags, differencing, MA lags. d is overridden by ADF test.
    seasonal_order : tuple(int,int,int,int)
        (P, D, Q, m) — seasonal AR/I/MA + period. m=28 ≈ 1 week of 6h candles.
        Set to (0,0,0,0) to disable seasonality (faster, less accurate).
    forecast_horizon : int
        Number of candles ahead to forecast. Default: 14.
    lookback : int
        Number of recent candles to fit on. Cap at 500 for production speed.
    """

    def __init__(
        self,
        asset: str,
        order: tuple = (2, 1, 2),
        seasonal_order: tuple = (1, 1, 1, 28),
        forecast_horizon: int = 14,
        lookback: int = 500,
    ):
        super().__init__(asset=asset, forecast_horizon=forecast_horizon)
        self._order = order
        self._seasonal_order = seasonal_order
        self.lookback = lookback

        # Set after fit()
        self._result = None
        self._last_price: float = 0.0

    # -----------------------------------------------------------------------
    # BaseForecaster interface
    # -----------------------------------------------------------------------

    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """
        Fit SARIMA model. Auto-detects stationarity via ADF test.
        Stateless model — always refits on each call.
        """
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            from statsmodels.tsa.stattools import adfuller
        except ImportError:
            raise ImportError(
                "statsmodels is required for ARIMAForecaster. "
                "Install with: pip install statsmodels"
            )

        self.validate_input(df)
        prices = df["close"].tail(self.lookback).dropna()
        self._last_price = float(prices.iloc[-1])

        # --- ADF stationarity test → auto-select d ---
        adf_pval = adfuller(prices)[1]
        is_stationary = adf_pval < 0.05
        d = 0 if is_stationary else 1
        order = (self._order[0], d, self._order[2])
        logger.debug(
            "[%s] ARIMA ADF p=%.4f → stationary=%s → d=%d",
            self.asset, adf_pval, is_stationary, d,
        )

        try:
            model = SARIMAX(
                prices,
                order=order,
                seasonal_order=self._seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            self._result = model.fit(disp=False)
            self._is_fitted = True
            logger.debug("[%s] ARIMA fit OK (AIC=%.2f)", self.asset, self._result.aic)
        except Exception as exc:
            logger.warning("[%s] ARIMA fit failed: %s — will emit HOLD", self.asset, exc)
            self._result = None
            self._is_fitted = True   # mark fitted so predict() can emit HOLD

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        Generate a 1-step ahead forecast (or multi-step mean).
        Returns HOLD on convergence failure.
        """
        if not self._is_fitted:
            self.fit(df)

        # Graceful fallback on convergence failure
        if self._result is None:
            return ModelSignal(
                name=self.model_name,
                signal="HOLD",
                confidence=0.0,
                pred_price=float(df["close"].iloc[-1]),
                meta={"error": "convergence_failure"},
            )

        try:
            forecast_obj = self._result.get_forecast(steps=1)
            forecast_mean = float(forecast_obj.predicted_mean.iloc[-1])
            conf_int = forecast_obj.conf_int(alpha=0.05)  # 95% CI
            ci_lo = float(conf_int.iloc[-1, 0])
            ci_hi = float(conf_int.iloc[-1, 1])
        except Exception as exc:
            logger.warning("[%s] ARIMA predict failed: %s", self.asset, exc)
            return ModelSignal(
                name=self.model_name,
                signal="HOLD",
                confidence=0.0,
                pred_price=self._last_price,
                meta={"error": str(exc)},
            )

        # --- Signal ---
        if forecast_mean > self._last_price:
            signal = "BUY"
        elif forecast_mean < self._last_price:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Confidence: 1 - (CI width / forecast_mean), clipped [0, 1]
        ci_width = ci_hi - ci_lo
        confidence = float(max(0.0, min(1.0, 1.0 - (ci_width / (abs(forecast_mean) + 1e-9)))))
        # Normalize to realistic range (ARIMA confidence is often low)
        confidence = min(confidence, 0.85)

        logger.debug(
            "[%s] ARIMA: forecast=%.4f CI=[%.4f,%.4f] → %s (conf=%.3f)",
            self.asset, forecast_mean, ci_lo, ci_hi, signal, confidence,
        )

        return ModelSignal(
            name=self.model_name,
            signal=signal,
            confidence=confidence,
            pred_price=round(forecast_mean, 4),
            meta={
                "ci_lo": round(ci_lo, 4),
                "ci_hi": round(ci_hi, 4),
            },
        )

    @property
    def model_name(self) -> str:
        return "arima"
