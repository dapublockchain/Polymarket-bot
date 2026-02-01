#!/usr/bin/env python3
"""
Fetch and save active Polymarket markets.

This script fetches active markets from the Polymarket API
and saves them to a JSON file for use by the trading bot.
"""
import asyncio
import json
import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.polymarket_api import PolymarketAPIClient
from loguru import logger


async def fetch_and_save_markets(
    output_path: str = "data/active_markets.json",
    min_volume: float = 1000.0,
    max_markets: int = 100,
):
    """
    Fetch active markets and save to JSON file.

    Args:
        output_path: Path to save markets JSON
        min_volume: Minimum 24h volume in USDC
        max_markets: Maximum number of markets to fetch
    """
    logger.info(f"Fetching active markets from Polymarket...")
    logger.info(f"Parameters: min_volume=${min_volume}, max_markets={max_markets}")

    try:
        async with PolymarketAPIClient() as client:
            # Fetch markets
            markets = await client.get_active_markets(
                min_volume=Decimal(str(min_volume)),
                max_markets=max_markets,
                closed=False,  # Only open markets
            )

            if not markets:
                logger.error("No markets found!")
                return False

            logger.info(f"Successfully fetched {len(markets)} markets")

            # Create output directory if needed
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Save to JSON
            with open(output_file, 'w') as f:
                json.dump(markets, f, indent=2)

            logger.success(f"✅ Saved {len(markets)} markets to {output_path}")

            # Print summary
            total_volume = sum(m['volume_24h'] for m in markets)
            total_liquidity = sum(m['liquidity'] for m in markets)

            print("\n" + "="*60)
            print("📊 Market Summary")
            print("="*60)
            print(f"Total Markets: {len(markets)}")
            print(f"Total Volume (24h): ${total_volume:,.2f}")
            print(f"Total Liquidity: ${total_liquidity:,.2f}")
            print(f"Avg Volume per Market: ${total_volume/len(markets):,.2f}")
            print(f"Avg Liquidity per Market: ${total_liquidity/len(markets):,.2f}")

            print("\n" + "="*60)
            print("🔝 Top 10 Markets by Volume")
            print("="*60)

            top_markets = sorted(markets, key=lambda x: x['volume_24h'], reverse=True)[:10]

            for i, m in enumerate(top_markets, 1):
                print(f"\n{i}. {m['question'][:65]}")
                print(f"   Volume:  ${m['volume_24h']:>10,.2f}")
                print(f"   Liquidity: ${m['liquidity']:>10,.2f}")
                print(f"   YES: ${m['yes_price']:.4f} | NO: ${m['no_price']:.4f}")
                print(f"   Token YES: {m['token_id_yes'][:20]}...")
                print(f"   Token NO:  {m['token_id_no'][:20]}...")

            print("\n" + "="*60)
            print("✅ Markets saved successfully!")
            print(f"📁 File: {output_path}")
            print("="*60)

            return True

    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch active Polymarket markets")
    parser.add_argument(
        "--output",
        "-o",
        default="data/active_markets.json",
        help="Output JSON file path (default: data/active_markets.json)",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=1000.0,
        help="Minimum 24h volume in USDC (default: 1000)",
    )
    parser.add_argument(
        "--max-markets",
        type=int,
        default=100,
        help="Maximum number of markets to fetch (default: 100)",
    )

    args = parser.parse_args()

    success = await fetch_and_save_markets(
        output_path=args.output,
        min_volume=args.min_volume,
        max_markets=args.max_markets,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
