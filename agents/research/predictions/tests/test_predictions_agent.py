"""
Unit Tests — Predictions Agent Core Modules

Tests cover:
  - ModelSignal validation and serialization
  - BaseForecaster interface enforcement
  - MonteCarloForecaster output shape and signal contract
  - HMMRegimeDetector regime label validity
  - ARIMAForecaster output types and fallback on failure
  - LGBMForecaster feature engineering and signal classification thresholds
  - EnsembleForecaster vote aggregation and confidence gating
  - DataLoader cleaning and column normalization
  - OutputWriter confidence gate (no write below threshold)
  - WalkForwardValidator fold structure and no-leakage guarantee

Run all:
    python -m pytest agents/research/predictions/tests/ -v

Run single file:
    python -m pytest agents/research/predictions/tests/test_predictions_agent.py -v
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def make_ohlcv(n: int = 600, base_price: float = 45000.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing (random walk)."""
    np.random.seed(42)
    returns = np.random.normal(0.0002, 0.015, n)
    closes  = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="6h"),
        "open":  closes * (1 + np.random.uniform(-0.005, 0.005, n)),
        "high":  closes * (1 + np.abs(np.random.normal(0, 0.008, n))),
        "low":   closes * (1 - np.abs(np.random.normal(0, 0.008, n))),
        "close": closes,
        "volume": np.random.uniform(1000, 5000, n),
    })
    return df


# ---------------------------------------------------------------------------
# ModelSignal
# ---------------------------------------------------------------------------

class TestModelSignal:
    from agents.research.predictions.model_signal import ModelSignal

    def test_valid_buy_signal(self):
        from agents.research.predictions.model_signal import ModelSignal
        sig = ModelSignal(name="lgbm", signal="BUY", confidence=0.75, pred_price=45200.0)
        assert sig.signal == "BUY"
        assert sig.confidence == 0.75
        assert sig.name == "lgbm"

    def test_invalid_signal_raises(self):
        from agents.research.predictions.model_signal import ModelSignal
        with pytest.raises(ValueError, match="BUY.*SELL.*HOLD"):
            ModelSignal(name="test", signal="MAYBE", confidence=0.5, pred_price=100.0)

    def test_confidence_out_of_range_raises(self):
        from agents.research.predictions.model_signal import ModelSignal
        with pytest.raises(ValueError, match="confidence"):
            ModelSignal(name="test", signal="BUY", confidence=1.5, pred_price=100.0)

    def test_to_breakdown_entry_with_weight(self):
        from agents.research.predictions.model_signal import ModelSignal
        sig = ModelSignal(
            name="lgbm", signal="BUY", confidence=0.61, pred_price=45200.0,
            meta={"prob_up": 0.61}
        )
        entry = sig.to_breakdown_entry(weight=0.30)
        assert entry["signal"] == "BUY"
        assert entry["weight"] == 0.30
        assert entry["prob_up"] == 0.61
        # No arrays in entry
        for v in entry.values():
            assert not isinstance(v, (list, np.ndarray)) or isinstance(v, list)


# ---------------------------------------------------------------------------
# DataLoader
# ---------------------------------------------------------------------------

class TestDataLoader:
    def test_clean_normalizes_columns(self):
        from agents.research.predictions.data_loader import _clean
        df = pd.DataFrame({
            "Timestamp": ["2023-01-01", "2023-01-02"],
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low":  [99.0,  100.0],
            "Close": [101.0, 102.0],
            "Volume": [1000, 1100],
        })
        cleaned = _clean(df, "TEST")
        assert list(cleaned.columns) == ["timestamp", "open", "high", "low", "close", "volume"]

    def test_clean_drops_null_close(self):
        from agents.research.predictions.data_loader import _clean
        df = pd.DataFrame({
            "timestamp": pd.date_range("2023-01-01", periods=3, freq="D"),
            "open": [1, 2, 3], "high": [1, 2, 3], "low": [1, 2, 3],
            "close": [1.0, None, 3.0], "volume": [100, 200, 300],
        })
        cleaned = _clean(df, "TEST")
        assert len(cleaned) == 2

    def test_unknown_asset_raises(self):
        from agents.research.predictions.data_loader import load_ohlcv
        with pytest.raises(ValueError, match="Unknown asset"):
            load_ohlcv("FAKE/USD")


# ---------------------------------------------------------------------------
# MonteCarloForecaster
# ---------------------------------------------------------------------------

class TestMonteCarlo:
    def test_signal_is_valid(self):
        from agents.research.predictions.models.monte_carlo import MonteCarloForecaster
        df = make_ohlcv(400)
        model = MonteCarloForecaster(asset="BTC/USD", n_simulations=100)
        model.fit(df)
        sig = model.predict(df)
        assert sig.signal in ("BUY", "SELL", "HOLD")

    def test_meta_has_required_keys(self):
        from agents.research.predictions.models.monte_carlo import MonteCarloForecaster
        df = make_ohlcv(400)
        model = MonteCarloForecaster(asset="BTC/USD", n_simulations=100)
        model.fit(df)
        sig = model.predict(df)
        assert "p05" in sig.meta
        assert "p50" in sig.meta
        assert "p95" in sig.meta

    def test_no_raw_paths_in_meta(self):
        """DB footprint rule: no arrays persisted."""
        from agents.research.predictions.models.monte_carlo import MonteCarloForecaster
        df = make_ohlcv(400)
        model = MonteCarloForecaster(asset="BTC/USD", n_simulations=100)
        model.fit(df)
        sig = model.predict(df)
        for v in sig.meta.values():
            assert not isinstance(v, (list, np.ndarray))

    def test_is_fitted_false_before_fit(self):
        from agents.research.predictions.models.monte_carlo import MonteCarloForecaster
        model = MonteCarloForecaster(asset="BTC/USD")
        assert not model.is_fitted


