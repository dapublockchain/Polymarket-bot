"""
Unit tests for NegRisk-related data models.

Tests are written FIRST (TDD methodology).
"""
import pytest
from decimal import Decimal
from datetime import datetime

from src.core.models import (
    Outcome,
    MarketMetadata,
    VWAPResult,
    TokenOpportunity,
    NegRiskSignal,
)


class TestOutcome:
    """Test suite for Outcome model."""

    def test_create_outcome_valid(self):
        """Test creating a valid outcome."""
        outcome = Outcome(
            name="Trump",
            token_id="token-trump",
            is_yes=True,
        )
        assert outcome.name == "Trump"
        assert outcome.token_id == "token-trump"
        assert outcome.is_yes is True

    def test_create_outcome_no_token(self):
        """Test creating an outcome for NO token."""
        outcome = Outcome(
            name="Not Trump",
            token_id="token-not-trump",
            is_yes=False,
        )
        assert outcome.is_yes is False


class TestMarketMetadata:
    """Test suite for MarketMetadata model."""

    def test_create_binary_market_metadata(self):
        """Test creating metadata for binary market."""
        outcomes = [
            Outcome(name="Yes", token_id="yes-123", is_yes=True),
            Outcome(name="No", token_id="no-123", is_yes=False),
        ]
        metadata = MarketMetadata(
            market_id="market-123",
            title="Will Trump win?",
            question="Will Trump win the 2024 election?",
            outcomes=outcomes,
            outcome_token_ids=["yes-123", "no-123"],
            is_binary=True,
        )
        assert metadata.market_id == "market-123"
        assert metadata.is_binary is True
        assert len(metadata.outcomes) == 2

    def test_create_multi_outcome_market_metadata(self):
        """Test creating metadata for multi-outcome market."""
        outcomes = [
            Outcome(name="Trump", token_id="token-trump", is_yes=True),
            Outcome(name="Biden", token_id="token-biden", is_yes=True),
            Outcome(name="Harris", token_id="token-harris", is_yes=True),
            Outcome(name="Other", token_id="token-other", is_yes=True),
        ]
        metadata = MarketMetadata(
            market_id="election-winner-2024",
            title="2024 Presidential Election Winner",
            question="Who will win the 2024 US Presidential Election?",
            outcomes=outcomes,
            outcome_token_ids=["token-trump", "token-biden", "token-harris", "token-other"],
            is_binary=False,
        )
        assert metadata.market_id == "election-winner-2024"
        assert metadata.is_binary is False
        assert len(metadata.outcomes) == 4

    def test_validate_token_ids_match_outcomes(self):
        """Test validation that token IDs match outcomes."""
        outcomes = [
            Outcome(name="Trump", token_id="token-trump", is_yes=True),
            Outcome(name="Biden", token_id="token-biden", is_yes=True),
        ]
        with pytest.raises(ValueError, match="Number of token IDs must match"):
            MarketMetadata(
                market_id="market-123",
                title="Test Market",
                question="Test question?",
                outcomes=outcomes,
                outcome_token_ids=["token-trump"],  # Only 1 token for 2 outcomes
                is_binary=False,
            )

    def test_market_metadata_with_end_date(self):
        """Test market metadata with end date."""
        outcomes = [
            Outcome(name="Yes", token_id="yes-123", is_yes=True),
            Outcome(name="No", token_id="no-123", is_yes=False),
        ]
        end_date = datetime(2024, 11, 5, 23, 59, 59)
        metadata = MarketMetadata(
            market_id="market-123",
            title="Test Market",
            question="Test question?",
            outcomes=outcomes,
            outcome_token_ids=["yes-123", "no-123"],
            is_binary=True,
            end_date=end_date,
        )
        assert metadata.end_date == end_date

    def test_market_metadata_default_timestamp(self):
        """Test that last_fetched timestamp is set by default."""
        outcomes = [
            Outcome(name="Yes", token_id="yes-123", is_yes=True),
            Outcome(name="No", token_id="no-123", is_yes=False),
        ]
        metadata = MarketMetadata(
            market_id="market-123",
            title="Test Market",
            question="Test question?",
            outcomes=outcomes,
            outcome_token_ids=["yes-123", "no-123"],
            is_binary=True,
        )
        assert metadata.last_fetched > 0
        assert metadata.last_fetched <= int(datetime.now().timestamp() * 1000)


