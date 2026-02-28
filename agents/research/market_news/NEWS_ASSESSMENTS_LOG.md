# Market News Assessments Log

> [!IMPORTANT]
> **News assessments are now tracked in the `market_news` database table:** `data/tradebot.db`

This document explains the database-backed news assessment tracking system. The database format enables full automation, programmatic analysis, and seamless integration with the Research and Backtest agents.

---

## Database Schema

The `market_news` table uses the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| **ID** | Unique identifier (NA-001, NA-002, etc.) | NA-001 |
| **Date** | Event date (YYYY-MM-DD) | 2024-03-20 |
| **Timestamp** | Assessment creation time (ISO format) | 2024-03-20T17:30:00 |
| **Event_Name** | Brief event description | Fed Rate Decision March 2024 |
| **Category** | Event category | Monetary Policy, Earnings, Geopolitical, Economic Data |
| **Severity** | Event severity | Critical, High, Medium, Low |
| **USD_Impact** | Direction of USD impact | Positive, Negative, Neutral |
| **Market_Reaction_SPY** | SPY percentage change | +0.9% |
| **Market_Reaction_VIX** | VIX change with levels | -8.3% (18.5→17.0) |
| **Market_Reaction_DXY** | USD Index change with levels | -0.4% (103.2→102.8) |
| **Strategy_Impact_Summary** | Brief summary of position impacts | Positive for iron condors, took profits on TLT |
| **Opportunities_Identified** | Trade ideas generated from event | Long Tech via QQQ diagonal, Short USD/JPY |
| **Action_Taken** | Immediate actions executed | Took 50% profit on TLT, widened strikes |
| **Review_Date** | When to reassess (YYYY-MM-DD) | 2024-04-10 |
| **Follow_Up_Required** | Monitoring tasks | Monitor CPI April 10, watch 10Y yield at 4.0% |
| **Confidence_Level** | Assessment confidence | High, Medium, Low |
| **Data_Sources** | Primary sources used | Fed Statement, Bloomberg, WSJ |
| **Notes** | Additional context | Brief observations or tags |

---

## How to Add a News Assessment

### Method 1: SQLAlchemy Entry (Recommended for Automation)

```python
from agents.common.database import get_db_session
from agents.common.models import MarketNews
from datetime import datetime, timezone

def log_news_assessment(assessment_data):
    with get_db_session() as session:
        news = MarketNews(**assessment_data)
        session.add(news)

# Example usage
new_assessment = {
    'ID': 'NA-002',
    'Date': '2024-04-10',
    'Timestamp': datetime.now().isoformat(),
    'Event_Name': 'March CPI Report',
    'Category': 'Economic Data',
    'Severity': 'High',
    'USD_Impact': 'Positive',
    'Market_Reaction_SPY': '-0.5%',
    'Market_Reaction_VIX': '+4.2% (17.0→17.7)',
    'Market_Reaction_DXY': '+0.3% (102.8→103.1)',
    'Strategy_Impact_Summary': 'Higher inflation supports USD, negative for growth stocks',
    'Opportunities_Identified': 'Short tech growth, Long defensive sectors, USD strength play',
    'Action_Taken': 'Reduced QQQ exposure, added UUP long position',
    'Review_Date': '2024-05-01',
    'Follow_Up_Required': 'Monitor next Fed meeting rhetoric, track PPI release',
    'Confidence_Level': 'Medium',
    'Data_Sources': 'BLS, Bloomberg, CNBC',
    'Notes': 'Core CPI beat expectations by 0.2%'
}

log_news_assessment(new_assessment)
```

### Method 2: Manual Database Entry

1. Use the SQLAlchemy ORM or a SQLite client
2. Insert new row into `market_news` table
3. Fill all required columns
4. Commit transaction

---

## Querying News Assessments

### Filter by Severity
```python
from agents.common.database import get_db_session
from agents.common.models import MarketNews

with get_db_session() as session:
    critical_events = session.query(MarketNews).filter_by(severity='Critical').all()
    print(f"Found {len(critical_events)} critical events")
```

### Find Events Requiring Follow-Up
```python
df['Review_Date'] = pd.to_datetime(df['Review_Date'])
upcoming_reviews = df[df['Review_Date'] <= pd.Timestamp.now() + pd.Timedelta(days=7)]
print("Events to review this week:")
print(upcoming_reviews[['ID', 'Event_Name', 'Review_Date']])
```

### Analyze USD Impact Patterns
```python
# Count USD impact by category
impact_by_category = df.groupby(['Category', 'USD_Impact']).size()
print("USD Impact Patterns by Event Category:")
print(impact_by_category)
```

### Extract Trade Opportunities
```python
# Get all opportunities identified from news events
opportunities = df[df['Opportunities_Identified'].notna()]
print("Trade ideas from news events:")
for _, row in opportunities.iterrows():
    print(f"{row['Date']} - {row['Event_Name']}: {row['Opportunities_Identified']}")
```

---

## Integration with Research & Backtest Workflow

### Market News → Research Agent

When a news assessment identifies opportunities, the Research Agent should:

