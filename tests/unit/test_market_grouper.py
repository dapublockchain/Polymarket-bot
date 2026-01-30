"""
Unit tests for Market Grouper.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from src.core.models import Outcome, MarketMetadata
from src.strategies.market_grouper import MarketGrouper


def create_mock_async_response(data: Dict[str, Any], status: int = 200):
    """Helper to create a mock async HTTP response."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=data)

    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx_mgr.__aexit__ = AsyncMock()

    return mock_ctx_mgr


class TestMarketGrouperInit:
    """Test suite for MarketGrouper initialization."""

    def test_init_with_default_url(self):
        """Test initialization with default Polymarket API URL."""
        grouper = MarketGrouper()
        assert grouper.polymarket_api_url == "https://api.polymarket.com"

    def test_init_with_custom_url(self):
        """Test initialization with custom API URL."""
        custom_url = "https://custom-api.example.com"
        grouper = MarketGrouper(polymarket_api_url=custom_url)
        assert grouper.polymarket_api_url == custom_url

    def test_init_creates_empty_cache(self):
        """Test that initialization creates empty market cache."""
        grouper = MarketGrouper()
        assert grouper.get_cached_markets() == {}


class TestFetchMarketMetadata:
    """Test suite for fetching market metadata."""

    @pytest.fixture
    def grouper(self):
        """Create a market grouper for testing."""
        return MarketGrouper()

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_success(self, grouper):
        """Test successfully fetching market metadata."""
        token_id = "token-trump-12345"

        mock_response = create_mock_async_response(
            {
                "market_id": "election-winner-2024",
                "title": "2024 Presidential Election Winner",
                "question": "Who will win the 2024 US Presidential Election?",
                "outcomes": [
                    {"name": "Trump", "token_id": "token-trump", "is_yes": True},
                    {"name": "Biden", "token_id": "token-biden", "is_yes": True},
                    {"name": "Harris", "token_id": "token-harris", "is_yes": True},
                    {"name": "Other", "token_id": "token-other", "is_yes": True},
                ],
                "outcome_token_ids": [
                    "token-trump",
                    "token-biden",
                    "token-harris",
                    "token-other",
                ],
                "end_date": "2024-11-05T23:59:59Z",
            }
        )

        with patch("aiohttp.ClientSession.get", return_value=mock_response):
            metadata = await grouper.fetch_market_metadata(token_id)

        assert metadata.market_id == "election-winner-2024"
        assert metadata.title == "2024 Presidential Election Winner"
        assert len(metadata.outcomes) == 4
        assert metadata.is_binary is False
        assert metadata.end_date is not None

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_binary_market(self, grouper):
        """Test fetching metadata for binary market."""
        token_id = "yes-12345"

        mock_response = create_mock_async_response(
            {
                "market_id": "will-trump-win",
                "title": "Will Trump Win?",
                "question": "Will Trump win the 2024 election?",
                "outcomes": [
                    {"name": "Yes", "token_id": "yes-12345", "is_yes": True},
                    {"name": "No", "token_id": "no-12345", "is_yes": False},
                ],
                "outcome_token_ids": ["yes-12345", "no-12345"],
            }
        )

        with patch("aiohttp.ClientSession.get", return_value=mock_response):
            metadata = await grouper.fetch_market_metadata(token_id)

        assert metadata.market_id == "will-trump-win"
        assert metadata.is_binary is True
        assert len(metadata.outcomes) == 2

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_caches_result(self, grouper):
        """Test that fetched metadata is cached."""
        token_id = "token-trump-12345"

        mock_response = create_mock_async_response(
            {
                "market_id": "election-winner-2024",
                "title": "2024 Presidential Election Winner",
                "question": "Who will win the 2024 US Presidential Election?",
                "outcomes": [
                    {"name": "Trump", "token_id": "token-trump", "is_yes": True},
                    {"name": "Biden", "token_id": "token-biden", "is_yes": True},
                ],
                "outcome_token_ids": ["token-trump", "token-biden"],
            }
        )

        with patch("aiohttp.ClientSession.get", return_value=mock_response):
            metadata1 = await grouper.fetch_market_metadata(token_id)
            cache_after_first = grouper.get_cached_markets()

            # Should be cached now
            assert "election-winner-2024" in cache_after_first

            # Fetch again - should use cache
            metadata2 = await grouper.fetch_market_metadata(token_id)

        assert metadata1.market_id == metadata2.market_id
        assert len(grouper.get_cached_markets()) == 1

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_api_error(self, grouper):
        """Test handling of API errors."""
        token_id = "invalid-token"

        mock_response = Mock()
        mock_response.status = 404

        with patch("aiohttp.ClientSession.get", return_value=mock_response):
            with pytest.raises(Exception, match="Failed to fetch market metadata"):
                await grouper.fetch_market_metadata(token_id)

    @pytest.mark.asyncio
    async def test_fetch_market_metadata_network_error(self, grouper):
        """Test handling of network errors."""
        token_id = "token-trump"

        with patch("aiohttp.ClientSession.get", side_effect=Exception("Network error")):
            with pytest.raises(Exception, match="Network error"):
                await grouper.fetch_market_metadata(token_id)


