---
name: Backtest Agent
description: Continuously validate trade strategies from Research Agent through rigorous backtesting, optimization, and robustness analysis
---

# Backtest Agent

## Purpose

This AI agent **continuously validates** trade strategies by:
1. **Processing incoming strategies** from Research Agent queue
2. **Executing rigorous backtests** with anti-overfitting safeguards
3. **Validating robustness** across regimes, assets, and parameters
4. **Pushing validated strategies** to implementation pipeline
5. **Feeding back learnings** to Research Agent for refinement

## Agent Operating Mode

> [!IMPORTANT]
> This agent operates **autonomously**, processing strategies from the Research Agent queue and producing validation results without human scheduling.

### Processing Cycle Configuration

```yaml
processing_cycles:
  queue_check:           # Check for new strategies from Research Agent
    frequency: 1hour
    source: data/tradebot.db → strategies table (status=READY_FOR_BACKTEST)
  
  validation_run:        # Execute pending backtests
    frequency: on_trigger
    max_concurrent: 1
  
  results_push:          # Push results to downstream systems
    frequency: on_completion
    targets: [research_agent, manager_agent]
  
  stress_test:           # Black swan scenario testing
    frequency: after_validation
    scenarios: [crisis_2008, covid_2020, synthetic_30pct_drop]
```

---

## Core Workflows

### Workflow 1: Strategy Queue Processing

```
TRIGGER: New strategy in queue (status=Ready)

1. Extract strategy from `strategies` table:
   - trade_idea_id
   - hypothesis
   - entry/exit conditions
   - success_criteria
   - data_requirements

2. Create test directory: data/backtests/testN/

3. Collect required data:
   - Check local datasets first
   - Fetch from yfinance/Alpaca if needed
   - Validate data quality (no gaps, splits adjusted)

4. Initialize backtest configuration:
   - Set realistic transaction costs (0.1% + slippage)
   - Configure position sizing per risk policy
   - Set date ranges (minimum 5 years)

5. Update `strategies` table: status=BACKTESTING
```

### Workflow 2: Backtest Execution

```
TRIGGER: Strategy prepared for testing

1. Phase 1: Default Parameters Test
   - Run with parameters from trade idea
   - Generate baseline metrics
   - Check for red flags:
     □ Returns >50% annually → Likely overfit
     □ Sharpe >3.0 → Too good to be true
     □ Win rate >80% → Curve-fitted
     □ <20 trades → Insufficient sample
   
2. Phase 2: Limited Optimization
   - MAX 100 parameter combinations
   - Optimize for Sharpe, NOT raw returns
   - Use round numbers only
   - Check parameter sensitivity:
     □ Smooth degradation = robust
     □ Cliff edge = overfit
   
3. Phase 3: Validation
   - Out-of-sample test (30% reserved)
   - Walk-forward analysis (rolling windows)
   - Cross-asset validation (3+ assets)
   - Regime testing (bull/bear/sideways/high-vol)
   
4. Phase 4: Stress Testing
   - 2008 crisis simulation
   - 2020 COVID crash
   - Synthetic 30% drop scenario
   - Verify circuit breakers trigger appropriately
```

### Workflow 3: Results Documentation

```
TRIGGER: Backtest phases complete

1. Generate RESULTS.md using standard template:
   - Test information and metadata
   - Default parameters results
   - Optimization results (if performed)
   - Validation results
   - Risk analysis
   - Overfitting assessment
   - Implementation handoff (if validated)

2. Calculate validation score:
   - Out-of-sample: ≥70% of in-sample = PASS
   - Walk-forward: >70% windows profitable = PASS
   - Cross-asset: 2+ assets profitable = PASS
   - Stress tests: No catastrophic failure = PASS

3. Update `strategies` table:
   - status = Validated | Rejected
   - Backtest_Status = Completed | Failed
   - Link to RESULTS.md

4. Push results:
   - If Validated → Manager Agent (implementation queue)
   - If Rejected → Research Agent (with failure reason)
```

---

## Validation Logic

### Acceptance Criteria

