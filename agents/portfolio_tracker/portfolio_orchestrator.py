"""
Portfolio Orchestrator
Integrates all monitoring systems and enforces enhanced risk policy
"""

from typing import Dict, List
import json
from datetime import datetime

# Import all monitoring systems
from liquidity_monitor import LiquidityMonitor, Position, LiquidityTier
from volatility_monitor import VolatilityMonitor
from correlation_monitor import CorrelationMonitor
from recovery_time_tracker import RecoveryTimeTracker
from sharpe_position_sizer import SharpePositionSizer, StrategyPerformance
from rebalancing_protocol import RebalancingProtocol, RebalanceFrequency

# Optional: risk_override (requires Alpaca connection)
try:
    from risk_override import RiskPolicyValidator, RiskProfile
    RISK_OVERRIDE_AVAILABLE = True
except ImportError:
    RISK_OVERRIDE_AVAILABLE = False
    print("[INFO] risk_override not available (requires alpaca_connection)")


class PortfolioOrchestrator:
    """
    Master orchestrator for enhanced risk policy framework
    Integrates all monitoring and enforcement systems
    """

    def __init__(self, policy: str = "MODERATE_AGGRESSIVE"):
        self.policy = policy

        # Initialize all monitoring systems
        self.liquidity_monitor = LiquidityMonitor(policy)
        self.volatility_monitor = VolatilityMonitor(policy)
        self.correlation_monitor = CorrelationMonitor(policy)
        self.recovery_tracker = RecoveryTimeTracker(policy)
        self.position_sizer = SharpePositionSizer(policy)
        self.rebalancing = RebalancingProtocol()

        # Optional: Initialize risk validator if available
        if RISK_OVERRIDE_AVAILABLE:
            self.risk_validator = RiskPolicyValidator()
        else:
            self.risk_validator = None

    def run_comprehensive_health_check(
        self,
        portfolio_data: Dict,
    ) -> Dict:
        """
        Run comprehensive portfolio health check
        Integrates all monitoring systems

        Expected portfolio_data structure:
        {
            "total_value": float,
            "cash": float,
            "positions": [{symbol, value, tier, avg_volume, spread, sector, asset_class, returns}],
            "returns_30d": [list of daily returns],
            "returns_90d": [list of daily returns],
            "current_vix": float,
            "peak_value": float,
            "strategies": {strategy_id: {sharpe_6m, sharpe_12m, returns, risk_level}},
            "base_limits": {strategy_id: base_limit_pct},
        }
        """

        results = {
            "timestamp": datetime.now().isoformat(),
            "policy": self.policy,
            "total_value": portfolio_data["total_value"],
        }

        # 1. Liquidity Check
        positions = [
            Position(
                symbol=p["symbol"],
                value=p["value"],
                liquidity_tier=p.get("tier", LiquidityTier.TIER_3),
                avg_daily_volume=p.get("avg_volume", 0),
                bid_ask_spread=p.get("spread", 0),
            )
            for p in portfolio_data["positions"]
        ]

        liquidity_report = self.liquidity_monitor.generate_liquidity_report(positions)
        results["liquidity"] = liquidity_report

        # 2. Volatility Check
        volatility_report = self.volatility_monitor.generate_volatility_report(
            portfolio_data["returns_30d"],
            portfolio_data["returns_90d"],
        )
        results["volatility"] = volatility_report

        # 3. Correlation Check
        returns_dict = {
            p["symbol"]: p.get("returns", []) for p in portfolio_data["positions"]
        }
        weights = {
            p["symbol"]: p["value"] / portfolio_data["total_value"]
            for p in portfolio_data["positions"]
        }
        positions_dict = {
            p["symbol"]: {
                "sector": p.get("sector", "Unknown"),
                "asset_class": p.get("asset_class", "Stock"),
                "value": p["value"],
            }
            for p in portfolio_data["positions"]
        }

        correlation_report = self.correlation_monitor.generate_correlation_report(
            returns_dict,
            weights,
            positions_dict,
            portfolio_data["total_value"],
            portfolio_data["current_vix"],
        )
        results["correlation"] = correlation_report

        # 4. Recovery Time Check
        recovery_status = self.recovery_tracker.update(
            datetime.now(),
            portfolio_data["total_value"],
            portfolio_data.get("peak_value", portfolio_data["total_value"]),
        )
        results["recovery"] = recovery_status

        # 5. Sharpe-Weighted Position Sizing
        if "strategies" in portfolio_data and "base_limits" in portfolio_data:
            strategies = {
                sid: StrategyPerformance(
                    strategy_id=sid,
                    sharpe_6m=s["sharpe_6m"],
                    sharpe_12m=s["sharpe_12m"],
                    returns=s.get("returns", []),
                    risk_level=s.get("risk_level", 5),
                )
                for sid, s in portfolio_data["strategies"].items()
            }

            allocation = self.position_sizer.calculate_portfolio_allocation(
                strategies,
                portfolio_data["base_limits"],
                portfolio_data["total_value"],
            )
            results["sharpe_allocation"] = allocation

        # 6. Overall Health Assessment
        health_score = self._calculate_health_score(results)
        results["health_score"] = health_score

        # 7. Required Actions
        actions = self._determine_required_actions(results)
        results["required_actions"] = actions

        return results

    def _calculate_health_score(self, results: Dict) -> Dict:
        """Calculate overall portfolio health score (0-100)"""

        score = 100
        issues = []

        # Liquidity (20 points)
        if not results["liquidity"]["compliance"]["meets_requirements"]:
            score -= 20
            issues.append("liquidity_violation")
        elif not results["liquidity"]["stress_test"]["passes_stress_test"]:
            score -= 10
            issues.append("liquidity_stress_fail")

        # Volatility (25 points)
        vol_status = results["volatility"]["status"]
        if vol_status == "circuit_breaker":
            score -= 25
            issues.append("volatility_circuit_breaker")
        elif vol_status == "warning":
            score -= 15
            issues.append("volatility_warning")
        elif vol_status == "caution":
            score -= 10
            issues.append("volatility_elevated")

        # Correlation (20 points)
        if not results["correlation"]["meets_requirements"]:
            score -= 20
            issues.append("correlation_violation")

        # Recovery (20 points)
        if results["recovery"]["in_drawdown"]:
            status = results["recovery"]["status"]
            if status == "critical":
                score -= 20
                issues.append("recovery_critical")
            elif status == "delayed":
                score -= 10
                issues.append("recovery_delayed")

        # Sharpe Performance (15 points)
        if "sharpe_allocation" in results:
            review_needed = results["sharpe_allocation"]["portfolio_summary"].get(
                "review_needed", 0
            )
            if review_needed > 0:
                score -= min(15, review_needed * 5)
                issues.append("sharpe_underperformance")

        # Determine rating
        if score >= 90:
            rating = "excellent"
        elif score >= 75:
            rating = "good"
        elif score >= 60:
            rating = "adequate"
        elif score >= 40:
            rating = "poor"
        else:
            rating = "critical"

        return {
            "score": max(0, score),
            "rating": rating,
            "issues": issues,
        }

    def _determine_required_actions(self, results: Dict) -> List[Dict]:
        """Determine required actions based on health check results"""

        actions = []

        # Liquidity violations
        if not results["liquidity"]["compliance"]["meets_requirements"]:
            actions.append({
                "priority": "high",
                "category": "liquidity",
                "action": "Increase Tier 1-2 assets to meet liquidity requirements",
                "violations": results["liquidity"]["compliance"]["violations"],
            })

        # Volatility circuit breakers
        vol_status = results["volatility"]["status"]
        if vol_status in ["warning", "circuit_breaker", "emergency"]:
            actions.append({
                "priority": "critical",
                "category": "volatility",
                "action": f"Volatility {vol_status} triggered",
                "required_actions": results["volatility"]["required_actions"],
            })

        # Correlation violations
        if not results["correlation"]["meets_requirements"]:
            actions.append({
                "priority": "medium",
                "category": "correlation",
                "action": "Reduce portfolio correlation through diversification",
                "violations": results["correlation"]["violations"],
            })

        # Recovery time issues
        if results["recovery"]["in_drawdown"]:
            if results["recovery"]["action_required"]:
                actions.append({
                    "priority": "high",
                    "category": "recovery",
                    "action": "Drawdown recovery delayed",
                    "required_actions": results["recovery"]["action_required"],
                })

        # Sharpe underperformance
        if "sharpe_allocation" in results:
            for strategy_id, alloc in results["sharpe_allocation"]["allocations"].items():
                if alloc["action"] in ["reduce", "close"]:
                    actions.append({
                        "priority": "medium",
                        "category": "sharpe_performance",
                        "action": f"{alloc['action']} position in {strategy_id}",
                        "reasoning": alloc["reasoning"],
                    })

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda x: priority_order.get(x["priority"], 3))

        # ── ZeroMQ real-time notifications (best-effort) ──────────────
        try:
            from agents.common.event_bus import (
                EventPublisher,
                TOPIC_CIRCUIT_BREAKER,
                TOPIC_PORTFOLIO_ALERT,
            )

            pub = EventPublisher()
            for act in actions:
                if act["category"] == "volatility" and act["priority"] == "critical":
                    pub.publish(TOPIC_CIRCUIT_BREAKER, {
                        "status": vol_status,
                        "action": act["action"],
                    })
                elif act["priority"] in ("critical", "high"):
                    pub.publish(TOPIC_PORTFOLIO_ALERT, {
                        "category": act["category"],
                        "action": act["action"],
                        "priority": act["priority"],
                    })
            pub.close()
        except Exception:
            pass  # ZeroMQ is best-effort; DB is the source of truth

        return actions

    def save_health_report(self, report: Dict, filepath: str):
        """Save health report to file"""
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

    def generate_summary(self, report: Dict) -> str:
        """Generate human-readable summary of health check"""

        summary = []
        summary.append(f"Portfolio Health Report - {report['timestamp']}")
        summary.append(f"Policy: {report['policy']}")
        summary.append(f"Total Value: ${report['total_value']:,.2f}")
        summary.append(f"\nHealth Score: {report['health_score']['score']}/100 ({report['health_score']['rating'].upper()})")

        if report['health_score']['issues']:
            summary.append(f"\nIssues Detected:")
            for issue in report['health_score']['issues']:
                summary.append(f"  - {issue}")

        if report['required_actions']:
            summary.append(f"\nRequired Actions ({len(report['required_actions'])}):")
            for i, action in enumerate(report['required_actions'][:5], 1):  # Top 5
                summary.append(f"  {i}. [{action['priority'].upper()}] {action['action']}")

        summary.append(f"\nLiquidity: {report['liquidity']['compliance']['meets_requirements']}")
        summary.append(f"Volatility Status: {report['volatility']['status']}")
        summary.append(f"Correlation: {report['correlation']['meets_requirements']}")
        summary.append(f"In Drawdown: {report['recovery']['in_drawdown']}")

        return "\n".join(summary)


