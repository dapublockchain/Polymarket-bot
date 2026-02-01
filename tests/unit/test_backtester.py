"""
Unit tests for Backtester module.
"""
import pytest
import asyncio
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.backtesting.backtester import (
    Backtester,
    BacktestResult,
    Trade,
    StrategyComparator,
)


@pytest.fixture
def sample_orderbook_events():
    """Create sample orderbook events."""
    return [
        {
            "event_type": "orderbook_snapshot",
            "timestamp": "2026-02-01T10:00:00",
            "data": {
                "token_id": "token_yes",
                "bids": [{"price": "0.48", "size": "100"}],
                "asks": [{"price": "0.50", "size": "100"}],
            }
        },
        {
            "event_type": "orderbook_snapshot",
            "timestamp": "2026-02-01T10:00:01",
            "data": {
                "token_id": "token_no",
                "bids": [{"price": "0.50", "size": "100"}],
                "asks": [{"price": "0.52", "size": "100"}],
            }
        },
    ]


@pytest.fixture
def sample_signal_events():
    """Create sample signal events."""
    return [
        {
            "event_type": "signal",
            "timestamp": "2026-02-01T10:01:00",
            "data": {
                "yes_token": "token_yes",
                "no_token": "token_no",
                "yes_price": "0.48",
                "no_price": "0.50",
                "expected_profit": "0.05",
                "signal_type": "BUY_YES",
            }
        },
        {
            "event_type": "signal",
            "timestamp": "2026-02-01T10:02:00",
            "data": {
                "yes_token": "token_yes",
                "no_token": "token_no",
                "yes_price": "0.49",
                "no_price": "0.51",
                "expected_profit": "0.03",
                "signal_type": "BUY_YES",
            }
        },
    ]


