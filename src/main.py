"""
Main entry point for PolyArb-X.

Demonstrates the arbitrage bot in dry-run mode.
"""

import asyncio
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path

from loguru import logger

from src.core.config import Config
from src.connectors.polymarket_ws import PolymarketWSClient
from src.strategies.atomic import AtomicArbitrageStrategy
from src.core.recorder import EventRecorder
from src.core.telemetry import generate_trace_id, TraceContext


async def load_active_markets(markets_file: str = "data/active_markets.json"):
    """
    Load active markets from JSON file.

    Args:
        markets_file: Path to markets JSON file

    Returns:
        List of market dictionaries or None if file not found
    """
    try:
        markets_path = Path(markets_file)

        if not markets_path.exists():
            logger.warning(f"Markets file not found: {markets_file}")
            logger.warning("Will use default example tokens")
            return None

        with open(markets_path, 'r') as f:
            markets = json.load(f)

        logger.success(f"✅ Loaded {len(markets)} active markets from {markets_file}")

        # Log summary
        total_volume = sum(m['volume_24h'] for m in markets)
        total_liquidity = sum(m['liquidity'] for m in markets)

        logger.info(f"📊 Markets Summary:")
        logger.info(f"   Total Volume (24h): ${total_volume:,.2f}")
        logger.info(f"   Total Liquidity: ${total_liquidity:,.2f}")
        logger.info(f"   Avg Volume: ${total_volume/len(markets):,.2f}")
        logger.info(f"   Avg Liquidity: ${total_liquidity/len(markets):,.2f}")

        return markets

    except Exception as e:
        logger.error(f"Failed to load markets: {e}")
        return None


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
        # Load active markets
        markets = await load_active_markets()

        # Connect to WebSocket
        await ws_client.connect()
        logger.success("✅ 已连接到 Polymarket WebSocket")

        # Subscribe to markets
        if markets:
            # Subscribe to all loaded markets
            logger.info(f"📡 Subscribing to {len(markets)} markets...")

            # Subscribe to both YES and NO tokens for each market
            token_pairs = []
            for i, market in enumerate(markets, 1):
                yes_token = market['token_id_yes']
                no_token = market['token_id_no']

                await ws_client.subscribe(yes_token)
                await ws_client.subscribe(no_token)

                token_pairs.append({
                    'market_id': market['market_id'],
                    'question': market['question'],
                    'yes_token': yes_token,
                    'no_token': no_token,
                })

                if i <= 5 or i % 10 == 0:  # Log first 5 and every 10th
                    logger.info(f"   [{i}/{len(markets)}] {market['question'][:50]}...")

            logger.success(f"✅ Subscribed to {len(token_pairs)} markets ({len(token_pairs)*2} tokens)")
        else:
            # Fallback to example tokens
            logger.warning("⚠️ Using example tokens (no markets loaded)")
            example_tokens = [
                "93592949212798121127213117304912625505836768562433217537850469496310204567695",  # YES
                "3074539347152748632858978545166555332546941892131779352477699494423276162345",  # NO
            ]

            for token_id in example_tokens:
                await ws_client.subscribe(token_id)
                logger.info(f"已订阅 {token_id}")

            token_pairs = [{
                'market_id': 'example',
                'question': 'Example Market',
                'yes_token': example_tokens[0],
                'no_token': example_tokens[1],
            }]

        # Start listening for messages in background
        logger.info("🎧 正在监听订单本更新...")
        listen_task = asyncio.create_task(ws_client.listen())

        # Statistics
        stats = {
            'checks': 0,
            'opportunities': 0,
            'trades': 0,
            'start_time': asyncio.get_event_loop().time(),
        }

        try:
            # Monitor for opportunities
            # In production, this would be an infinite loop
            # Loop indefinitely in dry-run
            logger.info("🔍 开始监控套利机会...")
            logger.info("="*60)

            while True:
                await asyncio.sleep(1)
                stats['checks'] += 1

                # Check all market pairs
                for pair in token_pairs:
                    yes_book = ws_client.get_order_book(pair['yes_token'])
                    no_book = ws_client.get_order_book(pair['no_token'])

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
                            stats['opportunities'] += 1

                            logger.info("🎯 检测到套利机会:")
                            logger.info(f"   市场: {pair['question'][:60]}")
                            logger.info(f"   YES 代币: {opportunity.yes_token_id[:20]}...")
                            logger.info(f"   NO 代币: {opportunity.no_token_id[:20]}...")
                            logger.info(f"   YES 价格: {opportunity.yes_price:.4f}")
                            logger.info(f"   NO 价格: {opportunity.no_price:.4f}")
                            logger.info(f"   预期利润: ${opportunity.expected_profit:.4f} ({opportunity.expected_profit/Config.TRADE_SIZE*100:.2f}%)")
                            logger.info(f"   原因: {opportunity.reason}")

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
                                logger.info("   [模拟模式] 未执行交易")
                                stats['trades'] += 1

                                # Record simulated order result
                                await recorder.record_order_result(
                                    trace_id=trace_id,
                                    success=True,
                                    tx_hash="0x_simulated",
                                    gas_used=0,
                                    actual_price=opportunity.yes_price
                                )
                            else:
                                logger.warning("   [实盘模式] 将在此处执行交易")

                # Log statistics every 60 seconds
                if stats['checks'] % 60 == 0:
                    elapsed = asyncio.get_event_loop().time() - stats['start_time']
                    rate = stats['checks'] / elapsed * 60  # checks per minute

                    logger.info("="*60)
                    logger.info(f"📊 运行统计 (运行时间: {int(elapsed)}s):")
                    logger.info(f"   检查次数: {stats['checks']}")
                    logger.info(f"   检测机会: {stats['opportunities']}")
                    logger.info(f"   执行交易: {stats['trades']}")
                    logger.info(f"   检查速率: {rate:.1f} 次/分钟")
                    logger.info(f"   机会率: {stats['opportunities']/stats['checks']*100:.2f}%")
                    logger.info("="*60)

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
