"""
Unit tests for Risk Manager.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock

from src.execution.risk_manager import RiskManager
from src.core.models import Signal, ArbitrageOpportunity


class TestRiskManagerInitialization:
    """Test suite for RiskManager initialization."""

    def test_initialization_with_defaults(self):
        """Test that RiskManager initializes with default values."""
        risk_mgr = RiskManager()

        assert risk_mgr.max_position_size == Decimal("1000")
        assert risk_mgr.min_profit_threshold == Decimal("0.01")
        assert risk_mgr.max_gas_cost == Decimal("1.0")

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        risk_mgr = RiskManager(
            max_position_size=Decimal("500"),
            min_profit_threshold=Decimal("0.02"),
            max_gas_cost=Decimal("0.5"),
        )

        assert risk_mgr.max_position_size == Decimal("500")
        assert risk_mgr.min_profit_threshold == Decimal("0.02")
        assert risk_mgr.max_gas_cost == Decimal("0.5")


class TestValidateSignal:
    """Test suite for signal validation."""

    @pytest.fixture
    def risk_mgr(self):
        """Create a RiskManager for testing."""
        return RiskManager(
            max_position_size=Decimal("1000"),
            min_profit_threshold=Decimal("0.01"),
            max_gas_cost=Decimal("1.0"),
        )

    @pytest.fixture
    def profitable_signal(self):
        """Create a profitable trading signal."""
        return Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.5"),  # $0.50 profit
            trade_size=Decimal("10"),  # $10 trade
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Profitable arbitrage opportunity",
        )

    def test_validate_profitable_signal(self, risk_mgr, profitable_signal):
        """Test that a profitable signal passes validation."""
        balance = Decimal("100")  # $100 USDC
        gas_cost = Decimal("0.1")  # $0.10 gas

        is_valid = risk_mgr.validate_signal(profitable_signal, balance, gas_cost)

        assert is_valid is True

    def test_reject_insufficient_balance(self, risk_mgr, profitable_signal):
        """Test that signal is rejected when balance is insufficient."""
        balance = Decimal("5")  # Only $5, but trade needs $10
        gas_cost = Decimal("0.1")

        is_valid = risk_mgr.validate_signal(profitable_signal, balance, gas_cost)

        assert is_valid is False

    def test_reject_unprofitable_signal(self, risk_mgr):
        """Test that unprofitable signal is rejected."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.005"),  # Only $0.005 profit (below 1% threshold)
            trade_size=Decimal("10"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Low profit opportunity",
        )

        balance = Decimal("100")
        gas_cost = Decimal("0.1")

        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is False

    def test_reject_gas_exceeds_profit(self, risk_mgr):
        """Test that signal is rejected when gas cost exceeds profit."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.05"),  # $0.05 profit
            trade_size=Decimal("10"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Small profit opportunity",
        )

        balance = Decimal("100")
        gas_cost = Decimal("0.10")  # $0.10 gas, more than profit

        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is False

    def test_reject_position_size_exceeded(self, risk_mgr):
        """Test that signal is rejected when position size exceeds limit."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("50"),  # $50 profit
            trade_size=Decimal("2000"),  # $2000 position (exceeds $1000 limit)
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Large position",
        )

        balance = Decimal("5000")
        gas_cost = Decimal("0.1")

        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is False

    def test_reject_gas_cost_too_high(self, risk_mgr, profitable_signal):
        """Test that signal is rejected when gas cost is too high."""
        balance = Decimal("100")
        gas_cost = Decimal("2.0")  # $2.00 gas (exceeds $1.00 max)

        is_valid = risk_mgr.validate_signal(profitable_signal, balance, gas_cost)

        assert is_valid is False

    def test_reject_zero_balance(self, risk_mgr, profitable_signal):
        """Test that signal is rejected when balance is zero."""
        balance = Decimal("0")
        gas_cost = Decimal("0.1")

        is_valid = risk_mgr.validate_signal(profitable_signal, balance, gas_cost)

        assert is_valid is False

    def test_accept_exactly_at_threshold(self, risk_mgr):
        """Test signal exactly at minimum profit threshold."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.10"),  # Exactly 1% of $10 trade
            trade_size=Decimal("10"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Threshold profit",
        )

        balance = Decimal("100")
        gas_cost = Decimal("0.01")

        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is True

    def test_accept_maximum_position_size(self, risk_mgr):
        """Test signal at maximum position size."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("10"),  # $10 profit
            trade_size=Decimal("1000"),  # Exactly $1000 limit
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Max position",
        )

        balance = Decimal("2000")
        gas_cost = Decimal("0.1")

        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is True


