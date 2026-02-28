# AI Intelligence Source Configuration

## Overview

This document configures Perplexity and Grok AI sources for the Market News Agent's continuous monitoring operations.

---

## Source Configuration

### Perplexity Finance Ecosystem

| Source | URL | Query Interval | Data Type |
|--------|-----|----------------|-----------|
| **Perplexity Finance** | perplexity.ai/finance | 15 min | News aggregation, AI synthesis |
| **Perplexity Earnings** | perplexity.ai/finance/earnings | 1 hour | Earnings calendar, results |
| **Perplexity Predictions** | perplexity.ai/finance/predictions | 1 hour | Analyst consensus, forecasts |
| **Perplexity Screener** | perplexity.ai/finance/screener | On-demand | Stock screening, filtering |

### Grok Social Intelligence

| Source | URL | Query Interval | Data Type |
|--------|-----|----------------|-----------|
| **Grok** | grok.com | 5 min | X.com sentiment, trending, breaking |

---

## Perplexity Finance

**Endpoint**: https://www.perplexity.ai/finance

### Query Types

**News Aggregation** (Standard Interval: 15 min)
```
Query: "What were the major market developments in the last hour?"
Query: "Summarize today's Fed meeting decision and market reaction"
Query: "What are analysts saying about [TICKER] earnings?"
Output: market_news table
```

**Breaking News Synthesis** (Triggered by alerts)
```
Query: "What is happening with [TOPIC] right now?"
Query: "Summarize the latest on [GEOPOLITICAL EVENT]"
Verification: Cross-check with Reuters/Bloomberg within 5 min
```

### Reliability Level: MODERATE

- **Strengths**: Fast synthesis, multi-source aggregation, good for overview
- **Weaknesses**: May miss nuance, not real-time during fast-moving events
- **Always Verify**: Critical claims via primary sources (Fed statements, filings)

---

## Perplexity Screener

**Endpoint**: https://www.perplexity.ai/finance/screener

### Query Types

**Strategy Candidate Search** (Triggered by Research Agent)
```
Query: "Show stocks with P/E < 15, positive momentum, market cap > $5B"
Query: "Find crypto with increasing volume and RSI < 40"
Output: Candidate list for research validation
```

**Anomaly Detection** (Daily scan)
```
Query: "Stocks near 52-week lows with improving fundamentals"
Query: "High short interest stocks with positive earnings surprises"
Output: Opportunity flags to Research Agent
```

### Processing Rules

1. Screener results are starting points, not trade signals
2. Each candidate requires fundamental validation
3. Check liquidity (can we actually trade?)
4. Verify patterns make logical sense

---

## Perplexity Earnings

**Endpoint**: https://www.perplexity.ai/finance/earnings

### Query Types

**Calendar Monitoring** (Hourly)
```
Query: "What earnings are scheduled for the next 24 hours?"
Query: "Which bellwether companies report this week?"
Output: Pre-event alerts to Manager Agent
```

**Post-Earnings Analysis** (Triggered by earnings release)
```
Query: "What were [TICKER] earnings results vs expectations?"
Query: "How is the market reacting to [TICKER] guidance?"
Output: market_news table with impact assessment
```

### Bellwether Companies

Priority monitoring for market-moving earnings:
- **Tech**: AAPL, MSFT, GOOGL, AMZN, NVDA, META
- **Financials**: JPM, BAC, GS
- **Industrials**: CAT, UPS, FDX
- **Retail**: WMT, TGT, COST

---

## Perplexity Predictions

**Endpoint**: https://www.perplexity.ai/finance/predictions

### Query Types

**Consensus Baseline** (Hourly)
```
Query: "What is the consensus Fed rate expectation?"
Query: "What are analyst predictions for [TICKER] earnings?"
Query: "What is the GDP growth consensus for next quarter?"
Output: Baseline expectations for strategy validation
```

**Prediction Divergence Detection**
```
Indicator: Wide forecast range = high uncertainty
Indicator: Narrow range = high confidence (crowded)
Indicator: Shifting predictions = regime change signal
Output: Divergence flags to Manager Agent
```

### Integration Logic

