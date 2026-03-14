# Predictions Agent

## Status: Active Development

ML-based forecasting agent that generates probabilistic price signals for all tradeable assets. Operates under the Research phase of the RBI pipeline. Signals are consumed by the **Strategy Agent** and **Portfolio Tracker**.

---

## Architecture

```
run_predictions.py  ← main entry point
│
├── data_loader.py       ← OHLCV from tradebot.db / CSV fallback
├── model_signal.py      ← ModelSignal dataclass (shared contract)
├── base_forecaster.py   ← Abstract base class all models implement
├── walk_forward.py      ← Time-series CV harness (no look-ahead)
├── output_writer.py     ← Writes ensemble result → predictions table
│
└── models/
    ├── hmm_regime.py        ← Phase 5: Regime detection (run FIRST every cycle)
    ├── monte_carlo.py       ← Phase 2: Risk bands (P5/P50/P95)
    ├── arima_forecaster.py  ← Phase 3: Statistical baseline / mean-reversion
    ├── lgbm_forecaster.py   ← Phase 4: Directional classifier (primary signal)
    ├── prophet_forecaster.py← Phase 6: Seasonality decomposition
    ├── lstm_forecaster.py   ← Phase 7: Nonlinear pattern learning
    ├── tft_forecaster.py    ← Phase 8: Multi-horizon quantile forecast
    └── ensemble.py          ← Phase 9: Adaptive weighted voting
```

---

## Model Reference

> An AI agent should select models using this table. **Never run all models simultaneously** — activate by regime and purpose.

| Model | Purpose | Regime | Schedule |
|:---|:---|:---:|:---:|
| **HMM** | Regime detection — **run first, gates all others** | Always | Every cycle |
| **Monte Carlo** | Price distribution / risk bands (P5/P50/P95) | Always | Every cycle |
| **ARIMA/SARIMA** | Mean-reversion detection, statistical baseline | BEAR / NEUTRAL | Every cycle |
| **LightGBM** | Next-candle direction (primary entry signal) | BULL / NEUTRAL | Every cycle |
| **Prophet** | Seasonality decomposition, trend confirmation | BULL / NEUTRAL | Every 6h |
| **LSTM** | Nonlinear pattern sequences, 60-candle lookback | BULL / NEUTRAL | Every 6h |
| **TFT** | Multi-horizon quantile forecast (1/6/14 candles) | All | Every 6h |
| **Ensemble** | Confidence-weighted signal synthesis (final output) | All | Every cycle |

### Regime-Gating Rules

```
BEAR    → activate: HMM, Monte Carlo, ARIMA
          suppress: LightGBM, Prophet, LSTM

BULL    → activate: HMM, Monte Carlo, LightGBM, Prophet, LSTM, TFT
          suppress: ARIMA

NEUTRAL → activate: all models; equal ensemble weights
```

### Model Limitations Summary

| Model | Key Limitation |
|:---|:---|
| Monte Carlo | Assumes log-normal returns — underestimates fat tails. Weak directional signal. |
| ARIMA/SARIMA | Strictly linear. Slow on long series. Suppress in strong trends. |
| LightGBM | No temporal ordering. Requires ≥500 rows. Acts on `prob_up > 0.55` only. |
| HMM | Labels ambiguous in low-volatility sideways markets. Lags true regime by 1–3 candles. |
| Prophet | Assumes trend continuity — gaps confuse model. Uncertainty widens past 7 candles. |
| LSTM | High overfitting risk. Requires retraining every 4 weeks. No uncertainty output. |
| TFT | Requires all 12 assets present. Heaviest resource cost (~30–60 min CPU train). |
| Ensemble | Only as good as inputs. Confidence < 0.6 → signal discarded (not written to DB). |

---

## Database Output

One row written to the `predictions` table **per asset per cycle** (only if `confidence >= 0.6`).