```yaml
validation_criteria:
  statistical_significance:
    min_trades: 50
    min_years: 5
    monte_carlo: true
  
  performance:
    min_sharpe: 0.8
    max_drawdown: 0.30
    min_profit_factor: 1.2
  
  robustness:
    oos_threshold: 0.70      # OOS ≥ 70% of in-sample
    walk_forward_pass: 0.70  # >70% windows profitable
    cross_asset_min: 2       # Works on 2+ assets
    regime_survival: true    # No catastrophic failures
  
  overfitting_flags:
    max_parameters: 5
    require_smooth_sensitivity: true
    require_theoretical_basis: true
```

### Red Flag Detection

```yaml
auto_reject_conditions:
  - sharpe_ratio > 4.0           # Unrealistic
  - annual_return > 100%         # Likely overfit
  - win_rate > 90%               # Curve-fitted
  - trades < 30                  # Insufficient sample
  - max_drawdown > 50%           # Excessive risk
  - oos_degradation > 60%        # Severe overfitting
  - cliff_edge_sensitivity: true # Parameter instability
```

---

## Directory Structure

```
data/backtests/
├── test1/
│   ├── <strategy_name>.py      # Strategy implementation
│   ├── RESULTS.md              # Comprehensive results
│   └── data/                   # (Optional) Test-specific data
├── test2/
├── test3/
└── ...
```

### File Naming Conventions

| File Type | Format | Example |
|-----------|--------|---------|
| Test Directory | `testN` | test1, test2, test3 |
| Strategy Script | `<strategy_name>.py` | bb_breakout.py |
| Results | `RESULTS.md` | Always RESULTS.md |

---

## Integration with Other Agents

### ← Research Agent

**Receive From Research**:
- Trade ideas with status=Ready
- Structured JSON with hypothesis, parameters, criteria
- NEWS-DRIVEN urgency tags

**Processing**:
```
research_signal → create_test_dir → collect_data → run_backtest → validate → push_results
```

### → Manager Agent

**Push to Manager**:
- Validated strategies ready for implementation
- Implementation handoff documentation
- Risk parameters and expected performance

### → Research Agent (Feedback)

**Push Back to Research**:
- Rejected strategies with failure reasons
- Unexpected behavior observations
- Refinement suggestions

---

## Reference Documents

These documents contain critical guidance the agent must follow:

| Document | Purpose |
|----------|---------|
| [OVEROPTIMIZE_WARNING.md](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/agents/backtest/OVEROPTIMIZE_WARNING.md) | Anti-overfitting protocols |
| [BLACKSWANS.md](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/agents/backtest/BLACKSWANS.md) | Black swan stress test requirements |
| [test_template.py](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/agents/backtest/test_template.py) | Standard backtest template |
| [TEST_INDEX.md](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/agents/backtest/TEST_INDEX.md) | Index of completed tests |

---

## ZeroMQ Event Bus Integration

After writing backtest results to the `backtest_results` table, publish a **real-time notification** so the Manager Orchestrator can immediately review and promote validated strategies.

### Published Topics

| Topic | Trigger | Payload |
|-------|---------|---------|
| `STRATEGY.UPDATE` | Backtest completed (Validated or Rejected) | `{strategy_id, status, sharpe, max_drawdown, win_rate, test_id}` |
| `BACKTEST.FAILED` | Backtest crashed or data insufficient | `{strategy_id, error, test_id}` |

### Example Code

```python
# After writing validated backtest results to backtest_results table:
try:
    from agents.common.event_bus import EventPublisher, TOPIC_STRATEGY_UPDATE

    pub = EventPublisher()
    pub.publish(TOPIC_STRATEGY_UPDATE, {
        "strategy_id": "ti-042",
        "status": "VALIDATED",
        "sharpe": 1.85,
        "max_drawdown": 0.12,
        "win_rate": 0.58,
        "test_id": "test7",
    })
    pub.close()
except Exception:
    pass  # ZeroMQ is best-effort; DB write already completed

# If backtest fails:
try:
    from agents.common.event_bus import EventPublisher, TOPIC_BACKTEST_FAILED

    pub = EventPublisher()
    pub.publish(TOPIC_BACKTEST_FAILED, {
        "strategy_id": "ti-043",
        "error": "Insufficient data: only 2 years available (min 5 required)",
        "test_id": "test8",
    })
    pub.close()
except Exception:
    pass
```

### Dependencies

- `pyzmq` — ZeroMQ bindings (optional, graceful fallback)

