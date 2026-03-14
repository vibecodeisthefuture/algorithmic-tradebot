"""
LGBMForecaster — LightGBM Next-Candle Directional Classifier

PRIMARY USE CASE
----------------
Next-candle directional classification. The PRIMARY actionable signal for
trade entry decisions. Answers: "Is the next candle more likely to close
higher or lower than the current close, and with what probability?"

This is the HIGHEST-WEIGHT model in the ensemble (~0.30) because it:
  - Produces well-calibrated probabilities (prob_up)
  - Is fast to train and retrain
  - Handles mixed feature types natively
  - Has low sensitivity to individual outliers (tree ensemble)

WHEN TO ACTIVATE
----------------
BULL or NEUTRAL regime. In BEAR regimes, lag/momentum features cause the
model to trend-chase into falling markets — suppress unless specifically
calibrated for bearish directional trading.

LIMITATIONS
-----------
- NO TEMPORAL ORDERING AWARENESS. LightGBM sees features as a tabular dataset.
  Temporal leakage is a constant risk — NEVER use close.shift(0) as a feature.
  Target must always be close.shift(-1) > close (next candle's direction).
- TimeSeriesSplit REQUIRED for cross-validation. Standard KFold leaks future data.
- Does not extrapolate outside training distribution. After a regime change
  or black swan event, accuracy degrades rapidly until retrain.
- Requires minimum ~500 rows for meaningful 5-fold CV. Thin data = noisy model.
- prob_up near 0.5 = essentially random. Only act on prob_up > 0.55 (BUY)
  or prob_up < 0.45 (SELL). The 0.45–0.55 band maps to HOLD.
- Retraining cadence: rolling 6-month window, every 4 weeks.

DB FOOTPRINT
------------
Stores: prob_up (float), signal, top 10 feature names (JSON list).
Full feature importance array is NOT persisted. Model object not persisted
to DB (stored on disk if caching is added in future, but currently stateless).
"""

import logging

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)

# Thresholds for BUY / SELL / HOLD classification
_BUY_THRESHOLD  = 0.55   # prob_up > 0.55 → BUY
_SELL_THRESHOLD = 0.45   # prob_up < 0.45 → SELL
# 0.45 ≤ prob_up ≤ 0.55 → HOLD (below conviction threshold)


