"""
Backtesting module for strategy testing.

This module provides:
- Historical strategy testing
- Performance metrics calculation
- Portfolio simulation
- Trade analysis

Example:
    backtester = Backtester()
    results = await backtester.backtest_date(
        date(2026, 2, 1),
        strategy=AtomicArbitrageStrategy()
    )
"""
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import uuid

from src.backtesting.event_replayer import EventReplayer, ReplayMode
from src.core.models import OrderBook, Bid, Ask, Signal
from src.strategies.atomic import AtomicArbitrageStrategy
from src.core.recorder import EventType
from loguru import logger


@dataclass
class Trade:
    """A simulated trade."""

    id: str
    timestamp: datetime
    token_id: str
    signal_type: str  # BUY_YES or SELL_YES
    price: Decimal
    size: Decimal
    expected_profit: Decimal
    actual_profit: Optional[Decimal] = None
    status: str = "executed"  # executed, failed, pending


@dataclass
class BacktestResult:
    """Results from a backtest."""

    start_date: date
    end_date: date

    # Performance metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # Profit metrics
    total_profit: Decimal = Decimal("0")
    total_loss: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    avg_profit_per_trade: Decimal = Decimal("0")

    # Capital metrics
    starting_capital: Decimal = Decimal("1000")
    ending_capital: Decimal = Decimal("1000")
    max_drawdown: Decimal = Decimal("0")
    roi: float = 0.0

    # Trade details
    trades: List[Trade] = field(default_factory=list)

    # Timestamps
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class Backtester:
    """
    Backtests trading strategies on historical data.

    Simulates trading with realistic execution and slippage.
    """

    def __init__(
        self,
        initial_capital: Decimal = Decimal("1000"),
        slippage_bps: int = 5,  # 5 basis points (0.05%)
        max_position_size: Decimal = Decimal("100"),
    ):
        """
        Initialize backtester.

        Args:
            initial_capital: Starting capital
            slippage_bps: Slippage in basis points
            max_position_size: Maximum position size
        """
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.max_position_size = max_position_size
        self.replayer = EventReplayer(mode=ReplayMode.FAST_FORWARD)

        # Order books for all tokens
        self.orderbooks: Dict[str, OrderBook] = {}

        # Simulated portfolio
        self.cash: Decimal = initial_capital
        self.positions: Dict[str, Decimal] = {}

    async def backtest_date(
        self,
        event_date: date,
        strategy,
        min_profit: float = 0.01,
    ) -> BacktestResult:
        """
        Backtest a strategy on a single date.

        Args:
            event_date: Date to backtest
            strategy: Strategy instance to test
            min_profit: Minimum profit threshold for signals

        Returns:
            BacktestResult with performance metrics
        """
        result = BacktestResult(
            start_date=event_date,
            end_date=event_date,
            starting_capital=self.initial_capital,
        )
        result.start_time = datetime.now()

        # Reset state
        self.cash = self.initial_capital
        self.positions = {}
        self.orderbooks = {}

        # Replay events
        trade_count = 0
        async for event in self.replayer.replay_date(event_date):
            await self._process_event(event, strategy, result, min_profit)
            trade_count += 1

        # Calculate final metrics
        result.end_time = datetime.now()
        result.total_trades = len(result.trades)
        result.winning_trades = sum(1 for t in result.trades if t.actual_profit and t.actual_profit > 0)
        result.losing_trades = sum(1 for t in result.trades if t.actual_profit and t.actual_profit < 0)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0.0

        result.total_profit = sum(t.actual_profit for t in result.trades if t.actual_profit and t.actual_profit > 0) or Decimal("0")
        result.total_loss = abs(sum(t.actual_profit for t in result.trades if t.actual_profit and t.actual_profit < 0)) or Decimal("0")
        result.net_profit = result.total_profit - result.total_loss
        result.avg_profit_per_trade = result.net_profit / result.total_trades if result.total_trades > 0 else Decimal("0")

        result.ending_capital = self.cash
        result.roi = float((result.ending_capital - result.starting_capital) / result.starting_capital * 100)

        return result

    async def backtest_date_range(
        self,
        start_date: date,
        end_date: date,
        strategy,
        min_profit: float = 0.01,
    ) -> BacktestResult:
        """
        Backtest a strategy over a date range.

        Args:
            start_date: Start date
            end_date: End date
            strategy: Strategy instance to test
            min_profit: Minimum profit threshold

        Returns:
            BacktestResult with aggregated metrics
        """
        result = BacktestResult(
            start_date=start_date,
            end_date=end_date,
            starting_capital=self.initial_capital,
        )
        result.start_time = datetime.now()

        # Reset state
        self.cash = self.initial_capital
        self.positions = {}
        self.orderbooks = {}

        # Replay events over date range
        async for event in self.replayer.replay_date_range(start_date, end_date):
            await self._process_event(event, strategy, result, min_profit)

        # Calculate final metrics
        result.end_time = datetime.now()
        result.total_trades = len(result.trades)
        result.winning_trades = sum(1 for t in result.trades if t.actual_profit and t.actual_profit > 0)
        result.losing_trades = sum(1 for t in result.trades if t.actual_profit and t.actual_profit < 0)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0.0

        result.total_profit = sum(t.actual_profit for t in result.trades if t.actual_profit and t.actual_profit > 0) or Decimal("0")
        result.total_loss = abs(sum(t.actual_profit for t in result.trades if t.actual_profit and t.actual_profit < 0)) or Decimal("0")
        result.net_profit = result.total_profit - result.total_loss
        result.avg_profit_per_trade = result.net_profit / result.total_trades if result.total_trades > 0 else Decimal("0")

        result.ending_capital = self.cash
        result.roi = float((result.ending_capital - self.starting_capital) / self.starting_capital * 100)

        return result

    async def _process_event(
        self,
        event: Dict[str, Any],
        strategy,
        result: BacktestResult,
        min_profit: float,
    ):
        """Process a single event during backtest."""
        event_type = event["event_type"]

        if event_type == EventType.ORDERBOOK_SNAPSHOT.value:
            # Update order book
            await self._update_orderbook(event)

        elif event_type == EventType.SIGNAL.value:
            # Check if we should execute this signal
            signal_data = event["data"]
            expected_profit = float(signal_data["expected_profit"])

            if expected_profit >= min_profit:
                await self._execute_signal(event, result)

    async def _update_orderbook(self, event: Dict[str, Any]):
        """Update order book from event."""
        data = event["data"]
        token_id = data["token_id"]

        # Parse bids and asks
        bids = [
            Bid(
                price=Decimal(str(b["price"])),
                size=Decimal(str(b["size"])),
                token_id=token_id,
            )
            for b in data.get("bids", [])
        ]

        asks = [
            Ask(
                price=Decimal(str(a["price"])),
                size=Decimal(str(a["size"])),
                token_id=token_id,
            )
            for a in data.get("asks", [])
        ]

        # Create order book
        self.orderbooks[token_id] = OrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks,
            last_update=int(datetime.fromisoformat(event["timestamp"]).timestamp() * 1000),
        )

    async def _execute_signal(self, event: Dict[str, Any], result: BacktestResult):
        """Execute a trading signal in backtest."""
        signal_data = event["data"]
        token_id = signal_data["yes_token"]  # YES token

        # Get order book
        orderbook = self.orderbooks.get(token_id)
        if not orderbook:
            return

        # Calculate trade size
        trade_size = min(
            self.max_position_size,
            self.cash,
        )

        if trade_size <= 0:
            return

        # Apply slippage
        slippage_multiplier = 1 - (self.slippage_bps / 10000)

        # Simulate trade execution
        signal_type = signal_data.get("signal_type", "BUY_YES")
        expected_profit = Decimal(str(signal_data["expected_profit"]))
        actual_profit = expected_profit * Decimal(str(slippage_multiplier))

        # Check if we have enough capital
        if self.cash < trade_size:
            return

        # Execute trade
        self.cash -= trade_size  # Simulate buying

        # Simulate profit/loss
        profit = actual_profit * (trade_size / self.max_position_size)
        self.cash += trade_size + profit  # Return capital + profit

        # Record trade
        trade = Trade(
            id=str(uuid.uuid4()),
            timestamp=datetime.fromisoformat(event["timestamp"]),
            token_id=token_id,
            signal_type=signal_type,
            price=Decimal("0"),  # Not tracked in backtest
            size=trade_size,
            expected_profit=expected_profit,
            actual_profit=profit,
            status="executed",
        )

        result.trades.append(trade)

    def calculate_max_drawdown(self, result: BacktestResult) -> Decimal:
        """Calculate maximum drawdown from backtest results."""
        if not result.trades:
            return Decimal("0")

        peak = self.initial_capital
        max_drawdown = Decimal("0")

        running_capital = self.initial_capital
        for trade in result.trades:
            if trade.actual_profit:
                running_capital += trade.actual_profit

            if running_capital > peak:
                peak = running_capital

            drawdown = (peak - running_capital) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    def print_summary(self, result: BacktestResult):
        """Print a summary of backtest results."""
        print(f"\n{'='*60}")
        print(f"Backtest Summary: {result.start_date} to {result.end_date}")
        print(f"{'='*60}")
        print(f"Total Trades: {result.total_trades}")
        print(f"Win Rate: {result.win_rate*100:.2f}%")
        print(f"Winning Trades: {result.winning_trades}")
        print(f"Losing Trades: {result.losing_trades}")
        print(f"\nProfit Metrics:")
        print(f"  Total Profit: ${result.total_profit:.2f}")
        print(f"  Total Loss: ${result.total_loss:.2f}")
        print(f"  Net Profit: ${result.net_profit:.2f}")
        print(f"  Avg Profit/Trade: ${result.avg_profit_per_trade:.4f}")
        print(f"\nCapital Metrics:")
        print(f"  Starting Capital: ${result.starting_capital:.2f}")
        print(f"  Ending Capital: ${result.ending_capital:.2f}")
        print(f"  ROI: {result.roi:.2f}%")
        print(f"{'='*60}\n")


