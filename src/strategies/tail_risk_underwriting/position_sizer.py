"""
Position Sizer for Tail Risk Underwriting Strategy.

This module calculates position sizes with worst-case loss caps.
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass
from collections import defaultdict

from loguru import logger

from .candidate_selector import TailRiskCandidate


@dataclass
class PositionSize:
    """Calculated position size for tail risk underwriting.

    Attributes:
        market_id: Market identifier
        position_size_usd: Position size in USDC
        worst_case_loss: Worst case loss in USDC
        worst_case_loss_pct: Worst case loss as percentage of capital
        potential_payout: Potential payout in USDC
        payout_ratio: Payout as multiple of stake
        kelly_fraction: Kelly criterion fraction
        acceptable: Whether position size is acceptable
        reason: Explanation
    """
    market_id: str
    position_size_usd: Decimal
    worst_case_loss: Decimal
    worst_case_loss_pct: Decimal
    potential_payout: Decimal
    payout_ratio: float
    kelly_fraction: float
    acceptable: bool
    reason: str


@dataclass
class ClusterMetrics:
    """Metrics for a correlation cluster.

    Attributes:
        cluster_id: Cluster identifier
        total_exposure: Total exposure in USDC
        total_worst_case_loss: Total worst case loss across cluster
        position_count: Number of positions in cluster
        utilization_pct: Utilization of cluster limit
    """
    cluster_id: str
    total_exposure: Decimal
    total_worst_case_loss: Decimal
    position_count: int
    utilization_pct: float


class PositionSizer:
    """
    Calculates position sizes for tail risk underwriting.

    Key features:
    - Worst-case loss caps
    - Kelly criterion sizing
    - Correlation cluster limits
    - Risk-based position sizing
    """

    def __init__(
        self,
        max_worst_case_loss: Decimal = Decimal("100"),
        max_cluster_exposure: Decimal = Decimal("300"),
        kelly_multiplier: float = 0.25,  # Conservative Kelly (1/4 Kelly)
    ):
        """
        Initialize position sizer.

        Args:
            max_worst_case_loss: Maximum worst case loss per position
            max_cluster_exposure: Maximum exposure per correlation cluster
            kelly_multiplier: Kelly criterion multiplier (0.25 = quarter Kelly)
        """
        self.max_worst_case_loss = max_worst_case_loss
        self.max_cluster_exposure = max_cluster_exposure
        self.kelly_multiplier = kelly_multiplier

        # Track cluster exposures
        self.cluster_exposures: Dict[str, Decimal] = defaultdict(Decimal)
        self.cluster_losses: Dict[str, Decimal] = defaultdict(Decimal)

    async def calculate_position_size(
        self,
        candidate: TailRiskCandidate,
        capital: Decimal,
    ) -> PositionSize:
        """
        Calculate position size for a tail risk candidate.

        Args:
            candidate: Tail risk candidate
            capital: Available capital

        Returns:
            PositionSize with calculated size
        """
        # Calculate Kelly criterion position
        # Kelly = (p * b - q) / b
        # where:
        #   p = probability of winning (tail_probability)
        #   b = payout ratio (potential_payout / worst_case_loss)
        #   q = 1 - p
        p = candidate.tail_probability
        b = float(candidate.potential_payout)
        q = 1.0 - p

        if b > 0:
            kelly_fraction = (p * b - q) / b
        else:
            kelly_fraction = 0.0

        # Kelly can be negative (negative EV), clamp to 0
        kelly_fraction = max(kelly_fraction, 0.0)

        # Apply conservative multiplier (quarter Kelly)
        kelly_fraction *= self.kelly_multiplier

        # Calculate position size based on Kelly
        position_size_usd = capital * Decimal(str(kelly_fraction))

        # Worst case loss = position size (we lose the stake if tail event doesn't occur)
        worst_case_loss = position_size_usd

        # Check worst case loss limit
        if worst_case_loss > self.max_worst_case_loss:
            # Cap position at max worst case loss
            position_size_usd = self.max_worst_case_loss
            worst_case_loss = self.max_worst_case_loss
            kelly_fraction = float(position_size_usd / capital) if capital > 0 else 0.0

        # Check cluster exposure limit
        cluster_id = candidate.correlation_cluster
        current_cluster_exposure = self.cluster_exposures.get(cluster_id, Decimal("0"))
        new_cluster_exposure = current_cluster_exposure + position_size_usd

        if new_cluster_exposure > self.max_cluster_exposure:
            # Reduce position to fit within cluster limit
            available_cluster_capacity = self.max_cluster_exposure - current_cluster_exposure
            if available_cluster_capacity <= 0:
                return PositionSize(
                    market_id=candidate.market_id,
                    position_size_usd=Decimal("0"),
                    worst_case_loss=Decimal("0"),
                    worst_case_loss_pct=Decimal("0"),
                    potential_payout=Decimal("0"),
                    payout_ratio=0.0,
                    kelly_fraction=0.0,
                    acceptable=False,
                    reason=f"Cluster {cluster_id} at max capacity: ${current_cluster_exposure} / ${self.max_cluster_exposure}",
                )
            position_size_usd = available_cluster_capacity
            worst_case_loss = position_size_usd
            kelly_fraction = float(position_size_usd / capital) if capital > 0 else 0.0

        # Calculate potential payout
        potential_payout = position_size_usd * candidate.potential_payout
        payout_ratio = float(candidate.potential_payout)

        # Calculate worst case loss as percentage of capital
        worst_case_loss_pct = (worst_case_loss / capital * 100) if capital > 0 else Decimal("0")

        # Check if position size is acceptable
        # Minimum position size = $10
        if position_size_usd < Decimal("10"):
            return PositionSize(
                market_id=candidate.market_id,
                position_size_usd=position_size_usd,
                worst_case_loss=worst_case_loss,
                worst_case_loss_pct=worst_case_loss_pct,
                potential_payout=potential_payout,
                payout_ratio=payout_ratio,
                kelly_fraction=kelly_fraction,
                acceptable=False,
                reason=f"Position size too small: ${position_size_usd}",
            )

        # All checks passed
        return PositionSize(
            market_id=candidate.market_id,
            position_size_usd=position_size_usd,
            worst_case_loss=worst_case_loss,
            worst_case_loss_pct=worst_case_loss_pct,
            potential_payout=potential_payout,
            payout_ratio=payout_ratio,
            kelly_fraction=kelly_fraction,
            acceptable=True,
            reason=(
                f"Position sized: ${position_size_usd:.2f}, "
                f"max_loss=${worst_case_loss:.2f} ({worst_case_loss_pct:.2f}%), "
                f"potential=${potential_payout:.2f} ({payout_ratio:.1f}x), "
                f"kelly={kelly_fraction:.3f}"
            ),
        )

    def add_position(
        self,
        cluster_id: str,
        position_size: Decimal,
    ) -> None:
        """
        Add a position to cluster tracking.

        Args:
            cluster_id: Cluster identifier
            position_size: Position size in USDC
        """
        self.cluster_exposures[cluster_id] += position_size
        self.cluster_losses[cluster_id] += position_size  # Worst case = position size

    def remove_position(
        self,
        cluster_id: str,
        position_size: Decimal,
    ) -> None:
        """
        Remove a position from cluster tracking.

        Args:
            cluster_id: Cluster identifier
            position_size: Position size in USDC
        """
        if cluster_id in self.cluster_exposures:
            self.cluster_exposures[cluster_id] -= position_size
            if self.cluster_exposures[cluster_id] <= 0:
                del self.cluster_exposures[cluster_id]

        if cluster_id in self.cluster_losses:
            self.cluster_losses[cluster_id] -= position_size
            if self.cluster_losses[cluster_id] <= 0:
                del self.cluster_losses[cluster_id]

    def get_cluster_metrics(self, cluster_id: str) -> ClusterMetrics:
        """
        Get metrics for a correlation cluster.

        Args:
            cluster_id: Cluster identifier

        Returns:
            ClusterMetrics
        """
        total_exposure = self.cluster_exposures.get(cluster_id, Decimal("0"))
        total_worst_case_loss = self.cluster_losses.get(cluster_id, Decimal("0"))

        # Count positions (estimate from exposure)
        # This is approximate - real implementation would track exact count
        position_count = len([c for c in self.cluster_exposures.keys() if c == cluster_id])

        utilization = float(total_exposure / self.max_cluster_exposure) if self.max_cluster_exposure > 0 else 0.0

        return ClusterMetrics(
            cluster_id=cluster_id,
            total_exposure=total_exposure,
            total_worst_case_loss=total_worst_case_loss,
            position_count=position_count,
            utilization_pct=min(utilization, 1.0),
        )

    def get_all_cluster_metrics(self) -> Dict[str, ClusterMetrics]:
        """
        Get metrics for all clusters.

        Returns:
            Dictionary mapping cluster_id to ClusterMetrics
        """
        clusters = set(self.cluster_exposures.keys()) | set(self.cluster_losses.keys())
        return {
            cluster_id: self.get_cluster_metrics(cluster_id)
            for cluster_id in clusters
        }