```
If (agent_view == consensus_view):
    position_size_modifier = 0.5  # Crowded trade risk
    
If (agent_view != consensus_view):
    validate_reasoning()  # Why do we differ?
    if reasoning_validated:
        position_size_modifier = 1.0
        
If (consensus_extreme):  # >90% agreement
    contrarian_signal = True
    alert_manager("Extreme consensus detected")
```

---

## Grok - Social Intelligence

**Endpoint**: https://grok.com/

### Query Types

**Trending Detection** (5 min interval)
```
Query: "What are the top trending financial topics on X right now?"
Query: "Is there breaking financial news on X in the last hour?"
Query: "Any unusual spikes in discussion about [TICKER]?"
Output: Early warning signals requiring verification
```

**Sentiment Analysis** (15 min interval)
```
Query: "What is the retail sentiment on $[TICKER]?"
Query: "How is X reacting to the Fed announcement?"
Query: "Is crypto sentiment bullish or bearish today?"
Output: Sentiment metrics for contrarian analysis
```

**Narrative Tracking** (Every 6 hours)
```
Query: "What market narratives are trending on FinTwit this week?"
Query: "Is [NARRATIVE] gaining or losing momentum?"
Query: "Which themes are approaching saturation?"
Output: Narrative lifecycle stage for strategy context
```

### Reliability Level: LOW (Early Warning Only)

- **Strengths**: 10-30 min speed advantage, retail sentiment, crypto/meme expertise
- **Weaknesses**: Misinformation, bots, pump schemes, echo chambers
- **CRITICAL**: Never trade on Grok alone. Always verify via Tier 1 sources.

### Verification Protocol

```
grok_signal_detected:
    set timer: 10 min
    query reuters: "[topic]"
    query bloomberg: "[topic]"
    
    if (verified_by_tier1):
        process_as_confirmed_news()
        log severity: based_on_impact
        
    if (not verified_after 30 min):
        log as: "unverified_rumor"
        continue_monitoring: True
        do_not_act: True
```

### Signal Quality Assessment

**Trust (After Verification)**:
- Early breaking news (verify immediately)
- Retail positioning insights (contrarian signals)
- Crypto developments (social-driven assets)
- Narrative strength indicators

**Never Trust Alone**:
- Specific price predictions
- Single-source rumors
- Pump group activity
- Extreme sentiment without catalyst

---

## Source Priority Matrix

| Scenario | Primary Source | Secondary | Verification Required |
|----------|---------------|-----------|----------------------|
| Breaking News | Grok → Reuters | Bloomberg | 3 sources for Critical |
| Overnight Recap | Perplexity Finance | FT, WSJ | Low (synthesis) |
| Earnings | Perplexity Earnings | Company filings | Medium (data) |
| Consensus | Perplexity Predictions | Analyst research | Low (baseline) |
| Screening | Perplexity Screener | Fundamentals check | High (validation) |
| Sentiment | Grok | Compare to price action | Always verify |

---

## Error Handling

### Source Unavailable

```
if source_unavailable:
    log_error(source, timestamp)
    fallback_to_tier_backup:
        perplexity → traditional_sources
        grok → monitor_via_alerts
    alert_if_outage > 1_hour
```

### Conflicting Information

```
if sources_conflict:
    priority_order: [government_data, company_filings, reuters, bloomberg, perplexity, grok]
    log_discrepancy(sources, claims)
    flag_for_manual_review_if_high_impact
    default_to_highest_reliability_source
```

### Unverified Breaking News

```
if critical_and_unverified:
    set urgency: HIGH
    monitor_intensively: 5_min_intervals
    prepare_response_scenarios: [confirmed_bullish, confirmed_bearish, debunked]
    do_not_execute_until_verified
```

---

## Performance Tracking

Track source effectiveness:

```yaml
metrics_to_track:
  - speed_advantage: "Time Grok detected vs confirmed news"
  - verification_rate: "% of Grok signals confirmed"
  - synthesis_accuracy: "Perplexity summary correctness"
  - prediction_accuracy: "Consensus vs actual outcomes"
  - screener_pass_rate: "% of screened candidates passing validation"
```

---

*This configuration enables continuous AI-powered intelligence gathering with appropriate verification protocols and reliability weighting.*
