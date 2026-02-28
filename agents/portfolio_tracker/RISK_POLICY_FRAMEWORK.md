# Risk Policy Framework

## Overview

The TradeBot system operates under a **four-tier risk management framework** that balances aggressive growth with capital preservation. The AI Manager can dynamically switch between policies based on market conditions, portfolio performance, and strategic objectives.

**Four Risk Policies**:
1. **MODERATE-AGGRESSIVE** - Growth-Focused (65/35) - **DEFAULT POLICY**
2. **HIGH** - Aggressive Growth (80/20) - Opportunistic expansion mode
3. **MODERATE** - Balanced (60/40) - Conservative baseline
4. **LOW** - Capital Preservation (30/70) - Survival mode

**Philosophy**: Default to aggressive growth with disciplined controls (**MODERATE-AGGRESSIVE**), scaling up to **HIGH** during exceptional market strength, down to **MODERATE** during elevated volatility, or **LOW** during crisis conditions. Maintain Sharpe >2.0 focus across all stances.

---

## Risk-Adjusted Performance Priority

> [!IMPORTANT]
> **SHARPE RATIO TARGET: >2.0 ACROSS ALL RISK STANCES**
>
> While minimum Sharpe ratio requirements vary by policy (HIGH: ≥0.6, MODERATE-AGGRESSIVE: ≥1.5, MODERATE: ≥0.8, LOW: ≥1.0), the **target for all strategies and policies is a Sharpe ratio >2.0**. This represents excellent risk-adjusted returns and ensures we're not just chasing raw returns at the expense of excessive volatility.
>
> **Why Sharpe >2 Matters**:
> - Sharpe >2 = Exceptional risk-adjusted performance
> - Sharpe 1-2 = Good risk-adjusted performance
> - Sharpe 0.5-1 = Adequate but room for improvement
> - Sharpe <0.5 = Poor risk-adjusted returns (re-evaluate strategy)
>
> **Application**:
> - Prioritize strategies with Sharpe >2 for increased allocation
> - Monitor portfolio-level Sharpe across all risk stances
> - If portfolio Sharpe drops below 1.5, review position sizing and strategy mix
> - Aim for consistent 2+ Sharpe through proper risk management, not just leverage

---

## Policy Comparison Table

### Key Metrics

| Metric | **HIGH** | **MOD-AGG** (Default) | **MODERATE** | **LOW** |
|--------|----------|---------------------|--------------|---------|
| **Philosophy** | 80% Growth / 20% Preservation | 65% Growth / 35% Preservation | 60% Growth / 40% Preservation | 30% Growth / 70% Preservation |
| **Max Drawdown** | 35% | 20% | 25% | 15% |
| **Circuit Breaker** | 22% | 15% | 18% | 12% |
| **Max Leverage** | 3x | 2.5x | 2x | 1.2x |
| **Cash Buffer** | 1% min | 5% min | 3% min | 10% min |
| **Single Position Max** | 30% | 25% | 20% | 12% |
| **Sector Concentration** | 50% | 45% | 35% | 25% |
| **Strategy Concentration** | 60% | 50% | 45% | 35% |
| **Liquidity Tier 1-2 Min** | 10% | 20% | 20% | 30% |
| **Portfolio Volatility Max** | 30% | 20% | 20% | 15% |
| **Avg Portfolio Correlation** | 0.50 | 0.40 | 0.40 | 0.30 |
| **Max Recovery Time (15% DD)** | 9 months | 6 months | 6 months | 3 months |

### Position Sizing by Risk Level

#### Risk Level 0-2 (Minimal Risk - Safe Strategies)
| Profile | Max Single Position | Max Total Exposure |
|---------|--------------------|--------------------|
| **HIGH** | 35% | 90% |
| **MODERATE-AGGRESSIVE** | 30% | 80% |
| **MODERATE** | 25% | 70% |
| **LOW** | 15% | 50% |

