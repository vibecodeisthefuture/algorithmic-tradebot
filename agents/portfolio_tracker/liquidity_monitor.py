"""
Liquidity Monitoring System
Tracks portfolio liquidity tiers and enforces requirements
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import json
from datetime import datetime


class LiquidityTier(Enum):
    TIER_1 = "T+0"  # Immediate
    TIER_2 = "T+1"  # Quick
    TIER_3 = "T+2-3"  # Standard
    TIER_4 = "T+7+"  # Illiquid


@dataclass
class Position:
    symbol: str
    value: float
    liquidity_tier: LiquidityTier
    avg_daily_volume: float
    bid_ask_spread: float


@dataclass
class LiquidityRequirements:
    tier1_min: float  # percentage
    tier2_min: float  # percentage
    tier1_2_combined_min: float  # percentage
    tier4_max: float  # percentage


class LiquidityMonitor:
    """Monitor and enforce liquidity requirements"""

    REQUIREMENTS = {
        "HIGH": LiquidityRequirements(2, 8, 10, 30),
        "MODERATE_AGGRESSIVE": LiquidityRequirements(5, 15, 20, 30),
        "MODERATE": LiquidityRequirements(5, 15, 20, 30),
        "LOW": LiquidityRequirements(10, 20, 30, 25),
    }

    # Classification rules for liquidity tiers
    TIER_CLASSIFICATION = {
        "cash": LiquidityTier.TIER_1,
        "money_market": LiquidityTier.TIER_1,
        "SPY": LiquidityTier.TIER_2,
        "QQQ": LiquidityTier.TIER_2,
        "DIA": LiquidityTier.TIER_2,
        "IWM": LiquidityTier.TIER_2,
    }

    def __init__(self, policy: str = "MODERATE_AGGRESSIVE"):
        self.policy = policy
        self.requirements = self.REQUIREMENTS[policy]

    def classify_position(self, position: Position) -> LiquidityTier:
        """Classify a position into liquidity tier"""

        # Check if specific symbol has classification
        if position.symbol.upper() in self.TIER_CLASSIFICATION:
            return self.TIER_CLASSIFICATION[position.symbol.upper()]

        # For stocks, classify by volume and spread
        if position.symbol.isupper() and len(position.symbol) <= 5:
            # Assume it's a stock
            if position.avg_daily_volume > 10_000_000 and position.bid_ask_spread < 0.005:
                return LiquidityTier.TIER_2  # Large-cap, liquid
            elif position.avg_daily_volume > 1_000_000 and position.bid_ask_spread < 0.02:
                return LiquidityTier.TIER_3  # Mid-cap, standard
            else:
                return LiquidityTier.TIER_4  # Small-cap or illiquid

        # Default to Tier 3 for unknown
        return LiquidityTier.TIER_3

    def calculate_liquidity_distribution(
        self, positions: List[Position]
    ) -> Dict[str, float]:
        """Calculate percentage of portfolio in each liquidity tier"""

        total_value = sum(p.value for p in positions)
        if total_value == 0:
            return {
                "tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0,
                "tier1_2_combined": 0
            }

        tier_values = {tier: 0.0 for tier in LiquidityTier}

        for position in positions:
            tier = self.classify_position(position)
            tier_values[tier] += position.value

        return {
            "tier1": (tier_values[LiquidityTier.TIER_1] / total_value) * 100,
            "tier2": (tier_values[LiquidityTier.TIER_2] / total_value) * 100,
            "tier3": (tier_values[LiquidityTier.TIER_3] / total_value) * 100,
            "tier4": (tier_values[LiquidityTier.TIER_4] / total_value) * 100,
            "tier1_2_combined": (
                (tier_values[LiquidityTier.TIER_1] + tier_values[LiquidityTier.TIER_2])
                / total_value
            ) * 100,
        }

    def check_requirements(
        self, liquidity_dist: Dict[str, float]
    ) -> Dict[str, any]:
        """Check if liquidity requirements are met"""

        violations = []

        if liquidity_dist["tier1"] < self.requirements.tier1_min:
            violations.append(
                f"Tier 1 below minimum: {liquidity_dist['tier1']:.1f}% "
                f"< {self.requirements.tier1_min}%"
            )

        if liquidity_dist["tier1_2_combined"] < self.requirements.tier1_2_combined_min:
            violations.append(
                f"Tier 1+2 combined below minimum: "
                f"{liquidity_dist['tier1_2_combined']:.1f}% "
                f"< {self.requirements.tier1_2_combined_min}%"
            )

        if liquidity_dist["tier4"] > self.requirements.tier4_max:
            violations.append(
                f"Tier 4 exceeds maximum: {liquidity_dist['tier4']:.1f}% "
                f"> {self.requirements.tier4_max}%"
            )

        return {
            "meets_requirements": len(violations) == 0,
            "violations": violations,
            "liquidity_distribution": liquidity_dist,
            "timestamp": datetime.now().isoformat(),
        }

    def liquidity_stress_test(
        self, positions: List[Position], target_liquidation_pct: float = 25
    ) -> Dict[str, any]:
        """
        Stress test: Can we liquidate target_liquidation_pct%
        within 48 hours with <3% slippage?
        """

        total_value = sum(p.value for p in positions)
        target_value = total_value * (target_liquidation_pct / 100)

        # Sort by liquidity (best first)
        tier_order = [
            LiquidityTier.TIER_1,
            LiquidityTier.TIER_2,
            LiquidityTier.TIER_3,
            LiquidityTier.TIER_4,
        ]

        liquidated_value = 0
        estimated_slippage = 0

        for tier in tier_order:
            tier_positions = [
                p for p in positions if self.classify_position(p) == tier
            ]

            for pos in tier_positions:
                if liquidated_value >= target_value:
                    break

                # Estimate slippage based on tier
                if tier == LiquidityTier.TIER_1:
                    slippage = 0.001  # 0.1%
                elif tier == LiquidityTier.TIER_2:
                    slippage = 0.005  # 0.5%
                elif tier == LiquidityTier.TIER_3:
                    slippage = 0.015  # 1.5%
                else:  # TIER_4
                    slippage = 0.04  # 4%

                liquidated_value += pos.value
                estimated_slippage += pos.value * slippage

        avg_slippage = (estimated_slippage / target_value) if target_value > 0 else 0

        return {
            "target_liquidation_value": target_value,
            "achievable": liquidated_value >= target_value,
            "estimated_slippage_pct": avg_slippage * 100,
            "passes_stress_test": avg_slippage < 0.03,  # <3%
            "timestamp": datetime.now().isoformat(),
        }

    def generate_liquidity_report(self, positions: List[Position]) -> Dict:
        """Generate comprehensive liquidity report"""

        liquidity_dist = self.calculate_liquidity_distribution(positions)
        requirements_check = self.check_requirements(liquidity_dist)
        stress_test = self.liquidity_stress_test(positions)

        return {
            "policy": self.policy,
            "requirements": {
                "tier1_min": self.requirements.tier1_min,
                "tier1_2_combined_min": self.requirements.tier1_2_combined_min,
                "tier4_max": self.requirements.tier4_max,
            },
            "current_liquidity": liquidity_dist,
            "compliance": requirements_check,
            "stress_test": stress_test,
            "timestamp": datetime.now().isoformat(),
        }


# Example usage
if __name__ == "__main__":
    monitor = LiquidityMonitor(policy="MODERATE_AGGRESSIVE")

    # Example positions
    positions = [
        Position("cash", 5000, LiquidityTier.TIER_1, 0, 0),
        Position("SPY", 15000, LiquidityTier.TIER_2, 50_000_000, 0.001),
        Position("AAPL", 20000, LiquidityTier.TIER_2, 80_000_000, 0.002),
        Position("MSFT", 18000, LiquidityTier.TIER_2, 30_000_000, 0.003),
        Position("AMD", 12000, LiquidityTier.TIER_3, 5_000_000, 0.01),
        Position("SMALLCAP", 8000, LiquidityTier.TIER_4, 500_000, 0.03),
    ]

    report = monitor.generate_liquidity_report(positions)
    print(json.dumps(report, indent=2))
