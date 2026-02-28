"""
Volatility Monitoring System
Tracks portfolio volatility and triggers circuit breakers
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict
import numpy as np
from datetime import datetime, timedelta


class VolatilityStatus(Enum):
    NORMAL = "normal"
    MONITOR = "monitor"
    CAUTION = "caution"
    WARNING = "warning"
    CIRCUIT_BREAKER = "circuit_breaker"
    EMERGENCY = "emergency"


@dataclass
class VolatilityThresholds:
    """Volatility thresholds for circuit breakers"""
    normal_max: float  # annualized %
    monitor_max: float
    caution_max: float
    warning_max: float
    circuit_breaker_max: float

    position_sizing_multipliers: Dict[str, float]


class VolatilityMonitor:
    """Monitor portfolio volatility and enforce circuit breakers"""

    THRESHOLDS = {
        "HIGH": VolatilityThresholds(
            normal_max=20, monitor_max=25, caution_max=30,
            warning_max=35, circuit_breaker_max=40,
            position_sizing_multipliers={
                "normal": 1.00, "monitor": 0.95, "caution": 0.85,
                "warning": 0.70, "circuit_breaker": 0.50, "emergency": 0.30
            }
        ),
        "MODERATE_AGGRESSIVE": VolatilityThresholds(
            normal_max=15, monitor_max=20, caution_max=25,
            warning_max=30, circuit_breaker_max=35,
            position_sizing_multipliers={
                "normal": 1.00, "monitor": 1.00, "caution": 0.85,
                "warning": 0.70, "circuit_breaker": 0.50, "emergency": 0.30
            }
        ),
        "MODERATE": VolatilityThresholds(
            normal_max=15, monitor_max=20, caution_max=25,
            warning_max=30, circuit_breaker_max=35,
            position_sizing_multipliers={
                "normal": 1.00, "monitor": 1.00, "caution": 0.85,
                "warning": 0.70, "circuit_breaker": 0.50, "emergency": 0.30
            }
        ),
        "LOW": VolatilityThresholds(
            normal_max=12, monitor_max=15, caution_max=20,
            warning_max=25, circuit_breaker_max=30,
            position_sizing_multipliers={
                "normal": 1.00, "monitor": 0.95, "caution": 0.70,
                "warning": 0.50, "circuit_breaker": 0.30, "emergency": 0.10
            }
        ),
    }

    def __init__(self, policy: str = "MODERATE_AGGRESSIVE"):
        self.policy = policy
        self.thresholds = self.THRESHOLDS[policy]

    def calculate_volatility(
        self, returns: List[float], annualize: bool = True
    ) -> float:
        """Calculate volatility from returns series"""

        if len(returns) < 2:
            return 0.0

        volatility = np.std(returns, ddof=1)

        if annualize:
            # Annualize assuming daily returns
            volatility = volatility * np.sqrt(252)

        return volatility * 100  # Convert to percentage

    def calculate_rolling_volatility(
        self, returns: List[float], window: int = 30
    ) -> List[float]:
        """Calculate rolling volatility"""

        rolling_vols = []
        for i in range(len(returns)):
            if i < window:
                # Not enough data yet
                rolling_vols.append(None)
            else:
                window_returns = returns[i - window : i]
                vol = self.calculate_volatility(window_returns, annualize=True)
                rolling_vols.append(vol)

        return rolling_vols

    def determine_status(self, volatility: float) -> VolatilityStatus:
        """Determine volatility status based on thresholds"""

        if volatility < self.thresholds.normal_max:
            return VolatilityStatus.NORMAL
        elif volatility < self.thresholds.monitor_max:
            return VolatilityStatus.MONITOR
        elif volatility < self.thresholds.caution_max:
            return VolatilityStatus.CAUTION
        elif volatility < self.thresholds.warning_max:
            return VolatilityStatus.WARNING
        elif volatility < self.thresholds.circuit_breaker_max:
            return VolatilityStatus.CIRCUIT_BREAKER
        else:
            return VolatilityStatus.EMERGENCY

    def get_position_sizing_multiplier(self, status: VolatilityStatus) -> float:
        """Get position sizing multiplier for given volatility status"""
        return self.thresholds.position_sizing_multipliers[status.value]

    def get_required_actions(self, status: VolatilityStatus) -> List[str]:
        """Get required actions for given volatility status"""

        actions = {
            VolatilityStatus.NORMAL: [
                "Normal operations",
                "Continue monitoring",
            ],
            VolatilityStatus.MONITOR: [
                "Close new positions with Sharpe <1.0",
                "Review all positions",
                "Increase monitoring frequency",
            ],
            VolatilityStatus.CAUTION: [
                "Close positions with Sharpe <1.5",
                "Reduce sizing on remaining positions by 15%",
                "Tighten stop losses",
                "Increase liquidity buffer",
            ],
            VolatilityStatus.WARNING: [
                "Close positions with Sharpe <2.0",
                "Keep only best performers",
                "Reduce position sizing by 30%",
                "Move to more liquid assets",
                "Consider policy downgrade",
            ],
            VolatilityStatus.CIRCUIT_BREAKER: [
                "CIRCUIT BREAKER TRIGGERED",
                "Close all positions with Sharpe <2.0",
                "Reduce position sizing by 50%",
                "Move to high-liquidity assets only",
                "Mandatory policy review",
            ],
            VolatilityStatus.EMERGENCY: [
                "EMERGENCY MODE",
                "Immediate defensive posture",
                "Close most positions",
                "Keep only Tier 1-2 liquid assets",
                "Switch to LOW policy",
            ],
        }

        return actions.get(status, ["Unknown status"])

    def generate_volatility_report(
        self, returns_30d: List[float], returns_90d: List[float]
    ) -> Dict:
        """Generate comprehensive volatility report"""

        vol_30d = self.calculate_volatility(returns_30d, annualize=True)
        vol_90d = self.calculate_volatility(returns_90d, annualize=True)

        status = self.determine_status(vol_30d)
        multiplier = self.get_position_sizing_multiplier(status)
        actions = self.get_required_actions(status)

        # Calculate trend
        if vol_30d > vol_90d * 1.2:
            trend = "increasing"
        elif vol_30d < vol_90d * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "policy": self.policy,
            "volatility_30d": round(vol_30d, 2),
            "volatility_90d": round(vol_90d, 2),
            "volatility_trend": trend,
            "status": status.value,
            "position_sizing_multiplier": multiplier,
            "thresholds": {
                "normal_max": self.thresholds.normal_max,
                "monitor_max": self.thresholds.monitor_max,
                "caution_max": self.thresholds.caution_max,
                "warning_max": self.thresholds.warning_max,
                "circuit_breaker_max": self.thresholds.circuit_breaker_max,
            },
            "required_actions": actions,
            "timestamp": datetime.now().isoformat(),
        }


# Example usage
if __name__ == "__main__":
    monitor = VolatilityMonitor(policy="MODERATE_AGGRESSIVE")

    # Generate sample returns (daily returns as decimals)
    np.random.seed(42)
    returns_30d = list(np.random.normal(0.001, 0.015, 30))  # ~15% annualized vol
    returns_90d = list(np.random.normal(0.001, 0.012, 90))  # ~12% annualized vol

    report = monitor.generate_volatility_report(returns_30d, returns_90d)

    print("Volatility Report:")
    print(f"Policy: {report['policy']}")
    print(f"30-day volatility: {report['volatility_30d']}%")
    print(f"90-day volatility: {report['volatility_90d']}%")
    print(f"Trend: {report['volatility_trend']}")
    print(f"Status: {report['status']}")
    print(f"Position sizing multiplier: {report['position_sizing_multiplier']}")
    print(f"\nRequired actions:")
    for action in report['required_actions']:
        print(f"  - {action}")
