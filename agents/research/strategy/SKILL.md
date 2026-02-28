---
name: Trade Strategy Research Agent
description: Continuously research trading strategies, generate testable hypotheses, and log trade ideas for validation by the Backtest Agent
---

# Trade Strategy Research Agent

## Purpose

This AI agent **continuously researches** trading strategies to:
1. **Generate testable hypotheses** from academic research and market data
2. **Log trade ideas** with structured parameters for backtest validation
3. **Identify opportunities** from market news, regime changes, and pattern detection
4. **Validate strategy logic** against theoretical foundations
5. **Feed the Backtest Agent** with well-documented, testable strategies

## Agent Operating Mode

> [!IMPORTANT]
> This agent operates **autonomously**, querying research sources, identifying patterns, and generating trade ideas without human time-based schedules.

### Query Cycle Configuration

```yaml
research_cycles:
  academic_scan:         # New papers, studies
    frequency: 24hours
    sources: [google_scholar, ssrn, arxiv_finance]
  
  pattern_detection:     # Screener-based opportunities
    frequency: 6hours
    sources: [perplexity_screener, market_data]
  
  news_integration:      # Process market_news agent signals
    frequency: on_trigger
    sources: [market_news_agent_feed]
  
  consensus_tracking:    # Monitor prediction shifts
    frequency: 12hours
    sources: [perplexity_predictions, analyst_consensus]
```

---

## Core Workflows

### Workflow 1: Continuous Hypothesis Generation

```
LOOP every {research_cycle}:
    1. Query academic sources for new strategy research
    2. Scan market screeners for pattern candidates
    3. Receive triggers from Market News Agent (NEWS-DRIVEN opportunities)
    4. For each viable pattern:
       a. Validate theoretical foundation (WHY should this work?)
       b. Check against known biases (survivorship, look-ahead, curve-fit)
       c. Assess real-world constraints (transaction costs, liquidity)
       d. Generate structured trade idea
       e. Insert into `strategies` table in `data/tradebot.db`
    5. Push ready ideas to Backtest Agent queue
```

### Workflow 2: News-Triggered Research

```
TRIGGER: Receive signal from Market News Agent

1. Parse news event category and severity
2. Identify affected asset classes and sectors
3. Query for relevant strategy research:
   - Historical precedent analysis
   - Regime change implications
   - Sector rotation patterns
4. Generate NEWS-DRIVEN trade idea if opportunity found
5. Link to news assessment ID
6. Push to `strategies` table with NEWS-DRIVEN tag
```

### Workflow 3: Strategy Validation Pipeline

```
TRIGGER: New hypothesis generated OR backtest feedback received

1. Validate theoretical foundation:
   - Behavioral finance explanation?
   - Risk factor explanation?
   - Market structure explanation?
2. Check for critical red flags:
   - Over-complexity (>5 parameters = curve-fit risk)
   - No risk discussion = incomplete
   - Cherry-picked results = bias
3. Assess implementation constraints:
   - Transaction costs impact
   - Liquidity requirements
   - Scalability limits
4. Update trade idea status accordingly
```

### Workflow 4: Crypto Pattern Research

> [!IMPORTANT]
> This workflow runs via `crypto_strategy_generator.py` on a configurable loop (default 10 min) and uses a **pluggable `PatternRegistry` system** to support N pattern detectors.

```
LOOP every {pattern_scan_cycle}:
    1. Discover all tradeable crypto on Alpaca (cached 1hr)
    2. Classify each coin: stablecoin / meme / major
    3. Exclude stablecoins (except depeg event tracking)
    4. Fetch hourly bar data for all tradeable coins
    5. Run all registered pattern detectors via PatternRegistry:
       - Each detector is filtered by coin category
       - Each detector returns a strategy idea dict or None
       - Failed detectors are isolated (logged, not fatal)
    6. Run news-driven strategy generation from CRITICAL/HIGH market_news
    7. Store unique strategies to `strategies` table
```

**Adding a new detector** requires only a decorated function:

```python
@PatternRegistry.register(
    name="My Detector",
    categories=["major", "meme"],         # which coin types
    description="Detects XYZ when ...",    # for --list-patterns output
)
def detect_my_pattern(symbol, bars, category):
    # ... compute indicators ...
    return strategy_dict_or_None
```

**Current registered detectors**: Run `py agents/research/strategy/crypto_strategy_generator.py --list-patterns` to enumerate all active detectors.

**Coin category risk parameters**:

| Category | Stop Loss | Take Profit | Max Hold | Sizing |
|----------|-----------|-------------|----------|--------|
| **major** | 3% | 8% | 48h | Standard |
| **meme** | 5% | 15% | 12h | Reduced |
| **stablecoin** | — | — | — | Excluded |

---

## Research Source Configuration

### Academic Sources (24h cycle)

