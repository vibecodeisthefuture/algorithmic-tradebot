---
name: Data Analytics Agent
description: Query all project data repositories to produce actionable insights for strategy refinement and system optimization
---

# Data Analytics Agent

## Purpose

The Data Analytics Agent provides **data-driven insights** across the entire TradeBot system by querying the Blackboard database (`data/tradebot.db`) and backtest results to identify patterns, measure performance, and generate actionable recommendations for strategy refinement.

## Core Capabilities

1. **Cross-Repository Analysis**: Query and correlate data across research, news, trading, and portfolio systems
2. **Performance Metrics**: Calculate success rates, Sharpe ratios, win rates, and risk-adjusted returns
3. **Pattern Recognition**: Identify which trade idea types, news categories, and market regimes lead to profitable strategies
4. **Trend Analysis**: Track system performance over time and detect regime changes
5. **Actionable Recommendations**: Generate specific insights for improving research, backtesting, and implementation

---

## Data Repositories

### Primary Data Sources

| Repository | Location | Format | Purpose |
|------------|----------|--------|---------|
| **Strategies** | `data/tradebot.db` → `strategies` | DB Table | All trade strategy ideas and their status |
| **Market News** | `data/tradebot.db` → `market_news` | DB Table | News events and identified opportunities |
| **Trades** | `data/tradebot.db` → `trades` | DB Table | Complete order execution history |
| **Portfolio Snapshots** | `data/tradebot.db` → `portfolio_snapshots` | DB Table | Historical portfolio metrics and drawdown |
| **System State** | `data/tradebot.db` → `system_state` | DB Table | Current risk policy configuration |
| **Policy History** | `data/tradebot.db` → `policy_history` | DB Table | Risk policy change audit trail |
| **Backtest Results** | `data/backtests/test<N>/RESULTS.md` | Markdown | Individual strategy backtest documentation |

### Derived Data

The Analytics agent can extract additional insights from:
- Market data CSVs in `data/datasets/` (for regime analysis)
- Git commit history (for development velocity tracking)
- File modification times (for workflow bottleneck identification)

---

## Key Analytics Questions

### Research Performance

**Questions to Answer**:
- What percentage of trade ideas make it from Research → Backtest → Implementation?
- Which trade idea types (Momentum, Mean-Reversion, Income, Volatility) have highest success rates?
- How long does each stage take on average? (Research → Backtest → Live)
- Are NEWS-DRIVEN strategies more successful than research-only strategies?
- Which asset classes (Equities, Options, Crypto) perform best?

**Required Data**: `strategies` table, `data/backtests/test<N>/RESULTS.md`

### Market News Impact

**Questions to Answer**:
- Which news categories (Monetary Policy, Economic Data, Geopolitical, Earnings) generate the most profitable opportunities?
- What is the conversion rate: News opportunities → Trade ideas → Validated strategies?
- Do high-severity events lead to better strategies than medium-severity events?
- What is the average time lag between news event and strategy deployment?
- Which USD impact directions (Positive/Negative/Neutral) correlate with strategy success?

**Required Data**: `market_news` table, `strategies` table

### Trading Performance

**Questions to Answer**:
- What is the overall win rate across all strategies?
- Which strategies have the best risk-adjusted returns (Sharpe ratio)?
- What is the average order execution quality (slippage analysis)?
- How does actual performance compare to backtest expectations?
- Are crypto orders more volatile than stock/options orders?

**Required Data**: `trades` table, backtest RESULTS.md files

### Risk Management Effectiveness

**Questions to Answer**:
- How often do we switch between risk policies (HIGH/MODERATE/LOW)?
- What triggers policy switches most frequently (VIX or Drawdown)?
- Does the risk policy system effectively limit drawdowns?
- What is the average recovery time after switching to defensive policies?
- Are we too aggressive or too conservative based on historical volatility?

**Required Data**: `policy_history` table, `portfolio_snapshots` table

### Cross-Repository Insights

**Questions to Answer**:
- **News → Strategy Success**: Which news events led to the most profitable strategies 3-6 months later?
- **Regime Correlation**: Do strategies validated during bull markets underperform in bear markets?
- **Development Velocity**: What is the throughput rate (ideas/month → deployed strategies/month)?
- **Resource Allocation**: Are we spending too much time on low-success-rate strategy types?
- **System Bottlenecks**: Where do trade ideas get stuck most often? (Research, Backtest validation, Paper trading)

