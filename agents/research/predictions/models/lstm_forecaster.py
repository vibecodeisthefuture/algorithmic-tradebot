"""
LSTMForecaster — Long Short-Term Memory Neural Network

PRIMARY USE CASE
----------------
Nonlinear temporal pattern learning from multi-feature sequences.
Answers: "What nonlinear price pattern in the last 60 candles best
predicts the next candle's direction or price?"

Complements LightGBM by learning from raw feature sequences without
manual lag engineering. Particularly useful for capturing momentum
discontinuities and complex feature interactions invisible to tree models.

WHEN TO ACTIVATE
----------------
BULL or NEUTRAL regime with >= 500 rows of history.
Suppress in BEAR regime (momentum patterns break down).
Suppress if data < 300 rows (insufficient for meaningful training).
Runs on the 6h/daily scheduled tick — NOT every cycle.

LIMITATIONS
-----------
- HIGH OVERFITTING RISK — financial series are short relative to LSTM capacity.
  Dropout (0.2) and EarlyStopping (patience=5) are mandatory safeguards.
- Weights become STALE after 4 weeks in a changed regime. Stale weights in a
  new regime are worse than no model. Retrain schedule must be enforced.
- MinMaxScaler must be refit on TRAINING data only. Fitting on test data → leakage.
- CPU training: ~5–15 min per asset. Schedule in off-peak hours.
- NO UNCERTAINTY OUTPUT natively. Pair with Monte Carlo for price bands.
  LSTM pred_price is a point estimate only.

DB FOOTPRINT
------------
Stores only: pred_price (float), signal.
Model weights saved to disk: data/state/model_weights/lstm_{asset_safe}.keras
(asset_safe = asset with / replaced by _). File is overwritten on retrain.
Model weights are NOT stored in the database.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent.parent.parent
_WEIGHTS_DIR = _PROJECT_ROOT / "data" / "state" / "model_weights"


def _asset_safe(asset: str) -> str:
    """Convert asset identifier to a filesystem-safe string."""
    return asset.replace("/", "_").replace(" ", "_")


class LSTMForecaster(BaseForecaster):
    """
    LSTM sequence-to-scalar forecaster predicting next-candle price.

    Architecture:
        LSTM(64, return_sequences=True) → Dropout(0.2)
        → LSTM(32)                      → Dropout(0.2)
        → Dense(16, activation='relu')
        → Dense(1)  ← next close price (normalized)

    Parameters
    ----------
    asset : str
        Asset identifier.
    forecast_horizon : int
        Candles ahead for signal labeling. Default: 14.
    lookback_seq : int
        Input sequence length (candles per sample). Default: 60.
    lookback_train : int
        Max training rows. Default: 5000 (~2.5 years of 6h).
    epochs : int
        Maximum training epochs. EarlyStopping will halt earlier.
    """

    def __init__(
        self,
        asset: str,
        forecast_horizon: int = 14,
        lookback_seq: int = 60,
        lookback_train: int = 5000,
        epochs: int = 50,
    ):
        super().__init__(asset=asset, forecast_horizon=forecast_horizon)
        self.lookback_seq   = lookback_seq
        self.lookback_train = lookback_train
        self.epochs         = epochs

        self._model = None
        self._scaler = None           # MinMaxScaler — refit on training data only
        self._feature_cols: list[str] = []
        self._weights_path: Path | None = None

    def fit(self, df: pd.DataFrame, force_retrain: bool = False) -> None:
        """
        Build and train the LSTM on the most recent lookback_train candles.
        Saves weights to disk. Skips refit unless force_retrain=True.
        """
        weights_path = _WEIGHTS_DIR / f"lstm_{_asset_safe(self.asset)}.keras"
        self._weights_path = weights_path

        # Try loading cached weights first (avoids 10+ min retrain on every run)
        if not force_retrain and weights_path.exists() and self._model is not None:
            logger.info("[%s] LSTM: using cached weights from %s", self.asset, weights_path)
            self._is_fitted = True
            return

        try:
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from tensorflow.keras.callbacks import EarlyStopping
            from sklearn.preprocessing import MinMaxScaler
        except ImportError:
            raise ImportError(
                "TensorFlow and scikit-learn are required for LSTMForecaster. "
                "Install with: pip install tensorflow scikit-learn"
            )

        self.validate_input(df)

        df_fit = df.tail(self.lookback_train).copy()

        # Feature set: OHLCV + momentum indicators
        from agents.research.predictions.models.lgbm_forecaster import (
            _compute_rsi, engineer_features,
        )
        # Use a simplified feature set to reduce dimensionality for LSTM
        feat = df_fit.copy()
        feat["rsi_14"] = _compute_rsi(feat["close"], 14)
        ema12 = feat["close"].ewm(span=12, adjust=False).mean()
        ema26 = feat["close"].ewm(span=26, adjust=False).mean()
        feat["macd"] = ema12 - ema26
        feat = feat.dropna()

        self._feature_cols = ["open", "high", "low", "close", "volume", "rsi_14", "macd"]
        data = feat[self._feature_cols].values

        # Fit scaler on training data ONLY (critical: no test data leakage)
        split = int(len(data) * 0.8)
        self._scaler = MinMaxScaler()
        self._scaler.fit(data[:split])          # fit on train portion only
        scaled = self._scaler.transform(data)   # transform entire dataset

        # Build supervised sequences
        X, y = [], []
        close_idx = self._feature_cols.index("close")
        for i in range(self.lookback_seq, len(scaled)):
            X.append(scaled[i - self.lookback_seq:i])
            y.append(scaled[i, close_idx])
        X, y = np.array(X), np.array(y)

        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

        # Build model
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(self.lookback_seq, len(self._feature_cols))),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation="relu"),
            Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse")

        es = EarlyStopping(patience=5, restore_best_weights=True)
        model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=self.epochs,
            batch_size=32,
            callbacks=[es],
            verbose=0,
        )

        # Save weights to disk (overwrites previous — no versioning needed for now)
        _WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        model.save(str(weights_path))
        self._model = model
        self._is_fitted = True
        logger.info("[%s] LSTM trained and weights saved to %s", self.asset, weights_path)

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        Predict the next close price from the last lookback_seq candles.
        """
        if not self._is_fitted:
            self.fit(df)

        if self._model is None or self._scaler is None:
            logger.warning("[%s] LSTM model not loaded — emitting HOLD", self.asset)
            return ModelSignal(
                name=self.model_name, signal="HOLD", confidence=0.0,
                pred_price=float(df["close"].iloc[-1]),
                meta={"error": "model_not_loaded"},
            )

        feat = df.copy()
        from agents.research.predictions.models.lgbm_forecaster import _compute_rsi
        feat["rsi_14"] = _compute_rsi(feat["close"], 14)
        ema12 = feat["close"].ewm(span=12, adjust=False).mean()
        ema26 = feat["close"].ewm(span=26, adjust=False).mean()
        feat["macd"] = ema12 - ema26
        feat = feat.dropna()

        if len(feat) < self.lookback_seq:
            return ModelSignal(
                name=self.model_name, signal="HOLD", confidence=0.0,
                pred_price=float(df["close"].iloc[-1]),
                meta={"error": "insufficient_rows"},
            )

        data = feat[self._feature_cols].values
        scaled = self._scaler.transform(data)
        seq = scaled[-self.lookback_seq:].reshape(1, self.lookback_seq, len(self._feature_cols))
        pred_scaled = float(self._model.predict(seq, verbose=0)[0][0])

        # Inverse-transform the close price prediction
        close_idx = self._feature_cols.index("close")
        dummy = np.zeros((1, len(self._feature_cols)))
        dummy[0, close_idx] = pred_scaled
        pred_price = float(self._scaler.inverse_transform(dummy)[0, close_idx])

        current_price = float(df["close"].iloc[-1])
        pct_change = (pred_price - current_price) / (current_price + 1e-9)

        if pct_change > 0.005:
            signal = "BUY"
        elif pct_change < -0.005:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Confidence: magnitude of predicted move normalized to 5% range
        confidence = float(min(abs(pct_change) / 0.05, 1.0))

        logger.debug(
            "[%s] LSTM: current=%.4f pred=%.4f pct=%.4f → %s (conf=%.3f)",
            self.asset, current_price, pred_price, pct_change, signal, confidence,
        )

        return ModelSignal(
            name=self.model_name,
            signal=signal,
            confidence=confidence,
            pred_price=round(pred_price, 4),
            meta={},   # No additional scalars needed — pred_price is the output
        )

    @property
    def model_name(self) -> str:
        return "lstm"
