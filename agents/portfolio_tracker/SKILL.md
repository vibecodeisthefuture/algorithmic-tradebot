---
name: Risk Policy Control
description: Dynamically manage and switch between four risk tolerance policies (HIGH/MODERATE-AGGRESSIVE/MODERATE/LOW) based on market conditions, portfolio health, and AI agent analysis
---

# Risk Policy Control Skill

This skill enables AI agents to dynamically control the risk tolerance policy for the algorithmic trading system. **The default stance is aggressive growth with discipline (MODERATE-AGGRESSIVE policy)**, scaling up to HIGH during exceptional conditions, down to MODERATE during elevated volatility, or LOW during crisis. The philosophy is to optimize for Sharpe >2.0 risk-adjusted returns while maintaining circuit breakers for extreme events.

## Prerequisites

### Required Files
- **risk_override.py** - Four-tier policy risk validation system
- `data/tradebot.db` → `portfolio_snapshots` table — Portfolio state tracking
- `data/tradebot.db` → `system_state` table — Current policy configuration
- **RISK_POLICY_FRAMEWORK.md** - Complete four-tier framework documentation (v3.0)

### Required Python Libraries
- `yfinance` - VIX data source
- `dataclasses` - Policy configuration management
- `pyzmq` - ZeroMQ bindings for real-time event publishing (optional, graceful fallback)

### ZeroMQ Event Bus Integration

The Portfolio Tracker publishes real-time notifications via the ZeroMQ event bus when critical actions are detected:

| Topic | Trigger |
|-------|---------|
| `CIRCUIT_BREAKER` | Volatility circuit breaker or emergency triggered |
| `PORTFOLIO.ALERT` | High-priority liquidity, recovery, or performance alerts |

> These are best-effort notifications — the SQLite database remains the source of truth. If ZeroMQ is unavailable, the agent operates normally via DB writes.

> [!IMPORTANT]
> **Version 3.0 Update - Four-Tier Framework**
>
> The risk policy system has been upgraded from three-tier to four-tier framework (Version 3.0):
> - **OLD**: HIGH → MODERATE → LOW
> - **NEW**: HIGH → MODERATE-AGGRESSIVE (default) → MODERATE → LOW
>
> **Key Changes**:
> - Default changed from HIGH to **MODERATE-AGGRESSIVE**
> - MODERATE-AGGRESSIVE optimized for 10-year aggressive growth with Sharpe >2 focus
> - HIGH now used for opportunistic expansion only (VIX <15)
> - MODERATE is now defensive buffer (VIX 20-25), not default
> - See [RISK_POLICY_FRAMEWORK.md](RISK_POLICY_FRAMEWORK.md) v3.0 for complete details

## 1. Understanding the Four Policies

| Policy | Profile | Growth/Preservation | Max Drawdown | Max Leverage | Single Position |
|--------|---------|---------------------|--------------|--------------|-----------------|
| **HIGH** | Aggressive Growth | 80/20 | 35% | 3x | 30% |
| **MOD-AGG** | Growth-Focused (DEFAULT) | 65/35 | 20% | 2.5x | 25% |
| **MODERATE** | Balanced | 60/40 | 25% | 2x | 20% |
| **LOW** | Conservative | 30/70 | 15% | 1.2x | 12% |

### When to Use Each Policy

**MODERATE-AGGRESSIVE (Growth-Focused) - DEFAULT STANCE**
- Normal/strong market conditions (VIX 15-20)
- Portfolio drawdown < 10%
- Sharpe >2.0 optimization focus
- 10-year aggressive growth with liquidity maintenance
- **Default policy (65-70% of time) - primary operating mode**

**HIGH (Aggressive Growth) - OPPORTUNISTIC EXPANSION**
- Exceptional market strength (VIX < 15)
- Portfolio drawdown < 8%
- Strong bullish momentum with low volatility
- **Temporary use (5-10% of time) - return to MOD-AGG when normalizes**

**MODERATE (Balanced) - DEFENSIVE BUFFER**
- Elevated volatility (VIX 20-25)
- Portfolio drawdown 10-15%
- Transitional buffer between MOD-AGG and LOW
- **Temporary use (10-15% of time) - return to MOD-AGG when stabilizes**

**LOW (Conservative) - SURVIVAL MODE**
- Crisis conditions (VIX > 25 OR drawdown > 15%)
- Black swan events or severe market stress
- Capital preservation during extreme volatility
- **Emergency use (10-15% of time) - return to MOD-AGG after recovery**

## 2. Checking Current Policy

