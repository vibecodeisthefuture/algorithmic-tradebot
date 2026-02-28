# Delegation Rules: Manager vs Portfolio Tracker

## Executive Summary

The **Manager Agent** is an **autonomous AI agent with final authority** on all strategic, risk, and operational decisions, available 24/7 including weekends and holidays. The **Portfolio Tracker** serves as an **advisory monitoring system** that continuously analyzes market conditions and portfolio health, providing recommendations and alerts to the Manager rather than making autonomous changes.

**Core Principle**: *Manager Decides, Portfolio Tracker Recommends*

**Key Advantage**: As an AI agent, the Manager can respond instantly to alerts at any time, enabling rapid decision-making for both stock and crypto markets without human availability constraints.

---

## Authority Structure

```
┌─────────────────────────────────────────────┐
│          MANAGER AGENT (Decision Maker)      │
│  - Final authority on all risk decisions    │
│  - Reviews and approves/rejects recommendations│
│  - Can override any Portfolio Tracker alert  │
│  - Makes discretionary judgments             │
└─────────────────────────────────────────────┘
                    ▲
                    │ Recommendations
                    │ Alerts
                    │ Reports
                    │
┌─────────────────────────────────────────────┐
│    PORTFOLIO TRACKER (Advisory System)       │
│  - Monitors market conditions (VIX, etc.)    │
│  - Calculates portfolio metrics (drawdown)   │
│  - Generates risk recommendations            │
│  - Validates order compliance with active policy│
│  - Queues suggestions for Manager review     │
└─────────────────────────────────────────────┘
```

---

## Portfolio Tracker Responsibilities

### **1. Monitoring & Analysis** (Continuous)

The Portfolio Tracker **continuously monitors** without requiring Manager intervention:

- ✅ **VIX levels** and volatility trends
- ✅ **Portfolio drawdown** from peak value
- ✅ **Position sizing** compliance with active policy
- ✅ **Market regime changes** (trending, volatile, ranging)
- ✅ **Portfolio health metrics** (exposure, concentration, correlation)
- ✅ **Order validation** against active risk policy limits

**Action**: Real-time tracking with automatic logging to `portfolio_snapshots` table in `data/tradebot.db`

---

### **2. Recommendation Generation** (Advisory)

When monitoring detects conditions that may warrant a risk policy change, Portfolio Tracker **generates recommendations** for Manager review:

#### **Risk Policy Change Recommendations**

Portfolio Tracker evaluates market conditions and suggests policy adjustments:

| Condition Detected | Portfolio Tracker Action | Manager Decision Required |
|-------------------|-------------------------|---------------------------|
| **VIX > 30** OR **Drawdown > 18%** | 🔴 **URGENT**: Recommend switch to LOW policy | ✅ Manager reviews and approves/rejects |
| **VIX 25-30** OR **Drawdown 12-18%** | 🟡 **CAUTION**: Recommend switch to MODERATE policy | ✅ Manager reviews and approves/rejects |
| **VIX < 25** AND **Drawdown < 12%** | 🟢 **STABLE**: Confirm HIGH policy appropriate | ℹ️ No action unless Manager wants review |
| **Drawdown approaching circuit breaker** (within 3%) | 🚨 **CRITICAL**: Recommend immediate position reduction | ✅ Manager makes emergency decision |

**Output**: Recommendations logged to `recommendations_queue.json` with:
- Timestamp
- Current conditions (VIX, drawdown, regime)
- Recommended action
- Reasoning
- Urgency level (Info, Caution, Urgent, Critical)

---

### **3. Alert System** (Notification)

Portfolio Tracker sends alerts to Manager for review:

#### **Alert Levels - Asset-Specific Response Times**

Due to crypto's extreme volatility (24/7 trading, flash crashes, whale movements), **crypto alerts require faster response times** than traditional stocks. With an **AI Manager available 24/7**, these response times are consistently achievable regardless of time or day.

| Level | Trigger | Stocks Response Time | Crypto Response Time | Example |
|-------|---------|---------------------|----------------------|---------|
| 🔵 **INFO** | Routine monitoring updates | Review within 24-48 hrs | Review within 12-24 hrs | "Portfolio drawdown now 8%, well within limits" |
| 🟡 **CAUTION** | Approaching threshold | Review within 24 hours | Review within 4-6 hours | "VIX rising to 26" / "BTC dropping 8% in 2 hours" |
| 🟠 **URGENT** | Threshold breached | Review within 4 hours | Review within 1-2 hours | "Drawdown exceeds 15%" / "ETH flash crash -15%" |
| 🔴 **CRITICAL** | Circuit breaker proximity or extreme event | Review within 1 hour | Review within 15-30 min | "Drawdown at 19%" / "BTC liquidation cascade detected" |

