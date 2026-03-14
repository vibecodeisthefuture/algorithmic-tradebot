"""
Shared Enums for TradeBot

Single canonical source for all status values and categories used across agents.
These enums are used both as Python types and as SQLAlchemy column types.
"""

import enum


# ---------------------------------------------------------------------------
# Strategy Lifecycle
# ---------------------------------------------------------------------------


class StrategyStatus(str, enum.Enum):
    """Strategy lifecycle states — managed by the Project Manager."""

    NEW = "NEW"
    READY_FOR_BACKTEST = "READY_FOR_BACKTEST"
    BACKTESTING = "BACKTESTING"
    BACKTEST_COMPLETE = "BACKTEST_COMPLETE"
    LIVE_PAPER = "LIVE_PAPER"
    LIVE_REAL = "LIVE_REAL"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"


# ---------------------------------------------------------------------------
# Risk Management
# ---------------------------------------------------------------------------


class RiskPolicy(str, enum.Enum):
    """Four-tier risk policy system (per RISK_POLICY_FRAMEWORK.md)."""

    HIGH = "HIGH"
    MODERATE_AGGRESSIVE = "MODERATE_AGGRESSIVE"
    MODERATE = "MODERATE"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# Market News
# ---------------------------------------------------------------------------


class ImpactRating(str, enum.Enum):
    """News event impact severity."""

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Trade Execution
# ---------------------------------------------------------------------------


class TradeSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    BRACKET = "BRACKET"


# ---------------------------------------------------------------------------
# Broker Routing
# ---------------------------------------------------------------------------


class BrokerName(str, enum.Enum):
    ALPACA = "ALPACA"
    IBKR = "IBKR"
    OKX = "OKX"
    BYBIT = "BYBIT"


# ---------------------------------------------------------------------------
# Predictions Agent — Signal & Regime Contracts
# ---------------------------------------------------------------------------


class PredictionSignal(str, enum.Enum):
    """
    Directional signal emitted by the Predictions Agent ensemble.

    Consumers (Strategy Agent, Portfolio Tracker) should only act on
    signals accompanied by ensemble confidence >= 0.6.
    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketRegime(str, enum.Enum):
    """
    Market regime label produced by the HMM Regime Detector.

    The regime gates which forecasting models are activated each cycle:
      BULL    → LightGBM, LSTM, Prophet active; ARIMA suppressed
      BEAR    → ARIMA, Monte Carlo active; LightGBM/Prophet suppressed
      NEUTRAL → all models active; ensemble weights equal
    """

    BULL = "BULL"
    NEUTRAL = "NEUTRAL"
    BEAR = "BEAR"


# ---------------------------------------------------------------------------
# Inter-Agent Events
# ---------------------------------------------------------------------------


class EventType(str, enum.Enum):
    """Types of events agents can emit/consume via the event_log table."""

    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    REGIME_CHANGE = "REGIME_CHANGE"
    POLICY_SWITCH = "POLICY_SWITCH"
    CORRELATION_WARNING = "CORRELATION_WARNING"
    LIQUIDITY_WARNING = "LIQUIDITY_WARNING"
    STRATEGY_VALIDATED = "STRATEGY_VALIDATED"
    STRATEGY_REJECTED = "STRATEGY_REJECTED"
    ORDER_EXECUTED = "ORDER_EXECUTED"
    ORDER_FAILED = "ORDER_FAILED"
    NEWS_CRITICAL = "NEWS_CRITICAL"
    LIQUIDATION_CASCADE = "LIQUIDATION_CASCADE"
    WHALE_CLUSTER = "WHALE_CLUSTER"
    PREDICTION_SIGNAL = "PREDICTION_SIGNAL"   # Predictions Agent high-confidence signal
    MODEL_ACCURACY_WARNING = "MODEL_ACCURACY_WARNING"  # Model rolling accuracy < 52%


class EventUrgency(str, enum.Enum):
    INFO = "INFO"
    CAUTION = "CAUTION"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Policy Change Triggers
# ---------------------------------------------------------------------------


class PolicyTrigger(str, enum.Enum):
    """What caused a risk policy switch."""

    MANUAL = "MANUAL"
    VIX = "VIX"
    DRAWDOWN = "DRAWDOWN"
    REGIME = "REGIME"
    EMERGENCY = "EMERGENCY"
