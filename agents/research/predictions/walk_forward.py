"""
WalkForwardValidator — Time-Series Cross-Validation Harness

Provides a strictly time-ordered validation framework for all Predictions Agent
models. No data from the future is ever used to evaluate a past-period model.

Why walk-forward (not standard k-fold)?
---------------------------------------
Standard k-fold shuffles data randomly — this leaks future information into
training sets, artificially inflating accuracy metrics. Walk-forward uses only
past data to train, then evaluates on the immediate future window, matching
real deployment conditions.

Usage
-----
    from agents.research.predictions.walk_forward import WalkForwardValidator
    from agents.research.predictions.models.lgbm_forecaster import LGBMForecaster

    validator = WalkForwardValidator(n_folds=5, test_size=100)
    results = validator.run(
        df=df,
        model_cls=LGBMForecaster,
        model_kwargs={"asset": "BTC/USD"},
    )
    print(f"Mean directional accuracy: {results['mean_accuracy']:.3f}")
"""

import logging
from dataclasses import dataclass, field
from typing import Type

import numpy as np
import pandas as pd

from agents.research.predictions.base_forecaster import BaseForecaster
from agents.research.predictions.model_signal import ModelSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class FoldResult:
    """Accuracy metrics for a single walk-forward fold."""
    fold: int
    train_rows: int
    test_rows: int
    directional_accuracy: float    # fraction of correct BUY/SELL/HOLD vs. actual direction
    signals: list = field(default_factory=list)   # list of ModelSignal produced
    actuals: list = field(default_factory=list)   # list of "UP" / "DOWN" strings