**Rationale for Faster Crypto Response**:
- Crypto markets move 2-4x faster than stocks (24/7 trading, higher volatility)
- Flash crashes and liquidation cascades can unfold in minutes, not hours
- AI Manager can respond instantly; shorter windows match crypto's speed, not human availability

**Asset Type Detection**:
- Portfolio Tracker automatically identifies asset type from position symbols
- Stocks: Traditional equities during market hours (9:30 AM - 4:00 PM EST)
- Crypto: 24/7 assets (BTC, ETH, SOL, etc.) requiring continuous monitoring

**Delivery Method**:
- Real-time alerts to AI Manager (instant notification)
- Logged to `event_log` table in database with Manager acknowledgment tracking
- No email/SMS needed - AI Manager is always active

**Crypto-Specific Alert Enhancements**:
- Flash crash detection (>10% drop in <1 hour) triggers immediate CRITICAL alert
- Liquidation cascade monitoring (funding rates + open interest) triggers URGENT alerts
- Whale movement alerts (large on-chain transfers >$100M) trigger CAUTION minimum

---

### **4. Order Validation** (Real-time Enforcement)

Portfolio Tracker **enforces compliance** with the active risk policy for all new orders:

**Pre-Trade Validation Checks**:
- ✅ Position sizing within policy limits
- ✅ Leverage not exceeding policy maximum
- ✅ Sector/asset concentration acceptable
- ✅ Total portfolio exposure within bounds
- ✅ Stop-loss levels defined

**Action**:
- ✅ **PASS**: Order forwarded to Alpaca API for execution
- ❌ **BLOCK**: Order rejected with specific violation reason
- ⚠️ **WARN**: Order allowed but Manager notified of elevated risk

**Note**: This is **automated enforcement** of policies already approved by Manager. Portfolio Tracker does NOT decide the policy limits—it only enforces them.

---

## Manager Responsibilities

### **1. Strategic Decision-Making** (Final Authority)

The Manager **makes all final decisions** on:

- ✅ **Risk Policy Selection**: Choosing HIGH/MODERATE/LOW policy
- ✅ **Policy Overrides**: Temporarily adjusting limits beyond standard policies
- ✅ **Strategy Deployment**: Approving strategies from Backtest → Implementation
- ✅ **Circuit Breaker Activation**: Emergency trading halt decisions
- ✅ **Position Adjustments**: Approving major position increases/decreases
- ✅ **Recovery Plans**: Post-drawdown strategies to return to profitability

---

### **2. Recommendation Review** (Active Oversight)

Manager reviews Portfolio Tracker recommendations and decides:

**Review Workflow**:
```
1. Portfolio Tracker detects VIX > 30
2. Generates recommendation: "Switch to LOW policy"
3. Logs to recommendations_queue.json with reasoning
4. Sends URGENT alert to Manager
5. Manager reviews:
   - Current market conditions
   - Portfolio positioning
   - Time horizon
   - Macro outlook
6. Manager decides:
   ✅ APPROVE: "Switch to LOW policy" → Portfolio Tracker updates `system_state` table (key=`risk_mode`)
   ✅ APPROVE with MODIFICATION: "Switch to MODERATE instead" → Custom action
   ❌ REJECT: "Maintain HIGH policy, this is temporary volatility" → No change
```

**Acknowledgment Required**: Manager must explicitly approve/reject recommendations. No automatic timeouts or default actions.

---

### **3. Crisis Management** (Emergency Protocol)

During market crises or black swan events, Manager has authority to:

- ✅ **Override all systems**: Manually execute emergency trades
- ✅ **Create custom risk policies**: Define temporary rules outside standard policies
- ✅ **Halt trading**: Activate circuit breaker at any time
- ✅ **Emergency hedges**: Deploy protective positions immediately

**Portfolio Tracker Role in Crisis**:
- Provides real-time data and calculations
- Flags critical situations
- Validates emergency orders for compliance (if Manager requests validation)
- Does NOT interfere with Manager emergency decisions

---

## Decision Escalation Matrix

### **Who Decides What?**