| Source | Query Method | Priority Topics |
|--------|--------------|-----------------|
| **Google Scholar** | Targeted queries | Momentum, mean-reversion, factor investing |
| **SSRN** | Finance category | New working papers, quant strategies |
| **arXiv q-fin** | Quantitative finance | ML/AI trading, statistical arbitrage |

**Standard Query Templates**:
```
"momentum trading strategies" site:scholar.google.com
"mean reversion profitability" after:2023
"machine learning stock prediction" site:ssrn.com
"time series momentum factor" site:arxiv.org
```

### Market Intelligence Sources (6h cycle)

| Source | URL | Query Type |
|--------|-----|------------|
| **Perplexity Screener** | perplexity.ai/finance/screener | Pattern candidate identification |
| **Perplexity Predictions** | perplexity.ai/finance/predictions | Consensus baseline tracking |

### Reference Documentation (On-demand)

| Document | Purpose |
|----------|---------|
| **OPTIONS_STRATEGIES.md** | Options strategy structures and Greeks |
| **CRYPTO_INVESTING_GUIDE.md** | Crypto liquidation and whale tracking methods |
| **Portfolio Tracker SKILL.md** | Risk policy constraints (leverage, position sizing) |

---

## Trade Idea Schema

All trade ideas use this JSON structure:

```json
{
  "trade_idea_id": "TI-XXX",
  "timestamp": "ISO-8601",
  "name": "Descriptive Strategy Name",
  "status": "Research|Ready|Backtesting|Validated|Rejected",
  "priority": "High|Medium|Low",
  "source_type": "Academic|Pattern|NewsTriggered|Regime",
  
  "classification": {
    "type": "Momentum|MeanReversion|Volatility|Income|Arbitrage|Other",
    "market_outlook": "Bullish|Bearish|Neutral|HighVol|LowVol",
    "asset_class": "Equities|Options|Futures|Crypto",
    "time_horizon": "Intraday|Swing|Position|LongTerm"
  },
  
  "hypothesis": {
    "statement": "Clear, testable statement",
    "theoretical_basis": "WHY this should work",
    "supporting_research": ["citation1", "citation2"]
  },
  
  "strategy_logic": {
    "entry_conditions": ["condition1", "condition2"],
    "exit_conditions": {
      "profit_target": "condition",
      "stop_loss": "condition",
      "time_exit": "condition"
    },
    "position_sizing": "Risk per trade rule"
  },
  
  "expected_characteristics": {
    "win_rate_pct": 0-100,
    "avg_win_pct": 0.0,
    "avg_loss_pct": 0.0,
    "profit_factor": 0.0,
    "max_drawdown_pct": 0.0,
    "hold_time_days": 0
  },
  
  "risk_factors": ["risk1", "risk2", "risk3"],
  
  "backtest_requirements": {
    "data_needed": ["OHLCV", "options chain", "etc"],
    "date_range": "YYYY-MM-DD to YYYY-MM-DD",
    "frequency": "1min|1hour|1day",
    "success_criteria": {
      "min_sharpe": 0.0,
      "max_drawdown": 0.0,
      "min_trades": 0,
      "min_profit_factor": 0.0
    }
  },
  
  "news_link": "NA-XXX or null",
  "related_ideas": ["TI-XXX", "TI-YYY"]
}
```

---

## Strategy Categories

### Momentum Strategies

**Research Focus**: Cross-sectional momentum, time-series momentum, dual momentum

**Key Sources**:
- Jegadeesh & Titman (1993) - Original momentum anomaly
- Moskowitz et al. (2012) - Time series momentum
- Academic papers on momentum crashes and risk

**Validation Criteria**:
- Works across asset classes (equities, futures, forex)
- Survives transaction costs
- Has theoretical explanation (underreaction, herding)

### Mean Reversion Strategies

**Research Focus**: Pairs trading, statistical arbitrage, RSI-based reversals

**Key Sources**:
- Gatev et al. (2006) - Pairs trading study
- Cointegration-based research
- Market microstructure papers

**Validation Criteria**:
- Sufficient trading frequency
- Robust to regime changes
- Clear half-life estimation

### Options Strategies

**Reference**: [OPTIONS_STRATEGIES.md](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/agents/research/strategy/OPTIONS_STRATEGIES.md)

**Research Focus**: Volatility premium, theta decay, defined-risk structures

**Common Strategies**:
- Iron Condor (income in low volatility)
- Credit spreads (directional + income)
- Calendar spreads (volatility term structure)

### Crypto Strategies

**Reference**: [CRYPTO_INVESTING_GUIDE.md](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/agents/research/strategy/CRYPTO_INVESTING_GUIDE.md)

**Research Focus**: Liquidation cascades, whale tracking, funding rate arbitrage

**Data Sources**:
- CoinGlass (liquidations, funding rates, open interest)
- Whale Alert (large transaction monitoring)
- Glassnode (on-chain analytics)