#### Risk Level 3-4 (Low Risk)
| Profile | Max Single Position | Max Total Exposure |
|---------|--------------------|--------------------|
| **HIGH** | 20% | 60% |
| **MODERATE-AGGRESSIVE** | 18% | 55% |
| **MODERATE** | 12% | 45% |
| **LOW** | 8% | 30% |

#### Risk Level 5-6 (Moderate Risk)
| Profile | Max Single Position | Max Total Exposure |
|---------|--------------------|--------------------|
| **HIGH** | 10% | 35% |
| **MODERATE-AGGRESSIVE** | 8% | 30% |
| **MODERATE** | 6% | 25% |
| **LOW** | 4% | 15% |

#### Risk Level 7-8 (High Risk - Speculative)
| Profile | Max Single Position | Max Total Exposure |
|---------|--------------------|--------------------|
| **HIGH** | 3% | 12% |
| **MODERATE-AGGRESSIVE** | 2.5% | 11% |
| **MODERATE** | 2% | 10% |
| **LOW** | 1% | 5% |

#### Risk Level 9-10 (Extreme Risk)
| Profile | Max Single Position | Max Total Exposure |
|---------|--------------------|--------------------|
| **HIGH** | 1% / 0% | 3% / 0% |
| **MODERATE-AGGRESSIVE** | 0.75% / 0% | 2.5% / 0% |
| **MODERATE** | 0.5% / 0% | 2% / 0% |
| **LOW** | 0.25% / 0% | 1% / 0% |

### VIX-Based Position Sizing Multipliers

| VIX Range | **HIGH** | **MOD-AGG** | **MODERATE** | **LOW** | Market Condition |
|-----------|----------|------------|--------------|---------|------------------|
| **< 15** | 130% | 125% | 115% | 105% | Low volatility - maximize positions |
| **15-20** | 120% | 110% | 105% | 95% | Normal market conditions |
| **20-25** | 105% | 95% | 90% | 75% | Elevated volatility - moderate caution |
| **25-30** | 85% | 75% | 70% | 50% | High volatility - defensive |
| **30-35** | 60% | 50% | 45% | 30% | Crisis volatility - highly defensive |
| **35-45** | 35% | 30% | 25% | 15% | Extreme volatility - emergency mode |
| **> 45** | 20% | 15% | 12% | 5% | Black swan - survival mode |

### Drawdown Circuit Breakers

| Drawdown Level | **HIGH** Action | **MOD-AGG** Action | **MODERATE** Action | **LOW** Action |
|----------------|----------------|------------------|-------------------|---------------|
| **5% from peak** | Monitor (100%) | Monitor (100%) | Review positions (90%) | Tighten stops (90%) |
| **8% from peak** | Monitor (100%) | Monitor (95%) | Reduce sizing (80%) | Reduce sizing (60%) |
| **12% from peak** | Review (100%) | Review (85%) | Caution (80%) | **CIRCUIT BREAKER** (50%) |
| **15% from peak** | Review (95%) | **CIRCUIT BREAKER** (70%) | Caution (75%) | Emergency (30%) |
| **18% from peak** | Caution (90%) | Emergency (40%) | **CIRCUIT BREAKER** (60%) | **EMERGENCY STOP** (20%) |
| **20% from peak** | Caution (85%) | **EMERGENCY STOP** (20%) | Emergency (40%) | Full liquidation |
| **22% from peak** | **CIRCUIT BREAKER** (70%) | Full liquidation | Emergency (25%) | Full liquidation |
| **35% from peak** | **EMERGENCY STOP** (0%) | Full liquidation | Full liquidation | Full liquidation |

---

## HIGH Policy (Aggressive Growth)

**Profile**: 80/20 - Growth Priority / Capital Preservation

> [!WARNING]
> **AGGRESSIVE PROFILE**: Tolerates substantial volatility and drawdowns up to 35% in pursuit of maximum returns. Only suitable for accounts with high risk tolerance and opportunistic growth periods.

### Risk Philosophy
- **Growth Priority (80%)**: Maximize returns through aggressive position sizing and leverage
- **Preservation Secondary (20%)**: Emergency circuit breakers only for catastrophic scenarios