| Decision Type | Portfolio Tracker | Manager | Notes |
|---------------|------------------|---------|-------|
| **Risk Policy Change** | Recommends | Decides | PT analyzes conditions, Manager approves |
| **Circuit Breaker Activation** | Alerts | Decides | PT calculates drawdown, Manager activates |
| **Order Validation** | Enforces | Sets limits | PT enforces limits Manager defined |
| **Position Sizing Limits** | Validates | Sets | Manager defines limits in active policy |
| **Strategy Deployment** | N/A | Decides | Manager-only decision |
| **Emergency Overrides** | Alerts | Executes | PT warns, Manager overrides as needed |
| **Portfolio Rebalancing** | Recommends | Approves | PT suggests, Manager decides timing |
| **Stop-Loss Adjustments** | Recommends | Approves | PT calculates optimal levels, Manager sets |

---

## Workflow Examples

### **Example 1: Normal VIX Spike**

```
Day 1, 10:00 AM - Market opens, VIX jumps from 18 → 27

Portfolio Tracker:
├─ Detects VIX breach of 25 threshold
├─ Calculates portfolio drawdown: 8% (within limits)
├─ Generates CAUTION recommendation:
│  "VIX at 27. Recommend switching to MODERATE policy as buffer.
│   Portfolio currently healthy (8% drawdown) but volatility rising."
├─ Logs to recommendations_queue.json
└─ Sends CAUTION alert to Manager

Manager (reviews within 24 hours):
├─ Checks macro news: Fed announcement causing temporary volatility
├─ Reviews portfolio: Tech-heavy, some sensitivity
├─ Decision: "Approve switch to MODERATE as precaution"
└─ Commands Portfolio Tracker: "Switch to MODERATE"

Portfolio Tracker:
├─ Updates system_state table (key=risk_mode):
│  risk_mode → MODERATE
│  changed_by → Manager
│  reason → VIX spike to 27, Fed volatility, precautionary buffer
├─ Adjusts position sizing for new orders (max 20% per position)
├─ Continues monitoring
└─ Logs policy change to policy_history table
```

---

### **Example 1A: Crypto Flash Crash (Faster Response Protocol)**

```
Sunday, 3:00 AM - BTC drops from $48,000 → $41,000 (-14.5%) in 2 hours

Portfolio Tracker:
├─ Detects crypto flash crash (>10% drop in <3 hours)
├─ Calculates crypto portfolio drawdown: 11% (BTC positions + correlated alts)
├─ Overall portfolio drawdown: 6% (crypto is 30% of total portfolio)
├─ Generates URGENT recommendation:
│  "⚠️ CRYPTO ALERT: BTC flash crash -14.5% (2 hours). Crypto portfolio -11%.
│   Funding rates negative, potential liquidation cascade.
│   Recommend:
│   1. Switch to MODERATE policy
│   2. Close 30-40% of crypto positions (highest beta: SOL, DOGE)
│   3. Tighten stops on remaining crypto to -18%"
├─ Logs to recommendations_queue.json (priority: URGENT)
├─ Sends URGENT push notification to Manager
└─ **Crypto SLA: 1-2 hour response required**

AI Manager (responds within 2 minutes - Sunday 3:02 AM):
├─ Analyzes on-chain data: Whale wallet moved 50,000 BTC to exchange (sell pressure)
├─ Reviews funding rates: Negative, declining open interest (liquidation cascade risk)
├─ Macro context: Weekend, no macro catalyst, technical selling
├─ Cross-references historical patterns: Similar flash crash in May 2021 recovered 60% within 48h
├─ Decision: "Approve partial close with recovery-positioned modification"
└─ Commands (executed at 3:02:15 AM):
   "Close 25% of crypto positions (not 30-40%):
    - Exit: 100% of SOL, 100% of DOGE (high beta, limited recovery conviction)
    - Hold: 100% of BTC, 100% of ETH (core holdings, strong recovery potential)
    Switch to MODERATE policy.
    Set stops: BTC @ -18% ($33,620), ETH @ -20% ($2,400).
    If BTC recovers above $43,000 within 24h, consider re-entry to closed positions.
    Monitor funding rates - if turn positive, potential reversal signal."

Portfolio Tracker:
├─ Executes commands (3:02:30 AM):
│  ✅ Submits market sell orders: SOL, DOGE (25% of crypto portfolio)
│  ✅ Updates system_state table → risk_mode=MODERATE
│  ✅ Sets stops: BTC @ $33,620 (-18%), ETH @ $2,400 (-20%)
├─ Logs to event_log table:
│  "2026-02-03T03:00:00,BTC,-14.5,120,URGENT_ALERT,CLOSED_25PCT,MANAGER_RESPONSE_2MIN"
├─ Continues enhanced monitoring (15-minute intervals)
└─ AI Manager response time: 2 minutes (well within 1-2 hour crypto URGENT SLA ✅)

Outcome:
├─ BTC recovers to $44,000 by Monday morning (+7% from low)
├─ Closed positions (SOL/DOGE) saved -8% additional losses
├─ Held positions (BTC/ETH) recovered fully
└─ Manager reviews decision quality: "Partial close was optimal"
```

