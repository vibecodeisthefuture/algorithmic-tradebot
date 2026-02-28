"""
Correlation Monitoring System
Tracks portfolio correlation and enforces diversification requirements
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np
from datetime import datetime


@dataclass
class CorrelationRequirements:
    """Correlation and diversification requirements"""
    max_pairwise: float
    max_avg_portfolio: float
    max_avg_high_vix: float
    min_sectors: int
    min_asset_classes: int
    max_single_sector: float  # percentage


class CorrelationMonitor:
    """Monitor portfolio correlation and diversification"""

    REQUIREMENTS = {
        "HIGH": CorrelationRequirements(0.75, 0.50, 0.45, 3, 2, 50),
        "MODERATE_AGGRESSIVE": CorrelationRequirements(0.70, 0.40, 0.35, 4, 3, 45),
        "MODERATE": CorrelationRequirements(0.70, 0.40, 0.35, 4, 3, 40),
        "LOW": CorrelationRequirements(0.65, 0.30, 0.25, 5, 3, 30),
    }

    def __init__(self, policy: str = "MODERATE_AGGRESSIVE"):
        self.policy = policy
        self.requirements = self.REQUIREMENTS[policy]

    def calculate_correlation_matrix(
        self, returns_dict: Dict[str, List[float]]
    ) -> np.ndarray:
        """
        Calculate correlation matrix from returns

        Args:
            returns_dict: {symbol: [returns_list]}

        Returns:
            Correlation matrix as numpy array
        """

        # Convert to numpy array (symbols x time)
        symbols = list(returns_dict.keys())
        returns_matrix = np.array([returns_dict[sym] for sym in symbols])

        # Calculate correlation
        corr_matrix = np.corrcoef(returns_matrix)

        return corr_matrix, symbols

    def get_max_pairwise_correlation(
        self, corr_matrix: np.ndarray, symbols: List[str]
    ) -> Tuple[float, str, str]:
        """Find maximum pairwise correlation (excluding diagonal)"""

        n = len(corr_matrix)
        max_corr = -1
        max_pair = ("", "")

        for i in range(n):
            for j in range(i + 1, n):
                corr = corr_matrix[i, j]
                if corr > max_corr:
                    max_corr = corr
                    max_pair = (symbols[i], symbols[j])

        return max_corr, max_pair[0], max_pair[1]

    def calculate_avg_correlation(
        self, corr_matrix: np.ndarray
    ) -> float:
        """Calculate average correlation (excluding diagonal)"""

        n = len(corr_matrix)
        if n <= 1:
            return 0.0

        # Get upper triangle (excluding diagonal)
        upper_triangle = corr_matrix[np.triu_indices(n, k=1)]

        return np.mean(upper_triangle)

    def calculate_portfolio_correlation(
        self,
        returns_dict: Dict[str, List[float]],
        weights: Dict[str, float],
    ) -> float:
        """
        Calculate weighted average portfolio correlation

        More sophisticated: weight correlations by position sizes
        """

        corr_matrix, symbols = self.calculate_correlation_matrix(returns_dict)

        # Create weight vector in same order as symbols
        weight_vector = np.array([weights.get(sym, 0) for sym in symbols])
        weight_vector = weight_vector / weight_vector.sum()  # Normalize

        # Calculate weighted correlation
        weighted_corr = 0
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                weighted_corr += (
                    weight_vector[i] * weight_vector[j] * corr_matrix[i, j]
                )

        # Normalize by sum of weight products
        normalization = np.sum(weight_vector[:, np.newaxis] * weight_vector)
        if normalization > 0:
            weighted_corr = weighted_corr / normalization

        return weighted_corr

    def check_diversification(
        self,
        positions: Dict[str, Dict],  # {symbol: {sector, asset_class, value}}
        total_value: float,
    ) -> Dict:
        """Check diversification requirements"""

        # Count sectors and asset classes
        sectors = set()
        asset_classes = set()
        sector_values = {}

        for symbol, info in positions.items():
            sectors.add(info["sector"])
            asset_classes.add(info["asset_class"])

            sector = info["sector"]
            sector_values[sector] = sector_values.get(sector, 0) + info["value"]

        # Calculate sector concentrations
        sector_percentages = {
            sector: (value / total_value) * 100
            for sector, value in sector_values.items()
        }

        # Find max sector concentration
        max_sector = max(sector_percentages.items(), key=lambda x: x[1])

        # Check violations
        violations = []

        if len(sectors) < self.requirements.min_sectors:
            violations.append(
                f"Too few sectors: {len(sectors)} < {self.requirements.min_sectors}"
            )

        if len(asset_classes) < self.requirements.min_asset_classes:
            violations.append(
                f"Too few asset classes: {len(asset_classes)} "
                f"< {self.requirements.min_asset_classes}"
            )

        if max_sector[1] > self.requirements.max_single_sector:
            violations.append(
                f"Sector {max_sector[0]} exceeds max: {max_sector[1]:.1f}% "
                f"> {self.requirements.max_single_sector}%"
            )

        return {
            "num_sectors": len(sectors),
            "num_asset_classes": len(asset_classes),
            "sectors": list(sectors),
            "asset_classes": list(asset_classes),
            "sector_concentrations": sector_percentages,
            "max_sector_concentration": {
                "sector": max_sector[0],
                "percentage": round(max_sector[1], 2),
            },
            "meets_requirements": len(violations) == 0,
            "violations": violations,
        }

    def generate_correlation_report(
        self,
        returns_dict: Dict[str, List[float]],
        weights: Dict[str, float],
        positions: Dict[str, Dict],
        total_value: float,
        current_vix: float,
    ) -> Dict:
        """Generate comprehensive correlation report"""

        # Calculate correlation metrics
        corr_matrix, symbols = self.calculate_correlation_matrix(returns_dict)
        max_corr, sym1, sym2 = self.get_max_pairwise_correlation(corr_matrix, symbols)
        avg_corr = self.calculate_avg_correlation(corr_matrix)
        weighted_corr = self.calculate_portfolio_correlation(returns_dict, weights)

        # Check diversification
        diversification = self.check_diversification(positions, total_value)

        # Determine appropriate threshold based on VIX
        if current_vix > 25:
            max_allowed = self.requirements.max_avg_high_vix
            vix_mode = "high_vix"
        else:
            max_allowed = self.requirements.max_avg_portfolio
            vix_mode = "normal"

        # Check violations
        violations = []

        if max_corr > self.requirements.max_pairwise:
            violations.append(
                f"Max pairwise correlation exceeds limit: {max_corr:.3f} "
                f"> {self.requirements.max_pairwise} ({sym1}-{sym2})"
            )

        if weighted_corr > max_allowed:
            violations.append(
                f"Portfolio correlation exceeds limit ({vix_mode}): "
                f"{weighted_corr:.3f} > {max_allowed}"
            )

        return {
            "policy": self.policy,
            "vix": current_vix,
            "vix_mode": vix_mode,
            "correlation_metrics": {
                "max_pairwise": round(max_corr, 3),
                "max_pair": f"{sym1}-{sym2}",
                "avg_correlation": round(avg_corr, 3),
                "weighted_portfolio_correlation": round(weighted_corr, 3),
            },
            "thresholds": {
                "max_pairwise": self.requirements.max_pairwise,
                "max_avg_portfolio": self.requirements.max_avg_portfolio,
                "max_avg_high_vix": self.requirements.max_avg_high_vix,
                "current_max_allowed": max_allowed,
            },
            "diversification": diversification,
            "meets_requirements": (
                len(violations) == 0 and diversification["meets_requirements"]
            ),
            "violations": violations + diversification["violations"],
            "timestamp": datetime.now().isoformat(),
        }


# Example usage
if __name__ == "__main__":
    monitor = CorrelationMonitor(policy="MODERATE_AGGRESSIVE")

    # Generate sample data
    np.random.seed(42)

    # Simulate correlated returns
    n_days = 90
    market_return = np.random.normal(0.001, 0.02, n_days)

    returns_dict = {
        "AAPL": list(market_return + np.random.normal(0, 0.01, n_days)),
        "MSFT": list(market_return + np.random.normal(0, 0.01, n_days)),
        "GOOGL": list(market_return + np.random.normal(0, 0.012, n_days)),
        "AMZN": list(market_return + np.random.normal(0, 0.015, n_days)),
        "TSLA": list(np.random.normal(0.002, 0.03, n_days)),  # Less correlated
    }

    weights = {
        "AAPL": 0.25,
        "MSFT": 0.25,
        "GOOGL": 0.20,
        "AMZN": 0.20,
        "TSLA": 0.10,
    }

    positions = {
        "AAPL": {"sector": "Technology", "asset_class": "Stock", "value": 25000},
        "MSFT": {"sector": "Technology", "asset_class": "Stock", "value": 25000},
        "GOOGL": {"sector": "Technology", "asset_class": "Stock", "value": 20000},
        "AMZN": {"sector": "Consumer", "asset_class": "Stock", "value": 20000},
        "TSLA": {"sector": "Automotive", "asset_class": "Stock", "value": 10000},
    }

    report = monitor.generate_correlation_report(
        returns_dict, weights, positions, 100000, current_vix=19
    )

    print("Correlation Report:")
    print(f"Policy: {report['policy']}")
    print(f"VIX: {report['vix']} ({report['vix_mode']})")
    print(f"\nCorrelation Metrics:")
    for key, value in report['correlation_metrics'].items():
        print(f"  {key}: {value}")
    print(f"\nDiversification:")
    print(f"  Sectors: {report['diversification']['num_sectors']}")
    print(f"  Asset Classes: {report['diversification']['num_asset_classes']}")
    print(f"  Max Sector: {report['diversification']['max_sector_concentration']}")
    print(f"\nMeets Requirements: {report['meets_requirements']}")
    if report['violations']:
        print(f"\nViolations:")
        for v in report['violations']:
            print(f"  - {v}")
