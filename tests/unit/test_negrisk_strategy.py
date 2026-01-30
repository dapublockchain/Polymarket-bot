"""
Unit tests for NegRisk Strategy.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock

from src.core.models import (
    OrderBook,
    Ask,
    MarketMetadata,
    Outcome,
    NegRiskSignal,
    TokenOpportunity,
)
from src.strategies.negrisk import NegRiskStrategy


class TestNegRiskStrategyInit:
    """Test suite for NegRiskStrategy initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        strategy = NegRiskStrategy()
        assert strategy.fee_rate == Decimal("0.0035")  # 0.35% default
        assert strategy.min_profit_threshold == Decimal("0.005")  # 0.5% default
        assert strategy.trade_size == Decimal("10.0")  # $10 default
        assert strategy.gas_estimate == Decimal("0.0")

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        strategy = NegRiskStrategy(
            fee_rate=Decimal("0.01"),  # 1%
            min_profit_threshold=Decimal("0.02"),  # 2%
            trade_size=Decimal("100.0"),  # $100
            gas_estimate=Decimal("0.5"),  # $0.50 gas
        )
        assert strategy.fee_rate == Decimal("0.01")
        assert strategy.min_profit_threshold == Decimal("0.02")
        assert strategy.trade_size == Decimal("100.0")
        assert strategy.gas_estimate == Decimal("0.5")