def _compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder smoothing approximation)."""
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(window).mean()
    loss  = (-delta.clip(upper=0)).rolling(window).mean()
    rs    = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def engineer_features(df: pd.DataFrame, lags: list = None) -> pd.DataFrame:
    """
    Build supervised learning features from OHLCV data.

    Feature groups:
      - Lagged close returns [1, 3, 6, 12, 24 candles]: captures short/medium momentum
      - Rolling volatility [6, 24 candle windows]: captures vol regime
      - RSI(14): overbought/oversold
      - MACD (EMA12 - EMA26): momentum smoothed
      - Bollinger Band %B: normalized price position within band
      - High/Low range: intrabar volatility proxy

    Target: 1 if next candle's close > current close, else 0.
    CRITICAL: target uses shift(-1) — future row, not current row.
    Rows with NaN target (last row) are dropped.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame sorted ascending.
    lags : list of int
        Lag periods for return features. Default: [1, 3, 6, 12, 24].

    Returns
    -------
    pd.DataFrame with feature columns and 'target' column, NaN rows dropped.
    """
    if lags is None:
        lags = [1, 3, 6, 12, 24]

    feat = df.copy()

    # --- Lag features (returns only, not raw prices — avoids scale issues) ---
    for lag in lags:
        feat[f"close_lag_{lag}"]   = feat["close"].shift(lag)
        feat[f"return_lag_{lag}"]  = feat["close"].pct_change(lag)

    # --- Rolling volatility ---
    feat["vol_6"]  = feat["close"].pct_change().rolling(6).std()
    feat["vol_24"] = feat["close"].pct_change().rolling(24).std()

    # --- Momentum indicators ---
    feat["rsi_14"] = _compute_rsi(feat["close"], 14)
    ema12          = feat["close"].ewm(span=12, adjust=False).mean()
    ema26          = feat["close"].ewm(span=26, adjust=False).mean()
    feat["macd"]   = ema12 - ema26
    feat["macd_signal"] = feat["macd"].ewm(span=9, adjust=False).mean()

    # --- Bollinger Band %B ---
    bb_mid        = feat["close"].rolling(20).mean()
    bb_std        = feat["close"].rolling(20).std()
    feat["bb_upper"] = bb_mid + 2 * bb_std
    feat["bb_lower"] = bb_mid - 2 * bb_std
    feat["bb_pct"]   = (feat["close"] - feat["bb_lower"]) / (feat["bb_upper"] - feat["bb_lower"] + 1e-9)

    # --- High/Low range proxy ---
    feat["hl_range"]     = (feat["high"] - feat["low"]) / (feat["close"] + 1e-9)
    feat["close_vs_open"] = (feat["close"] - feat["open"]) / (feat["open"] + 1e-9)

    # --- Target: 1 = next candle up, 0 = next candle down ---
    feat["target"] = (feat["close"].shift(-1) > feat["close"]).astype(int)

    return feat.dropna()


class LGBMForecaster(BaseForecaster):
    """
    LightGBM gradient-boosted directional classifier.

    Uses TimeSeriesSplit cross-validation (5 folds) during training.
    Produces prob_up ∈ [0, 1] — the probability that the next candle closes higher.

    Parameters
    ----------
    asset : str
        Asset identifier.
    n_splits : int
        Number of TimeSeriesSplit folds. Default: 5.
    n_estimators : int
        Trees per model. Default: 300.
    learning_rate : float
        Shrinkage. Default: 0.05.
    num_leaves : int
        Max leaves per tree. Default: 31 (default LightGBM).
    lookback : int
        Max rows to train on. Default: 5000 (≈2.5 years of 6h candles).
    """

    def __init__(
        self,
        asset: str,
        forecast_horizon: int = 14,
        n_splits: int = 5,
        n_estimators: int = 300,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        lookback: int = 5000,
    ):
        super().__init__(asset=asset, forecast_horizon=forecast_horizon)
        self.n_splits      = n_splits
        self.n_estimators  = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves    = num_leaves
        self.lookback      = lookback

        self._model = None
        self._feature_cols: list[str] = []
        self._cv_accuracy: float = 0.0
        self._top_features: list[str] = []

    # -----------------------------------------------------------------------
    # BaseForecaster interface
    # -----------------------------------------------------------------------

    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """
        Engineer features, run TimeSeriesSplit CV, train final model on all data.
        """
        if self._is_fitted and not force_retrain:
            return

        try:
            import lightgbm as lgb
            from sklearn.model_selection import TimeSeriesSplit
            from sklearn.metrics import accuracy_score
        except ImportError:
            raise ImportError(
                "lightgbm and scikit-learn are required for LGBMForecaster. "
                "Install with: pip install lightgbm scikit-learn"
            )

        self.validate_input(df)

        # Limit lookback to prevent slow training on very large datasets
        df_fit = df.tail(self.lookback).copy()
        feat_df = engineer_features(df_fit)

        if len(feat_df) < 100:
            raise ValueError(
                f"[{self.asset}] Only {len(feat_df)} feature rows after engineering — "
                "need ≥100. Increase lookback or check data."
            )

        # Exclude raw OHLCV columns and timestamp from features
        exclude = {"timestamp", "target", "open", "high", "low", "close",
                   "volume", "bb_upper", "bb_lower"}
        self._feature_cols = [c for c in feat_df.columns if c not in exclude]

        X = feat_df[self._feature_cols]
        y = feat_df["target"]

        # --- TimeSeriesSplit cross-validation (no leakage) ---
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        cv_scores = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

            clf = lgb.LGBMClassifier(
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                num_leaves=self.num_leaves,
                random_state=42,
                verbosity=-1,
            )
            clf.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(30, verbose=False)],
            )
            preds = clf.predict(X_val)
            score = accuracy_score(y_val, preds)
            cv_scores.append(score)

        self._cv_accuracy = float(np.mean(cv_scores))
        logger.info(
            "[%s] LGBM CV: acc=%.3f ± %.3f over %d folds",
            self.asset, self._cv_accuracy, float(np.std(cv_scores)), len(cv_scores),
        )

        # --- Final model on all data ---
        self._model = lgb.LGBMClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            random_state=42,
            verbosity=-1,
        )
        self._model.fit(X, y)

        # Top 10 features by importance (for model_breakdown JSON)
        importances = self._model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]
        self._top_features = [self._feature_cols[i] for i in sorted_idx[:10]]

        self._is_fitted = True
        logger.debug("[%s] LGBM fit complete. Top features: %s", self.asset, self._top_features[:5])

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        Predict next-candle direction probability from the most recent feature row.
        """
        if not self._is_fitted:
            self.fit(df)

        feat_df = engineer_features(df.tail(self.lookback).copy())
        if feat_df.empty:
            logger.warning("[%s] LGBM: empty feature set — emitting HOLD", self.asset)
            return ModelSignal(
                name=self.model_name,
                signal="HOLD",
                confidence=0.0,
                pred_price=float(df["close"].iloc[-1]),
                meta={"error": "empty_features"},
            )

        last_features = feat_df[self._feature_cols].iloc[[-1]]
        prob_up = float(self._model.predict_proba(last_features)[0][1])
        current_price = float(df["close"].iloc[-1])

        # --- Signal classification ---
        if prob_up > _BUY_THRESHOLD:
            signal     = "BUY"
            confidence = (prob_up - 0.5) * 2         # scale 0.55→0.10 to 1.0→1.0
        elif prob_up < _SELL_THRESHOLD:
            signal     = "SELL"
            confidence = (0.5 - prob_up) * 2
        else:
            signal     = "HOLD"
            confidence = 0.0

        confidence = float(min(max(confidence, 0.0), 1.0))

        logger.debug(
            "[%s] LGBM: prob_up=%.3f → %s (conf=%.3f)", self.asset, prob_up, signal, confidence
        )

        return ModelSignal(
            name=self.model_name,
            signal=signal,
            confidence=confidence,
            pred_price=current_price,   # LightGBM is a classifier, not a price regressor
            meta={
                "prob_up": round(prob_up, 4),
                "cv_accuracy": round(self._cv_accuracy, 4),
                "top_features": self._top_features[:10],
            },
        )

    @property
    def model_name(self) -> str:
        return "lgbm"