### Get Active Policy

```python
from risk_override import RiskPolicyValidator

validator = RiskPolicyValidator()
current_policy = validator.get_current_policy()

print(f"Active Policy: {current_policy['profile']}")
print(f"Max Drawdown: {current_policy['max_drawdown']}%")
print(f"Circuit Breaker: {current_policy['circuit_breaker']}%")
print(f"Max Leverage: {current_policy['max_leverage']}x")
print(f"Single Position Max: {current_policy['single_position_max']}%")
```

### Expected Output
```
Active Policy: MODERATE
Max Drawdown: 25.0%
Circuit Breaker: 18.0%
Max Leverage: 2.0x
Single Position Max: 20.0%
```

## 3. Switching Between Policies

### Basic Policy Switch

```python
from risk_override import RiskProfile

# Switch to aggressive growth
validator.switch_policy(
    RiskProfile.HIGH,
    reason="Favorable market: VIX 14.2, drawdown 2.3%"
)

# Switch to conservative
validator.switch_policy(
    RiskProfile.LOW,
    reason="High volatility: VIX 32.5, defensive positioning"
)

# Switch to balanced
validator.switch_policy(
    RiskProfile.MODERATE,
    reason="Normalizing market conditions"
)
```

### Policy Switch with Logging

The system automatically logs all policy changes to `policy_history` table in `data/tradebot.db`:

```json
{
  "active_policy": "LOW",
  "changed_at": "2026-02-03T07:27:23.000000",
  "reason": "High volatility detected: VIX>30"
}
```

## 4. VIX-Based Policy Switching

Use current market volatility to determine appropriate risk policy.

### Simple VIX Threshold Strategy

```python
validator = RiskPolicyValidator()
vix_level = validator.get_vix_level()

if vix_level > 25:
    # High volatility → Conservative
    validator.switch_policy(
        RiskProfile.LOW,
        f"VIX spike: {vix_level:.2f} (>25 threshold)"
    )
    print("📉 Switched to LOW policy - Capital preservation mode")

elif vix_level > 20:
    # Elevated volatility → Defensive buffer
    validator.switch_policy(
        RiskProfile.MODERATE,
        f"Elevated volatility: VIX {vix_level:.2f} (20-25 range)"
    )
    print("⚖️  Switched to MODERATE policy - Defensive buffer")

elif vix_level < 15:
    # Low volatility → Opportunistic
    validator.switch_policy(
        RiskProfile.HIGH,
        f"Low volatility: VIX {vix_level:.2f} (<15 threshold)"
    )
    print("📈 Switched to HIGH policy - Opportunistic growth mode")

else:
    # Normal volatility (VIX 15-20) → Default growth-focused
    if validator.policy_profile != RiskProfile.MODERATE_AGGRESSIVE:
        validator.switch_policy(
            RiskProfile.MODERATE_AGGRESSIVE,
            f"Normal volatility: VIX {vix_level:.2f} (15-20 range)"
        )
        print("🚀 Switched to MODERATE-AGGRESSIVE policy - Default growth mode")
```

### VIX Threshold Reference (Four-Tier Framework)

| VIX Level | Market Condition | Recommended Policy |
|-----------|-----------------|-------------------|
| < 15 | Low volatility | **HIGH** (opportunistic) |
| 15-20 | Normal/Strong | **MODERATE-AGGRESSIVE** (default) |
| 20-25 | Elevated | **MODERATE** (defensive buffer) |
| 25-30 | High volatility | **MODERATE or LOW** (evaluate) |
| 30-35 | Crisis | **LOW** (capital preservation) |
| > 35 | Extreme | **LOW** (survival mode) |

**Default Stance**: MODERATE-AGGRESSIVE for VIX 15-20. Scale up to HIGH for exceptional conditions, down to MODERATE/LOW as volatility increases.

## 5. Drawdown-Based Policy Switching

Protect capital by adjusting policy when portfolio declines.

### Drawdown Response Strategy

