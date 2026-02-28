"""
Cross-Repository Analytics Script

Combines data from all repositories to provide system-wide insights:
- End-to-end strategy tracking (News → Idea → Backtest → Live)
- System throughput metrics
- Pipeline bottleneck analysis
- News-driven strategy success tracking
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Data repository paths (relative to project root)
NEWS_CSV = Path("../../data/logs/news_assessments_log.csv")
TRADE_IDEAS_CSV = Path("../../data/logs/trade_ideas_log.csv")
ORDER_HISTORY_CSV = Path("../../data/logs/order_history.csv")


def load_all_data():
    """Load all data repositories"""
    news_df = pd.read_csv(NEWS_CSV)
    ideas_df = pd.read_csv(TRADE_IDEAS_CSV)
    
    news_df['Date'] = pd.to_datetime(news_df['Date'])
    ideas_df['Date_Created'] = pd.to_datetime(ideas_df['Date_Created'])
    ideas_df['Last_Updated'] = pd.to_datetime(ideas_df['Last_Updated'])
    
    # Try to load order history if it exists
    try:
        orders_df = pd.read_csv(ORDER_HISTORY_CSV)
        orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])
    except FileNotFoundError:
        orders_df = None
    
    return news_df, ideas_df, orders_df


def end_to_end_tracking():
    """Track complete journey: News → Trade Idea → Strategy"""
    news_df, ideas_df, _ = load_all_data()
    
    print("=" * 70)
    print("END-TO-END STRATEGY TRACKING (News → Research → Backtest)")
    print("=" * 70)
    
    # Filter news-driven ideas
    news_driven = ideas_df[ideas_df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)]
    
    if len(news_driven) == 0:
        print("\n⚠️ No NEWS-DRIVEN strategies found yet for tracking")
        print("=" * 70)
        return
    
    # Extract news ID
    news_driven['News_ID'] = news_driven['Notes'].str.extract(r'(NA-\d+)')
    
    # Join with news data
    merged = news_driven.merge(
        news_df[['ID', 'Event_Name', 'Category', 'Severity', 'Date']], 
        left_on='News_ID', 
        right_on='ID',
        how='left',
        suffixes=('_idea', '_news')
    )
    
    # Calculate time deltas
    merged['Days_To_Idea'] = (merged['Date_Created'] - merged['Date']).dt.days
    merged['Days_Total'] = (merged['Last_Updated'] - merged['Date']).dt.days
    
    print(f"\nTracking {len(merged)} news-driven strategies:\n")
    
    for _, row in merged.iterrows():
        print(f"📰 {row['ID_news']} - {row['Event_Name']}")
        print(f"   Category: {row['Category']} | Severity: {row['Severity']}")
        print(f"   ↓")
        print(f"   {row['Days_To_Idea']} days later...")
        print(f"   ↓")
        print(f"🔬 {row['ID_idea']} - {row['Name']}")
        print(f"   Type: {row['Type']} | Status: {row['Status']}")
        print(f"   Total Duration: {row['Days_Total']} days")
        print()
    
    # Summary stats
    print("Summary Statistics:")
    print(f"  Average news → idea time: {merged['Days_To_Idea'].mean():.1f} days")
    print(f"  Average total duration: {merged['Days_Total'].mean():.1f} days")
    
    # Status breakdown
    status_counts = merged['Status'].value_counts()
    print(f"\nStatus Breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    print("=" * 70)


def system_throughput():
    """Calculate system throughput metrics"""
    _, ideas_df, _ = load_all_data()
    
    print("\n" + "=" * 70)
    print("SYSTEM THROUGHPUT METRICS")
    print("=" * 70)
    
    # Calculate monthly throughput
    now = pd.Timestamp.now()
    
    # Last 30 days
    last_30 = ideas_df[ideas_df['Date_Created'] >= now - pd.Timedelta(days=30)]
    ideas_per_month = len(last_30)
    
    # Validated in last 30 days
    validated_30 = ideas_df[
        (ideas_df['Last_Updated'] >= now - pd.Timedelta(days=30)) &
        (ideas_df['Status'] == 'Validated')
    ]
    validations_per_month = len(validated_30)
    
    # Active deployments in last 30 days
    deployed_30 = ideas_df[
        (ideas_df['Last_Updated'] >= now - pd.Timedelta(days=30)) &
        (ideas_df['Status'] == 'Active')
    ]
    deployments_per_month = len(deployed_30)
    
    print(f"\nLast 30 Days:")
    print(f"  Ideas Generated: {ideas_per_month}")
    print(f"  Strategies Validated: {validations_per_month}")
    print(f"  Strategies Deployed: {deployments_per_month}")
    
    # Calculate annualized throughput
    annualized_ideas = ideas_per_month * 12
    annualized_deployments = deployments_per_month * 12
    
    print(f"\nAnnualized Projections:")
    print(f"  Ideas/Year: ~{annualized_ideas}")
    print(f"  Deployments/Year: ~{annualized_deployments}")
    
    # Throughput efficiency
    if ideas_per_month > 0:
        efficiency = (deployments_per_month / ideas_per_month * 100)
        print(f"\n📊 Throughput Efficiency: {efficiency:.1f}% (Ideas → Active)")
        
        if efficiency < 10:
            print("   ⚠️ Below target (10%). Pipeline may have bottlenecks.")
        else:
            print("   ✅ Meeting or exceeding target efficiency")
    
    print("=" * 70)


def bottleneck_analysis():
    """Identify where ideas get stuck in the pipeline"""
    _, ideas_df, _ = load_all_data()
    
    print("\n" + "=" * 70)
    print("PIPELINE BOTTLENECK ANALYSIS")
    print("=" * 70)
    
    now = pd.Timestamp.now()
    ideas_df['days_since_update'] = (now - ideas_df['Last_Updated']).dt.days
    
    # Analyze each non-terminal status
    statuses = ['Research', 'Ready for Backtest', 'Backtesting']
    
    for status in statuses:
        status_df = ideas_df[ideas_df['Status'] == status]
        
        if len(status_df) == 0:
            continue
        
        avg_age = status_df['days_since_update'].mean()
        max_age = status_df['days_since_update'].max()
        count = len(status_df)
        
        print(f"\n{status}:")
        print(f"  Count: {count}")
        print(f"  Avg days since update: {avg_age:.1f}")
        print(f"  Max days since update: {max_age}")
        
        # Flag bottlenecks
        if avg_age > 30:
            print(f"  ⚠️ BOTTLENECK: Average age exceeds 30 days")
        elif avg_age > 14:
            print(f"  ⚠️ WARNING: Average age exceeds 14 days")
    
    print("\n💡 Recommendation:")
    print("   Review ideas with >30 days since update to unblock pipeline")
    
    print("=" * 70)


def news_category_to_strategy_success():
    """Which news categories lead to successful strategies?"""
    news_df, ideas_df, _ = load_all_data()
    
    print("\n" + "=" * 70)
    print("NEWS CATEGORY → STRATEGY SUCCESS ANALYSIS")
    print("=" * 70)
    
    # Filter news-driven ideas
    news_driven = ideas_df[ideas_df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)]
    
    if len(news_driven) == 0:
        print("\n⚠️ Insufficient data: No NEWS-DRIVEN strategies yet")
        print("=" * 70)
        return
    
    # Extract news ID and join
    news_driven['News_ID'] = news_driven['Notes'].str.extract(r'(NA-\d+)')
    merged = news_driven.merge(
        news_df[['ID', 'Category']], 
        left_on='News_ID', 
        right_on='ID',
        how='left'
    )
    
    # Analyze by category
    categories = merged['Category'].value_counts()
    
    print(f"\nNews-Driven Strategies by Category:\n")
    
    for category in categories.index:
        cat_df = merged[merged['Category'] == category]
        total = len(cat_df)
        validated = len(cat_df[cat_df['Status'] == 'Validated'])
        active = len(cat_df[cat_df['Status'] == 'Active'])
        rejected = len(cat_df[cat_df['Status'] == 'Rejected'])
        
        tested = validated + rejected
        success_rate = (validated / tested * 100) if tested > 0 else 0
        
        print(f"{category}:")
        print(f"  Strategies Generated: {total}")
        print(f"  Success Rate: {validated}/{tested} tested ({success_rate:.1f}%)")
        print(f"  Active in Live: {active}")
        print()
    
    print("💡 Use this data to prioritize high-success news categories")
    print("=" * 70)


def comprehensive_status_report():
    """Generate comprehensive system status"""
    news_df, ideas_df, orders_df = load_all_data()
    
    print("\n" + "=" * 70)
    print("COMPREHENSIVE SYSTEM STATUS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # News stats
    total_news = len(news_df)
    high_sev_news = len(news_df[news_df['Severity'].isin(['Critical', 'High'])])
    news_with_opp = news_df['Opportunities_Identified'].notna().sum()
    
    print(f"\n📰 Market News:")
    print(f"   Total Events Logged: {total_news}")
    print(f"   High-Severity Events: {high_sev_news}")
    print(f"   With Opportunities: {news_with_opp}")
    
    # Ideas stats
    total_ideas = len(ideas_df)
    validated = len(ideas_df[ideas_df['Status'] == 'Validated'])
    active = len(ideas_df[ideas_df['Status'] == 'Active'])
    news_driven = len(ideas_df[ideas_df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)])
    
    print(f"\n🔬 Trade Ideas:")
    print(f"   Total Ideas: {total_ideas}")
    print(f"   Validated: {validated}")
    print(f"   Active (Live): {active}")
    print(f"   NEWS-DRIVEN: {news_driven}")
    
    # Trading stats
    if orders_df is not None and len(orders_df) > 0:
        total_orders = len(orders_df)
        print(f"\n💹 Trading:")
        print(f"   Total Orders: {total_orders}")
    else:
        print(f"\n💹 Trading:")
        print(f"   No order history available yet")
    
    # System health
    stuck_ideas = len(ideas_df[
        (~ideas_df['Status'].isin(['Validated', 'Active', 'Rejected', 'Retired'])) &
        ((pd.Timestamp.now() - ideas_df['Last_Updated']).dt.days > 30)
    ])
    
    print(f"\n⚕️ System Health:")
    print(f"   Stuck Ideas (>30 days): {stuck_ideas}")
    
    if stuck_ideas > 0:
        print(f"   ⚠️ {stuck_ideas} ideas need attention")
    else:
        print(f"   ✅ All ideas progressing normally")
    
    print("=" * 70)


def main():
    """Run all cross-repository analytics"""
    print("\n" + "🔗" * 30)
    print("CROSS-REPOSITORY ANALYTICS REPORT")
    print("🔗" * 30)
    
    try:
        comprehensive_status_report()
        end_to_end_tracking()
        system_throughput()
        bottleneck_analysis()
        news_category_to_strategy_success()
        
        print("\n✅ Analytics Complete!")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: Could not find required CSV files")
        print(f"Details: {e}")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
