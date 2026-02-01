"""
Edge analysis module for arbitrage decision attribution.

This module provides:
- Decision breakdown with cost analysis
- Net profit calculation
- Decision validation
- Reason tracking

Example:
    edge = EdgeBreakdown(
        gross_edge=Decimal("100.0"),
        fees_est=Decimal("2.0"),
        slippage_est=Decimal("1.0"),
        gas_est=Decimal("0.5"),
        latency_buffer=Decimal("0.3"),
        min_threshold=Decimal("95.0")
    )
    edge._calculate_decision()
    if edge.decision == Decision.ACCEPT:
        # Execute trade
        pass
"""
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field


class Decision(str, Enum):
    """Trading decision"""
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass
class EdgeBreakdown:
    """
    Arbitrage edge breakdown with cost analysis.

    Attributes:
        gross_edge: Gross profit before costs
        fees_est: Estimated fees
        slippage_est: Estimated slippage
        gas_est: Estimated gas cost
        latency_buffer: Buffer for latency risk
        min_threshold: Minimum acceptable profit
        net_edge: Net profit after costs (calculated)
        decision: Trading decision (ACCEPT/REJECT)
        reason: Explanation for the decision
        risk_tags: List of risk tags for risk tracking
    """
    gross_edge: Decimal
    fees_est: Decimal
    slippage_est: Decimal
    gas_est: Decimal
    latency_buffer: Decimal
    min_threshold: Decimal
    net_edge: Decimal = None
    decision: Decision = None
    reason: str = None
    risk_tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Calculate net edge after initialization"""
        if self.net_edge is None:
            self.net_edge = calculate_net_edge(
                self.gross_edge,
                self.fees_est,
                self.slippage_est,
                self.gas_est,
                self.latency_buffer
            )

    def _calculate_decision(self) -> None:
        """
        Calculate trading decision based on net edge.

        Sets:
            decision: ACCEPT or REJECT
            reason: Explanation string
        """
        if self.net_edge >= self.min_threshold:
            self.decision = Decision.ACCEPT
            self.reason = (
                f"Acceptable profit: net_edge=${self.net_edge:.2f} "
                f">= threshold=${self.min_threshold:.2f}"
            )
        else:
            self.decision = Decision.REJECT
            self.reason = (
                f"Insufficient profit: net_edge=${self.net_edge:.2f} "
                f"< threshold=${self.min_threshold:.2f} "
                f"(shortfall=${self.min_threshold - self.net_edge:.2f})"
            )


def calculate_net_edge(
    gross_edge: Decimal,
    fees: Decimal,
    slippage: Decimal,
    gas: Decimal,
    latency_buffer: Decimal
) -> Decimal:
    """
    Calculate net profit after all costs.

    Args:
        gross_edge: Gross profit
        fees: Trading fees
        slippage: Expected slippage
        gas: Gas cost
        latency_buffer: Buffer for latency

    Returns:
        Net profit
    """
    return (
        gross_edge
        - fees
        - slippage
        - gas
        - latency_buffer
    )


def validate_edge_breakdown(edge: EdgeBreakdown) -> List[str]:
    """
    Validate an EdgeBreakdown instance.

    Args:
        edge: EdgeBreakdown to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check if decision is set
    if edge.decision is None:
        errors.append("Decision not calculated. Call _calculate_decision() first.")

    # Check if REJECT has a reason
    if edge.decision == Decision.REJECT and not edge.reason:
        errors.append("REJECT decision must have a non-empty reason.")

    # Check if net_edge is negative (warning only)
    if edge.net_edge < 0:
        errors.append(f"Warning: Negative net_edge (${edge.net_edge})")

    return errors