```python
validator = RiskPolicyValidator()
drawdown = validator.health_monitor.calculate_drawdown()
current_policy = validator.policy_profile

print(f"Current Drawdown: {drawdown:.2f}%")
print(f"Current Policy: {current_policy.value}")

# Aggressive → Moderate at 8% drawdown
if drawdown > 8 and current_policy == RiskProfile.HIGH:
    validator.switch_policy(
        RiskProfile.MODERATE,
        f"Drawdown {drawdown:.2f}% exceeds 8% - reducing risk"
    )
    print("⚠️  Reduced risk: HIGH → MODERATE")

# Moderate → Conservative at 12% drawdown
elif drawdown > 12 and current_policy != RiskProfile.LOW:
    validator.switch_policy(
        RiskProfile.LOW,
        f"Drawdown {drawdown:.2f}% exceeds 12% - preserving capital"
    )
    print("🛡️  Capital preservation: → LOW")

# Return to aggressive when recovered
elif drawdown < 3 and current_policy == RiskProfile.MODERATE:
    validator.switch_policy(
        RiskProfile.HIGH,
        f"Portfolio recovered: drawdown only {drawdown:.2f}%"
    )
    print("✅ Portfolio healthy: MODERATE → HIGH")
```

### Drawdown Action Thresholds (Four-Tier Framework)

| Drawdown | From HIGH | From MOD-AGG (Default) | From MODERATE | From LOW |
|----------|-----------|------------------------|---------------|----------|
| < 5% | **Stay HIGH** | **Stay MOD-AGG** | → MOD-AGG | Stay |
| 5-8% | **Stay HIGH** | **Stay MOD-AGG** | → MOD-AGG if VIX<20 | Stay |
| 8-10% | → MOD-AGG | **Stay MOD-AGG** (monitor) | Stay | Stay |
| 10-15% | → MOD-AGG | → MODERATE (brief) | Stay | Stay |
| 15-18% | → MODERATE | → LOW (circuit breaker) | Stay | Stay |
| 18-20% | → LOW | → LOW (emergency) | → LOW | Stay |
| > 20% | → LOW | → LOW (full liquidation) | → LOW | Stay |

**Default**: MODERATE-AGGRESSIVE is the primary operating mode (65-70% of time). Scale to HIGH for exceptional conditions, MODERATE/LOW for elevated volatility.

## 6. Market Regime Detection

Comprehensive AI analysis to classify market conditions.

### Multi-Signal Regime Classification

```python
validator = RiskPolicyValidator()

# Gather market signals
vix = validator.get_vix_level()
drawdown = validator.health_monitor.calculate_drawdown()
portfolio_value = validator.health_monitor.get_portfolio_value()

print(f"Market Analysis:")
print(f"  VIX: {vix:.2f}")
print(f"  Drawdown: {drawdown:.2f}%")
print(f"  Portfolio: ${portfolio_value:,.2f}")

# Classify market regime (AGGRESSIVE BIAS)
if vix < 25 and drawdown < 12:
    regime = "NORMAL_GROWTH"
    recommended_policy = RiskProfile.HIGH
    confidence = 0.85
    
elif vix > 30 or drawdown > 18:
    regime = "CRISIS"  
    recommended_policy = RiskProfile.LOW
    confidence = 0.90
    
elif vix > 25 or drawdown > 12:
    regime = "VOLATILITY_SPIKE"
    recommended_policy = RiskProfile.MODERATE
    confidence = 0.75
    
else:
    regime = "TRANSITIONAL"
    recommended_policy = RiskProfile.HIGH  # Default to HIGH
    confidence = 0.70

print(f"\nRegime: {regime} (Confidence: {confidence:.0%})")
print(f"Recommended: {recommended_policy.value}")

# Apply policy if different from current
if validator.policy_profile != recommended_policy:
    validator.switch_policy(
        recommended_policy,
        f"Market regime: {regime} (confidence: {confidence:.0%})"
    )
    print(f"✅ Policy adjusted to {recommended_policy.value}")
```

### Regime Classification Rules (Four-Tier Framework)

| Regime | VIX | Drawdown | Duration | Policy |
|--------|-----|----------|----------|--------|
| **EXCEPTIONAL** | < 15 | < 8% | Opportunistic | **HIGH** |
| **NORMAL_GROWTH** | 15-20 | < 10% | Default | **MODERATE-AGGRESSIVE** |
| **ELEVATED** | 20-25 | 10-15% | Defensive | **MODERATE** |
| **CRISIS** | 25-30 | 15-20% | Severe | **LOW** |
| **BLACK_SWAN** | > 35 | > 20% | Extreme | **LOW** (survival) |

**Default**: MODERATE-AGGRESSIVE is the primary regime (VIX 15-20). Scale to HIGH only during exceptional conditions (VIX <15).

## 7. Daily Policy Review Workflow

Automated daily check and adjustment routine.

### Complete Daily Review