### Core Metrics
- **Maximum Drawdown**: 35% (circuit breaker at 22%)
- **Target Leverage**: 2-3x
- **Cash Buffer**: 1% minimum (99% deployed)
- **Position Concentration**: Up to 30% single position

### Concentration Limits
- **Single Position**: 30% max
- **Single Sector**: 50% max
- **Single Strategy**: 60% max
- **Options Premium**: 40% max
- **Maximum Leverage**: 3x

### Strategy Risk Levels (HIGH Profile)

| Strategy | Risk Level | Max Position | Max Concurrent/Total |
|----------|-----------|--------------|---------------------|
| Short Iron Condor | 1 | 20% | 6 concurrent |
| Covered Call | 1 | 35% | - |
| Cash-Secured Put | 1 | 25% | 6 concurrent |
| Long Call/Put | 1 | 15% per | 35% total |
| Bull/Bear Spreads | 2 | 15% per | 40% total |
| Credit Spreads | 2 | 15% per | 40% total |
| Long Equity (Diversified) | 1 | 35% per stock | 99% total |
| Short Strangle | 3 | 15% per | 5 concurrent |

### Validation Requirements (HIGH)
- Backtest period: **3+ years minimum**
- Maximum drawdown: **≤ 40%**
- Win rate: **≥ 25%** OR Profit Factor **≥ 1.2**
- Sharpe ratio: **≥ 0.6**

### When to Use HIGH
✅ **Opportunistic growth mode** - strong market conditions with favorable technicals
✅ VIX < 15 AND Drawdown < 8%
✅ Strong bullish market conditions with low volatility
✅ Portfolio performing exceptionally well
✅ High conviction in market strength

---

## MODERATE-AGGRESSIVE Policy (Growth-Focused) - DEFAULT

**Profile**: 65/35 - Aggressive Growth / Disciplined Controls

> [!SUCCESS]
> **GROWTH-FOCUSED PROFILE**: Default risk stance optimized for aggressive growth with minimum instability and maintained liquidity. Tolerates drawdowns up to 20%. Ideal for 10-year horizon seeking 15-20% annual returns with Sharpe >2.0 optimization.

### Risk Philosophy
- **Aggressive Growth (65%)**: Pursue superior returns through optimized position sizing
- **Disciplined Controls (35%)**: Maintain strict risk management through volatility, correlation, and liquidity monitoring

### Core Metrics
- **Maximum Drawdown**: 20% (circuit breaker at 15%)
- **Target Leverage**: 1.75-2.5x (only on Sharpe >2 strategies)
- **Cash Buffer**: 5% minimum (95% deployed)
- **Position Concentration**: Up to 25% single position
- **Liquidity Requirement**: 20% minimum in Tier 1-2 assets
- **Volatility Target**: <20% annualized
- **Portfolio Correlation**: <0.40 average
- **Recovery Time Target**: <6 months for 15% drawdown

### Concentration Limits
- **Single Position**: 25% max
- **Single Sector**: 45% max
- **Single Strategy**: 50% max
- **Options Premium**: 30% max
- **Maximum Leverage**: 2.5x
- **Tier 1-2 Assets**: 20% minimum
- **Tier 4 Assets**: 30% maximum
- **Minimum Sectors**: 4 different sectors
- **Minimum Asset Classes**: 3 (stocks, options, cash/bonds)

### Strategy Risk Levels (MODERATE-AGGRESSIVE Profile)

| Strategy | Risk Level | Max Position | Max Concurrent/Total |
|----------|-----------|--------------|---------------------|
| Short Iron Condor | 1 | 18% | 5 concurrent |
| Covered Call | 1 | 30% | - |
| Cash-Secured Put | 1 | 20% | 5 concurrent |
| Long Call/Put | 2 | 12% per | 30% total |
| Bull/Bear Spreads | 2 | 12% per | 35% total |
| Credit Spreads | 2 | 12% per | 35% total |
| Long Equity (Diversified) | 2 | 25% per stock | 90% total |
| Short Strangle | 4 | 8% per | 4 concurrent |

