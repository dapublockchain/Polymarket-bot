"""
Market Making Strategy.

This strategy provides bid-ask spreads to earn the spread.

CRITICAL: This strategy MUST use post-only orders to avoid taking liquidity.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List

from loguru import logger

from src.core.models import MarketMakingSignal, RiskTag
from src.core.config import Config
from .spread_model import SpreadModel, SpreadCalculation, PricingModel
from .quote_manager import QuoteManager, Quote
from .inventory_skew import InventoryManager, InventoryMetrics, Side


class MarketMakingStrategy:
    """
    Market making strategy for earning bid-ask spread.

    Key features:
    - Post-only orders enforced (NEVER takes liquidity)
    - Quote aging and refresh
    - Inventory skew management
    - Position size limits
    - Cancellation rate limiting

    All signals are tagged with LOW_LIQUIDITY risk (market making risk).
    """

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        """
        Initialize market making strategy.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or Config()

        # Initialize components
        self.spread_model = SpreadModel(
            default_spread_bps=50,  # 0.5% default spread
            max_spread_bps=self.config.MM_MAX_SPREAD_BPS,  # From config
            min_spread_bps=10,
            pricing_model=PricingModel.INVENTORY_ADJUSTED,
        )

        self.quote_manager = QuoteManager(
            quote_age_limit_seconds=self.config.MM_QUOTE_AGE_LIMIT_SECONDS,
            max_cancel_rate_per_minute=self.config.MM_MAX_CANCEL_RATE_PER_MIN,
        )

        self.inventory_manager = InventoryManager(
            max_position_size=self.config.MM_MAX_POSITION_SIZE,
            max_total_exposure=self.config.MM_MAX_POSITION_SIZE * 4,  # Max 4 positions
            max_skew_threshold=Decimal("0.7"),
        )

        # Post-only enforcement
        if not self.config.MM_POST_ONLY:
            logger.error("MM_POST_ONLY must be TRUE for market making")
            raise ValueError("Market making requires MM_POST_ONLY=true")

        self.enabled = self.config.MARKET_MAKING_ENABLED

        if self.enabled:
            logger.info("Market Making Strategy initialized (post-only enforced)")
        else:
            logger.info("Market Making Strategy initialized (DISABLED)")

    async def evaluate_market(
        self,
        token_id: str,
        mid_price: Decimal,
        order_book_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[MarketMakingSignal]:
        """
        Evaluate a market for market making opportunity.

        Args:
            token_id: Token identifier
            mid_price: Mid-market price
            order_book_snapshot: Current order book data

        Returns:
            MarketMakingSignal if opportunity found, None otherwise
        """
        if not self.enabled:
            logger.debug("Market Making Strategy is disabled")
            return None

        # Get current inventory metrics
        inventory_metrics = self.inventory_manager.get_metrics()

        # Calculate spread with inventory adjustment
        spread_calc = await self.spread_model.calculate_spread(
            mid_price=mid_price,
            inventory_skew=inventory_metrics.inventory_skew,
        )

        if not spread_calc.is_acceptable:
            logger.debug(f"Spread calculation failed: {spread_calc.reason}")
            return None

        # Check if we can open positions (both bid and ask)
        can_bid, bid_reason = self.inventory_manager.can_open_position(
            token_id=token_id,
            size_usdc=self.config.TRADE_SIZE,
            side=Side.BUY,
        )

        can_ask, ask_reason = self.inventory_manager.can_open_position(
            token_id=token_id,
            size_usdc=self.config.TRADE_SIZE,
            side=Side.SELL,
        )

        if not can_bid or not can_ask:
            logger.debug(
                f"Cannot make market: bid_ok={can_bid}, ask_ok={can_ask}"
            )
            return None

        # Calculate expected profit (spread capture)
        # Profit = spread * trade_size
        expected_profit = spread_calc.spread_pct * self.config.TRADE_SIZE

        # Calculate confidence
        confidence = self._calculate_confidence(
            spread_calc=spread_calc,
            inventory_metrics=inventory_metrics,
        )

        # Create signal
        signal = MarketMakingSignal(
            strategy="market_making",
            token_id=token_id,
            signal_type="ARBITRAGE",
            expected_profit=expected_profit,
            trade_size=self.config.TRADE_SIZE,
            yes_price=spread_calc.bid_price,
            no_price=spread_calc.ask_price,
            confidence=confidence,
            reason=(
                f"Market making: mid={mid_price:.4f}, "
                f"spread={spread_calc.spread_bps}bps, "
                f"bid={spread_calc.bid_price:.4f}, ask={spread_calc.ask_price:.4f}, "
                f"skew={float(spread_calc.inventory_skew_factor):.2f}, "
                f"profit=${expected_profit:.2f}"
            ),
            bid_price=spread_calc.bid_price,
            ask_price=spread_calc.ask_price,
            spread_bps=spread_calc.spread_bps,
            inventory_skew=spread_calc.inventory_skew_factor,
            quote_age_seconds=0.0,
            max_position_size=self.config.MM_MAX_POSITION_SIZE,
            post_only=True,  # CRITICAL: Always post-only
        )

        logger.info(
            f"Market making signal: {token_id} - "
            f"{spread_calc.spread_bps}bps spread, ${expected_profit:.2f} profit"
        )

        return signal

    async def on_trade_filled(
        self,
        token_id: str,
        side: Side,
        size_usdc: Decimal,
        price: Decimal,
    ) -> bool:
        """
        Handle a filled trade.

        Args:
            token_id: Token identifier
            side: Trade side
            size_usdc: Trade size
            price: Fill price

        Returns:
            True if handled successfully
        """
        return await self.inventory_manager.update_position(
            token_id=token_id,
            side=side,
            size_usdc=size_usdc,
            price=price,
        )

    async def refresh_quotes(self) -> int:
        """
        Refresh all stale quotes.

        Returns:
            Number of quotes cancelled
        """
        return await self.quote_manager.refresh_stale_quotes()

    def get_inventory_metrics(self) -> InventoryMetrics:
        """
        Get current inventory metrics.

        Returns:
            InventoryMetrics
        """
        return self.inventory_manager.get_metrics()

    def get_quote_metrics(self) -> Dict[str, Any]:
        """
        Get quote management metrics.

        Returns:
            Metrics dictionary
        """
        return self.quote_manager.get_metrics()

    def _calculate_confidence(
        self,
        spread_calc: SpreadCalculation,
        inventory_metrics: InventoryMetrics,
    ) -> float:
        """
        Calculate confidence score for the signal.

        Args:
            spread_calc: Spread calculation
            inventory_metrics: Inventory metrics

        Returns:
            Confidence score (0-1)
        """
        # Base confidence from spread quality
        # Narrower spreads are more competitive (higher confidence)
        spread_quality = 1.0 - (spread_calc.spread_bps / 100.0)  # 100 bps = 0% quality
        confidence = spread_quality * 0.4

        # Add inventory balance (balanced inventory = higher confidence)
        skew_abs = abs(float(spread_calc.inventory_skew_factor))
        inventory_balance = (1.0 - skew_abs) * 0.3
        confidence += inventory_balance

        # Add utilization (lower utilization = more capacity = higher confidence)
        capacity_factor = (1.0 - inventory_metrics.utilization_pct) * 0.3
        confidence += capacity_factor

        return min(confidence, 1.0)

    def get_risk_tags(self) -> List[str]:
        """
        Get risk tags for this strategy.

        Returns:
            List of risk tags
        """
        return [
            RiskTag.LOW_LIQUIDITY.value,  # Market making has liquidity risk
        ]


def create_market_making_strategy(config: Optional[Config] = None) -> MarketMakingStrategy:
    """
    Factory function to create market making strategy.

    Args:
        config: Optional configuration

    Returns:
        MarketMakingStrategy instance
    """
    return MarketMakingStrategy(config=config)
