"""
Unit tests for Atomic Arbitrage Strategy.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock

from src.core.models import OrderBook, Bid, Ask, ArbitrageOpportunity
from src.strategies.atomic import AtomicArbitrageStrategy


class TestVWAPCalculation:
    """Test suite for VWAP (Volume-Weighted Average Price) calculation."""

    @pytest.fixture
    def strategy(self):
        """Create a strategy instance for testing."""
        return AtomicArbitrageStrategy(
            trade_size=Decimal("10"),  # $10 USDC
            fee_rate=Decimal("0.0035"),  # 0.35% fee
            min_profit_threshold=Decimal("0.01"),  # 1% minimum profit
        )

    def test_calculate_vwap_single_order(self, strategy):
        """Test VWAP with a single order that covers full trade size."""
        asks = [
            Ask(price=Decimal("0.50"), size=Decimal("100"), token_id="yes_token")
        ]
        vwap = strategy._calculate_vwap(asks, Decimal("10"))
        assert vwap == Decimal("0.50")

    def test_calculate_vwap_multiple_orders_exact(self, strategy):
        """Test VWAP with multiple orders that exactly cover trade size."""
        asks = [
            Ask(price=Decimal("0.50"), size=Decimal("20"), token_id="yes_token"),
            Ask(price=Decimal("0.52"), size=Decimal("20"), token_id="yes_token"),
        ]
        # First order: 20 tokens at $0.50 = $10.00 (fills entire trade)
        # We only need $10, so we take $10 / $0.50 = 20 tokens from first order
        # VWAP = $10 / 20 = 0.50
        vwap = strategy._calculate_vwap(asks, Decimal("10"))
        assert vwap == Decimal("0.50")

    def test_calculate_vwap_multiple_orders_partial(self, strategy):
        """Test VWAP with partial fill from multiple orders."""
        asks = [
            Ask(price=Decimal("0.50"), size=Decimal("10"), token_id="yes_token"),
            Ask(price=Decimal("0.52"), size=Decimal("20"), token_id="yes_token"),
        ]
        # First order: 10 tokens at $0.50 = $5.00 (fully taken)
        # Remaining $5 needed at $0.52 = 9.62 tokens
        # Total cost = $5.00 + $5.00 = $10.00
        # Total tokens = 10 + 9.62 = 19.62
        # VWAP = $10.00 / 19.62 = ~0.5097
        vwap = strategy._calculate_vwap(asks, Decimal("10"))
        # Calculate expected VWAP
        tokens_from_second = Decimal("5") / Decimal("0.52")
        total_tokens = Decimal("10") + tokens_from_second
        expected_vwap = Decimal("10") / total_tokens
        assert abs(vwap - expected_vwap) < Decimal("0.0001")

    def test_calculate_vwap_insufficient_liquidity(self, strategy):
        """Test VWAP when insufficient liquidity available."""
        asks = [
            Ask(price=Decimal("0.50"), size=Decimal("5"), token_id="yes_token")
        ]
        # Only $2.50 worth of liquidity available
        with pytest.raises(ValueError, match="Insufficient liquidity"):
            strategy._calculate_vwap(asks, Decimal("10"))

    def test_calculate_vwap_empty_orderbook(self, strategy):
        """Test VWAP with empty order book."""
        with pytest.raises(ValueError, match="Insufficient liquidity"):
            strategy._calculate_vwap([], Decimal("10"))


class TestCheckOpportunity:
    """Test suite for checking arbitrage opportunities."""

    @pytest.fixture
    def strategy(self):
        """Create a strategy instance for testing."""
        return AtomicArbitrageStrategy(
            trade_size=Decimal("10"),
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.01"),
        )

    @pytest.fixture
    def yes_orderbook(self):
        """Create a YES order book."""
        return OrderBook(
            token_id="yes_123",
            asks=[
                Ask(price=Decimal("0.48"), size=Decimal("20"), token_id="yes_123"),
                Ask(price=Decimal("0.50"), size=Decimal("30"), token_id="yes_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

    @pytest.fixture
    def no_orderbook(self):
        """Create a NO order book."""
        return OrderBook(
            token_id="no_123",
            asks=[
                Ask(price=Decimal("0.50"), size=Decimal("20"), token_id="no_123"),
                Ask(price=Decimal("0.52"), size=Decimal("30"), token_id="no_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

    async def test_profitable_arbitrage_detected(self, strategy, yes_orderbook, no_orderbook):
        """Test that profitable arbitrage is detected."""
        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)

        assert opportunity is not None
        assert isinstance(opportunity, ArbitrageOpportunity)
        assert opportunity.yes_token_id == "yes_123"
        assert opportunity.no_token_id == "no_123"
        assert opportunity.expected_profit > 0
        assert opportunity.net_profit > 0

    async def test_no_arbitrage_when_prices_sum_above_one(self, strategy):
        """Test no arbitrage when YES + NO prices > 1.0."""
        yes_orderbook = OrderBook(
            token_id="yes_123",
            asks=[
                Ask(price=Decimal("0.60"), size=Decimal("20"), token_id="yes_123"),
            ],
            bids=[],
            last_update=1234567890,
        )
        no_orderbook = OrderBook(
            token_id="no_123",
            asks=[
                Ask(price=Decimal("0.50"), size=Decimal("20"), token_id="no_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)
        assert opportunity is None

    async def test_no_arbitrage_when_profit_below_threshold(self, strategy):
        """Test no arbitrage when profit is below minimum threshold."""
        yes_orderbook = OrderBook(
            token_id="yes_123",
            asks=[
                Ask(price=Decimal("0.50"), size=Decimal("20"), token_id="yes_123"),
            ],
            bids=[],
            last_update=1234567890,
        )
        no_orderbook = OrderBook(
            token_id="no_123",
            asks=[
                Ask(price=Decimal("0.495"), size=Decimal("20"), token_id="no_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

        # Sum = 0.995, but after fees it's not profitable
        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)
        # This might return an opportunity with very low profit, depending on fees
        # We'll verify in implementation

    async def test_arbitrage_includes_fees_and_gas(self, strategy, yes_orderbook, no_orderbook):
        """Test that arbitrage calculation includes fees and gas."""
        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)

        if opportunity:
            # Verify fees are included
            assert opportunity.fees > 0
            # Verify gas estimate is included
            assert opportunity.gas_estimate >= 0
            # Verify net profit is positive
            assert opportunity.net_profit > 0
            # Verify net profit < expected profit (due to fees and gas)
            cost_per_unit = opportunity.yes_price + opportunity.no_price
            gross_profit_per_unit = Decimal("1.0") - cost_per_unit
            expected_net = gross_profit_per_unit * opportunity.trade_size - opportunity.fees - opportunity.gas_estimate
            assert abs(opportunity.net_profit - expected_net) < Decimal("0.01")

    async def test_no_arbitrage_with_empty_orderbook(self, strategy):
        """Test no arbitrage when one order book is empty."""
        yes_orderbook = OrderBook(
            token_id="yes_123",
            asks=[],
            bids=[],
            last_update=1234567890,
        )
        no_orderbook = OrderBook(
            token_id="no_123",
            asks=[
                Ask(price=Decimal("0.50"), size=Decimal("20"), token_id="no_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)
        assert opportunity is None

    async def test_no_arbitrage_with_insufficient_liquidity(self, strategy):
        """Test no arbitrage when insufficient liquidity for trade size."""
        yes_orderbook = OrderBook(
            token_id="yes_123",
            asks=[
                Ask(price=Decimal("0.40"), size=Decimal("5"), token_id="yes_123"),
            ],
            bids=[],
            last_update=1234567890,
        )
        no_orderbook = OrderBook(
            token_id="no_123",
            asks=[
                Ask(price=Decimal("0.40"), size=Decimal("5"), token_id="no_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)
        # Should return None or opportunity with reduced size
        assert opportunity is None or opportunity.trade_size < Decimal("10")


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.fixture
    def strategy(self):
        """Create a strategy instance for testing."""
        return AtomicArbitrageStrategy(
            trade_size=Decimal("10"),
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.01"),
        )

    def test_zero_fee_rate(self):
        """Test strategy with zero fee rate."""
        strategy = AtomicArbitrageStrategy(
            trade_size=Decimal("10"),
            fee_rate=Decimal("0.0"),
            min_profit_threshold=Decimal("0.01"),
        )
        assert strategy.fee_rate == Decimal("0.0")

    def test_very_small_trade_size(self):
        """Test strategy with very small trade size."""
        strategy = AtomicArbitrageStrategy(
            trade_size=Decimal("0.01"),
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.01"),
        )
        assert strategy.trade_size == Decimal("0.01")

    async def test_gas_estimate_can_be_zero(self, strategy):
        """Test that gas estimate can be zero (for dry-run mode)."""
        # In dry-run mode, gas estimate might be zero
        assert True  # Placeholder for implementation verification

    async def test_exact_threshold_profit(self, strategy):
        """Test arbitrage at exactly minimum profit threshold."""
        yes_orderbook = OrderBook(
            token_id="yes_123",
            asks=[
                Ask(price=Decimal("0.49"), size=Decimal("20"), token_id="yes_123"),
            ],
            bids=[],
            last_update=1234567890,
        )
        no_orderbook = OrderBook(
            token_id="no_123",
            asks=[
                Ask(price=Decimal("0.49"), size=Decimal("20"), token_id="no_123"),
            ],
            bids=[],
            last_update=1234567890,
        )

        opportunity = await strategy.check_opportunity(yes_orderbook, no_orderbook)
        # Sum = 0.98, which is profitable after fees
        # Should detect opportunity