class TestGroupTokensByMarket:
    """Test suite for grouping tokens by market."""

    @pytest.fixture
    def grouper(self):
        """Create a market grouper for testing."""
        return MarketGrouper()

    @pytest.mark.asyncio
    async def test_group_tokens_by_market_single_market(self, grouper):
        """Test grouping tokens from a single market."""
        token_ids = ["token-trump", "token-biden", "token-harris", "token-other"]

        # Mock fetch_market_metadata to return market data
        async def mock_fetch_metadata(token_id):
            return MarketMetadata(
                market_id="election-winner-2024",
                title="2024 Presidential Election Winner",
                question="Who will win?",
                outcomes=[
                    Outcome(name="Trump", token_id="token-trump", is_yes=True),
                    Outcome(name="Biden", token_id="token-biden", is_yes=True),
                    Outcome(name="Harris", token_id="token-harris", is_yes=True),
                    Outcome(name="Other", token_id="token-other", is_yes=True),
                ],
                outcome_token_ids=["token-trump", "token-biden", "token-harris", "token-other"],
                is_binary=False,
            )

        grouper.fetch_market_metadata = AsyncMock(side_effect=mock_fetch_metadata)

        groups = await grouper.group_tokens_by_market(token_ids)

        assert len(groups) == 1
        assert "election-winner-2024" in groups
        assert len(groups["election-winner-2024"]) == 4

    @pytest.mark.asyncio
    async def test_group_tokens_by_market_multiple_markets(self, grouper):
        """Test grouping tokens from multiple markets."""
        token_ids = [
            "token-trump",  # Market 1
            "token-biden",  # Market 1
            "yes-123",  # Market 2
            "no-123",  # Market 2
        ]

        async def mock_fetch_metadata(token_id):
            if token_id in ["token-trump", "token-biden"]:
                return MarketMetadata(
                    market_id="market-1",
                    title="Market 1",
                    question="Question 1?",
                    outcomes=[
                        Outcome(name="Trump", token_id="token-trump", is_yes=True),
                        Outcome(name="Biden", token_id="token-biden", is_yes=True),
                    ],
                    outcome_token_ids=["token-trump", "token-biden"],
                    is_binary=False,
                )
            else:
                return MarketMetadata(
                    market_id="market-2",
                    title="Market 2",
                    question="Question 2?",
                    outcomes=[
                        Outcome(name="Yes", token_id="yes-123", is_yes=True),
                        Outcome(name="No", token_id="no-123", is_yes=False),
                    ],
                    outcome_token_ids=["yes-123", "no-123"],
                    is_binary=True,
                )

        grouper.fetch_market_metadata = AsyncMock(side_effect=mock_fetch_metadata)

        groups = await grouper.group_tokens_by_market(token_ids)

        assert len(groups) == 2
        assert "market-1" in groups
        assert "market-2" in groups
        assert len(groups["market-1"]) == 2
        assert len(groups["market-2"]) == 2

    @pytest.mark.asyncio
    async def test_group_tokens_by_market_empty_list(self, grouper):
        """Test grouping with empty token list."""
        groups = await grouper.group_tokens_by_market([])
        assert groups == {}

    @pytest.mark.asyncio
    async def test_group_tokens_by_market_uses_cache(self, grouper):
        """Test that grouping uses cached metadata when available."""
        token_ids = ["token-trump", "token-biden"]

        # Pre-populate cache
        cached_metadata = MarketMetadata(
            market_id="cached-market",
            title="Cached Market",
            question="Cached?",
            outcomes=[
                Outcome(name="Trump", token_id="token-trump", is_yes=True),
                Outcome(name="Biden", token_id="token-biden", is_yes=True),
            ],
            outcome_token_ids=["token-trump", "token-biden"],
            is_binary=False,
        )

        # Manually add to cache
        grouper.market_cache["cached-market"] = cached_metadata
        grouper.token_to_market_cache["token-trump"] = "cached-market"
        grouper.token_to_market_cache["token-biden"] = "cached-market"

        # Track HTTP calls (should not be called when using cache)
        with patch("aiohttp.ClientSession.get") as mock_get:
            groups = await grouper.group_tokens_by_market(token_ids)

            # Should use cache, not make HTTP calls
            mock_get.assert_not_called()

        assert len(groups) == 1
        assert "cached-market" in groups


