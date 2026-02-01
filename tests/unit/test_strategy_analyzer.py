"""
Unit tests for Strategy Analyzer module.
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from src.backtesting.strategy_analyzer import (
    StrategyAnalyzer,
    PerformanceMetrics,
    OptimizationSuggestion,
)
from src.backtesting.backtester import BacktestResult, Trade


@pytest.fixture
def sample_backtest_result():
    """Create a sample backtest result."""
    return BacktestResult(
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 1),
        starting_capital=Decimal("1000"),
        ending_capital=Decimal("1100"),
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        net_profit=Decimal("100"),
        trades=[
            Trade(
                id="1",
                timestamp=datetime(2026, 2, 1, 10, 0, 0),
                token_id="token_1",
                signal_type="BUY_YES",
                price=Decimal("0.50"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("15"),  # Win
            ),
            Trade(
                id="2",
                timestamp=datetime(2026, 2, 1, 11, 0, 0),
                token_id="token_1",
                signal_type="BUY_YES",
                price=Decimal("0.50"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("-5"),  # Loss
            ),
        ],
    )


class TestStrategyAnalyzerInit:
    """Test suite for StrategyAnalyzer initialization."""

    def test_init_with_default_risk_free_rate(self):
        """Test initialization with default risk-free rate."""
        analyzer = StrategyAnalyzer()

        assert analyzer.risk_free_rate == 0.02

    def test_init_with_custom_risk_free_rate(self):
        """Test initialization with custom risk-free rate."""
        analyzer = StrategyAnalyzer(risk_free_rate=0.03)

        assert analyzer.risk_free_rate == 0.03


class TestAnalyzeResults:
    """Test suite for analyze_results method."""

    def test_analyze_results_basic_metrics(self, sample_backtest_result):
        """Test basic metrics analysis."""
        analyzer = StrategyAnalyzer()
        metrics = analyzer.analyze_results(sample_backtest_result)

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 0.5
        assert metrics.loss_rate == 0.5

    def test_analyze_results_profit_metrics(self, sample_backtest_result):
        """Test profit metrics analysis."""
        analyzer = StrategyAnalyzer()
        metrics = analyzer.analyze_results(sample_backtest_result)

        assert metrics.net_profit == Decimal("100")
        assert metrics.total_trades == 2

    def test_analyze_results_no_trades(self):
        """Test analysis with no trades."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            trades=[],
        )

        analyzer = StrategyAnalyzer()
        metrics = analyzer.analyze_results(result)

        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.max_winning_streak == 0
        assert metrics.max_losing_streak == 0

    def test_analyze_results_all_winning_trades(self):
        """Test analysis with all winning trades."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            ending_capital=Decimal("1200"),
            trades=[
                Trade(
                    id=str(i),
                    timestamp=datetime.now(),
                    token_id="test",
                    signal_type="BUY",
                    price=Decimal("0.5"),
                    size=Decimal("100"),
                    expected_profit=Decimal("10"),
                    actual_profit=Decimal("20"),
                )
                for i in range(5)
            ],
        )

        analyzer = StrategyAnalyzer()
        metrics = analyzer.analyze_results(result)

        assert metrics.win_rate == 1.0
        assert metrics.profit_factor == 0.0  # No losses means division by zero, returns 0

    def test_analyze_results_all_losing_trades(self):
        """Test analysis with all losing trades."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            ending_capital=Decimal("900"),
            trades=[
                Trade(
                    id=str(i),
                    timestamp=datetime.now(),
                    token_id="test",
                    signal_type="BUY",
                    price=Decimal("0.5"),
                    size=Decimal("100"),
                    expected_profit=Decimal("10"),
                    actual_profit=Decimal("-20"),
                )
                for i in range(5)
            ],
        )

        analyzer = StrategyAnalyzer()
        metrics = analyzer.analyze_results(result)

        assert metrics.win_rate == 0.0
        assert metrics.loss_rate == 1.0


