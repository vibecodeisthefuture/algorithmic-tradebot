"""
Trade Ideas Analytics Script

Analyzes the trade_ideas_log.csv to provide insights on:
- Conversion rates through the pipeline
- Success rates by strategy type
- Time to deployment metrics
- Stuck/stalled ideas identification
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Data repository paths (relative to project root)
TRADE_IDEAS_CSV = Path("../../data/logs/trade_ideas_log.csv")


def load_trade_ideas():
    """Load and parse trade ideas CSV"""
    df = pd.read_csv(TRADE_IDEAS_CSV)
    df['Date_Created'] = pd.to_datetime(df['Date_Created'])
    df['Last_Updated'] = pd.to_datetime(df['Last_Updated'])
    return df


def calculate_conversion_rates():
    """Calculate pipeline conversion rates"""
    df = load_trade_ideas()
    
    total_ideas = len(df)
    ready_for_backtest = len(df[df['Status'] == 'Ready for Backtest'])
    backtesting = len(df[df['Status'] == 'Backtesting'])
    validated = len(df[df['Status'] == 'Validated'])
    active = len(df[df['Status'] == 'Active'])
    rejected = len(df[df['Status'] == 'Rejected'])
    
    print("=" * 60)
    print("TRADE IDEAS PIPELINE CONVERSION RATES")
    print("=" * 60)
    print(f"\nTotal Ideas Generated: {total_ideas}")
    print(f"\nPipeline Breakdown:")
    print(f"  Research → Ready for Backtest: {ready_for_backtest} ({ready_for_backtest/total_ideas*100:.1f}%)")
    print(f"  Currently Backtesting: {backtesting} ({backtesting/total_ideas*100:.1f}%)")
    print(f"  Validated (Passed Backtest): {validated} ({validated/total_ideas*100:.1f}%)")
    print(f"  Active (Live Trading): {active} ({active/total_ideas*100:.1f}%)")
    print(f"  Rejected: {rejected} ({rejected/total_ideas*100:.1f}%)")
    
    # Calculate success metrics
    tested = validated + rejected
    if tested > 0:
        validation_rate = validated / tested * 100
        print(f"\n✅ Backtest Validation Rate: {validation_rate:.1f}% ({validated}/{tested} tested ideas)")
    
    if validated > 0:
        deployment_rate = active / validated * 100
        print(f"✅ Deployment Rate: {deployment_rate:.1f}% ({active}/{validated} validated ideas)")
    
    # Overall conversion
    if total_ideas > 0:
        overall_conversion = active / total_ideas * 100
        print(f"\n🎯 Overall Conversion (Ideas → Live): {overall_conversion:.1f}%")
    
    print("=" * 60)
    
    return {
        'total': total_ideas,
        'ready_backtest': ready_for_backtest,
        'backtesting': backtesting,
        'validated': validated,
        'active': active,
        'rejected': rejected
    }


def success_rate_by_type():
    """Analyze success rates by strategy type"""
    df = load_trade_ideas()
    
    print("\n" + "=" * 60)
    print("SUCCESS RATE BY STRATEGY TYPE")
    print("=" * 60)
    
    types = df['Type'].value_counts()
    
    for strategy_type in types.index:
        type_df = df[df['Type'] == strategy_type]
        total = len(type_df)
        validated = len(type_df[type_df['Status'] == 'Validated'])
        active = len(type_df[type_df['Status'] == 'Active'])
        rejected = len(type_df[type_df['Status'] == 'Rejected'])
        
        tested = validated + rejected
        validation_rate = (validated / tested * 100) if tested > 0 else 0
        
        print(f"\n{strategy_type}:")
        print(f"  Total Ideas: {total}")
        print(f"  Validated: {validated} / {tested} tested ({validation_rate:.1f}%)")
        print(f"  Active in Live: {active}")
        print(f"  Rejected: {rejected}")
    
    print("=" * 60)


def average_time_to_deployment():
    """Calculate average time from idea creation to deployment"""
    df = load_trade_ideas()
    
    # Filter to active or validated strategies
    deployed = df[df['Status'].isin(['Validated', 'Active'])]
    
    if len(deployed) == 0:
        print("\n⚠️ No validated/active strategies yet to calculate deployment time")
        return
    
    # Calculate days from creation to last update (proxy for deployment)
    deployed['days_to_deploy'] = (deployed['Last_Updated'] - deployed['Date_Created']).dt.days
    
    avg_days = deployed['days_to_deploy'].mean()
    median_days = deployed['days_to_deploy'].median()
    min_days = deployed['days_to_deploy'].min()
    max_days = deployed['days_to_deploy'].max()
    
    print("\n" + "=" * 60)
    print("TIME TO DEPLOYMENT METRICS")
    print("=" * 60)
    print(f"Average time to deployment: {avg_days:.1f} days")
    print(f"Median time to deployment: {median_days:.1f} days")
    print(f"Fastest deployment: {min_days} days")
    print(f"Slowest deployment: {max_days} days")
    print("=" * 60)
    
    return avg_days


def identify_stuck_ideas(days_threshold=30):
    """Find ideas that haven't progressed in >30 days"""
    df = load_trade_ideas()
    
    now = pd.Timestamp.now()
    df['days_since_update'] = (now - df['Last_Updated']).dt.days
    
    # Find stuck ideas (not in terminal states and no update in threshold days)
    non_terminal = df[~df['Status'].isin(['Validated', 'Active', 'Rejected', 'Retired'])]
    stuck = non_terminal[non_terminal['days_since_update'] > days_threshold]
    
    if len(stuck) == 0:
        print(f"\n✅ No stuck ideas found (threshold: {days_threshold} days)")
        return
    
    print("\n" + "=" * 60)
    print(f"STUCK IDEAS (No update in >{days_threshold} days)")
    print("=" * 60)
    
    for _, idea in stuck.iterrows():
        print(f"\n❗ ID {idea['ID']} - {idea['Name']}")
        print(f"   Status: {idea['Status']}")
        print(f"   Last Updated: {idea['Last_Updated'].date()} ({idea['days_since_update']} days ago)")
        print(f"   Priority: {idea['Priority']}")
    
    print("=" * 60)
    print(f"\nTotal Stuck Ideas: {len(stuck)}")
    
    return stuck


