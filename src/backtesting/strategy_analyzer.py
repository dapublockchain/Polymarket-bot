"""
Strategy Analyzer module for performance analysis and optimization.

This module provides:
- Performance metric calculations
- Trade analysis
- Optimization suggestions
- Risk metrics

Example:
    analyzer = StrategyAnalyzer()
    metrics = analyzer.analyze_results(backtest_result)
    suggestions = analyzer.get_suggestions(backtest_result)
"""
import statistics
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.backtesting.backtester import BacktestResult, Trade
from loguru import logger


@dataclass
class PerformanceMetrics:
    """Detailed performance metrics."""

    # Profitability metrics
    total_profit: Decimal
    total_loss: Decimal
    net_profit: Decimal
    profit_factor: float  # total_profit / total_loss
    avg_profit: Decimal
    avg_loss: Decimal
    avg_profit_per_trade: Decimal

    # Trade metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    loss_rate: float

    # Risk metrics
    max_drawdown: Decimal
    max_drawdown_pct: float
    avg_drawdown: Decimal

    # Efficiency metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Streak metrics
    max_winning_streak: int
    max_losing_streak: int
    avg_winning_streak: float
    avg_losing_streak: float

    # Time metrics
    avg_trade_duration_hours: float
    first_trade_time: Optional[datetime]
    last_trade_time: Optional[datetime]


@dataclass
class OptimizationSuggestion:
    """Suggestion for strategy optimization."""

    category: str
    priority: str  # low, medium, high
    title: str
    description: str
    expected_impact: str
    action_items: List[str]


