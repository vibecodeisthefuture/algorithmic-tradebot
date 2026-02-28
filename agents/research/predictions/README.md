# Predictions Agent

## Status: Planned Development

This directory is reserved for the Predictions Agent, which will generate ML-based market predictions.

## Planned Capabilities

```yaml
predictions_agent:
  purpose: Generate ML-based market predictions for strategy validation
  
  workflows:
    - model_training: Train on historical data, validate out-of-sample
    - prediction_generation: Produce forward-looking forecasts
    - strategy_refinement: AI-generated strategy improvements
    - confidence_scoring: Probabilistic prediction confidence
  
  integrations:
    receive_from: [strategy_research_agent, market_news_agent]
    push_to: [backtest_agent, manager_agent]
  
  outputs:
    - data/state/predictions.json
    - Prediction signals to Manager Agent
```

## Data Requirements

- Historical OHLCV data (minimum 5 years)
- News sentiment scores
- Economic indicators
- Order flow data (if available)

## Model Types (Planned)

1. **Time Series Forecasting** - ARIMA, Prophet, LSTM
2. **Classification** - Bull/Bear regime detection
3. **Regression** - Price target estimation
4. **Ensemble** - Combined model confidence scoring

---

*Development pending. See [Strategy Research SKILL.md](../strategy/SKILL.md) for current research workflows.*