### Enhanced Risk Controls

**Liquidity Management**:
- Maintain 20% in Tier 1-2 assets at all times
- Can liquidate 25% of portfolio within 48 hours with <3% slippage
- No new Tier 4 positions if liquidity drops below 18%

**Volatility Monitoring**:
- Portfolio volatility monitored continuously
- At 20% volatility: Reduce positions with Sharpe <1.5
- At 25% volatility: Circuit breaker - close Sharpe <2.0 positions

**Correlation Constraints**:
- Maximum pairwise correlation: 0.70
- Average portfolio correlation: <0.40
- During high VIX (>25): Reduce to <0.35
- Minimum 4 sectors, 3 asset classes

**Recovery Time Tracking**:
- 15% drawdown must recover within 6 months
- If recovery takes >150% expected time: Reduce allocation by 30%
- If recovery takes >200% expected time: Reduce allocation by 60%

### Validation Requirements (MODERATE-AGGRESSIVE)
- Backtest period: **7+ years minimum** (must include 2020 crash)
- Maximum drawdown: **≤ 20%**
- Win rate: **≥ 40%** OR Profit Factor **≥ 1.6**
- **Sharpe ratio: ≥ 1.5** (targeting >2.0)
- **Sortino ratio: ≥ 2.0** (downside risk focus)
- **Calmar ratio: ≥ 1.0** (return/max drawdown)

**Recovery Metrics**:
- Average drawdown recovery time: **< 4 months**
- Maximum single drawdown recovery: **< 12 months**
- % of time in drawdown: **< 30%**

**Volatility Metrics**:
- Annualized volatility: **< 20%**
- Maximum monthly volatility: **< 25%**

**Stress Tests**:
- **Required**: -20% market shock → portfolio -15% max
- **Required**: VIX spike to 40 → portfolio drawdown <18%
- **Required**: Liquidity test (can exit 30% portfolio in 48 hours with <3% slippage)
- **Required**: Correlation stress (market correlation spikes to 0.8, portfolio stays <0.5)

### Sharpe-Weighted Position Sizing

**Base position limits are adjusted by strategy's Sharpe ratio**:

| Strategy Sharpe | Position Multiplier | Example (25% base) | Priority |
|----------------|--------------------|--------------------|----------|
| **Sharpe ≥ 3.0** | 150% | 37.5% max | Top - Maximize |
| **Sharpe 2.0-3.0** | 125% | 31% max | High - Increase |
| **Sharpe 1.5-2.0** | 100% | 25% max | Standard |
| **Sharpe 1.0-1.5** | 75% | 19% max | Lower - Reduce |
| **Sharpe 0.5-1.0** | 50% | 12.5% max | Review |
| **Sharpe < 0.5** | 25% or close | 6% max | Close/Remove |

**Rules**:
- Calculate rolling 6-month Sharpe for each strategy
- Review Sharpe performance monthly
- If Sharpe drops below 1.0 for 3 months → reduce by 50%
- If Sharpe drops below 0.5 for 2 months → close position

### When to Use MODERATE-AGGRESSIVE
✅ **Default policy** - primary operating mode
✅ VIX 15-20 AND Drawdown < 10%
✅ Normal to strong market conditions
✅ 10-year aggressive growth with liquidity maintenance
✅ Focus on Sharpe >2 risk-adjusted returns
✅ Scale to HIGH for exceptional conditions
✅ Scale to MODERATE during elevated volatility
✅ Scale to LOW during crisis

---

## MODERATE Policy (Balanced)

**Profile**: 60/40 - Balanced Growth / Capital Preservation

> [!IMPORTANT]
> **BALANCED PROFILE**: Conservative baseline balancing growth objectives with capital protection. Tolerates drawdowns up to 25%. Used during elevated volatility as temporary defensive buffer between MODERATE-AGGRESSIVE and LOW.

### Risk Philosophy
- **Growth Focus (60%)**: Pursue solid returns through measured risk-taking
- **Preservation Focus (40%)**: Maintain disciplined risk controls and position sizing