class TestVWAPResult:
    """Test suite for VWAPResult model."""

    def test_create_vwap_result_valid(self):
        """Test creating a valid VWAP result."""
        result = VWAPResult(
            token_id="token-trump",
            vwap_price=Decimal("0.45"),
            vwap_cost=Decimal("10.00"),
            shares=Decimal("22.22"),
            trade_size=Decimal("10.00"),
            filled=True,
        )
        assert result.token_id == "token-trump"
        assert result.vwap_price == Decimal("0.45")
        assert result.filled is True

    def test_validate_vwap_price_non_negative(self):
        """Test that VWAP price cannot be negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            VWAPResult(
                token_id="token-trump",
                vwap_price=Decimal("-0.45"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("22.22"),
                trade_size=Decimal("10.00"),
                filled=True,
            )

    def test_validate_vwap_cost_non_negative(self):
        """Test that VWAP cost cannot be negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            VWAPResult(
                token_id="token-trump",
                vwap_price=Decimal("0.45"),
                vwap_cost=Decimal("-10.00"),
                shares=Decimal("22.22"),
                trade_size=Decimal("10.00"),
                filled=True,
            )

    def test_validate_shares_non_negative(self):
        """Test that shares cannot be negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            VWAPResult(
                token_id="token-trump",
                vwap_price=Decimal("0.45"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("-22.22"),
                trade_size=Decimal("10.00"),
                filled=True,
            )

    def test_vwap_result_zero_allowed(self):
        """Test that zero values are allowed."""
        result = VWAPResult(
            token_id="token-trump",
            vwap_price=Decimal("0"),
            vwap_cost=Decimal("0"),
            shares=Decimal("0"),
            trade_size=Decimal("0"),
            filled=False,
        )
        assert result.vwap_price == Decimal("0")
        assert result.shares == Decimal("0")


class TestTokenOpportunity:
    """Test suite for TokenOpportunity model."""

    def test_create_token_opportunity_valid(self):
        """Test creating a valid token opportunity."""
        opportunity = TokenOpportunity(
            token_id="token-trump",
            outcome_name="Trump",
            yes_price=Decimal("0.45"),
            vwap_cost=Decimal("10.00"),
            shares=Decimal("22.22"),
        )
        assert opportunity.token_id == "token-trump"
        assert opportunity.outcome_name == "Trump"
        assert opportunity.yes_price == Decimal("0.45")

    def test_validate_yes_price_positive(self):
        """Test that YES price must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            TokenOpportunity(
                token_id="token-trump",
                outcome_name="Trump",
                yes_price=Decimal("0"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("22.22"),
            )

    def test_validate_vwap_cost_positive(self):
        """Test that VWAP cost must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            TokenOpportunity(
                token_id="token-trump",
                outcome_name="Trump",
                yes_price=Decimal("0.45"),
                vwap_cost=Decimal("0"),
                shares=Decimal("22.22"),
            )

    def test_validate_shares_positive(self):
        """Test that shares must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            TokenOpportunity(
                token_id="token-trump",
                outcome_name="Trump",
                yes_price=Decimal("0.45"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("0"),
            )


class TestNegRiskSignal:
    """Test suite for NegRiskSignal model."""

    @pytest.fixture
    def sample_opportunities(self):
        """Create sample token opportunities."""
        return [
            TokenOpportunity(
                token_id="token-trump",
                outcome_name="Trump",
                yes_price=Decimal("0.45"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("22.22"),
            ),
            TokenOpportunity(
                token_id="token-biden",
                outcome_name="Biden",
                yes_price=Decimal("0.30"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("33.33"),
            ),
            TokenOpportunity(
                token_id="token-harris",
                outcome_name="Harris",
                yes_price=Decimal("0.15"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("66.67"),
            ),
            TokenOpportunity(
                token_id="token-other",
                outcome_name="Other",
                yes_price=Decimal("0.08"),
                vwap_cost=Decimal("10.00"),
                shares=Decimal("125.00"),
            ),
        ]

    def test_create_negrisk_signal_valid(self, sample_opportunities):
        """Test creating a valid NegRisk signal."""
        signal = NegRiskSignal(
            market_id="election-winner-2024",
            market_title="2024 Presidential Election Winner",
            opportunities=sample_opportunities,
            total_cost=Decimal("38.40"),
            total_payout=Decimal("40.00"),
            estimated_profit=Decimal("1.60"),
            profit_percentage=Decimal("0.0417"),
            gas_cost=Decimal("0.10"),
            fees=Decimal("0.50"),
        )
        assert signal.market_id == "election-winner-2024"
        assert len(signal.opportunities) == 4
        assert signal.estimated_profit == Decimal("1.60")

    def test_validate_at_least_two_opportunities(self):
        """Test that NegRisk requires at least 2 opportunities."""
        # Pydantic's built-in min_length validation runs first
        with pytest.raises(Exception):  # Pydantic ValidationError
            NegRiskSignal(
                market_id="market-123",
                market_title="Test Market",
                opportunities=[
                    TokenOpportunity(
                        token_id="token-trump",
                        outcome_name="Trump",
                        yes_price=Decimal("0.45"),
                        vwap_cost=Decimal("10.00"),
                        shares=Decimal("22.22"),
                    )
                ],
                total_cost=Decimal("10.00"),
                total_payout=Decimal("10.00"),
                estimated_profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("0"),
                fees=Decimal("0"),
            )

    def test_validate_total_cost_non_negative(self, sample_opportunities):
        """Test that total cost cannot be negative."""
        with pytest.raises(ValueError, match="Costs cannot be negative"):
            NegRiskSignal(
                market_id="market-123",
                market_title="Test Market",
                opportunities=sample_opportunities,
                total_cost=Decimal("-10.00"),
                total_payout=Decimal("10.00"),
                estimated_profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("0"),
                fees=Decimal("0"),
            )

    def test_validate_gas_cost_non_negative(self, sample_opportunities):
        """Test that gas cost cannot be negative."""
        with pytest.raises(ValueError, match="Costs cannot be negative"):
            NegRiskSignal(
                market_id="market-123",
                market_title="Test Market",
                opportunities=sample_opportunities,
                total_cost=Decimal("10.00"),
                total_payout=Decimal("10.00"),
                estimated_profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("-0.10"),
                fees=Decimal("0"),
            )

    def test_validate_fees_non_negative(self, sample_opportunities):
        """Test that fees cannot be negative."""
        with pytest.raises(ValueError, match="Costs cannot be negative"):
            NegRiskSignal(
                market_id="market-123",
                market_title="Test Market",
                opportunities=sample_opportunities,
                total_cost=Decimal("10.00"),
                total_payout=Decimal("10.00"),
                estimated_profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("0"),
                fees=Decimal("-0.50"),
            )

    def test_negative_profit_allowed(self, sample_opportunities):
        """Test that negative profit is allowed (no opportunity)."""
        signal = NegRiskSignal(
            market_id="market-123",
            market_title="Test Market",
            opportunities=sample_opportunities,
            total_cost=Decimal("42.00"),
            total_payout=Decimal("40.00"),
            estimated_profit=Decimal("-2.00"),
            profit_percentage=Decimal("-0.0476"),
            gas_cost=Decimal("0.10"),
            fees=Decimal("0.50"),
        )
        assert signal.estimated_profit == Decimal("-2.00")

    def test_default_timestamp(self, sample_opportunities):
        """Test that timestamp is set by default."""
        signal = NegRiskSignal(
            market_id="market-123",
            market_title="Test Market",
            opportunities=sample_opportunities,
            total_cost=Decimal("38.40"),
            total_payout=Decimal("40.00"),
            estimated_profit=Decimal("1.60"),
            profit_percentage=Decimal("0.0417"),
            gas_cost=Decimal("0.10"),
            fees=Decimal("0.50"),
        )
        assert signal.timestamp is not None
        assert isinstance(signal.timestamp, datetime)

    def test_zero_costs_allowed(self, sample_opportunities):
        """Test that zero costs are allowed."""
        signal = NegRiskSignal(
            market_id="market-123",
            market_title="Test Market",
            opportunities=sample_opportunities,
            total_cost=Decimal("0"),
            total_payout=Decimal("0"),
            estimated_profit=Decimal("0"),
            profit_percentage=Decimal("0"),
            gas_cost=Decimal("0"),
            fees=Decimal("0"),
        )
        assert signal.total_cost == Decimal("0")
        assert signal.gas_cost == Decimal("0")
        assert signal.fees == Decimal("0")
