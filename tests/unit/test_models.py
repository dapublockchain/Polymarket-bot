"""
Unit tests for core data models.

Tests are written FIRST (TDD methodology).
These should fail initially because models might not have proper validation.
"""
import pytest
from decimal import Decimal
from pydantic import ValidationError

from src.core.models import Bid, Ask, OrderBook, Signal, ArbitrageOpportunity, MarketPair


class TestBid:
    """Test suite for Bid model."""

    def test_create_valid_bid(self):
        """Test creating a valid bid."""
        bid = Bid(price=Decimal("0.55"), size=Decimal("100"), token_id="yes_token_123")
        assert bid.price == Decimal("0.55")
        assert bid.size == Decimal("100")
        assert bid.token_id == "yes_token_123"

    def test_bid_rejects_negative_price(self):
        """Test that bid rejects negative price."""
        with pytest.raises(ValidationError):
            Bid(price=Decimal("-0.55"), size=Decimal("100"), token_id="yes_token_123")

    def test_bid_rejects_zero_price(self):
        """Test that bid rejects zero price."""
        with pytest.raises(ValidationError):
            Bid(price=Decimal("0.0"), size=Decimal("100"), token_id="yes_token_123")

    def test_bid_rejects_negative_size(self):
        """Test that bid rejects negative size."""
        with pytest.raises(ValidationError):
            Bid(price=Decimal("0.55"), size=Decimal("-100"), token_id="yes_token_123")

    def test_bid_rejects_zero_size(self):
        """Test that bid rejects zero size."""
        with pytest.raises(ValidationError):
            Bid(price=Decimal("0.55"), size=Decimal("0"), token_id="yes_token_123")

    def test_bid_accepts_very_small_values(self):
        """Test that bid accepts very small positive values."""
        bid = Bid(price=Decimal("0.0001"), size=Decimal("0.001"), token_id="yes_token_123")
        assert bid.price == Decimal("0.0001")
        assert bid.size == Decimal("0.001")


class TestAsk:
    """Test suite for Ask model."""

    def test_create_valid_ask(self):
        """Test creating a valid ask."""
        ask = Ask(price=Decimal("0.45"), size=Decimal("50"), token_id="no_token_456")
        assert ask.price == Decimal("0.45")
        assert ask.size == Decimal("50")
        assert ask.token_id == "no_token_456"

    def test_ask_rejects_negative_price(self):
        """Test that ask rejects negative price."""
        with pytest.raises(ValidationError):
            Ask(price=Decimal("-0.45"), size=Decimal("50"), token_id="no_token_456")

    def test_ask_rejects_zero_price(self):
        """Test that ask rejects zero price."""
        with pytest.raises(ValidationError):
            Ask(price=Decimal("0.0"), size=Decimal("50"), token_id="no_token_456")

    def test_ask_rejects_negative_size(self):
        """Test that ask rejects negative size."""
        with pytest.raises(ValidationError):
            Ask(price=Decimal("0.45"), size=Decimal("-50"), token_id="no_token_456")


class TestOrderBook:
    """Test suite for OrderBook model."""

    def test_create_empty_orderbook(self):
        """Test creating an empty order book."""
        orderbook = OrderBook(token_id="test_token", last_update=1234567890)
        assert orderbook.token_id == "test_token"
        assert orderbook.bids == []
        assert orderbook.asks == []
        assert orderbook.last_update == 1234567890

    def test_create_orderbook_with_bids_and_asks(self):
        """Test creating an order book with orders."""
        bids = [Bid(price=Decimal("0.60"), size=Decimal("100"), token_id="token1")]
        asks = [Ask(price=Decimal("0.40"), size=Decimal("100"), token_id="token1")]
        orderbook = OrderBook(token_id="token1", bids=bids, asks=asks, last_update=1234567890)

        assert len(orderbook.bids) == 1
        assert len(orderbook.asks) == 1
        assert orderbook.bids[0].price == Decimal("0.60")
        assert orderbook.asks[0].price == Decimal("0.40")

    def test_get_best_bid_returns_highest(self):
        """Test that get_best_bid returns highest bid."""
        bids = [
            Bid(price=Decimal("0.60"), size=Decimal("100"), token_id="token1"),
            Bid(price=Decimal("0.65"), size=Decimal("50"), token_id="token1"),
            Bid(price=Decimal("0.55"), size=Decimal("200"), token_id="token1"),
        ]
        orderbook = OrderBook(token_id="token1", bids=bids, last_update=1234567890)

        best_bid = orderbook.get_best_bid()
        assert best_bid is not None
        assert best_bid.price == Decimal("0.65")

    def test_get_best_bid_returns_none_when_empty(self):
        """Test that get_best_bid returns None when no bids."""
        orderbook = OrderBook(token_id="token1", last_update=1234567890)
        assert orderbook.get_best_bid() is None

    def test_get_best_ask_returns_lowest(self):
        """Test that get_best_ask returns lowest ask."""
        asks = [
            Ask(price=Decimal("0.40"), size=Decimal("100"), token_id="token1"),
            Ask(price=Decimal("0.35"), size=Decimal("50"), token_id="token1"),
            Ask(price=Decimal("0.45"), size=Decimal("200"), token_id="token1"),
        ]
        orderbook = OrderBook(token_id="token1", asks=asks, last_update=1234567890)

        best_ask = orderbook.get_best_ask()
        assert best_ask is not None
        assert best_ask.price == Decimal("0.35")

    def test_get_best_ask_returns_none_when_empty(self):
        """Test that get_best_ask returns None when no asks."""
        orderbook = OrderBook(token_id="token1", last_update=1234567890)
        assert orderbook.get_best_ask() is None