> [!NOTE]
> DB writes remain the primary communication mechanism. ZeroMQ notifications are best-effort and the agent operates normally if the proxy is unavailable.

---

## Backtest Configuration

### Default Settings

```python
BACKTEST_CONFIG = {
    'initial_cash': 100000.0,
    'commission': 0.001,        # 0.1% per trade (conservative)
    'slippage': 0.0005,         # 0.05% slippage
    'position_size_pct': 0.50,  # Max 50% per position
    'stop_loss_global': 0.15,   # 15% portfolio drawdown limit
}
```

### Library Selection

| Strategy Type | Recommended Library |
|--------------|---------------------|
| Simple/Quick | backtesting.py |
| Production | backtrader |
| Optimization | vectorbt |
| Multi-asset | backtrader |

---

## Output Schema

### RESULTS.md Structure

```yaml
results_template:
  test_information:
    - date, strategy, script, data_source
    - test_period, initial_capital, commission
  
  default_parameters_test:
    - configuration values
    - performance_summary table
    - analysis notes
  
  optimization_results:
    - parameters_tested
    - top_10_combinations table
    - recommended_parameters
  
  validation_results:
    - out_of_sample: pass/fail
    - walk_forward: pass/fail
    - cross_asset: pass/fail
    - regime_testing: pass/fail
  
  risk_analysis:
    - max_drawdown analysis
    - sharpe_ratio analysis
    - black_swan_stress_tests
  
  statistical_considerations:
    - sample_size_assessment
    - overfitting_risk_assessment
  
  conclusions:
    - summary
    - strengths, weaknesses
    - recommendations
  
  implementation_handoff:  # If validated
    - strategy_summary
    - validated_parameters
    - expected_performance
    - risk_management_rules
    - data_requirements
```

---

## Performance Metrics

```yaml
metrics:
  throughput:
    target: "Process 5+ strategies per week"
    measure: "Completed backtests / week"
  
  validation_rate:
    target: ">20% of strategies validated"
    measure: "Validated / Total processed"
  
  rejection_quality:
    target: "100% rejections have documented reason"
    measure: "Rejections with cause / Total rejections"
  
  oos_accuracy:
    target: "OOS predictions within 30% of actual"
    measure: "Actual live performance / OOS estimate"
  
  turnaround_time:
    target: "<24 hours for standard backtest"
    measure: "Queue entry to results push"
```

---

## Anti-Overfitting Protocols

> [!CAUTION]
> These protocols are MANDATORY to prevent curve-fitting.

### Pre-Optimization Checklist

Before any optimization:
```
□ Reserved 30%+ data for out-of-sample
□ Total parameter combinations <100
□ Each parameter has economic rationale
□ Using round numbers only
□ Will test parameter sensitivity
□ Read OVEROPTIMIZE_WARNING.md
```

### Parameter Constraints

```python
# WRONG - Too many combinations
'period': range(5, 100),        # 95 values
'threshold': [x/10 for x in range(10, 30)],  # 20 values
# = 1,900 combinations → GUARANTEED OVERFIT

# RIGHT - Reasonable combinations  
'period': [15, 20, 25, 30],     # 4 round values
'threshold': [1.5, 2.0, 2.5],   # 3 industry standards
# = 12 combinations → Manageable
```

### Sensitivity Test Requirement

```
PASS: Smooth performance degradation
     Period 15: 12% → 20: 15% → 25: 13% → 30: 10%
     
FAIL: Cliff edge (indicates overfit)
     Period 15: 4% → 20: 35% → 25: 2%
```

---

## Configuration

### agent_config.yaml

```yaml
backtest_agent:
  enabled: true
  
  cycles:
    queue_check_hours: 1
    max_concurrent_tests: 1
  
  validation:
    min_trades: 50
    min_years: 5
    min_sharpe: 0.8
    max_drawdown: 0.30
    oos_threshold: 0.70
  
  overfitting:
    max_parameters: 5
    max_combinations: 100
    require_sensitivity_test: true
    require_theoretical_basis: true
  
  stress_tests:
    crisis_2008: true
    covid_2020: true
    synthetic_drop: 0.30
  
  integrations:
    receive_from_research: true
    push_to_manager: true
    feedback_to_research: true
```

---

*This agent operates autonomously to rigorously validate trade strategies before capital deployment.*