### Core Metrics
- **Maximum Drawdown**: 25% (circuit breaker at 18%)
- **Target Leverage**: 1.5-2x
- **Cash Buffer**: 3% minimum (97% deployed)
- **Position Concentration**: Up to 20% single position

### Concentration Limits
- **Single Position**: 20% max
- **Single Sector**: 35% max
- **Single Strategy**: 45% max
- **Options Premium**: 25% max
- **Maximum Leverage**: 2x

### Strategy Risk Levels (MODERATE Profile)

| Strategy | Risk Level | Max Position | Max Concurrent/Total |
|----------|-----------|--------------|---------------------|
| Short Iron Condor | 2 | 12% | 4 concurrent |
| Covered Call | 1 | 25% | - |
| Cash-Secured Put | 2 | 15% | 4 concurrent |
| Long Call/Put | 2 | 8% per | 25% total |
| Bull/Bear Spreads | 2 | 10% per | 30% total |
| Credit Spreads | 3 | 10% per | 30% total |
| Long Equity (Diversified) | 2 | 20% per stock | 85% total |
| Short Strangle | 5 | 6% per | 3 concurrent |

### Validation Requirements (MODERATE)
- Backtest period: **5+ years minimum**
- Maximum drawdown: **≤ 30%**
- Win rate: **≥ 35%** OR Profit Factor **≥ 1.4**
- Sharpe ratio: **≥ 0.8**

### When to Use MODERATE
⚖️ **Defensive buffer** - temporary use during elevated volatility
⚖️ VIX 20-25 OR Drawdown 10-15%
⚖️ Transitional policy between MODERATE-AGGRESSIVE and LOW
⚖️ Elevated but manageable market uncertainty
⚖️ Return to MODERATE-AGGRESSIVE when conditions stabilize
⚖️ Scale to LOW if conditions deteriorate further

---

## LOW Policy (Capital Preservation)

**Profile**: 30/70 - Growth Secondary / Capital Preservation Priority

> [!CAUTION]
> **CONSERVATIVE PROFILE**: Prioritizes capital protection above all else. Drawdowns exceeding 15% trigger emergency protocols. For conservative investors, retirement accounts, or survival mode during crises.

### Risk Philosophy
- **Growth Secondary (30%)**: Seek steady, low-risk returns
- **Preservation Priority (70%)**: Protect capital through strict risk controls and conservative positioning

### Core Metrics
- **Maximum Drawdown**: 15% (circuit breaker at 12%)
- **Target Leverage**: 1-1.2x (minimal)
- **Cash Buffer**: 10% minimum (90% deployed max)
- **Position Concentration**: Up to 12% single position

### Concentration Limits
- **Single Position**: 12% max
- **Single Sector**: 25% max
- **Single Strategy**: 35% max
- **Options Premium**: 15% max
- **Maximum Leverage**: 1.2x

### Strategy Risk Levels (LOW Profile)

| Strategy | Risk Level | Max Position | Max Concurrent/Total |
|----------|-----------|--------------|---------------------|
| Short Iron Condor | 3 | 8% | 3 concurrent |
| Covered Call | 2 | 15% | - |
| Cash-Secured Put | 3 | 10% | 3 concurrent |
| Long Call/Put | 3 | 5% per | 15% total |
| Bull/Bear Spreads | 3 | 7% per | 20% total |
| Credit Spreads | 4 | 6% per | 20% total |
| Long Equity (Diversified) | 3 | 12% per stock | 70% total |
| Short Strangle | 6 | 4% per | 2 concurrent |

### Additional Conservative Constraints
- **Stop Losses**: Mandatory on all positions (no exceptions)
- **Position Holding**: Re-evaluate daily, exit weakness immediately
- **VIX Trigger**: Close all new positions if VIX >25
- **Correlation**: Maximum 0.60 portfolio correlation
- **Quality Filter**: Only trade liquid, established securities

