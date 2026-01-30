"""
Market Grouper - Groups related outcome tokens by market.

This module handles fetching market metadata from Polymarket and grouping
tokens that belong to the same market (e.g., all outcomes in an election).
"""
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp

from src.core.models import Outcome, MarketMetadata


class MarketGrouper:
    """
    Groups tokens by market and fetches market metadata.

    This class is responsible for:
    - Fetching market metadata from Polymarket API
    - Caching metadata to avoid repeated API calls
    - Grouping tokens by their market_id
    - Identifying binary vs multi-outcome markets
    """

    def __init__(self, polymarket_api_url: str = "https://api.polymarket.com"):
        """
        Initialize the market grouper.

        Args:
            polymarket_api_url: Base URL for Polymarket API
        """
        self.polymarket_api_url = polymarket_api_url
        self.market_cache: Dict[str, MarketMetadata] = {}
        self.token_to_market_cache: Dict[str, str] = {}

    def get_cached_markets(self) -> Dict[str, MarketMetadata]:
        """
        Get all cached market metadata.

        Returns:
            Dictionary mapping market_id to MarketMetadata
        """
        return self.market_cache.copy()

    async def fetch_market_metadata(self, token_id: str) -> MarketMetadata:
        """
        Fetch market metadata for a given token.

        Args:
            token_id: Token identifier

        Returns:
            MarketMetadata object

        Raises:
            Exception: If API request fails
        """
        # Check if token is in cache
        if token_id in self.token_to_market_cache:
            market_id = self.token_to_market_cache[token_id]
            if market_id in self.market_cache:
                return self.market_cache[market_id]

        # Fetch from Polymarket API
        url = f"{self.polymarket_api_url}/tokens/{token_id}/market"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to fetch market metadata: HTTP {response.status}"
                        )

                    data = await response.json()
        except Exception as e:
            raise Exception(f"Failed to fetch market metadata: {e}")

        # Parse outcomes
        outcomes_data = data.get("outcomes", [])
        outcomes = [
            Outcome(
                name=outcome["name"],
                token_id=outcome["token_id"],
                is_yes=outcome.get("is_yes", True),
            )
            for outcome in outcomes_data
        ]

        # Parse end date
        end_date = None
        if "end_date" in data:
            try:
                end_date = datetime.fromisoformat(data["end_date"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Create market metadata
        metadata = MarketMetadata(
            market_id=data["market_id"],
            title=data["title"],
            question=data["question"],
            outcomes=outcomes,
            outcome_token_ids=data["outcome_token_ids"],
            is_binary=len(outcomes) == 2,
            end_date=end_date,
        )

        # Cache the metadata
        self.market_cache[metadata.market_id] = metadata

        # Cache token -> market mapping for all tokens in this market
        for token_id_in_market in metadata.outcome_token_ids:
            self.token_to_market_cache[token_id_in_market] = metadata.market_id

        return metadata

    async def group_tokens_by_market(
        self, token_ids: List[str]
    ) -> Dict[str, List[str]]:
        """
        Group tokens by their market_id.

        Args:
            token_ids: List of token identifiers

        Returns:
            Dictionary mapping market_id to list of token_ids
        """
        if not token_ids:
            return {}

        groups: Dict[str, List[str]] = {}

        for token_id in token_ids:
            try:
                metadata = await self.fetch_market_metadata(token_id)
                market_id = metadata.market_id

                if market_id not in groups:
                    groups[market_id] = []

                # Add token to group if not already present
                if token_id not in groups[market_id]:
                    groups[market_id].append(token_id)

            except Exception as e:
                # Skip tokens that fail to fetch
                # Log warning in production
                continue

        return groups

    async def is_multi_outcome_market(self, token_id: str) -> bool:
        """
        Check if a token belongs to a multi-outcome market.

        Args:
            token_id: Token identifier

        Returns:
            True if market has 3+ outcomes, False if binary (2 outcomes)
        """
        metadata = await self.fetch_market_metadata(token_id)
        return not metadata.is_binary

    async def get_market_outcomes(self, token_id: str) -> List[Outcome]:
        """
        Get all outcomes for the market containing this token.

        Args:
            token_id: Token identifier

        Returns:
            List of Outcome objects
        """
        metadata = await self.fetch_market_metadata(token_id)
        return metadata.outcomes
