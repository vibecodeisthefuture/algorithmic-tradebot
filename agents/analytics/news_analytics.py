"""
Market News Analytics Script

Analyzes news_assessments_log.csv to provide insights on:
- News category effectiveness
- Opportunity conversion rates
- USD impact correlation with strategy success
- News response time metrics
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Data repository paths (relative to project root)
NEWS_CSV = Path("../../data/logs/news_assessments_log.csv")
TRADE_IDEAS_CSV = Path("../../data/logs/trade_ideas_log.csv")


def load_data():
    """Load both news and trade ideas CSVs"""
    news_df = pd.read_csv(NEWS_CSV)
    ideas_df = pd.read_csv(TRADE_IDEAS_CSV)
    
    news_df['Date'] = pd.to_datetime(news_df['Date'])
    ideas_df['Date_Created'] = pd.to_datetime(ideas_df['Date_Created'])
    
    return news_df, ideas_df


def news_category_effectiveness():
    """Analyze which news categories are most valuable"""
    news_df, _ = load_data()
    
    print("=" * 60)
    print("NEWS CATEGORY ANALYSIS")
    print("=" * 60)
    
    categories = news_df['Category'].value_counts()
    
    for category in categories.index:
        cat_df = news_df[news_df['Category'] == category]
        total = len(cat_df)
        critical = len(cat_df[cat_df['Severity'] == 'Critical'])
        high = len(cat_df[cat_df['Severity'] == 'High'])
        
        # Opportunities identified
        has_opp = cat_df['Opportunities_Identified'].notna().sum()
        opp_rate = (has_opp / total * 100) if total > 0 else 0
        
        print(f"\n{category}:")
        print(f"  Total Events: {total}")
        print(f"  High Severity: {critical} Critical + {high} High = {critical + high} ({(critical + high)/total*100:.1f}%)")
        print(f"  Opportunities Identified: {has_opp} ({opp_rate:.1f}%)")
    
    print("=" * 60)


def opportunity_conversion_rate():
    """Calculate how many identified opportunities become trade ideas"""
    news_df, ideas_df = load_data()
    
    # Count news events with opportunities
    has_opportunities = news_df['Opportunities_Identified'].notna().sum()
    
    # Count news-driven trade ideas
    news_driven_ideas = len(ideas_df[ideas_df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)])
    
    conversion_rate = (news_driven_ideas / has_opportunities * 100) if has_opportunities > 0 else 0
    
    print("\n" + "=" * 60)
    print("OPPORTUNITY CONVERSION RATE")
    print("=" * 60)
    print(f"News Events with Opportunities: {has_opportunities}")
    print(f"NEWS-DRIVEN Trade Ideas Created: {news_driven_ideas}")
    print(f"Conversion Rate: {conversion_rate:.1f}%")
    
    if conversion_rate < 40:
        print(f"\n⚠️ Conversion rate below target (40%). Research agent may not be picking up all opportunities.")
    elif conversion_rate >= 40:
        print(f"\n✅ Good conversion rate (target: >40%)")
    
    print("=" * 60)
    
    return conversion_rate


def usd_impact_analysis():
    """Analyze USD impact patterns"""
    news_df, _ = load_data()
    
    print("\n" + "=" * 60)
    print("USD IMPACT ANALYSIS")
    print("=" * 60)
    
    usd_impacts = news_df['USD_Impact'].value_counts()
    
    for impact in ['Positive', 'Negative', 'Neutral']:
        if impact in usd_impacts.index:
            impact_df = news_df[news_df['USD_Impact'] == impact]
            total = len(impact_df)
            has_opp = impact_df['Opportunities_Identified'].notna().sum()
            opp_rate = (has_opp / total * 100) if total > 0 else 0
            
            print(f"\n{impact} USD Impact:")
            print(f"  Events: {total}")
            print(f"  Opportunities Identified: {has_opp} ({opp_rate:.1f}%)")
    
    print("=" * 60)


def severity_to_opportunity_correlation():
    """Analyze if high-severity events generate more opportunities"""
    news_df, _ = load_data()
    
    print("\n" + "=" * 60)
    print("SEVERITY → OPPORTUNITY CORRELATION")
    print("=" * 60)
    
    for severity in ['Critical', 'High', 'Medium', 'Low']:
        sev_df = news_df[news_df['Severity'] == severity]
        total = len(sev_df)
        if total == 0:
            continue
        
        has_opp = sev_df['Opportunities_Identified'].notna().sum()
        opp_rate = (has_opp / total * 100)
        
        print(f"\n{severity} Severity:")
        print(f"  Events: {total}")
        print(f"  With Opportunities: {has_opp} ({opp_rate:.1f}%)")
    
    print("\n💡 Insight: Higher severity events should generate more opportunities")
    print("=" * 60)


def news_response_time():
    """Calculate average time lag between news event and trade idea creation"""
    news_df, ideas_df = load_data()
    
    # Filter news-driven ideas
    news_driven = ideas_df[ideas_df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)]
    
    if len(news_driven) == 0:
        print("\n⚠️ No NEWS-DRIVEN trade ideas found yet")
        return
    
    # Extract news ID from notes (format: "NEWS-DRIVEN from NA-XXX")
    news_driven['News_ID'] = news_driven['Notes'].str.extract(r'(NA-\d+)')
    
    # Join with news events
    merged = news_driven.merge(
        news_df[['ID', 'Date']], 
        left_on='News_ID', 
        right_on='ID', 
        how='left'
    )
    
    # Calculate response time
    merged['response_days'] = (merged['Date_Created'] - merged['Date']).dt.days
    
    avg_response = merged['response_days'].mean()
    median_response = merged['response_days'].median()
    fastest = merged['response_days'].min()
    
    print("\n" + "=" * 60)
    print("NEWS RESPONSE TIME")
    print("=" * 60)
    print(f"Average Response Time: {avg_response:.1f} days")
    print(f"Median Response Time: {median_response:.1f} days")
    print(f"Fastest Response: {fastest} days")
    
    if avg_response <= 3:
        print(f"\n✅ Excellent response time (target: <3 days)")
    else:
        print(f"\n⚠️ Response time above target (goal: <3 days)")
    
    print("=" * 60)


def recent_high_severity_events(days=30):
    """Show recent high-severity events for context"""
    news_df, _ = load_data()
    
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    recent = news_df[news_df['Date'] >= cutoff]
    high_sev = recent[recent['Severity'].isin(['Critical', 'High'])]
    
    print("\n" + "=" * 60)
    print(f"HIGH-SEVERITY EVENTS (Last {days} Days)")
    print("=" * 60)
    
    if len(high_sev) == 0:
        print(f"No Critical or High severity events in last {days} days")
    else:
        for _, event in high_sev.iterrows():
            print(f"\n{event['ID']} - {event['Event_Name']}")
            print(f"  Date: {event['Date'].date()}")
            print(f"  Severity: {event['Severity']}")
            print(f"  Category: {event['Category']}")
            has_opp = "Yes" if pd.notna(event['Opportunities_Identified']) else "No"
            print(f"  Opportunities: {has_opp}")
    
    print("=" * 60)


def main():
    """Run all news analytics"""
    print("\n" + "📰" * 30)
    print("MARKET NEWS ANALYTICS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📰" * 30)
    
    try:
        news_category_effectiveness()
        opportunity_conversion_rate()
        usd_impact_analysis()
        severity_to_opportunity_correlation()
        news_response_time()
        recent_high_severity_events(days=30)
        
        print("\n✅ Analytics Complete!")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: Could not find required CSV files")
        print(f"Details: {e}")
        print("Make sure you're running this script from the Analytics directory")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")


if __name__ == "__main__":
    main()