### Validation Requirements (LOW)
- Backtest period: **7+ years minimum** (must include 2008, 2020)
- Maximum drawdown: **≤ 20%**
- Win rate: **≥ 45%** OR Profit Factor **≥ 1.6**
- Sharpe ratio: **≥ 1.0**
- **Stress test REQUIRED**: Must survive -30% market shock with <15% drawdown

### When to Use LOW
🛡️ **Survival mode** - crisis conditions only
🛡️ VIX > 30 OR Drawdown > 18%
🛡️ Black swan events (pandemic, war, financial crisis)
🛡️ Severe market stress requiring capital preservation
🛡️ Return to MODERATE/HIGH ASAP after stabilization

---

## Policy Switching Logic

### Automated Switching Recommendations (AI Manager Decides)

**Portfolio Tracker monitors conditions and recommends policy changes to AI Manager**:

```
Exceptional Conditions (VIX < 15, Drawdown < 8%):
├─ Recommended Policy: HIGH (Aggressive Growth)
└─ Rationale: Maximize returns during extraordinary market strength

Normal/Strong Conditions (VIX 15-20, Drawdown < 10%):
├─ Recommended Policy: MODERATE-AGGRESSIVE (Growth-Focused) - DEFAULT
└─ Rationale: Aggressive growth with disciplined risk management and Sharpe >2 focus

Elevated Volatility (VIX 20-25, Drawdown 10-15%):
├─ Recommended Policy: MODERATE (Balanced)
└─ Rationale: Temporary defensive buffer during elevated uncertainty

Crisis Conditions (VIX 25-30 OR Drawdown 15-20%):
├─ Recommended Policy: MODERATE or LOW (evaluate severity)
└─ Rationale: Significant market stress - defensive posture needed

Severe Crisis (VIX > 30 OR Drawdown > 20%):
├─ Recommended Policy: LOW (Capital Preservation)
└─ Rationale: Protect capital during severe stress

Black Swan (VIX > 35 OR Drawdown > 25%):
├─ Recommended Policy: LOW (Survival Mode)
└─ Rationale: Emergency defensive posture
```

### Policy Transition Guidelines

**MODERATE-AGGRESSIVE → HIGH** (Opportunistic Expansion):
- Trigger: VIX drops below 15 AND drawdown <8% AND exceptional market strength
- Action: Increase position sizes, deploy additional capital, expand leverage to 3x
- Goal: Maximize returns during extraordinary conditions

**MODERATE-AGGRESSIVE → MODERATE** (Defensive Caution):
- Trigger: VIX 20-25 OR drawdown 10-15%
- Action: Reduce position sizes, tighten correlation limits, increase liquidity buffer
- Goal: Temporary defensive posture during elevated volatility

**MODERATE → MODERATE-AGGRESSIVE** (Return to Default):
- Trigger: VIX drops below 20 AND drawdown recovers to <10% AND stabilization confirmed
- Action: Gradually increase exposure, return to default aggressive growth stance
- Goal: Resume normal operations with Sharpe >2 optimization

**MODERATE → LOW** (Crisis Response):
- Trigger: VIX exceeds 25 OR drawdown exceeds 15%
- Action: Significantly reduce exposure, close risky positions, increase cash to 10%
- Goal: Capital preservation during crisis

**HIGH → MODERATE-AGGRESSIVE** (Normalization):
- Trigger: VIX rises above 15 OR drawdown exceeds 8% OR weakening conditions
- Action: Reduce position sizes to default levels, normalize leverage to 2.5x
- Goal: Return to default disciplined growth

**LOW → MODERATE** (Initial Recovery):
- Trigger: VIX drops below 25 AND drawdown recovers to <15% AND stabilization beginning
- Action: Begin gradual exposure increase, maintain elevated caution
- Goal: Transition from survival to defensive buffer

**LOW → MODERATE-AGGRESSIVE** (Full Recovery):
- Trigger: VIX drops below 20 AND drawdown recovers to <10% AND strong stability (3+ days)
- Action: Resume default aggressive growth stance
- Goal: Return to primary operating mode

### AI Manager Authority

