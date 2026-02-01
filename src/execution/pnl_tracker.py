"""
PnL tracker for simulated and live trades.

This module tracks PnL separately for:
- Simulated fills (dry-run mode)
- Realized fills (live mode)

Key principle: PnL only updates after fills, NOT after order submission.
"""
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from src.execution.fill import Fill


@dataclass
class PnLUpdate:
    """PnL update event."""

    timestamp_ms: int
    trace_id: str
    strategy: str
    token_id: str

    # For arbitrage
    yes_token_id: Optional[str] = None
    no_token_id: Optional[str] = None

    # PnL values
    expected_edge: Decimal = Decimal("0")  # Expected profit at signal time
    simulated_pnl: Decimal = Decimal("0")   # Simulated execution PnL
    realized_pnl: Decimal = Decimal("0")    # Actual realized PnL

    # Costs
    fees_paid: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")

    is_simulated: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp_ms": self.timestamp_ms,
            "trace_id": self.trace_id,
            "strategy": self.strategy,
            "token_id": self.token_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "expected_edge": str(self.expected_edge),
            "simulated_pnl": str(self.simulated_pnl),
            "realized_pnl": str(self.realized_pnl),
            "fees_paid": str(self.fees_paid),
            "slippage_cost": str(self.slippage_cost),
            "is_simulated": self.is_simulated,
        }


class PnLTracker:
    """
    Tracks PnL for simulated and live trades.

    Key principle: PnL only updates after fills, not after order submission.

    For arbitrage (YES + NO = 1.0):
    - We buy both YES and NO tokens
    - At settlement, YES + NO = 1.0 USDC per pair
    - PnL = payout - (cost + fees + slippage)
    """

    def __init__(self):
        self._positions: Dict[str, Decimal] = defaultdict(Decimal)  # token_id -> quantity
        self._cumulative_expected_edge: Decimal = Decimal("0")
        self._cumulative_simulated_pnl: Decimal = Decimal("0")
        self._cumulative_realized_pnl: Decimal = Decimal("0")
        self._pnl_updates: List[PnLUpdate] = []

        # For arbitrage (YES + NO = 1.0)
        self._arbitrage_positions: Dict[str, tuple[Decimal, Decimal]] = {}

    async def process_fills(
        self,
        fills: List[Fill],
        expected_edge: Decimal,
        trace_id: str,
        strategy: str = "atomic",
    ) -> PnLUpdate:
        """
        Process fills and generate PnL update.

        For arbitrage:
        - Buying YES + NO costs us money (negative proceeds)
        - At settlement, YES + NO = 1.0 USDC per pair
        - PnL = 1.0 - (cost + fees + slippage) per unit

        Args:
            fills: List of fills from this execution
            expected_edge: Expected profit from the signal
            trace_id: Trace ID for this trade
            strategy: Strategy name

        Returns:
            PnLUpdate with calculated PnL
        """
        if not fills:
            return PnLUpdate(
                timestamp_ms=int(datetime.now().timestamp() * 1000),
                trace_id=trace_id,
                strategy=strategy,
                token_id="",
                expected_edge=expected_edge,
            )

        # Calculate total cost and fees
        total_cost = Decimal("0")
        total_fees = Decimal("0")
        total_slippage = Decimal("0")

        for fill in fills:
            total_cost += fill.net_proceeds  # This is negative for buys
            total_fees += fill.fees
            if fill.slippage_bps:
                total_slippage += fill.notional_usdc * Decimal(fill.slippage_bps) / Decimal("10000")

            # Track position
            self._positions[fill.token_id] += fill.quantity

        # For arbitrage: YES + NO = 1.0
        # Our profit = 1.0 - (cost + fees + slippage) per unit
        is_arbitrage = len(fills) == 2
        simulated_pnl = Decimal("0")

        if is_arbitrage:
            # Total tokens we bought = sum of quantities
            total_tokens = sum(f.quantity for f in fills)
            # Payout at settlement = total_tokens * 1.0
            payout = total_tokens
            # PnL = payout + total_cost (total_cost is negative, so this is payout - cost)
            simulated_pnl = payout + total_cost - total_slippage
        else:
            # Simple trade (not arbitrage)
            # For now, just track the expected value
            simulated_pnl = expected_edge - total_fees - total_slippage

        # Update cumulative
        self._cumulative_expected_edge += expected_edge
        if fills[0].is_simulated:
            self._cumulative_simulated_pnl += simulated_pnl
        else:
            self._cumulative_realized_pnl += simulated_pnl

        # Create PnL update
        pnl_update = PnLUpdate(
            timestamp_ms=int(datetime.now().timestamp() * 1000),
            trace_id=trace_id,
            strategy=strategy,
            token_id=fills[0].token_id,
            yes_token_id=fills[0].token_id if len(fills) > 0 else None,
            no_token_id=fills[1].token_id if len(fills) > 1 else None,
            expected_edge=expected_edge,
            simulated_pnl=simulated_pnl if fills[0].is_simulated else Decimal("0"),
            realized_pnl=simulated_pnl if not fills[0].is_simulated else Decimal("0"),
            fees_paid=total_fees,
            slippage_cost=total_slippage,
            is_simulated=fills[0].is_simulated,
        )

        self._pnl_updates.append(pnl_update)

        return pnl_update

    def get_summary(self) -> dict:
        """Get PnL summary."""
        return {
            "cumulative_expected_edge": str(self._cumulative_expected_edge),
            "cumulative_simulated_pnl": str(self._cumulative_simulated_pnl),
            "cumulative_realized_pnl": str(self._cumulative_realized_pnl),
            "total_pnl_updates": len(self._pnl_updates),
            "open_positions": {k: str(v) for k, v in self._positions.items()},
        }
