# Backtest Agent

## Overview

This agent **continuously validates** trade strategies from the Research Agent through rigorous backtesting, optimization, and robustness analysis.

## Operating Mode

**Continuous Automated Validation** - Processes strategy queue autonomously.

```yaml
Processing Cycles:
  Queue Check (1h):      Check for new strategies (status=Ready)
  Validation Run:        On trigger, max 1 concurrent
  Results Push:          On completion to Manager/Research
  Stress Test:           After validation (crisis scenarios)
```

## Core Workflows

| Workflow | Trigger | Output |
|----------|---------|--------|
| **Queue Processing** | New strategy (status=Ready) | Test directory created |
| **Backtest Execution** | Strategy prepared | Performance metrics |
| **Validation** | Backtest complete | PASS/FAIL determination |
| **Results Documentation** | Validation complete | RESULTS.md, status update |

## Agent Integration

| Agent | Direction | Data |
|-------|-----------|------|
| **Research** | ← Receive | Trade ideas with status=Ready |
| **Research** | → Push | Rejected strategies with failure reason |
| **Manager** | → Push | Validated strategies for implementation |

## Files

| File | Purpose |
|------|---------|
| **SKILL.md** | Complete agent instructions |
| **README.md** | This quick reference |
| **OVEROPTIMIZE_WARNING.md** | Anti-overfitting protocols (MUST READ) |
| **BLACKSWANS.md** | Stress test requirements (MUST READ) |
| **test_template.py** | Standard backtest template |
| **TEST_INDEX.md** | Index of completed tests |

## Validation Criteria

```yaml
Pass Requirements:
  - min_trades: 50
  - min_sharpe: 0.8
  - max_drawdown: 30%
  - OOS ≥ 70% of in-sample
  - Walk-forward: >70% windows profitable
  - Cross-asset: Works on 2+ assets
  - Stress tests: No catastrophic failures
```

## Auto-Reject Conditions

- Sharpe > 4.0 (unrealistic)
- Annual return > 100% (overfit)
- Win rate > 90% (curve-fitted)
- Trades < 30 (insufficient sample)
- Max drawdown > 50% (excessive risk)

## Output Structure

```
data/backtests/testN/
├── <strategy_name>.py   # Strategy code
├── RESULTS.md           # Comprehensive results
└── data/                # (Optional) Test-specific data
```

## Performance Targets

- Throughput: 5+ strategies per week
- Validation Rate: >20% of strategies validated
- Turnaround: <24 hours for standard backtest
- Rejection Documentation: 100% with documented reason

---

*Autonomous strategy validation with anti-overfitting safeguards.*