**Risk Constraints**:
Must align with Portfolio Tracker risk policy:
- HIGH: 3x max leverage, 22% circuit breaker
- MODERATE: 2x max leverage, 18% circuit breaker
- LOW: 1.2x max leverage, 12% circuit breaker

---

## Integration with Other Agents

### ← Market News Agent

**Receive From Market News**:
- NEWS-DRIVEN opportunity signals
- Regime change alerts
- Sector rotation triggers
- Economic event implications

**Processing**:
```
news_signal → identify_opportunity → research_precedent → generate_hypothesis → log_trade_idea
```

### → Backtest Agent

**Push to Backtest**:
- Trade ideas with status = "Ready"
- Structured JSON with all parameters
- Clear success criteria

**Receive From Backtest**:
- Validation results (passed/failed)
- Performance metrics
- Optimization suggestions

**Feedback Loop**:
```
research → backtest → unexpected_results → additional_research → refined_hypothesis → re-backtest
```

### → Manager Agent

**Push to Manager**:
- High-priority validated strategies
- Weekly research summary
- Red flag alerts (strategy failure patterns)

---

## Quality Filters

### Pre-Logging Validation

Before logging any trade idea, verify:

```
□ Theoretical foundation exists (not just pattern-matching)
□ Transaction costs considered
□ Liquidity requirements assessed
□ Risk factors documented
□ Failure modes identified
□ Success criteria defined
□ Data requirements specified
```

### Red Flag Detection

Automatically flag ideas with:

| Red Flag | Indicator | Action |
|----------|-----------|--------|
| Curve-fitting | >5 parameters | Mark HIGH risk, require extra validation |
| No theory | No WHY explanation | Require theoretical research |
| Cherry-picked | Only best periods shown | Request full period analysis |
| Survivorship | Only winning assets analyzed | Expand universe |
| Unrealistic | >80% win rate claimed | Skeptical review |

---

## Output Destinations

### strategies table (in data/tradebot.db)
**Location**: `data/tradebot.db` → `strategies` table (ORM: `agents.common.models.Strategy`)

**Schema**: See [DATA_SCHEMAS.md](file:///C:/Users/rafae/Documents/PROJECTS/TradeBot/docs/DATA_SCHEMAS.md)

**Write Triggers**:
- New hypothesis passes pre-validation
- Status updates from backtest results
- Rejection with documented reason

### Research Knowledge Base

**Location**: Strategy documentation files in this directory

**Update Triggers**:
- New strategy category researched
- Significant academic paper found
- Pattern validated/invalidated

---

## Performance Metrics

```yaml
metrics:
  hypothesis_generation_rate:
    target: "3-5 new trade ideas per week"
    measure: "Count of ideas logged with status=Ready"
  
  backtest_pass_rate:
    target: ">30% of ideas pass backtest validation"
    measure: "Validated / Total submitted"
  
  theoretical_grounding:
    target: "100% of ideas have WHY documentation"
    measure: "Ideas with theoretical_basis populated"
  
  news_integration:
    target: "Process 100% of Market News Agent triggers"
    measure: "Triggers processed / triggers received"
  
  false_positive_rate:
    target: "<50% of backtested ideas fail"
    measure: "Rejected / Total backtested"
```

---

## Anti-Patterns to Avoid

> [!CAUTION]
> The agent must avoid these research failures:

### 1. Confirmation Bias
- **Problem**: Only seeking sources supporting the hypothesis
- **Solution**: Actively query for disconfirming evidence

### 2. Complexity Creep
- **Problem**: Adding parameters until backtest looks good
- **Solution**: Prefer simple strategies; flag >5 parameter ideas

### 3. Data Mining
- **Problem**: Testing hundreds of variations to find what worked
- **Solution**: Require theoretical basis BEFORE backtest

### 4. Survivorship Bias
- **Problem**: Only analyzing assets/strategies that survived
- **Solution**: Include failed entities in research universe

### 5. Transaction Cost Ignorance
- **Problem**: Academic strategies ignoring real trading costs
- **Solution**: Always estimate costs before logging idea

---

## Configuration

### agent_config.yaml

```yaml
strategy_research_agent:
  enabled: true
  
  cycles:
    academic_scan_hours: 24
    pattern_detection_hours: 6
    consensus_tracking_hours: 12
  
  filters:
    min_theoretical_basis: true
    max_parameters: 5
    require_risk_factors: true
    require_success_criteria: true
  
  integrations:
    receive_from_market_news: true
    push_to_backtest: true
    push_to_manager: true
  
  quality:
    require_3_sources_for_academic: true
    flag_high_win_rate_claims: true
    reject_no_theory_ideas: true
```

---

*This agent operates autonomously to generate high-quality, well-researched trade hypotheses for systematic validation.*
