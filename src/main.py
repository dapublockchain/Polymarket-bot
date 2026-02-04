"""
Main entry point for PolyArb-X.

Demonstrates the arbitrage bot in dry-run mode.
"""

import asyncio
import json
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

from loguru import logger

from src.core.config import Config
from src.connectors.polymarket_ws import PolymarketWSClient
from src.strategies.atomic import AtomicArbitrageStrategy
from src.core.recorder import EventRecorder
from src.core.telemetry import generate_trace_id, TraceContext
from src.core.models import TradingMetrics
from src.execution.simulated_executor import SimulatedExecutor
from src.execution.execution_router import ExecutionRouter
from src.execution.pnl_tracker import PnLTracker
from src.execution.diagnostics import DryRunSanityCheck


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

    # Log mode
    if Config.DRY_RUN:
        logger.info("启动 PolyArb-X (模拟模式)")
    else:
        logger.warning("⚠️  启动 PolyArb-X (实盘模式) - 真实资金将用于交易!")
        logger.warning("⚠️  请确保您已了解风险并设置了适当的限额")

    logger.info(f"交易规模: ${Config.TRADE_SIZE}")
    logger.info(f"最小利润阈值: {Config.MIN_PROFIT_THRESHOLD * 100}%")

    # Initialize event recorder with immediate flush for real-time UI updates
    recorder = EventRecorder(buffer_size=100, immediate_flush=True)
    logger.info("事件记录器已初始化 (immediate flush enabled)")

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

    # Initialize simulated executor and execution router
    simulated_executor = SimulatedExecutor(
        slippage_bps=int(Config.MAX_SLIPPAGE * 10000),  # Convert to bps
    )

    # Initialize live executor if in production mode
    live_executor = None
    if not Config.DRY_RUN:
        from src.execution.live_executor import LiveExecutor
        from src.execution.tx_sender import TxSender
        from src.execution.nonce_manager import NonceManager
        from src.execution.risk_manager import RiskManager
        from src.execution.circuit_breaker import CircuitBreaker
        from src.execution.retry_policy import RetryPolicy
        from src.connectors.web3_client import Web3Client

        # Validate private key
        if not Config.PRIVATE_KEY:
            raise ValueError("PRIVATE_KEY must be set in .env for live mode")

        # Initialize Web3 client
        web3_client = Web3Client(
            rpc_url=Config.POLYGON_RPC_URL,
            private_key=Config.PRIVATE_KEY
        )
        logger.info(f"✅ Web3 client initialized for {web3_client.address}")

        # Initialize risk manager
        risk_manager = RiskManager(
            max_position_size=Config.MAX_POSITION_SIZE,
            max_gas_cost=Config.MAX_GAS_COST,
        )

        # Initialize nonce manager
        nonce_manager = NonceManager(
            web3_client=web3_client,
            address=web3_client.address
        )

        # Initialize circuit breaker
        from src.execution.circuit_breaker import CircuitBreakerConfig

        circuit_breaker_config = CircuitBreakerConfig(
            consecutive_failures_threshold=5,
            open_timeout_seconds=60
        )
        circuit_breaker = CircuitBreaker(
            config=circuit_breaker_config,
            name="trading"
        )

        # Initialize retry policy
        from src.execution.retry_policy import RetryPolicyConfig

        retry_policy_config = RetryPolicyConfig(
            max_retries=Config.MAX_RETRIES,
            base_delay_ms=int(Config.RETRY_DELAY * 1000)
        )
        retry_policy = RetryPolicy(config=retry_policy_config)

        # Initialize transaction sender
        tx_sender = TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            slippage_tolerance=Config.MAX_SLIPPAGE,
        )
        logger.info("✅ TxSender initialized")

        # Initialize live executor with REAL EXECUTION enabled
        live_executor = LiveExecutor(
            tx_sender=tx_sender,
            fee_rate=Config.FEE_RATE,
            slippage_tolerance=Config.MAX_SLIPPAGE,
            use_real_execution=True,  # 🔴 CRITICAL: Enable real trading
        )
        logger.warning("🔴 LiveExecutor initialized (REAL TRADING MODE - use_real_execution=True)")

        # Initialize execution router with live executor
        execution_router = ExecutionRouter(
            simulated_executor=simulated_executor,
            live_executor=live_executor,
        )
        logger.warning("⚠️  ExecutionRouter in LIVE mode")
    else:
        # Dry-run mode
        execution_router = ExecutionRouter(simulated_executor=simulated_executor)
        logger.info("✅ ExecutionRouter initialized in DRY_RUN mode")

    pnl_tracker = PnLTracker()
    sanity_checker = DryRunSanityCheck(check_interval_seconds=60)
    logger.info("✅ PnL tracker initialized")
    logger.info("✅ Dry-run sanity checker initialized")

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

        # Statistics - Using TradingMetrics for proper tracking
        stats = TradingMetrics(
            start_time=asyncio.get_event_loop().time(),
        )
        checks = 0  # Keep separate counter for loop iterations

        # Start dry-run sanity checker
        await sanity_checker.start(stats)
        logger.info("✅ Dry-run sanity checker started (60s interval)")

        try:
            # Monitor for opportunities
            # In production, this would be an infinite loop
            # Loop indefinitely in dry-run
            logger.info("🔍 开始监控套利机会...")
            logger.info("="*60)

            while True:
                await asyncio.sleep(1)
                checks += 1

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

                        # Update orderbooks in simulated executor
                        simulated_executor.update_orderbook(yes_book.token_id, yes_book)
                        simulated_executor.update_orderbook(no_book.token_id, no_book)

                        # Generate trace_id for this opportunity check
                        trace_id = generate_trace_id()

                        # Check for opportunity with trace_id
                        opportunity = await strategy.check_opportunity(yes_book, no_book, trace_id=trace_id)

                        if opportunity:
                            stats.opportunities_seen += 1

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

                            # Use execution router for unified pipeline
                            stats.orders_submitted += 1

                            if Config.DRY_RUN:
                                # Execute with simulated executor
                                yes_fill, no_fill, tx_result = await execution_router.execute_arbitrage(
                                    opportunity,
                                    yes_book,
                                    no_book,
                                    trace_id
                                )

                                # Track fills
                                if yes_fill and no_fill:
                                    stats.fills_simulated += 2

                                    # Record fill events
                                    await recorder.record_event("fill", yes_fill.to_dict())
                                    await recorder.record_event("fill", no_fill.to_dict())

                                    # Process fills through PnL tracker
                                    pnl_update = await pnl_tracker.process_fills(
                                        fills=[yes_fill, no_fill],
                                        expected_edge=opportunity.expected_profit,
                                        trace_id=trace_id,
                                        strategy="atomic"
                                    )

                                    # Update stats
                                    stats.pnl_updates += 1

                                    # Update cumulative metrics
                                    stats.cumulative_simulated_pnl = pnl_tracker._cumulative_simulated_pnl
                                    stats.cumulative_expected_edge = pnl_tracker._cumulative_expected_edge

                                    # Record PnL update event
                                    await recorder.record_event("pnl_update", pnl_update.to_dict())

                                    # Log PnL information
                                    logger.info(f"   [模拟模式] PnL更新:")
                                    logger.info(f"      预期收益: ${pnl_update.expected_edge:.4f}")
                                    logger.info(f"      模拟PnL: ${pnl_update.simulated_pnl:.4f}")
                                    logger.info(f"      手续费: ${pnl_update.fees_paid:.4f}")
                                    logger.info(f"      滑点成本: ${pnl_update.slippage_cost:.4f}")
                                else:
                                    logger.warning("   [模拟模式] 模拟成交失败")
                            else:
                                # Execute with live executor (REAL TRADING)
                                logger.warning("⚠️  [实盘模式] 执行真实交易...")
                                yes_fill, no_fill, tx_result = await execution_router.execute_arbitrage(
                                    opportunity,
                                    yes_book,
                                    no_book,
                                    trace_id
                                )

                                # Track fills
                                if yes_fill and no_fill:
                                    stats.fills_confirmed += 2

                                    # Record fill events
                                    await recorder.record_event("fill", yes_fill.to_dict())
                                    await recorder.record_event("fill", no_fill.to_dict())

                                    # Process fills through PnL tracker
                                    pnl_update = await pnl_tracker.process_fills(
                                        fills=[yes_fill, no_fill],
                                        expected_edge=opportunity.expected_profit,
                                        trace_id=trace_id,
                                        strategy="atomic"
                                    )

                                    # Update stats
                                    stats.pnl_updates += 1

                                    # Update cumulative metrics
                                    stats.cumulative_realized_pnl = pnl_tracker._cumulative_realized_pnl
                                    stats.cumulative_expected_edge = pnl_tracker._cumulative_expected_edge

                                    # Record PnL update event
                                    await recorder.record_event("pnl_update", pnl_update.to_dict())

                                    # Log PnL information
                                    logger.success("   [实盘模式] 真实成交成功:")
                                    logger.success(f"      YES: {yes_fill.quantity:.4f} @ ${yes_fill.price:.4f} (tx: {yes_fill.tx_hash[:20]}...)" if yes_fill.tx_hash else f"      YES: {yes_fill.quantity:.4f} @ ${yes_fill.price:.4f}")
                                    logger.success(f"      NO:  {no_fill.quantity:.4f} @ ${no_fill.price:.4f} (tx: {no_fill.tx_hash[:20]}...)" if no_fill.tx_hash else f"      NO:  {no_fill.quantity:.4f} @ ${no_fill.price:.4f}")
                                    logger.success(f"      预期收益: ${pnl_update.expected_edge:.4f}")
                                    logger.success(f"      实际PnL: ${pnl_update.realized_pnl if pnl_update.realized_pnl else 'TBD':.4f}")
                                    logger.success(f"      手续费: ${pnl_update.fees_paid:.4f}")
                                else:
                                    logger.error("   [实盘模式] ❌ 真实成交失败!")

                # Log statistics every 60 seconds
                if checks % 60 == 0:
                    elapsed = asyncio.get_event_loop().time() - stats.start_time
                    rate = checks / elapsed * 60  # checks per minute

                    logger.info("="*60)
                    logger.info(f"📊 运行统计 (运行时间: {int(elapsed)}s):")
                    logger.info(f"   检查次数: {checks}")
                    logger.info(f"   检测机会: {stats.opportunities_seen}")
                    logger.info(f"   订单提交: {stats.orders_submitted}")
                    logger.info(f"   模拟成交: {stats.fills_simulated}")
                    logger.info(f"   确认成交: {stats.fills_confirmed}")
                    logger.info(f"   PnL更新: {stats.pnl_updates}")
                    logger.info(f"   检查速率: {rate:.1f} 次/分钟")
                    if checks > 0:
                        logger.info(f"   机会率: {stats.opportunities_seen/checks*100:.2f}%")
                    logger.info(f"   累计预期收益: ${stats.cumulative_expected_edge:.4f}")
                    logger.info(f"   累计模拟PnL: ${stats.cumulative_simulated_pnl:.4f}")
                    logger.info(f"   累计实际PnL: ${stats.cumulative_realized_pnl:.4f}")

                    # Dry-run sanity check
                    if Config.DRY_RUN:
                        if stats.orders_submitted > 0 and stats.fills_simulated == 0:
                            logger.error("")
                            logger.error("⚠️  DRY_RUN_NO_FILLS: 订单已提交但没有模拟成交!")
                            logger.error("   这表明 dry-run 模式未正确模拟执行。")
                            logger.error("   请检查 SimulatedExecutor 是否已正确集成。")
                            logger.error("")

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
        # Stop sanity checker
        await sanity_checker.stop()
        logger.info("Dry-run sanity checker stopped")

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