**Key Differences from Stock Example**:
- ⏰ **Faster Response**: 2 min vs typical hours (AI Manager's instant availability)
- 🌙 **Off-Hours**: Sunday 3 AM (AI Manager always active, no sleep needed)
- 🤖 **No Human Delay**: AI processes alert → analyzes data → decides in seconds
- 📊 **Crypto-Specific Data**: Funding rates, on-chain metrics, whale movements integrated
- ⚡ **Nuanced Decision**: AI can make contrarian calls with supporting data, not just defensive reactions

---

### **Example 2: Approaching Circuit Breaker**

```
Day 5, 2:00 PM - Market crash, portfolio deteriorating

Portfolio Tracker:
├─ Detects drawdown: 19.5% (circuit breaker at 22% for HIGH policy)
├─ Calculates proximity: Within 2.5% of circuit breaker
├─ Generates CRITICAL recommendation:
│  "⚠️ CRITICAL: Drawdown at 19.5%, approaching 22% circuit breaker.
│   Current policy: HIGH (should be LOW given drawdown).
│   Recommend:
│   1. Immediate switch to LOW policy
│   2. Close 30% of positions (highest beta/drawdown contributors)
│   3. Prepare for possible circuit breaker activation"
├─ Logs to recommendations_queue.json (priority: CRITICAL)
└─ Sends CRITICAL alert to Manager (push notification)

Manager (reviews immediately):
├─ Analyzes situation: Market-wide selloff, high correlation
├─ Reviews open positions: 15 positions, concentrated in tech
├─ Considers options:
│  A) Switch to LOW + reduce positions (Portfolio Tracker rec)
│  B) Activate circuit breaker now (emergency halt)
│  C) Hold and wait (contrarian view)
├─ Decision: "Approve Option A with modification"
└─ Commands:
   "Switch to LOW policy immediately.
    Close bottom 5 positions by P&L (not 30% of all).
    Tighten stops on remaining positions to -5%.
    Prepare circuit breaker for activation if drawdown hits 21%."

Portfolio Tracker:
├─ Executes commands:
│  ✅ Updates system_state table → risk_mode=LOW
│  ✅ Identifies bottom 5 positions by P&L
│  ✅ Submits market close orders to Alpaca
│  ✅ Sets circuit breaker trigger at 21% drawdown
├─ Monitors execution and new drawdown level
└─ Logs all actions to audit trail
```

---

### **Example 3: Manager Override (Contrarian Bet)**

```
Day 10, 9:00 AM - VIX at 32, Drawdown at 16%

Portfolio Tracker:
├─ Detects: VIX > 30 AND Drawdown > 15%
├─ Generates URGENT recommendation:
│  "VIX at 32, drawdown 16%. Recommend immediate switch to LOW policy."
└─ Sends URGENT alert to Manager

Manager (reviews immediately):
├─ Analyzes: Oversold conditions, high fear, potential reversal
├─ Macro view: Believes selloff is overreaction, opportunity to add
├─ Decision: "REJECT recommendation, maintain HIGH policy"
└─ Response:
   "Override: Maintain HIGH policy despite VIX/drawdown.
    Rationale: Extreme oversold conditions, contrarian opportunity.
    Accept elevated risk for potential rebound.
    Set manual circuit breaker at 23% drawdown (vs standard 22%).
    Acknowledge this is discretionary override."

Portfolio Tracker:
├─ Logs Manager override:
│  {
│    "recommendation_id": "rec-456",
│    "recommended_action": "Switch to LOW",
│    "manager_decision": "REJECT - Maintain HIGH",
│    "override_reason": "Contrarian bet on oversold reversal",
│    "custom_circuit_breaker": 23,
│    "timestamp": "2026-02-10T09:15:00"
│  }
├─ Continues monitoring with HIGH policy active
├─ Adjusts circuit breaker to 23% as Manager specified
├─ Sends INFO alert: "Override acknowledged, HIGH policy maintained"
└─ Will generate new recommendation if conditions worsen
```

---

## Data Files & State Management

### **Portfolio Tracker Maintains** (in `data/tradebot.db`):

1. **portfolio_snapshots** table (Real-time)
   ```python
   # Equivalent to former portfolio_health.json
   with get_db_session() as session:
       snapshot = PortfolioSnapshot(
           total_equity=98500, cash_balance=14775,
           drawdown_pct=6.2, vix_level=22,
           positions_count=12, leverage=1.2
       )
       session.add(snapshot)
   ```

2. **event_log** table (Pending Manager Review + Alerts History)
   ```python
   # Replaces recommendations_queue.json and alerts_log.csv
   with get_db_session() as session:
       event = EventLog(
           event_type=EventType.RISK_ALERT,
           urgency=Urgency.WARNING,
           source_agent="portfolio_tracker",
           target_agent="manager",
           summary="Consider switching to MODERATE policy",
           details={"vix": 26, "drawdown": 9.5, "regime": "volatile"}
       )
       session.add(event)
   ```

---

### **Manager Controls** (in `data/tradebot.db`):

1. **system_state** table (Current Risk Stance)
   ```python
   # Replaces active_policy.json
   with get_db_session() as session:
       session.merge(SystemState(key="risk_mode", value="HIGH"))
   ```

2. **policy_history** table (Audit Trail)
   ```python
   # Replaces policy_change_history.csv
   with get_db_session() as session:
       change = PolicyHistory(
           old_policy=RiskPolicy.MODERATE,
           new_policy=RiskPolicy.HIGH,
           changed_by="manager",
           reason="Market recovery",
           vix_level=19.0, drawdown_pct=5.2
       )
       session.add(change)
   ```

---

## Communication Protocols

### **How Portfolio Tracker Communicates with Manager**

1. **Real-time Alerts** (Console/CLI)
   - Display during active sessions
   - Color-coded by urgency level

2. **Recommendation Queue** (File-based)
   - Manager checks `recommendations_queue.json` daily
   - Each recommendation requires explicit response

3. **Reports** (Scheduled)
   - Daily portfolio health summary (automated)
   - Weekly risk policy effectiveness analysis
   - Monthly performance attribution

4. **Emergency Notifications** (CRITICAL only)
   - Can integrate with external alerting (email, SMS, Slack)
   - Reserved for circuit breaker proximity or extreme events

---

## Manager Response Requirements

### **Required Actions by Urgency Level (Asset-Specific SLAs)**

| Alert Level | Stocks SLA | Crypto SLA | Acknowledgment | Action Required |
|-------------|-----------|-----------|----------------|-----------------|
| 🔵 **INFO** | 24-48 hours | 12-24 hours | Optional | Read and archive |
| 🟡 **CAUTION** | 24 hours | 4-6 hours | Recommended | Review and decide |
| 🟠 **URGENT** | 4 hours | 1-2 hours | Required | Approve/reject/modify |
| 🔴 **CRITICAL** | 1 hour | 15-30 minutes | Required | Immediate decision |

**AI Manager Advantage**:
- **Always Available**: AI Manager operates 24/7/365 without downtime
- **Instant Response Capability**: Can respond in seconds to any alert
- **Consistent Decision-Making**: No fatigue, weekend delays, or off-hours unavailability
- **Parallel Processing**: Can handle multiple simultaneous alerts across stocks and crypto

**SLA Enforcement**:
- Response time starts from alert timestamp
- AI Manager typically responds within minutes for URGENT/CRITICAL alerts
- SLA windows represent maximum acceptable response time, not typical response time
- Crypto's shorter SLAs match the asset class's faster market dynamics

**Consequence of Missed SLA** (Failsafe):
- Portfolio Tracker logs missed response to audit trail (indicates potential Manager malfunction)
- Escalates urgency level after SLA expires:
  - **Stocks**: CAUTION → URGENT (after 24h), URGENT → CRITICAL (after 4h)
  - **Crypto**: CAUTION → URGENT (after 6h), URGENT → CRITICAL (after 2h)
- No autonomous action taken (system waits for Manager decision)
- Repeated missed alerts trigger diagnostic review of Manager agent

---

## System Safeguards

### **Portfolio Tracker Cannot**:

- ❌ Change risk policy without Manager approval
- ❌ Activate circuit breaker autonomously
- ❌ Close positions without Manager command
- ❌ Override Manager decisions
- ❌ Execute trades (only validates and forwards to Alpaca)
- ❌ Modify strategy parameters
- ❌ Take "emergency action" independently

### **Portfolio Tracker Must**:

- ✅ Provide reasoning for all recommendations
- ✅ Log all alerts and Manager responses
- ✅ Enforce active risk policy limits on new orders
- ✅ Monitor 24/7 and alert on threshold breaches
- ✅ Calculate accurate portfolio metrics
- ✅ Maintain transparent audit trail

---

## Scenarios Requiring Manager Judgment

These situations **always require Manager decision** (Portfolio Tracker provides data only):

1. **Conflicting Signals**
   - VIX high but drawdown low (which to prioritize?)
   - Manager assesses broader context

2. **Black Swan Events**
   - Unprecedented market conditions (COVID-style crash)
   - Portfolio Tracker has no historical precedent
   - Manager makes crisis decisions

3. **Regime Shifts**
   - Transition from bull to bear market
   - Requires strategic repositioning beyond policy change

4. **Opportunity Captures**
   - Extreme oversold conditions (contrarian entry)
   - Portfolio Tracker is defensive; Manager can be opportunistic

5. **Strategy Correlation Breaks**
   - Strategies performing unexpectedly (diverging from backtest)
   - Manager decides whether to pause, adjust, or continue

---

## Crypto-Specific Considerations

Due to cryptocurrency's unique characteristics (24/7 trading, extreme volatility, flash crashes), additional monitoring and analysis protocols apply:

### **24/7 Trading Management**

**Advantage of AI Manager**: Unlike human traders, the AI Manager operates continuously without fatigue, enabling full-time oversight of crypto markets including weekends, holidays, and overnight sessions.

**Crypto Risk Management**:
1. **Same Risk Limits as Stocks** (AI availability enables this):
   - Single-position max follows standard risk tolerance policies (HIGH: 30%, MODERATE: 20%, LOW: 12%)
   - Leverage limits per standard policies (HIGH: 3x, MODERATE: 2x, LOW: 1.2x)
   - Stop-losses calibrated to asset volatility:
     - **Stocks**: -8 to -10% (lower volatility)
     - **Crypto**: -15 to -20% (higher volatility to avoid noise-triggered exits)

2. **Enhanced Monitoring (Not Restrictions)**:
   - AI Manager monitors crypto positions continuously, even during traditional market off-hours
   - Weekend/overnight sessions receive same attention as weekday trading
   - No need to reduce exposure prophylactically - Manager is always alert

3. **Rapid Response to Events**:
   - **Flash Crash Detection**: >10% drop in <1 hour triggers immediate analysis and response
   - **Liquidation Cascade Monitoring**: Real-time tracking of funding rates and open interest
   - **Whale Movement Analysis**: On-chain data integrated into decision-making
   - Manager can execute defensive actions within minutes when warranted

### **Crypto Volatility Multipliers**

Portfolio Tracker applies **volatility adjustments** to crypto recommendations:

| Crypto Condition | Threshold Adjustment | Example |
|-----------------|---------------------|---------|
| **Normal** (BTC volatility <3% daily) | Standard thresholds | VIX 30 equivalent |
| **Elevated** (BTC volatility 3-5% daily) | Reduce thresholds by 20% | VIX 24 triggers MODERATE recommendation |
| **High** (BTC volatility 5-10% daily) | Reduce thresholds by 40% | VIX 18 triggers MODERATE recommendation |
| **Extreme** (BTC volatility >10% daily) | Immediate CRITICAL alert | Auto-recommend LOW policy |

**Crypto-Specific VIX Equivalent**:
- No traditional VIX for crypto
- Portfolio Tracker calculates **Crypto Fear Index** using:
  - Bitcoin 24-hour volatility
  - Funding rates across exchanges
  - Open interest changes
  - On-chain metrics (whale movements, exchange inflows)

### **Crypto Alert Categories**

Beyond standard market alerts, crypto requires additional monitoring:

1. **Flash Crash Alerts** 🔴
   - Trigger: >10% drop in <1 hour for major crypto (BTC/ETH)
   - Action: Immediate CRITICAL alert to Manager
   - Recommendation: Consider closing leveraged crypto positions

2. **Liquidation Cascade Alerts** 🔴
   - Trigger: Funding rates spike + open interest drops >20%
   - Action: URGENT alert (potential domino liquidations incoming)
   - Recommendation: Reduce leverage, tighten stops

3. **Whale Movement Alerts** 🟡
   - Trigger: Large on-chain transfers to/from exchanges (>$100M)
   - Action: CAUTION alert (potential large sell/buy incoming)
   - Recommendation: Monitor for next 4-6 hours

4. **Exchange Instability Alerts** 🔴
   - Trigger: Alpaca crypto API errors, degraded performance, or exchange outages
   - Action: CRITICAL alert (execution risk)
   - Recommendation: Halt new crypto orders, consider closing positions

### **Crypto Position Management**

**Sizing Rules** (AI Manager Enables Full Risk Tolerance):
```
Position Max (HIGH policy): 30% for both stocks and crypto
Leverage Max (HIGH policy): 3x for both stocks and crypto

Rationale: AI Manager's 24/7 availability enables same aggressive growth approach
          for crypto as stocks, with rapid response capability to manage volatility
```

**Stop-Loss Adjustments** (Volatility-Based):
```
Stock Stop-Loss: -8 to -10%  (lower volatility asset class)
Crypto Stop-Loss: -15 to -20%  (higher volatility asset class)

Rationale: Wider stops for crypto prevent noise-triggered exits while maintaining
          downside protection. AI Manager monitors continuously and can intervene
          manually if crypto position deteriorates faster than stop-loss threshold.
```

**Correlation Considerations**:
- Treat all crypto as **highly correlated** during market stress (0.8-0.9 correlation)
- BTC drives 70-80% of altcoin movements during crashes
- Diversification within crypto provides limited protection
- AI Manager factors correlation into position sizing decisions dynamically

### **Manager Crypto Response Playbook**

**Scenario 1: Weekend Crypto Flash Crash** (AI Manager Response)
```
Saturday 2:00 AM - BTC drops 18% in 3 hours

Portfolio Tracker:
├─ Detects crypto flash crash (>10% drop threshold breached)
├─ Calculates crypto portfolio impact: -12% (BTC + correlated alts)
├─ Sends CRITICAL alert to AI Manager
├─ Recommendation: "BTC flash crash -18%. Crypto portfolio down 12%.
│                   Recommend immediate switch to LOW + close 50% crypto exposure"
└─ Alert timestamp: 2:00:03 AM

AI Manager (responds in 45 seconds - well within 30-min SLA):
├─ Analyzes macro context: No external news catalyst (weekend)
├─ Reviews on-chain data: Whale wallet moved 50,000 BTC to exchange (sell pressure)
├─ Checks funding rates: Negative -0.05% (shorts dominating)
├─ Assesses market regime: Technical sell-off, potential oversold bounce
├─ Decision: "Approve PARTIAL close with contrarian modification"
└─ Commands (2:00:48 AM):
   "Close 30% of crypto positions (not 50%):
    - Exit: 100% of high-beta alts (SOL, DOGE)
    - Hold: 80% of BTC, 80% of ETH (core holdings, potential bounce)
    Switch to MODERATE policy (not LOW - maintain growth capacity).
    Set aggressive stops: BTC @ -22%, ETH @ -25%.
    Monitor funding rates every 15 min - switch to LOW if rates stay negative >4 hours."

Result: Manager makes nuanced decision in <1 minute, no human delay
```

**Scenario 2: Crypto Liquidation Cascade**
```
Funding rates spike to 0.1% (8-hour), open interest drops 25%

Portfolio Tracker:
├─ Detects liquidation cascade pattern
├─ Sends URGENT alert: "Liquidation cascade detected - high volatility incoming"
├─ Recommendation: "Reduce crypto leverage to <1.5x, tighten stops to -12%"
└─ Manager has 1-2 hours to respond

Manager Action:
- Review open crypto positions
- Identify leveraged positions
- Decide: De-leverage now or accept elevated risk
```

### **Crypto-Specific Data Files**

Portfolio Tracker maintains additional crypto monitoring data:

1. **crypto_volatility_index.json**
   ```json
   {
     "btc_24h_volatility": 4.2,
     "eth_24h_volatility": 5.8,
     "funding_rate_btc": 0.01,
     "open_interest_change_24h": -12.5,
     "crypto_fear_index": 35,
     "last_updated": "2026-02-03T14:30:00"
   }
   ```

2. **whale_movements_log.csv**
   ```csv
   timestamp,asset,amount_usd,direction,exchange,alert_level
   2026-02-03T12:00:00,BTC,150000000,to_exchange,Coinbase,CAUTION
   ```

3. **crypto_flash_events_log.csv**
   ```csv
   timestamp,asset,drop_pct,duration_minutes,trigger_action
   2026-02-03T02:15:00,BTC,-12.5,45,CRITICAL_ALERT
   ```

---

## Review & Audit

### **Weekly Manager Review**

Every week, Manager reviews:
- ✅ All Portfolio Tracker recommendations (approved/rejected)
- ✅ Policy change effectiveness (did switches improve performance?)
- ✅ Alert accuracy (false positives vs true warnings)
- ✅ Portfolio Tracker calibration (are thresholds appropriate?)

**Outcome**: Adjustments to thresholds, alert logic, or delegation rules if needed

### **Monthly System Audit**

Every month:
- ✅ Review override history (Manager overrides vs Portfolio Tracker recs)
- ✅ Analyze decision quality (did overrides help or hurt?)
- ✅ Update delegation rules based on lessons learned
- ✅ Refine Portfolio Tracker recommendation logic

---

## Summary: Division of Labor

| Function | Portfolio Tracker | Manager |
|----------|------------------|---------|
| **Monitoring** | Continuous real-time tracking | Reviews summaries and alerts |
| **Analysis** | Quantitative risk calculations | Qualitative judgment & strategy |
| **Recommendations** | Generates based on rules | Reviews and decides |
| **Enforcement** | Validates orders vs active policy | Defines policy limits |
| **Decisions** | None (advisory only) | All final decisions |
| **Emergency Action** | Alerts and calculates | Executes or delegates |
| **Audit Trail** | Logs all activity | Reviews and approves |

---

## Summary: Stocks vs Crypto Protocol Differences

### **Quick Reference: Asset-Specific Alert Protocols**

| Parameter | Stocks | Crypto | Rationale |
|-----------|--------|--------|-----------|
| **Trading Hours** | 9:30 AM - 4:00 PM EST (Mon-Fri) | 24/7 (365 days) | AI Manager monitors both continuously |
| **🔵 INFO Response** | 24-48 hours | 12-24 hours | Crypto moves faster, shorter review cycles |
| **🟡 CAUTION Response** | 24 hours | 4-6 hours | Crypto volatility escalates quickly |
| **🟠 URGENT Response** | 4 hours | 1-2 hours | Flash crashes can unfold in minutes |
| **🔴 CRITICAL Response** | 1 hour | 15-30 minutes | Liquidation cascades require rapid response |
| **Position Size Max (HIGH)** | 30% | 30% | **Same** - AI availability enables full risk tolerance |
| **Leverage Max (HIGH)** | 3x | 3x | **Same** - AI monitors 24/7, can respond instantly |
| **Stop-Loss Width** | -8 to -10% | -15 to -20% | Wider stops for crypto volatility, not restrictions |
| **Weekend Protocol** | N/A (markets closed) | **Normal operations** | AI Manager active 24/7, no defensiveness needed |
| **After-Hours Monitoring** | Queued for next open | **Continuous real-time** | AI never sleeps, monitors crypto overnight |
| **Volatility Threshold** | VIX-based (market-wide) | BTC 24h + funding rates + on-chain | Crypto needs custom volatility index |
| **Flash Crash Detection** | Rare (circuit breakers exist) | >10% in <1 hour triggers CRITICAL | Common in crypto, rapid AI response |
| **AI Manager Advantage** | Responds during market hours | **Responds 24/7 instantly** | No human unavailability constraints |

### **When to Use Which Response Time**

**Portfolio Tracker Auto-Detects Asset Type**:
```python
# Pseudo-code
if position.symbol in ['BTC', 'ETH', 'SOL', 'ADA', 'DOGE', etc]:
    use_crypto_SLA = True
    if is_weekend() or is_after_hours():
        escalate_urgency_by_one_level()
else:
    use_stock_SLA = True
    if market_closed():
        queue_alert_for_next_open()
```

**Mixed Portfolio Handling**:
- AI Manager monitors **both** stocks and crypto simultaneously without conflicts
- Alerts are asset-specific: Stock alerts use stock SLAs, crypto alerts use crypto SLAs
- No need to apply "stricter" SLA globally - AI can handle different response windows concurrently
- During market hours overlap (9:30 AM - 4:00 PM EST), AI manages both with appropriate urgency per asset class

---

## Conclusion

The Portfolio Tracker is a **sophisticated monitoring and recommendation engine**, not an autonomous decision-maker. It continuously analyzes portfolio health and market conditions, providing timely, data-driven recommendations to the Manager. The Manager retains full strategic control, exercising judgment that incorporates context, macro outlook, and discretionary insights that Portfolio Tracker cannot replicate.

**This delegation structure ensures**:
- ✅ **AI judgment** governs critical decisions with consistent, data-driven reasoning
- ✅ **24/7 availability** enables real-time response to both stock and crypto markets
- ✅ **Automated monitoring** (Portfolio Tracker) + **intelligent decision-making** (AI Manager)
- ✅ Clear accountability (Manager owns outcomes, Portfolio Tracker provides analysis)
- ✅ Scalability (can manage multiple asset classes, strategies, and alerts simultaneously)
- ✅ Flexibility (Manager can make contrarian decisions based on broader context)
- ✅ **No human constraints**: No fatigue, sleep, weekends, or availability gaps

**Result**: A dual-AI system combining systematic risk monitoring (Portfolio Tracker) with strategic autonomous decision-making (AI Manager)—optimized for both traditional and 24/7 crypto markets.
