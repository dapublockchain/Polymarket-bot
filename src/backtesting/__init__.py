"""
Backtesting module for strategy testing and optimization.

This module provides tools for:
- Event replay from recorded data
- Historical backtesting
- Performance analysis
- Strategy comparison

Example usage:
    from src.backtesting import Backtester, EventReplayer, StrategyAnalyzer

    # Replay events
    replayer = EventReplayer()
    async for event in replayer.replay_date(date(2026, 2, 1)):
        print(event)

    # Run backtest
    backtester = Backtester()
    result = await backtester.backtest_date(date(2026, 2, 1), strategy)

    # Analyze results
    analyzer = StrategyAnalyzer()
    metrics = analyzer.analyze_results(result)
    suggestions = analyzer.get_suggestions(result)
"""

from src.backtesting.event_replayer import EventReplayer, ReplayMode
from src.backtesting.backtester import Backtester, BacktestResult, Trade, StrategyComparator
from src.backtesting.strategy_analyzer import (
    StrategyAnalyzer,
    PerformanceMetrics,
    OptimizationSuggestion,
)

__all__ = [
    "EventReplayer",
    "ReplayMode",
    "Backtester",
    "BacktestResult",
    "Trade",
    "StrategyComparator",
    "StrategyAnalyzer",
    "PerformanceMetrics",
    "OptimizationSuggestion",
]
