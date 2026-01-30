"""
Risk Manager for validating trading signals.

This module provides functionality for:
- Validating signals before execution
- Checking sufficient balance
- Calculating gas costs
- Enforcing position limits
- Ensuring profitability after costs

All trades must pass risk management before execution.
"""
from decimal import Decimal
from typing import Optional

from src.core.models import Signal, ArbitrageOpportunity
from loguru import logger


class RiskManager:
    """
    Risk manager for validating trading signals.

    Ensures all trades meet safety and profitability requirements.
    """

    def __init__(
        self,
        max_position_size: Decimal = Decimal("1000"),
        min_profit_threshold: Decimal = Decimal("0.01"),  # 1%
        max_gas_cost: Decimal = Decimal("1.0"),  # $1 max gas
    ):
        """
        Initialize risk manager.

        Args:
            max_position_size: Maximum position size in USDC
            min_profit_threshold: Minimum profit as decimal (0.01 = 1%)
            max_gas_cost: Maximum acceptable gas cost in USDC
        """
        self.max_position_size = max_position_size
        self.min_profit_threshold = min_profit_threshold
        self.max_gas_cost = max_gas_cost

    def validate_signal(
        self,
        signal: Signal,
        balance: Decimal,
        gas_cost: Decimal
    ) -> bool:
        """
        Validate a trading signal before execution.

        Checks:
        1. Sufficient balance
        2. Position size within limits
        3. Profit exceeds minimum threshold
        4. Gas cost is acceptable
        5. Profit > gas cost

        Args:
            signal: Trading signal to validate
            balance: Current USDC balance
            gas_cost: Estimated gas cost in USDC

        Returns:
            True if signal passes all validation checks
        """
        # Check for negative values first
        if balance < 0 or gas_cost < 0 or signal.expected_profit < 0:
            logger.warning("Rejecting signal: negative values detected")
            return False

        # Check sufficient balance
        if balance < signal.trade_size:
            logger.warning(
                f"Insufficient balance: {balance} < {signal.trade_size}"
            )
            return False

        # Check position limit
        if not self.check_position_limit(signal.trade_size, self.max_position_size):
            logger.warning(
                f"Position size exceeds limit: {signal.trade_size} > {self.max_position_size}"
            )
            return False

        # Check gas cost is acceptable
        if gas_cost > self.max_gas_cost:
            logger.warning(f"Gas cost too high: {gas_cost} > {self.max_gas_cost}")
            return False

        # Check profit exceeds gas cost
        if signal.expected_profit <= gas_cost:
            logger.warning(
                f"Profit does not cover gas: {signal.expected_profit} <= {gas_cost}"
            )
            return False

        # Check minimum profit threshold (as percentage of trade size)
        profit_percentage = signal.expected_profit / signal.trade_size
        if profit_percentage < self.min_profit_threshold:
            logger.warning(
                f"Profit below threshold: {profit_percentage:.4f} < {self.min_profit_threshold}"
            )
            return False

        logger.info(f"Signal validated: {signal.signal_type} - ${signal.expected_profit}")
        return True

    def calculate_gas_cost(self, gas_price: int, gas_limit: int) -> Decimal:
        """
        Calculate gas cost in USDC.

        Args:
            gas_price: Gas price in wei
            gas_limit: Gas limit in units

        Returns:
            Gas cost in USDC (assuming 1 MATIC = $1 for simplicity)

        Note:
            In production, you should fetch the actual MATIC/USDC price
            from a price oracle for accurate conversion.
        """
        # Calculate gas cost in wei
        gas_cost_wei = Decimal(gas_price) * Decimal(gas_limit)

        # Convert to ETH/MATIC (1e18 wei per ETH/MATIC)
        gas_cost_matic = gas_cost_wei / Decimal("1e18")

        # For simplicity, assume 1 MATIC = $1 USDC
        # In production, use a price oracle for accurate conversion
        gas_cost_usdc = gas_cost_matic

        return gas_cost_usdc

    def check_position_limit(
        self,
        size: Decimal,
        max_position: Decimal
    ) -> bool:
        """
        Check if position size is within limit.

        Args:
            size: Position size in USDC
            max_position: Maximum allowed position size

        Returns:
            True if position size is within limit
        """
        return size <= max_position

    def estimate_total_cost(
        self,
        signal: Signal,
        gas_cost: Decimal
    ) -> Decimal:
        """
        Estimate total cost of executing a signal.

        For arbitrage signals, includes YES + NO costs.
        For regular signals, uses trade_size.

        Args:
            signal: Trading signal
            gas_cost: Estimated gas cost

        Returns:
            Total cost in USDC
        """
        if isinstance(signal, ArbitrageOpportunity):
            # Arbitrage: YES cost + NO cost + fees
            base_cost = signal.total_cost
        else:
            # Regular signal: trade size
            base_cost = signal.trade_size

        total_cost = base_cost + gas_cost
        return total_cost
