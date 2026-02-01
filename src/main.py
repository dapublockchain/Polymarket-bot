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
from src.core.recorder import EventRecorder
from src.core.telemetry import generate_trace_id, TraceContext


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

    logger.info("启动 PolyArb-X (模拟模式)")
    logger.info(f"交易规模: ${Config.TRADE_SIZE}")
    logger.info(f"最小利润阈值: {Config.MIN_PROFIT_THRESHOLD * 100}%")

    # Initialize event recorder
    recorder = EventRecorder(buffer_size=100)
    logger.info("事件记录器已初始化")

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
        logger.info("已连接到 Polymarket WebSocket")

        # Subscribe to example tokens (replace with real token IDs)
        # Real tokens for "MicroStrategy sells any Bitcoin in 2025?"
        example_tokens = [
            "93592949212798121127213117304912625505836768562433217537850469496310204567695",  # YES
            "3074539347152748632858978545166555332546941892131779352477699494423276162345",  # NO
        ]

        for token_id in example_tokens:
            await ws_client.subscribe(token_id)
            logger.info(f"已订阅 {token_id}")

        # Start listening for messages in background
        logger.info("正在监听订单本更新...")
        listen_task = asyncio.create_task(ws_client.listen())

        try:
            # Simulate monitoring for opportunities
            # In production, this would be an infinite loop
            # Loop indefinitely in dry-run
            while True:
                await asyncio.sleep(1)

                # Check for arbitrage opportunities
                # In production, you'd check multiple token pairs
                yes_book = ws_client.get_order_book(example_tokens[0])
                no_book = ws_client.get_order_book(example_tokens[1])

                if yes_book and no_book:
                    # Record orderbook snapshot
                    await recorder.record_orderbook_snapshot(
                        token_id=yes_book.token_id,
                        bids=[{"price": str(b.price), "size": str(b.size)} for b in yes_book.bids],
                        asks=[{"price": str(a.price), "size": str(a.size)} for a in yes_book.asks]
                    )

                    # Generate trace_id for this opportunity check
                    trace_id = generate_trace_id()

                    # Check for opportunity with trace_id
                    opportunity = await strategy.check_opportunity(yes_book, no_book, trace_id=trace_id)

                    if opportunity:
                        logger.info("检测到套利机会:")
                        logger.info(f"  YES 代币: {opportunity.yes_token_id}")
                        logger.info(f"  NO 代币: {opportunity.no_token_id}")
                        logger.info(f"  YES 价格: {opportunity.yes_price:.4f}")
                        logger.info(f"  NO 价格: {opportunity.no_price:.4f}")
                        logger.info(f"  预期利润: ${opportunity.expected_profit:.4f}")
                        logger.info(f"  原因: {opportunity.reason}")

                        # Record signal
                        await recorder.record_signal(
                            trace_id=trace_id,
                            strategy=opportunity.strategy,
                            yes_token=opportunity.yes_token_id,
                            no_token=opportunity.no_token_id,
                            yes_price=opportunity.yes_price,
                            no_price=opportunity.no_price,
                            expected_profit=opportunity.expected_profit
                        )

                        if Config.DRY_RUN:
                            logger.info("  [模拟模式] 未执行交易")

                            # Record simulated order result
                            await recorder.record_order_result(
                                trace_id=trace_id,
                                success=True,
                                tx_hash="0x_simulated",
                                gas_used=0,
                                actual_price=opportunity.yes_price
                            )
                        else:
                            logger.warning("  [实盘模式] 将在此处执行交易")

            logger.info("演示完成。在生产环境中，这将无限期运行。")
        finally:
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"错误: {e}")
        raise

    finally:
        # Flush recorder before exiting
        await recorder.flush()
        logger.info("事件记录器已刷新")

        await ws_client.disconnect()
        logger.info("已断开与 Polymarket WebSocket 的连接")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("正在关闭...")
