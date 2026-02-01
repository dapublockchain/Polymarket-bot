"""
Polymarket REST API Client

Fetches market data from Polymarket REST API.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class PolymarketAPIClient:
    """Client for Polymarket REST API."""

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Initialize async context."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup async context."""
        if self.session:
            await self.session.close()

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        url = f"{self.base_url}/{endpoint}"

        if not self.session:
            raise RuntimeError("Client not initialized. Use 'async with' statement.")

        try:
            logger.debug(f"API Request: {url}")

            async with self.session.get(url, params=params) as response:
                response.raise_for_status()

                data = await response.json()
                logger.debug(f"API Response: {len(data) if isinstance(data, list) else 'single'} items")

                return data

        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_active_markets(
        self,
        min_volume: Decimal = Decimal("1000"),
        min_liquidity: Decimal = Decimal("1000"),
        max_markets: int = 100,
        closed: bool = False,
        order_by: str = "volume_desc",
    ) -> List[Dict[str, Any]]:
        """
        Get active markets from Polymarket Gamma API.

        Args:
            min_volume: Minimum 24h volume in USDC
            min_liquidity: Minimum liquidity in USDC
            max_markets: Maximum number of markets to return
            closed: Include closed markets
            order_by: Sort order (volume_desc, liquidity_desc, etc)

        Returns:
            List of active markets with token IDs
        """
        try:
            # Build query params
            params = {}
            if not closed:
                params["closed"] = "false"
            if max_markets:
                params["limit"] = str(max_markets * 3)

            # Fetch markets from Gamma API
            markets = await self._get(
                "markets",
                params=params,
            )

            if not isinstance(markets, list):
                logger.warning(f"Unexpected API response type: {type(markets)}")
                return []

            # Filter markets
            active_markets = []
            for market in markets:
                try:
                    # Extract market data
                    volume_24h = Decimal(str(market.get("volume24hr", 0)))
                    liquidity = Decimal(str(market.get("liquidityNum", 0)))

                    # Skip if below thresholds
                    if volume_24h < min_volume:
                        continue
                    if liquidity < min_liquidity:
                        continue

                    # Extract CLOB token IDs
                    import json
                    clob_token_ids_str = market.get("clobTokenIds", "[]")
                    try:
                        clob_token_ids = json.loads(clob_token_ids_str)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(clob_token_ids, list) or len(clob_token_ids) != 2:
                        continue  # Only binary markets (YES/NO)

                    # Extract outcome prices
                    outcome_prices_str = market.get("outcomePrices", "[]")
                    try:
                        outcome_prices = json.loads(outcome_prices_str)
                    except json.JSONDecodeError:
                        outcome_prices = ["0", "0"]

                    # Extract outcomes
                    outcomes_str = market.get("outcomes", "[\"Yes\", \"No\"]")
                    try:
                        outcomes = json.loads(outcomes_str)
                    except json.JSONDecodeError:
                        outcomes = ["Yes", "No"]

                    # First token is YES, second is NO
                    token_id_yes = clob_token_ids[0] if len(clob_token_ids) > 0 else None
                    token_id_no = clob_token_ids[1] if len(clob_token_ids) > 1 else None

                    if not token_id_yes or not token_id_no:
                        continue

                    # Parse prices
                    try:
                        yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.0
                        no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.0
                    except (ValueError, IndexError):
                        yes_price = 0.0
                        no_price = 0.0

                    # Build market info
                    market_info = {
                        "market_id": market.get("id"),
                        "question": market.get("question", ""),
                        "description": market.get("description", ""),
                        "slug": market.get("slug", ""),
                        "token_id_yes": token_id_yes,
                        "token_id_no": token_id_no,
                        "condition_id": market.get("conditionId", ""),
                        "end_date": market.get("endDate", ""),
                        "category": market.get("category", ""),
                        "volume_24h": float(volume_24h),
                        "liquidity": float(liquidity),
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "active": market.get("active", True),
                        "closed": market.get("closed", False),
                    }

                    active_markets.append(market_info)

                    # Stop if we have enough
                    if len(active_markets) >= max_markets:
                        break

                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                    logger.warning(f"Error processing market {market.get('id', 'unknown')}: {e}")
                    continue

            logger.info(f"Retrieved {len(active_markets)} active markets (min_volume: {min_volume})")
            return active_markets

        except Exception as e:
            logger.error(f"Failed to fetch active markets: {e}")
            return []

    async def get_market_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order book for a specific token.

        Args:
            token_id: Token ID to fetch order book for

        Returns:
            Order book data with bids and asks
        """
        try:
            data = await self._get(f"market/{token_id}/book")

            # Validate response
            if not data or not isinstance(data, dict):
                return None

            # Extract order book
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            return {
                "token_id": token_id,
                "bids": bids,
                "asks": asks,
                "last_updated": data.get("last_updated"),
            }

        except Exception as e:
            logger.error(f"Failed to fetch order book for {token_id}: {e}")
            return None

    async def validate_token(self, token_id: str) -> bool:
        """
        Validate if a token ID is active and valid.

        Args:
            token_id: Token ID to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            orderbook = await self.get_market_orderbook(token_id)
            return orderbook is not None

        except Exception:
            return False


async def main():
    """Test the API client."""
    async with PolymarketAPIClient() as client:
        # Fetch active markets
        markets = await client.get_active_markets(
            min_volume=Decimal("1000"),
            max_markets=10,
        )

        print(f"\n✅ Found {len(markets)} active markets:\n")

        for i, market in enumerate(markets[:5], 1):
            print(f"{i}. {market['question'][:60]}...")
            print(f"   YES Token: {market['token_id_yes'][:20]}...")
            print(f"   NO Token:  {market['token_id_no'][:20]}...")
            print(f"   Volume: ${market['volume_24h']:,.2f}")
            print(f"   YES Price: {market['yes_price']:.4f}")
            print(f"   NO Price:  {market['no_price']:.4f}")
            print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
