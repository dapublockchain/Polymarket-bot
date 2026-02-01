"""
Tail Risk Underwriting Strategy.

This strategy insures against extreme events (NOT risk-free).

WARNING: This strategy has explicit worst-case loss caps.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List

from loguru import logger

from src.core.models import TailRiskSignal, RiskTag
from src.core.config import Config
from .candidate_selector import CandidateSelector, TailRiskCandidate
from .position_sizer import PositionSizer, PositionSize
from .tail_hedge import TailHedge, HedgePosition


class TailRiskStrategy:
    """
    Tail risk underwriting strategy.

    Insures against extreme events for a premium.

    Key features:
    - Explicit worst-case loss caps
    - Correlation cluster limits
    - Kelly criterion position sizing
    - Optional hedging

    All signals are tagged with TAIL_RISK and CORRELATION_CLUSTER_RISK.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        """
        Initialize tail risk strategy.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or Config()

        # Initialize components
        self.candidate_selector = CandidateSelector(
            min_tail_probability=self.config.TAIL_RISK_MIN_TAIL_PROBABILITY,
            max_tail_probability=0.20,
            min_payout_ratio=10.0,
        )

        self.position_sizer = PositionSizer(
            max_worst_case_loss=self.config.TAIL_RISK_MAX_WORST_CASE_LOSS,
            max_cluster_exposure=self.config.TAIL_RISK_MAX_CORRELATION_CLUSTER_EXPOSURE,
            kelly_multiplier=0.25,  # Conservative quarter Kelly
        )

        self.hedge_module = TailHedge(
            max_hedge_cost_pct=0.05,
            min_hedge_ratio=0.5,
        )

        self.enabled = self.config.TAIL_RISK_ENABLED

        if self.enabled:
            logger.info("Tail Risk Strategy initialized (NOT risk-free)")
        else:
            logger.info("Tail Risk Strategy initialized (DISABLED)")

    async def evaluate_markets(
        self,
        markets: List[Dict[str, Any]],
        capital: Decimal,
    ) -> List[TailRiskSignal]:
        """
        Evaluate markets for tail risk opportunities.

        Args:
            markets: List of market dictionaries
            capital: Available capital

        Returns:
            List of tail risk signals
        """
        if not self.enabled:
            logger.debug("Tail Risk Strategy is disabled")
            return []

        # Select candidates
        candidates = await self.candidate_selector.select_candidates(markets)

        if not candidates:
            logger.debug("No tail risk candidates found")
            return []

        # Calculate position sizes and create signals
        signals = []

        for candidate in candidates:
            position_size = await self.position_sizer.calculate_position_size(
                candidate=candidate,
                capital=capital,
            )

            if not position_size.acceptable:
                logger.debug(
                    f"Position size rejected for {candidate.market_id}: "
                    f"{position_size.reason}"
                )
                continue

            # Calculate expected profit (insurance premium)
            # For tail risk, profit = potential_payout * tail_probability - cost
            # This is the expected value of the insurance contract
            expected_payout = position_size.potential_payout * candidate.tail_probability
            expected_profit = expected_payout - position_size.position_size_usd

            if expected_profit <= 0:
                logger.debug(
                    f"Negative expected value for {candidate.market_id}: "
                    f"${expected_profit:.2f}"
                )
                continue

            # Determine which side to bet on (the tail event)
            if candidate.yes_price < candidate.no_price:
                # YES is the tail event (low probability)
                yes_price = candidate.yes_price
                no_price = candidate.no_price
                bet_side = "YES"
            else:
                # NO is the tail event
                yes_price = candidate.yes_price
                no_price = candidate.no_price
                bet_side = "NO"

            # Create signal
            signal = TailRiskSignal(
                strategy="tail_risk_underwriting",
                token_id=candidate.market_id,
                signal_type="BUY",
                expected_profit=expected_profit,
                trade_size=position_size.position_size_usd,
                yes_price=yes_price,
                no_price=no_price,
                confidence=self._calculate_confidence(
                    candidate=candidate,
                    position_size=position_size,
                ),
                reason=(
                    f"Tail risk underwriting: {candidate.category.value}, "
                    f"tail_prob={candidate.tail_probability:.3f}, "
                    f"payout={position_size.payout_ratio:.1f}x, "
                    f"max_loss=${position_size.worst_case_loss:.2f}, "
                    f"exp_profit=${expected_profit:.2f}, "
                    f"cluster={candidate.correlation_cluster}"
                ),
                worst_case_loss=position_size.worst_case_loss,
                correlation_cluster=candidate.correlation_cluster,
                hedge_ratio=None,  # Will be set if hedging is used
                tail_probability=candidate.tail_probability,
                max_exposure=self.config.TAIL_RISK_MAX_CORRELATION_CLUSTER_EXPOSURE,
            )

            # Add position to tracker
            self.position_sizer.add_position(
                cluster_id=candidate.correlation_cluster,
                position_size=position_size.position_size_usd,
            )

            signals.append(signal)

            logger.info(
                f"Tail risk signal: {candidate.market_id} - "
                f"{candidate.category.value}, ${expected_profit:.2f} profit, "
                f"${position_size.worst_case_loss:.2f} max loss"
            )

        return signals

    async def evaluate_hedge_opportunities(
        self,
        signals: List[TailRiskSignal],
        available_hedge_markets: List[Dict[str, Any]],
    ) -> List[HedgePosition]:
        """
        Evaluate hedging opportunities for tail risk signals.

        Args:
            signals: Tail risk signals
            available_hedge_markets: Potential hedge markets

        Returns:
            List of hedge positions created
        """
        hedges = []

        for signal in signals:
            hedge = await self.hedge_module.evaluate_hedge(
                original_market_id=signal.token_id,
                position_size=signal.trade_size,
                worst_case_loss=signal.worst_case_loss,
                available_hedge_markets=available_hedge_markets,
            )

            if hedge:
                hedges.append(hedge)
                # Update signal with hedge ratio
                signal.hedge_ratio = hedge.hedge_ratio

        return hedges

    def get_cluster_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all correlation clusters.

        Returns:
            Dictionary of cluster metrics
        """
        return self.position_sizer.get_all_cluster_metrics()

    def get_hedge_metrics(self) -> Dict[str, Any]:
        """
        Get hedging metrics.

        Returns:
            Metrics dictionary
        """
        return self.hedge_module.get_hedge_metrics()

    def _calculate_confidence(
        self,
        candidate: TailRiskCandidate,
        position_size: PositionSize,
    ) -> float:
        """
        Calculate confidence score for the signal.

        Args:
            candidate: Tail risk candidate
            position_size: Calculated position size

        Returns:
            Confidence score (0-1)
        """
        # Base confidence from Kelly fraction
        # Higher Kelly = higher confidence (up to a point)
        kelly_confidence = min(position_size.kelly_fraction * 10, 1.0) * 0.4

        # Add confidence from payout ratio
        # Higher payout ratio = better risk/reward
        payout_confidence = min(position_size.payout_ratio / 100, 1.0) * 0.3

        # Add confidence from probability
        # Not too low (unpredictable) or too high (not really tail risk)
        if 0.02 <= candidate.tail_probability <= 0.10:
            prob_confidence = 0.3
        elif 0.01 <= candidate.tail_probability < 0.02:
            prob_confidence = 0.2
        elif 0.10 < candidate.tail_probability <= 0.20:
            prob_confidence = 0.2
        else:
            prob_confidence = 0.1

        return kelly_confidence + payout_confidence + prob_confidence

    def get_risk_tags(self) -> List[str]:
        """
        Get risk tags for this strategy.

        Returns:
            List of risk tags
        """
        return [
            RiskTag.TAIL_RISK.value,
            RiskTag.CORRELATION_CLUSTER_RISK.value,
        ]


def create_tail_risk_strategy(config: Optional[Config] = None) -> TailRiskStrategy:
    """
    Factory function to create tail risk strategy.

    Args:
        config: Optional configuration

    Returns:
        TailRiskStrategy instance
    """
    return TailRiskStrategy(config=config)
