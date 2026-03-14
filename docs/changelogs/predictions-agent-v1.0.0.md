# CHANGELOG — Predictions Agent Implementation

## [1.0.0] — 2026-03-09

### Summary
Initial implementation of the TradeBot **Predictions Agent** (`agents/research/predictions/`).
Spanning Phases 1–9 of the 10-phase plan, this release introduces a full ML forecasting
pipeline that generates probabilistic BUY/SELL/HOLD signals for all 12 tracked assets
(6 crypto + 6 stocks). Signals are consumed by the Strategy Agent and Portfolio Tracker.

---

### New — Core Infrastructure

#### `agents/research/predictions/__init__.py`
Package marker for the predictions agent module.

#### `agents/research/predictions/model_signal.py`
- `ModelSignal` dataclass — shared IO contract between all models and the ensemble layer
- Fields: `name`, `signal` (BUY/SELL/HOLD), `confidence` (0–1), `pred_price`, `meta`
- Includes input validation and `to_breakdown_entry()` serialization helper for DB storage

#### `agents/research/predictions/base_forecaster.py`
- Abstract `BaseForecaster` class all models must subclass
- Enforces `fit(df)` and `predict(df) → ModelSignal` interface
- Provides `validate_input()`, `is_fitted`, and `model_name` property

#### `agents/research/predictions/data_loader.py`
- `load_ohlcv(asset, max_rows, min_rows)` — DB-first, CSV-fallback OHLCV loader
- Supports all 12 assets; normalizes column names (`date` → `timestamp`)
- Auto-detects and connects to `tradebot.db` via existing SQLAlchemy engine;
  falls back to `data/datasets/data_tables/{crypto,stocks}/*.csv`

#### `agents/research/predictions/output_writer.py`
- `write_prediction()` — sole writer to the `predictions` table
- Enforces confidence gate: rows with `confidence < 0.60` are discarded (not written)
- `prune_old_predictions(ttl_days=90)` — TTL pruning to prevent DB bloat

#### `agents/research/predictions/walk_forward.py`
- `WalkForwardValidator` — strictly time-ordered cross-validation harness
- N folds, each trained only on past data; directional accuracy scored per fold
- HOLD signals excluded from accuracy calculation (non-committed)

#### `agents/research/predictions/run_predictions.py`
- Main entry point — CLI with `--asset`, `--all-assets`, `--dry-run`, `--force-retrain`, `--model`
- Regime-gated model activation table: BEAR → {HMM, MC, ARIMA}; BULL → {HMM, MC, LGBM, Prophet, LSTM, TFT}
- Lazy imports for optional heavy dependencies (TF, PyTorch) — pipeline runs with whatever is installed
- Calls `prune_old_predictions()` at end of each cycle

---

### New — Forecasting Models (`agents/research/predictions/models/`)

#### `models/hmm_regime.py` — `HMMRegimeDetector` (Phase 5)
- Gaussian HMM on log-returns + rolling volatility
- `n_components=3` auto-labeled BULL / NEUTRAL / BEAR by mean return
- **Runs unconditionally first every cycle** — output gates all other models
- Requires: `pip install hmmlearn`

#### `models/monte_carlo.py` — `MonteCarloForecaster` (Phase 2)
- Geometric Brownian Motion simulation (`n_simulations=2000`, `n_steps=14`)
- Produces P5/P50/P95 price bands — primary risk-sizing input for Portfolio Tracker
- Weak directional signal (weight=0.10 in ensemble); run every cycle regardless of regime
- No external dependencies beyond numpy

#### `models/arima_forecaster.py` — `ARIMAForecaster` (Phase 3)
- SARIMA with ADF auto-stationarity detection (selects differencing order `d` automatically)
- Default: `order=(2,d,2)`, `seasonal_order=(1,1,1,28)` for 6h candles
- Graceful convergence-failure fallback emits HOLD (never crashes pipeline)
- Active in BEAR / NEUTRAL regimes; suppressed in BULL
- Requires: `pip install statsmodels`

#### `models/lgbm_forecaster.py` — `LGBMForecaster` (Phase 4)
- LightGBM next-candle directional classifier
- Feature engineering: lag returns [1,3,6,12,24], rolling vol, RSI(14), MACD, BB %B, HL range
- `TimeSeriesSplit` 5-fold CV — no temporal leakage
- BUY threshold: `prob_up > 0.55`; SELL: `prob_up < 0.45`; HOLD otherwise
- Highest ensemble prior weight (0.30) — primary entry signal
- Active in BULL / NEUTRAL; suppressed in BEAR
- Requires: `pip install lightgbm scikit-learn`

#### `models/prophet_forecaster.py` — `ProphetForecaster` (Phase 6)
- Facebook Prophet with daily + weekly seasonality; optional volume regressor
- Uncertainty band width stored as scalar; terminal candle `yhat/yhat_lo/yhat_hi` only
- Active in BULL / NEUTRAL; run on 6h schedule (not every cycle)
- Requires: `pip install prophet`