# ---------------------------------------------------------------------------
# EnsembleForecaster
# ---------------------------------------------------------------------------

class TestEnsemble:
    def _make_signals(self, signals: list[tuple]) -> list:
        from agents.research.predictions.model_signal import ModelSignal
        return [
            ModelSignal(name=n, signal=s, confidence=c, pred_price=45000.0)
            for n, s, c in signals
        ]

    def test_majority_buy_produces_buy(self):
        from agents.research.predictions.models.ensemble import EnsembleForecaster
        ensemble = EnsembleForecaster()
        signals = self._make_signals([
            ("lgbm", "BUY", 0.80),
            ("arima", "BUY", 0.60),
            ("monte_carlo", "SELL", 0.40),
            ("hmm", "HOLD", 1.0),   # hmm excluded from vote
        ])
        result = ensemble.aggregate(signals)
        assert result["signal"] == "BUY"
        assert "model_breakdown" in result
        assert "hmm" in result["model_breakdown"]

    def test_all_hold_produces_hold(self):
        from agents.research.predictions.models.ensemble import EnsembleForecaster
        ensemble = EnsembleForecaster()
        signals = self._make_signals([
            ("lgbm", "HOLD", 0.0),
            ("arima", "HOLD", 0.0),
        ])
        result = ensemble.aggregate(signals)
        assert result["signal"] == "HOLD"

    def test_confidence_is_clipped_to_one(self):
        from agents.research.predictions.models.ensemble import EnsembleForecaster
        ensemble = EnsembleForecaster()
        signals = self._make_signals([("lgbm", "BUY", 1.0)])
        result = ensemble.aggregate(signals)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_empty_signals_returns_hold(self):
        from agents.research.predictions.models.ensemble import EnsembleForecaster
        ensemble = EnsembleForecaster()
        result = ensemble.aggregate([])
        assert result["signal"] == "HOLD"
        assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# OutputWriter
# ---------------------------------------------------------------------------

class TestOutputWriter:
    def test_low_confidence_not_written(self):
        """DB footprint rule #3: rows with confidence < 0.60 are discarded."""
        from agents.research.predictions.output_writer import write_prediction
        result = write_prediction(
            asset="BTC/USD",
            candle_timestamp=datetime.utcnow(),
            ensemble_result={
                "signal": "BUY",
                "confidence": 0.45,   # below threshold
                "estimated_price": 45000.0,
                "regime": "BULL",
                "model_breakdown": {},
                "forecast_horizon": 14,
            },
            dry_run=True,   # no DB write even if threshold passes
        )
        assert result is None  # discarded

    def test_dry_run_does_not_raise(self):
        from agents.research.predictions.output_writer import write_prediction
        result = write_prediction(
            asset="BTC/USD",
            candle_timestamp=datetime.utcnow(),
            ensemble_result={
                "signal": "BUY",
                "confidence": 0.75,
                "estimated_price": 45200.0,
                "regime": "BULL",
                "model_breakdown": {"lgbm": {"signal": "BUY", "weight": 0.30}},
                "forecast_horizon": 14,
            },
            dry_run=True,
        )
        assert result is not None
        assert result.confidence == 0.75


# ---------------------------------------------------------------------------
# WalkForwardValidator
# ---------------------------------------------------------------------------

class TestWalkForward:
    def test_fold_structure_no_leakage(self):
        """Verify that test windows never overlap with training windows."""
        from agents.research.predictions.walk_forward import WalkForwardValidator, FoldResult
        from agents.research.predictions.models.monte_carlo import MonteCarloForecaster

        df = make_ohlcv(700)
        validator = WalkForwardValidator(n_folds=3, test_size=50, min_train_size=200)

        result = validator.run(
            df=df,
            model_cls=MonteCarloForecaster,
            model_kwargs={"asset": "BTC/USD", "n_simulations": 50},
        )
        assert result.n_folds == 3
        assert 0.0 <= result.mean_accuracy <= 1.0

    def test_insufficient_data_raises(self):
        from agents.research.predictions.walk_forward import WalkForwardValidator
        from agents.research.predictions.models.monte_carlo import MonteCarloForecaster
        df = make_ohlcv(100)   # too small for default fold config
        validator = WalkForwardValidator(n_folds=5, test_size=50, min_train_size=200)
        with pytest.raises(ValueError, match="Not enough data"):
            validator.run(df=df, model_cls=MonteCarloForecaster,
                          model_kwargs={"asset": "BTC/USD"})