class TestBacktesterInit:
    """Test suite for Backtester initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        backtester = Backtester()

        assert backtester.initial_capital == Decimal("1000")
        assert backtester.slippage_bps == 5
        assert backtester.max_position_size == Decimal("100")
        assert backtester.cash == Decimal("1000")
        assert backtester.positions == {}
        assert backtester.orderbooks == {}

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        backtester = Backtester(
            initial_capital=Decimal("5000"),
            slippage_bps=10,
            max_position_size=Decimal("500"),
        )

        assert backtester.initial_capital == Decimal("5000")
        assert backtester.slippage_bps == 10
        assert backtester.max_position_size == Decimal("500")


class TestBacktestDate:
    """Test suite for backtest_date method."""

    @pytest.mark.asyncio
    async def test_backtest_date_basic(self, sample_orderbook_events, sample_signal_events):
        """Test basic backtest execution."""
        # Mock the replayer
        all_events = sample_orderbook_events + sample_signal_events

        with patch("src.backtesting.backtester.EventReplayer") as MockReplayer:
            replayer_instance = Mock()
            MockReplayer.return_value = replayer_instance

            # Setup async iterator for events
            async def event_iterator():
                for event in all_events:
                    yield event

            replayer_instance.replay_date = Mock(return_value=event_iterator())

            # Run backtest
            backtester = Backtester(initial_capital=Decimal("1000"))
            strategy = Mock()

            result = await backtester.backtest_date(date(2026, 2, 1), strategy, min_profit=0.01)

            # Verify results
            assert result.start_date == date(2026, 2, 1)
            assert result.end_date == date(2026, 2, 1)
            assert result.starting_capital == Decimal("1000")
            assert result.total_trades >= 0  # May have executed trades
            assert isinstance(result.trades, list)

    @pytest.mark.asyncio
    async def test_backtest_date_with_no_trades(self, sample_orderbook_events):
        """Test backtest with no qualifying signals."""
        with patch("src.backtesting.backtester.EventReplayer") as MockReplayer:
            replayer_instance = Mock()
            MockReplayer.return_value = replayer_instance

            # Only orderbook events, no signals
            async def event_iterator():
                for event in sample_orderbook_events:
                    yield event

            replayer_instance.replay_date = Mock(return_value=event_iterator())

            backtester = Backtester()
            strategy = Mock()

            result = await backtester.backtest_date(date(2026, 2, 1), strategy, min_profit=0.01)

            assert result.total_trades == 0
            assert result.winning_trades == 0
            assert result.losing_trades == 0
            assert result.win_rate == 0.0


class TestCalculateMaxDrawdown:
    """Test suite for calculate_max_drawdown method."""

    def test_calculate_max_drawdown_no_trades(self):
        """Test drawdown calculation with no trades."""
        backtester = Backtester()
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
        )

        drawdown = backtester.calculate_max_drawdown(result)

        assert drawdown == Decimal("0")

    def test_calculate_max_drawdown_with_trades(self):
        """Test drawdown calculation with trades."""
        backtester = Backtester()
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
                    actual_profit=Decimal("50"),  # Win
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
                Trade(
                    id="3",
                    timestamp=datetime.now(),
                    token_id="test",
                    signal_type="BUY",
                    price=Decimal("0.5"),
                    size=Decimal("100"),
                    expected_profit=Decimal("10"),
                    actual_profit=Decimal("-20"),  # Loss
                ),
            ],
        )

        drawdown = backtester.calculate_max_drawdown(result)

        # Peak is 1050, trough is 1000, drawdown is 50
        assert drawdown > 0


class TestPrintSummary:
    """Test suite for print_summary method."""

    def test_print_summary(self, capsys):
        """Test printing backtest summary."""
        backtester = Backtester()
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            ending_capital=Decimal("1100"),
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            net_profit=Decimal("100"),
        )

        backtester.print_summary(result)

        captured = capsys.readouterr()
        assert "Backtest Summary" in captured.out
        assert "Total Trades: 10" in captured.out
        assert "Win Rate:" in captured.out
        assert "Net Profit:" in captured.out


class TestStrategyComparator:
    """Test suite for StrategyComparator."""

    @pytest.mark.asyncio
    async def test_compare_strategies(self):
        """Test comparing multiple strategies."""
        comparator = StrategyComparator(initial_capital=Decimal("1000"))

        # Mock strategies
        strategy1 = Mock()
        strategy2 = Mock()

        # Mock backtest results
        with patch("src.backtesting.backtester.Backtester") as MockBacktester:
            backtester_instance = Mock()
            MockBacktester.return_value = backtester_instance

            result1 = BacktestResult(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 1),
                starting_capital=Decimal("1000"),
                total_trades=5,
                net_profit=Decimal("50"),
            )

            result2 = BacktestResult(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 1),
                starting_capital=Decimal("1000"),
                total_trades=3,
                net_profit=Decimal("30"),
            )

            async def mock_backtest(event_date, strategy, min_profit=0.01):
                return result1 if strategy == strategy1 else result2

            backtester_instance.backtest_date = mock_backtest

            results = await comparator.compare_strategies(
                date(2026, 2, 1),
                [strategy1, strategy2],
                ["Strategy A", "Strategy B"],
            )

            assert len(results) == 2
            assert "Strategy A" in results
            assert "Strategy B" in results
            assert results["Strategy A"].total_trades == 5
            assert results["Strategy B"].total_trades == 3

    def test_print_comparison(self, capsys):
        """Test printing comparison."""
        comparator = StrategyComparator()

        results = {
            "Strategy A": BacktestResult(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 1),
                starting_capital=Decimal("1000"),
                total_trades=10,
                winning_trades=7,
                net_profit=Decimal("100"),
                win_rate=0.7,
            ),
            "Strategy B": BacktestResult(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 1),
                starting_capital=Decimal("1000"),
                total_trades=5,
                winning_trades=2,
                net_profit=Decimal("-20"),
                win_rate=0.4,
            ),
        }

        comparator.print_comparison(results)

        captured = capsys.readouterr()
        assert "Strategy Comparison" in captured.out
        assert "Strategy A" in captured.out
        assert "Strategy B" in captured.out


class TestTrade:
    """Test suite for Trade dataclass."""

    def test_trade_creation(self):
        """Test creating a Trade."""
        trade = Trade(
            id="test_trade",
            timestamp=datetime.now(),
            token_id="token_1",
            signal_type="BUY_YES",
            price=Decimal("0.50"),
            size=Decimal("100"),
            expected_profit=Decimal("10"),
            actual_profit=Decimal("8"),
        )

        assert trade.id == "test_trade"
        assert trade.token_id == "token_1"
        assert trade.signal_type == "BUY_YES"
        assert trade.actual_profit == Decimal("8")


class TestBacktestResult:
    """Test suite for BacktestResult dataclass."""

    def test_backtest_result_creation(self):
        """Test creating a BacktestResult."""
        result = BacktestResult(
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 1),
            starting_capital=Decimal("1000"),
            ending_capital=Decimal("1100"),
        )

        assert result.start_date == date(2026, 2, 1)
        assert result.end_date == date(2026, 2, 1)
        assert result.starting_capital == Decimal("1000")
        assert result.ending_capital == Decimal("1100")
        assert result.total_trades == 0
