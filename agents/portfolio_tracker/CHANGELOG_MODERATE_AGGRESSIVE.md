# CHANGELOG: MODERATE-AGGRESSIVE Implementation
## Version 3.0 - Four-Tier Risk Framework

**Date**: 2026-02-05
**Status**: ✅ COMPLETED

---

## Summary

Successfully implemented **MODERATE-AGGRESSIVE** as the new fourth risk policy and set it as the default for the TradeBot system. The framework has been upgraded from three-tier to four-tier risk management.

---

## Major Changes

### 1. **Framework Structure**
- **Before**: Three-tier (HIGH → MODERATE → LOW)
- **After**: Four-tier (HIGH → MODERATE-AGGRESSIVE → MODERATE → LOW)
- **Default Changed**: MODERATE → MODERATE-AGGRESSIVE

### 2. **New MODERATE-AGGRESSIVE Policy Created**

**Profile**: 65/35 - Aggressive Growth with Disciplined Controls

**Key Parameters**:
- Max Drawdown: 20% (circuit breaker at 15%)
- Target Leverage: 1.75-2.5x
- Cash Buffer: 5% minimum
- Single Position Max: 25%
- Liquidity Tier 1-2: 20% minimum
- Portfolio Volatility Max: 20% annualized
- Avg Portfolio Correlation: <0.40
- Max Recovery Time (15% DD): 6 months
- Min Sharpe Ratio: 1.5 (targeting >2.0)

**Enhanced Controls**:
- Liquidity monitoring and enforcement
- Volatility-based circuit breakers
- Correlation constraints
- Recovery time tracking
- Sharpe-weighted position sizing

---

## Detailed Changes by Section

### ✅ Overview Section (Lines 3-13)
- Updated from "three-tier" to "four-tier" framework
- Added MODERATE-AGGRESSIVE as policy #1 (default)
- Reordered policies: MOD-AGG, HIGH, MODERATE, LOW
- Updated philosophy to emphasize Sharpe >2.0 focus

### ✅ Risk-Adjusted Performance (Line 21)
- Updated Sharpe requirements to include MODERATE-AGGRESSIVE: ≥1.5

### ✅ Policy Comparison Table (Lines 41-53)
- Added MODERATE-AGGRESSIVE column to all metrics
- Added 4 new metrics rows:
  - Liquidity Tier 1-2 Min
  - Portfolio Volatility Max
  - Avg Portfolio Correlation
  - Max Recovery Time (15% DD)

### ✅ Position Sizing by Risk Level (Lines 54-87)
- Added MODERATE-AGGRESSIVE row to all 5 risk level tables:
  - Risk Level 0-2: 30% / 80%
  - Risk Level 3-4: 18% / 55%
  - Risk Level 5-6: 8% / 30%
  - Risk Level 7-8: 2.5% / 11%
  - Risk Level 9-10: 0.75% / 2.5%

### ✅ VIX-Based Position Sizing (Lines 91-99)
- Added MODERATE-AGGRESSIVE column with multipliers:
  - VIX <15: 125%
  - VIX 15-20: 110%
  - VIX 20-25: 95%
  - VIX 25-30: 75%
  - VIX 30-35: 50%
  - VIX 35-45: 30%
  - VIX >45: 15%

### ✅ Drawdown Circuit Breakers (Lines 82-89)
- Added MODERATE-AGGRESSIVE column with new triggers:
  - 5%: Monitor (100%)
  - 8%: Monitor (95%)
  - 12%: Review (85%)
  - **15%: CIRCUIT BREAKER (70%)**
  - 18%: Emergency (40%)
  - **20%: EMERGENCY STOP (20%)**

### ✅ NEW: Complete MODERATE-AGGRESSIVE Policy Section (After line 143)
**Added comprehensive policy documentation**:
- Risk Philosophy (65/35 split)
- Core Metrics (8 metrics including liquidity, volatility, correlation)
- Concentration Limits (9 limits)
- Strategy Risk Levels table (8 strategies)
- Enhanced Risk Controls:
  - Liquidity Management
  - Volatility Monitoring
  - Correlation Constraints
  - Recovery Time Tracking
- Validation Requirements (enhanced with Sortino, Calmar, stress tests)
- Sharpe-Weighted Position Sizing table
- When to Use MOD-AGG section