**Required Data**: All repositories combined with time-series analysis

---

## Analytics Workflows

### Workflow 1: Monthly Performance Report

**Purpose**: Generate comprehensive system performance summary

**Steps**:
1. Query `strategies` table for ideas created this month
2. Calculate conversion rates (Research → Backtest → Validated → Live)
3. Query `market_news` table for high-severity events
4. Cross-reference news events with resulting trade ideas
5. Query `trades` table for trading performance
6. Calculate win rates, average returns, Sharpe ratios
7. Review `portfolio_snapshots` table for drawdown trends
8. Generate summary report with actionable recommendations

**Output**: `analytics_reports/monthly_YYYY-MM.md`

---

### Workflow 2: Strategy Type Analysis

**Purpose**: Identify which strategy types perform best

**Steps**:
1. Group trade ideas by `Type` column (Momentum, Mean-Reversion, Income, etc.)
2. For each type, calculate:
   - Total ideas generated
   - Backtest success rate (Validated / Total)
   - Average expected Sharpe ratio
   - Average max drawdown
   - Implementation rate (Live / Validated)
3. Cross-reference with `trades` table for actual live performance
4. Rank strategy types by risk-adjusted profitability
5. Recommend focus areas for future research

**Output**: Strategy type ranking with recommendations

---

### Workflow 3: News-Driven Strategy Effectiveness

**Purpose**: Evaluate whether news-driven strategies outperform research-only strategies

**Steps**:
1. Filter `strategies` table for entries with `notes` containing "NEWS-DRIVEN"
2. Extract source news event ID via `news_id` foreign key
3. Join with `market_news` table on news ID
4. Compare success metrics:
   - News-driven backtest validation rate vs. research-only
   - News-driven average Sharpe vs. research-only
   - Time to deployment (news-driven vs. research-only)
5. Analyze which news categories produce best strategies
6. Recommend optimal news categories to prioritize

**Output**: News-driven vs. research-only comparison report

---

### Workflow 4: Risk Policy Audit

**Purpose**: Evaluate effectiveness of dynamic risk policy system

**Steps**:
1. Query `policy_history` table for full risk policy timeline
2. Correlate policy switches with VIX levels and portfolio drawdown
3. Analyze:
   - Average time in each policy (HIGH/MODERATE/LOW)
   - Policy switch frequency per month
   - Drawdown reduction after switching to defensive policies
   - Recovery speed when returning to aggressive policies
