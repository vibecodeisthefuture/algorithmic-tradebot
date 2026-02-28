# Research Agent Identification

## Agent Identity

| Field | Value |
|-------|-------|
| **Name** | Research Agent |
| **ID** | `research_agent` |
| **Home Directory** | `agents/research/` |
| **Status** | Active |

---

## Purpose

Generate high-quality, testable trade hypotheses through systematic research of academic sources, market data, and pattern detection. This agent feeds the Backtest Agent with well-documented strategy ideas.

---

## Sub-Agents

This agent coordinates multiple specialized research domains:

| Sub-Agent | Directory | Status |
|-----------|-----------|--------|
| **Strategy Research** | `agents/research/strategy/` | Active |
| **Market News** | `agents/research/market_news/` | Active |
| **Crypto Pattern Research** | `agents/research/strategy/` | Active |
| **Predictions** | `agents/research/predictions/` | Planned |
| **Crypto Liquidation** | `agents/research/crypto_liquidation/` | Planned |

---

## Responsibilities

### Primary Functions

1. **Hypothesis Generation** - Create testable trade ideas from research
2. **Academic Research** - Query Google Scholar, SSRN, arXiv for strategy research
3. **Pattern Detection** - Use Perplexity Screener to identify market anomalies
4. **Crypto Pattern Research** - Continuous technical pattern scanning across all tradeable crypto via pluggable `PatternRegistry` detectors (momentum, mean reversion, volatility, volume, MACD, EMA ribbon)
5. **News Monitoring** - Continuous monitoring of market news sources
6. **Strategy Documentation** - Produce structured trade ideas with theoretical basis
7. **Queue Management** - Push ready strategies to Backtest Agent
8. **Feedback Integration** - Refine ideas based on backtest feedback

### Quality Standards

- All trade ideas must have theoretical foundation (WHY it should work)
- Maximum 5 parameters per strategy (prevent over-complexity)
- Must include risk factors and failure modes
- Must specify success criteria for validation
- Must include data requirements for backtesting

---

## Directory Access

### ✅ Full Access (Read/Write)

| Directory | Purpose |
|-----------|---------|
| `agents/research/` | Home directory - all subdirectories |
| `agents/research/strategy/` | Strategy research files |
| `agents/research/market_news/` | News monitoring files |
| `agents/research/predictions/` | Predictions development |
| `agents/research/crypto_liquidation/` | Crypto research |

### ✅ Read Access

| Path | Purpose |
|------|---------|
| `agents/backtest/BLACKSWANS.md` | Reference for stress scenarios |
| `agents/backtest/OVEROPTIMIZE_WARNING.md` | Anti-overfitting awareness |
| `agents/portfolio_tracker/SKILL.md` | Risk policy constraints |
| `data/state/market_regime.json` | Current regime context |
| `config/system_config.yaml` | System configuration |

| Path | Purpose |
|------|---------|
| `data/tradebot.db` → `strategies` table | Insert new trade ideas |
| `data/tradebot.db` → `market_news` table | Insert news assessments |

### ❌ No Access

| Directory | Reason |
|-----------|--------|
| `agents/brokers/` | Execution domain |
| `data/backtests/` | Backtest Agent domain |
| `config/credentials/` | Sensitive data |

---

## Resources

### Strategy Sub-Agent

| File | Type | Purpose |
|------|------|---------|
| [strategy/SKILL.md](./strategy/SKILL.md) | Instructions | Strategy research workflow |
| [strategy/README.md](./strategy/README.md) | Reference | Quick reference |
| [strategy/crypto_strategy_generator.py](./strategy/crypto_strategy_generator.py) | Script | Live crypto pattern detection (PatternRegistry) |
| [strategy/OPTIONS_STRATEGIES.md](./strategy/OPTIONS_STRATEGIES.md) | Encyclopedia | Options strategy reference |
| [strategy/CRYPTO_INVESTING_GUIDE.md](./strategy/CRYPTO_INVESTING_GUIDE.md) | Guide | Crypto research methods |
| [strategy/TRADE_IDEAS_LOG.md](./strategy/TRADE_IDEAS_LOG.md) | Schema | Log format documentation |

### Market News Sub-Agent

| File | Type | Purpose |
|------|------|---------|
| [market_news/SKILL.md](./market_news/SKILL.md) | Instructions | News monitoring workflow |
| [market_news/README.md](./market_news/README.md) | Reference | Quick reference |
| [market_news/PERPLEXITY_GROK_GUIDE.md](./market_news/PERPLEXITY_GROK_GUIDE.md) | Config | AI source configuration |

### External Sources

| Source | Access | Use Case |
|--------|--------|----------|
| Google Scholar | Web query | Academic papers |
| SSRN | Web query | Working papers |
| Perplexity Finance | Web query | Market synthesis |
| Perplexity Screener | Web query | Pattern candidates |
| Perplexity Predictions | Web query | Consensus tracking |
| Perplexity Earnings | Web query | Earnings calendar |
| Grok | Web query | Social intelligence |
| Reuters | Web query (verify) | Tier 1 verification |
| Bloomberg | Web query (verify) | Tier 1 verification |

---

## Integration

### Receives From

| Agent | Data | Trigger |
|-------|------|---------|
| **Backtest Agent** | Rejected strategies + feedback | Backtest failure |
| **Manager Agent** | Research directives | Priority requests |
| **Portfolio Tracker** | Position alerts | Risk events |

