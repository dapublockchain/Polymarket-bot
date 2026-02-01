"""
Unit tests for Fill model.

Tests the unified Fill dataclass used for both simulated and real fills.
"""
import pytest
from decimal import Decimal
from datetime import datetime

from src.execution.fill import Fill, FillSide


class TestFillSide:
    """Test FillSide enum."""

    def test_fill_side_values(self):
        """Test FillSide enum values."""
        assert FillSide.BUY.value == "buy"
        assert FillSide.SELL.value == "sell"

    def test_fill_side_comparison(self):
        """Test FillSide comparison."""
        assert FillSide.BUY == FillSide.BUY
        assert FillSide.BUY != FillSide.SELL


class TestFill:
    """Test Fill dataclass."""

    @pytest.fixture
    def buy_fill(self):
        """Create a sample buy fill."""
        return Fill(
            fill_id="fill_123",
            order_request_id="order_456",
            token_id="token_abc",
            side=FillSide.BUY,
            price=Decimal("0.65"),
            quantity=Decimal("100"),
            fees=Decimal("0.35"),
            timestamp_ms=1234567890,
            trace_id="trace_789",
            is_simulated=True,
            slippage_bps=5,
        )

    @pytest.fixture
    def sell_fill(self):
        """Create a sample sell fill."""
        return Fill(
            fill_id="fill_124",
            order_request_id="order_457",
            token_id="token_def",
            side=FillSide.SELL,
            price=Decimal("0.35"),
            quantity=Decimal("50"),
            fees=Decimal("0.175"),
            timestamp_ms=1234567891,
            trace_id="trace_790",
            is_simulated=False,
            tx_hash="0xabc123",
            on_chain_filled=True,
        )

    def test_fill_creation(self, buy_fill):
        """Test fill object creation."""
        assert buy_fill.fill_id == "fill_123"
        assert buy_fill.side == FillSide.BUY
        assert buy_fill.price == Decimal("0.65")
        assert buy_fill.quantity == Decimal("100")
        assert buy_fill.is_simulated is True
        assert buy_fill.slippage_bps == 5

    def test_notional_usdc_calculation(self, buy_fill):
        """Test notional USDC calculation."""
        expected = Decimal("0.65") * Decimal("100")  # 65.0
        assert buy_fill.notional_usdc == expected

    def test_net_proceeds_buy(self, buy_fill):
        """Test net proceeds for buy fill (should be negative)."""
        # Buy: -notional - fees
        # -65.0 - 0.35 = -65.35
        expected = -Decimal("65.0") - Decimal("0.35")
        assert buy_fill.net_proceeds == expected

    def test_net_proceeds_sell(self, sell_fill):
        """Test net proceeds for sell fill (should be positive)."""
        # Sell: +notional - fees
        # 0.35 * 50 = 17.5
        # 17.5 - 0.175 = 17.325
        expected = Decimal("17.5") - Decimal("0.175")
        assert sell_fill.net_proceeds == expected

    def test_to_dict(self, buy_fill):
        """Test Fill to_dict serialization."""
        fill_dict = buy_fill.to_dict()

        assert fill_dict["fill_id"] == "fill_123"
        assert fill_dict["side"] == "buy"
        assert fill_dict["price"] == "0.65"
        assert fill_dict["quantity"] == "100"
        assert fill_dict["is_simulated"] is True
        assert fill_dict["slippage_bps"] == 5

    def test_to_dict_with_tx_hash(self, sell_fill):
        """Test to_dict includes tx_hash for real fills."""
        fill_dict = sell_fill.to_dict()

        assert fill_dict["tx_hash"] == "0xabc123"
        assert fill_dict["on_chain_filled"] is True

    def test_simulated_fill_attributes(self, buy_fill):
        """Test simulated fill has slippage but no tx_hash."""
        assert buy_fill.is_simulated is True
        assert buy_fill.slippage_bps == 5
        assert buy_fill.tx_hash is None
        assert buy_fill.on_chain_filled is False

    def test_real_fill_attributes(self, sell_fill):
        """Test real fill has tx_hash but no slippage."""
        assert sell_fill.is_simulated is False
        assert sell_fill.tx_hash == "0xabc123"
        assert sell_fill.on_chain_filled is True
        assert sell_fill.slippage_bps is None

    def test_fill_decimal_precision(self):
        """Test that Fill handles decimal precision correctly."""
        fill = Fill(
            fill_id="fill_precision",
            order_request_id="order_precision",
            token_id="token_precision",
            side=FillSide.BUY,
            price=Decimal("0.333333333333333333"),
            quantity=Decimal("1000"),
            fees=Decimal("0.001"),
            timestamp_ms=1234567890,
            trace_id="trace_precision",
            is_simulated=True,
        )

        # Should preserve full precision
        assert fill.price == Decimal("0.333333333333333333")
        expected_notional = Decimal("333.333333333333333000")
        assert fill.notional_usdc == expected_notional

    def test_fill_with_zero_quantity(self):
        """Test Fill handles zero quantity edge case."""
        fill = Fill(
            fill_id="fill_zero",
            order_request_id="order_zero",
            token_id="token_zero",
            side=FillSide.BUY,
            price=Decimal("0.50"),
            quantity=Decimal("0"),
            fees=Decimal("0"),
            timestamp_ms=1234567890,
            trace_id="trace_zero",
            is_simulated=True,
        )

        assert fill.quantity == Decimal("0")
        assert fill.notional_usdc == Decimal("0")
        assert fill.net_proceeds == Decimal("0")

    def test_fill_with_high_fees(self):
        """Test Fill with high fees (stress test)."""
        fill = Fill(
            fill_id="fill_high_fees",
            order_request_id="order_high_fees",
            token_id="token_high_fees",
            side=FillSide.BUY,
            price=Decimal("1.0"),
            quantity=Decimal("100"),
            fees=Decimal("50.0"),  # 50% fee!
            timestamp_ms=1234567890,
            trace_id="trace_high_fees",
            is_simulated=True,
        )

        # -100 - 50 = -150
        assert fill.net_proceeds == -Decimal("150.0")
