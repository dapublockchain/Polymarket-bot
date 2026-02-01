"""
Spread Model for Market Making Strategy.

This module calculates optimal bid-ask spreads for market making.
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class PricingModel(str, Enum):
    """Pricing model types."""
    FIXED_SPREAD = "fixed_spread"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    INVENTORY_ADJUSTED = "inventory_adjusted"


@dataclass
class SpreadCalculation:
    """Calculated bid-ask spread.

    Attributes:
        mid_price: Mid-market price
        bid_price: Calculated bid price
        ask_price: Calculated ask price
        spread_bps: Spread in basis points
        spread_pct: Spread as percentage
        inventory_skew_factor: Inventory skew adjustment factor (-1 to 1)
        volatility_factor: Volatility adjustment factor
        is_acceptable: Whether spread is within acceptable bounds
        reason: Explanation
    """
    mid_price: Decimal
    bid_price: Decimal
    ask_price: Decimal
    spread_bps: int
    spread_pct: Decimal
    inventory_skew_factor: Decimal
    volatility_factor: float
    is_acceptable: bool
    reason: str


class SpreadModel:
    """
    Calculates optimal bid-ask spreads for market making.

    Key features:
    - Fixed spread or volatility-adjusted spread
    - Inventory skew adjustment
    - Post-only enforcement
    """

    def __init__(
        self,
        default_spread_bps: int = 50,  # 0.5% default spread
        max_spread_bps: int = 100,  # 1% max spread
        min_spread_bps: int = 10,  # 0.1% min spread
        pricing_model: PricingModel = PricingModel.FIXED_SPREAD,
    ):
        """
        Initialize spread model.

        Args:
            default_spread_bps: Default spread in basis points
            max_spread_bps: Maximum allowed spread in basis points
            min_spread_bps: Minimum allowed spread in basis points
            pricing_model: Pricing model to use
        """
        self.default_spread_bps = default_spread_bps
        self.max_spread_bps = max_spread_bps
        self.min_spread_bps = min_spread_bps
        self.pricing_model = pricing_model

    async def calculate_spread(
        self,
        mid_price: Decimal,
        inventory_skew: Decimal = Decimal("0"),
        volatility_score: float = 0.0,
        order_book_snapshot: Optional[Dict[str, Any]] = None,
    ) -> SpreadCalculation:
        """
        Calculate optimal bid-ask spread.

        Args:
            mid_price: Mid-market price
            inventory_skew: Inventory skew (-1 to 1, negative = short biased)
            volatility_score: Volatility score (0-1)
            order_book_snapshot: Optional order book data

        Returns:
            SpreadCalculation with bid/ask prices
        """
        # Calculate base spread based on model
        if self.pricing_model == PricingModel.FIXED_SPREAD:
            spread_bps = self.default_spread_bps
            volatility_factor = 0.0
        elif self.pricing_model == PricingModel.VOLATILITY_ADJUSTED:
            spread_bps, volatility_factor = self._calculate_volatility_adjusted_spread(
                volatility_score=volatility_score,
            )
        else:  # INVENTORY_ADJUSTED
            spread_bps, volatility_factor = self._calculate_inventory_adjusted_spread(
                inventory_skew=inventory_skew,
                volatility_score=volatility_score,
            )

        # Apply inventory skew to prices
        # Positive skew = long biased => lower ask, higher bid
        # Negative skew = short biased => higher ask, lower bid
        skew_adjustment = Decimal(str(inventory_skew)) * Decimal("0.02")  # Max 2% adjustment

        # Calculate bid and ask prices
        half_spread_pct = Decimal(spread_bps) / Decimal("20000")  # Convert bps to decimal, then half

        # Apply skew adjustment
        bid_adjustment = half_spread_pct + skew_adjustment
        ask_adjustment = half_spread_pct - skew_adjustment

        bid_price = mid_price - (mid_price * bid_adjustment)
        ask_price = mid_price + (mid_price * ask_adjustment)

        # Ensure prices are valid (0-1 range for binary options)
        bid_price = max(Decimal("0.01"), min(bid_price, mid_price - Decimal("0.01")))
        ask_price = max(mid_price + Decimal("0.01"), min(ask_price, Decimal("0.99")))

        # Calculate actual spread
        actual_spread_pct = (ask_price - bid_price) / mid_price
        actual_spread_bps = int(actual_spread_pct * 10000)

        # Check if acceptable
        is_acceptable = self.min_spread_bps <= actual_spread_bps <= self.max_spread_bps

        if is_acceptable:
            reason = (
                f"Spread acceptable: {actual_spread_bps} bps (bid={bid_price:.4f}, ask={ask_price:.4f}), "
                f"skew={float(inventory_skew):.2f}"
            )
        else:
            reason = (
                f"Spread out of bounds: {actual_spread_bps} bps "
                f"(min={self.min_spread_bps}, max={self.max_spread_bps})"
            )

        calculation = SpreadCalculation(
            mid_price=mid_price,
            bid_price=bid_price,
            ask_price=ask_price,
            spread_bps=actual_spread_bps,
            spread_pct=actual_spread_pct,
            inventory_skew_factor=inventory_skew,
            volatility_factor=volatility_factor,
            is_acceptable=is_acceptable,
            reason=reason,
        )

        if is_acceptable:
            logger.debug(f"Spread calculated: {actual_spread_bps} bps")
        else:
            logger.warning(f"Spread calculation failed: {reason}")

        return calculation

    def _calculate_volatility_adjusted_spread(
        self,
        volatility_score: float,
    ) -> tuple[int, float]:
        """
        Calculate spread adjusted for volatility.

        Higher volatility = wider spread for protection.

        Args:
            volatility_score: Volatility score (0-1)

        Returns:
            Tuple of (spread_bps, volatility_factor)
        """
        # Base spread
        base_spread = self.default_spread_bps

        # Volatility multiplier: 1.0 to 3.0x based on volatility
        vol_multiplier = 1.0 + (volatility_score * 2.0)

        # Calculate adjusted spread
        adjusted_spread = int(base_spread * vol_multiplier)

        # Cap at max
        adjusted_spread = min(adjusted_spread, self.max_spread_bps)

        # Ensure at least min
        adjusted_spread = max(adjusted_spread, self.min_spread_bps)

        return adjusted_spread, volatility_score

    def _calculate_inventory_adjusted_spread(
        self,
        inventory_skew: Decimal,
        volatility_score: float,
    ) -> tuple[int, float]:
        """
        Calculate spread adjusted for inventory and volatility.

        Args:
            inventory_skew: Inventory skew (-1 to 1)
            volatility_score: Volatility score (0-1)

        Returns:
            Tuple of (spread_bps, volatility_factor)
        """
        # Start with volatility-adjusted spread
        spread_bps, _ = self._calculate_volatility_adjusted_spread(volatility_score)

        # Inventory skew can widen spread slightly when heavily biased
        skew_abs = abs(float(inventory_skew))
        skew_multiplier = 1.0 + (skew_abs * 0.5)  # Up to 1.5x wider

        adjusted_spread = int(spread_bps * skew_multiplier)
        adjusted_spread = min(adjusted_spread, self.max_spread_bps)

        return adjusted_spread, volatility_score


def calculate_spread_sync(
    model: SpreadModel,
    mid_price: Decimal,
    inventory_skew: Decimal = Decimal("0"),
) -> SpreadCalculation:
    """
    Synchronous wrapper for spread calculation.

    Args:
        model: SpreadModel instance
        mid_price: Mid-market price
        inventory_skew: Inventory skew

    Returns:
        SpreadCalculation
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        model.calculate_spread(
            mid_price=mid_price,
            inventory_skew=inventory_skew,
        )
    )
