"""
ORM Models for the TradeBot Blackboard

Every table in the shared SQLite database is defined here.
Agents import these models and use them via `get_db_session()`.

Schema version: 1.0
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from agents.common.enums import (
    StrategyStatus,
    RiskPolicy,
    ImpactRating,
    TradeSide,
    TradeStatus,
    OrderType,
    BrokerName,
    EventType,
    EventUrgency,
    PolicyTrigger,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# system_state — key/value runtime configuration (single-row per key)
# ---------------------------------------------------------------------------


class SystemState(Base):
    """
    Replaces: active_policy.json, portfolio_health.json

    Example keys:
        risk_mode         → "HIGH"
        active_broker     → "ALPACA"
        max_drawdown_limit→ "0.22"
        current_drawdown  → "0.05"
        vix_current       → "18.5"
    """

    __tablename__ = "system_state"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<SystemState {self.key}={self.value!r}>"


# ---------------------------------------------------------------------------
# market_news — replaces news_assessments_log.csv
# ---------------------------------------------------------------------------


class MarketNews(Base):
    """
    Replaces: data/logs/news_assessments_log.csv

    The Market News agent writes rows here.
    The Manager polls for processed_by_manager == False.
    """

    __tablename__ = "market_news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    headline = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    impact_rating = Column(SAEnum(ImpactRating), nullable=False)
    affected_assets = Column(Text, nullable=True)          # comma-separated
    opportunities_identified = Column(Text, nullable=True)
    sources_urls = Column(Text, nullable=True)              # comma-separated
    discovered_at = Column(DateTime, default=_utcnow)
    processed_by_manager = Column(Boolean, default=False)

    def __repr__(self):
        return f"<MarketNews {self.id}: {self.headline[:40]}>"


# ---------------------------------------------------------------------------
# strategies — replaces trade_ideas_log.csv (the core unit of work)
# ---------------------------------------------------------------------------


class Strategy(Base):
    """
    Replaces: data/logs/trade_ideas_log.csv

    This is the core lifecycle table.  Status transitions are managed
    exclusively by the Project Manager Agent via the Orchestrator.
    """

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    asset_class = Column(String, nullable=True)            # e.g. "Crypto", "Stocks"
    strategy_type = Column(String, nullable=True)          # e.g. "Breakout", "Mean Reversion"
    status = Column(SAEnum(StrategyStatus), nullable=False, default=StrategyStatus.NEW)
    priority = Column(String, nullable=True, default="Medium")
    parameters = Column(JSON, nullable=True)               # strategy logic/params
    source = Column(String, nullable=True)                 # where idea originated
    notes = Column(Text, nullable=True)
    news_id = Column(Integer, ForeignKey("market_news.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    backtest_results = relationship("BacktestResult", back_populates="strategy")
    trades = relationship("Trade", back_populates="strategy")
    news = relationship("MarketNews", foreign_keys=[news_id])

    def __repr__(self):
        return f"<Strategy {self.id}: {self.name} [{self.status.value}]>"


# ---------------------------------------------------------------------------
# backtest_results
# ---------------------------------------------------------------------------


class BacktestResult(Base):
    """Result metrics from a single backtest run."""

    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    trades_count = Column(Integer, nullable=True)
    total_return_pct = Column(Float, nullable=True)
    oos_performance_ratio = Column(Float, nullable=True)   # OOS / IS performance
    logs_path = Column(String, nullable=True)              # path to RESULTS.md
    run_at = Column(DateTime, default=_utcnow)

    # Relationships
    strategy = relationship("Strategy", back_populates="backtest_results")

    def __repr__(self):
        return f"<BacktestResult strategy={self.strategy_id} sharpe={self.sharpe_ratio}>"


# ---------------------------------------------------------------------------
# trades — replaces order_history.csv
# ---------------------------------------------------------------------------


class Trade(Base):
    """
    Replaces: data/logs/order_history.csv

    Written by the Broker (Trading) Agent after order execution.
    """

    __tablename__ = "trades"

    id = Column(String, primary_key=True)                  # order ID from broker
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    symbol = Column(String, nullable=False)
    side = Column(SAEnum(TradeSide), nullable=False)
    qty = Column(Float, nullable=False)
    order_type = Column(SAEnum(OrderType), nullable=True)
    limit_price = Column(Float, nullable=True)
    filled_qty = Column(Float, nullable=True)
    filled_price = Column(Float, nullable=True)
    status = Column(SAEnum(TradeStatus), nullable=False)
    broker = Column(SAEnum(BrokerName), nullable=True)
    commission = Column(Float, nullable=True, default=0.0)
    slippage_pct = Column(Float, nullable=True)
    risk_policy = Column(SAEnum(RiskPolicy), nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)

    # Relationships
    strategy = relationship("Strategy", back_populates="trades")

    def __repr__(self):
        return f"<Trade {self.id}: {self.side.value} {self.qty} {self.symbol}>"


# ---------------------------------------------------------------------------
# portfolio_snapshots — time-series portfolio metrics
# ---------------------------------------------------------------------------


class PortfolioSnapshot(Base):
    """
    Periodic portfolio health snapshots written by the Portfolio Tracker.
    Used by the Analytics Agent for trend analysis.
    """

    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=_utcnow)
    total_equity = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=True)
    buying_power = Column(Float, nullable=True)
    daily_pnl = Column(Float, nullable=True)
    drawdown_pct = Column(Float, nullable=True)
    vix_level = Column(Float, nullable=True)
    positions_count = Column(Integer, nullable=True)
    leverage = Column(Float, nullable=True)
    risk_policy = Column(SAEnum(RiskPolicy), nullable=True)

    def __repr__(self):
        return f"<PortfolioSnapshot {self.timestamp}: ${self.total_equity:,.2f}>"


# ---------------------------------------------------------------------------
# event_log — NEW: inter-agent communication backbone
# ---------------------------------------------------------------------------


class EventLog(Base):
    """
    Unified event/alert table for inter-agent communication.

    Replaces: recommendations_queue.json, ad-hoc alert mechanisms.

    Any agent can write events; the Manager polls for unacknowledged ones.
    """

    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(SAEnum(EventType), nullable=False)
    urgency = Column(SAEnum(EventUrgency), nullable=False, default=EventUrgency.INFO)
    source_agent = Column(String, nullable=False)          # who emitted
    target_agent = Column(String, nullable=True)           # intended recipient (NULL = broadcast)
    summary = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)                  # structured payload
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, nullable=True)
    response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    acknowledged_at = Column(DateTime, nullable=True)

    def __repr__(self):
        ack = "✓" if self.acknowledged else "✗"
        return f"<EventLog [{ack}] {self.event_type.value} from {self.source_agent}>"


# ---------------------------------------------------------------------------
# policy_history — NEW: risk policy change audit trail
# ---------------------------------------------------------------------------


class PolicyHistory(Base):
    """
    Audit trail for every risk policy change.

    Replaces: policy_switch_log.csv (from DATA_SCHEMAS.md).
    """

    __tablename__ = "policy_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=_utcnow)
    old_policy = Column(SAEnum(RiskPolicy), nullable=False)
    new_policy = Column(SAEnum(RiskPolicy), nullable=False)
    changed_by = Column(String, nullable=False)            # "Manager" or "Portfolio Tracker"
    reason = Column(Text, nullable=False)
    vix_level = Column(Float, nullable=True)
    drawdown_pct = Column(Float, nullable=True)
    trigger_type = Column(SAEnum(PolicyTrigger), nullable=True)

    def __repr__(self):
        return f"<PolicyHistory {self.old_policy.value}→{self.new_policy.value} by {self.changed_by}>"


# ---------------------------------------------------------------------------
# crypto_liquidations — real-time liquidation events from Hyperliquid / CoinGlass
# ---------------------------------------------------------------------------


class CryptoLiquidation(Base):
    """
    Individual liquidation events captured by the Crypto Liquidation Agent.

    Written in real-time from the Hyperliquid WebSocket stream.
    """

    __tablename__ = "crypto_liquidations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)           # "Buy" or "Sell"
    price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    usd_value = Column(Float, nullable=False)
    is_cascade = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        return f"<CryptoLiquidation {self.symbol} {self.side} ${self.usd_value:,.0f}>"


# ---------------------------------------------------------------------------
# whale_trades — large trades detected by the Crypto Liquidation Agent
# ---------------------------------------------------------------------------


class WhaleTrade(Base):
    """
    Whale-sized trades (≥ $1M notional) captured from the Hyperliquid public trade stream.

    Written in real-time by the Crypto Liquidation Agent.
    """

    __tablename__ = "whale_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)           # "Buy" or "Sell"
    price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    usd_value = Column(Float, nullable=False)
    is_cluster = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        return f"<WhaleTrade {self.symbol} {self.side} ${self.usd_value:,.0f}>"


# ---------------------------------------------------------------------------
# crypto_liquidation_summary — hourly aggregated liquidation stats
# ---------------------------------------------------------------------------


class CryptoLiquidationSummary(Base):
    """
    Hourly aggregated liquidation and whale statistics.

    Created by the pruning/rollup task before raw rows older than
    7 days are deleted from crypto_liquidations & whale_trades.
    Keeps historical trends available indefinitely at low storage cost.
    """

    __tablename__ = "crypto_liquidation_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hour = Column(DateTime, nullable=False)             # start of the hour bucket
    symbol = Column(String, nullable=False)

    # Liquidation aggregates
    liq_count = Column(Integer, default=0)
    liq_total_usd = Column(Float, default=0.0)
    liq_long_usd = Column(Float, default=0.0)           # "Sell" side liquidations
    liq_short_usd = Column(Float, default=0.0)          # "Buy" side liquidations
    liq_max_single_usd = Column(Float, default=0.0)
    cascade_count = Column(Integer, default=0)

    # Whale aggregates
    whale_count = Column(Integer, default=0)
    whale_total_usd = Column(Float, default=0.0)
    whale_buy_usd = Column(Float, default=0.0)
    whale_sell_usd = Column(Float, default=0.0)
    cluster_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        return f"<LiqSummary {self.symbol} {self.hour} liqs={self.liq_count} whales={self.whale_count}>"