class TestCalculateGasCost:
    """Test suite for gas cost calculation."""

    @pytest.fixture
    def risk_mgr(self):
        """Create a RiskManager for testing."""
        return RiskManager()

    def test_calculate_gas_cost_basic(self, risk_mgr):
        """Test basic gas cost calculation."""
        gas_price = 50_000_000_000  # 50 gwei in wei
        gas_limit = 100_000  # 100k gas units

        cost = risk_mgr.calculate_gas_cost(gas_price, gas_limit)

        # 50 gwei * 100k = 5,000,000,000,000 wei = 0.005 MATIC
        # Assuming 1 MATIC = $1 (simplified)
        expected = Decimal("0.005")
        assert abs(cost - expected) < Decimal("0.0001")

    def test_calculate_gas_cost_high_gas(self, risk_mgr):
        """Test gas cost calculation with high gas price."""
        gas_price = 200_000_000_000  # 200 gwei
        gas_limit = 300_000  # 300k gas

        cost = risk_mgr.calculate_gas_cost(gas_price, gas_limit)

        # 200 gwei * 300k = 60,000,000,000,000 wei = 0.06 MATIC
        expected = Decimal("0.06")
        assert abs(cost - expected) < Decimal("0.0001")

    def test_calculate_gas_cost_zero_gas(self, risk_mgr):
        """Test gas cost calculation with zero gas."""
        gas_price = 0
        gas_limit = 100_000

        cost = risk_mgr.calculate_gas_cost(gas_price, gas_limit)

        assert cost == Decimal("0")

    def test_calculate_gas_cost_very_high(self, risk_mgr):
        """Test gas cost calculation with very high values."""
        gas_price = 500_000_000_000  # 500 gwei
        gas_limit = 1_000_000  # 1M gas

        cost = risk_mgr.calculate_gas_cost(gas_price, gas_limit)

        # 500 gwei * 1M = 500,000,000,000,000,000 wei = 0.5 MATIC
        expected = Decimal("0.5")
        assert abs(cost - expected) < Decimal("0.001")


class TestCheckPositionLimit:
    """Test suite for position limit checking."""

    @pytest.fixture
    def risk_mgr(self):
        """Create a RiskManager for testing."""
        return RiskManager(max_position_size=Decimal("1000"))

    def test_position_within_limit(self, risk_mgr):
        """Test position size within limit."""
        size = Decimal("500")
        max_position = Decimal("1000")

        is_valid = risk_mgr.check_position_limit(size, max_position)

        assert is_valid is True

    def test_position_at_limit(self, risk_mgr):
        """Test position size exactly at limit."""
        size = Decimal("1000")
        max_position = Decimal("1000")

        is_valid = risk_mgr.check_position_limit(size, max_position)

        assert is_valid is True

    def test_position_exceeds_limit(self, risk_mgr):
        """Test position size exceeds limit."""
        size = Decimal("1500")
        max_position = Decimal("1000")

        is_valid = risk_mgr.check_position_limit(size, max_position)

        assert is_valid is False

    def test_position_very_small(self, risk_mgr):
        """Test very small position size."""
        size = Decimal("0.01")
        max_position = Decimal("1000")

        is_valid = risk_mgr.check_position_limit(size, max_position)

        assert is_valid is True

    def test_position_zero(self, risk_mgr):
        """Test zero position size."""
        size = Decimal("0")
        max_position = Decimal("1000")

        is_valid = risk_mgr.check_position_limit(size, max_position)

        assert is_valid is True