class StrategyComparator:
    """
    Compares multiple strategies on the same data.

    Useful for finding the best strategy configuration.
    """

    def __init__(self, initial_capital: Decimal = Decimal("1000")):
        """Initialize strategy comparator."""
        self.initial_capital = initial_capital

    async def compare_strategies(
        self,
        event_date: date,
        strategies: List[Any],
        strategy_names: Optional[List[str]] = None,
    ) -> Dict[str, BacktestResult]:
        """
        Compare multiple strategies on the same date.

        Args:
            event_date: Date to test
            strategies: List of strategy instances
            strategy_names: Optional names for strategies

        Returns:
            Dictionary mapping strategy names to results
        """
        if strategy_names is None:
            strategy_names = [f"Strategy_{i}" for i in range(len(strategies))]

        results = {}

        for name, strategy in zip(strategy_names, strategies):
            backtester = Backtester(initial_capital=self.initial_capital)
            result = await backtester.backtest_date(event_date, strategy)
            results[name] = result

        return results

    def print_comparison(self, results: Dict[str, BacktestResult]):
        """Print comparison of strategy results."""
        print(f"\n{'='*80}")
        print(f"Strategy Comparison")
        print(f"{'='*80}")
        print(f"{'Strategy':<20} {'Trades':>10} {'Win Rate':>10} {'Net Profit':>12} {'ROI':>8}")
        print(f"{'-'*80}")

        for name, result in results.items():
            print(
                f"{name:<20} {result.total_trades:>10} "
                f"{result.win_rate*100:>9.1f}% ${result.net_profit:>10.2f} "
                f"{result.roi:>7.2f}%"
            )

        print(f"{'='*80}\n")
