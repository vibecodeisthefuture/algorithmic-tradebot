# Data Analytics Agent - Quick Reference

This directory contains the Analytics Agent framework for querying all project data repositories.

## Purpose

Generate actionable insights from:
- Trade ideas pipeline (`strategies` table)
- Market news events (`market_news` table)
- Trading history (`trades` table)
- Portfolio health data (`portfolio_snapshots` table)
- Backtest results (`backtest_results` table)

## Quick Start

### Run Individual Analytics

```bash
# Analyze trade ideas pipeline
python trade_ideas_analytics.py

# Analyze market news impact
python news_analytics.py

# Cross-repository insights
python cross_repository_analytics.py

# Generate unified dashboard
python analytics_dashboard.py
```

### Generated Reports

Reports are saved to `../analytics_reports/` directory.

## Scripts Overview

| Script | Purpose | Key Metrics |
|--------|---------|-------------|
| `trade_ideas_analytics.py` | Research pipeline analysis | Conversion rates, success by type, stuck ideas |
| `news_analytics.py` | Market news effectiveness | Category success, opportunity conversion, response time |
| `cross_repository_analytics.py` | End-to-end tracking | News → Idea → Strategy journey, bottlenecks |
| `analytics_dashboard.py` | Unified reporting | Executive summary, health status, recommendations |

## Key Insights Provided

✅ **Pipeline Conversion**: Research → Backtest → Live success rates  
✅ **Strategy Type Performance**: Which types (Momentum, Income, etc.) succeed most  
✅ **News Impact**: Which news categories generate profitable strategies  
✅ **Bottleneck Identification**: Where ideas get stuck in pipeline  
✅ **Throughput Metrics**: Ideas/month, deployments/month, cycle time  
✅ **System Health**: Stuck ideas, stalled processes  

## Dependencies

```bash
pip install pandas numpy matplotlib
```

## Documentation

See `SKILL.md` for complete documentation, workflows, and KPIs.

---

*For full Analytics Agent capabilities and integration details, refer to SKILL.md*