#### `models/lstm_forecaster.py` — `LSTMForecaster` (Phase 7)
- Architecture: LSTM(64) → Dropout(0.2) → LSTM(32) → Dropout(0.2) → Dense(16) → Dense(1)
- `EarlyStopping(patience=5)`; MinMaxScaler refit on training window only
- Weights cached to `data/state/model_weights/lstm_{asset}.keras` — overwritten on retrain
- Walk-forward retrain every 4 weeks; run on 6h schedule
- Requires: `pip install tensorflow scikit-learn`

#### `models/tft_forecaster.py` — `TFTForecaster` (Phase 8)
- Temporal Fusion Transformer: all 12 assets in a single joint `TimeSeriesDataSet`
- `QuantileLoss` at P10/P25/P50/P75/P90; multi-horizon (1, 6, 14 candles)
- Checkpoint saved to `data/state/model_weights/tft_checkpoint.ckpt`
- Run on 6h schedule; requires all 12 assets present with ≥300 rows each
- Requires: `pip install pytorch-forecasting lightning torch`

#### `models/ensemble.py` — `EnsembleForecaster` (Phase 9)
- Adaptive softmax-weighted vote aggregation across all active models
- Initial weights: MC=0.10, ARIMA=0.20, LGBM=0.30, Prophet=0.20, LSTM=0.15, TFT=0.20
- HMM excluded from vote (regime-only role)
- Rolling accuracy window (50 candles) per model → weights recomputed via softmax
- Final signal: `score > +0.15` → BUY; `score < -0.15` → SELL; else HOLD
- Confidence gate at 0.60 — only actionable signals written to DB

---

### New — Tests

#### `agents/research/predictions/tests/test_predictions_agent.py`
- **19 unit tests**, all passing
- Covers: `ModelSignal` validation, `DataLoader` cleaning, `MonteCarloForecaster` output/meta/DB-footprint,
  `EnsembleForecaster` voting/empty-signals, `OutputWriter` confidence gate, `WalkForwardValidator` leakage check

---

### Modified — Shared Infrastructure

#### `agents/common/enums.py`
```python
class PredictionSignal(str, enum.Enum):
    BUY = "BUY" | SELL = "SELL" | HOLD = "HOLD"

class MarketRegime(str, enum.Enum):
    BULL = "BULL" | NEUTRAL = "NEUTRAL" | BEAR = "BEAR"

class EventType(str, enum.Enum):
    ...
    PREDICTION_SIGNAL = "PREDICTION_SIGNAL"
    MODEL_ACCURACY_WARNING = "MODEL_ACCURACY_WARNING"
```

#### `agents/common/models.py`
Added `Prediction` ORM model mapping to `predictions` table:

| Column | Type | Notes |
|:---|:---|:---|
| `id` | INTEGER PK | Auto-increment |
| `timestamp` | DATETIME | Candle bar timestamp (not wall clock) |
| `asset` | STRING | e.g. `BTC/USD`, `AAPL` |
| `signal` | ENUM | `PredictionSignal` (BUY/SELL/HOLD) |
| `confidence` | FLOAT | Ensemble confidence 0.0–1.0 |
| `forecast_horizon` | INTEGER | Candles ahead (default: 14) |
| `regime` | ENUM | `MarketRegime` from HMM |
| `model_breakdown` | JSON | Compact per-model summaries |
| `created_at` | DATETIME | Auto UTC |

#### `agents/research/predictions/README.md`
Fully rewritten. Now includes: model reference table, regime-gating rules, limitations summary,
DB output schema with `model_breakdown` JSON example, usage commands, data sources, integration map,
and retrain schedule.

---

### DB Footprint Design Decisions

| Rule | Implementation |
|:---|:---|
| One row per asset per cycle | Ensemble writes the only DB row; no per-model rows |
| Summary JSON only | `model_breakdown` stores scalars; no arrays or full series |
| Confidence gate | `confidence < 0.60` → row discarded before write |
| 90-day TTL | `prune_old_predictions()` called each run cycle |
| Slow model schedule | Prophet/LSTM/TFT run every 6h, not every cycle |
| Weights on disk | LSTM/TFT weights at `data/state/model_weights/`; never in DB |

---

### Verification

```
Tests  : 19 passed, 2 warnings in 1.09s
Smoke  : PASSED — BTC/USD 13,999 rows loaded; MC P05/P50/P95 computed;
         Ensemble ran; OutputWriter confidence gate validated
Python : 3.13 (C:\Users\rafae\AppData\Local\Programs\Python\Python313\python.exe)
```

---

### Pending — Phase 10

- [ ] Update `agents/research/AGENTS.md` — mark Predictions sub-agent status `Active`
- [ ] Update `docs/DATA_SCHEMAS.md` — add `predictions` table schema
- [ ] Create `agents/research/predictions/SKILL.md` — AI agent workflow instructions
- [ ] Create `analytics/model_accuracy.py` — rolling accuracy tracker + `MODEL_ACCURACY_WARNING` event

### Pending — Optional Dep Installs

```powershell
py -3.13 -m pip install hmmlearn
py -3.13 -m pip install statsmodels
py -3.13 -m pip install lightgbm scikit-learn
py -3.13 -m pip install prophet
py -3.13 -m pip install tensorflow
py -3.13 -m pip install pytorch-forecasting lightning torch
```