**Final decision on all policy switches resides with AI Manager**:
- Portfolio Tracker **recommends** policy changes based on rules
- AI Manager **reviews** market context, macro outlook, technical indicators
- AI Manager **approves, modifies, or rejects** recommendations
- AI Manager can make contrarian decisions (e.g., maintain HIGH during temporary VIX spike)

---

## Implementation

### Active Policy Configuration

Current policy is stored in the `system_state` table (`key='risk_mode'`):

```json
// Equivalent system_state row:
// key: "risk_mode"
// value:
  "policy": "MODERATE_AGGRESSIVE",
  "timestamp": "2026-02-05T09:00:00",
  "changed_by": "Manager",
  "reason": "Default growth-focused stance, VIX 18, drawdown 3%, normal market conditions, Sharpe >2 optimization",
  "custom_overrides": {}
}
```

### Policy Change History

All policy switches are logged to the `policy_history` table:

```csv
timestamp,from_policy,to_policy,changed_by,reason,vix,drawdown
2026-02-05T09:00:00,HIGH,MODERATE_AGGRESSIVE,Manager,Return to default growth-focused stance,18,3.8
2026-02-03T09:00:00,MODERATE_AGGRESSIVE,HIGH,Manager,Exceptional market strength opportunity,13,2.1
2026-01-30T14:30:00,MODERATE,MODERATE_AGGRESSIVE,Manager,Recovery to default after volatility,19,7.2
2026-01-28T10:00:00,MODERATE_AGGRESSIVE,MODERATE,Manager,Elevated volatility defensive buffer,23,11.5
2026-01-26T14:30:00,MODERATE,LOW,Manager,VIX spike to 28 crisis response,28,14.2
2026-01-24T09:00:00,LOW,MODERATE,Manager,Initial recovery stabilization,24,12.1
```

### Using the Risk Override System

```python
from risk_override import RiskPolicyValidator, RiskProfile

# Initialize validator
validator = RiskPolicyValidator()

# Check current policy
current = validator.get_current_policy()
print(f"Active: {current['profile']}")  # Expected: MODERATE_AGGRESSIVE (default)

# Switch policy to MODERATE during elevated volatility
validator.switch_policy(
    RiskProfile.MODERATE,
    reason="VIX elevated to 23, defensive buffer"
)

# Validate trade against active policy
decision = validator.validate_trade(
    symbol="AAPL",
    quantity=100,
    price=150.00,
    risk_level=2
)

if decision.status == ValidationStatus.APPROVED:
    # Execute trade
    pass
```

---

## Strategy Examples by Policy

### Short Iron Condor Comparison
| Policy | Risk Level | Max Position | Max Concurrent | Rationale |
|--------|-----------|--------------|----------------|-----------|
| **HIGH** | 1 | 20% | 6 | Aggressive income generation |
| **MODERATE-AGGRESSIVE** | 1 | 18% | 5 | Growth-focused income with discipline |
| **MODERATE** | 2 | 12% | 4 | Balanced income with control |
| **LOW** | 3 | 8% | 3 | Conservative income, tight risk |

### Long Equity (Diversified) Comparison
| Policy | Risk Level | Max Per Stock | Max Total | Rationale |
|--------|-----------|---------------|-----------|-----------|
| **HIGH** | 1 | 35% | 99% | Full deployment, concentrated bets |
| **MODERATE-AGGRESSIVE** | 2 | 25% | 90% | Aggressive deployment with diversification |
| **MODERATE** | 2 | 20% | 85% | Diversified, moderate concentration |
| **LOW** | 3 | 12% | 70% | Highly diversified, low concentration |

### Credit Spreads Comparison
| Policy | Risk Level | Max Position | Max Total | Rationale |
|--------|-----------|--------------|-----------|-----------|
| **HIGH** | 2 | 15% | 40% | Aggressive premium collection |
| **MODERATE-AGGRESSIVE** | 2 | 12% | 35% | Growth-focused premium with controls |
| **MODERATE** | 3 | 10% | 30% | Balanced premium with risk limits |
| **LOW** | 4 | 6% | 20% | Conservative premium, strict limits |

