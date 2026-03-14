"""
MonteCarloForecaster — Geometric Brownian Motion Price Simulator

PRIMARY USE CASE
----------------
Risk sizing and probability-weighted price range estimation.
Answers: "What is the distribution of possible prices over the next N candles?"

This model is NOT a directional signal generator — it is a risk tool.
Its P5/P50/P95 bands feed into Portfolio Tracker position sizing.
The BUY/SELL/HOLD signal it emits is WEAK and should receive low ensemble weight
(~0.15). Do not use it alone as a trade entry trigger.

WHEN TO ACTIVATE
----------------
Always. Run every cycle on every asset regardless of regime. Monte Carlo is
the baseline risk-band provider — even in BEAR regimes, the P5 band is used
as a downside stop reference.

LIMITATIONS
-----------
- Assumes log-normal returns (GBM) — UNDERESTIMATES fat tails and crashes.
  Black swan events (VIX > 35, flash crashes) are not reflected in GBM paths.
- Drift (mu) and volatility (sigma) are estimated from a historical window.
  If the regime has shifted recently, these statistics are stale.
- P50 trending above the current price does NOT indicate a reliable BUY.
  GBM drift is mean-reverting over short windows. Use LightGBM for directional.
- No external features used — price history only.

DB FOOTPRINT
------------
Stores only p05, p50, p95 in the model_breakdown JSON. The 2,000 simulation
paths are computed in memory and discarded. Never persisted.
"""

import logging

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)


class MonteCarloForecaster(BaseForecaster):
    """
    Simulates future price paths using Geometric Brownian Motion (GBM).

    GBM formula per step:
        S_{t+1} = S_t * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
    where Z ~ N(0,1), mu is the log-return mean, sigma is log-return std.

    Parameters
    ----------
    asset : str
        Asset identifier, e.g. "BTC/USD".
    n_simulations : int
        Number of Monte Carlo paths to simulate. More paths = smoother
        percentile estimates. Default: 2000 (balances speed vs. accuracy).
    forecast_horizon : int
        Number of candles ahead to simulate. Default: 14 (~3.5 days on 6h).
    lookback : int
        Number of historical candles used to estimate mu and sigma.
        Default: 168 (4 weeks of 6h candles). Too short → noisy estimates;
        too long → stale statistics in a changed regime.
    buy_threshold : float
        P50 final price must exceed S0 * (1 + buy_threshold) to emit BUY.
        Default: 0.02 (2% above current price).
    sell_threshold : float
        P50 final price must fall below S0 * (1 - sell_threshold) to emit SELL.
        Default: 0.02 (2% below current price).
    """

    def __init__(
        self,
        asset: str,
        n_simulations: int = 2000,
        forecast_horizon: int = 14,
        lookback: int = 168,
        buy_threshold: float = 0.02,
        sell_threshold: float = 0.02,
    ):
        super().__init__(asset=asset, forecast_horizon=forecast_horizon)
        self.n_simulations = n_simulations
        self.lookback = lookback
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

        # Fitted statistics (set in fit())
        self._mu: float = 0.0
        self._sigma: float = 0.0
        self._s0: float = 0.0

    # -----------------------------------------------------------------------
    # BaseForecaster interface
    # -----------------------------------------------------------------------

    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """
        Estimate GBM parameters (mu, sigma) from historical log-returns.

        Monte Carlo is stateless — always refits on each call. Parameters are
        stored so predict() can be called separately without re-fitting.
        """
        self.validate_input(df)

        prices = df["close"].tail(self.lookback).dropna()
        log_returns = np.log(prices / prices.shift(1)).dropna()

        self._mu    = float(log_returns.mean())
        self._sigma = float(log_returns.std())
        self._s0    = float(prices.iloc[-1])
        self._is_fitted = True

        logger.debug(
            "[%s] MonteCarloForecaster fit: mu=%.6f sigma=%.6f S0=%.4f (n=%d)",
            self.asset, self._mu, self._sigma, self._s0, len(prices),
        )

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        Simulate n_simulations GBM paths and extract P5/P50/P95 percentiles.

        Returns a ModelSignal with:
          signal     : BUY if P50[-1] > S0*(1+buy_threshold)
                       SELL if P50[-1] < S0*(1-sell_threshold)
                       HOLD otherwise
          confidence : normalized distance of P50 from S0 (clipped to 0–1)
          pred_price : P50 of the final simulated candle
          meta       : {p05, p50, p95} — compact risk bands for DB storage
        """
        if not self._is_fitted:
            self.fit(df)

        dt = 1  # one candle per step
        drift = (self._mu - 0.5 * self._sigma ** 2) * dt
        diffusion = self._sigma * np.sqrt(dt)

        # Generate all random shocks at once: shape (n_steps, n_simulations)
        shocks = np.random.normal(
            loc=drift,
            scale=diffusion,
            size=(self.forecast_horizon, self.n_simulations),
        )

        # Compute cumulative price paths from S0
        paths = self._s0 * np.exp(np.cumsum(shocks, axis=0))  # (n_steps, n_sims)

        # Extract terminal percentiles (last candle of each path)
        terminal = paths[-1, :]
        p05 = float(np.percentile(terminal, 5))
        p50 = float(np.percentile(terminal, 50))
        p95 = float(np.percentile(terminal, 95))

        # --- Directional signal ---
        if p50 > self._s0 * (1 + self.buy_threshold):
            signal = "BUY"
        elif p50 < self._s0 * (1 - self.sell_threshold):
            signal = "SELL"
        else:
            signal = "HOLD"

        # Confidence: normalized |P50 - S0| / S0, clipped [0, 1]
        # Intentionally kept low — GBM signal is weak for directional decisions
        confidence = float(min(abs(p50 - self._s0) / (self._s0 * 0.10 + 1e-9), 1.0))

        logger.debug(
            "[%s] MC: S0=%.4f P5=%.4f P50=%.4f P95=%.4f → %s (conf=%.3f)",
            self.asset, self._s0, p05, p50, p95, signal, confidence,
        )

        return ModelSignal(
            name=self.model_name,
            signal=signal,
            confidence=confidence,
            pred_price=p50,
            meta={
                "p05": round(p05, 4),
                "p50": round(p50, 4),
                "p95": round(p95, 4),
            },
        )

    @property
    def model_name(self) -> str:
        return "monte_carlo"