class TestIsMultiOutcomeMarket:
    """Test suite for checking if market is multi-outcome."""

    @pytest.fixture
    def grouper(self):
        """Create a market grouper for testing."""
        return MarketGrouper()

    @pytest.mark.asyncio
    async def test_is_multi_outcome_market_true(self, grouper):
        """Test detecting multi-outcome market."""
        market_metadata = MarketMetadata(
            market_id="election-winner",
            title="Election Winner",
            question="Who will win?",
            outcomes=[
                Outcome(name="A", token_id="token-a", is_yes=True),
                Outcome(name="B", token_id="token-b", is_yes=True),
                Outcome(name="C", token_id="token-c", is_yes=True),
            ],
            outcome_token_ids=["token-a", "token-b", "token-c"],
            is_binary=False,
        )

        # Mock fetch to return this metadata
        grouper.fetch_market_metadata = AsyncMock(return_value=market_metadata)

        is_multi = await grouper.is_multi_outcome_market("token-a")
        assert is_multi is True

    @pytest.mark.asyncio
    async def test_is_multi_outcome_market_false_binary(self, grouper):
        """Test detecting binary market."""
        market_metadata = MarketMetadata(
            market_id="binary-market",
            title="Binary Market",
            question="Yes or No?",
            outcomes=[
                Outcome(name="Yes", token_id="yes-123", is_yes=True),
                Outcome(name="No", token_id="no-123", is_yes=False),
            ],
            outcome_token_ids=["yes-123", "no-123"],
            is_binary=True,
        )

        grouper.fetch_market_metadata = AsyncMock(return_value=market_metadata)

        is_multi = await grouper.is_multi_outcome_market("yes-123")
        assert is_multi is False

    @pytest.mark.asyncio
    async def test_is_multi_outcome_market_uses_cache(self, grouper):
        """Test that check uses cached metadata."""
        # Pre-populate cache
        market_metadata = MarketMetadata(
            market_id="cached-market",
            title="Cached",
            question="Cached?",
            outcomes=[
                Outcome(name="A", token_id="token-a", is_yes=True),
                Outcome(name="B", token_id="token-b", is_yes=True),
            ],
            outcome_token_ids=["token-a", "token-b"],
            is_binary=True,
        )

        grouper.market_cache["cached-market"] = market_metadata
        grouper.token_to_market_cache["token-a"] = "cached-market"

        # Track HTTP calls (should not be called when using cache)
        with patch("aiohttp.ClientSession.get") as mock_get:
            is_multi = await grouper.is_multi_outcome_market("token-a")

            # Should use cache, not make HTTP calls
            mock_get.assert_not_called()

        assert is_multi is False


