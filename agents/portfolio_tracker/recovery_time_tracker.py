"""
Recovery Time Tracking System
Monitors drawdown recovery times and enforces constraints
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


@dataclass
class DrawdownEvent:
    """Represents a drawdown event"""
    event_id: str
    start_date: datetime
    peak_value: float
    current_value: float
    current_drawdown_pct: float
    days_in_drawdown: int
    expected_recovery_days: int
    status: str  # "ongoing", "recovered", "critical"


@dataclass
class RecoveryTimeTargets:
    """Recovery time targets for different drawdown levels"""
    dd_5pct: int  # days
    dd_10pct: int
    dd_15pct: int
    dd_20pct: int


class RecoveryTimeTracker:
    """Track drawdown recovery times and enforce constraints"""

    TARGETS = {
        "HIGH": RecoveryTimeTargets(60, 120, 270, 450),  # days
        "MODERATE_AGGRESSIVE": RecoveryTimeTargets(45, 90, 180, 365),
        "MODERATE": RecoveryTimeTargets(45, 90, 180, 365),
        "LOW": RecoveryTimeTargets(21, 45, 90, 180),
    }

    def __init__(self, policy: str = "MODERATE_AGGRESSIVE"):
        self.policy = policy
        self.targets = self.TARGETS[policy]
        self.current_drawdown: Optional[DrawdownEvent] = None
        self.drawdown_history: List[Dict] = []

    def get_expected_recovery_time(self, drawdown_pct: float) -> int:
        """Get expected recovery time in days for given drawdown percentage"""

        if drawdown_pct < 5:
            return self.targets.dd_5pct
        elif drawdown_pct < 10:
            # Linear interpolation between 5% and 10%
            ratio = (drawdown_pct - 5) / 5
            return int(
                self.targets.dd_5pct
                + ratio * (self.targets.dd_10pct - self.targets.dd_5pct)
            )
        elif drawdown_pct < 15:
            ratio = (drawdown_pct - 10) / 5
            return int(
                self.targets.dd_10pct
                + ratio * (self.targets.dd_15pct - self.targets.dd_10pct)
            )
        elif drawdown_pct < 20:
            ratio = (drawdown_pct - 15) / 5
            return int(
                self.targets.dd_15pct
                + ratio * (self.targets.dd_20pct - self.targets.dd_15pct)
            )
        else:
            return self.targets.dd_20pct

    def update(
        self, current_date: datetime, current_value: float, peak_value: float
    ) -> Dict:
        """Update drawdown tracking"""

        drawdown_pct = ((peak_value - current_value) / peak_value) * 100

        # Check if in drawdown
        if drawdown_pct > 0.5:  # >0.5% considered a drawdown
            if self.current_drawdown is None:
                # Start new drawdown event
                self.current_drawdown = DrawdownEvent(
                    event_id=f"DD_{current_date.strftime('%Y%m%d')}",
                    start_date=current_date,
                    peak_value=peak_value,
                    current_value=current_value,
                    current_drawdown_pct=drawdown_pct,
                    days_in_drawdown=0,
                    expected_recovery_days=self.get_expected_recovery_time(
                        drawdown_pct
                    ),
                    status="ongoing",
                )
            else:
                # Update existing drawdown
                days_in_dd = (current_date - self.current_drawdown.start_date).days
                expected = self.get_expected_recovery_time(drawdown_pct)

                self.current_drawdown.current_value = current_value
                self.current_drawdown.current_drawdown_pct = drawdown_pct
                self.current_drawdown.days_in_drawdown = days_in_dd
                self.current_drawdown.expected_recovery_days = expected

                # Determine status
                if days_in_dd > expected * 2.0:
                    self.current_drawdown.status = "critical"
                elif days_in_dd > expected * 1.5:
                    self.current_drawdown.status = "delayed"
                else:
                    self.current_drawdown.status = "ongoing"

        else:
            # Recovered from drawdown
            if self.current_drawdown is not None:
                # Log recovery
                days_in_dd = (current_date - self.current_drawdown.start_date).days

                recovery_event = {
                    "event_id": self.current_drawdown.event_id,
                    "start_date": self.current_drawdown.start_date.isoformat(),
                    "end_date": current_date.isoformat(),
                    "peak_value": self.current_drawdown.peak_value,
                    "max_drawdown_pct": self.current_drawdown.current_drawdown_pct,
                    "recovery_days": days_in_dd,
                    "expected_days": self.current_drawdown.expected_recovery_days,
                    "recovery_ratio": days_in_dd
                    / self.current_drawdown.expected_recovery_days,
                    "policy": self.policy,
                }

                self.drawdown_history.append(recovery_event)
                self.current_drawdown = None

        return self.get_status_report()

    def get_status_report(self) -> Dict:
        """Generate status report"""

        if self.current_drawdown is None:
            return {
                "in_drawdown": False,
                "status": "healthy",
                "current_drawdown_pct": 0,
                "days_in_drawdown": 0,
                "expected_recovery_days": 0,
                "recovery_progress": 1.0,
                "action_required": None,
                "timestamp": datetime.now().isoformat(),
            }

        dd = self.current_drawdown
        progress = dd.days_in_drawdown / dd.expected_recovery_days if dd.expected_recovery_days > 0 else 0

        # Determine required actions
        actions = []
        if dd.status == "critical":
            actions.append("CRITICAL: Reduce allocation by 60% or close position")
            actions.append("Recovery taking >2x expected time")
        elif dd.status == "delayed":
            actions.append("DELAYED: Reduce allocation by 30%")
            actions.append("Recovery taking >1.5x expected time")
        elif progress > 1.0:
            actions.append("MONITOR: Drawdown exceeding expected recovery time")

        return {
            "in_drawdown": True,
            "status": dd.status,
            "event_id": dd.event_id,
            "start_date": dd.start_date.isoformat(),
            "peak_value": dd.peak_value,
            "current_value": dd.current_value,
            "current_drawdown_pct": round(dd.current_drawdown_pct, 2),
            "days_in_drawdown": dd.days_in_drawdown,
            "expected_recovery_days": dd.expected_recovery_days,
            "recovery_progress": round(progress, 2),
            "action_required": actions if actions else None,
            "targets": {
                "5pct": self.targets.dd_5pct,
                "10pct": self.targets.dd_10pct,
                "15pct": self.targets.dd_15pct,
                "20pct": self.targets.dd_20pct,
            },
            "timestamp": datetime.now().isoformat(),
        }

    def get_historical_performance(self) -> Dict:
        """Analyze historical recovery performance"""

        if not self.drawdown_history:
            return {
                "num_drawdowns": 0,
                "avg_recovery_ratio": None,
                "performance": "insufficient_data",
            }

        recovery_ratios = [
            event["recovery_ratio"] for event in self.drawdown_history
        ]
        avg_ratio = sum(recovery_ratios) / len(recovery_ratios)

        # Performance rating
        if avg_ratio < 0.5:
            performance = "excellent"
        elif avg_ratio < 0.75:
            performance = "good"
        elif avg_ratio < 1.0:
            performance = "acceptable"
        elif avg_ratio < 1.5:
            performance = "poor"
        else:
            performance = "critical"

        return {
            "num_drawdowns": len(self.drawdown_history),
            "avg_recovery_ratio": round(avg_ratio, 2),
            "performance": performance,
            "recent_events": self.drawdown_history[-5:],  # Last 5 events
        }

    def save_history(self, filepath: str):
        """Save drawdown history to file"""
        with open(filepath, "w") as f:
            json.dump(self.drawdown_history, f, indent=2)

    def load_history(self, filepath: str):
        """Load drawdown history from file"""
        try:
            with open(filepath, "r") as f:
                self.drawdown_history = json.load(f)
        except FileNotFoundError:
            self.drawdown_history = []


# Example usage
if __name__ == "__main__":
    tracker = RecoveryTimeTracker(policy="MODERATE_AGGRESSIVE")

    # Simulate drawdown scenario
    peak = 100000
    start_date = datetime(2026, 1, 1)

    # Day 0: Enter drawdown
    report = tracker.update(start_date, 92000, peak)  # 8% drawdown
    print(f"Day 0: {report['current_drawdown_pct']}% drawdown")
    print(f"Expected recovery: {report['expected_recovery_days']} days")

    # Day 60: Still in drawdown
    report = tracker.update(start_date + timedelta(days=60), 94000, peak)
    print(f"\nDay 60: {report['current_drawdown_pct']}% drawdown")
    print(f"Progress: {report['recovery_progress']:.0%}")
    print(f"Status: {report['status']}")

    # Day 120: Recovered
    report = tracker.update(start_date + timedelta(days=120), 100500, peak)
    print(f"\nDay 120: Recovered!")
    print(f"In drawdown: {report['in_drawdown']}")

    # Historical performance
    hist = tracker.get_historical_performance()
    print(f"\nHistorical Performance:")
    print(f"Drawdowns: {hist['num_drawdowns']}")
    print(f"Avg recovery ratio: {hist['avg_recovery_ratio']}")
    print(f"Rating: {hist['performance']}")
