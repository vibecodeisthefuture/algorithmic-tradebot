"""
TradeBot Common Package

Shared database layer, ORM models, enums, and ZeroMQ event bus
used by all agents.
"""

from agents.common.enums import (
    StrategyStatus,
    RiskPolicy,
    ImpactRating,
    TradeSide,
    TradeStatus,
    EventType,
    EventUrgency,
)

# ZeroMQ event bus — optional (graceful no-op if pyzmq is not installed)
try:
    from agents.common.event_bus import (
        EventPublisher,
        EventSubscriber,
        TOPIC_CIRCUIT_BREAKER,
        TOPIC_POLICY_SWITCH,
        TOPIC_NEWS_CRITICAL,
        TOPIC_NEWS_HIGH,
        TOPIC_NEWS_SENTIMENT_SHIFT,
        TOPIC_LIQUIDATION_CASCADE,
        TOPIC_WHALE_CLUSTER,
        TOPIC_STRATEGY_UPDATE,
        TOPIC_TRADE_EXECUTED,
        TOPIC_TRADE_FAILED,
        TOPIC_PORTFOLIO_ALERT,
        TOPIC_BACKTEST_FAILED,
    )
    _HAS_ZMQ = True
except ImportError:
    _HAS_ZMQ = False

__all__ = [
    # Enums
    "StrategyStatus",
    "RiskPolicy",
    "ImpactRating",
    "TradeSide",
    "TradeStatus",
    "EventType",
    "EventUrgency",
    # Event bus (available when pyzmq installed)
    "EventPublisher",
    "EventSubscriber",
    "TOPIC_CIRCUIT_BREAKER",
    "TOPIC_POLICY_SWITCH",
    "TOPIC_NEWS_CRITICAL",
    "TOPIC_NEWS_HIGH",
    "TOPIC_NEWS_SENTIMENT_SHIFT",
    "TOPIC_LIQUIDATION_CASCADE",
    "TOPIC_WHALE_CLUSTER",
    "TOPIC_STRATEGY_UPDATE",
    "TOPIC_TRADE_EXECUTED",
    "TOPIC_TRADE_FAILED",
    "TOPIC_PORTFOLIO_ALERT",
    "TOPIC_BACKTEST_FAILED",
]