class TestEstimateTotalCost:
    """Test suite for total cost estimation."""

    @pytest.fixture
    def risk_mgr(self):
        """Create a RiskManager for testing."""
        return RiskManager()

    @pytest.fixture
    def arbitrage_signal(self):
        """Create an arbitrage opportunity signal."""
        return ArbitrageOpportunity(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="ARBITRAGE",
            expected_profit=Decimal("0.5"),
            trade_size=Decimal("10"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Arbitrage opportunity",
            yes_token_id="yes_123",
            no_token_id="no_123",
            yes_cost=Decimal("4.8"),
            no_cost=Decimal("5.0"),
            total_cost=Decimal("9.8"),
            fees=Decimal("0.07"),
            gas_estimate=Decimal("0.1"),
            net_profit=Decimal("0.33"),
        )

    def test_estimate_total_cost_with_gas(self, risk_mgr, arbitrage_signal):
        """Test total cost estimation including gas."""
        gas_cost = Decimal("0.15")

        total_cost = risk_mgr.estimate_total_cost(arbitrage_signal, gas_cost)

        # total_cost (9.8) + gas (0.15) = 9.95
        expected = Decimal("9.95")
        assert total_cost == expected

    def test_estimate_total_cost_zero_gas(self, risk_mgr, arbitrage_signal):
        """Test total cost with zero gas."""
        gas_cost = Decimal("0")

        total_cost = risk_mgr.estimate_total_cost(arbitrage_signal, gas_cost)

        # total_cost (9.8) + gas (0) = 9.8
        expected = Decimal("9.8")
        assert total_cost == expected

    def test_estimate_total_cost_high_gas(self, risk_mgr, arbitrage_signal):
        """Test total cost with high gas."""
        gas_cost = Decimal("1.5")

        total_cost = risk_mgr.estimate_total_cost(arbitrage_signal, gas_cost)

        # total_cost (9.8) + gas (1.5) = 11.3
        expected = Decimal("11.3")
        assert total_cost == expected


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.fixture
    def risk_mgr(self):
        """Create a RiskManager for testing."""
        return RiskManager(
            max_position_size=Decimal("1000"),
            min_profit_threshold=Decimal("0.01"),
            max_gas_cost=Decimal("1.0"),
        )

    def test_validate_signal_with_negative_profit(self, risk_mgr):
        """Test validation with negative profit (should fail at model level)."""
        from pydantic import ValidationError

        # Signal model validates non-negative profit
        with pytest.raises(ValidationError, match="Expected profit and trade size must be non-negative"):
            Signal(
                strategy="atomic_arbitrage",
                token_id="yes_123",
                signal_type="BUY_YES",
                expected_profit=Decimal("-0.1"),  # Negative!
                trade_size=Decimal("10"),
                yes_price=Decimal("0.48"),
                no_price=Decimal("0.50"),
                confidence=0.95,
                reason="Bad trade",
            )

    def test_validate_signal_with_zero_trade_size(self, risk_mgr):
        """Test validation with zero trade size."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0"),
            trade_size=Decimal("0"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="No trade",
        )

        balance = Decimal("100")
        gas_cost = Decimal("0.1")

        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is False

    def test_validate_with_negative_gas_cost(self, risk_mgr):
        """Test validation with negative gas cost (should handle gracefully)."""
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.5"),
            trade_size=Decimal("10"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Good trade",
        )

        balance = Decimal("100")
        gas_cost = Decimal("-0.1")  # Negative gas (invalid)

        # Should reject negative gas cost
        is_valid = risk_mgr.validate_signal(signal, balance, gas_cost)

        assert is_valid is False