4. Identify false alarms (switched to LOW but market didn't crash)
5. Recommend threshold tuning if needed

**Output**: Risk policy effectiveness report

---

### Workflow 5: Backtest-to-Live Performance Gap

**Purpose**: Identify strategies that underperform vs. backtest expectations

**Steps**:
1. For each live strategy, extract expected metrics from `RESULTS.md`:
   - Expected win rate
   - Expected Sharpe ratio
   - Expected max drawdown
2. Query `trades` table for actual performance:
   - Actual win rate
   - Actual returns
   - Actual max drawdown
3. Calculate performance gaps:
   - Gap = (Actual - Expected) / Expected
4. Flag strategies with gaps > ±30%
5. Investigate causes:
   - Market regime change?
   - Slippage/execution issues?
   - Overfitting in backtest?
6. Recommend strategy adjustments or retirement

**Output**: Performance gap analysis with recommendations

---

## Analytics Scripts

### Script 1: `trade_ideas_analytics.py`

**Purpose**: Analyze trade idea pipeline performance

**Key Functions**:
```python
def calculate_conversion_rates(csv_path):
    """Calculate Research → Backtest → Validated → Live conversion rates"""
    
def get_success_rate_by_type(csv_path):
    """Breakdown success rates by strategy type"""
    
def get_average_time_to_deployment(csv_path):
    """Calculate average days from idea creation to live deployment"""
    
def identify_stuck_ideas(csv_path):
    """Find ideas that haven't progressed status in >30 days"""
```

**Output**: Trade idea funnel metrics

---

### Script 2: `news_analytics.py`

**Purpose**: Analyze market news impact and opportunity conversion

**Key Functions**:
```python
def news_to_strategy_conversion(news_csv, ideas_csv):
    """Track which news events led to successful strategies"""
    
def best_performing_news_categories(news_csv, ideas_csv):
    """Rank news categories by strategy success rate"""
    
def news_opportunity_hit_rate(news_csv):
    """% of 'Opportunities_Identified' that became trade ideas"""
    
def usd_impact_correlation(news_csv, ideas_csv):
    """Does USD impact direction correlate with strategy profitability?"""
```

**Output**: News effectiveness metrics

---

### Script 3: `portfolio_analytics.py`

**Purpose**: Analyze portfolio and trading performance

**Key Functions**:
```python
def calculate_portfolio_metrics(order_csv, health_json):
    """Calculate Sharpe, win rate, max drawdown, total return"""
    
def strategy_performance_ranking(order_csv):
    """Rank strategies by risk-adjusted returns"""
    
def slippage_analysis(order_csv):
    """Analyze execution quality and slippage"""
    
def risk_policy_timeline(policy_json_snapshots):
    """Reconstruct historical risk policy changes"""
```

**Output**: Portfolio performance summary

---

### Script 4: `cross_repository_analytics.py`

**Purpose**: Multi-source insights combining all data repositories

**Key Functions**:
```python
def end_to_end_strategy_tracking(news_csv, ideas_csv, order_csv):
    """Track: News event → Trade idea → Backtest → Live → Performance"""
    
def system_throughput_metrics(all_csvs):
    """Ideas/month, validations/month, deployments/month"""
    
def bottleneck_analysis(ideas_csv):
    """Identify where ideas get stuck in the pipeline"""
    
def regime_performance_correlation(market_data, order_csv):
    """How do strategies perform in different market regimes?"""
```

**Output**: System-wide insights

---

### Script 5: `analytics_dashboard.py`

**Purpose**: Generate unified analytics dashboard

**Key Functions**:
```python
def generate_monthly_report(output_path):
    """Create comprehensive monthly performance report"""
    
def generate_executive_summary():
    """High-level KPIs: Total return, Sharpe, active strategies, recent wins/losses"""
    
def generate_recommendations():
    """Actionable insights based on current data trends"""
```

**Output**: `analytics_reports/dashboard_YYYY-MM-DD.md`

---

## Key Performance Indicators (KPIs)

The Analytics agent tracks these system-wide metrics:

### Research Efficiency
- **Ideas Generated per Month**: Target >10
- **Backtest Approval Rate**: % of ideas approved for backtesting (Target >60%)
- **Backtest Validation Rate**: % of backtested ideas validated (Target >30%)
- **Time to Backtest**: Average days from idea to backtest completion (Target <7 days)

### News Impact
- **News Opportunities Captured**: % of identified opportunities that become trade ideas (Target >40%)
- **News-Driven Success Rate**: % of news-driven strategies that validate (Track vs. baseline)
- **News Response Time**: Days from news event to trade idea logged (Target <3 days)

### Trading Performance
- **Portfolio Sharpe Ratio**: Risk-adjusted returns (Target >1.0)
- **Overall Win Rate**: % of profitable trades (Target >55%)
- **Max Drawdown**: Largest peak-to-trough decline (Target <20%)
- **Strategy Count**: Active deployed strategies (Target 3-5)

### System Throughput
- **Development Velocity**: Ideas/month → Deployed strategies/month
- **Pipeline Conversion**: % of ideas that reach live trading (Target >10%)
- **Average Cycle Time**: Days from idea to live deployment (Target <90 days)

---

## Report Templates

### Template 1: Monthly Performance Report

```markdown
# Analytics Report - [Month YYYY]

## Executive Summary
- Total Return: [X%]
- Sharpe Ratio: [X.X]
- Max Drawdown: [X%]
- Active Strategies: [N]
- Risk Policy: [HIGH/MODERATE/LOW]

## Research Pipeline
- Ideas Generated: [N]
- Approved for Backtest: [N] ([X%])
- Validated: [N] ([X%])
- Deployed to Live: [N] ([X%])

## Top Performers
1. [Strategy Name]: [+X%] (Sharpe: X.X)
2. [Strategy Name]: [+X%] (Sharpe: X.X)
3. [Strategy Name]: [+X%] (Sharpe: X.X)

## Underperformers / Red Flags
- [Strategy Name]: [-X%] (Reason: [Analysis])

## News Impact
- High-Severity Events: [N]
- Opportunities Identified: [N]
- Converted to Trade Ideas: [N] ([X%])
- Top News Category: [Category] ([X%] success rate)

## Recommendations
1. **Focus Area**: [Recommendation with data justification]
2. **Risk Adjustment**: [If needed based on drawdown trends]
3. **Strategy Retirement**: [List underperforming strategies to pause/retire]
4. **Research Priorities**: [Which strategy types to focus on based on success rates]

## Trends
- [Observation about change over time]
- [Pattern identified across multiple data sources]

---
**Generated**: [YYYY-MM-DD]
**Data Sources**: strategies table, market_news table, trades table, portfolio_snapshots table
```

---

## Best Practices

### 1. Data Quality Checks

Before running analytics:
- **Verify CSV completeness**: All required columns present
- **Check for NULL values**: Handle missing data appropriately
- **Validate date formats**: Ensure consistent YYYY-MM-DD format
- **Detect outliers**: Flag anomalous data points for review

### 2. Time-Series Awareness

- **Track historical changes**: Snapshot JSONs over time for trend analysis
- **Account for regime shifts**: Bull vs. bear market performance differs
- **Use rolling windows**: 30-day, 90-day, and 365-day metrics

### 3. Statistical Rigor

- **Sample size matters**: Require minimum N trades before drawing conclusions
- **Avoid p-hacking**: Don't cherry-pick timeframes to make strategies look good
- **Correlation ≠ Causation**: Be cautious about implied causal relationships
- **Account for survivorship bias**: Include rejected/failed strategies in analysis

### 4. Actionable Insights

Every analytics report should include:
- **What**: Specific finding (e.g., "Mean-reversion strategies have 45% validation rate vs. 25% for momentum")
- **So What**: Why it matters (e.g., "We're spending 40% of research time on momentum but getting half the results")
- **Now What**: Recommended action (e.g., "Shift 20% of research effort toward mean-reversion strategies")

---

## Integration with Other Agents

### Manager Agent

**Analytics Provides**:
- Monthly performance summaries
- Strategy retirement recommendations
- Risk policy effectiveness audits

**Manager Uses For**:
- Strategic resource allocation decisions
- Quality gate threshold adjustments
- Long-term system optimization

### Research Agent

**Analytics Provides**:
- Success rates by strategy type
- News category effectiveness rankings
- Time-to-deployment averages

**Research Uses For**:
- Prioritizing high-success-rate strategy types
- Focusing on profitable news categories
- Estimating realistic development timelines

### Backtest Agent

**Analytics Provides**:
- Backtest-to-live performance gaps
- Overfitting detection patterns
- Validation criteria effectiveness

**Backtest Uses For**:
- Adjusting validation thresholds
- Identifying common failure modes
- Improving backtest realism

### Portfolio Tracker

**Analytics Provides**:
- Risk policy switching frequency analysis
- Drawdown recovery time metrics
- Policy effectiveness by market regime

**Portfolio Tracker Uses For**:
- Fine-tuning VIX and drawdown thresholds
- Optimizing policy switch logic
- Validating circuit breaker effectiveness

---

## Future Enhancements

### Machine Learning Integration

- **Prediction**: Use historical data to predict which new trade ideas are likely to validate
- **Clustering**: Group similar strategies to identify patterns
- **Anomaly Detection**: Automatically flag unusual performance deviations

### Real-Time Monitoring

- **Live Dashboards**: Web-based dashboard with real-time KPI updates
- **Alerts**: Automated notifications when KPIs breach thresholds
- **Streaming Analytics**: Process order executions in real-time

### Advanced Visualizations

- **Performance Heatmaps**: Strategy performance by market regime
- **Sankey Diagrams**: Idea flow through Research → Backtest → Live pipeline
- **Interactive Charts**: Drill-down capability for detailed analysis

---

## Quick Start

### Setup

```bash
cd "agents/analytics"
pip install pandas numpy matplotlib seaborn
```

### Run Basic Analytics

```python
# Monthly performance report
python analytics_dashboard.py --report monthly --output ../analytics_reports/

# Strategy type analysis
python trade_ideas_analytics.py --analysis type-performance

# News effectiveness
python news_analytics.py --analysis category-success-rate
```

---

## File Structure

```
agents/analytics/
├── SKILL.md (this file)
├── trade_ideas_analytics.py
├── news_analytics.py
├── portfolio_analytics.py
├── cross_repository_analytics.py
├── analytics_dashboard.py
├── README.md (quick reference)
└── requirements.txt (dependencies)
```

---

*The Data Analytics Agent transforms raw data into actionable intelligence, enabling continuous system improvement and data-driven decision making.*