class TestGetMarketOutcomes:
    """Test suite for getting market outcomes."""

    @pytest.fixture
    def grouper(self):
        """Create a market grouper for testing."""
        return MarketGrouper()

    @pytest.mark.asyncio
    async def test_get_market_outcomes_success(self, grouper):
        """Test getting outcomes for a market."""
        market_metadata = MarketMetadata(
            market_id="election-winner",
            title="Election Winner",
            question="Who will win?",
            outcomes=[
                Outcome(name="Trump", token_id="token-trump", is_yes=True),
                Outcome(name="Biden", token_id="token-biden", is_yes=True),
                Outcome(name="Harris", token_id="token-harris", is_yes=True),
            ],
            outcome_token_ids=["token-trump", "token-biden", "token-harris"],
            is_binary=False,
        )

        grouper.fetch_market_metadata = AsyncMock(return_value=market_metadata)

        outcomes = await grouper.get_market_outcomes("token-trump")

        assert len(outcomes) == 3
        assert outcomes[0].name == "Trump"
        assert outcomes[1].name == "Biden"
        assert outcomes[2].name == "Harris"

    @pytest.mark.asyncio
    async def test_get_market_outcomes_from_cache(self, grouper):
        """Test getting outcomes from cache."""
        market_metadata = MarketMetadata(
            market_id="cached-market",
            title="Cached",
            question="Cached?",
            outcomes=[
                Outcome(name="A", token_id="token-a", is_yes=True),
                Outcome(name="B", token_id="token-b", is_yes=True),
            ],
            outcome_token_ids=["token-a", "token-b"],
            is_binary=True,
        )

        grouper.market_cache["cached-market"] = market_metadata
        grouper.token_to_market_cache["token-a"] = "cached-market"

        # Track HTTP calls (should not be called when using cache)
        with patch("aiohttp.ClientSession.get") as mock_get:
            outcomes = await grouper.get_market_outcomes("token-a")

            # Should use cache, not make HTTP calls
            mock_get.assert_not_called()

        assert len(outcomes) == 2


class TestGetCachedMarkets:
    """Test suite for getting cached markets."""

    def test_get_cached_markets_empty(self):
        """Test getting cached markets when cache is empty."""
        grouper = MarketGrouper()
        cached = grouper.get_cached_markets()
        assert cached == {}

    def test_get_cached_markets_with_data(self):
        """Test getting cached markets with data."""
        grouper = MarketGrouper()

        # Add some data to cache
        metadata = MarketMetadata(
            market_id="test-market",
            title="Test",
            question="Test?",
            outcomes=[Outcome(name="A", token_id="token-a", is_yes=True)],
            outcome_token_ids=["token-a"],
            is_binary=True,
        )

        grouper.market_cache["test-market"] = metadata

        cached = grouper.get_cached_markets()
        assert "test-market" in cached
        assert cached["test-market"].market_id == "test-market"


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.fixture
    def grouper(self):
        """Create a market grouper for testing."""
        return MarketGrouper()

    @pytest.mark.asyncio
    async def test_market_with_many_outcomes(self, grouper):
        """Test handling market with many outcomes (10+)."""
        outcomes = [
            Outcome(name=f"Candidate {i}", token_id=f"token-{i}", is_yes=True)
            for i in range(10)
        ]

        market_metadata = MarketMetadata(
            market_id="large-market",
            title="Large Market",
            question="Large?",
            outcomes=outcomes,
            outcome_token_ids=[f"token-{i}" for i in range(10)],
            is_binary=False,
        )

        grouper.fetch_market_metadata = AsyncMock(return_value=market_metadata)

        is_multi = await grouper.is_multi_outcome_market("token-0")
        assert is_multi is True

    @pytest.mark.asyncio
    async def test_duplicate_token_ids(self, grouper):
        """Test handling duplicate token IDs in input."""
        token_ids = ["token-trump", "token-trump", "token-biden"]

        async def mock_fetch_metadata(token_id):
            return MarketMetadata(
                market_id="election-winner",
                title="Election",
                question="Who?",
                outcomes=[
                    Outcome(name="Trump", token_id="token-trump", is_yes=True),
                    Outcome(name="Biden", token_id="token-biden", is_yes=True),
                ],
                outcome_token_ids=["token-trump", "token-biden"],
                is_binary=False,
            )

        grouper.fetch_market_metadata = AsyncMock(side_effect=mock_fetch_metadata)

        groups = await grouper.group_tokens_by_market(token_ids)

        # Should handle duplicates gracefully
        assert len(groups) == 1
        assert "election-winner" in groups
