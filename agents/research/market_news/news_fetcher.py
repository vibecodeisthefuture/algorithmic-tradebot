#!/usr/bin/env python3
"""
Market News Agent — Live Crypto News Fetcher

Continuously queries real-time crypto news from the Alpaca News API and
writes structured assessments to the `market_news` table in the Blackboard.

This script fulfills the Market News Agent's SKILL.md responsibilities:
  - Continuous news monitoring at configurable intervals
  - Impact scoring (CRITICAL / HIGH / MED / LOW)
  - Structured DB inserts for downstream agent consumption
  - ZeroMQ event bus notifications on CRITICAL/HIGH events
  - Dynamic symbol discovery — no hardcoded coin lists

Usage:
    py agents/research/market_news/news_fetcher.py             # single fetch
    py agents/research/market_news/news_fetcher.py --loop 300  # poll every 5 min
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.common.database import get_db_session, init_db
from agents.common.models import MarketNews
from agents.common.enums import ImpactRating

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [NEWS-FETCHER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("news_fetcher")


# ═══════════════════════════════════════════════════════════════════════════
# Crypto Asset Classification
# ═══════════════════════════════════════════════════════════════════════════

# Stablecoins — pegged to fiat or commodities; NOT traded as speculative
# assets.  These are filtered OUT of strategy generation but still tracked
# for depeg events (which are CRITICAL news).
STABLECOINS = frozenset({
    "USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP", "FRAX",
    "GUSD", "LUSD", "SUSD", "PYUSD", "FDUSD", "USDD", "EURC",
    "XSGD", "EURT",
})

# Meme coins — high-volatility, sentiment-driven.  Used for aggressive
# momentum/scalp strategies only.  Subject to tighter risk controls.
MEME_COINS = frozenset({
    "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "MEME",
    "MYRO", "SAMO", "ELON", "BABYDOGE", "KISHU", "AKITA",
    "NEIRO", "POPCAT", "BRETT", "MOG", "SPX", "TURBO", "LADYS",
    "BOME", "SLERF", "WEN", "BOOK", "SILLY",
})


def classify_crypto(symbol: str) -> str:
    """
    Classify a crypto symbol into one of three categories.

    Returns:
        "stablecoin" | "meme" | "major"
    """
    base = symbol.upper().replace("/USD", "").replace("USD", "")
    if base in STABLECOINS:
        return "stablecoin"
    if base in MEME_COINS:
        return "meme"
    return "major"


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic Symbol Discovery
# ═══════════════════════════════════════════════════════════════════════════

_cached_symbols: Optional[list[str]] = None
_cache_timestamp: Optional[datetime] = None
SYMBOL_CACHE_TTL = timedelta(hours=1)


def discover_tradeable_crypto() -> list[str]:
    """
    Dynamically fetch ALL crypto symbols tradeable on Alpaca.
    Results are cached for 1 hour to avoid excessive API calls.

    Returns list of symbols in Alpaca format (e.g. "BTCUSD").
    """
    global _cached_symbols, _cache_timestamp

    now = datetime.now(timezone.utc)
    if (
        _cached_symbols is not None
        and _cache_timestamp is not None
        and now - _cache_timestamp < SYMBOL_CACHE_TTL
    ):
        return _cached_symbols

    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")
    if not api_key or not api_secret:
        log.error("ALPACA_API_KEY / ALPACA_API_SECRET not set")
        return _cached_symbols or []

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetAssetsRequest
        from alpaca.trading.enums import AssetClass

        client = TradingClient(
            api_key=api_key, secret_key=api_secret, paper=True
        )
        request = GetAssetsRequest(asset_class=AssetClass.CRYPTO)
        assets = client.get_all_assets(filter=request)

        symbols = []
        for asset in assets:
            if asset.tradable and asset.status == "active":
                symbols.append(asset.symbol)

        _cached_symbols = sorted(symbols)
        _cache_timestamp = now

        n_stable = sum(1 for s in symbols if classify_crypto(s) == "stablecoin")
        n_meme = sum(1 for s in symbols if classify_crypto(s) == "meme")
        n_major = len(symbols) - n_stable - n_meme

        log.info(
            f"Discovered {len(symbols)} tradeable crypto assets "
            f"(major={n_major}, meme={n_meme}, stablecoin={n_stable})"
        )
        return _cached_symbols

    except Exception as e:
        log.error(f"Failed to discover crypto assets: {e}")
        return _cached_symbols or []


# ═══════════════════════════════════════════════════════════════════════════
# Impact Scoring
# ═══════════════════════════════════════════════════════════════════════════

# Keywords that elevate severity — ordered by priority
CRITICAL_KEYWORDS = [
    "fed", "fomc", "rate cut", "rate hike", "emergency",
    "crash", "collapse", "bank run", "default", "war",
    "sanctions", "ban", "sec lawsuit", "hack", "exploit",
    "depegged", "depeg", "insolvency", "bankruptcy",
    "rug pull", "exit scam", "frozen", "seized",
]
HIGH_KEYWORDS = [
    "regulation", "etf", "whale", "liquidation", "billion",
    "inflation", "cpi", "gdp", "treasury", "yield",
    "halving", "stablecoin", "cbdc", "lawsuit", "subpoena",
    "investigation", "dump", "pump", "surge", "plunge",
    "delisting", "suspension", "vulnerability", "breach",
]
MEDIUM_KEYWORDS = [
    "upgrade", "partnership", "launch", "listing", "adoption",
    "milestone", "record", "fund", "institutional", "mining",
    "network", "fork", "airdrop", "governance", "defi",
    "staking", "yield", "tvl", "integration", "rollup",
]


def _score_impact(headline: str, summary: str) -> ImpactRating:
    """Score a news item's market impact using keyword analysis."""
    text = (headline + " " + (summary or "")).lower()

    for kw in CRITICAL_KEYWORDS:
        if kw in text:
            return ImpactRating.CRITICAL
    for kw in HIGH_KEYWORDS:
        if kw in text:
            return ImpactRating.HIGH
    for kw in MEDIUM_KEYWORDS:
        if kw in text:
            return ImpactRating.MED

    return ImpactRating.LOW