class TestSignal:
    """Test suite for Signal model."""

    def test_create_valid_signal(self):
        """Test creating a valid trading signal."""
        signal = Signal(
            strategy="atomic",
            token_id="token123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.50"),
            trade_size=Decimal("10"),
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.55"),
            confidence=0.85,
            reason="Price misalignment detected",
        )
        assert signal.strategy == "atomic"
        assert signal.token_id == "token123"
        assert signal.expected_profit == Decimal("0.50")
        assert signal.confidence == 0.85

    def test_signal_rejects_negative_profit(self):
        """Test that signal rejects negative expected profit."""
        with pytest.raises(ValidationError):
            Signal(
                strategy="atomic",
                token_id="token123",
                signal_type="BUY_YES",
                expected_profit=Decimal("-0.50"),
                trade_size=Decimal("10"),
                confidence=0.85,
                reason="Test",
            )

    def test_signal_rejects_confidence_out_of_range(self):
        """Test that signal rejects confidence outside [0, 1]."""
        with pytest.raises(ValidationError):
            Signal(
                strategy="atomic",
                token_id="token123",
                signal_type="BUY_YES",
                expected_profit=Decimal("0.50"),
                trade_size=Decimal("10"),
                confidence=1.5,  # Invalid
                reason="Test",
            )

        with pytest.raises(ValidationError):
            Signal(
                strategy="atomic",
                token_id="token123",
                signal_type="BUY_YES",
                expected_profit=Decimal("0.50"),
                trade_size=Decimal("10"),
                confidence=-0.1,  # Invalid
                reason="Test",
            )

    def test_signal_accepts_boundary_confidence(self):
        """Test that signal accepts confidence at boundaries."""
        signal1 = Signal(
            strategy="atomic",
            token_id="token123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.50"),
            trade_size=Decimal("10"),
            confidence=0.0,
            reason="Test",
        )
        assert signal1.confidence == 0.0

        signal2 = Signal(
            strategy="atomic",
            token_id="token123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.50"),
            trade_size=Decimal("10"),
            confidence=1.0,
            reason="Test",
        )
        assert signal2.confidence == 1.0


class TestArbitrageOpportunity:
    """Test suite for ArbitrageOpportunity model."""

    def test_create_valid_arbitrage(self):
        """Test creating a valid arbitrage opportunity."""
        arb = ArbitrageOpportunity(
            strategy="atomic",
            token_id="pair123",
            signal_type="ARBITRAGE",
            expected_profit=Decimal("0.10"),
            trade_size=Decimal("10"),
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.54"),
            confidence=0.90,
            reason="YES + NO < 1.0",
            yes_token_id="yes_123",
            no_token_id="no_123",
            yes_cost=Decimal("4.50"),
            no_cost=Decimal("5.40"),
            total_cost=Decimal("9.90"),
            fees=Decimal("0.05"),
            gas_estimate=Decimal("0.02"),
            net_profit=Decimal("0.08"),
        )
        assert arb.net_profit == Decimal("0.08")
        assert arb.total_cost == Decimal("9.90")

    def test_arbitrage_rejects_negative_costs(self):
        """Test that arbitrage rejects negative costs."""
        with pytest.raises(ValidationError):
            ArbitrageOpportunity(
                strategy="atomic",
                token_id="pair123",
                signal_type="ARBITRAGE",
                expected_profit=Decimal("0.10"),
                trade_size=Decimal("10"),
                confidence=0.90,
                reason="Test",
                yes_token_id="yes_123",
                no_token_id="no_123",
                yes_cost=Decimal("-4.50"),  # Invalid
                no_cost=Decimal("5.40"),
                total_cost=Decimal("9.90"),
                fees=Decimal("0.05"),
                gas_estimate=Decimal("0.02"),
                net_profit=Decimal("0.08"),
            )


class TestMarketPair:
    """Test suite for MarketPair model."""

    def test_create_valid_market_pair(self):
        """Test creating a valid market pair."""
        pair = MarketPair(
            condition_id="condition_123",
            yes_token_id="yes_123",
            no_token_id="no_123",
            question="Will it rain tomorrow?",
            end_time=1735689600,
        )
        assert pair.condition_id == "condition_123"
        assert pair.yes_token_id == "yes_123"
        assert pair.no_token_id == "no_123"
        assert pair.end_time == 1735689600

    def test_market_pair_with_tick_size(self):
        """Test market pair with tick size."""
        pair = MarketPair(
            condition_id="condition_123",
            yes_token_id="yes_123",
            no_token_id="no_123",
            question="Will it rain tomorrow?",
            tick_size=Decimal("0.01"),
        )
        assert pair.tick_size == Decimal("0.01")

    def test_is_mutually_exclusive_default_false(self):
        """Test that is_mutually_exclusive returns False by default."""
        pair1 = MarketPair(
            condition_id="condition_123",
            yes_token_id="yes_123",
            no_token_id="no_123",
            question="Will it rain tomorrow?",
        )
        pair2 = MarketPair(
            condition_id="condition_456",
            yes_token_id="yes_456",
            no_token_id="no_456",
            question="Will it be sunny tomorrow?",
        )
        assert pair1.is_mutually_exclusive(pair2) is False
