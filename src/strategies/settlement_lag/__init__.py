"""
Settlement Lag Window Strategy.

This strategy identifies trading opportunities during the resolution window
when markets may have inefficiencies due to uncertainty about the outcome.

Key features:
- Uses ONLY publicly available information (end_date, order book, market metadata)
- Filters high-dispute-risk markets
- Accounts for capital carry costs
- Requires explicit risk_tag=SETTLEMENT_RISK
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime

from loguru import logger

from src.core.models import SettlementLagSignal, RiskTag
from src.core.config import Config
from .market_state_detector import MarketStateDetector, MarketState
from .dispute_risk_filter import DisputeRiskFilter, DisputeRiskAssessment
from .time_to_resolution_model import TimeToResolutionModel, CarryCostCalculation


class SettlementLagStrategy:
    """
    Settlement lag window trading strategy.

    Identifies opportunities during the resolution window when:
    1. Market is approaching resolution (1-72 hours)
    2. Dispute risk is low
    3. Carry cost is acceptable
    4. Liquidity is sufficient

    All signals are tagged with SETTLEMENT_RISK and CARRY_COST_RISK.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        """
        Initialize settlement lag strategy.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or Config()

        # Initialize components
        self.market_state_detector = MarketStateDetector(
            min_resolution_window_hours=self.config.SETTLEMENT_LAG_MIN_WINDOW_HOURS,
            max_resolution_window_hours=72.0,
            min_volume_usd=Decimal("1000"),
            max_spread_bps=200,  # 2%
            min_liquidity_score=0.3,
        )

        self.dispute_filter = DisputeRiskFilter(
            max_risk_score=self.config.SETTLEMENT_LAG_MAX_DISPUTE_SCORE,
            max_volatility_contribution=0.5,
        )

        self.carry_cost_model = TimeToResolutionModel(
            daily_opportunity_cost_pct=Decimal("0.001"),  # 0.1% per day
            max_carry_cost_pct=self.config.SETTLEMENT_LAG_MAX_CARRY_COST_PCT,
        )

        self.enabled = self.config.SETTLEMENT_LAG_ENABLED

        if self.enabled:
            logger.info("Settlement Lag Strategy initialized")
        else:
            logger.info("Settlement Lag Strategy initialized (DISABLED)")

    async def evaluate_market(
        self,
        market_id: str,
        question: str,
        end_date: Optional[datetime],
        order_book_snapshot: Dict[str, Any],
        token_id: str,
        yes_price: Decimal,
        no_price: Decimal,
        trade_size: Decimal,
    ) -> Optional[SettlementLagSignal]:
        """
        Evaluate a market for settlement lag opportunity.

        Args:
            market_id: Market identifier
            question: Market question text
            end_date: Market end date (from public metadata)
            order_book_snapshot: Current order book data
            token_id: Token ID to trade
            yes_price: Current YES price
            no_price: Current NO price
            trade_size: Trade size in USDC

        Returns:
            SettlementLagSignal if opportunity found, None otherwise
        """
        if not self.enabled:
            logger.debug("Settlement Lag Strategy is disabled")
            return None

        # Step 1: Detect market state
        market_state = await self.market_state_detector.detect_market_state(
            market_id=market_id,
            end_date=end_date,
            order_book_snapshot=order_book_snapshot,
        )

        if not market_state.is_suitable:
            logger.debug(
                f"Market {market_id} not suitable: {market_state.disqualification_reason}"
            )
            return None

        # Step 2: Assess dispute risk
        dispute_assessment = await self.dispute_filter.assess_dispute_risk(
            market_id=market_id,
            question=question,
            volatility_score=market_state.volatility_score,
            resolution_uncertainty=0.0,  # Will be calculated from market state
        )

        if not dispute_assessment.is_acceptable:
            logger.debug(
                f"Market {market_id} dispute risk too high: {dispute_assessment.risk_score:.2f}"
            )
            return None

        # Step 3: Calculate carry cost
        carry_calc = await self.carry_cost_model.calculate_carry_cost(
            capital_amount=trade_size,
            hours_to_resolution=market_state.hours_to_resolution,
        )

        if not carry_calc.acceptable:
            logger.debug(
                f"Market {market_id} carry cost too high: {carry_calc.carry_cost_pct_of_capital:.2%}"
            )
            return None

        # Step 4: Calculate expected profit
        # For settlement lag, profit comes from price inefficiencies
        # We look for opportunities where yes_price + no_price < 1.0
        combined_price = yes_price + no_price
        gross_profit = Decimal("1.0") - combined_price

        if gross_profit <= 0:
            logger.debug(f"Market {market_id} has no arbitrage opportunity")
            return None

        # Subtract carry cost from gross profit
        net_profit = gross_profit - carry_calc.total_carry_cost_usd

        if net_profit <= 0:
            logger.debug(
                f"Market {market_id} net profit negative after carry cost: "
                f"${net_profit:.2f}"
            )
            return None

        # Step 5: Create signal
        signal = SettlementLagSignal(
            strategy="settlement_lag",
            token_id=token_id,
            signal_type="ARBITRAGE",
            expected_profit=net_profit,
            trade_size=trade_size,
            yes_price=yes_price,
            no_price=no_price,
            confidence=self._calculate_confidence(
                market_state=market_state,
                dispute_assessment=dispute_assessment,
                carry_calc=carry_calc,
            ),
            reason=(
                f"Settlement lag opportunity: {market_state.hours_to_resolution:.1f}h to resolution, "
                f"dispute_risk={dispute_assessment.risk_level.value}, "
                f"carry_cost=${carry_calc.total_carry_cost_usd:.2f}, "
                f"net_profit=${net_profit:.2f}"
            ),
            market_id=market_id,
            resolution_window_hours=market_state.hours_to_resolution,
            dispute_score=dispute_assessment.risk_score,
            carry_cost=carry_calc.total_carry_cost_usd,
            resolution_uncertainty=1.0 - market_state.liquidity_score,
            end_date=end_date,
        )

        logger.info(
            f"Settlement lag signal generated: {market_id} - "
            f"${net_profit:.2f} profit in {market_state.hours_to_resolution:.1f}h"
        )

        return signal

    def _calculate_confidence(
        self,
        market_state: MarketState,
        dispute_assessment: DisputeRiskAssessment,
        carry_calc: CarryCostCalculation,
    ) -> float:
        """
        Calculate confidence score for the signal.

        Args:
            market_state: Market state assessment
            dispute_assessment: Dispute risk assessment
            carry_calc: Carry cost calculation

        Returns:
            Confidence score (0-1)
        """
        # Base confidence from liquidity
        confidence = market_state.liquidity_score * 0.4

        # Add inverse dispute risk
        confidence += (1.0 - dispute_assessment.risk_score) * 0.4

        # Add carry cost buffer (lower carry cost = higher confidence)
        carry_cost_ratio = carry_calc.carry_cost_pct_of_capital / self.config.SETTLEMENT_LAG_MAX_CARRY_COST_PCT
        confidence += (1.0 - min(float(carry_cost_ratio), 1.0)) * 0.2

        return min(confidence, 1.0)

    def get_risk_tags(self) -> list[str]:
        """
        Get risk tags for this strategy.

        Returns:
            List of risk tags
        """
        return [
            RiskTag.SETTLEMENT_RISK.value,
            RiskTag.CARRY_COST_RISK.value,
        ]


def create_settlement_lag_strategy(config: Optional[Config] = None) -> SettlementLagStrategy:
    """
    Factory function to create settlement lag strategy.

    Args:
        config: Optional configuration

    Returns:
        SettlementLagStrategy instance
    """
    return SettlementLagStrategy(config=config)