| Column | Type | Description |
|:---|:---|:---|
| `timestamp` | DATETIME | Candle timestamp the signal applies to |
| `asset` | STRING | e.g. `BTC/USD`, `AAPL` |
| `signal` | ENUM | `BUY` / `SELL` / `HOLD` |
| `confidence` | FLOAT | Ensemble confidence 0.0–1.0 |
| `forecast_horizon` | INTEGER | Candles ahead (default: 14) |
| `regime` | ENUM | `BULL` / `NEUTRAL` / `BEAR` (from HMM) |
| `model_breakdown` | JSON | Per-model summaries + weights (compact) |
| `created_at` | DATETIME | Auto-set UTC timestamp |

### `model_breakdown` JSON shape

```json
{
  "monte_carlo": {"p05": 42100, "p50": 45200, "p95": 48900, "signal": "BUY", "weight": 0.15},
  "arima":       {"forecast": 44800, "ci_lo": 43200, "ci_hi": 46400, "signal": "HOLD", "weight": 0.20},
  "lgbm":        {"prob_up": 0.61, "signal": "BUY", "top_features": ["rsi_14", "macd"], "weight": 0.30},
  "hmm":         {"regime": "BULL"},
  "prophet":     {"yhat": 45500, "yhat_lo": 44100, "yhat_hi": 46900, "uncertainty": 0.062, "signal": "BUY", "weight": 0.20},
  "lstm":        {"pred_price": 45350, "signal": "BUY", "weight": 0.15}
}
```

### DB Footprint Rules

1. **One row per cycle per asset** — no per-model rows
2. **Summary JSON only** — no raw simulation arrays or full forecast series
3. **Confidence gate** — rows with `confidence < 0.6` are discarded (not written)
4. **90-day TTL** — rows pruned automatically by `run_predictions.py`
5. **Slow models on 6h clock** — LSTM, TFT, Prophet run every 6h, not every cycle
6. **Weights on disk** — `data/state/model_weights/lstm_{asset}.keras` — never in DB

---

## Usage

```powershell
# Run predictions for a single asset (dry run — no DB write)
python agents/research/predictions/run_predictions.py --asset BTC/USD --dry-run

# Run predictions for all configured assets
python agents/research/predictions/run_predictions.py --all-assets

# Run with a specific model only
python agents/research/predictions/run_predictions.py --asset BTC/USD --model lgbm

# Run tests
python -m pytest agents/research/predictions/tests/ -v
```

---

## Data Sources

| Asset Class | Source | Fallback |
|:---|:---|:---|
| Crypto (6h candles) | `tradebot.db` → `ohlcv` table | `data/datasets/data_tables/crypto/*.csv` |
| Stocks (1d candles) | `tradebot.db` → `ohlcv` table | `data/datasets/data_tables/stocks/*.csv` |

Assets tracked: **BTC, ETH, SOL, XRP, ADA, DOGE** (crypto) · **AAPL, GOOG, NVDA, META, NFLX, ASTS** (stocks)

---

## Integration

### Outputs To

| Consumer | Signal Used For |
|:---|:---|
| **Strategy Agent** | Entry filter — signal must be `BUY` with `confidence >= 0.6` |
| **Portfolio Tracker** | Confidence-adjusted position sizing; `regime` informs risk policy gate |
| **Analytics Agent** | Tracks per-model accuracy over time; alerts if accuracy drops below 52% |

### Retrain Schedule

| Model | Retrain Frequency | Trigger |
|:---|:---|:---|
| LightGBM | Rolling window, every 4 weeks | Scheduled |
| LSTM | Every 4 weeks | Scheduled (off-peak) |
| TFT | Every 4 weeks | Scheduled (GPU preferred) |
| HMM | Every run | Fit on last 500 candles |
| Monte Carlo / ARIMA | Every run | Stateless (fit on each call) |

---

*See [SKILL.md](./SKILL.md) for AI agent workflow instructions · See [../AGENTS.md](../AGENTS.md) for Research Agent context*
