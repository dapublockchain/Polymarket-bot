"""
Tail Hedge Module for Tail Risk Underwriting Strategy.

This module provides optional hedging for tail risk positions.
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class HedgeType(str, Enum):
    """Types of hedging strategies."""
    NONE = "none"  # No hedging
    PARTIAL = "partial"  # Partial hedge (reduce exposure)
    FULL = "full"  # Full hedge (neutralize risk)


@dataclass
class HedgePosition:
    """A hedge position.

    Attributes:
        hedge_id: Unique hedge identifier
        original_market_id: Original tail risk position being hedged
        hedge_market_id: Market used for hedging
        hedge_type: Type of hedge
        hedge_ratio: Hedge ratio (0-1, where 1 = fully hedged)
        original_position_size: Original position size
        hedge_position_size: Hedge position size
        cost_usd: Cost of hedge in USDC
        effective_reduction: Reduction in worst case loss
    """
    hedge_id: str
    original_market_id: str
    hedge_market_id: str
    hedge_type: HedgeType
    hedge_ratio: Decimal
    original_position_size: Decimal
    hedge_position_size: Decimal
    cost_usd: Decimal
    effective_reduction: Decimal


class TailHedge:
    """
    Provides hedging strategies for tail risk positions.

    Note: Hedging is OPTIONAL and may not always be available or cost-effective.
    This module evaluates whether hedging makes sense for a given position.

    Hedging approaches:
    1. Cross-market hedge: Use opposite position in correlated market
    2. Partial hedge: Hedge portion of exposure
    3. No hedge: Accept full tail risk
    """

    def __init__(
        self,
        max_hedge_cost_pct: float = 0.05,  # Max 5% cost for hedge
        min_hedge_ratio: float = 0.5,  # Minimum 50% hedge if hedging
    ):
        """
        Initialize tail hedge module.

        Args:
            max_hedge_cost_pct: Maximum acceptable cost of hedge as % of position
            min_hedge_ratio: Minimum hedge ratio (0-1)
        """
        self.max_hedge_cost_pct = max_hedge_cost_pct
        self.min_hedge_ratio = min_hedge_ratio

        # Track active hedges
        self.active_hedges: Dict[str, HedgePosition] = {}

    async def evaluate_hedge(
        self,
        original_market_id: str,
        position_size: Decimal,
        worst_case_loss: Decimal,
        available_hedge_markets: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[HedgePosition]:
        """
        Evaluate and create a hedge if worthwhile.

        Args:
            original_market_id: Original market being hedged
            position_size: Original position size
            worst_case_loss: Worst case loss of original position
            available_hedge_markets: List of potential hedge markets

        Returns:
            HedgePosition if hedge created, None otherwise
        """
        # Check if hedge markets are available
        if not available_hedge_markets:
            logger.debug(f"No hedge markets available for {original_market_id}")
            return None

        # Find best hedge
        best_hedge = None
        best_cost = Decimal("Infinity")

        for hedge_market in available_hedge_markets:
            hedge = await self._evaluate_hedge_market(
                original_market_id=original_market_id,
                position_size=position_size,
                worst_case_loss=worst_case_loss,
                hedge_market=hedge_market,
            )

            if hedge and hedge.cost_usd < best_cost:
                best_hedge = hedge
                best_cost = hedge.cost_usd

        # Check if hedge is cost-effective
        if best_hedge:
            cost_pct = float(best_hedge.cost_usd / position_size)

            if cost_pct <= self.max_hedge_cost_pct:
                # Add to active hedges
                self.active_hedges[best_hedge.hedge_id] = best_hedge

                logger.info(
                    f"Hedge created: {best_hedge.hedge_id} - "
                    f"cost=${best_hedge.cost_usd:.2f} ({cost_pct:.2%}), "
                    f"reduction=${best_hedge.effective_reduction:.2f}"
                )

                return best_hedge
            else:
                logger.debug(
                    f"Hedge too expensive: {cost_pct:.2%} > {self.max_hedge_cost_pct:.2%}"
                )

        return None

    async def _evaluate_hedge_market(
        self,
        original_market_id: str,
        position_size: Decimal,
        worst_case_loss: Decimal,
        hedge_market: Dict[str, Any],
    ) -> Optional[HedgePosition]:
        """
        Evaluate a specific market for hedging.

        Args:
            original_market_id: Original market being hedged
            position_size: Original position size
            worst_case_loss: Worst case loss
            hedge_market: Potential hedge market data

        Returns:
            HedgePosition if viable, None otherwise
        """
        hedge_market_id = hedge_market.get("market_id")
        yes_price = Decimal(str(hedge_market.get("yes_price", "0")))
        no_price = Decimal(str(hedge_market.get("no_price", "0")))

        # For simplicity, we look for negatively correlated markets
        # In practice, this would require correlation analysis
        # Here we assume hedge_market has already been pre-filtered

        # Calculate hedge cost
        # Cost = hedge_position_size
        # We want to hedge to reduce worst case loss
        hedge_ratio = Decimal(str(self.min_hedge_ratio))
        hedge_position_size = position_size * hedge_ratio

        # Hedge cost is the cost of the hedge position
        # For binary options, this is roughly hedge_position_size * price
        # We use the lower price as conservative estimate
        hedge_cost = hedge_position_size * min(yes_price, no_price)

        # Effective reduction in worst case loss
        # If hedge pays off when original loses, reduction = hedge_payout - hedge_cost
        # This is simplified - real calculation depends on hedge structure
        effective_reduction = worst_case_loss * hedge_ratio - hedge_cost

        if effective_reduction <= 0:
            return None  # Hedge doesn't reduce risk

        # Create hedge position
        import time
        hedge_id = f"hedge_{int(time.time())}_{original_market_id}_{hedge_market_id}"

        return HedgePosition(
            hedge_id=hedge_id,
            original_market_id=original_market_id,
            hedge_market_id=hedge_market_id,
            hedge_type=HedgeType.PARTIAL,
            hedge_ratio=hedge_ratio,
            original_position_size=position_size,
            hedge_position_size=hedge_position_size,
            cost_usd=hedge_cost,
            effective_reduction=effective_reduction,
        )

    def close_hedge(self, hedge_id: str) -> bool:
        """
        Close an active hedge.

        Args:
            hedge_id: Hedge identifier

        Returns:
            True if hedge closed
        """
        if hedge_id in self.active_hedges:
            del self.active_hedges[hedge_id]
            logger.info(f"Hedge closed: {hedge_id}")
            return True
        return False

    def get_active_hedges(self) -> List[HedgePosition]:
        """
        Get all active hedges.

        Returns:
            List of active hedge positions
        """
        return list(self.active_hedges.values())

    def get_hedge_metrics(self) -> Dict[str, Any]:
        """
        Get hedging metrics.

        Returns:
            Metrics dictionary
        """
        total_cost = sum(h.cost_usd for h in self.active_hedges.values())
        total_reduction = sum(h.effective_reduction for h in self.active_hedges.values())

        return {
            "active_hedge_count": len(self.active_hedges),
            "total_hedge_cost": str(total_cost),
            "total_risk_reduction": str(total_reduction),
            "average_hedge_ratio": sum(float(h.hedge_ratio) for h in self.active_hedges.values()) / len(self.active_hedges) if self.active_hedges else 0.0,
        }
