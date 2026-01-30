"""
Integration tests for Execution Layer.

Tests the interaction between Web3Client, RiskManager, and TxSender.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.connectors.web3_client import Web3Client
from src.execution.risk_manager import RiskManager
from src.execution.tx_sender import TxSender
from src.core.models import Signal


class TestExecutionLayerIntegration:
    """Integration tests for the complete execution layer."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )

            # Mock async methods
            client.get_balance = AsyncMock(return_value=Decimal("1000"))
            client.estimate_eip1559_gas = AsyncMock(
                return_value={"maxFeePerGas": 50_000_000_000, "maxPriorityFeePerGas": 2_000_000_000}
            )
            client.estimate_gas = AsyncMock(return_value=100_000)
            client.get_nonce = AsyncMock(return_value=0)
            client.sign_transaction = AsyncMock(return_value=b"signed_tx")
            client.send_transaction = AsyncMock(return_value="0xabc123")
            client.get_transaction_receipt = AsyncMock(return_value=None)

            yield client

    @pytest.fixture
    def risk_manager(self):
        """Create a RiskManager."""
        return RiskManager(
            max_position_size=Decimal("1000"),
            min_profit_threshold=Decimal("0.01"),
            max_gas_cost=Decimal("1.0"),
        )

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager):
        """Create a TxSender."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            max_retries=3,
            retry_delay=0.1,
        )

    @pytest.fixture
    def profitable_signal(self):
        """Create a profitable signal."""
        return Signal(
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

    @pytest.mark.asyncio
    async def test_full_execution_flow(self, tx_sender, profitable_signal, web3_client):
        """Test the complete execution flow from signal to transaction."""
        # Execute signal
        tx_hash = await tx_sender.execute_signal(profitable_signal)

        # Verify transaction was executed
        assert tx_hash == "0xabc123"

        # Verify all steps were called
        web3_client.get_balance.assert_called_once()
        web3_client.estimate_eip1559_gas.assert_called_once()
        web3_client.estimate_gas.assert_called_once()
        web3_client.get_nonce.assert_called_once()
        web3_client.sign_transaction.assert_called_once()
        web3_client.send_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejection_by_risk_manager(self, tx_sender, web3_client):
        """Test that unprofitable signals are rejected."""
        # Create unprofitable signal
        signal = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_123",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.005"),  # Below 1% threshold
            trade_size=Decimal("10"),
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            confidence=0.95,
            reason="Low profit trade",
        )

        # Execute signal
        tx_hash = await tx_sender.execute_signal(signal)

        # Verify transaction was not executed
        assert tx_hash is None

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, tx_sender, web3_client, profitable_signal):
        """Test that signals are rejected when balance is insufficient."""
        # Set low balance
        web3_client.get_balance = AsyncMock(return_value=Decimal("5"))

        # Execute signal
        tx_hash = await tx_sender.execute_signal(profitable_signal)

        # Verify transaction was not executed
        assert tx_hash is None

    @pytest.mark.asyncio
    async def test_queue_and_process_multiple_signals(self, tx_sender, web3_client):
        """Test queuing and processing multiple signals."""
        # Create multiple signals
        signals = [
            Signal(
                strategy="atomic_arbitrage",
                token_id=f"yes_{i}",
                signal_type="BUY_YES",
                expected_profit=Decimal("0.5"),
                trade_size=Decimal("10"),
                yes_price=Decimal("0.48"),
                no_price=Decimal("0.50"),
                confidence=0.95,
                reason=f"Trade {i}",
            )
            for i in range(3)
        ]

        # Queue all signals
        for signal in signals:
            await tx_sender.queue_transaction(signal)

        # Process queue
        results = await tx_sender.process_queue()

        # Verify all signals were processed
        assert len(results) == 3
        assert all(r["success"] for r in results)
        assert len(tx_sender.transaction_queue) == 0

    @pytest.mark.asyncio
    async def test_transaction_retry_mechanism(self, tx_sender, web3_client, profitable_signal):
        """Test that failed transactions are retried."""
        # First two attempts fail, third succeeds
        web3_client.send_transaction = AsyncMock(
            side_effect=[Exception("Network error"), Exception("Network error"), "0xabc123"]
        )

        # Execute signal
        tx_hash = await tx_sender.execute_signal(profitable_signal)

        # Verify transaction eventually succeeded
        assert tx_hash == "0xabc123"
        assert web3_client.send_transaction.call_count == 3

    @pytest.mark.asyncio
    async def test_gas_cost_calculation_accuracy(self, tx_sender, web3_client, risk_manager):
        """Test that gas costs are calculated accurately."""
        # Set specific gas parameters
        web3_client.estimate_eip1559_gas = AsyncMock(
            return_value={"maxFeePerGas": 100_000_000_000, "maxPriorityFeePerGas": 2_000_000_000}  # 100 gwei
        )
        web3_client.estimate_gas = AsyncMock(return_value=200_000)  # 200k gas

        # Execute signal
        await tx_sender.execute_signal(
            Signal(
                strategy="atomic_arbitrage",
                token_id="yes_123",
                signal_type="BUY_YES",
                expected_profit=Decimal("0.5"),
                trade_size=Decimal("10"),
                yes_price=Decimal("0.48"),
                no_price=Decimal("0.50"),
                confidence=0.95,
                reason="Test trade",
            )
        )

        # Verify gas cost was calculated
        gas_cost = risk_manager.calculate_gas_cost(100_000_000_000, 200_000)
        expected_cost = Decimal("0.02")  # 100 gwei * 200k gas = 0.02 MATIC
        assert gas_cost == expected_cost

    @pytest.mark.asyncio
    async def test_slippage_protection(self, tx_sender):
        """Test that slippage protection is applied."""
        # Test buy side slippage
        buy_limit = tx_sender._calculate_slippage_limit(
            expected_price=Decimal("0.50"),
            side="buy"
        )
        assert buy_limit == Decimal("0.51")  # 2% higher

        # Test sell side slippage
        sell_limit = tx_sender._calculate_slippage_limit(
            expected_price=Decimal("0.50"),
            side="sell"
        )
        assert sell_limit == Decimal("0.49")  # 2% lower

    @pytest.mark.asyncio
    async def test_transaction_status_checking(self, tx_sender, web3_client):
        """Test transaction status checking."""
        # Test pending transaction
        web3_client.get_transaction_receipt = AsyncMock(return_value=None)
        status = await tx_sender.check_transaction_status("0xabc123")
        assert status.value == "pending"

        # Test confirmed transaction
        web3_client.get_transaction_receipt = AsyncMock(
            return_value={"status": 1, "blockNumber": 12345}
        )
        status = await tx_sender.check_transaction_status("0xabc123")
        assert status.value == "confirmed"

        # Test failed transaction
        web3_client.get_transaction_receipt = AsyncMock(
            return_value={"status": 0, "blockNumber": 12345}
        )
        status = await tx_sender.check_transaction_status("0xabc123")
        assert status.value == "failed"