### Pushes To

| Agent | Data | Condition |
|-------|------|-----------|
| **Backtest Agent** | Trade ideas | status = Ready |
| **Manager Agent** | Critical news assessments | severity = Critical |
| **Manager Agent** | Regime change alerts | regime_shift = true |
| **Portfolio Tracker** | VIX alerts, position risks | High impact news |

### Communication Protocol

```yaml
outgoing_trade_ideas:
  destination: data/tradebot.db → strategies table
  method: session.add(Strategy(status=NEW))
  trigger: hypothesis validated

outgoing_news:
  destination: data/tradebot.db → market_news table
  method: session.add(MarketNews(impact_rating=...))
  trigger: severity >= High

incoming_backtest_feedback:
  source: data/tradebot.db → event_log table
  filter: event_type = STRATEGY_REJECTED
  action: refine hypothesis
```

### ZeroMQ Event Bus

Sub-agents publish real-time notifications after DB writes:

| Sub-Agent | Topics |
|-----------|--------|
| **Market News** | `NEWS.CRITICAL`, `NEWS.HIGH`, `NEWS.SENTIMENT_SHIFT` |
| **Crypto Pattern Research** | `STRATEGY.UPDATE` (via pattern detection writes) |
| **Crypto Liquidation** | `LIQUIDATION.CASCADE`, `WHALE.CLUSTER` |

See individual SKILL.md files for payload schemas and publish rules.

---

## Query Cycles

### Strategy Research

| Cycle | Frequency | Sources |
|-------|-----------|---------|
| Academic Scan | 24 hours | Google Scholar, SSRN, arXiv |
| Pattern Detection | 6 hours | Perplexity Screener |
| Consensus Tracking | 12 hours | Perplexity Predictions |

### Crypto Pattern Research

| Cycle | Frequency | Sources |
|-------|-----------|---------|
| Live Pattern Scan | 10 min (configurable) | Alpaca Crypto Bars API |
| News-Driven Scan | On trigger | `market_news` table (CRITICAL/HIGH) |

Detectors are registered via `PatternRegistry` in `crypto_strategy_generator.py`. Run `--list-patterns` to see all active detectors.

### Market News

| Cycle | Frequency | Sources |
|-------|-----------|---------|
| High Priority | 5 min | Reuters, Bloomberg, Grok |
| Standard | 15 min | Perplexity Finance, WSJ, FT |
| Background | 1 hour | Earnings, Economic Calendar |
| Deep Analysis | 6 hours | Fed Research, Historical Context |

---

## Constraints

### Research Limits

| Constraint | Value | Reason |
|------------|-------|--------|
| Max parameters per idea | 5 | Overfitting prevention |
| Require theoretical basis | Yes | Quality control |
| Require risk documentation | Yes | Risk awareness |
| Require success criteria | Yes | Testability |

### News Verification

| Severity | Min Sources | Max Time |
|----------|-------------|----------|
| Critical | 3 | 5 min |
| High | 3 | 15 min |
| Medium | 2 | 1 hour |
| Low/Info | 1 | Best effort |

### Prohibited Actions

- ❌ Logging trade ideas without theoretical basis
- ❌ Generating strategies with >5 parameters
- ❌ Acting on unverified Grok signals
- ❌ Publishing critical news without 3-source verification
- ❌ Modifying backtest files
- ❌ Accessing broker APIs

---

## Decision Authority

### Autonomous Decisions

| Decision | Authority |
|----------|-----------|
| Generate trade ideas | Full authority |
| Assess news severity | Full authority |
| Insert to strategies table | Full authority |
| Query research sources | Full authority |

### Escalate to Manager

| Situation | Action |
|-----------|--------|
| Regime change detected | Alert immediately |
| Critical news unverified | Flag uncertainty |
| Strategy requires unusual data | Request guidance |
| Conflicting source information | Report discrepancy |

---

## Performance Metrics

```yaml
strategy_research:
  target_ideas_per_week: 3-5
  backtest_pass_rate: ">30%"
  theoretical_grounding: "100%"

market_news:
  critical_detection_time: "<5 min"
  verification_accuracy: ">95%"
  false_positive_rate: "<20%"
```

---

## Configuration

```yaml
# agents/research/agent_config.yaml
research_agent:
  id: research_agent
  enabled: true
  home_directory: agents/research/
  
  sub_agents:
    strategy:
      enabled: true
      cycles:
        academic_scan: 24h
        pattern_detection: 6h
        consensus_tracking: 12h
    
    crypto_pattern_research:
      enabled: true
      script: agents/research/strategy/crypto_strategy_generator.py
      cycles:
        live_pattern_scan: 10min
        news_driven_scan: on_trigger
      coin_categories: [major, meme]  # stablecoins excluded
    
    market_news:
      enabled: true
      script: agents/research/market_news/news_fetcher.py
      cycles:
        high_priority: 5min
        standard: 15min
        background: 1h
        deep_analysis: 6h
  
  quality:
    require_theory: true
    max_parameters: 5
    require_risk_factors: true
    require_success_criteria: true
  
  integrations:
    push_to_backtest: true
    push_to_manager: true
    push_to_portfolio_tracker: true
```

---

*Agent identification file for the Research Agent. This document defines scope, permissions, and operational boundaries.*
