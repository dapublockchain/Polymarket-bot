"""
Unified Fill model for simulated and real fills.

This provides a consistent interface between dry-run (simulated fills)
and live trading (real fills), ensuring both modes share the same
execution pipeline logic.
"""
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class FillSide(str, Enum):
    """Side of a fill (buy or sell)."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Fill:
    """
    Unified fill model for simulated and real fills.

    This model is used by both SimulatedExecutor (dry-run) and
    LiveExecutor (live mode) to ensure consistent execution pipeline.

    Attributes:
        fill_id: Unique identifier for this fill
        order_request_id: ID of the order request that generated this fill
        token_id: Token identifier
        side: Buy or sell
        price: Execution price (in USDC)
        quantity: Quantity filled (in tokens)
        fees: Trading fees paid (in USDC)
        timestamp_ms: Timestamp of fill (milliseconds since epoch)
        trace_id: Trace ID for telemetry
        is_simulated: Whether this is a simulated fill (dry-run) or real fill (live)
        slippage_bps: Slippage in basis points (simulated fills only)
        tx_hash: Transaction hash (real fills only)
        on_chain_filled: Whether the fill is confirmed on-chain (real fills only)
    """
    fill_id: str
    order_request_id: str
    token_id: str
    side: FillSide
    price: Decimal
    quantity: Decimal
    fees: Decimal
    timestamp_ms: int
    trace_id: str
    is_simulated: bool = False

    # For simulated fills
    slippage_bps: Optional[int] = None

    # For real fills
    tx_hash: Optional[str] = None
    on_chain_filled: bool = False

    @property
    def notional_usdc(self) -> Decimal:
        """Calculate notional value in USDC."""
        return self.price * self.quantity

    @property
    def net_proceeds(self) -> Decimal:
        """
        Calculate net proceeds after fees.

        For buys: Returns negative (cost)
        For sells: Returns positive (proceeds)
        """
        if self.side == FillSide.BUY:
            return -self.notional_usdc - self.fees
        else:
            return self.notional_usdc - self.fees

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "fill_id": self.fill_id,
            "order_request_id": self.order_request_id,
            "token_id": self.token_id,
            "side": self.side.value,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "fees": str(self.fees),
            "timestamp_ms": self.timestamp_ms,
            "trace_id": self.trace_id,
            "is_simulated": self.is_simulated,
            "slippage_bps": self.slippage_bps,
            "tx_hash": self.tx_hash,
            "on_chain_filled": self.on_chain_filled,
            "notional_usdc": str(self.notional_usdc),
            "net_proceeds": str(self.net_proceeds),
        }

    def __repr__(self) -> str:
        """String representation of fill."""
        sim_marker = "SIM" if self.is_simulated else "REAL"
        return (
            f"Fill({sim_marker}, {self.side.value}, "
            f"{self.token_id[:12]}..., "
            f"{self.quantity:.4f} @ ${self.price:.4f}, "
            f"fees=${self.fees:.4f})"
        )
