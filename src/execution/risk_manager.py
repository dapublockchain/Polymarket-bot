"""
Risk Manager for validating trading signals.

This module provides functionality for:
- Validating signals before execution
- Checking sufficient balance
- Calculating gas costs
- Enforcing position limits
- Ensuring profitability after costs
- Edge breakdown and decision attribution

All trades must pass risk management before execution.
"""
from decimal import Decimal
from typing import Optional
from enum import Enum

from src.core.models import Signal, ArbitrageOpportunity
from src.core.edge import EdgeBreakdown, Decision, calculate_net_edge
from src.core.telemetry import log_event, EventType as TeleEventType
from loguru import logger


class RejectCode(str, Enum):
    """Standardized reject codes for risk management decisions."""
    INSUFFICIENT_BALANCE = "insufficient_balance"
    POSITION_LIMIT = "position_limit"
    GAS_TOO_HIGH = "gas_too_high"
    PROFIT_TOO_LOW = "profit_too_low"
    NEGATIVE_VALUES = "negative_values"
    PROFIT_BELOW_GAS = "profit_below_gas"
    SLIPPAGE_EXCEEDED = "slippage_exceeded"

    # New strategy reject codes
    RESOLUTION_UNCERTAIN = "resolution_uncertain"
    DISPUTE_RISK_HIGH = "dispute_risk_high"
    CARRY_COST_TOO_HIGH = "carry_cost_too_high"
    MANIPULATION_RISK = "manipulation_risk"
    ABNORMAL_VOLATILITY = "abnormal_volatility"


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
        max_slippage: Decimal = Decimal("0.01"),  # 1% max slippage
    ):
        """
        Initialize risk manager.

        Args:
            max_position_size: Maximum position size in USDC
            min_profit_threshold: Minimum profit as decimal (0.01 = 1%)
            max_gas_cost: Maximum acceptable gas cost in USDC
            max_slippage: Maximum acceptable slippage as decimal (0.01 = 1%)
        """
        self.max_position_size = max_position_size
        self.min_profit_threshold = min_profit_threshold
        self.max_gas_cost = max_gas_cost
        self.max_slippage = max_slippage

    async def validate_signal_with_edge(
        self,
        signal: Signal,
        balance: Decimal,
        gas_cost: Decimal,
        fees: Decimal = Decimal("0"),
        slippage_est: Decimal = Decimal("0"),
        trace_id: Optional[str] = None,
    ) -> EdgeBreakdown:
        """
        Validate a trading signal with detailed edge breakdown.

        Args:
            signal: Trading signal to validate
            balance: Current USDC balance
            gas_cost: Estimated gas cost in USDC
            fees: Trading fees in USDC
            slippage_est: Estimated slippage in USDC
            trace_id: Optional trace_id for telemetry

        Returns:
            EdgeBreakdown with decision attribution
        """
        # Calculate gross edge (expected profit)
        gross_edge = signal.expected_profit

        # Estimate latency buffer (0.1% of profit as safety margin)
        latency_buffer = gross_edge * Decimal("0.001")

        # Calculate net edge
        net_edge = calculate_net_edge(
            gross_edge,
            fees,
            slippage_est,
            gas_cost,
            latency_buffer
        )

        # Determine decision and reason
        reject_code = None
        reason = ""

        # Check for negative values first
        if balance < 0 or gas_cost < 0 or signal.expected_profit < 0:
            reject_code = RejectCode.NEGATIVE_VALUES
            reason = "Negative values detected in balance, gas cost, or profit"

        # Check sufficient balance
        elif balance < signal.trade_size:
            reject_code = RejectCode.INSUFFICIENT_BALANCE
            reason = f"Insufficient balance: {balance} < {signal.trade_size}"

        # Check position limit
        elif not self.check_position_limit(signal.trade_size, self.max_position_size):
            reject_code = RejectCode.POSITION_LIMIT
            reason = f"Position size exceeds limit: {signal.trade_size} > {self.max_position_size}"

        # Check gas cost is acceptable
        elif gas_cost > self.max_gas_cost:
            reject_code = RejectCode.GAS_TOO_HIGH
            reason = f"Gas cost too high: {gas_cost} > {self.max_gas_cost}"

        # Check profit exceeds gas cost
        elif signal.expected_profit <= gas_cost:
            reject_code = RejectCode.PROFIT_BELOW_GAS
            reason = f"Profit does not cover gas: {signal.expected_profit} <= {gas_cost}"

        # Check minimum profit threshold (as percentage of trade size)
        elif net_edge < (signal.trade_size * self.min_profit_threshold):
            reject_code = RejectCode.PROFIT_TOO_LOW
            min_profit = signal.trade_size * self.min_profit_threshold
            reason = f"Profit below threshold: {net_edge:.4f} < {min_profit:.4f}"

        # Check slippage
        elif slippage_est > (signal.trade_size * self.max_slippage):
            reject_code = RejectCode.SLIPPAGE_EXCEEDED
            max_allowed = signal.trade_size * self.max_slippage
            reason = f"Slippage exceeds limit: {slippage_est:.4f} > {max_allowed:.4f}"

        # All checks passed
        else:
            decision = Decision.ACCEPT
            reason = f"Acceptable profit: net_edge=${net_edge:.4f} >= threshold=${signal.trade_size * self.min_profit_threshold:.4f}"

            # Log telemetry event
            if trace_id:
                await log_event(
                    TeleEventType.RISK_PASSED,
                    {
                        "strategy": signal.strategy,
                        "signal_type": signal.signal_type,
                        "gross_edge": str(gross_edge),
                        "fees": str(fees),
                        "slippage_est": str(slippage_est),
                        "gas_cost": str(gas_cost),
                        "net_edge": str(net_edge),
                        "trade_size": str(signal.trade_size),
                    },
                    trace_id=trace_id
                )

            logger.info(f"Signal validated: {signal.signal_type} - ${signal.expected_profit}")
            return EdgeBreakdown(
                gross_edge=gross_edge,
                fees_est=fees,
                slippage_est=slippage_est,
                gas_est=gas_cost,
                latency_buffer=latency_buffer,
                min_threshold=signal.trade_size * self.min_profit_threshold,
                net_edge=net_edge,
                decision=decision,
                reason=reason
            )

        # Rejected
        decision = Decision.REJECT
        logger.warning(f"Signal rejected: {reject_code} - {reason}")

        # Log rejection telemetry
        if trace_id:
            await log_event(
                TeleEventType.RISK_PASSED,  # Using same event type but with rejection
                {
                    "strategy": signal.strategy,
                    "signal_type": signal.signal_type,
                    "decision": "REJECT",
                    "reject_code": reject_code,
                    "reason": reason,
                    "gross_edge": str(gross_edge),
                    "net_edge": str(net_edge),
                },
                trace_id=trace_id
            )

        return EdgeBreakdown(
            gross_edge=gross_edge,
            fees_est=fees,
            slippage_est=slippage_est,
            gas_est=gas_cost,
            latency_buffer=latency_buffer,
            min_threshold=signal.trade_size * self.min_profit_threshold,
            net_edge=net_edge,
            decision=decision,
            reason=reason
        )

    def validate_signal(
        self,
        signal: Signal,
        balance: Decimal,
        gas_cost: Decimal
    ) -> bool:
        """
        Validate a trading signal before execution (legacy method).

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
