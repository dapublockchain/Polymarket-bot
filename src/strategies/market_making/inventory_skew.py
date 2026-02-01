"""
Inventory Skew Management for Market Making Strategy.

This module manages inventory and position limits to control risk.
"""
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class Side(str, Enum):
    """Trade side."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Position:
    """A trading position.

    Attributes:
        token_id: Token identifier
        side: Position side (long/short)
        size_usdc: Position size in USDC
        entry_price: Average entry price
        current_price: Current market price
        pnl_unrealized: Unrealized PnL
        opened_at: Position open timestamp
    """
    token_id: str
    side: Side
    size_usdc: Decimal
    entry_price: Decimal
    current_price: Decimal
    pnl_unrealized: Decimal
    opened_at: float  # Unix timestamp

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side == Side.BUY

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side == Side.SELL


@dataclass
class InventoryMetrics:
    """Inventory metrics.

    Attributes:
        total_long_exposure: Total long exposure in USDC
        total_short_exposure: Total short exposure in USDC
        net_exposure: Net exposure (long - short)
        gross_exposure: Gross exposure (long + short)
        inventory_skew: Inventory skew (-1 to 1, negative = short biased)
        position_count: Total number of positions
        utilization_pct: Utilization of max position limit
    """
    total_long_exposure: Decimal
    total_short_exposure: Decimal
    net_exposure: Decimal
    gross_exposure: Decimal
    inventory_skew: Decimal  # -1 to 1
    position_count: int
    utilization_pct: float


class InventoryManager:
    """
    Manages inventory and position limits for market making.

    Key features:
    - Position size limits
    - Inventory skew calculation
    - Exposure tracking
    - Risk limit enforcement
    """

    def __init__(
        self,
        max_position_size: Decimal = Decimal("500"),
        max_total_exposure: Decimal = Decimal("2000"),
        max_skew_threshold: Decimal = Decimal("0.7"),  # Allow up to 70% skew
    ):
        """
        Initialize inventory manager.

        Args:
            max_position_size: Maximum position size per token (USDC)
            max_total_exposure: Maximum total exposure (USDC)
            max_skew_threshold: Maximum allowed inventory skew (-1 to 1)
        """
        self.max_position_size = max_position_size
        self.max_total_exposure = max_total_exposure
        self.max_skew_threshold = max_skew_threshold

        self.positions: Dict[str, Position] = {}  # token_id -> Position

    async def update_position(
        self,
        token_id: str,
        side: Side,
        size_usdc: Decimal,
        price: Decimal,
    ) -> bool:
        """
        Update or create a position after a trade.

        Args:
            token_id: Token identifier
            side: Trade side
            size_usdc: Trade size in USDC
            price: Trade price

        Returns:
            True if position updated successfully
        """
        import time

        # Check if position exists
        if token_id in self.positions:
            position = self.positions[token_id]

            # Update existing position
            # For binary options, we track net exposure
            # Long (BUY) increases exposure, Short (SELL) decreases it
            if side == Side.BUY:
                position.size_usdc += size_usdc
                # Update weighted average entry price
                total_cost = (position.entry_price * (position.size_usdc - size_usdc)) + (price * size_usdc)
                position.entry_price = total_cost / position.size_usdc
            else:  # SELL
                position.size_usdc -= size_usdc
                # Check if position is closed or flipped
                if position.size_usdc <= 0:
                    # Position closed or flipped - close it
                    del self.positions[token_id]
                    logger.info(f"Position closed: {token_id}")
                    return True

            position.current_price = price

            # Calculate unrealized PnL
            # For binary options: PnL = (current_price - entry_price) * size
            price_diff = price - position.entry_price
            position.pnl_unrealized = price_diff * position.size_usdc

        else:
            # Create new position
            position = Position(
                token_id=token_id,
                side=side,
                size_usdc=size_usdc,
                entry_price=price,
                current_price=price,
                pnl_unrealized=Decimal("0"),
                opened_at=time.time(),
            )
            self.positions[token_id] = position
            logger.info(
                f"Position opened: {token_id} - {side.value} ${size_usdc} @ {price}"
            )

        return True

    def calculate_inventory_skew(self) -> Decimal:
        """
        Calculate inventory skew.

        Skew = (long_exposure - short_exposure) / max_total_exposure
        Returns value between -1 (fully short) and 1 (fully long)

        Returns:
            Inventory skew (-1 to 1)
        """
        metrics = self.get_metrics()
        return metrics.inventory_skew

    def get_metrics(self) -> InventoryMetrics:
        """
        Get current inventory metrics.

        Returns:
            InventoryMetrics with current state
        """
        total_long = Decimal("0")
        total_short = Decimal("0")

        for position in self.positions.values():
            if position.is_long:
                total_long += abs(position.size_usdc)
            else:
                total_short += abs(position.size_usdc)

        net_exposure = total_long - total_short
        gross_exposure = total_long + total_short

        # Calculate skew (-1 to 1)
        if self.max_total_exposure > 0:
            inventory_skew = net_exposure / self.max_total_exposure
        else:
            inventory_skew = Decimal("0")

        # Clamp to [-1, 1]
        inventory_skew = max(Decimal("-1"), min(inventory_skew, Decimal("1")))

        # Calculate utilization
        utilization = float(gross_exposure / self.max_total_exposure) if self.max_total_exposure > 0 else 0.0

        return InventoryMetrics(
            total_long_exposure=total_long,
            total_short_exposure=total_short,
            net_exposure=net_exposure,
            gross_exposure=gross_exposure,
            inventory_skew=inventory_skew,
            position_count=len(self.positions),
            utilization_pct=min(utilization, 1.0),
        )

    def can_open_position(
        self,
        token_id: str,
        size_usdc: Decimal,
        side: Side,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if position can be opened within risk limits.

        Args:
            token_id: Token identifier
            size_usdc: Position size in USDC
            side: Trade side

        Returns:
            Tuple of (allowed, rejection_reason)
        """
        metrics = self.get_metrics()

        # Check individual position limit
        if size_usdc > self.max_position_size:
            return False, f"Position size ${size_usdc} exceeds limit ${self.max_position_size}"

        # Check total exposure limit
        new_gross = metrics.gross_exposure + size_usdc
        if new_gross > self.max_total_exposure:
            return False, f"Total exposure ${new_gross} would exceed limit ${self.max_total_exposure}"

        # Check skew limits
        projected_skew = self._project_skew(metrics, size_usdc, side)
        if abs(projected_skew) > self.max_skew_threshold:
            return False, f"Projected skew {float(projected_skew):.2f} exceeds threshold {float(self.max_skew_threshold):.2f}"

        return True, None

    def _project_skew(
        self,
        metrics: InventoryMetrics,
        size_usdc: Decimal,
        side: Side,
    ) -> Decimal:
        """
        Project inventory skew after opening a position.

        Args:
            metrics: Current inventory metrics
            size_usdc: Position size
            side: Trade side

        Returns:
            Projected skew (-1 to 1)
        """
        if side == Side.BUY:
            new_net = metrics.net_exposure + size_usdc
        else:
            new_net = metrics.net_exposure - size_usdc

        if self.max_total_exposure > 0:
            return new_net / self.max_total_exposure
        return Decimal("0")

    def close_position(self, token_id: str) -> bool:
        """
        Close a position.

        Args:
            token_id: Token identifier

        Returns:
            True if position closed
        """
        if token_id in self.positions:
            del self.positions[token_id]
            logger.info(f"Position closed: {token_id}")
            return True
        return False

    def close_all_positions(self) -> int:
        """
        Close all positions.

        Returns:
            Number of positions closed
        """
        count = len(self.positions)
        self.positions.clear()
        logger.info(f"Closed all positions: {count}")
        return count

    def get_position(self, token_id: str) -> Optional[Position]:
        """
        Get position for a token.

        Args:
            token_id: Token identifier

        Returns:
            Position if exists, None otherwise
        """
        return self.positions.get(token_id)

    def get_all_positions(self) -> List[Position]:
        """
        Get all open positions.

        Returns:
            List of all positions
        """
        return list(self.positions.values())
