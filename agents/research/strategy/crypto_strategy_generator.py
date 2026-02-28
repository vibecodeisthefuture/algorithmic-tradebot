#!/usr/bin/env python3
"""
Strategy Research Agent — Live Crypto Strategy Generator

Dynamically discovers all tradeable crypto on Alpaca, classifies each
coin (stablecoin / meme / major), fetches live market data, and runs
a pluggable set of pattern detectors via the PatternRegistry.

**Adding a new pattern** requires only writing a function and decorating it:

    @PatternRegistry.register(
        name="My Detector",
        categories=["major", "meme"],
        description="Detects XYZ when ...",
    )
    def detect_my_pattern(symbol, bars, category):
        ...
        return idea_dict or None

The registry is iterated automatically during each scan cycle.

Usage:
    py agents/research/strategy/crypto_strategy_generator.py              # single scan
    py agents/research/strategy/crypto_strategy_generator.py --loop 600   # scan every 10 min
"""

import argparse
import logging
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.common.database import get_db_session, init_db
from agents.common.models import Strategy, MarketNews
from agents.common.enums import StrategyStatus, ImpactRating

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STRATEGY-GEN] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crypto_strategy_generator")


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Registry  — plug-in architecture for N pattern detectors
# ═══════════════════════════════════════════════════════════════════════════

class PatternRegistry:
    """
    Central registry for crypto pattern detectors.

    Usage:
        @PatternRegistry.register(
            name="Momentum Breakout",
            categories=["major", "meme"],
            description="Detects strong upward RSI + SMA breakout.",
        )
        def detect_momentum_breakout(symbol, bars, category):
            ...  # return dict or None

        # At scan time:
        for detector in PatternRegistry.all():
            idea = detector.fn(symbol, bars, category)
    """

    _detectors: list[dict] = []

    @classmethod
    def register(
        cls,
        name: str,
        categories: list[str],
        description: str = "",
    ) -> Callable:
        """Decorator to register a new pattern detector function."""
        def decorator(fn: Callable) -> Callable:
            cls._detectors.append({
                "name": name,
                "categories": frozenset(categories),
                "description": description,
                "fn": fn,
            })
            return fn
        return decorator

    @classmethod
    def all(cls) -> list[dict]:
        """Return every registered detector."""
        return cls._detectors

    @classmethod
    def for_category(cls, category: str) -> list[dict]:
        """Return detectors applicable to a given coin category."""
        return [d for d in cls._detectors if category in d["categories"]]

    @classmethod
    def count(cls) -> int:
        return len(cls._detectors)


# ═══════════════════════════════════════════════════════════════════════════
# Crypto Asset Classification
# ═══════════════════════════════════════════════════════════════════════════

STABLECOINS = frozenset({
    "USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP", "FRAX",
    "GUSD", "LUSD", "SUSD", "PYUSD", "FDUSD", "USDD", "EURC",
    "XSGD", "EURT",
})

MEME_COINS = frozenset({
    "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "MEME",
    "MYRO", "SAMO", "ELON", "BABYDOGE", "KISHU", "AKITA",
    "NEIRO", "POPCAT", "BRETT", "MOG", "SPX", "TURBO", "LADYS",
    "BOME", "SLERF", "WEN", "BOOK", "SILLY",
})


def _base(symbol: str) -> str:
    return symbol.upper().replace("/USD", "").replace("USD", "")


def classify_crypto(symbol: str) -> str:
    """Returns "stablecoin" | "meme" | "major"."""
    base = _base(symbol)
    if base in STABLECOINS:
        return "stablecoin"
    if base in MEME_COINS:
        return "meme"
    return "major"


