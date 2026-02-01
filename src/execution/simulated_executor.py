"""
Simulated execution engine for dry-run mode.

This module simulates order execution against current order books
with realistic pricing, slippage, and fill behavior.
"""
import asyncio
from decimal import Decimal
from typing import Optional, List, Tuple
from dataclasses import dataclass

from loguru import logger

from src.core.models import OrderBook, ArbitrageOpportunity
from src.execution.fill import Fill, FillSide
from src.core.telemetry import generate_trace_id, log_event, EventType


@dataclass
class OrderRequest:
    """Order request for execution."""
    request_id: str
    token_id: str
    side: FillSide
    quantity: Decimal  # In USDC notional
    trace_id: str
    timestamp_ms: int


class SimulatedExecutor:
    """
    Simulated execution engine for dry-run mode.

    Simulates fills against current order book with realistic slippage.
    Uses VWAP execution for better price discovery.

    Key features:
    - VWAP execution against order book
    - Configurable slippage
    - Support for partial fills
    - Arbitrage execution (YES + NO legs)
    """

    def __init__(
        self,
        slippage_bps: int = 5,  # 0.05% default slippage
        partial_fill_probability: float = 0.0,  # No partial fills initially
        fee_rate: Decimal = Decimal("0.0035"),  # 0.35% Polymarket fee
    ):
        """
        Initialize the simulated executor.

        Args:
            slippage_bps: Slippage in basis points (default 5 = 0.05%)
            partial_fill_probability: Probability of partial fill (0-1)
            fee_rate: Trading fee rate (default 0.35%)
        """
        self.slippage_bps = slippage_bps
        self.partial_fill_probability = partial_fill_probability
        self.fee_rate = fee_rate
        self._orderbooks: dict[str, OrderBook] = {}

    def update_orderbook(self, token_id: str, orderbook: OrderBook) -> None:
        """
        Update local order book for a token.

        Args:
            token_id: Token identifier
            orderbook: Current order book
        """
        self._orderbooks[token_id] = orderbook

    async def execute_order(
        self,
        order: OrderRequest,
    ) -> Optional[Fill]:
        """
        Simulate order execution against current order book.

        Args:
            order: Order request to execute

        Returns:
            Fill if successful, None if failed
        """
        orderbook = self._orderbooks.get(order.token_id)
        if not orderbook:
            logger.warning(f"No orderbook for {order.token_id[:20]}...")
            return None

        # Calculate execution based on order side
        if order.side == FillSide.BUY:
            return await self._execute_buy(order, orderbook)
        else:
            return await self._execute_sell(order, orderbook)

    async def _execute_buy(
        self,
        order: OrderRequest,
        orderbook: OrderBook,
    ) -> Optional[Fill]:
        """
        Execute a buy order against asks.

        Uses VWAP calculation to get realistic execution price.

        Args:
            order: Buy order to execute
            orderbook: Current order book

        Returns:
            Fill if successful, None if insufficient liquidity
        """
        if not orderbook.asks:
            logger.debug(f"No asks for {order.token_id[:20]}...")
            return None

        # VWAP calculation
        remaining_usdc = order.quantity
        total_tokens = Decimal("0")
        total_cost = Decimal("0")
        execution_price = Decimal("0")

        # Sort asks by price (lowest first)
        sorted_asks = sorted(orderbook.asks, key=lambda a: a.price)

        for ask in sorted_asks:
            if remaining_usdc <= 0:
                break

            level_value = ask.size * ask.price
            if level_value >= remaining_usdc:
                # This level can fill the remaining order
                tokens_needed = remaining_usdc / ask.price
                total_cost += remaining_usdc
                total_tokens += tokens_needed
                remaining_usdc = Decimal("0")
                execution_price = ask.price
                break
            else:
                # Take entire level
                total_cost += level_value
                total_tokens += ask.size
                remaining_usdc -= level_value
                execution_price = ask.price

        if remaining_usdc > 0:
            # Insufficient liquidity
            logger.debug(f"Insufficient liquidity for {order.token_id[:20]}...")
            return None

        # Calculate fees (0.35% for Polymarket)
        fees = total_cost * self.fee_rate

        # Apply slippage (worse price for buys)
        slippage_multiplier = Decimal("1") + Decimal(self.slippage_bps) / Decimal("10000")
        final_price = execution_price * slippage_multiplier

        # Create fill
        fill = Fill(
            fill_id=f"sim_{generate_trace_id()[:8]}",
            order_request_id=order.request_id,
            token_id=order.token_id,
            side=FillSide.BUY,
            price=final_price,
            quantity=total_tokens,
            fees=fees,
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
            trace_id=order.trace_id,
            is_simulated=True,
            slippage_bps=self.slippage_bps,
        )

        # Log telemetry
        await log_event(
            EventType.FILL,
            {
                "fill_id": fill.fill_id,
                "token_id": fill.token_id,
                "side": fill.side.value,
                "price": str(fill.price),
                "quantity": str(fill.quantity),
                "fees": str(fill.fees),
                "is_simulated": True,
                "slippage_bps": self.slippage_bps,
            },
            trace_id=order.trace_id
        )

        return fill

    async def _execute_sell(
        self,
        order: OrderRequest,
        orderbook: OrderBook,
    ) -> Optional[Fill]:
        """
        Execute a sell order against bids.

        For simplicity, executes at best bid with slippage.

        Args:
            order: Sell order to execute
            orderbook: Current order book

        Returns:
            Fill if successful, None if no bids
        """
        if not orderbook.bids:
            logger.debug(f"No bids for {order.token_id[:20]}...")
            return None

        # Get best bid (highest price)
        best_bid = orderbook.get_best_bid()
        if not best_bid:
            return None

        # For simplicity, sell at best bid with slippage
        # Apply slippage (worse price for sells)
        slippage_multiplier = Decimal("1") - Decimal(self.slippage_bps) / Decimal("10000")
        final_price = best_bid.price * slippage_multiplier

        # Calculate quantity to sell (order.quantity is in USDC notional)
        tokens_to_sell = order.quantity / final_price

        # Calculate fees
        fees = order.quantity * self.fee_rate

        fill = Fill(
            fill_id=f"sim_{generate_trace_id()[:8]}",
            order_request_id=order.request_id,
            token_id=order.token_id,
            side=FillSide.SELL,
            price=final_price,
            quantity=tokens_to_sell,
            fees=fees,
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
            trace_id=order.trace_id,
            is_simulated=True,
            slippage_bps=self.slippage_bps,
        )

        return fill

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        yes_orderbook: OrderBook,
        no_orderbook: OrderBook,
        trace_id: str,
    ) -> Tuple[Optional[Fill], Optional[Fill]]:
        """
        Execute an arbitrage opportunity (buy YES + buy NO).

        For arbitrage, we buy both YES and NO tokens. At settlement,
        one will be worth $1 and the other $0, so we always get $1 back
        per pair. Our profit = $1 - (cost_yes + cost_no + fees + slippage).

        Args:
            opportunity: Arbitrage opportunity to execute
            yes_orderbook: Current YES token order book
            no_orderbook: Current NO token order book
            trace_id: Trace ID for this execution

        Returns:
            Tuple of (yes_fill, no_fill)
        """
        # Update local orderbooks
        self.update_orderbook(opportunity.yes_token_id, yes_orderbook)
        self.update_orderbook(opportunity.no_token_id, no_orderbook)

        # Create order requests
        order_request_id = f"arb_{trace_id[:8]}"
        timestamp_ms = int(asyncio.get_event_loop().time() * 1000)

        yes_order = OrderRequest(
            request_id=f"{order_request_id}_yes",
            token_id=opportunity.yes_token_id,
            side=FillSide.BUY,
            quantity=opportunity.yes_cost,
            trace_id=trace_id,
            timestamp_ms=timestamp_ms,
        )

        no_order = OrderRequest(
            request_id=f"{order_request_id}_no",
            token_id=opportunity.no_token_id,
            side=FillSide.BUY,
            quantity=opportunity.no_cost,
            trace_id=trace_id,
            timestamp_ms=timestamp_ms,
        )

        # Execute both legs
        yes_fill = await self.execute_order(yes_order)
        no_fill = await self.execute_order(no_order)

        # Log results
        if yes_fill and no_fill:
            logger.info(f"   [模拟模式] 模拟成交成功:")
            logger.info(f"      YES: {yes_fill.quantity:.4f} @ ${yes_fill.price:.4f}")
            logger.info(f"      NO:  {no_fill.quantity:.4f} @ ${no_fill.price:.4f}")

            # Calculate actual PnL for this arbitrage
            # At settlement, we get $1.0 per pair (YES + NO = 1.0)
            total_cost = yes_fill.net_proceeds + no_fill.net_proceeds  # Negative (cost)
            total_tokens = yes_fill.quantity + no_fill.quantity
            payout = total_tokens * Decimal("1.0")  # Settlement value
            pnl = payout + total_cost  # total_cost is negative, so this is payout - cost

            logger.info(f"      总成本: ${-total_cost:.4f}")
            logger.info(f"      预期结算: ${payout:.4f}")
            logger.info(f"      模拟PnL: ${pnl:.4f}")
        else:
            logger.warning(f"   [模拟模式] 模拟成交失败:")
            if not yes_fill:
                logger.warning(f"      YES fill 失败")
            if not no_fill:
                logger.warning(f"      NO fill 失败")

        return yes_fill, no_fill

    def get_stats(self) -> dict:
        """Get executor statistics."""
        return {
            "slippage_bps": self.slippage_bps,
            "fee_rate": str(self.fee_rate),
            "tracked_orderbooks": len(self._orderbooks),
        }