# Example usage
if __name__ == "__main__":
    orchestrator = PortfolioOrchestrator(policy="MODERATE_AGGRESSIVE")

    # Sample portfolio data
    portfolio_data = {
        "total_value": 100000,
        "cash": 5000,
        "positions": [
            {
                "symbol": "SPY",
                "value": 20000,
                "tier": LiquidityTier.TIER_2,
                "avg_volume": 50000000,
                "spread": 0.001,
                "sector": "Market",
                "asset_class": "ETF",
                "returns": [0.01] * 90,
            },
            {
                "symbol": "AAPL",
                "value": 25000,
                "tier": LiquidityTier.TIER_2,
                "avg_volume": 80000000,
                "spread": 0.002,
                "sector": "Technology",
                "asset_class": "Stock",
                "returns": [0.012] * 90,
            },
        ],
        "returns_30d": [0.008] * 30,
        "returns_90d": [0.007] * 90,
        "current_vix": 18,
        "peak_value": 105000,
        "strategies": {
            "strategy_1": {
                "sharpe_6m": 2.5,
                "sharpe_12m": 2.3,
                "returns": [],
                "risk_level": 2,
            },
        },
        "base_limits": {"strategy_1": 20},
    }

    # Run comprehensive health check
    report = orchestrator.run_comprehensive_health_check(portfolio_data)

    # Print summary
    summary = orchestrator.generate_summary(report)
    print(summary)

    # Save full report
    orchestrator.save_health_report(report, "portfolio_health_report.json")
    print("\nFull report saved to portfolio_health_report.json")
