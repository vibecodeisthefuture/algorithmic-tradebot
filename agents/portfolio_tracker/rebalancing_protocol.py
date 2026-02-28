"""
Rebalancing Protocol System
Implements systematic portfolio rebalancing
"""

from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta
from enum import Enum


class RebalanceFrequency(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ON_DEMAND = "on_demand"


@dataclass
class RebalanceConfig:
    """Configuration for rebalancing protocol"""
    monthly_enabled: bool = True
    quarterly_enabled: bool = True
    annual_enabled: bool = True
    deviation_threshold_pct: float = 25.0  # Trigger rebalance if position deviates >25%
    profit_taking_enabled: bool = True
    profit_taking_threshold_quarterly: float = 15.0  # Take profits if >15% gain in quarter


class RebalancingProtocol:
    """Systematic portfolio rebalancing"""

    def __init__(self, config: RebalanceConfig = None):
        self.config = config or RebalanceConfig()
        self.last_monthly = None
        self.last_quarterly = None
        self.last_annual = None

    def check_monthly_rebalance(self, current_date: datetime) -> Dict:
        """Check if monthly rebalance is due"""

        if not self.config.monthly_enabled:
            return {"due": False, "reason": "monthly rebalance disabled"}

        if self.last_monthly is None:
            return {
                "due": True,
                "reason": "first monthly rebalance",
                "type": RebalanceFrequency.MONTHLY,
            }

        days_since = (current_date - self.last_monthly).days

        if days_since >= 30:
            return {
                "due": True,
                "reason": f"{days_since} days since last monthly rebalance",
                "type": RebalanceFrequency.MONTHLY,
            }

        return {"due": False, "reason": f"only {days_since} days since last rebalance"}

    def monthly_review_checklist(
        self,
        positions: Dict[str, Dict],  # {symbol: {value, limit, sharpe, etc}}
    ) -> Dict:
        """Generate monthly review checklist"""

        issues = []
        actions = []

        # Check position limit violations
        for symbol, info in positions.items():
            current_pct = info.get("current_pct", 0)
            limit_pct = info.get("limit_pct", 0)

            if current_pct > limit_pct * 1.25:  # >25% over limit
                issues.append(f"{symbol} exceeds limit by >25%")
                actions.append({
                    "symbol": symbol,
                    "action": "trim",
                    "current": current_pct,
                    "target": limit_pct,
                    "reason": "position limit violation",
                })

            # Check Sharpe performance
            sharpe = info.get("sharpe_6m", 0)
            if sharpe < 1.0:
                issues.append(f"{symbol} Sharpe <1.0 for 6 months")
                actions.append({
                    "symbol": symbol,
                    "action": "review",
                    "sharpe": sharpe,
                    "reason": "poor Sharpe performance",
                })

        return {
            "frequency": "monthly",
            "issues_found": len(issues),
            "issues": issues,
            "actions_required": len(actions),
            "actions": actions,
        }

    def quarterly_rebalance(
        self,
        current_positions: Dict[str, float],  # {symbol: current_value}
        target_allocations: Dict[str, float],  # {symbol: target_pct}
        total_portfolio_value: float,
        quarterly_return: float,  # Portfolio return this quarter (%)
    ) -> Dict:
        """Execute quarterly rebalancing logic"""

        rebalance_actions = []

        # 1. Profit-taking check
        profit_taken = 0
        if (
            self.config.profit_taking_enabled
            and quarterly_return > self.config.profit_taking_threshold_quarterly
        ):
            profit_taken_pct = 20  # Take 20% of profits
            profit_taken = total_portfolio_value * (quarterly_return / 100) * 0.20

            rebalance_actions.append({
                "action": "profit_taking",
                "amount": profit_taken,
                "reason": f"Quarterly return {quarterly_return:.1f}% exceeds "
                f"{self.config.profit_taking_threshold_quarterly}% threshold",
            })

        # 2. Trim winners that exceed limits
        for symbol, current_value in current_positions.items():
            current_pct = (current_value / total_portfolio_value) * 100
            target_pct = target_allocations.get(symbol, 0)

            # Trim if >25% above target
            if target_pct > 0 and current_pct > target_pct * 1.25:
                trim_to_pct = target_pct * 0.8  # Trim to 80% of max
                trim_amount = total_portfolio_value * ((current_pct - trim_to_pct) / 100)

                rebalance_actions.append({
                    "symbol": symbol,
                    "action": "trim",
                    "current_pct": current_pct,
                    "target_pct": trim_to_pct,
                    "amount": trim_amount,
                    "reason": "exceeds position limit",
                })

        # 3. Add to underweight Sharpe >2 strategies
        for symbol, target_pct in target_allocations.items():
            current_value = current_positions.get(symbol, 0)
            current_pct = (current_value / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0

            # Only add if significantly underweight and good Sharpe
            # (Assume we'd check Sharpe here - simplified for example)
            if target_pct > 0 and current_pct < target_pct * 0.75:
                add_to_pct = target_pct * 0.9  # Add to 90% of target
                add_amount = total_portfolio_value * ((add_to_pct - current_pct) / 100)

                rebalance_actions.append({
                    "symbol": symbol,
                    "action": "add",
                    "current_pct": current_pct,
                    "target_pct": add_to_pct,
                    "amount": add_amount,
                    "reason": "underweight in high-Sharpe strategy",
                })

        return {
            "frequency": "quarterly",
            "quarterly_return_pct": quarterly_return,
            "profit_taken": profit_taken,
            "num_actions": len(rebalance_actions),
            "actions": rebalance_actions,
            "timestamp": datetime.now().isoformat(),
        }

    def annual_review(
        self,
        yearly_performance: Dict,  # Full year performance metrics
    ) -> Dict:
        """Annual comprehensive portfolio review"""

        review_items = []

        # 1. Strategy performance review
        review_items.append({
            "category": "strategy_performance",
            "action": "Review all strategies with Sharpe <1 over past year",
            "priority": "high",
        })

        # 2. Risk policy adjustment
        review_items.append({
            "category": "risk_policy",
            "action": "Review and adjust risk policy for age/goals",
            "priority": "medium",
        })

        # 3. Diversification audit
        review_items.append({
            "category": "diversification",
            "action": "Audit sector concentrations and correlations",
            "priority": "medium",
        })

        # 4. Backtest validation
        review_items.append({
            "category": "validation",
            "action": "Re-run backtests on all strategies with latest data",
            "priority": "high",
        })

        return {
            "frequency": "annual",
            "year": datetime.now().year,
            "yearly_performance": yearly_performance,
            "review_items": review_items,
            "timestamp": datetime.now().isoformat(),
        }

    def execute_rebalance(
        self,
        rebalance_type: RebalanceFrequency,
        actions: List[Dict],
        current_date: datetime,
    ) -> Dict:
        """Execute rebalancing actions and log"""

        # Update last rebalance timestamps
        if rebalance_type == RebalanceFrequency.MONTHLY:
            self.last_monthly = current_date
        elif rebalance_type == RebalanceFrequency.QUARTERLY:
            self.last_quarterly = current_date
        elif rebalance_type == RebalanceFrequency.ANNUAL:
            self.last_annual = current_date

        return {
            "rebalance_type": rebalance_type.value,
            "execution_date": current_date.isoformat(),
            "num_actions": len(actions),
            "actions_executed": actions,
            "status": "completed",
        }


# Example usage
if __name__ == "__main__":
    protocol = RebalancingProtocol()

    # Check monthly rebalance
    current_date = datetime.now()
    monthly_check = protocol.check_monthly_rebalance(current_date)
    print(f"Monthly rebalance due: {monthly_check}")

    # Monthly review
    positions = {
        "AAPL": {"current_pct": 28, "limit_pct": 20, "sharpe_6m": 2.1},
        "WEAK_STOCK": {"current_pct": 15, "limit_pct": 20, "sharpe_6m": 0.7},
    }

    monthly_review = protocol.monthly_review_checklist(positions)
    print(f"\nMonthly Review:")
    print(f"Issues: {monthly_review['issues']}")
    print(f"Actions: {monthly_review['actions']}")

    # Quarterly rebalance
    current_positions = {
        "AAPL": 30000,
        "MSFT": 25000,
        "GOOGL": 20000,
    }
    target_allocations = {
        "AAPL": 25,
        "MSFT": 25,
        "GOOGL": 20,
    }

    quarterly = protocol.quarterly_rebalance(
        current_positions,
        target_allocations,
        total_portfolio_value=100000,
        quarterly_return=18.5,  # 18.5% this quarter
    )

    print(f"\nQuarterly Rebalance:")
    print(f"Return: {quarterly['quarterly_return_pct']}%")
    print(f"Profit taken: ${quarterly['profit_taken']:,.0f}")
    print(f"Actions: {quarterly['num_actions']}")
    for action in quarterly['actions']:
        print(f"  {action}")
