"""
Time to Resolution Model for Settlement Lag Strategy.

This module calculates capital carry costs during the resolution window.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from loguru import logger


@dataclass
class CarryCostCalculation:
    """Calculation of capital carry cost.

    Attributes:
        hours_to_resolution: Hours until market resolution
        days_to_resolution: Days until market resolution (fractional)
        capital_amount: Amount of capital tied up
        daily_opportunity_cost_pct: Daily opportunity cost percentage
        total_carry_cost_usd: Total carry cost in USDC
        carry_cost_pct_of_capital: Carry cost as percentage of capital
        acceptable: Whether carry cost is acceptable
        reason: Explanation
    """
    hours_to_resolution: float
    days_to_resolution: float
    capital_amount: Decimal
    daily_opportunity_cost_pct: Decimal
    total_carry_cost_usd: Decimal
    carry_cost_pct_of_capital: Decimal
    acceptable: bool
    reason: str


class TimeToResolutionModel:
    """
    Models the cost of capital during the resolution window.

    Calculates opportunity cost of tying up capital while waiting
    for market resolution.
    """

    # Default daily opportunity cost (0.1% per day)
    # This represents what capital could earn elsewhere
    DEFAULT_DAILY_OPPORTUNITY_COST_PCT = Decimal("0.001")

    def __init__(
        self,
        daily_opportunity_cost_pct: Optional[Decimal] = None,
        max_carry_cost_pct: Decimal = Decimal("0.02"),  # 2% max
    ):
        """
        Initialize time to resolution model.

        Args:
            daily_opportunity_cost_pct: Daily opportunity cost as decimal (default 0.001 = 0.1%)
            max_carry_cost_pct: Maximum acceptable carry cost as % of capital (default 0.02 = 2%)
        """
        self.daily_opportunity_cost_pct = daily_opportunity_cost_pct or self.DEFAULT_DAILY_OPPORTUNITY_COST_PCT
        self.max_carry_cost_pct = max_carry_cost_pct

    async def calculate_carry_cost(
        self,
        capital_amount: Decimal,
        hours_to_resolution: float,
        end_date: Optional[datetime] = None,
    ) -> CarryCostCalculation:
        """
        Calculate carry cost for capital during resolution window.

        Args:
            capital_amount: Amount of capital to be tied up (USDC)
            hours_to_resolution: Hours until resolution
            end_date: Optional explicit end date (overrides hours_to_resolution if provided)

        Returns:
            CarryCostCalculation with detailed cost breakdown
        """
        # Use explicit end date if provided, otherwise use hours
        if end_date is not None:
            time_to_resolution = end_date - datetime.now()
            days_to_resolution = time_to_resolution.total_seconds() / 86400
            hours_to_resolution = days_to_resolution * 24
        else:
            days_to_resolution = hours_to_resolution / 24

        # Calculate total carry cost
        # Formula: capital * daily_rate * days
        total_carry_cost_usd = capital_amount * self.daily_opportunity_cost_pct * Decimal(str(days_to_resolution))

        # Calculate as percentage of capital
        carry_cost_pct_of_capital = total_carry_cost_usd / capital_amount if capital_amount > 0 else Decimal("0")

        # Check if acceptable
        acceptable = carry_cost_pct_of_capital <= self.max_carry_cost_pct

        if acceptable:
            reason = (
                f"Carry cost acceptable: {carry_cost_pct_of_capital:.2%} <= {self.max_carry_cost_pct:.2%}. "
                f"Cost: ${total_carry_cost_usd:.2f} on ${capital_amount:.2f} for {days_to_resolution:.1f} days"
            )
        else:
            reason = (
                f"Carry cost too high: {carry_cost_pct_of_capital:.2%} > {self.max_carry_cost_pct:.2%}. "
                f"Cost: ${total_carry_cost_usd:.2f} on ${capital_amount:.2f} for {days_to_resolution:.1f} days"
            )

        calculation = CarryCostCalculation(
            hours_to_resolution=hours_to_resolution,
            days_to_resolution=days_to_resolution,
            capital_amount=capital_amount,
            daily_opportunity_cost_pct=self.daily_opportunity_cost_pct,
            total_carry_cost_usd=total_carry_cost_usd,
            carry_cost_pct_of_capital=carry_cost_pct_of_capital,
            acceptable=acceptable,
            reason=reason,
        )

        if acceptable:
            logger.debug(f"Carry cost for ${capital_amount}: ${total_carry_cost_usd:.2f} ({carry_cost_pct_of_capital:.2%})")
        else:
            logger.warning(f"Carry cost too high: ${total_carry_cost_usd:.2f} ({carry_cost_pct_of_capital:.2%})")

        return calculation

    def calculate_minimum_profit_threshold(
        self,
        capital_amount: Decimal,
        hours_to_resolution: float,
    ) -> Decimal:
        """
        Calculate minimum profit needed to justify carry cost.

        Args:
            capital_amount: Amount of capital to be tied up
            hours_to_resolution: Hours until resolution

        Returns:
            Minimum profit in USDC needed
        """
        days_to_resolution = hours_to_resolution / 24
        carry_cost = capital_amount * self.daily_opportunity_cost_pct * Decimal(str(days_to_resolution))

        # Require at least 2x carry cost as profit buffer
        return carry_cost * 2

    def calculate_max_acceptable_duration(
        self,
        capital_amount: Decimal,
        expected_profit_usd: Decimal,
    ) -> float:
        """
        Calculate maximum acceptable duration for given profit.

        Args:
            capital_amount: Amount of capital to be tied up
            expected_profit_usd: Expected profit in USDC

        Returns:
            Maximum acceptable hours until resolution
        """
        # Profit must cover carry cost with buffer
        # profit >= carry_cost * buffer
        # profit >= capital * daily_rate * days * buffer
        # days <= profit / (capital * daily_rate * buffer)

        buffer = 2  # Require 2x coverage
        daily_cost = capital_amount * self.daily_opportunity_cost_pct
        max_days = float(expected_profit_usd) / float(daily_cost * buffer)

        return max_days * 24  # Convert to hours


def calculate_carry_cost_sync(
    model: TimeToResolutionModel,
    capital_amount: Decimal,
    hours_to_resolution: float,
) -> CarryCostCalculation:
    """
    Synchronous wrapper for carry cost calculation.

    Useful for testing and non-async contexts.

    Args:
        model: TimeToResolutionModel instance
        capital_amount: Amount of capital to be tied up
        hours_to_resolution: Hours until resolution

    Returns:
        CarryCostCalculation
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        model.calculate_carry_cost(
            capital_amount=capital_amount,
            hours_to_resolution=hours_to_resolution,
        )
    )