### ✅ Updated MODERATE Policy (Line 145+)
- Removed "DEFAULT" designation
- Changed profile description to "Conservative baseline"
- Updated "When to Use" to show it as defensive buffer
- VIX trigger changed: 20-25 (was 15-25)
- Drawdown trigger: 10-15% (was <12%)

### ✅ Policy Switching Logic (Lines 263-283)
**Updated to four-tier transitions**:
- Exceptional: VIX <15 → HIGH
- Normal/Strong: VIX 15-20 → MODERATE-AGGRESSIVE (default)
- Elevated: VIX 20-25 → MODERATE
- Crisis: VIX 25-30 → MODERATE or LOW
- Severe: VIX >30 → LOW
- Black Swan: VIX >35 → LOW

### ✅ Policy Transition Guidelines (Lines 287-305)
**Added 7 transition paths**:
1. MOD-AGG → HIGH (opportunistic expansion)
2. MOD-AGG → MODERATE (defensive caution)
3. MODERATE → MOD-AGG (return to default)
4. MODERATE → LOW (crisis response)
5. HIGH → MOD-AGG (normalization)
6. LOW → MODERATE (initial recovery)
7. LOW → MOD-AGG (full recovery)

### ✅ Implementation Examples (Lines 320-339)
- Updated active_policy.json example to show MODERATE_AGGRESSIVE
- Updated policy change history with four-tier transitions
- Updated code example to show MOD-AGG as default

### ✅ Strategy Examples (Lines 557-575)
**Added MODERATE-AGGRESSIVE row to all comparison tables**:
- Short Iron Condor: 18% / 5 concurrent
- Long Equity: 25% per / 90% total
- Credit Spreads: 12% / 35% total

### ✅ Which Policy to Choose (Lines 597-625)
**Reordered with time distribution estimates**:
1. MODERATE-AGGRESSIVE (65-70% of time) - default
2. HIGH (5-10% of time) - opportunistic
3. MODERATE (10-15% of time) - defensive buffer
4. LOW (10-15% of time) - crisis survival

### ✅ Validation Summary (Lines 632-640)
**Added MODERATE-AGGRESSIVE column**:
- Backtest: 7+ years (incl 2020)
- Max DD: ≤20%
- Win Rate: ≥40%
- Profit Factor: ≥1.6
- Sharpe: ≥1.5
- Sortino: ≥2.0
- Calmar: ≥1.0
- Portfolio Vol: <20%
- Stress Test: Required (-20% shock)

### ✅ Philosophy Summary (Lines 647-658)
- Updated default stance to MODERATE-AGGRESSIVE
- Added four-tier policy flow
- Added expected policy distribution percentages
- Emphasized Sharpe >2.0 optimization

### ✅ Version Info (Lines 665-667)
- Updated version: 2.1 → 3.0
- Updated description: "Four-Tier Framework, Default: MODERATE-AGGRESSIVE"

---

## Policy Parameter Comparison

| Parameter | HIGH | **MOD-AGG** | MODERATE | LOW |
|-----------|------|-------------|----------|-----|
| Philosophy | 80/20 | **65/35** | 60/40 | 30/70 |
| Max DD | 35% | **20%** | 25% | 15% |
| Circuit Breaker | 22% | **15%** | 18% | 12% |
| Max Leverage | 3x | **2.5x** | 2x | 1.2x |
| Cash Buffer | 1% | **5%** | 3% | 10% |
| Single Position | 30% | **25%** | 20% | 12% |
| Sector Concentration | 50% | **45%** | 35% | 25% |
| Liquidity Tier 1-2 | 10% | **20%** | 20% | 30% |
| Portfolio Vol Max | 30% | **20%** | 20% | 15% |
| Correlation | 0.50 | **0.40** | 0.40 | 0.30 |
| Recovery Time (15% DD) | 9mo | **6mo** | 6mo | 3mo |
| Min Sharpe | 0.6 | **1.5** | 0.8 | 1.0 |

**MOD-AGG sits perfectly between HIGH and MODERATE, with stricter requirements than both in key areas (DD, Vol, Sharpe).**

---

## VIX-Based Policy Recommendations

| VIX Range | Recommended Policy | Rationale |
|-----------|-------------------|-----------|
| **< 15** | HIGH | Exceptional strength |
| **15-20** | **MODERATE-AGGRESSIVE** (default) | Normal/strong conditions |
| **20-25** | MODERATE | Elevated volatility buffer |
| **25-30** | MODERATE or LOW | Crisis evaluation |
| **> 30** | LOW | Severe stress |

