"""
Unit tests for SimulatedExecutor.

Tests the simulated execution engine that generates realistic fills
against order books with VWAP execution.
"""
import pytest
import asyncio
from decimal import Decimal
from datetime import datetime

from src.execution.simulated_executor import SimulatedExecutor, OrderRequest
from src.core.models import OrderBook, Bid, Ask, ArbitrageOpportunity
from src.execution.fill import FillSide


class TestSimulatedExecutor:
    """Test SimulatedExecutor class."""

    @pytest.fixture
    def executor(self):
        """Create a SimulatedExecutor instance."""
        return SimulatedExecutor(
            slippage_bps=5,
            fee_rate=Decimal("0.0035"),
        )

    @pytest.fixture
    def sample_orderbook(self):
        """Create a sample order book with multiple levels."""
        asks = [
            Ask(price=Decimal("0.60"), size=Decimal("100"), token_id="token_123"),
            Ask(price=Decimal("0.62"), size=Decimal("200"), token_id="token_123"),
            Ask(price=Decimal("0.65"), size=Decimal("300"), token_id="token_123"),
        ]
        bids = [
            Bid(price=Decimal("0.58"), size=Decimal("100"), token_id="token_123"),
            Bid(price=Decimal("0.55"), size=Decimal("200"), token_id="token_123"),
        ]
        return OrderBook(
            token_id="token_123",
            asks=asks,
            bids=bids,
            last_update=1234567890,
        )

    @pytest.mark.asyncio
    async def test_update_orderbook(self, executor, sample_orderbook):
        """Test updating order book."""
        executor.update_orderbook("token_123", sample_orderbook)
        assert "token_123" in executor._orderbooks
        assert executor._orderbooks["token_123"] == sample_orderbook

    @pytest.mark.asyncio
    async def test_execute_buy_vwap(self, executor, sample_orderbook):
        """Test buy order execution with VWAP."""
        executor.update_orderbook("token_123", sample_orderbook)

        # Buy $150 worth (should consume first two levels)
        order = OrderRequest(
            request_id="order_1",
            token_id="token_123",
            side=FillSide.BUY,
            quantity=Decimal("150"),
            trace_id="trace_1",
            timestamp_ms=1234567890,
        )

        fill = await executor.execute_order(order)

        assert fill is not None
        assert fill.side == FillSide.BUY
        assert fill.is_simulated is True
        assert fill.slippage_bps == 5

        # VWAP should be between 0.60 and 0.62
        assert fill.price >= Decimal("0.60")
        assert fill.price < Decimal("0.62")

        # Should have bought approximately 150/0.60 = 250 tokens (with slippage)
        expected_quantity = Decimal("150") / fill.price
        assert abs(fill.quantity - expected_quantity) < Decimal("1")

        # Fees = 150 * 0.0035 = 0.525
        expected_fees = Decimal("150") * Decimal("0.0035")
        assert abs(fill.fees - expected_fees) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_execute_buy_insufficient_liquidity(self, executor):
        """Test buy order fails with insufficient liquidity."""
        # Small order book
        orderbook = OrderBook(
            token_id="token_illiquid",
            asks=[
                Ask(price=Decimal("0.60"), size=Decimal("10"), token_id="token_illiquid"),
            ],
            bids=[],
            last_update=1234567890,
        )
        executor.update_orderbook("token_illiquid", orderbook)

        # Try to buy $100 worth but only $6 available (10 * 0.60)
        order = OrderRequest(
            request_id="order_illiquid",
            token_id="token_illiquid",
            side=FillSide.BUY,
            quantity=Decimal("100"),
            trace_id="trace_illiquid",
            timestamp_ms=1234567890,
        )

        fill = await executor.execute_order(order)
        assert fill is None

    @pytest.mark.asyncio
    async def test_execute_sell_best_bid(self, executor, sample_orderbook):
        """Test sell order executes at best bid."""
        executor.update_orderbook("token_123", sample_orderbook)

        # Sell $50 worth
        order = OrderRequest(
            request_id="order_sell",
            token_id="token_123",
            side=FillSide.SELL,
            quantity=Decimal("50"),
            trace_id="trace_sell",
            timestamp_ms=1234567890,
        )

        fill = await executor.execute_order(order)

        assert fill is not None
        assert fill.side == FillSide.SELL
        assert fill.is_simulated is True

        # Best bid is 0.58, with slippage should be lower
        assert fill.price < Decimal("0.58")
        assert fill.price > Decimal("0.57")

    @pytest.mark.asyncio
    async def test_execute_arbitrage(self, executor):
        """Test arbitrage execution (buy YES + buy NO)."""
        yes_orderbook = OrderBook(
            token_id="token_yes",
            asks=[
                Ask(price=Decimal("0.60"), size=Decimal("100"), token_id="token_yes"),
            ],
            bids=[],
            last_update=1234567890,
        )

        no_orderbook = OrderBook(
            token_id="token_no",
            asks=[
                Ask(price=Decimal("0.35"), size=Decimal("100"), token_id="token_no"),
            ],
            bids=[],
            last_update=1234567890,
        )

        opportunity = ArbitrageOpportunity(
            yes_token_id="token_yes",
            no_token_id="token_no",
            yes_price=Decimal("0.60"),
            no_price=Decimal("0.35"),
            yes_cost=Decimal("60"),
            no_cost=Decimal("35"),
            expected_profit=Decimal("5"),
            strategy="atomic",
            reason="YES + NO = 0.95 < 1.0",
        )

        yes_fill, no_fill = await executor.execute_arbitrage(
            opportunity, yes_orderbook, no_orderbook, "trace_arb"
        )

        assert yes_fill is not None
        assert no_fill is not None

        assert yes_fill.token_id == "token_yes"
        assert no_fill.token_id == "token_no"

        assert yes_fill.side == FillSide.BUY
        assert no_fill.side == FillSide.BUY

        # Both fills should have same trace_id
        assert yes_fill.trace_id == "trace_arb"
        assert no_fill.trace_id == "trace_arb"

    @pytest.mark.asyncio
    async def test_execute_arbitrage_insufficient_liquidity(self, executor):
        """Test arbitrage fails with insufficient liquidity."""
        yes_orderbook = OrderBook(
            token_id="token_yes",
            asks=[
                Ask(price=Decimal("0.60"), size=Decimal("10"), token_id="token_yes"),
            ],
            bids=[],
            last_update=1234567890,
        )

        no_orderbook = OrderBook(
            token_id="token_no",
            asks=[
                Ask(price=Decimal("0.35"), size=Decimal("10"), token_id="token_no"),
            ],
            bids=[],
            last_update=1234567890,
        )

        opportunity = ArbitrageOpportunity(
            yes_token_id="token_yes",
            no_token_id="token_no",
            yes_price=Decimal("0.60"),
            no_price=Decimal("0.35"),
            yes_cost=Decimal("60"),  # Too much liquidity needed
            no_cost=Decimal("35"),
            expected_profit=Decimal("5"),
            strategy="atomic",
            reason="YES + NO = 0.95 < 1.0",
        )

        yes_fill, no_fill = await executor.execute_arbitrage(
            opportunity, yes_orderbook, no_orderbook, "trace_arb_fail"
        )

        # At least one should fail
        assert yes_fill is None or no_fill is None

    @pytest.mark.asyncio
    async def test_execute_order_no_orderbook(self, executor):
        """Test order execution fails when no orderbook exists."""
        order = OrderRequest(
            request_id="order_no_book",
            token_id="token_nonexistent",
            side=FillSide.BUY,
            quantity=Decimal("100"),
            trace_id="trace_no_book",
            timestamp_ms=1234567890,
        )

        fill = await executor.execute_order(order)
        assert fill is None

    def test_get_stats(self, executor):
        """Test get_stats returns correct information."""
        stats = executor.get_stats()

        assert stats["slippage_bps"] == 5
        assert stats["fee_rate"] == "0.0035"
        assert stats["tracked_orderbooks"] == 0

    @pytest.mark.asyncio
    async def test_slippage_application(self, executor):
        """Test that slippage is correctly applied."""
        orderbook = OrderBook(
            token_id="token_slippage",
            asks=[
                Ask(price=Decimal("1.00"), size=Decimal("100"), token_id="token_slippage"),
            ],
            bids=[],
            last_update=1234567890,
        )

        executor.update_orderbook("token_slippage", orderbook)

        order = OrderRequest(
            request_id="order_slippage",
            token_id="token_slippage",
            side=FillSide.BUY,
            quantity=Decimal("100"),
            trace_id="trace_slippage",
            timestamp_ms=1234567890,
        )

        fill = await executor.execute_order(order)

        # Price should be 1.00 * (1 + 5/10000) = 1.0005
        expected_price = Decimal("1.00") * (Decimal("1") + Decimal("5") / Decimal("10000"))
        assert fill.price == expected_price

    @pytest.mark.asyncio
    async def test_fee_calculation(self, executor):
        """Test that fees are correctly calculated."""
        orderbook = OrderBook(
            token_id="token_fees",
            asks=[
                Ask(price=Decimal("1.00"), size=Decimal("100"), token_id="token_fees"),
            ],
            bids=[],
            last_update=1234567890,
        )

        executor.update_orderbook("token_fees", orderbook)

        order = OrderRequest(
            request_id="order_fees",
            token_id="token_fees",
            side=FillSide.BUY,
            quantity=Decimal("100"),
            trace_id="trace_fees",
            timestamp_ms=1234567890,
        )

        fill = await executor.execute_order(order)

        # Fees = 100 * 0.0035 = 0.35
        expected_fees = Decimal("100") * Decimal("0.0035")
        assert fill.fees == expected_fees
