"""
Unified execution router for dry-run and live modes.

This router provides a single interface that routes execution requests
to either SimulatedExecutor (dry-run) or LiveExecutor (live mode),
ensuring both modes share the same execution pipeline logic.
"""
from typing import Optional, Tuple

from loguru import logger

from src.core.models import ArbitrageOpportunity, OrderBook
from src.execution.simulated_executor import SimulatedExecutor
from src.execution.fill import Fill
from src.core.config import Config


class ExecutionRouter:
    """
    Unified execution router for dry-run and live modes.

    Routes execution requests to either SimulatedExecutor (dry-run)
    or LiveExecutor (live).

    This ensures both modes follow the same execution pipeline:
    signal → order_request → execution → fill → pnl_update

    Usage:
        router = ExecutionRouter(simulated_executor=SimulatedExecutor())
        yes_fill, no_fill, tx_result = await router.execute_arbitrage(
            opportunity, yes_book, no_book, trace_id
        )
    """

    def __init__(
        self,
        simulated_executor: SimulatedExecutor,
    ):
        """
        Initialize the execution router.

        Args:
            simulated_executor: Simulated executor for dry-run mode
        """
        self.simulated_executor = simulated_executor
        self._dry_run = Config.DRY_RUN

        logger.info(f"ExecutionRouter initialized (mode={'dry-run' if self._dry_run else 'live'})")

    def set_mode(self, dry_run: bool) -> None:
        """
        Switch between dry-run and live mode.

        Args:
            dry_run: True for dry-run mode, False for live mode
        """
        self._dry_run = dry_run
        logger.info(f"ExecutionRouter mode switched to {'dry-run' if dry_run else 'live'}")

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        yes_orderbook: OrderBook,
        no_orderbook: OrderBook,
        trace_id: str,
    ) -> Tuple[Optional[Fill], Optional[Fill], Optional[dict]]:
        """
        Execute an arbitrage opportunity.

        This method routes to the appropriate executor based on mode:
        - Dry-run: Uses SimulatedExecutor, returns (yes_fill, no_fill, None)
        - Live: Uses live executor, returns (None, None, tx_result)

        Args:
            opportunity: Arbitrage opportunity to execute
            yes_orderbook: Current YES token order book
            no_orderbook: Current NO token order book
            trace_id: Trace ID for this execution

        Returns:
            Tuple of (yes_fill, no_fill, tx_result)
            - In dry-run: fills are populated, tx_result is None
            - In live: fills are None, tx_result is populated (when implemented)
        """
        if self._dry_run:
            # Use simulated executor
            logger.debug(f"Routing to SimulatedExecutor for {trace_id[:8]}...")

            yes_fill, no_fill = await self.simulated_executor.execute_arbitrage(
                opportunity, yes_orderbook, no_orderbook, trace_id
            )

            return yes_fill, no_fill, None
        else:
            # Use live executor (not yet implemented)
            logger.warning(f"Live executor not yet implemented for {trace_id[:8]}...")

            # TODO: Integrate with existing tx_sender for live execution
            # For now, return None fills and no tx_result
            return None, None, None

    async def execute_single_leg(
        self,
        token_id: str,
        side: str,  # "buy" or "sell"
        quantity_usdc: float,  # Quantity in USDC notional
        orderbook: OrderBook,
        trace_id: str,
    ) -> Optional[Fill]:
        """
        Execute a single-leg order (not arbitrage).

        This can be used for strategies that trade a single token
        (e.g., market making, directional trading).

        Args:
            token_id: Token to trade
            side: "buy" or "sell"
            quantity_usdc: Quantity in USDC notional
            orderbook: Current order book
            trace_id: Trace ID for this execution

        Returns:
            Fill if successful, None if failed
        """
        from src.execution.fill import FillSide, OrderRequest

        # Create order request
        order_request_id = f"single_{trace_id[:8]}"
        timestamp_ms = int(__import__('asyncio').get_event_loop().time() * 1000)

        order = OrderRequest(
            request_id=order_request_id,
            token_id=token_id,
            side=FillSide.BUY if side.lower() == "buy" else FillSide.SELL,
            quantity=__import__('decimal').Decimal(str(quantity_usdc)),
            trace_id=trace_id,
            timestamp_ms=timestamp_ms,
        )

        if self._dry_run:
            # Update local orderbook
            self.simulated_executor.update_orderbook(token_id, orderbook)

            # Execute with simulated executor
            fill = await self.simulated_executor.execute_order(order)

            return fill
        else:
            # Live executor not yet implemented
            logger.warning(f"Live executor not yet implemented for single-leg orders")
            return None

    def get_stats(self) -> dict:
        """Get router statistics."""
        stats = {
            "mode": "dry-run" if self._dry_run else "live",
            "simulated_executor_stats": self.simulated_executor.get_stats(),
        }
        return stats
