"""
Risk Override System - Authoritative Risk Policy Enforcement
=============================================================

This module enforces risk tolerance policies with support for four-tier
risk profiles: HIGH (80/20), MODERATE-AGGRESSIVE (65/35), MODERATE (60/40), LOW (30/70).

AI agents can dynamically switch between policies based on market conditions
or portfolio performance.

Author: AI Trading System
Version: 3.0
Last Updated: 2026-02-05
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Add broker interface to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from broker_interface import BrokerInterface, BrokerFactory, TradingMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RiskPolicyViolation(Exception):
    """Raised when a trade violates risk policy"""
    pass


class RiskProfile(Enum):
    """Available risk tolerance profiles"""
    HIGH = "HIGH"  # 80/20 growth/preservation - Opportunistic
    MODERATE_AGGRESSIVE = "MODERATE_AGGRESSIVE"  # 65/35 growth-focused - DEFAULT
    MODERATE = "MODERATE"  # 60/40 balanced - Defensive buffer
    LOW = "LOW"  # 30/70 preservation priority - Survival


class ValidationStatus(Enum):
    """Status of risk validation"""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"


@dataclass
class RiskPolicyConfig:
    """Configuration for a specific risk tolerance profile"""
    profile: RiskProfile
    max_drawdown: float
    circuit_breaker_drawdown: float
    max_leverage: float
    min_cash_buffer: float
    single_position_max: float
    sector_concentration_max: float
    strategy_concentration_max: float
    position_size_limits: Dict[str, Dict[str, float]]  # Risk level -> {max_single, max_total}
    vix_multipliers: List[Tuple[float, float]]  # [(vix_threshold, multiplier)]
    drawdown_limits: Dict[float, Tuple[str, str, float]]  # threshold -> (level, description, multiplier)
    concentration_limits: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        data = asdict(self)
        data['profile'] = self.profile.value
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'RiskPolicyConfig':
        """Load config from dictionary"""
        data['profile'] = RiskProfile(data['profile'])
        return RiskPolicyConfig(**data)


@dataclass
class RiskOverrideDecision:
    """Result of risk validation"""
    status: ValidationStatus
    reasons: List[str]
    vix_level: Optional[float] = None
    portfolio_drawdown: Optional[float] = None
    position_size_pct: Optional[float] = None
    adjusted_position_size: Optional[float] = None
    
    def __str__(self):
        return f"{self.status.value}: {', '.join(self.reasons)}"


class PortfolioHealthMonitor:
    """Monitors current portfolio health and metrics

    Supports both paper trading (Alpaca) and live trading (IBKR) via broker abstraction.
    """

    HEALTH_FILE = os.path.join(os.path.dirname(__file__), 'portfolio_health.json')

    def __init__(self, broker: Optional[BrokerInterface] = None,
                 trading_mode: TradingMode = TradingMode.PAPER):
        """
        Initialize portfolio health monitor

        Args:
            broker: Broker interface instance (uses factory if None)
            trading_mode: PAPER (Alpaca) or LIVE (IBKR) - default is PAPER for safety
        """
        if broker:
            self.broker = broker
        else:
            self.broker = BrokerFactory.get_broker_for_mode(trading_mode)

        self.trading_mode = self.broker.trading_mode
        logger.info(f"PortfolioHealthMonitor initialized with {self.broker.broker_type.value} ({self.trading_mode.value})")

    def get_portfolio_value(self) -> float:
        """Get current portfolio value from broker"""
        try:
            portfolio_value = self.broker.get_portfolio_value()
            logger.info(f"Portfolio value from {self.broker.broker_type.value}: ${portfolio_value:,.2f}")
            return portfolio_value
        except Exception as e:
            logger.error(f"Error fetching portfolio value: {e}")
            return 100000.0  # Default fallback

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current portfolio positions from broker"""
        try:
            positions = self.broker.get_positions()
            # Convert NormalizedPosition to dict format
            position_list = []
            for pos in positions:
                position_list.append({
                    "symbol": pos.symbol,
                    "qty": pos.qty,
                    "market_value": pos.market_value,
                    "cost_basis": pos.cost_basis,
                    "unrealized_pl": pos.unrealized_pl,
                    "side": pos.side,
                    "avg_entry_price": pos.avg_entry_price
                })
            return position_list
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def load_historical_health(self) -> Dict[str, Any]:
        """Load historical portfolio health metrics from JSON"""
        if os.path.exists(self.HEALTH_FILE):
            try:
                with open(self.HEALTH_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading portfolio health: {e}")
        
        # Initialize with defaults
        return {
            "peak_value": 100000.0,
            "peak_date": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    
    def save_historical_health(self, health_data: Dict[str, Any]):
        """Save portfolio health metrics to JSON"""
        try:
            health_data["last_updated"] = datetime.now().isoformat()
            with open(self.HEALTH_FILE, 'w') as f:
                json.dump(health_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving portfolio health: {e}")
    
    def calculate_drawdown(self) -> float:
        """Calculate current drawdown from peak"""
        current_value = self.get_portfolio_value()
        health = self.load_historical_health()
        peak_value = health.get("peak_value", current_value)
        
        # Update peak if current value is higher
        if current_value > peak_value:
            peak_value = current_value
            health["peak_value"] = peak_value
            health["peak_date"] = datetime.now().isoformat()
            self.save_historical_health(health)
        
        # Calculate drawdown percentage
        if peak_value > 0:
            drawdown = ((peak_value - current_value) / peak_value) * 100
            return drawdown
        return 0.0
    
    def get_exposure_by_risk_level(self) -> Dict[str, float]:
        """Calculate total exposure by risk level"""
        positions = self.get_positions()
        portfolio_value = self.get_portfolio_value()
        
        exposure = {}
        for pos in positions:
            # Extract position value
            market_value = abs(float(pos.get("market_value", 0)))
            risk_level = pos.get("risk_level", "unknown")  # Would need to be tagged
            
            exposure[risk_level] = exposure.get(risk_level, 0) + market_value
        
        # Convert to percentages
        for level in exposure:
            exposure[level] = (exposure[level] / portfolio_value) * 100 if portfolio_value > 0 else 0
        
        return exposure
    
    def get_concentration_metrics(self) -> Dict[str, Any]:
        """Calculate concentration ratios"""
        positions = self.get_positions()
        portfolio_value = self.get_portfolio_value()
        
        if not positions or portfolio_value == 0:
            return {
                "max_position_pct": 0,
                "sector_exposure": {},
                "strategy_exposure": {},
                "total_leverage": 1.0
            }
        
        # Single position concentration
        max_position = 0
        sector_exposure = {}
        strategy_exposure = {}
        total_exposure = 0
        
        for pos in positions:
            market_value = abs(float(pos.get("market_value", 0)))
            position_pct = (market_value / portfolio_value) * 100
            
            max_position = max(max_position, position_pct)
            total_exposure += market_value
            
            # Sector tracking (would need to be tagged in positions)
            sector = pos.get("sector", "Unknown")
            sector_exposure[sector] = sector_exposure.get(sector, 0) + position_pct
            
            # Strategy type tracking
            strategy = pos.get("strategy_type", "Unknown")
            strategy_exposure[strategy] = strategy_exposure.get(strategy, 0) + position_pct
        
        leverage = total_exposure / portfolio_value if portfolio_value > 0 else 1.0
        
        return {
            "max_position_pct": max_position,
            "sector_exposure": sector_exposure,
            "strategy_exposure": strategy_exposure,
            "total_leverage": leverage
        }
    
    def get_portfolio_health(self) -> Dict[str, Any]:
        """Get complete portfolio health snapshot"""
        return {
            "portfolio_value": self.get_portfolio_value(),
            "drawdown_pct": self.calculate_drawdown(),
            "exposure_by_risk": self.get_exposure_by_risk_level(),
            "concentration": self.get_concentration_metrics(),
            "timestamp": datetime.now().isoformat()
        }


class PolicyManager:
    """Manages risk policy configurations and switching"""
    
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'active_policy.json')
    
    # Policy configurations
    POLICIES = {
        RiskProfile.HIGH: RiskPolicyConfig(
            profile=RiskProfile.HIGH,
            max_drawdown=35.0,
            circuit_breaker_drawdown=25.0,
            max_leverage=3.0,
            min_cash_buffer=1.0,
            single_position_max=30.0,
            sector_concentration_max=50.0,
            strategy_concentration_max=60.0,
            position_size_limits={
                "0-2": {"max_single": 35, "max_total": 90},
                "3-4": {"max_single": 20, "max_total": 60},
                "5-6": {"max_single": 10, "max_total": 35},
                "7-8": {"max_single": 3, "max_total": 12},
                "9": {"max_single": 1, "max_total": 3},
                "10": {"max_single": 0, "max_total": 0},
            },
            vix_multipliers=[
                (15, 1.30), (20, 1.20), (25, 1.05), (30, 0.85),
                (35, 0.60), (45, 0.35), (float('inf'), 0.20)
            ],
            drawdown_limits={
                12: ("MONITORING", "Review positions", 1.0),
                18: ("CAUTION", "Caution monitoring", 0.90),
                25: ("CRITICAL", "Circuit breaker: reduce exposure 30%", 0.70),
                35: ("CRISIS", "Emergency stop: close risky positions", 0.0),
            },
            concentration_limits={
                "single_position": 30,
                "single_sector": 50,
                "single_strategy": 60,
                "options_premium": 40,
                "max_leverage": 3.0,
                "max_total_exposure": 99
            }
        ),
        RiskProfile.MODERATE_AGGRESSIVE: RiskPolicyConfig(
            profile=RiskProfile.MODERATE_AGGRESSIVE,
            max_drawdown=20.0,
            circuit_breaker_drawdown=15.0,
            max_leverage=2.5,
            min_cash_buffer=5.0,
            single_position_max=25.0,
            sector_concentration_max=45.0,
            strategy_concentration_max=50.0,
            position_size_limits={
                "0-2": {"max_single": 30, "max_total": 80},
                "3-4": {"max_single": 18, "max_total": 55},
                "5-6": {"max_single": 8, "max_total": 30},
                "7-8": {"max_single": 2.5, "max_total": 11},
                "9": {"max_single": 0.75, "max_total": 2.5},
                "10": {"max_single": 0, "max_total": 0},
            },
            vix_multipliers=[
                (15, 1.25), (20, 1.10), (25, 0.95), (30, 0.75),
                (35, 0.50), (45, 0.30), (float('inf'), 0.15)
            ],
            drawdown_limits={
                5: ("MONITORING", "Monitor closely", 1.0),
                8: ("MONITORING", "Review positions", 0.95),
                12: ("REVIEW", "Review sizing", 0.85),
                15: ("CRITICAL", "Circuit breaker: reduce exposure 30%", 0.70),
                18: ("CRISIS", "Emergency: reduce exposure 60%", 0.40),
                20: ("EMERGENCY", "Emergency stop: close risky positions", 0.20),
            },
            concentration_limits={
                "single_position": 25,
                "single_sector": 45,
                "single_strategy": 50,
                "options_premium": 30,
                "max_leverage": 2.5,
                "max_total_exposure": 95,
                "liquidity_tier_1_2_min": 20,  # NEW
                "portfolio_volatility_max": 20,  # NEW
                "avg_correlation_max": 0.40,  # NEW
            }
        ),
        RiskProfile.MODERATE: RiskPolicyConfig(
            profile=RiskProfile.MODERATE,
            max_drawdown=25.0,
            circuit_breaker_drawdown=18.0,
            max_leverage=2.0,
            min_cash_buffer=3.0,
            single_position_max=20.0,
            sector_concentration_max=35.0,
            strategy_concentration_max=45.0,
            position_size_limits={
                "0-2": {"max_single": 25, "max_total": 70},
                "3-4": {"max_single": 12, "max_total": 45},
                "5-6": {"max_single": 6, "max_total": 25},
                "7-8": {"max_single": 2, "max_total": 10},
                "9": {"max_single": 0.5, "max_total": 2},
                "10": {"max_single": 0, "max_total": 0},
            },
            vix_multipliers=[
                (15, 1.15), (20, 1.05), (25, 0.90), (30, 0.70),
                (35, 0.45), (45, 0.25), (float('inf'), 0.12)
            ],
            drawdown_limits={
                8: ("MONITORING", "Review positions", 1.0),
                12: ("CAUTION", "Reduce new sizing 20%", 0.80),
                18: ("CRITICAL", "Circuit breaker: reduce exposure 40%", 0.60),
                25: ("CRISIS", "Emergency stop: defensive positions", 0.25),
            },
            concentration_limits={
                "single_position": 20,
                "single_sector": 35,
                "single_strategy": 45,
                "options_premium": 25,
                "max_leverage": 2.0,
                "max_total_exposure": 97
            }
        ),
        RiskProfile.LOW: RiskPolicyConfig(
            profile=RiskProfile.LOW,
            max_drawdown=15.0,
            circuit_breaker_drawdown=10.0,
            max_leverage=1.2,
            min_cash_buffer=10.0,
            single_position_max=12.0,
            sector_concentration_max=25.0,
            strategy_concentration_max=35.0,
            position_size_limits={
                "0-2": {"max_single": 15, "max_total": 50},
                "3-4": {"max_single": 8, "max_total": 30},
                "5-6": {"max_single": 4, "max_total": 15},
                "7-8": {"max_single": 1, "max_total": 5},
                "9": {"max_single": 0.25, "max_total": 1},
                "10": {"max_single": 0, "max_total": 0},
            },
            vix_multipliers=[
                (15, 1.05), (20, 0.95), (25, 0.75), (30, 0.50),
                (35, 0.30), (45, 0.15), (float('inf'), 0.05)
            ],
            drawdown_limits={
                5: ("MONITORING", "Review positions, tighten stops", 0.90),
                8: ("CAUTION", "Reduce new sizing 40%", 0.60),
                10: ("CRITICAL", "Circuit breaker: reduce exposure 50%", 0.50),
                15: ("CRISIS", "Emergency stop: close non-core positions", 0.20),
            },
            concentration_limits={
                "single_position": 12,
                "single_sector": 25,
                "single_strategy": 35,
                "options_premium": 15,
                "max_leverage": 1.2,
                "max_total_exposure": 90
            }
        )
    }
    
    @staticmethod
    def get_active_policy() -> RiskProfile:
        """Get currently active risk policy"""
        if os.path.exists(PolicyManager.CONFIG_FILE):
            try:
                with open(PolicyManager.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    return RiskProfile(data.get('active_policy', 'MODERATE_AGGRESSIVE'))
            except Exception as e:
                logger.warning(f"Error loading active policy: {e}")
        return RiskProfile.MODERATE_AGGRESSIVE  # Default to moderate-aggressive
    
    @staticmethod
    def set_active_policy(profile: RiskProfile, reason: str = "") -> None:
        """Set active risk policy (for AI agent to switch policies)"""
        try:
            data = {
                'active_policy': profile.value,
                'changed_at': datetime.now().isoformat(),
                'reason': reason
            }
            with open(PolicyManager.CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Risk policy changed to {profile.value}. Reason: {reason}")
        except Exception as e:
            logger.error(f"Error saving active policy: {e}")
    
    @staticmethod
    def get_policy_config(profile: RiskProfile) -> RiskPolicyConfig:
        """Get configuration for specific policy"""
        return PolicyManager.POLICIES[profile]


class RiskPolicyValidator:
    """Main validator that enforces risk tolerance policy

    Supports both paper trading (Alpaca) and live trading (IBKR) via broker abstraction.
    """

    def __init__(self, broker: Optional[BrokerInterface] = None,
                 policy_profile: Optional[RiskProfile] = None,
                 trading_mode: TradingMode = TradingMode.PAPER):
        """
        Initialize validator with optional policy override

        Args:
            broker: Broker interface instance (uses factory if None)
            policy_profile: Override default policy profile
            trading_mode: PAPER (Alpaca) or LIVE (IBKR) - default is PAPER for safety
        """
        if broker:
            self.broker = broker
        else:
            self.broker = BrokerFactory.get_broker_for_mode(trading_mode)

        self.health_monitor = PortfolioHealthMonitor(broker=self.broker)
        self.vix_conid = None

        # Load active policy or use override
        self.policy_profile = policy_profile or PolicyManager.get_active_policy()
        self.config = PolicyManager.get_policy_config(self.policy_profile)

        logger.info(f"Risk validator initialized with {self.policy_profile.value} policy ({self.broker.broker_type.value})")
    
    def switch_policy(self, new_profile: RiskProfile, reason: str = "") -> None:
        """Switch to a different risk policy (AI agent control)"""
        old_profile = self.policy_profile
        self.policy_profile = new_profile
        self.config = PolicyManager.get_policy_config(new_profile)
        PolicyManager.set_active_policy(new_profile, reason)
        
        logger.warning(f"POLICY SWITCH: {old_profile.value} -> {new_profile.value}")
        logger.warning(f"Reason: {reason}")
    
    def get_current_policy(self) -> Dict[str, Any]:
        """Get current policy information"""
        return {
            "profile": self.policy_profile.value,
            "max_drawdown": self.config.max_drawdown,
            "circuit_breaker": self.config.circuit_breaker_drawdown,
            "max_leverage": self.config.max_leverage,
            "single_position_max": self.config.single_position_max
        }
    
    # Legacy attribute mapping for backward compatibility
    @property
    def POSITION_SIZE_LIMITS(self):
        """Map risk level to position size limits from config"""
        return self._convert_position_limits(self.config.position_size_limits)
    
    @property
    def VIX_MULTIPLIERS(self):
        """Get VIX multipliers from config"""
        return self.config.vix_multipliers
    
    @property
    def DRAWDOWN_LIMITS(self):
        """Get drawdown limits from config"""
        return self.config.drawdown_limits
    
    @property
    def CONCENTRATION_LIMITS(self):
        """Get concentration limits from config"""
        return self.config.concentration_limits
    
    def _convert_position_limits(self, limits: Dict[str, Dict]) -> Dict[int, Dict]:
        """Convert string-based risk levels to integers"""
        result = {}
        for risk_range, values in limits.items():
            if '-' in risk_range:
                start, end = map(int, risk_range.split('-'))
                for i in range(start, end + 1):
                    result[i] = values
            else:
                result[int(risk_range)] = values
        return result
    
    def get_vix_level(self) -> float:
        """
        Fetch current VIX level using yfinance
        
        Priority:
        1. yfinance (^VIX symbol)
        2. Default conservative value (20.0)
        """
        # Try yfinance for VIX data
        
        # Fallback to yfinance
        try:
            import yfinance as yf
            logger.info("Attempting VIX retrieval from yfinance (backup source)...")
            
            vix_ticker = yf.Ticker("^VIX")
            vix_data = vix_ticker.history(period="1d")
            
            if not vix_data.empty:
                # Get the most recent close price
                vix_level = vix_data['Close'].iloc[-1]
                logger.info(f"VIX from yfinance: {vix_level:.2f}")
                return float(vix_level)
            else:
                logger.warning("yfinance returned empty VIX data")
        except ImportError:
            logger.warning("yfinance not installed. Install with: pip install yfinance")
        except Exception as e:
            logger.warning(f"yfinance VIX fetch failed: {e}")
        
        # Final fallback to conservative default
        logger.warning("All VIX sources failed, using conservative default VIX=20.0")
        return 20.0
    
    def apply_vix_adjustment(self, base_position_size: float, vix_level: float) -> float:
        """Apply VIX-based position sizing multiplier"""
        for vix_threshold, multiplier in self.VIX_MULTIPLIERS:
            if vix_level < vix_threshold:
                adjusted = base_position_size * multiplier
                logger.info(f"VIX {vix_level:.2f}: Applying {multiplier:.0%} multiplier -> {adjusted:.2f}%")
                return adjusted
        
        return base_position_size
    
    def check_drawdown_circuit_breaker(self, drawdown_pct: float) -> Tuple[bool, str, float]:
        """
        Check if drawdown triggers circuit breaker
        
        Returns:
            (is_violated, level_name, position_multiplier)
        """
        for threshold, (level, description, multiplier) in sorted(self.DRAWDOWN_LIMITS.items()):
            if drawdown_pct >= threshold:
                is_violated = threshold >= 22  # Critical or Crisis
                return is_violated, f"{level}: {description}", multiplier
        
        return False, "NORMAL: No drawdown restrictions", 1.0
    
    def check_position_sizing(self, risk_level: int, position_value: float,
                             portfolio_value: float) -> Tuple[bool, List[str]]:
        """
        Validate position size against risk level limits
        
        Returns:
            (is_valid, reasons)
        """
        reasons = []
        limits = self.POSITION_SIZE_LIMITS.get(risk_level)
        
        if not limits:
            reasons.append(f"Invalid risk level: {risk_level}")
            return False, reasons
        
        position_pct = (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0
        max_single = limits["max_single"]
        
        if max_single == 0:
            reasons.append(f"Risk Level {risk_level} is PROHIBITED (0% position limit)")
            return False, reasons
        
        if position_pct > max_single:
            reasons.append(
                f"Position size {position_pct:.2f}% exceeds max {max_single}% for Risk Level {risk_level}"
            )
            return False, reasons
        
        return True, reasons
    
    def check_concentration_limits(self, symbol: str, sector: str, strategy_type: str,
                                   position_value: float) -> Tuple[bool, List[str]]:
        """
        Check concentration limits
        
        Returns:
            (is_valid, reasons)
        """
        reasons = []
        concentration = self.health_monitor.get_concentration_metrics()
        portfolio_value = self.health_monitor.get_portfolio_value()
        
        position_pct = (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0
        
        # Single position limit
        if position_pct > self.CONCENTRATION_LIMITS["single_position"]:
            reasons.append(
                f"Position {position_pct:.2f}% exceeds single position limit "
                f"{self.CONCENTRATION_LIMITS['single_position']}%"
            )
        
        # Sector concentration
        current_sector_exposure = concentration["sector_exposure"].get(sector, 0)
        new_sector_exposure = current_sector_exposure + position_pct
        if new_sector_exposure > self.CONCENTRATION_LIMITS["single_sector"]:
            reasons.append(
                f"Sector '{sector}' exposure would be {new_sector_exposure:.2f}%, "
                f"exceeds limit {self.CONCENTRATION_LIMITS['single_sector']}%"
            )
        
        # Strategy type concentration
        current_strategy_exposure = concentration["strategy_exposure"].get(strategy_type, 0)
        new_strategy_exposure = current_strategy_exposure + position_pct
        if new_strategy_exposure > self.CONCENTRATION_LIMITS["single_strategy"]:
            reasons.append(
                f"Strategy '{strategy_type}' exposure would be {new_strategy_exposure:.2f}%, "
                f"exceeds limit {self.CONCENTRATION_LIMITS['single_strategy']}%"
            )
        
        # Leverage check
        if concentration["total_leverage"] > self.CONCENTRATION_LIMITS["max_leverage"]:
            reasons.append(
                f"Portfolio leverage {concentration['total_leverage']:.2f}x exceeds "
                f"max {self.CONCENTRATION_LIMITS['max_leverage']}x"
            )
        
        is_valid = len(reasons) == 0
        return is_valid, reasons
    
    def check_emergency_protocols(self, vix_level: float) -> Tuple[bool, List[str]]:
        """
        Check for emergency protocol triggers
        
        Returns:
            (is_triggered, warnings)
        """
        warnings = []
        
        # Volatility spike protocol (VIX > 30)
        if vix_level > 30:
            warnings.append(
                f"VOLATILITY SPIKE PROTOCOL: VIX {vix_level:.2f} > 30. "
                "All new positions suspended except hedges."
            )
            return True, warnings
        
        # Black Swan event (VIX > 50)
        if vix_level > 50:
            warnings.append(
                f"BLACK SWAN PROTOCOL: VIX {vix_level:.2f} > 50. "
                "Emergency mode: close all Risk Level 6+ positions."
            )
            return True, warnings
        
        return False, warnings
    
    def validate_trade(self, symbol: str, side: str, quantity: int,
                      order_type: str, strategy_type: str, risk_level: int,
                      price: Optional[float] = None,
                      sector: str = "Unknown") -> RiskOverrideDecision:
        """
        Main validation entry point - validates trade against all risk policies
        
        Args:
            symbol: Stock symbol
            side: BUY or SELL
            quantity: Number of shares/contracts
            order_type: MKT, LMT, etc.
            strategy_type: e.g., "Long Equity", "Short Iron Condor"
            risk_level: 0-10 risk level
            price: Optional limit price
            sector: Market sector
        
        Returns:
            RiskOverrideDecision with validation result
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"RISK POLICY VALIDATION")
        logger.info(f"{'='*70}")
        logger.info(f"Symbol: {symbol} | Side: {side} | Qty: {quantity}")
        logger.info(f"Strategy: {strategy_type} | Risk Level: {risk_level}")
        
        reasons = []
        
        # Get portfolio health
        portfolio_value = self.health_monitor.get_portfolio_value()
        drawdown_pct = self.health_monitor.calculate_drawdown()
        vix_level = self.get_vix_level()
        
        # Estimate position value
        if price:
            position_value = price * quantity
        else:
            # Would need to fetch current market price
            logger.warning("No price provided, cannot calculate position value accurately")
            position_value = 0
        
        position_pct = (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0
        
        logger.info(f"\nPortfolio Value: ${portfolio_value:,.2f}")
        logger.info(f"Drawdown: {drawdown_pct:.2f}%")
        logger.info(f"VIX Level: {vix_level:.2f}")
        logger.info(f"Position Value: ${position_value:,.2f} ({position_pct:.2f}% of portfolio)")
        
        # 1. Check emergency protocols
        emergency_triggered, emergency_warnings = self.check_emergency_protocols(vix_level)
        if emergency_triggered:
            reasons.extend(emergency_warnings)
            # Still allow hedges and defensive positions
            if risk_level >= 5:
                return RiskOverrideDecision(
                    status=ValidationStatus.REJECTED,
                    reasons=reasons,
                    vix_level=vix_level,
                    portfolio_drawdown=drawdown_pct,
                    position_size_pct=position_pct
                )
        
        # 2. Check drawdown circuit breaker
        is_violated, circuit_status, drawdown_multiplier = self.check_drawdown_circuit_breaker(drawdown_pct)
        if is_violated:
            reasons.append(f"DRAWDOWN CIRCUIT BREAKER: {circuit_status}")
            return RiskOverrideDecision(
                status=ValidationStatus.REJECTED,
                reasons=reasons,
                vix_level=vix_level,
                portfolio_drawdown=drawdown_pct,
                position_size_pct=position_pct
            )
        
        if drawdown_multiplier < 1.0:
            reasons.append(f"Drawdown {drawdown_pct:.2f}%: {circuit_status}")
            position_value *= drawdown_multiplier
            position_pct *= drawdown_multiplier
        
        # 3. Apply VIX adjustment
        adjusted_position_pct = self.apply_vix_adjustment(position_pct, vix_level)
        
        # 4. Check position sizing against risk level
        is_size_valid, size_reasons = self.check_position_sizing(
            risk_level, position_value, portfolio_value
        )
        if not is_size_valid:
            reasons.extend(size_reasons)
            return RiskOverrideDecision(
                status=ValidationStatus.REJECTED,
                reasons=reasons,
                vix_level=vix_level,
                portfolio_drawdown=drawdown_pct,
                position_size_pct=position_pct,
                adjusted_position_size=adjusted_position_pct
            )
        
        # 5. Check concentration limits
        is_conc_valid, conc_reasons = self.check_concentration_limits(
            symbol, sector, strategy_type, position_value
        )
        if not is_conc_valid:
            reasons.extend(conc_reasons)
            return RiskOverrideDecision(
                status=ValidationStatus.REJECTED,
                reasons=reasons,
                vix_level=vix_level,
                portfolio_drawdown=drawdown_pct,
                position_size_pct=position_pct,
                adjusted_position_size=adjusted_position_pct
            )
        
        # All checks passed
        if len(reasons) > 0:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.APPROVED
            reasons.append("Trade complies with all risk policy requirements")
        
        decision = RiskOverrideDecision(
            status=status,
            reasons=reasons,
            vix_level=vix_level,
            portfolio_drawdown=drawdown_pct,
            position_size_pct=position_pct,
            adjusted_position_size=adjusted_position_pct
        )
        
        logger.info(f"\n{decision}")
        logger.info(f"{'='*70}\n")
        
        return decision


def main():
    """Test the risk override system"""
    print("\n" + "="*70)
    print("RISK OVERRIDE SYSTEM TEST")
    print("="*70)
    
    validator = RiskPolicyValidator()
    
    # Test case 1: Valid low-risk trade
    print("\n[Test 1] Valid Low-Risk Long Equity Trade")
    decision = validator.validate_trade(
        symbol="AAPL",
        side="BUY",
        quantity=10,
        order_type="MKT",
        strategy_type="Long Equity",
        risk_level=2,
        price=175.0,
        sector="Technology"
    )
    print(f"Result: {decision}")
    
    # Test case 2: Prohibited trade
    print("\n[Test 2] Prohibited Naked Short Call")
    decision = validator.validate_trade(
        symbol="SPY",
        side="SELL",
        quantity=1,
        order_type="MKT",
        strategy_type="Naked Short Call",
        risk_level=10,
        price=450.0
    )
    print(f"Result: {decision}")
    
    # Get portfolio health
    print("\n[Test 3] Portfolio Health Check")
    health = validator.health_monitor.get_portfolio_health()
    print(json.dumps(health, indent=2))


if __name__ == "__main__":
    main()