---

## Key Features of MODERATE-AGGRESSIVE

### 1. **Liquidity Management** ✅
- 20% minimum in Tier 1-2 assets (immediate/quick liquidity)
- Stress test: Can liquidate 25% within 48 hours with <3% slippage
- Automatic position restrictions if liquidity drops below 18%

### 2. **Volatility Circuit Breakers** ✅
- Portfolio volatility monitored continuously
- At 20% volatility: Close Sharpe <1.5 positions
- At 25% volatility: Circuit breaker - close Sharpe <2.0 positions

### 3. **Correlation Constraints** ✅
- Maximum pairwise correlation: 0.70
- Average portfolio correlation: <0.40
- Minimum 4 sectors, 3 asset classes
- During high VIX: Tighten to <0.35

### 4. **Recovery Time Tracking** ✅
- 15% drawdown must recover within 6 months
- Automatic allocation reductions if delayed:
  - >150% expected time: Reduce 30%
  - >200% expected time: Reduce 60%

### 5. **Sharpe-Weighted Position Sizing** ✅
- Position sizes adjusted by strategy Sharpe ratio
- Sharpe ≥3.0: 150% multiplier
- Sharpe 2.0-3.0: 125% multiplier
- Sharpe <1.0: Reduce by 50% after 3 months
- Sharpe <0.5: Close after 2 months

---

## Integration Points

### Files That Need Updates:

1. ✅ **RISK_POLICY_FRAMEWORK.md** - COMPLETED
2. ⏳ **risk_override.py** - Add MODERATE_AGGRESSIVE to RiskProfile enum
3. ⏳ **data/state/active_policy.json** - Update default policy
4. ⏳ **data/state/portfolio_health.json** - Add new metric fields
5. ⏳ **AI Manager prompts** - Update policy switching logic
6. ⏳ **IMPLEMENTATION_GUIDE.md** - Add MOD-AGG to all monitoring systems

### Code Changes Required:

```python
# risk_override.py - Add to RiskProfile enum
class RiskProfile(Enum):
    HIGH = "HIGH"
    MODERATE_AGGRESSIVE = "MODERATE_AGGRESSIVE"  # NEW
    MODERATE = "MODERATE"
    LOW = "LOW"
```

```json
// active_policy.json - Update default
{
  "policy": "MODERATE_AGGRESSIVE",
  "timestamp": "2026-02-05T09:00:00",
  "changed_by": "Manager",
  "reason": "Default growth-focused stance"
}
```

---

## Benefits of MODERATE-AGGRESSIVE

✅ **Optimized for 30-year-old, 10-year horizon profile**
✅ **Balances aggressive growth with minimum instability**
✅ **Maintains liquidity for opportunistic needs**
✅ **Sharpe >2.0 optimization as primary focus**
✅ **Stricter risk controls than MODERATE (20% vs 25% DD)**
✅ **Enhanced monitoring (liquidity, volatility, correlation, recovery)**
✅ **Clearer policy hierarchy with 4 distinct tiers**
✅ **Expected to be active 65-70% of the time (true default)**

---

## Next Steps

1. ✅ Update RISK_POLICY_FRAMEWORK.md - **COMPLETED**
2. ⏳ Update risk_override.py with MODERATE_AGGRESSIVE enum
3. ⏳ Update active_policy.json to default policy
4. ⏳ Implement liquidity_monitor.py with MOD-AGG thresholds
5. ⏳ Implement volatility_monitor.py with MOD-AGG thresholds
6. ⏳ Implement correlation_monitor.py with MOD-AGG thresholds
7. ⏳ Implement recovery_time_tracker.py with MOD-AGG thresholds
8. ⏳ Implement sharpe_position_sizer.py
9. ⏳ Update portfolio_orchestrator.py to support four policies
10. ⏳ Update AI Manager system prompts

---

## Testing Checklist

- [ ] Verify all tables have MOD-AGG column
- [ ] Verify policy switching logic handles four tiers
- [ ] Test VIX-based policy recommendations
- [ ] Test drawdown circuit breakers for MOD-AGG
- [ ] Verify position sizing calculations
- [ ] Test Sharpe-weighted adjustments
- [ ] Verify liquidity requirements
- [ ] Test volatility circuit breakers
- [ ] Verify correlation constraints
- [ ] Test recovery time tracking

---

**Status**: ✅ Documentation updates complete. Ready to proceed with code implementation (Phase 2).