1. **Query market_news table** for recent high-severity events
2. **Extract Opportunities_Identified** column for preliminary trade ideas
3. **Conduct deep research** on promising opportunities
4. **Log refined strategies** to `strategies` table

**Example Workflow**:
```python
# Market News agent discovers opportunity
news_assessment = {
    'ID': 'NA-003',
    'Event_Name': 'Fed Signals Pause in Cuts',
    'Opportunities_Identified': 'Long USD via UUP, Short rate-sensitive tech growth stocks',
    ...
}

# Research agent picks up opportunity from database
with get_db_session() as session:
    high_priority = session.query(MarketNews).filter(
        MarketNews.severity.in_(['Critical', 'High']),
        MarketNews.opportunities_identified.isnot(None)
    ).all()

# For each opportunity, research and create trade idea
for news in high_priority:
    trade_idea = research_opportunity(news.opportunities_identified)
    
    # Log to strategies table with NEWS-DRIVEN tag
    trade_idea['notes'] = f"NEWS-DRIVEN from {news.id}: {news.event_name}"
    log_trade_idea(trade_idea)
```

### Research Agent → Backtest Agent

See the `strategies` table in `data/tradebot.db` for the research output that feeds into backtesting.

---

## When to Create an Assessment

### ✅ Create Assessment For:
- Fed meetings and rate decisions
- Major economic data surprises (beat/miss by >0.3%)
- Geopolitical crises affecting markets
- Earnings from positions you hold or bellwether companies
- Any event requiring position adjustments

### ❌ Skip Assessment For:
- Normal market fluctuations without catalyst
- Speculation or rumors
- Events with no USD or portfolio relevance

---

## Category Definitions

| Category | Description | Examples |
|----------|-------------|----------|
| **Monetary Policy** | Central bank decisions | Fed rate decisions, QT/QE announcements, ECB policy |
| **Economic Data** | Key economic indicators | CPI, NFP, GDP, PMI, Retail Sales |
| **Geopolitical** | International events | Wars, elections, trade disputes, sanctions |
| **Earnings** | Corporate earnings reports | AAPL earnings, Tech sector results, Guidance changes |
| **Other** | Miscellaneous events | Natural disasters, Black swan events, Regulatory changes |

---

## Severity Levels

| Severity | Description | Example |
|----------|-------------|---------|
| **Critical** | Portfolio-wide impact, immediate action required | Fed emergency rate cut, Market circuit breaker |
| **High** | Significant impact on multiple positions | Major economic data miss, Geopolitical crisis |
| **Medium** | Moderate impact on specific positions | Individual stock earnings, Sector news |
| **Low** | Minimal impact, informational only | Minor economic data, Forward guidance updates |

---

## Automation Guidelines

### Automated News Monitoring
```python
# Pseudo-code for automated news ingestion
def monitor_news_feeds():
    sources = ['Bloomberg API', 'Reuters API', 'Fed RSS']
    
    for source in sources:
        events = fetch_recent_events(source)
        
        for event in events:
            if is_significant(event):  # Filter by severity
                assessment = analyze_event(event)
                log_news_assessment(assessment)
                
                if assessment['Severity'] in ['Critical', 'High']:
                    # Trigger Research agent
                    notify_research_agent(assessment['Opportunities_Identified'])
```

### Integration with Portfolio Tracker
```python
# Check if news events require risk policy adjustment
def check_market_disruption():
    with get_db_session() as session:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_critical = session.query(MarketNews).filter(
            MarketNews.date >= week_ago,
            MarketNews.severity == 'Critical'
        ).all()
    
    if len(recent_critical) > 0:
        # Consider switching to MODERATE or LOW risk policy
        return True, [n.event_name for n in recent_critical]
    return False, []
```

---

## Analytics & Reporting

### Generate Summary Reports
```python
def generate_monthly_news_summary():
    with get_db_session() as session:
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        monthly = session.query(MarketNews).filter(
            MarketNews.date >= month_ago
        ).all()
    
    from collections import Counter
    report = {
        'total_events': len(monthly),
        'by_category': dict(Counter(n.category for n in monthly)),
        'by_severity': dict(Counter(n.severity for n in monthly)),
        'usd_strengthened': sum(1 for n in monthly if n.usd_impact == 'Positive'),
        'usd_weakened': sum(1 for n in monthly if n.usd_impact == 'Negative'),
        'opportunities_found': sum(1 for n in monthly if n.opportunities_identified)
    }
    
    return report
```

---

## Benefits of Database Format

✅ **Full Automation**: Programmatically log events via SQLAlchemy ORM  
✅ **Integration**: Research agent can query opportunities via SQL joins  
✅ **Analytics**: Track patterns with SQL aggregation  
✅ **Filtering**: SQL queries for events requiring follow-up  
✅ **Scalability**: Handle thousands of assessments efficiently  
✅ **Concurrency**: WAL mode supports concurrent agent access  
✅ **Data Pipeline**: Feeds into Research → Backtest → Implementation workflow  

---

*For the complete integrated workflow, see Market News → Research → Backtest pipeline documentation in the Manager README.*