---

## Which Policy to Choose?

### Choose **MODERATE-AGGRESSIVE** (Growth-Focused) if:
✅ **Default policy** - primary operating mode
✅ 10-year aggressive growth with liquidity needs
✅ Focus on Sharpe >2 risk-adjusted returns
✅ VIX 15-20 AND Drawdown < 10%
✅ Normal to strong market conditions
✅ Can tolerate 20% max drawdown with 6-month recovery
✅ Most common operating mode (65-70% of the time)

### Choose **HIGH** (Aggressive Growth) if:
📈 Exceptional market conditions with extraordinary strength
📈 VIX < 15 AND Drawdown < 8%
📈 High conviction in sustained market momentum
📈 Can tolerate 35% drawdowns
📈 Temporary opportunistic expansion (5-10% of the time)
📈 Return to MODERATE-AGGRESSIVE when conditions normalize

### Choose **MODERATE** (Balanced) if:
⚖️ Elevated volatility requiring defensive buffer
⚖️ VIX 20-25 OR Drawdown 10-15%
⚖️ Transitional policy during uncertainty
⚖️ Brief buffer between MODERATE-AGGRESSIVE and LOW (10-15% of the time)
⚖️ Return to MODERATE-AGGRESSIVE when volatility subsides

### Choose **LOW** (Conservative) if:
🛡️ Crisis conditions (VIX > 25 OR Drawdown > 15%)
🛡️ Black swan events or severe market stress
🛡️ Capital preservation priority during extreme volatility
🛡️ Survival mode (10-15% of the time)
🛡️ Return to MODERATE or MODERATE-AGGRESSIVE after stabilization

---

## Validation Summary

| Metric | **HIGH** | **MOD-AGG** | **MODERATE** | **LOW** |
|--------|----------|------------|--------------|---------|
| **Backtest Period** | 3+ years | 7+ years (incl 2020) | 5+ years | 7+ years (incl crises) |
| **Max Drawdown** | ≤ 40% | ≤ 20% | ≤ 30% | ≤ 20% |
| **Win Rate** | ≥ 25% | ≥ 40% | ≥ 35% | ≥ 45% |
| **Profit Factor** | ≥ 1.2 | ≥ 1.6 | ≥ 1.4 | ≥ 1.6 |
| **Sharpe Ratio** | ≥ 0.6 | ≥ 1.5 | ≥ 0.8 | ≥ 1.0 |
| **Sortino Ratio** | - | ≥ 2.0 | - | - |
| **Calmar Ratio** | - | ≥ 1.0 | - | - |
| **Portfolio Vol Max** | - | < 20% | - | - |
| **Stress Test** | Optional | **Required** (-20% shock) | Recommended | **Required** (-30% shock) |

---

## Philosophy Summary

**Default Stance**: Aggressive Growth with Discipline (MODERATE-AGGRESSIVE)
**Opportunistic Expansion**: Scale to HIGH during exceptional market strength (VIX <15)
**Defensive Buffer**: Scale to MODERATE during elevated volatility (VIX 20-25)
**Crisis Response**: Scale to LOW during severe stress (VIX >25)
**Recovery Protocol**: Return to MODERATE-AGGRESSIVE after stabilization

The four-tier framework enables **dynamic risk management** with a focus on **Sharpe >2.0 optimization**. The AI Manager can respond instantly to changing conditions while maintaining disciplined risk controls through the Portfolio Tracker's enforcement of liquidity, volatility, correlation, and recovery time requirements.

**Policy Distribution (Expected)**:
- MODERATE-AGGRESSIVE: 65-70% of time (default)
- HIGH: 5-10% of time (exceptional conditions)
- MODERATE: 10-15% of time (defensive buffer)
- LOW: 10-15% of time (crisis survival)

---

**Last Updated**: 2026-02-05
**Version**: 3.0 (Four-Tier Framework, Default: MODERATE-AGGRESSIVE)
**Maintained By**: AI Manager + Portfolio Tracker
