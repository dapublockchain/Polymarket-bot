"""
Main entry point for PolyArb-X.

Demonstrates the arbitrage bot in dry-run mode.
"""
import asyncio
import logging
import sys
from decimal import Decimal

from loguru import logger

from src.core.config import Config
from src.connectors.polymarket_ws import PolymarketWSClient
from src.strategies.atomic import AtomicArbitrageStrategy


async def main():
    """Main async entry point."""
    # Configure logging
    logger.remove()
    logger.add(
        Config.LOG_FILE,
        rotation="10 MB",
        level=Config.LOG_LEVEL,
    )
    logger.add(
        sys.stderr,
        level=Config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    logger.info("Starting PolyArb-X in dry-run mode")
    logger.info(f"Trade size: ${Config.TRADE_SIZE}")
    logger.info(f"Min profit threshold: {Config.MIN_PROFIT_THRESHOLD * 100}%")

    # Initialize WebSocket client
    ws_client = PolymarketWSClient(
        url=Config.POLYMARKET_WS_URL,
        max_reconnect_attempts=5,
        reconnect_delay=2.0,
    )

    # Initialize atomic arbitrage strategy
    strategy = AtomicArbitrageStrategy(
        trade_size=Config.TRADE_SIZE,
        fee_rate=Config.FEE_RATE,
        min_profit_threshold=Config.MIN_PROFIT_THRESHOLD,
        gas_estimate=Decimal("0.0"),  # No gas in dry-run
    )

    try:
        # Connect to WebSocket
        await ws_client.connect()
        logger.info("Connected to Polymarket WebSocket")

        # Subscribe to example tokens (replace with real token IDs)
        example_tokens = [
            "yes_token_example_1",
            "no_token_example_1",
        ]

        for token_id in example_tokens:
            await ws_client.subscribe(token_id)
            logger.info(f"Subscribed to {token_id}")

        # Start listening for messages
        logger.info("Listening for order book updates...")

        # Simulate monitoring for opportunities
        # In production, this would be an infinite loop
        for i in range(5):
            await asyncio.sleep(1)

            # Check for arbitrage opportunities
            # In production, you'd check multiple token pairs
            yes_book = ws_client.get_order_book(example_tokens[0])
            no_book = ws_client.get_order_book(example_tokens[1])

            if yes_book and no_book:
                opportunity = strategy.check_opportunity(yes_book, no_book)

                if opportunity:
                    logger.info(f"ARBITRAGE OPPORTUNITY DETECTED:")
                    logger.info(f"  YES token: {opportunity.yes_token_id}")
                    logger.info(f"  NO token: {opportunity.no_token_id}")
                    logger.info(f"  YES price: {opportunity.yes_price:.4f}")
                    logger.info(f"  NO price: {opportunity.no_price:.4f}")
                    logger.info(f"  Expected profit: ${opportunity.expected_profit:.4f}")
                    logger.info(f"  Reason: {opportunity.reason}")

                    if Config.DRY_RUN:
                        logger.info("  [DRY-RUN] Not executing trade")
                    else:
                        logger.warning("  [LIVE MODE] Would execute trade here")

        logger.info("Demo completed. In production, this would run indefinitely.")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        await ws_client.disconnect()
        logger.info("Disconnected from Polymarket WebSocket")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