def news_driven_vs_research():
    """Compare NEWS-DRIVEN strategies vs research-only"""
    df = load_trade_ideas()
    
    # Identify news-driven ideas
    news_driven = df[df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)]
    research_only = df[~df['Notes'].str.contains('NEWS-DRIVEN', case=False, na=False)]
    
    print("\n" + "=" * 60)
    print("NEWS-DRIVEN VS RESEARCH-ONLY COMPARISON")
    print("=" * 60)
    
    # News-driven metrics
    nd_total = len(news_driven)
    nd_validated = len(news_driven[news_driven['Status'] == 'Validated'])
    nd_active = len(news_driven[news_driven['Status'] == 'Active'])
    nd_rejected = len(news_driven[news_driven['Status'] == 'Rejected'])
    nd_tested = nd_validated + nd_rejected
    nd_val_rate = (nd_validated / nd_tested * 100) if nd_tested > 0 else 0
    
    # Research-only metrics
    ro_total = len(research_only)
    ro_validated = len(research_only[research_only['Status'] == 'Validated'])
    ro_active = len(research_only[research_only['Status'] == 'Active'])
    ro_rejected = len(research_only[research_only['Status'] == 'Rejected'])
    ro_tested = ro_validated + ro_rejected
    ro_val_rate = (ro_validated / ro_tested * 100) if ro_tested > 0 else 0
    
    print(f"\n📰 NEWS-DRIVEN Strategies:")
    print(f"   Total: {nd_total}")
    print(f"   Validated: {nd_validated} / {nd_tested} tested ({nd_val_rate:.1f}%)")
    print(f"   Active: {nd_active}")
    
    print(f"\n🔬 RESEARCH-ONLY Strategies:")
    print(f"   Total: {ro_total}")
    print(f"   Validated: {ro_validated} / {ro_tested} tested ({ro_val_rate:.1f}%)")
    print(f"   Active: {ro_active}")
    
    # Comparison
    if nd_val_rate > ro_val_rate:
        improvement = nd_val_rate - ro_val_rate
        print(f"\n✅ News-driven strategies validate {improvement:.1f}% more often")
    elif ro_val_rate > nd_val_rate:
        improvement = ro_val_rate - nd_val_rate
        print(f"\n✅ Research-only strategies validate {improvement:.1f}% more often")
    else:
        print(f"\n➡️ Both approaches have equal validation rates")
    
    print("=" * 60)


def main():
    """Run all trade ideas analytics"""
    print("\n" + "🔍" * 30)
    print("TRADE IDEAS ANALYTICS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔍" * 30)
    
    try:
        # Run all analyses
        calculate_conversion_rates()
        success_rate_by_type()
        average_time_to_deployment()
        identify_stuck_ideas(days_threshold=30)
        news_driven_vs_research()
        
        print("\n✅ Analytics Complete!")
        
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find {TRADE_IDEAS_CSV}")
        print("Make sure you're running this script from the Analytics directory")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")


if __name__ == "__main__":
    main()