```python
def daily_policy_review():
    """AI agent daily policy review and adjustment"""
    
    validator = RiskPolicyValidator()
    
    # Step 1: Gather all signals
    vix = validator.get_vix_level()
    dd = validator.health_monitor.calculate_drawdown()
    current = validator.policy_profile
    
    print("="*70)
    print("DAILY POLICY REVIEW")
    print("="*70)
    print(f"VIX: {vix:.2f}")
    print(f"Drawdown: {dd:.2f}%")
    print(f"Current Policy: {current.value}\n")
    
    # Step 2: Determine recommended policy (FOUR-TIER FRAMEWORK)
    if vix > 25 or dd > 15:
        rec = RiskProfile.LOW
        reason = f"Crisis mode: VIX={vix:.2f}, DD={dd:.2f}%"
    elif vix > 20 or dd > 10:
        rec = RiskProfile.MODERATE
        reason = f"Elevated volatility: VIX={vix:.2f}, DD={dd:.2f}%"
    elif vix < 15 and dd < 8:
        rec = RiskProfile.HIGH
        reason = f"Exceptional conditions: VIX={vix:.2f}, DD={dd:.2f}%"
    else:
        # DEFAULT TO MODERATE-AGGRESSIVE for normal conditions
        rec = RiskProfile.MODERATE_AGGRESSIVE
        reason = f"Normal growth: VIX={vix:.2f}, DD={dd:.2f}%"
    
    # Step 3: Apply if change needed
    if rec != current:
        validator.switch_policy(rec, reason)
        print(f"🔄 Policy Changed: {current.value} → {rec.value}")
        print(f"   Reason: {reason}")
    else:
        print(f"✓ Policy Maintained: {current.value}")
        print(f"   Rationale: {reason}")
    
    print("="*70)

# Run daily (e.g., before market open)
daily_policy_review()
```

### Recommended Schedule

- **Before Market Open**: Daily review at 9:00 AM EST
- **Mid-Day Check**: 12:00 PM EST if high volatility
- **After Market Close**: 4:30 PM EST for next day prep
- **Emergency**: Immediate check if VIX spikes >10 points

## 8. Policy Configuration Details

### Position Sizing by Policy

**Risk Level 0-2 (Minimal Risk)**
| Policy | Max Single | Max Total |
|--------|-----------|-----------|
| HIGH | 35% | 90% |
| MODERATE-AGGRESSIVE | 30% | 80% |
| MODERATE | 25% | 70% |
| LOW | 15% | 50% |

**Risk Level 3-4 (Low Risk)**
| Policy | Max Single | Max Total |
|--------|-----------|-----------|
| HIGH | 20% | 60% |
| MODERATE-AGGRESSIVE | 18% | 55% |
| MODERATE | 12% | 45% |
| LOW | 8% | 30% |

**Risk Level 5-6 (Moderate Risk)**
| Policy | Max Single | Max Total |
|--------|-----------|-----------|
| HIGH | 10% | 35% |
| MODERATE-AGGRESSIVE | 8% | 30% |
| MODERATE | 6% | 25% |
| LOW | 4% | 15% |

### VIX-Based Multipliers

**VIX < 15 (Low Volatility)**
- HIGH: 130% sizing
- MODERATE-AGGRESSIVE: 125% sizing
- MODERATE: 115% sizing
- LOW: 105% sizing

**VIX 15-20 (Normal)**
- HIGH: 120% sizing
- MODERATE-AGGRESSIVE: 110% sizing
- MODERATE: 105% sizing
- LOW: 95% sizing

**VIX 20-25 (Elevated)**
- HIGH: 105% sizing
- MODERATE-AGGRESSIVE: 95% sizing
- MODERATE: 90% sizing
- LOW: 75% sizing

**VIX > 45 (Crisis)**
- HIGH: 20% sizing
- MODERATE-AGGRESSIVE: 15% sizing
- MODERATE: 12% sizing
- LOW: 5% sizing

## 9. Common Workflows

### Volatility Spike Response

```powershell
# Quick VIX check and policy adjustment
cd "c:\Users\rafae\Documents\PROJECTS\TradeBot\3. Implement\PortfolioTracker"
py -c "from risk_override import RiskPolicyValidator, RiskProfile; v=RiskPolicyValidator(); vix=v.get_vix_level(); print(f'VIX: {vix:.2f}'); v.switch_policy(RiskProfile.LOW, f'VIX spike: {vix:.2f}') if vix > 30 else print('Normal')"
```

### Recovery Assessment

