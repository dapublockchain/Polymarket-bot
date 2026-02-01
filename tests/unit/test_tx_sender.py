"""
Unit tests for Transaction Sender.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.execution.tx_sender import TxSender, TxStatus, TxResult
from src.core.models import Signal
from src.execution.risk_manager import RiskManager
from src.execution.nonce_manager import NonceManager


class TestTxSenderInitialization:
    """Test suite for TxSender initialization."""

    def test_initialization_with_defaults(self):
        """Test that TxSender initializes with default values."""
        with patch("src.execution.tx_sender.Web3Client") as mock_web3_client:
            with patch("src.execution.tx_sender.RiskManager") as mock_risk_mgr:
                with patch("src.execution.tx_sender.NonceManager") as mock_nonce_mgr:
                    sender = TxSender(
                        web3_client=mock_web3_client,
                        risk_manager=mock_risk_mgr,
                        nonce_manager=mock_nonce_mgr,
                    )

                    assert sender.web3_client == mock_web3_client
                    assert sender.risk_manager == mock_risk_mgr
                    assert sender.nonce_manager == mock_nonce_mgr
                    assert sender.slippage_tolerance == Decimal("0.02")
                    assert sender._total_executions == 0
                    assert sender._successful_executions == 0

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        with patch("src.execution.tx_sender.Web3Client") as mock_web3_client:
            with patch("src.execution.tx_sender.RiskManager") as mock_risk_mgr:
                with patch("src.execution.tx_sender.RetryPolicy") as mock_retry:
                    with patch("src.execution.tx_sender.NonceManager") as mock_nonce_mgr:
                        sender = TxSender(
                            web3_client=mock_web3_client,
                            risk_manager=mock_risk_mgr,
                            nonce_manager=mock_nonce_mgr,
                            retry_policy=mock_retry,
                            slippage_tolerance=Decimal("0.01"),
                        )

                        assert sender.slippage_tolerance == Decimal("0.01")
                        assert sender.retry_policy == mock_retry


class TestExecuteSignal:
    """Test suite for signal execution."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        client = Mock()
        client.address = "0x1234567890123456789012345678901234567890"
        client.get_balance = AsyncMock(return_value=Decimal("100"))
        client.estimate_eip1559_gas = AsyncMock(
            return_value={"maxFeePerGas": 50_000_000_000, "maxPriorityFeePerGas": 2_000_000_000}
        )
        client.estimate_gas = AsyncMock(return_value=100_000)
        client.sign_transaction = AsyncMock(return_value=b"signed_tx")
        client.send_transaction = AsyncMock(return_value="0xabc123")
        client.get_transaction_receipt = AsyncMock(return_value=None)
        return client

    @pytest.fixture
    def risk_manager(self):
        """Create a mock RiskManager."""
        risk_mgr = Mock(spec=RiskManager)
        risk_mgr.validate_signal = Mock(return_value=True)
        risk_mgr.calculate_gas_cost = Mock(return_value=Decimal("0.1"))
        risk_mgr.estimate_total_cost = Mock(return_value=Decimal("10.1"))
        return risk_mgr

    @pytest.fixture
    def nonce_manager(self):
        """Create a mock NonceManager."""
        nonce_mgr = Mock(spec=NonceManager)
        nonce_mgr.allocate_nonce = AsyncMock(return_value=0)
        nonce_mgr.mark_confirmed = Mock()
        nonce_mgr.mark_failed = Mock()
        nonce_mgr.get_stats = Mock(return_value={"pending_count": 0})
        return nonce_mgr

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager, nonce_manager):
        """Create a TxSender for testing."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
        )

    @pytest.fixture
    def valid_signal(self):
        """Create a valid trading signal."""
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
    async def test_execute_signal_success(self, tx_sender, valid_signal, web3_client, risk_manager):
        """Test successful signal execution."""
        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is True
        assert result.tx_hash == "0xabc123"
        risk_manager.validate_signal.assert_called_once()
        web3_client.get_balance.assert_called_once()
        web3_client.estimate_gas.assert_called_once()
        web3_client.sign_transaction.assert_called_once()
        web3_client.send_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_signal_fails_validation(self, tx_sender, valid_signal, risk_manager):
        """Test that execution fails when signal is invalid."""
        risk_manager.validate_signal.return_value = False

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False
        assert "Risk manager rejection" in result.error
        risk_manager.validate_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_signal_insufficient_balance(self, tx_sender, valid_signal, web3_client, risk_manager):
        """Test execution fails with insufficient balance."""
        # Mock balance to be insufficient
        web3_client.get_balance = AsyncMock(return_value=Decimal("5"))  # Only $5, need $10

        # Risk manager should reject the signal
        risk_manager.validate_signal.return_value = False

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False
        risk_manager.validate_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_signal_retry_on_failure(self, tx_sender, valid_signal, web3_client):
        """Test that execution retries on transaction failure."""
        # First two attempts fail, third succeeds
        web3_client.send_transaction = AsyncMock(
            side_effect=[Exception("Network error"), Exception("Network error"), "0xabc123"]
        )

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is True
        assert result.tx_hash == "0xabc123"
        assert web3_client.send_transaction.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_signal_max_retries_exceeded(self, tx_sender, valid_signal, web3_client):
        """Test that execution fails after max retries."""
        web3_client.send_transaction = AsyncMock(
            side_effect=Exception("Network error")
        )

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False
        assert result.error is not None
        assert web3_client.send_transaction.call_count > 1

    @pytest.mark.asyncio
    async def test_execute_signal_gas_estimation_failure(self, tx_sender, valid_signal, web3_client):
        """Test handling of gas estimation failure."""
        web3_client.estimate_gas.side_effect = Exception("Gas estimation failed")

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_signing_failure(self, tx_sender, valid_signal, web3_client):
        """Test handling of transaction signing failure."""
        web3_client.sign_transaction.side_effect = Exception("Signing failed")

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False


class TestQueueTransaction:
    """Test suite for transaction queuing."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        client = Mock()
        return client

    @pytest.fixture
    def risk_manager(self):
        """Create a mock RiskManager."""
        return Mock(spec=RiskManager)

    @pytest.fixture
    def nonce_manager(self):
        """Create a mock NonceManager."""
        return Mock(spec=NonceManager)

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager, nonce_manager):
        """Create a TxSender for testing."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
        )

    @pytest.fixture
    def valid_signal(self):
        """Create a valid trading signal."""
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
    async def test_queue_single_transaction(self, tx_sender, valid_signal):
        """Test queuing a single transaction."""
        await tx_sender.queue_transaction(valid_signal)

        assert len(tx_sender.transaction_queue) == 1
        assert tx_sender.transaction_queue[0] == valid_signal

    @pytest.mark.asyncio
    async def test_queue_multiple_transactions(self, tx_sender, valid_signal):
        """Test queuing multiple transactions."""
        signal2 = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_456",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.3"),
            trade_size=Decimal("10"),
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.52"),
            confidence=0.90,
            reason="Another trade",
        )

        await tx_sender.queue_transaction(valid_signal)
        await tx_sender.queue_transaction(signal2)

        assert len(tx_sender.transaction_queue) == 2
        assert tx_sender.transaction_queue[0] == valid_signal
        assert tx_sender.transaction_queue[1] == signal2


class TestProcessQueue:
    """Test suite for queue processing."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        client = Mock()
        client.address = "0x1234567890123456789012345678901234567890"
        client.get_balance = AsyncMock(return_value=Decimal("1000"))
        client.estimate_eip1559_gas = AsyncMock(
            return_value={"maxFeePerGas": 50_000_000_000, "maxPriorityFeePerGas": 2_000_000_000}
        )
        client.estimate_gas = AsyncMock(return_value=100_000)
        client.sign_transaction = AsyncMock(return_value=b"signed_tx")
        client.send_transaction = AsyncMock(return_value="0xabc123")
        return client

    @pytest.fixture
    def risk_manager(self):
        """Create a mock RiskManager."""
        risk_mgr = Mock(spec=RiskManager)
        risk_mgr.validate_signal = Mock(return_value=True)
        risk_mgr.calculate_gas_cost = Mock(return_value=Decimal("0.1"))
        risk_mgr.estimate_total_cost = Mock(return_value=Decimal("10.1"))
        return risk_mgr

    @pytest.fixture
    def nonce_manager(self):
        """Create a mock NonceManager."""
        nonce_mgr = Mock(spec=NonceManager)
        nonce_mgr.allocate_nonce = AsyncMock(return_value=0)
        nonce_mgr.mark_confirmed = Mock()
        return nonce_mgr

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager, nonce_manager):
        """Create a TxSender for testing."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
        )

    @pytest.fixture
    def valid_signal(self):
        """Create a valid trading signal."""
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
    async def test_process_empty_queue(self, tx_sender):
        """Test processing an empty queue."""
        results = await tx_sender.process_queue()

        assert results == []

    @pytest.mark.asyncio
    async def test_process_single_transaction(self, tx_sender, valid_signal):
        """Test processing a single queued transaction."""
        await tx_sender.queue_transaction(valid_signal)

        results = await tx_sender.process_queue()

        assert len(results) == 1
        assert results[0].signal == valid_signal
        assert results[0].tx_hash == "0xabc123"
        assert results[0].success is True
        assert len(tx_sender.transaction_queue) == 0

    @pytest.mark.asyncio
    async def test_process_multiple_transactions(self, tx_sender, valid_signal):
        """Test processing multiple queued transactions."""
        signal2 = Signal(
            strategy="atomic_arbitrage",
            token_id="yes_456",
            signal_type="BUY_YES",
            expected_profit=Decimal("0.3"),
            trade_size=Decimal("10"),
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.52"),
            confidence=0.90,
            reason="Another trade",
        )

        await tx_sender.queue_transaction(valid_signal)
        await tx_sender.queue_transaction(signal2)

        results = await tx_sender.process_queue()

        assert len(results) == 2
        assert len(tx_sender.transaction_queue) == 0

    @pytest.mark.asyncio
    async def test_process_queue_with_failure(self, tx_sender, valid_signal, web3_client):
        """Test processing queue with one failed transaction."""
        web3_client.send_transaction = AsyncMock(side_effect=Exception("Network error"))

        await tx_sender.queue_transaction(valid_signal)

        results = await tx_sender.process_queue()

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error is not None


class TestCheckTransactionStatus:
    """Test suite for transaction status checking."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        client = Mock()
        return client

    @pytest.fixture
    def risk_manager(self):
        """Create a mock RiskManager."""
        return Mock(spec=RiskManager)

    @pytest.fixture
    def nonce_manager(self):
        """Create a mock NonceManager."""
        return Mock(spec=NonceManager)

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager, nonce_manager):
        """Create a TxSender for testing."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
        )

    @pytest.mark.asyncio
    async def test_check_pending_transaction(self, tx_sender, web3_client):
        """Test checking status of pending transaction."""
        web3_client.get_transaction_receipt = AsyncMock(return_value=None)

        status = await tx_sender.check_transaction_status("0xabc123")

        assert status == TxStatus.PENDING

    @pytest.mark.asyncio
    async def test_check_confirmed_transaction(self, tx_sender, web3_client):
        """Test checking status of confirmed transaction."""
        web3_client.get_transaction_receipt = AsyncMock(
            return_value={"status": 1, "blockNumber": 12345}
        )

        status = await tx_sender.check_transaction_status("0xabc123")

        assert status == TxStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_check_failed_transaction(self, tx_sender, web3_client):
        """Test checking status of failed transaction."""
        web3_client.get_transaction_receipt = AsyncMock(
            return_value={"status": 0, "blockNumber": 12345}
        )

        status = await tx_sender.check_transaction_status("0xabc123")

        assert status == TxStatus.FAILED

    @pytest.mark.asyncio
    async def test_check_transaction_receipt_error(self, tx_sender, web3_client):
        """Test handling error when fetching receipt."""
        web3_client.get_transaction_receipt = AsyncMock(
            side_effect=Exception("RPC error")
        )

        status = await tx_sender.check_transaction_status("0xabc123")

        assert status == TxStatus.PENDING  # Assume pending on error


class TestSlippageProtection:
    """Test suite for slippage protection."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        client = Mock()
        return client

    @pytest.fixture
    def risk_manager(self):
        """Create a mock RiskManager."""
        return Mock(spec=RiskManager)

    @pytest.fixture
    def nonce_manager(self):
        """Create a mock NonceManager."""
        return Mock(spec=NonceManager)

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager, nonce_manager):
        """Create a TxSender for testing."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
            slippage_tolerance=Decimal("0.02"),  # 2% slippage
        )

    def test_calculate_slippage_limit_buy(self, tx_sender):
        """Test calculating slippage limit for buy order."""
        expected_price = Decimal("0.50")

        # For buy, we want to pay at most 2% more
        limit_price = tx_sender._calculate_slippage_limit(
            expected_price=expected_price,
            side="buy"
        )

        assert limit_price == Decimal("0.51")  # 0.50 * 1.02

    def test_calculate_slippage_limit_sell(self, tx_sender):
        """Test calculating slippage limit for sell order."""
        expected_price = Decimal("0.50")

        # For sell, we want to receive at least 2% less
        limit_price = tx_sender._calculate_slippage_limit(
            expected_price=expected_price,
            side="sell"
        )

        assert limit_price == Decimal("0.49")  # 0.50 * 0.98

    def test_calculate_slippage_limit_custom_tolerance(self, tx_sender):
        """Test calculating slippage limit with custom tolerance."""
        tx_sender.slippage_tolerance = Decimal("0.01")  # 1%

        limit_price = tx_sender._calculate_slippage_limit(
            expected_price=Decimal("0.50"),
            side="buy"
        )

        assert limit_price == Decimal("0.505")  # 0.50 * 1.01


class TestErrorHandling:
    """Test suite for error handling."""

    @pytest.fixture
    def web3_client(self):
        """Create a mock Web3Client."""
        client = Mock()
        client.address = "0x1234567890123456789012345678901234567890"
        client.get_balance = AsyncMock(side_effect=Exception("RPC error"))
        return client

    @pytest.fixture
    def risk_manager(self):
        """Create a mock RiskManager."""
        return Mock(spec=RiskManager)

    @pytest.fixture
    def nonce_manager(self):
        """Create a mock NonceManager."""
        nonce_mgr = Mock(spec=NonceManager)
        nonce_mgr.allocate_nonce = AsyncMock(return_value=0)
        return nonce_mgr

    @pytest.fixture
    def tx_sender(self, web3_client, risk_manager, nonce_manager):
        """Create a TxSender for testing."""
        return TxSender(
            web3_client=web3_client,
            risk_manager=risk_manager,
            nonce_manager=nonce_manager,
        )

    @pytest.fixture
    def valid_signal(self):
        """Create a valid trading signal."""
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
    async def test_handle_network_timeout(self, tx_sender, valid_signal, web3_client):
        """Test handling network timeout."""
        import asyncio
        web3_client.get_balance = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False

    @pytest.mark.asyncio
    async def test_handle_connection_error(self, tx_sender, valid_signal, web3_client):
        """Test handling connection error."""
        web3_client.get_balance = AsyncMock(side_effect=ConnectionError("Connection lost"))

        result = await tx_sender.execute_signal(valid_signal)

        assert result is not None
        assert result.success is False
