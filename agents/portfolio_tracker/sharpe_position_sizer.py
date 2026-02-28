"""
Sharpe-Weighted Position Sizing System
Adjusts position sizes based on strategy Sharpe ratios
"""

from dataclasses import dataclass
from typing import Dict
from datetime import datetime
import numpy as np


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy"""
    strategy_id: str
    sharpe_6m: float
    sharpe_12m: float
    returns: list
    risk_level: int  # 0-10


class SharpePositionSizer:
    """Calculate position sizes weighted by Sharpe ratio"""

    SHARPE_MULTIPLIERS = {
        # Sharpe >= 3.0
        "excellent": {"min": 3.0, "multiplier": 1.50, "priority": "top"},
        # Sharpe 2.0-3.0
        "high": {"min": 2.0, "multiplier": 1.25, "priority": "high"},
        # Sharpe 1.5-2.0
        "standard": {"min": 1.5, "multiplier": 1.00, "priority": "standard"},
        # Sharpe 1.0-1.5
        "lower": {"min": 1.0, "multiplier": 0.75, "priority": "lower"},
        # Sharpe 0.5-1.0
        "review": {"min": 0.5, "multiplier": 0.50, "priority": "review"},
        # Sharpe < 0.5
        "poor": {"min": 0.0, "multiplier": 0.25, "priority": "close"},
    }

    def __init__(self, policy: str = "MODERATE_AGGRESSIVE"):
        self.policy = policy

    def get_sharpe_tier(self, sharpe: float) -> str:
        """Determine Sharpe tier for given Sharpe ratio"""

        if sharpe >= 3.0:
            return "excellent"
        elif sharpe >= 2.0:
            return "high"
        elif sharpe >= 1.5:
            return "standard"
        elif sharpe >= 1.0:
            return "lower"
        elif sharpe >= 0.5:
            return "review"
        else:
            return "poor"

    def calculate_adjusted_position_size(
        self,
        base_position_limit: float,  # percentage
        sharpe_ratio: float,
    ) -> Dict:
        """Calculate adjusted position size based on Sharpe ratio"""

        tier = self.get_sharpe_tier(sharpe_ratio)
        tier_info = self.SHARPE_MULTIPLIERS[tier]

        multiplier = tier_info["multiplier"]
        adjusted_limit = base_position_limit * multiplier

        # Determine action
        if tier == "poor":
            action = "close"
            reasoning = (
                f"Sharpe ratio {sharpe_ratio:.2f} < 0.5 indicates poor risk-adjusted "
                "returns. Close position and remove strategy."
            )
        elif tier == "review":
            action = "reduce"
            reasoning = (
                f"Sharpe ratio {sharpe_ratio:.2f} is below standard. "
                "Reduce allocation to 50% and review strategy."
            )
        elif tier == "lower":
            action = "reduce"
            reasoning = (
                f"Sharpe ratio {sharpe_ratio:.2f} is adequate but below target. "
                "Reduce allocation to 75%."
            )
        elif tier == "standard":
            action = "maintain"
            reasoning = (
                f"Sharpe ratio {sharpe_ratio:.2f} meets baseline standards. "
                "Maintain base allocation."
            )
        elif tier == "high":
            action = "increase"
            reasoning = (
                f"Sharpe ratio {sharpe_ratio:.2f} exceeds target >2.0. "
                "Increase allocation to 125%."
            )
        else:  # excellent
            action = "maximize"
            reasoning = (
                f"Sharpe ratio {sharpe_ratio:.2f} is exceptional (>3.0). "
                "Maximize allocation to 150%."
            )

        return {
            "base_limit": base_position_limit,
            "sharpe_ratio": sharpe_ratio,
            "tier": tier,
            "multiplier": multiplier,
            "adjusted_limit": round(adjusted_limit, 2),
            "priority": tier_info["priority"],
            "action": action,
            "reasoning": reasoning,
        }

    def calculate_portfolio_allocation(
        self,
        strategies: Dict[str, StrategyPerformance],
        base_limits: Dict[str, float],  # {strategy_id: base_limit_pct}
        total_capital: float,
    ) -> Dict:
        """
        Calculate optimal portfolio allocation across strategies
        based on Sharpe-weighted position sizing
        """

        allocations = {}
        total_adjusted_limit = 0

        # Calculate adjusted limits for each strategy
        for strategy_id, perf in strategies.items():
            base_limit = base_limits.get(strategy_id, 0)
            sharpe = perf.sharpe_6m  # Use 6-month Sharpe

            sizing = self.calculate_adjusted_position_size(base_limit, sharpe)

            allocations[strategy_id] = {
                "strategy_id": strategy_id,
                "sharpe_6m": perf.sharpe_6m,
                "sharpe_12m": perf.sharpe_12m,
                "risk_level": perf.risk_level,
                "base_limit_pct": base_limit,
                "adjusted_limit_pct": sizing["adjusted_limit"],
                "tier": sizing["tier"],
                "priority": sizing["priority"],
                "action": sizing["action"],
                "reasoning": sizing["reasoning"],
                "allocated_capital": total_capital * (sizing["adjusted_limit"] / 100),
            }

            total_adjusted_limit += sizing["adjusted_limit"]

        # Sort by priority (excellent first, poor last)
        priority_order = ["top", "high", "standard", "lower", "review", "close"]
        sorted_allocations = sorted(
            allocations.items(),
            key=lambda x: priority_order.index(x[1]["priority"]),
        )

        return {
            "policy": self.policy,
            "total_capital": total_capital,
            "total_adjusted_limit_pct": round(total_adjusted_limit, 2),
            "num_strategies": len(strategies),
            "allocations": dict(sorted_allocations),
            "portfolio_summary": {
                "top_priority": sum(
                    1 for a in allocations.values() if a["priority"] == "top"
                ),
                "high_priority": sum(
                    1 for a in allocations.values() if a["priority"] == "high"
                ),
                "review_needed": sum(
                    1 for a in allocations.values() if a["priority"] in ["review", "close"]
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def recommend_rebalancing(
        self,
        current_allocations: Dict[str, float],  # {strategy_id: current_pct}
        optimal_allocations: Dict[str, Dict],  # from calculate_portfolio_allocation
        rebalance_threshold: float = 25.0,  # % deviation
    ) -> Dict:
        """
        Recommend rebalancing if current allocations deviate significantly
        from optimal Sharpe-weighted allocations
        """

        rebalance_actions = []

        for strategy_id, optimal in optimal_allocations.items():
            current_pct = current_allocations.get(strategy_id, 0)
            optimal_pct = optimal["adjusted_limit_pct"]

            if optimal_pct == 0:
                deviation_pct = float('inf') if current_pct > 0 else 0
            else:
                deviation_pct = abs((current_pct - optimal_pct) / optimal_pct) * 100

            if deviation_pct > rebalance_threshold:
                if current_pct > optimal_pct:
                    action_type = "trim"
                    amount = current_pct - optimal_pct
                else:
                    action_type = "add"
                    amount = optimal_pct - current_pct

                rebalance_actions.append({
                    "strategy_id": strategy_id,
                    "current_pct": current_pct,
                    "optimal_pct": optimal_pct,
                    "deviation_pct": round(deviation_pct, 1),
                    "action": action_type,
                    "amount_pct": round(amount, 2),
                    "priority": optimal["priority"],
                })

        # Sort by priority (handle high priority first)
        priority_order = ["top", "high", "standard", "lower", "review", "close"]
        rebalance_actions.sort(
            key=lambda x: (priority_order.index(x["priority"]), -x["deviation_pct"])
        )

        return {
            "rebalance_needed": len(rebalance_actions) > 0,
            "num_actions": len(rebalance_actions),
            "actions": rebalance_actions,
            "threshold_pct": rebalance_threshold,
            "timestamp": datetime.now().isoformat(),
        }


# Example usage
if __name__ == "__main__":
    sizer = SharpePositionSizer(policy="MODERATE_AGGRESSIVE")

    # Example strategies with performance
    strategies = {
        "iron_condor_1": StrategyPerformance(
            "iron_condor_1", sharpe_6m=2.8, sharpe_12m=2.5, returns=[], risk_level=2
        ),
        "covered_call_1": StrategyPerformance(
            "covered_call_1", sharpe_6m=1.9, sharpe_12m=2.1, returns=[], risk_level=1
        ),
        "long_equity_1": StrategyPerformance(
            "long_equity_1", sharpe_6m=1.2, sharpe_12m=1.4, returns=[], risk_level=3
        ),
        "credit_spread_1": StrategyPerformance(
            "credit_spread_1", sharpe_6m=0.7, sharpe_12m=0.9, returns=[], risk_level=3
        ),
    }

    # Base position limits (from MODERATE_AGGRESSIVE policy)
    base_limits = {
        "iron_condor_1": 12,  # 12% max for risk level 2
        "covered_call_1": 25,  # 25% max for risk level 1
        "long_equity_1": 20,  # 20% max for risk level 3
        "credit_spread_1": 10,  # 10% max for risk level 3
    }

    # Calculate optimal allocation
    allocation = sizer.calculate_portfolio_allocation(
        strategies, base_limits, total_capital=100000
    )

    print("Sharpe-Weighted Portfolio Allocation:\n")
    for strategy_id, alloc in allocation["allocations"].items():
        print(f"\n{strategy_id}:")
        print(f"  Sharpe (6m): {alloc['sharpe_6m']}")
        print(f"  Tier: {alloc['tier']}")
        print(f"  Base limit: {alloc['base_limit_pct']}%")
        print(f"  Adjusted limit: {alloc['adjusted_limit_pct']}%")
        print(f"  Allocated capital: ${alloc['allocated_capital']:,.0f}")
        print(f"  Action: {alloc['action']}")
        print(f"  Reasoning: {alloc['reasoning']}")

    print(f"\nTotal adjusted limit: {allocation['total_adjusted_limit_pct']}%")

    # Check rebalancing
    current_allocations = {
        "iron_condor_1": 10,
        "covered_call_1": 28,
        "long_equity_1": 22,
        "credit_spread_1": 12,
    }

    rebalance = sizer.recommend_rebalancing(
        current_allocations, allocation["allocations"], rebalance_threshold=20
    )

    if rebalance["rebalance_needed"]:
        print(f"\n\nRebalancing Recommended ({rebalance['num_actions']} actions):\n")
        for action in rebalance["actions"]:
            print(f"{action['strategy_id']}:")
            print(f"  Current: {action['current_pct']}%")
            print(f"  Optimal: {action['optimal_pct']}%")
            print(f"  Deviation: {action['deviation_pct']}%")
            print(f"  Action: {action['action'].upper()} {action['amount_pct']}%")
            print()