def _extract_affected_assets(headline: str, summary: str) -> str:
    """Extract crypto symbols mentioned in the text."""
    text = (headline + " " + (summary or "")).upper()

    # Check against all discovered symbols (base names)
    all_symbols = discover_tradeable_crypto()
    base_names = set()
    for s in all_symbols:
        base = s.replace("/USD", "").replace("USD", "")
        if len(base) >= 2:
            base_names.add(base)

    found = [sym for sym in base_names if f" {sym} " in f" {text} " or f" {sym}/" in f" {text}/"]
    return ",".join(sorted(found)) if found else ""


def _extract_opportunities(headline: str, summary: str, impact: ImpactRating) -> str:
    """Generate a brief opportunity note based on impact."""
    if impact == ImpactRating.CRITICAL:
        return "CRITICAL event — immediate portfolio review required. Potential defensive repositioning."
    elif impact == ImpactRating.HIGH:
        return "High-impact event — review active positions for exposure. Potential strategy adjustment."
    elif impact == ImpactRating.MED:
        return "Medium-impact — monitor for follow-up developments."
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# Alpaca News API Client
# ═══════════════════════════════════════════════════════════════════════════

def fetch_crypto_news(since_minutes: int = 30, max_items: int = 50) -> list[dict]:
    """
    Fetch recent crypto news from the Alpaca News API.

    Uses dynamically discovered symbols — no hardcoded list.

    Returns a list of dicts with keys: headline, summary, source, url,
    created_at, symbols.
    """
    try:
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest
    except ImportError:
        log.error("alpaca-py not installed. Install with: pip install alpaca-py")
        return []

    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")

    if not api_key or not api_secret:
        log.error("ALPACA_API_KEY / ALPACA_API_SECRET not set")
        return []

    try:
        client = NewsClient(api_key=api_key, secret_key=api_secret)
        start = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

        # Use dynamically discovered symbols for the news query
        all_symbols = discover_tradeable_crypto()
        # Alpaca News API needs "BTCUSD" format (no slash)
        news_symbols = [s.replace("/", "") for s in all_symbols]

        # Alpaca limits symbol list per request — batch in groups of 50
        all_articles: list[dict] = []
        batch_size = 50
        for i in range(0, len(news_symbols), batch_size):
            batch = news_symbols[i : i + batch_size]
            try:
                request = NewsRequest(
                    symbols=batch,
                    start=start,
                    limit=max_items,
                    sort="DESC",
                )
                news_set = client.get_news(request)
                for article in news_set.news:
                    all_articles.append({
                        "headline": article.headline or "",
                        "summary": article.summary or "",
                        "source": article.source or "Unknown",
                        "url": article.url or "",
                        "created_at": article.created_at,
                        "symbols": [s for s in (article.symbols or [])],
                    })
            except Exception as e:
                log.warning(f"News batch {i}-{i+batch_size} failed: {e}")

        # Deduplicate across batches (same headline)
        seen = set()
        unique = []
        for art in all_articles:
            if art["headline"] not in seen:
                seen.add(art["headline"])
                unique.append(art)

        log.info(f"Fetched {len(unique)} unique news articles from Alpaca")
        return unique

    except Exception as e:
        log.error(f"Failed to fetch news from Alpaca: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Write to Blackboard
# ═══════════════════════════════════════════════════════════════════════════

def process_and_store_news(articles: list[dict]) -> int:
    """
    Process raw news articles and write them to the market_news table.
    Returns the number of new articles stored.
    """
    if not articles:
        return 0

    stored = 0
    with get_db_session() as session:
        for article in articles:
            headline = article["headline"]
            summary = article.get("summary", "")

            # Deduplicate — skip if we already have this headline
            existing = (
                session.query(MarketNews)
                .filter_by(headline=headline)
                .first()
            )
            if existing:
                continue

            impact = _score_impact(headline, summary)
            affected = _extract_affected_assets(headline, summary)
            opportunities = _extract_opportunities(headline, summary, impact)

            news_row = MarketNews(
                source=article["source"],
                headline=headline,
                content=summary,
                sentiment_score=None,  # Future: plug in NLP sentiment model
                impact_rating=impact,
                affected_assets=affected,
                opportunities_identified=opportunities,
                sources_urls=article.get("url", ""),
                discovered_at=article.get(
                    "created_at", datetime.now(timezone.utc)
                ),
                processed_by_manager=False,
            )
            session.add(news_row)
            stored += 1

            icon = {
                ImpactRating.CRITICAL: "🔴",
                ImpactRating.HIGH: "🔶",
                ImpactRating.MED: "⚠",
                ImpactRating.LOW: "ℹ",
            }.get(impact, "•")
            log.info(f"  {icon} [{impact.value}] {headline[:80]}")

    # Publish ZeroMQ events for CRITICAL / HIGH items
    _publish_zmq_alerts(articles)

    return stored


def _publish_zmq_alerts(articles: list[dict]) -> None:
    """Publish ZeroMQ notifications for CRITICAL and HIGH news."""
    try:
        from agents.common.event_bus import (
            EventPublisher,
            TOPIC_NEWS_CRITICAL,
            TOPIC_NEWS_HIGH,
        )

        pub = EventPublisher()
        for article in articles:
            impact = _score_impact(
                article["headline"], article.get("summary", "")
            )
            if impact == ImpactRating.CRITICAL:
                pub.publish(TOPIC_NEWS_CRITICAL, {
                    "event_name": article["headline"][:100],
                    "category": "Crypto",
                    "severity": "Critical",
                    "affected_assets": _extract_affected_assets(
                        article["headline"], article.get("summary", "")
                    ).split(","),
                })
            elif impact == ImpactRating.HIGH:
                pub.publish(TOPIC_NEWS_HIGH, {
                    "event_name": article["headline"][:100],
                    "category": "Crypto",
                    "severity": "High",
                    "affected_assets": _extract_affected_assets(
                        article["headline"], article.get("summary", "")
                    ).split(","),
                })
        pub.close()
    except Exception:
        pass  # ZeroMQ is best-effort


# ═══════════════════════════════════════════════════════════════════════════
# Main fetch cycle
# ═══════════════════════════════════════════════════════════════════════════

def run_fetch(since_minutes: int = 30) -> int:
    """Execute one complete news fetch + store cycle."""
    log.info("═" * 60)
    log.info("Starting news fetch cycle")
    log.info("═" * 60)

    articles = fetch_crypto_news(since_minutes=since_minutes)
    stored = process_and_store_news(articles)

    if stored:
        log.info(f"Fetch complete: {stored} new article(s) stored")
    else:
        log.info("Fetch complete: no new articles")

    return stored


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Market News Agent — Live Crypto News Fetcher"
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECS",
        help="Poll interval in seconds (0 = single fetch). Default: 0",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=30,
        metavar="MINS",
        help="Look back N minutes for news. Default: 30",
    )
    args = parser.parse_args()

    init_db()

    if args.loop > 0:
        log.info(
            f"Starting continuous news monitoring "
            f"(every {args.loop}s). Ctrl+C to stop."
        )
        try:
            while True:
                run_fetch(since_minutes=args.since)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
    else:
        run_fetch(since_minutes=args.since)


if __name__ == "__main__":
    main()