class StrategyAnalyzer:
    """
    Analyzes backtest results and provides optimization suggestions.

    Calculates advanced metrics and identifies areas for improvement.
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize strategy analyzer.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe/Sortino ratios
        """
        self.risk_free_rate = risk_free_rate

    def analyze_results(self, result: BacktestResult) -> PerformanceMetrics:
        """
        Perform comprehensive analysis of backtest results.

        Args:
            result: BacktestResult to analyze

        Returns:
            PerformanceMetrics with all calculated metrics
        """
        trades = result.trades

        # Basic metrics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.actual_profit and t.actual_profit > 0)
        losing_trades = sum(1 for t in trades if t.actual_profit and t.actual_profit < 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        loss_rate = 1.0 - win_rate

        # Profit metrics
        profits = [t.actual_profit for t in trades if t.actual_profit and t.actual_profit > 0]
        losses = [abs(t.actual_profit) for t in trades if t.actual_profit and t.actual_profit < 0]

        total_profit = sum(profits) if profits else Decimal("0")
        total_loss = sum(losses) if losses else Decimal("0")

        avg_profit = statistics.mean([float(p) for p in profits]) if profits else 0.0
        avg_loss = statistics.mean([float(l) for l in losses]) if losses else 0.0

        profit_factor = float(total_profit / total_loss) if total_loss > 0 else 0.0

        # Drawdown analysis
        drawdowns = self._calculate_drawdowns(trades, result.starting_capital)
        max_drawdown = max(drawdowns) if drawdowns else Decimal("0")
        max_drawdown_pct = float(max_drawdown / result.starting_capital) if result.starting_capital > 0 else 0.0
        avg_drawdown = statistics.mean([float(d) for d in drawdowns]) if drawdowns else 0.0

        # Streak analysis
        winning_streaks, losing_streaks = self._calculate_streaks(trades)
        max_winning_streak = max(winning_streaks) if winning_streaks else 0
        max_losing_streak = max(losing_streaks) if losing_streaks else 0
        avg_winning_streak = statistics.mean(winning_streaks) if winning_streaks else 0.0
        avg_losing_streak = statistics.mean(losing_streaks) if losing_streaks else 0.0

        # Calculate returns series
        returns = [float(t.actual_profit) for t in trades if t.actual_profit]
        risk_free_daily = self.risk_free_rate / 365

        # Sharpe ratio (simplified, assuming daily returns)
        if returns:
            excess_returns = [r - risk_free_daily for r in returns]
            if len(excess_returns) > 1:
                try:
                    sharpe_ratio = statistics.mean(excess_returns) / statistics.stdev(excess_returns)
                except (statistics.StatisticsError, ZeroDivisionError):
                    # stdev is 0 when all values are identical
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # Sortino ratio (downside deviation only)
        if returns:
            downside_returns = [r for r in returns if r < risk_free_daily]
            if downside_returns:
                if len(downside_returns) > 1:
                    try:
                        downside_deviation = statistics.stdev(downside_returns)
                    except statistics.StatisticsError:
                        downside_deviation = 0.001
                else:
                    downside_deviation = 0.001
                sortino_ratio = statistics.mean(returns) / downside_deviation if downside_deviation > 0 else 0.0
            else:
                sortino_ratio = 0.0
        else:
            sortino_ratio = 0.0

        # Calmar ratio (annual return / max drawdown)
        annual_return = float(result.net_profit) / float(result.starting_capital) if result.starting_capital > 0 else 0.0
        calmar_ratio = annual_return / max_drawdown_pct if max_drawdown_pct > 0 else 0.0

        # Time metrics
        if trades:
            first_trade = trades[0].timestamp
            last_trade = trades[-1].timestamp
            duration_hours = (last_trade - first_trade).total_seconds() / 3600
            avg_trade_duration_hours = duration_hours / len(trades)
        else:
            first_trade = None
            last_trade = None
            avg_trade_duration_hours = 0.0

        return PerformanceMetrics(
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=result.net_profit,
            profit_factor=profit_factor,
            avg_profit=Decimal(str(avg_profit)),
            avg_loss=Decimal(str(avg_loss)),
            avg_profit_per_trade=result.avg_profit_per_trade,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            loss_rate=loss_rate,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            avg_drawdown=Decimal(str(avg_drawdown)),
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_winning_streak=max_winning_streak,
            max_losing_streak=max_losing_streak,
            avg_winning_streak=avg_winning_streak,
            avg_losing_streak=avg_losing_streak,
            avg_trade_duration_hours=avg_trade_duration_hours,
            first_trade_time=first_trade,
            last_trade_time=last_trade,
        )

    def get_suggestions(self, result: BacktestResult) -> List[OptimizationSuggestion]:
        """
        Generate optimization suggestions based on backtest results.

        Args:
            result: BacktestResult to analyze

        Returns:
            List of optimization suggestions
        """
        suggestions = []
        metrics = self.analyze_results(result)

        # Win rate analysis
        if metrics.win_rate < 0.4:
            suggestions.append(OptimizationSuggestion(
                category="Strategy",
                priority="high",
                title="Improve Win Rate",
                description=f"Win rate of {metrics.win_rate*100:.1f}% is below 40%. Consider adjusting entry criteria.",
                expected_impact="Increase win rate to 50%+ for better consistency",
                action_items=[
                    "Increase minimum profit threshold",
                    "Add additional confirmation indicators",
                    "Filter volatile market conditions",
                ]
            ))

        # Profit factor analysis
        if metrics.profit_factor < 1.5:
            suggestions.append(OptimizationSuggestion(
                category="Risk Management",
                priority="medium",
                title="Low Profit Factor",
                description=f"Profit factor of {metrics.profit_factor:.2f} indicates poor risk/reward.",
                expected_impact="Aim for profit factor > 2.0",
                action_items=[
                    "Implement tighter stop-losses",
                    "Reduce position size on marginal trades",
                    "Skip low-conviction opportunities",
                ]
            ))

        # Max drawdown analysis
        if metrics.max_drawdown_pct > 0.20:
            suggestions.append(OptimizationSuggestion(
                category="Risk Management",
                priority="high",
                title="High Max Drawdown",
                description=f"Max drawdown of {metrics.max_drawdown_pct*100:.1f}% exceeds 20%.",
                expected_impact="Reduce drawdown to < 15%",
                action_items=[
                    "Implement daily loss limits",
                    "Reduce maximum position size",
                    "Add volatility-based position sizing",
                ]
            ))

        # Losing streak analysis
        if metrics.max_losing_streak >= 5:
            suggestions.append(OptimizationSuggestion(
                category="Strategy",
                priority="medium",
                title="Long Losing Streaks",
                description=f"Maximum losing streak of {metrics.max_losing_streak} trades.",
                expected_impact="Limit losing streaks to 3 or fewer",
                action_items=[
                    "Pause trading after 2 consecutive losses",
                    "Review market conditions during losing periods",
                    "Add regime detection filters",
                ]
            ))

        # Low trade count
        if metrics.total_trades < 10:
            suggestions.append(OptimizationSuggestion(
                category="Strategy",
                priority="low",
                title="Low Trade Frequency",
                description=f"Only {metrics.total_trades} trades in backtest period.",
                expected_impact="Increase trade frequency for better statistics",
                action_items=[
                    "Lower profit threshold slightly",
                    "Add more token pairs",
                    "Extend backtest period",
                ]
            ))

        # Sharpe ratio analysis
        if metrics.sharpe_ratio < 1.0:
            suggestions.append(OptimizationSuggestion(
                category="Performance",
                priority="medium",
                title="Low Risk-Adjusted Return",
                description=f"Sharpe ratio of {metrics.sharpe_ratio:.2f} is below 1.0.",
                expected_impact="Aim for Sharpe ratio > 2.0",
                action_items=[
                    "Reduce volatility of returns",
                    "Improve win rate or profit per trade",
                    "Implement better risk management",
                ]
            ))

        return suggestions

    def _calculate_drawdowns(self, trades: List[Trade], initial_capital: Decimal) -> List[Decimal]:
        """Calculate all drawdowns from trade series."""
        if not trades:
            return []

        capital = initial_capital
        peak = capital
        drawdowns = []

        for trade in trades:
            if trade.actual_profit:
                capital += trade.actual_profit

            if capital > peak:
                peak = capital

            drawdown = peak - capital
            if drawdown > 0:
                drawdowns.append(drawdown)

        return drawdowns

    def _calculate_streaks(self, trades: List[Trade]) -> Tuple[List[int], List[int]]:
        """Calculate winning and losing streaks."""
        winning_streaks = []
        losing_streaks = []

        current_winning_streak = 0
        current_losing_streak = 0

        for trade in trades:
            if trade.actual_profit:
                if trade.actual_profit > 0:
                    current_winning_streak += 1
                    if current_losing_streak > 0:
                        losing_streaks.append(current_losing_streak)
                        current_losing_streak = 0
                else:
                    current_losing_streak += 1
                    if current_winning_streak > 0:
                        winning_streaks.append(current_winning_streak)
                        current_winning_streak = 0

        # Add final streaks
        if current_winning_streak > 0:
            winning_streaks.append(current_winning_streak)
        if current_losing_streak > 0:
            losing_streaks.append(current_losing_streak)

        return winning_streaks, losing_streaks

    def print_analysis(self, metrics: PerformanceMetrics):
        """Print detailed analysis."""
        print(f"\n{'='*70}")
        print(f"Performance Analysis")
        print(f"{'='*70}")

        print(f"\nProfitability:")
        print(f"  Total Profit: ${metrics.total_profit:.2f}")
        print(f"  Total Loss: ${metrics.total_loss:.2f}")
        print(f"  Net Profit: ${metrics.net_profit:.2f}")
        print(f"  Profit Factor: {metrics.profit_factor:.2f}")
        print(f"  Avg Profit: ${metrics.avg_profit:.4f}")
        print(f"  Avg Loss: ${metrics.avg_loss:.4f}")

        print(f"\nTrading Performance:")
        print(f"  Total Trades: {metrics.total_trades}")
        print(f"  Winning Trades: {metrics.winning_trades} ({metrics.win_rate*100:.1f}%)")
        print(f"  Losing Trades: {metrics.losing_trades} ({metrics.loss_rate*100:.1f}%)")

        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown: ${metrics.max_drawdown:.2f} ({metrics.max_drawdown_pct*100:.1f}%)")
        print(f"  Avg Drawdown: ${metrics.avg_drawdown:.2f}")

        print(f"\nRisk-Adjusted Returns:")
        print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio: {metrics.sortino_ratio:.2f}")
        print(f"  Calmar Ratio: {metrics.calmar_ratio:.2f}")

        print(f"\nStreak Analysis:")
        print(f"  Max Winning Streak: {metrics.max_winning_streak}")
        print(f"  Max Losing Streak: {metrics.max_losing_streak}")
        print(f"  Avg Winning Streak: {metrics.avg_winning_streak:.1f}")
        print(f"  Avg Losing Streak: {metrics.avg_losing_streak:.1f}")

        print(f"\nTime Metrics:")
        print(f"  Avg Trade Duration: {metrics.avg_trade_duration_hours:.2f} hours")
        if metrics.first_trade_time and metrics.last_trade_time:
            print(f"  First Trade: {metrics.first_trade_time}")
            print(f"  Last Trade: {metrics.last_trade_time}")

        print(f"{'='*70}\n")

    def print_suggestions(self, suggestions: List[OptimizationSuggestion]):
        """Print optimization suggestions."""
        if not suggestions:
            print("\n✅ No optimization suggestions - strategy looks good!")
            return

        print(f"\n{'='*70}")
        print(f"Optimization Suggestions ({len(suggestions)} found)")
        print(f"{'='*70}")

        for i, suggestion in enumerate(suggestions, 1):
            priority_icon = "🔴" if suggestion.priority == "high" else "🟡" if suggestion.priority == "medium" else "🟢"
            print(f"\n{i}. [{priority_icon}] {suggestion.title}")
            print(f"   Category: {suggestion.category}")
            print(f"   Description: {suggestion.description}")
            print(f"   Expected Impact: {suggestion.expected_impact}")
            print(f"   Action Items:")
            for action in suggestion.action_items:
                print(f"     • {action}")

        print(f"\n{'='*70}\n")