class TestGetSuggestions:
    """Test suite for get_suggestions method."""

    def test_get_suggestions_low_win_rate(self):
        """Test suggestions for low win rate."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            total_trades=10,
            winning_trades=3,
            losing_trades=7,
            net_profit=Decimal("-50"),
        )

        analyzer = StrategyAnalyzer()
        suggestions = analyzer.get_suggestions(result)

        # Should have suggestion for low win rate
        win_rate_suggestions = [s for s in suggestions if "Win Rate" in s.title]
        assert len(win_rate_suggestions) > 0
        assert win_rate_suggestions[0].priority == "high"

    def test_get_suggestions_high_drawdown(self):
        """Test suggestions for high drawdown."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            trades=[
                Trade(
                    id="1",
                    timestamp=datetime.now(),
                    token_id="test",
                    signal_type="BUY",
                    price=Decimal("0.5"),
                    size=Decimal("100"),
                    expected_profit=Decimal("10"),
                    actual_profit=Decimal("-200"),  # Big loss
                )
            ],
        )

        analyzer = StrategyAnalyzer()

        # Mock the max drawdown calculation
        with patch.object(analyzer, '_calculate_drawdowns', return_value=[Decimal("300")]):
            suggestions = analyzer.get_suggestions(result)

        # Should have suggestion for high drawdown
        drawdown_suggestions = [s for s in suggestions if "Drawdown" in s.title]
        assert len(drawdown_suggestions) > 0
        assert drawdown_suggestions[0].priority == "high"

    def test_get_suggestions_low_sharpe_ratio(self):
        """Test suggestions for low Sharpe ratio."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            trades=[
                Trade(
                    id=str(i),
                    timestamp=datetime.now(),
                    token_id="test",
                    signal_type="BUY",
                    price=Decimal("0.5"),
                    size=Decimal("100"),
                    expected_profit=Decimal("10"),
                    actual_profit=Decimal("1") if i % 2 == 0 else Decimal("-1"),
                )
                for i in range(10)
            ],
        )

        analyzer = StrategyAnalyzer(risk_free_rate=0.05)  # High risk-free rate

        # Mock analyze_results to return low Sharpe ratio
        with patch.object(analyzer, 'analyze_results') as mock_analyze:
            mock_analyze.return_value = PerformanceMetrics(
                total_profit=Decimal("50"),
                total_loss=Decimal("50"),
                net_profit=Decimal("0"),
                profit_factor=1.0,
                avg_profit=Decimal("10"),
                avg_loss=Decimal("10"),
                avg_profit_per_trade=Decimal("0"),
                total_trades=10,
                winning_trades=5,
                losing_trades=5,
                win_rate=0.5,
                loss_rate=0.5,
                max_drawdown=Decimal("100"),
                max_drawdown_pct=0.1,
                avg_drawdown=Decimal("50"),
                sharpe_ratio=0.5,  # Low Sharpe ratio
                sortino_ratio=0.6,
                calmar_ratio=0.0,
                max_winning_streak=2,
                max_losing_streak=2,
                avg_winning_streak=1.0,
                avg_losing_streak=1.0,
                avg_trade_duration_hours=1.0,
                first_trade_time=datetime.now(),
                last_trade_time=datetime.now(),
            )

            suggestions = analyzer.get_suggestions(result)

        # Should have suggestion for low Sharpe ratio
        sharpe_suggestions = [s for s in suggestions if "Risk-Adjusted Return" in s.title]
        assert len(sharpe_suggestions) > 0


class TestCalculateDrawdowns:
    """Test suite for _calculate_drawdowns method."""

    def test_calculate_drawdowns_with_profitable_trades(self):
        """Test drawdown calculation with profitable trades."""
        analyzer = StrategyAnalyzer()

        trades = [
            Trade(
                id="1",
                timestamp=datetime.now(),
                token_id="test",
                signal_type="BUY",
                price=Decimal("0.5"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("100"),
            ),
            Trade(
                id="2",
                timestamp=datetime.now(),
                token_id="test",
                signal_type="BUY",
                price=Decimal("0.5"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("50"),
            ),
        ]

        drawdowns = analyzer._calculate_drawdowns(trades, Decimal("1000"))

        # No drawdowns since all trades are profitable
        assert len(drawdowns) == 0

    def test_calculate_drawdowns_with_losses(self):
        """Test drawdown calculation with losses."""
        analyzer = StrategyAnalyzer()

        trades = [
            Trade(
                id="1",
                timestamp=datetime.now(),
                token_id="test",
                signal_type="BUY",
                price=Decimal("0.5"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("50"),
            ),
            Trade(
                id="2",
                timestamp=datetime.now(),
                token_id="test",
                signal_type="BUY",
                price=Decimal("0.5"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("-30"),  # Loss
            ),
        ]

        drawdowns = analyzer._calculate_drawdowns(trades, Decimal("1000"))

        # Peak is 1050, drawdown is 30
        assert len(drawdowns) > 0


class TestCalculateStreaks:
    """Test suite for _calculate_streaks method."""

    def test_calculate_streaks_alternating(self):
        """Test streak calculation with alternating wins/losses."""
        analyzer = StrategyAnalyzer()

        trades = [
            Trade(
                id=str(i),
                timestamp=datetime.now(),
                token_id="test",
                signal_type="BUY",
                price=Decimal("0.5"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("10") if i % 2 == 0 else Decimal("-5"),
            )
            for i in range(6)
        ]

        winning_streaks, losing_streaks = analyzer._calculate_streaks(trades)

        # All streaks should be length 1 (alternating)
        assert all(s == 1 for s in winning_streaks)
        assert all(s == 1 for s in losing_streaks)

    def test_calculate_streaks_all_wins(self):
        """Test streak calculation with all wins."""
        analyzer = StrategyAnalyzer()

        trades = [
            Trade(
                id=str(i),
                timestamp=datetime.now(),
                token_id="test",
                signal_type="BUY",
                price=Decimal("0.5"),
                size=Decimal("100"),
                expected_profit=Decimal("10"),
                actual_profit=Decimal("10"),
            )
            for i in range(5)
        ]

        winning_streaks, losing_streaks = analyzer._calculate_streaks(trades)

        assert len(winning_streaks) == 1
        assert winning_streaks[0] == 5
        assert len(losing_streaks) == 0

    def test_calculate_streaks_no_trades(self):
        """Test streak calculation with no trades."""
        analyzer = StrategyAnalyzer()

        winning_streaks, losing_streaks = analyzer._calculate_streaks([])

        assert len(winning_streaks) == 0
        assert len(losing_streaks) == 0


class TestPrintAnalysis:
    """Test suite for print_analysis method."""

    def test_print_analysis(self, capsys):
        """Test printing analysis."""
        analyzer = StrategyAnalyzer()

        metrics = PerformanceMetrics(
            total_profit=Decimal("100"),
            total_loss=Decimal("50"),
            net_profit=Decimal("50"),
            profit_factor=2.0,
            avg_profit=Decimal("10"),
            avg_loss=Decimal("5"),
            avg_profit_per_trade=Decimal("5"),
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            win_rate=0.7,
            loss_rate=0.3,
            max_drawdown=Decimal("100"),
            max_drawdown_pct=0.1,
            avg_drawdown=Decimal("50"),
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=0.5,
            max_winning_streak=3,
            max_losing_streak=2,
            avg_winning_streak=1.5,
            avg_losing_streak=1.0,
            avg_trade_duration_hours=2.5,
            first_trade_time=datetime.now(),
            last_trade_time=datetime.now(),
        )

        analyzer.print_analysis(metrics)

        captured = capsys.readouterr()
        assert "Performance Analysis" in captured.out
        assert "Total Profit:" in captured.out
        assert "Winning Trades:" in captured.out
        assert "Sharpe Ratio:" in captured.out


class TestPrintSuggestions:
    """Test suite for print_suggestions method."""

    def test_print_suggestions_empty(self, capsys):
        """Test printing with no suggestions."""
        analyzer = StrategyAnalyzer()
        analyzer.print_suggestions([])

        captured = capsys.readouterr()
        assert "No optimization suggestions" in captured.out

    def test_print_suggestions_with_items(self, capsys):
        """Test printing with suggestions."""
        analyzer = StrategyAnalyzer()

        suggestions = [
            OptimizationSuggestion(
                category="Strategy",
                priority="high",
                title="Improve Win Rate",
                description="Win rate is too low",
                expected_impact="Better performance",
                action_items=["Action 1", "Action 2"],
            )
        ]

        analyzer.print_suggestions(suggestions)

        captured = capsys.readouterr()
        assert "Optimization Suggestions" in captured.out
        assert "Improve Win Rate" in captured.out
        assert "Action 1" in captured.out
        assert "Action 2" in captured.out