class TestCalculateTotalCost:
    """Test suite for VWAP calculation across multiple tokens."""

    @pytest.fixture
    def strategy(self):
        """Create a strategy instance for testing."""
        return NegRiskStrategy(
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
        )

    def test_calculate_total_cost_single_order_each(self, strategy):
        """Test VWAP when each token has single order covering trade size."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.45"), size=Decimal("100"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.30"), size=Decimal("100"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        results = strategy.calculate_total_cost(order_books, strategy.trade_size)

        assert len(results) == 2
        assert results["token-trump"].vwap_price == Decimal("0.45")
        assert results["token-trump"].vwap_cost == Decimal("10.0")
        assert results["token-trump"].shares == Decimal("10.0") / Decimal("0.45")
        assert results["token-trump"].filled is True

        assert results["token-biden"].vwap_price == Decimal("0.30")
        assert results["token-biden"].vwap_cost == Decimal("10.0")

    def test_calculate_total_cost_multiple_orders(self, strategy):
        """Test VWAP with multiple orders per token."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.45"), size=Decimal("10"), token_id="token-trump"),
                    Ask(price=Decimal("0.46"), size=Decimal("20"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        results = strategy.calculate_total_cost(order_books, Decimal("10.0"))

        # First order: 10 tokens at $0.45 = $4.50
        # Second order: Need $5.50 more at $0.46 = 11.96 tokens
        # Total cost: $10.00
        # Total tokens: 10 + 11.96 = 21.96
        # VWAP: $10.00 / 21.96 = ~0.4554
        assert results["token-trump"].filled is True
        assert results["token-trump"].vwap_cost == Decimal("10.0")

    def test_calculate_total_cost_insufficient_liquidity(self, strategy):
        """Test VWAP when some tokens have insufficient liquidity."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.45"), size=Decimal("5"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.30"), size=Decimal("100"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        results = strategy.calculate_total_cost(order_books, Decimal("10.0"))

        # Trump has insufficient liquidity, Biden is fine
        assert results["token-trump"].filled is False
        assert results["token-biden"].filled is True

    def test_calculate_total_cost_empty_orderbook(self, strategy):
        """Test VWAP when one order book is empty."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.30"), size=Decimal("100"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        results = strategy.calculate_total_cost(order_books, Decimal("10.0"))

        assert results["token-trump"].filled is False
        assert results["token-biden"].filled is True


class TestCalculateProfit:
    """Test suite for profit calculation."""

    @pytest.fixture
    def strategy(self):
        """Create a strategy instance for testing."""
        return NegRiskStrategy(
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
            gas_estimate=Decimal("0.01"),  # Lower gas for tests
        )

    def test_calculate_profit_profitable_opportunity(self, strategy):
        """Test profit calculation for profitable opportunity."""
        # 4 tokens, total cost = $3.80, payout = $4.00 (4 * $1)
        total_cost = Decimal("3.80")
        num_tokens = 4

        profit = strategy.calculate_profit(total_cost, num_tokens)

        # Payout = 4 * 1.0 = 4.0
        # Fees = 3.80 * 0.0035 = 0.0133
        # Gas = 0.1
        # Profit = 4.0 - 3.80 - 0.0133 - 0.1 = 0.0867
        expected_profit = Decimal("4.0") - total_cost - (total_cost * strategy.fee_rate) - strategy.gas_estimate
        assert abs(profit - expected_profit) < Decimal("0.0001")

    def test_calculate_profit_unprofitable_opportunity(self, strategy):
        """Test profit calculation for unprofitable opportunity."""
        # High total cost makes it unprofitable
        total_cost = Decimal("4.50")
        num_tokens = 4

        profit = strategy.calculate_profit(total_cost, num_tokens)
        assert profit < 0

    def test_calculate_profit_zero_fees(self):
        """Test profit calculation with zero fees."""
        strategy = NegRiskStrategy(
            fee_rate=Decimal("0.0"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
            gas_estimate=Decimal("0.0"),
        )

        total_cost = Decimal("3.80")
        num_tokens = 4

        profit = strategy.calculate_profit(total_cost, num_tokens)
        # Profit = 4.0 - 3.80 = 0.20
        expected_profit = Decimal("4.0") - total_cost
        assert abs(profit - expected_profit) < Decimal("0.0001")


class TestCheckThreshold:
    """Test suite for profit threshold checking."""

    def test_check_threshold_above_minimum(self):
        """Test threshold check when profit is above minimum."""
        strategy = NegRiskStrategy(
            min_profit_threshold=Decimal("0.01"),  # 1%
        )

        profit = Decimal("1.0")  # $1 profit
        total_investment = Decimal("50.0")  # $50 investment
        profit_pct = profit / total_investment  # 2%

        assert strategy.check_threshold(profit, total_investment) is True

    def test_check_threshold_below_minimum(self):
        """Test threshold check when profit is below minimum."""
        strategy = NegRiskStrategy(
            min_profit_threshold=Decimal("0.01"),  # 1%
        )

        profit = Decimal("0.25")  # $0.25 profit
        total_investment = Decimal("50.0")  # $50 investment
        profit_pct = profit / total_investment  # 0.5%

        assert strategy.check_threshold(profit, total_investment) is False

    def test_check_threshold_exactly_minimum(self):
        """Test threshold check at exactly minimum."""
        strategy = NegRiskStrategy(
            min_profit_threshold=Decimal("0.01"),  # 1%
        )

        profit = Decimal("0.50")  # $0.50 profit
        total_investment = Decimal("50.0")  # $50 investment
        profit_pct = profit / total_investment  # 1%

        assert strategy.check_threshold(profit, total_investment) is True

    def test_check_threshold_negative_profit(self):
        """Test threshold check with negative profit."""
        strategy = NegRiskStrategy(
            min_profit_threshold=Decimal("0.01"),
        )

        profit = Decimal("-1.0")  # Loss
        total_investment = Decimal("50.0")

        assert strategy.check_threshold(profit, total_investment) is False


class TestCheckOpportunity:
    """Test suite for checking NegRisk opportunities."""

    @pytest.fixture
    def strategy(self):
        """Create a strategy instance for testing."""
        return NegRiskStrategy(
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
            gas_estimate=Decimal("0.01"),  # Lower gas for tests
        )

    @pytest.fixture
    def market_metadata(self):
        """Create sample market metadata."""
        return MarketMetadata(
            market_id="election-winner-2024",
            title="2024 Presidential Election Winner",
            question="Who will win the 2024 US Presidential Election?",
            outcomes=[
                Outcome(name="Trump", token_id="token-trump", is_yes=True),
                Outcome(name="Biden", token_id="token-biden", is_yes=True),
                Outcome(name="Harris", token_id="token-harris", is_yes=True),
                Outcome(name="Other", token_id="token-other", is_yes=True),
            ],
            outcome_token_ids=["token-trump", "token-biden", "token-harris", "token-other"],
            is_binary=False,
        )

    def test_profitable_opportunity_detected(self, strategy, market_metadata):
        """Test that profitable opportunity is detected."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.40"), size=Decimal("1000"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.25"), size=Decimal("1000"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-harris": OrderBook(
                token_id="token-harris",
                asks=[
                    Ask(price=Decimal("0.15"), size=Decimal("1000"), token_id="token-harris"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-other": OrderBook(
                token_id="token-other",
                asks=[
                    Ask(price=Decimal("0.10"), size=Decimal("1000"), token_id="token-other"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        signal = strategy.check_opportunity(market_metadata, order_books)

        assert signal is not None
        assert isinstance(signal, NegRiskSignal)
        assert signal.market_id == "election-winner-2024"
        assert len(signal.opportunities) == 4
        assert signal.estimated_profit > 0
        assert signal.total_payout == Decimal("1.0")  # 1 share * $1 payout

    def test_no_opportunity_when_sum_exceeds_one(self, strategy, market_metadata):
        """Test no opportunity when sum of prices >= 1.0."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.60"), size=Decimal("100"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.40"), size=Decimal("100"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-harris": OrderBook(
                token_id="token-harris",
                asks=[
                    Ask(price=Decimal("0.20"), size=Decimal("100"), token_id="token-harris"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-other": OrderBook(
                token_id="token-other",
                asks=[
                    Ask(price=Decimal("0.10"), size=Decimal("100"), token_id="token-other"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        # Sum = 1.30 > 1.0, no arbitrage possible
        signal = strategy.check_opportunity(market_metadata, order_books)
        assert signal is None

    def test_no_opportunity_with_insufficient_liquidity(self, strategy, market_metadata):
        """Test no opportunity when some tokens have insufficient liquidity."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.01"), size=Decimal("5"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.30"), size=Decimal("100"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-harris": OrderBook(
                token_id="token-harris",
                asks=[
                    Ask(price=Decimal("0.15"), size=Decimal("100"), token_id="token-harris"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-other": OrderBook(
                token_id="token-other",
                asks=[
                    Ask(price=Decimal("0.08"), size=Decimal("100"), token_id="token-other"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        # Trump has very low liquidity, should skip or return None
        signal = strategy.check_opportunity(market_metadata, order_books)
        # Depending on implementation, might return None or signal with partial liquidity
        assert signal is None or not all(opp.vwap_cost == strategy.trade_size for opp in signal.opportunities)

    def test_no_opportunity_with_empty_orderbooks(self, strategy, market_metadata):
        """Test no opportunity when order books are empty."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[],
                bids=[],
                last_update=1234567890,
            ),
            "token-harris": OrderBook(
                token_id="token-harris",
                asks=[],
                bids=[],
                last_update=1234567890,
            ),
            "token-other": OrderBook(
                token_id="token-other",
                asks=[],
                bids=[],
                last_update=1234567890,
            ),
        }

        signal = strategy.check_opportunity(market_metadata, order_books)
        assert signal is None

    def test_no_opportunity_for_binary_market(self, strategy):
        """Test that binary markets are skipped."""
        binary_metadata = MarketMetadata(
            market_id="will-trump-win",
            title="Will Trump Win?",
            question="Will Trump win the 2024 election?",
            outcomes=[
                Outcome(name="Yes", token_id="yes-123", is_yes=True),
                Outcome(name="No", token_id="no-123", is_yes=False),
            ],
            outcome_token_ids=["yes-123", "no-123"],
            is_binary=True,
        )

        order_books = {
            "yes-123": OrderBook(
                token_id="yes-123",
                asks=[
                    Ask(price=Decimal("0.48"), size=Decimal("100"), token_id="yes-123"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "no-123": OrderBook(
                token_id="no-123",
                asks=[
                    Ask(price=Decimal("0.48"), size=Decimal("100"), token_id="no-123"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        signal = strategy.check_opportunity(binary_metadata, order_books)
        # Binary markets should use atomic strategy instead
        assert signal is None

    def test_signal_includes_all_required_fields(self, strategy, market_metadata):
        """Test that signal includes all required fields."""
        order_books = {
            "token-trump": OrderBook(
                token_id="token-trump",
                asks=[
                    Ask(price=Decimal("0.40"), size=Decimal("1000"), token_id="token-trump"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-biden": OrderBook(
                token_id="token-biden",
                asks=[
                    Ask(price=Decimal("0.25"), size=Decimal("1000"), token_id="token-biden"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-harris": OrderBook(
                token_id="token-harris",
                asks=[
                    Ask(price=Decimal("0.15"), size=Decimal("1000"), token_id="token-harris"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-other": OrderBook(
                token_id="token-other",
                asks=[
                    Ask(price=Decimal("0.10"), size=Decimal("1000"), token_id="token-other"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        signal = strategy.check_opportunity(market_metadata, order_books)

        assert signal is not None
        assert signal.market_id == "election-winner-2024"
        assert signal.market_title == "2024 Presidential Election Winner"
        assert len(signal.opportunities) == 4
        assert signal.total_cost > 0
        assert signal.total_payout == Decimal("1.0")
        assert signal.estimated_profit > 0
        assert signal.profit_percentage > 0
        assert signal.gas_cost > 0
        assert signal.fees > 0
        assert isinstance(signal.timestamp, datetime)


class TestEdgeCases:
    """Test suite for edge cases."""

    def test_market_with_many_outcomes(self):
        """Test handling market with many outcomes (10+)."""
        strategy = NegRiskStrategy(
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
        )

        outcomes = [
            Outcome(name=f"Candidate {i}", token_id=f"token-{i}", is_yes=True)
            for i in range(10)
        ]

        market_metadata = MarketMetadata(
            market_id="large-election",
            title="Large Election",
            question="Who will win?",
            outcomes=outcomes,
            outcome_token_ids=[f"token-{i}" for i in range(10)],
            is_binary=False,
        )

        order_books = {
            f"token-{i}": OrderBook(
                token_id=f"token-{i}",
                asks=[
                    Ask(price=Decimal("0.09"), size=Decimal("1000"), token_id=f"token-{i}"),
                ],
                bids=[],
                last_update=1234567890,
            )
            for i in range(10)
        }

        signal = strategy.check_opportunity(market_metadata, order_books)

        # Should handle large markets
        # Sum = 10 * 0.09 = 0.90 < 1.0, profitable
        assert signal is not None
        assert len(signal.opportunities) == 10

    def test_gas_cost_exceeds_profit(self):
        """Test when gas cost exceeds potential profit."""
        strategy = NegRiskStrategy(
            fee_rate=Decimal("0.0035"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
            gas_estimate=Decimal("10.0"),  # Very high gas cost
        )

        market_metadata = MarketMetadata(
            market_id="test-market",
            title="Test",
            question="Test?",
            outcomes=[
                Outcome(name="A", token_id="token-a", is_yes=True),
                Outcome(name="B", token_id="token-b", is_yes=True),
            ],
            outcome_token_ids=["token-a", "token-b"],
            is_binary=False,
        )

        order_books = {
            "token-a": OrderBook(
                token_id="token-a",
                asks=[
                    Ask(price=Decimal("0.49"), size=Decimal("100"), token_id="token-a"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-b": OrderBook(
                token_id="token-b",
                asks=[
                    Ask(price=Decimal("0.49"), size=Decimal("100"), token_id="token-b"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        signal = strategy.check_opportunity(market_metadata, order_books)

        # Gas cost ($10) exceeds profit (~$0.02), should not trade
        assert signal is None

    def test_zero_fees(self):
        """Test strategy with zero fees."""
        strategy = NegRiskStrategy(
            fee_rate=Decimal("0.0"),
            min_profit_threshold=Decimal("0.005"),
            trade_size=Decimal("10.0"),
            gas_estimate=Decimal("0.0"),
        )

        market_metadata = MarketMetadata(
            market_id="test-market",
            title="Test",
            question="Test?",
            outcomes=[
                Outcome(name="A", token_id="token-a", is_yes=True),
                Outcome(name="B", token_id="token-b", is_yes=True),
            ],
            outcome_token_ids=["token-a", "token-b"],
            is_binary=False,
        )

        order_books = {
            "token-a": OrderBook(
                token_id="token-a",
                asks=[
                    Ask(price=Decimal("0.45"), size=Decimal("1000"), token_id="token-a"),
                ],
                bids=[],
                last_update=1234567890,
            ),
            "token-b": OrderBook(
                token_id="token-b",
                asks=[
                    Ask(price=Decimal("0.45"), size=Decimal("1000"), token_id="token-b"),
                ],
                bids=[],
                last_update=1234567890,
            ),
        }

        signal = strategy.check_opportunity(market_metadata, order_books)

        # Should still be profitable even with zero fees
        assert signal is not None
        assert signal.fees == Decimal("0")