# Per-category risk parameters — referenced by pattern detectors
CATEGORY_PARAMS = {
    "major": {
        "stop_loss_pct": 3.0,
        "take_profit_pct": 8.0,
        "max_hold_hours": 48,
        "position_sizing": "standard",
    },
    "meme": {
        "stop_loss_pct": 5.0,
        "take_profit_pct": 15.0,
        "max_hold_hours": 12,
        "position_sizing": "reduced",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic Symbol Discovery
# ═══════════════════════════════════════════════════════════════════════════

_cached_symbols: Optional[list[str]] = None
_cache_timestamp: Optional[datetime] = None
SYMBOL_CACHE_TTL = timedelta(hours=1)


def discover_tradeable_crypto() -> list[str]:
    """Fetch ALL crypto symbols tradeable on Alpaca (cached 1 hr)."""
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

        client = TradingClient(api_key=api_key, secret_key=api_secret, paper=True)
        request = GetAssetsRequest(asset_class=AssetClass.CRYPTO)
        assets = client.get_all_assets(filter=request)

        symbols = [a.symbol for a in assets if a.tradable and a.status == "active"]
        _cached_symbols = sorted(symbols)
        _cache_timestamp = now

        cats = {"major": 0, "meme": 0, "stablecoin": 0}
        for s in symbols:
            cats[classify_crypto(s)] += 1
        log.info(
            f"Discovered {len(symbols)} tradeable crypto "
            f"(major={cats['major']}, meme={cats['meme']}, "
            f"stablecoin={cats['stablecoin']})"
        )
        return _cached_symbols
    except Exception as e:
        log.error(f"Failed to discover crypto assets: {e}")
        return _cached_symbols or []


# ═══════════════════════════════════════════════════════════════════════════
# Market Data Fetcher
# ═══════════════════════════════════════════════════════════════════════════

MIN_BARS_FOR_ANALYSIS = 20


def fetch_crypto_bars(
    symbols: list[str], lookback_days: int = 7
) -> dict[str, list[dict]]:
    """Fetch hourly bars from Alpaca.  Batches to respect API limits."""
    try:
        from alpaca.data.historical import CryptoHistoricalDataClient
        from alpaca.data.requests import CryptoBarsRequest
        from alpaca.data.timeframe import TimeFrame
    except ImportError:
        log.error("alpaca-py not installed. Install with: pip install alpaca-py")
        return {}

    try:
        client = CryptoHistoricalDataClient()
        start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        result: dict[str, list[dict]] = {}
        batch_size = 25

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            try:
                request = CryptoBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Hour,
                    start=start,
                )
                resp = client.get_crypto_bars(request)
                for sym in batch:
                    try:
                        bars_list = [
                            {
                                "open": float(b.open),
                                "high": float(b.high),
                                "low": float(b.low),
                                "close": float(b.close),
                                "volume": float(b.volume),
                                "timestamp": b.timestamp,
                            }
                            for b in (resp[sym] if sym in resp else [])
                        ]
                        if bars_list:
                            result[sym] = bars_list
                    except (KeyError, TypeError):
                        pass
            except Exception as e:
                log.warning(f"Bar batch {i}-{i+batch_size} failed: {e}")

        log.info(f"Fetched bar data for {len(result)}/{len(symbols)} symbols")
        return result
    except Exception as e:
        log.error(f"Failed to fetch crypto bars: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════
# Technical Indicators  — shared helpers used by pattern detectors
# ═══════════════════════════════════════════════════════════════════════════

MOMENTUM_LOOKBACK = 14
VOLATILITY_LOOKBACK = 20
MEAN_REVERSION_THRESHOLD = 2.0


def compute_rsi(closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0.0001
    avg_loss = sum(losses) / period if losses else 0.0001
    return 100 - (100 / (1 + avg_gain / avg_loss))


def compute_sma(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def compute_ema(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def compute_std(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    subset = values[-period:]
    mean = sum(subset) / len(subset)
    return math.sqrt(sum((x - mean) ** 2 for x in subset) / len(subset))


def compute_atr(bars: list[dict], period: int = 14) -> Optional[float]:
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, lo, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    return sum(trs[-period:]) / period


def compute_momentum_pct(closes: list[float], period: int = 24) -> Optional[float]:
    if len(closes) < period + 1 or closes[-period] == 0:
        return None
    return ((closes[-1] - closes[-period]) / closes[-period]) * 100


def compute_volume_spike(bars: list[dict], period: int = 20) -> Optional[float]:
    if len(bars) < period + 1:
        return None
    avg_vol = sum(b["volume"] for b in bars[-period - 1 : -1]) / period
    return bars[-1]["volume"] / avg_vol if avg_vol else None


def compute_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Optional[tuple[float, float, float]]:
    """Returns (macd_line, signal_line, histogram) or None."""
    fast_ema = compute_ema(closes, fast)
    slow_ema = compute_ema(closes, slow)
    if fast_ema is None or slow_ema is None:
        return None
    macd_line = fast_ema - slow_ema
    # Approximate signal line from recent MACD values
    if len(closes) < slow + signal:
        return None
    macd_series = []
    for i in range(signal + slow, len(closes) + 1):
        f = compute_ema(closes[:i], fast)
        s = compute_ema(closes[:i], slow)
        if f is not None and s is not None:
            macd_series.append(f - s)
    if len(macd_series) < signal:
        return None
    sig = compute_ema(macd_series, signal)
    if sig is None:
        return None
    return (macd_line, sig, macd_line - sig)


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Detectors  — each auto-registers via @PatternRegistry.register
# ═══════════════════════════════════════════════════════════════════════════

@PatternRegistry.register(
    name="Momentum Breakout",
    categories=["major", "meme"],
    description="RSI > 60 + price above SMA20 + positive momentum. "
                "Meme coins require 10%+ momentum; majors 5%+.",
)
def detect_momentum_breakout(
    symbol: str, bars: list[dict], category: str
) -> Optional[dict]:
    closes = [b["close"] for b in bars]
    rsi = compute_rsi(closes, MOMENTUM_LOOKBACK)
    sma20 = compute_sma(closes, 20)
    momentum = compute_momentum_pct(closes, 24)
    vol_spike = compute_volume_spike(bars, 20)

    if rsi is None or sma20 is None or momentum is None:
        return None

    price = closes[-1]
    min_momentum = 10.0 if category == "meme" else 5.0

    if rsi > 60 and price > sma20 and momentum > min_momentum:
        p = CATEGORY_PARAMS[category]
        return {
            "name": f"Momentum Breakout — {_base(symbol)}",
            "asset_class": "Crypto",
            "strategy_type": "Momentum",
            "coin_category": category,
            "parameters": {
                "signal": "RSI_ABOVE_60_PLUS_SMA_BREAKOUT",
                "rsi": round(rsi, 2),
                "sma20": round(sma20, 6),
                "current_price": round(price, 6),
                "momentum_24h_pct": round(momentum, 2),
                "volume_spike_ratio": round(vol_spike, 2) if vol_spike else None,
                "coin_category": category,
                "entry": "market_buy_on_signal",
                **{k: v for k, v in p.items()},
            },
            "notes": (
                f"[{category.upper()}] Momentum breakout on {symbol}. "
                f"RSI={rsi:.1f}, 24h mom={momentum:.1f}%, "
                f"price {price:,.6f} > SMA20 {sma20:,.6f}. "
                f"Basis: time-series momentum (Moskowitz 2012)."
            ),
            "source": "pattern_detection",
            "priority": "High" if momentum > min_momentum * 2 else "Medium",
        }
    return None


@PatternRegistry.register(
    name="Mean Reversion Bounce",
    categories=["major"],
    description="RSI < 30 + price below lower Bollinger Band. "
                "Majors only — meme coins don't mean-revert reliably.",
)
def detect_mean_reversion(
    symbol: str, bars: list[dict], category: str
) -> Optional[dict]:
    closes = [b["close"] for b in bars]
    rsi = compute_rsi(closes, MOMENTUM_LOOKBACK)
    sma20 = compute_sma(closes, VOLATILITY_LOOKBACK)
    std20 = compute_std(closes, VOLATILITY_LOOKBACK)

    if rsi is None or sma20 is None or std20 is None:
        return None

    price = closes[-1]
    lower_band = sma20 - (MEAN_REVERSION_THRESHOLD * std20)

    if rsi < 30 and price < lower_band:
        p = CATEGORY_PARAMS[category]
        return {
            "name": f"Mean Reversion Bounce — {_base(symbol)}",
            "asset_class": "Crypto",
            "strategy_type": "Mean Reversion",
            "coin_category": category,
            "parameters": {
                "signal": "RSI_BELOW_30_PLUS_BOLLINGER_BREAK",
                "rsi": round(rsi, 2),
                "sma20": round(sma20, 6),
                "lower_bollinger": round(lower_band, 6),
                "current_price": round(price, 6),
                "coin_category": category,
                "entry": "market_buy_on_signal",
                **{k: v for k, v in p.items()},
            },
            "notes": (
                f"[{category.upper()}] Oversold on {symbol}. "
                f"RSI={rsi:.1f}, price below lower BB. "
                f"Basis: mean reversion (Gatev et al. 2006)."
            ),
            "source": "pattern_detection",
            "priority": "High",
        }
    return None


@PatternRegistry.register(
    name="Volatility Squeeze",
    categories=["major", "meme"],
    description="ATR/Price at multi-period low — consolidation before "
                "expansion. Threshold: 1% (major), 2% (meme).",
)
def detect_volatility_squeeze(
    symbol: str, bars: list[dict], category: str
) -> Optional[dict]:
    closes = [b["close"] for b in bars]
    atr = compute_atr(bars, VOLATILITY_LOOKBACK)
    if atr is None or not closes:
        return None

    price = closes[-1]
    if price == 0:
        return None
    atr_pct = (atr / price) * 100
    threshold = 2.0 if category == "meme" else 1.0

    if atr_pct < threshold:
        p = CATEGORY_PARAMS[category]
        return {
            "name": f"Volatility Squeeze — {_base(symbol)}",
            "asset_class": "Crypto",
            "strategy_type": "Volatility",
            "coin_category": category,
            "parameters": {
                "signal": "ATR_SQUEEZE",
                "atr_pct": round(atr_pct, 3),
                "squeeze_threshold_pct": threshold,
                "current_price": round(price, 6),
                "coin_category": category,
                "entry": "breakout_of_range",
                **{k: v for k, v in p.items()},
                "time_exit_hours": 72,
            },
            "notes": (
                f"[{category.upper()}] Squeeze on {symbol}. "
                f"ATR/Price={atr_pct:.2f}% < {threshold}%. "
                f"Basis: volatility clustering (Mandelbrot)."
            ),
            "source": "pattern_detection",
            "priority": "Medium",
        }
    return None


@PatternRegistry.register(
    name="Volume Divergence",
    categories=["major", "meme"],
    description="Price flat (<2% move) but volume >3x average. "
                "Often precedes a large directional move.",
)
def detect_volume_divergence(
    symbol: str, bars: list[dict], category: str
) -> Optional[dict]:
    closes = [b["close"] for b in bars]
    vol_spike = compute_volume_spike(bars, 20)
    momentum = compute_momentum_pct(closes, 24)

    if vol_spike is None or momentum is None:
        return None

    price = closes[-1]
    if abs(momentum) < 2.0 and vol_spike > 3.0:
        p = CATEGORY_PARAMS[category]
        return {
            "name": f"Volume Divergence — {_base(symbol)}",
            "asset_class": "Crypto",
            "strategy_type": "Volume Analysis",
            "coin_category": category,
            "parameters": {
                "signal": "PRICE_FLAT_VOLUME_SPIKE",
                "momentum_24h_pct": round(momentum, 2),
                "volume_spike_ratio": round(vol_spike, 2),
                "current_price": round(price, 6),
                "coin_category": category,
                "entry": "breakout_of_range",
                **{k: v for k, v in p.items()},
                "time_exit_hours": 24,
            },
            "notes": (
                f"[{category.upper()}] Volume divergence on {symbol}. "
                f"24h Δ={momentum:.1f}% but vol={vol_spike:.1f}x avg. "
                f"Basis: volume-price divergence analysis."
            ),
            "source": "pattern_detection",
            "priority": "High",
        }
    return None


@PatternRegistry.register(
    name="MACD Bullish Cross",
    categories=["major"],
    description="MACD line crosses above signal line while both are "
                "below zero — strong reversal signal on major coins.",
)
def detect_macd_bullish_cross(
    symbol: str, bars: list[dict], category: str
) -> Optional[dict]:
    closes = [b["close"] for b in bars]
    if len(closes) < 35:
        return None

    macd = compute_macd(closes)
    if macd is None:
        return None

    macd_line, signal_line, histogram = macd
    # Need previous histogram to confirm fresh cross
    prev_macd = compute_macd(closes[:-1])
    if prev_macd is None:
        return None

    _, _, prev_hist = prev_macd

    # Bullish cross: histogram flips positive and MACD below zero (recovery)
    if prev_hist < 0 and histogram > 0 and macd_line < 0:
        p = CATEGORY_PARAMS[category]
        price = closes[-1]
        return {
            "name": f"MACD Bullish Cross — {_base(symbol)}",
            "asset_class": "Crypto",
            "strategy_type": "Momentum",
            "coin_category": category,
            "parameters": {
                "signal": "MACD_BULLISH_CROSS_BELOW_ZERO",
                "macd_line": round(macd_line, 6),
                "signal_line": round(signal_line, 6),
                "histogram": round(histogram, 6),
                "current_price": round(price, 6),
                "coin_category": category,
                "entry": "market_buy_on_signal",
                **{k: v for k, v in p.items()},
            },
            "notes": (
                f"[{category.upper()}] MACD bullish cross below zero on {symbol}. "
                f"Histogram flipped from {prev_hist:.6f} → {histogram:.6f}. "
                f"Basis: MACD convergence/divergence indicator."
            ),
            "source": "pattern_detection",
            "priority": "Medium",
        }
    return None


@PatternRegistry.register(
    name="EMA Ribbon Expansion",
    categories=["major", "meme"],
    description="Short EMAs (8,13,21) all above long EMAs (55,100) and "
                "fanning out — confirms strong trend establishment.",
)
def detect_ema_ribbon_expansion(
    symbol: str, bars: list[dict], category: str
) -> Optional[dict]:
    closes = [b["close"] for b in bars]
    ema8 = compute_ema(closes, 8)
    ema13 = compute_ema(closes, 13)
    ema21 = compute_ema(closes, 21)
    ema55 = compute_ema(closes, 55)
    ema100 = compute_ema(closes, 100)

    if any(v is None for v in [ema8, ema13, ema21, ema55, ema100]):
        return None

    # All short EMAs above all long EMAs and properly ordered
    if ema8 > ema13 > ema21 > ema55 > ema100:
        # Calculate ribbon spread as % of price
        price = closes[-1]
        if price == 0:
            return None
        spread_pct = ((ema8 - ema100) / price) * 100

        if spread_pct > 2.0:  # meaningful fan-out
            p = CATEGORY_PARAMS[category]
            return {
                "name": f"EMA Ribbon Expansion — {_base(symbol)}",
                "asset_class": "Crypto",
                "strategy_type": "Trend",
                "coin_category": category,
                "parameters": {
                    "signal": "EMA_RIBBON_BULLISH_EXPANSION",
                    "ema8": round(ema8, 6),
                    "ema13": round(ema13, 6),
                    "ema21": round(ema21, 6),
                    "ema55": round(ema55, 6),
                    "ema100": round(ema100, 6),
                    "ribbon_spread_pct": round(spread_pct, 2),
                    "current_price": round(price, 6),
                    "coin_category": category,
                    "entry": "market_buy_on_confirmation",
                    **{k: v for k, v in p.items()},
                },
                "notes": (
                    f"[{category.upper()}] EMA ribbon fan-out on {symbol}. "
                    f"EMA8>13>21>55>100, spread={spread_pct:.1f}%. "
                    f"Basis: EMA ribbon trend confirmation."
                ),
                "source": "pattern_detection",
                "priority": "High",
            }
    return None


# ═══════════════════════════════════════════════════════════════════════════
# News-Triggered Strategy Generation
# ═══════════════════════════════════════════════════════════════════════════

def generate_news_driven_strategies() -> list[dict]:
    """
    Check market_news for CRITICAL/HIGH events not yet linked to a strategy.
    """
    all_symbols = discover_tradeable_crypto()
    symbol_set = {_base(s) for s in all_symbols}
    strategies = []

    with get_db_session() as session:
        news_items = (
            session.query(MarketNews)
            .filter(
                MarketNews.impact_rating.in_([
                    ImpactRating.CRITICAL, ImpactRating.HIGH,
                ]),
            )
            .order_by(MarketNews.discovered_at.desc())
            .limit(10)
            .all()
        )
        for news in news_items:
            if session.query(Strategy).filter_by(news_id=news.id).first():
                continue

            affected = [a.strip() for a in (news.affected_assets or "").split(",") if a.strip()]
            if not affected:
                affected = ["BTC"]

            for asset in affected[:3]:
                if asset not in symbol_set:
                    continue
                cat = classify_crypto(f"{asset}/USD")
                if cat == "stablecoin" and "depeg" not in (news.headline or "").lower():
                    continue
                if cat == "stablecoin":
                    cat = "major"

                p = CATEGORY_PARAMS.get(cat, CATEGORY_PARAMS["major"])
                is_critical = news.impact_rating == ImpactRating.CRITICAL
                strategies.append({
                    "name": f"NEWS-DRIVEN: {news.headline[:50]} — {asset}",
                    "asset_class": "Crypto",
                    "strategy_type": "News-Driven",
                    "coin_category": cat,
                    "parameters": {
                        "signal": "CRITICAL_NEWS_EVENT" if is_critical else "HIGH_IMPACT_NEWS",
                        "news_headline": news.headline[:100],
                        "news_impact": news.impact_rating.value,
                        "coin_category": cat,
                        "entry": "immediate_market_order" if is_critical else "limit_order_at_support",
                        "position_sizing": "reduced_due_to_uncertainty" if is_critical else p["position_sizing"],
                        "stop_loss_pct": max(p["stop_loss_pct"] - 1, 1.5) if is_critical else p["stop_loss_pct"],
                        "take_profit_pct": p["take_profit_pct"],
                        "time_exit_hours": 12 if is_critical else p["max_hold_hours"],
                    },
                    "notes": (
                        f"[{cat.upper()}] {'Critical' if is_critical else 'High-impact'} "
                        f"news: {news.headline}. Source: {news.source}. "
                        f"Affected: {asset}."
                    ),
                    "source": "news_triggered",
                    "priority": "High" if is_critical else "Medium",
                    "news_id": news.id,
                })
    return strategies


# ═══════════════════════════════════════════════════════════════════════════
# Write to Blackboard
# ═══════════════════════════════════════════════════════════════════════════

def store_strategies(ideas: list[dict]) -> int:
    if not ideas:
        return 0
    stored = 0
    with get_db_session() as session:
        for idea in ideas:
            if session.query(Strategy).filter_by(name=idea["name"]).first():
                continue
            session.add(Strategy(
                name=idea["name"],
                asset_class=idea.get("asset_class", "Crypto"),
                strategy_type=idea.get("strategy_type"),
                status=StrategyStatus.NEW,
                priority=idea.get("priority", "Medium"),
                parameters=idea.get("parameters"),
                source=idea.get("source", "pattern_detection"),
                notes=idea.get("notes"),
                news_id=idea.get("news_id"),
            ))
            stored += 1
            cat_tag = idea.get("coin_category", "?").upper()
            log.info(f"  ✓ [{cat_tag}] Strategy logged: '{idea['name']}'")
    return stored


# ═══════════════════════════════════════════════════════════════════════════
# Main Scan Cycle
# ═══════════════════════════════════════════════════════════════════════════

def run_scan(lookback_days: int = 7) -> int:
    log.info("═" * 60)
    log.info(
        f"Starting strategy research scan "
        f"({PatternRegistry.count()} registered pattern detectors)"
    )
    log.info("═" * 60)

    all_ideas: list[dict] = []

    # 1. Discover all tradeable crypto
    all_symbols = discover_tradeable_crypto()
    tradeable = [s for s in all_symbols if classify_crypto(s) != "stablecoin"]
    log.info(
        f"Phase 1: {len(tradeable)} tradeable symbols "
        f"(excluded {len(all_symbols) - len(tradeable)} stablecoins)"
    )

    # 2. Fetch live market data
    log.info("Phase 2: Fetching live crypto market data...")
    bars_data = fetch_crypto_bars(tradeable, lookback_days=lookback_days)

    # 3. Run registered pattern detectors
    log.info("Phase 3: Running pattern detection...")
    for symbol, bars in bars_data.items():
        if len(bars) < MIN_BARS_FOR_ANALYSIS:
            continue
        category = classify_crypto(symbol)
        for detector in PatternRegistry.for_category(category):
            try:
                idea = detector["fn"](symbol, bars, category)
                if idea:
                    all_ideas.append(idea)
            except Exception as e:
                log.warning(
                    f"Detector '{detector['name']}' failed on {symbol}: {e}"
                )
    log.info(f"Phase 3 complete: {len(all_ideas)} pattern(s) detected")

    # 4. News-driven
    log.info("Phase 4: Checking for news-driven opportunities...")
    news_ideas = generate_news_driven_strategies()
    all_ideas.extend(news_ideas)
    log.info(f"Phase 4 complete: {len(news_ideas)} news-driven idea(s)")

    # 5. Store
    stored = store_strategies(all_ideas)
    log.info(
        f"Scan complete: {stored} new strategy/ies stored "
        f"(total candidates: {len(all_ideas)})"
    )
    return stored


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Strategy Research Agent — Live Crypto Strategy Generator"
    )
    parser.add_argument(
        "--loop", type=int, default=0, metavar="SECS",
        help="Poll interval in seconds (0 = single scan).",
    )
    parser.add_argument(
        "--lookback", type=int, default=7, metavar="DAYS",
        help="Lookback period for historical bars. Default: 7",
    )
    parser.add_argument(
        "--list-patterns", action="store_true",
        help="List all registered pattern detectors and exit.",
    )
    args = parser.parse_args()

    if args.list_patterns:
        print(f"\n  Registered Pattern Detectors ({PatternRegistry.count()}):\n")
        for d in PatternRegistry.all():
            cats = ", ".join(sorted(d["categories"]))
            print(f"  • {d['name']:30s}  [{cats}]")
            if d["description"]:
                for line in d["description"].split(". "):
                    print(f"    {line.strip()}")
            print()
        return

    init_db()

    if args.loop > 0:
        log.info(
            f"Starting continuous strategy research "
            f"(every {args.loop}s, {PatternRegistry.count()} detectors). "
            f"Ctrl+C to stop."
        )
        try:
            while True:
                run_scan(lookback_days=args.lookback)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
    else:
        run_scan(lookback_days=args.lookback)


if __name__ == "__main__":
    main()
