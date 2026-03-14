"""
HMMRegimeDetector — Hidden Markov Model Market Regime Classifier

PRIMARY USE CASE
----------------
Classify the current market regime into BULL / NEUTRAL / BEAR.
Run FIRST every cycle — its output gates which other models activate.
This is the conductor of the ensemble, not a directional signal generator.

WHEN TO ACTIVATE
----------------
ALWAYS and unconditionally. Every asset, every cycle.
Even in isolation, the regime label alone is actionable:
  - BEAR  → Portfolio Tracker considers tightening stops / reducing leverage
  - BULL  → greenlights momentum model activation
  - NEUTRAL → equal-weight ensemble, no suppression

LIMITATIONS
-----------
- HMM states are UNLABELED by default. Auto-labeling by mean log-return can
  misfire in ambiguous regimes (low-vol sideways with tiny positive drift
  may be labeled BULL incorrectly). Always sanity-check labels against
  known historical periods before trusting in production.
- Sensitive to lookback window. A 500-candle window (recommended) balances
  stability and recency. Too short → noisy; too long → slow to detect shifts.
- n_regimes=3 is a design choice. Real markets have more nuanced states.
  Increasing n_regimes improves expressiveness but raises fitting instability.
- Does NOT forecast WHEN a regime will change — only labels the current state.
- Markov (memoryless): abrupt regime transitions may lag by 1–3 candles.

DB FOOTPRINT
------------
Writes only regime (string: BULL/NEUTRAL/BEAR) to the predictions row.
Never persists the full hidden-state sequence, emission matrices, or
transition probability matrix.
"""

import logging

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)


class HMMRegimeDetector(BaseForecaster):
    """
    Fits a Gaussian HMM on log-returns + rolling volatility to identify
    hidden market regime states, then auto-labels them BULL / NEUTRAL / BEAR
    by mean return (ascending → BEAR, middle → NEUTRAL, highest → BULL).

    Parameters
    ----------
    asset : str
        Asset identifier.
    n_regimes : int
        Number of hidden states. 3 recommended (BULL/NEUTRAL/BEAR).
        Use 2 for assets with insufficient data (500 rows minimum).
    lookback : int
        Number of recent candles used to fit the HMM. Default: 500 (~125 days
        on 6h candles). Recommended range: 300–1000.
    vol_window : int
        Rolling window for the volatility feature. Default: 14 candles.
    """

    def __init__(
        self,
        asset: str,
        n_regimes: int = 3,
        forecast_horizon: int = 14,
        lookback: int = 500,
        vol_window: int = 14,
    ):
        super().__init__(asset=asset, forecast_horizon=forecast_horizon)
        self.n_regimes = n_regimes
        self.lookback = lookback
        self.vol_window = vol_window

        self._model = None          # fitted GaussianHMM instance
        self._labels: dict = {}     # {state_int: "BULL"|"NEUTRAL"|"BEAR"}
        self._current_regime: str = "NEUTRAL"

    # -----------------------------------------------------------------------
    # BaseForecaster interface
    # -----------------------------------------------------------------------

    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """
        Fit the Gaussian HMM on log-returns + rolling volatility.

        Always refits (stateless model — cheap to refit each cycle).
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            raise ImportError(
                "hmmlearn is required for HMMRegimeDetector. "
                "Install with: pip install hmmlearn"
            )

        self.validate_input(df)

        prices = df["close"].tail(self.lookback).dropna()
        returns = np.log(prices / prices.shift(1)).dropna().values

        # Feature matrix: [log_return, rolling_volatility]
        # Rolling vol uses pandas for efficiency; forward-fill the initial NaNs
        ret_series = pd.Series(returns)
        vol = ret_series.rolling(self.vol_window).std().fillna(method="bfill").values
        features = np.column_stack([returns, vol])

        model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=1000,
            random_state=42,
        )
        model.fit(features)

        hidden_states = model.predict(features)

        # Auto-label states by mean log-return (ascending: BEAR < NEUTRAL < BULL)
        state_means = {
            s: features[hidden_states == s, 0].mean()
            for s in range(self.n_regimes)
        }
        sorted_states = sorted(state_means, key=state_means.get)

        if self.n_regimes == 2:
            self._labels = {
                sorted_states[0]: "BEAR",
                sorted_states[1]: "BULL",
            }
        else:
            self._labels = {
                sorted_states[0]: "BEAR",
                sorted_states[-1]: "BULL",
            }
            # All middle states → NEUTRAL
            for s in sorted_states[1:-1]:
                self._labels[s] = "NEUTRAL"

        self._model = model
        self._current_regime = self._labels.get(hidden_states[-1], "NEUTRAL")
        self._is_fitted = True

        logger.debug(
            "[%s] HMM fit: regime=%s labels=%s (n=%d)",
            self.asset, self._current_regime, self._labels, len(returns),
        )

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        Return the current regime label as a ModelSignal.

        signal     : always "HOLD" — HMM is not a directional signal generator
        confidence : always 1.0 — the regime label is a hard classification
        pred_price : current close price (HMM produces no price forecast)
        meta       : {"regime": "BULL"|"NEUTRAL"|"BEAR"}
        """
        if not self._is_fitted:
            self.fit(df)

        current_price = float(df["close"].iloc[-1])
        regime = self._current_regime

        logger.info("[%s] HMM regime: %s", self.asset, regime)

        return ModelSignal(
            name=self.model_name,
            signal="HOLD",      # HMM does not emit directional signals
            confidence=1.0,     # Regime label is a hard classification
            pred_price=current_price,
            meta={"regime": regime},
        )

    @property
    def model_name(self) -> str:
        return "hmm"

    @property
    def current_regime(self) -> str:
        """The regime label from the most recent fit."""
        return self._current_regime