```python
# Check if conditions support returning to aggressive stance
validator = RiskPolicyValidator()
vix = validator.get_vix_level()
dd = validator.health_monitor.calculate_drawdown()

if vix < 18 and dd < 5 and validator.policy_profile != RiskProfile.HIGH:
    print("✅ Recovery confirmed - conditions support growth")
    validator.switch_policy(
        RiskProfile.HIGH,
        f"Market recovery: VIX {vix:.2f}, DD {dd:.2f}%"
    )
```

### Emergency Defensive Mode

```python
# Force LOW policy during black swan event
validator = RiskPolicyValidator()
validator.switch_policy(
    RiskProfile.LOW,
    "EMERGENCY: Black swan event - immediate capital preservation"
)
print("🚨 Emergency mode activated")
```

## 10. Integration with Trading System

The risk policy system integrates seamlessly with order submission.

### Order Validation Flow

```
User/AI Order Request
         ↓
Risk Policy Validator (uses active policy)
         ↓
    APPROVED? ────No───→ Reject & Log
         ↓ Yes
    Order Submission
         ↓
    Execution
```

### Automatic Policy Enforcement

All trades submitted through `submit_order.py` are automatically validated against the **currently active policy**:

```python
# In submit_order.py (already integrated)
validator = RiskPolicyValidator()  # Loads active policy
decision = validator.validate_trade(...)

if decision.status == ValidationStatus.REJECTED:
    raise RiskPolicyViolation(decision.reasons)
```

## 11. Best Practices

### Policy Switching Guidelines

1. **Document All Changes**: Always provide clear reasons
2. **Avoid Excessive Switching**: Max 1-2 changes per day unless emergency
3. **Use Gradual Transitions**: HIGH → MODERATE → LOW (avoid jumping)
4. **Monitor Impact**: Track performance under each policy
5. **Set Clear Thresholds**: Define objective triggers

### Risk Management Rules

- **Never override LOW during crisis**: If VIX > 40, stay LOW
- **Verify recovery before increasing risk**: Require 2-3 days stability
- **Respect circuit breakers**: Don't switch to HIGH if near drawdown limits
- **Log all decisions**: Maintain audit trail
- **Test policy switches**: Use dry-run mode before live trading

## 12. Monitoring and Alerts

### Check Policy History

```python
from risk_override import PolicyManager
import json

with open(PolicyManager.CONFIG_FILE, 'r') as f:
    history = json.load(f)

print(f"Active: {history['active_policy']}")
print(f"Changed: {history['changed_at']}")
print(f"Reason: {history['reason']}")
```

### Set Up Policy Change Alerts

```python
# Monitor for policy changes and alert
def check_policy_change():
    current = PolicyManager.get_active_policy()
    # Compare with expected policy
    # Send alert if unexpected change
    # Log to external monitoring system
```

## 13. Troubleshooting

### Policy Not Switching
- Verify `system_state` table is accessible (key=`risk_mode`)
- Check for file permission errors
- Ensure `reason` parameter is provided

### Inconsistent Policy Application
- Restart validator instance after manual JSON edits
- Verify Alpaca API is returning correct portfolio data
- Check `portfolio_snapshots` table is updating

### VIX Data Unavailable
- System falls back to yfinance automatically
- If both fail, uses conservative default (VIX=20)
- Install yfinance: `pip install yfinance`

## Summary Checklist

When using the Risk Policy Control skill:

- [ ] Understand current market regime (VIX, drawdown, trend)
- [ ] Check active policy before making decisions
- [ ] Use objective criteria for policy switches
- [ ] Document reason for every policy change
- [ ] Monitor policy impact on performance
- [ ] Respect circuit breakers and emergency protocols
- [ ] Review policy daily before market open
- [ ] Avoid excessive switching (max 1-2x per day)
- [ ] Test switches in dry-run mode first
- [ ] Maintain audit trail in `policy_history` table

## Additional Resources

- [RISK_TOLERANCE_HIGH.md](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/3.%20Implement/PortfolioTracker/RISK_TOLERANCE_HIGH.md) - Aggressive growth policy
- [RISK_TOLERANCE_MODERATE.md](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/3.%20Implement/PortfolioTracker/RISK%20TOLERANCE_MODERATE.md) - Balanced policy
- [RISK_TOLERANCE_LOW.md](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/3.%20Implement/PortfolioTracker/RISK_TOLERANCE_LOW.md) - Conservative policy
- [RISK_TOLERANCE_COMPARISON.md](file:///c:/Users/rafae/Documents/PROJECTS/TradeBot/3.%20Implement/PortfolioTracker/RISK_TOLERANCE_COMPARISON.md) - Side-by-side comparison
- Local Scripts: `ai_policy_control_examples.py`, `risk_override.py`