@dataclass
class WalkForwardResult:
    """Aggregate result across all walk-forward folds."""
    asset: str
    model_name: str
    n_folds: int
    fold_results: list[FoldResult]
    mean_accuracy: float
    std_accuracy: float
    min_accuracy: float
    max_accuracy: float

    def summary(self) -> str:
        return (
            f"[{self.model_name} on {self.asset}] "
            f"Accuracy: {self.mean_accuracy:.3f} ± {self.std_accuracy:.3f} "
            f"(min={self.min_accuracy:.3f}, max={self.max_accuracy:.3f}) "
            f"over {self.n_folds} folds"
        )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class WalkForwardValidator:
    """
    Runs walk-forward cross-validation for any BaseForecaster subclass.

    Walk-forward schedule (example with n_folds=5, test_size=50):

        Fold 1:  train[0:N-200]          test[N-200:N-150]
        Fold 2:  train[0:N-150]          test[N-150:N-100]
        Fold 3:  train[0:N-100]          test[N-100:N-50]
        Fold 4:  train[0:N-50]           test[N-50:N]
        Fold 5:  (if expanding window)   ...

    Each test window is evaluated on the immediately subsequent data.
    No test-period data is ever seen during training.

    Parameters
    ----------
    n_folds : int
        Number of walk-forward folds. Each fold shifts forward by test_size bars.
    test_size : int
        Number of candles per test fold.
    min_train_size : int
        Minimum training rows required before the first fold.
        Default: 200 (ensures meaningful model fit).
    """

    def __init__(
        self,
        n_folds: int = 5,
        test_size: int = 100,
        min_train_size: int = 200,
    ):
        self.n_folds = n_folds
        self.test_size = test_size
        self.min_train_size = min_train_size

    def run(
        self,
        df: pd.DataFrame,
        model_cls: Type[BaseForecaster],
        model_kwargs: dict,
    ) -> WalkForwardResult:
        """
        Execute walk-forward validation for a given model class on the dataset.

        Parameters
        ----------
        df : pd.DataFrame
            Full OHLCV DataFrame sorted ascending by timestamp.
        model_cls : Type[BaseForecaster]
            The model class to instantiate and train on each fold.
        model_kwargs : dict
            Keyword arguments passed to the model constructor.

        Returns
        -------
        WalkForwardResult
            Accuracy statistics across all folds.
        """
        total_rows = len(df)
        required = self.min_train_size + self.n_folds * self.test_size
        if total_rows < required:
            raise ValueError(
                f"Not enough data for {self.n_folds} folds of size {self.test_size}. "
                f"Need ≥{required} rows, got {total_rows}."
            )

        asset = model_kwargs.get("asset", "unknown")
        fold_results = []

        # Walk backwards: define test windows from the end of the dataset
        for fold_i in range(self.n_folds, 0, -1):
            test_end   = total_rows - (fold_i - 1) * self.test_size
            test_start = test_end - self.test_size
            train_df   = df.iloc[:test_start].copy()
            test_df    = df.iloc[test_start:test_end].copy()

            if len(train_df) < self.min_train_size:
                logger.warning(
                    "Fold %d: only %d training rows — skipping (need %d)",
                    fold_i, len(train_df), self.min_train_size,
                )
                continue

            # Instantiate a fresh model for each fold (no weight leakage)
            model: BaseForecaster = model_cls(**model_kwargs)

            try:
                model.fit(train_df, force_retrain=True)
            except Exception as exc:
                logger.error("Fold %d fit failed: %s", fold_i, exc)
                continue

            signals = []
            actuals = []

            # Evaluate one candle at a time using an expanding window
            for i in range(len(test_df)):
                # Predict using all data up to (but not including) row i
                eval_df = pd.concat([train_df, test_df.iloc[:i]], ignore_index=True)
                if len(eval_df) < self.min_train_size:
                    continue  # not enough context yet

                try:
                    sig: ModelSignal = model.predict(eval_df)
                except Exception as exc:
                    logger.debug("Fold %d row %d predict failed: %s", fold_i, i, exc)
                    continue

                # Ground truth: did price actually go up or down next candle?
                if i + 1 < len(test_df):
                    nxt = test_df.iloc[i + 1]["close"]
                    cur = test_df.iloc[i]["close"]
                    actual_dir = "UP" if nxt > cur else "DOWN"

                    # Directional match: BUY→UP, SELL→DOWN, HOLD→always "wrong"
                    predicted_dir = (
                        "UP"   if sig.signal == "BUY"  else
                        "DOWN" if sig.signal == "SELL" else
                        None   # HOLD is not directionally committed
                    )

                    signals.append(sig)
                    actuals.append(actual_dir)

            # Accuracy: only non-HOLD signals count
            directed = [
                (s.signal, a)
                for s, a in zip(signals, actuals)
                if s.signal != "HOLD"
            ]
            if directed:
                correct = sum(
                    1 for (sig_s, act) in directed
                    if (sig_s == "BUY" and act == "UP") or (sig_s == "SELL" and act == "DOWN")
                )
                acc = correct / len(directed)
            else:
                acc = 0.0  # all HOLDs → no directional accuracy

            fold_result = FoldResult(
                fold=fold_i,
                train_rows=len(train_df),
                test_rows=len(test_df),
                directional_accuracy=acc,
                signals=signals,
                actuals=actuals,
            )
            fold_results.append(fold_result)
            logger.info(
                "[%s] Fold %d/%d: acc=%.3f, directed=%d, train=%d, test=%d",
                asset, self.n_folds - fold_i + 1, self.n_folds,
                acc, len(directed), len(train_df), len(test_df),
            )

        if not fold_results:
            raise RuntimeError(f"All {self.n_folds} folds failed for {asset}.")

        accuracies = [r.directional_accuracy for r in fold_results]
        model_name = model_cls.__name__.lower()

        return WalkForwardResult(
            asset=asset,
            model_name=model_name,
            n_folds=len(fold_results),
            fold_results=fold_results,
            mean_accuracy=float(np.mean(accuracies)),
            std_accuracy=float(np.std(accuracies)),
            min_accuracy=float(np.min(accuracies)),
            max_accuracy=float(np.max(accuracies)),
        )
