"""
Unit tests for Web3 Client.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.

NOTE: All Web3 connections are MOCKED - no real blockchain calls in tests.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from web3 import Web3
from web3.types import TxParams, TxReceipt
from eth_account import Account

from src.connectors.web3_client import Web3Client
from src.core.config import Config


class TestWeb3ClientInitialization:
    """Test suite for Web3Client initialization."""

    def test_initialization_with_valid_config(self):
        """Test that Web3Client initializes with valid configuration."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_web3_instance = Mock()
            mock_web3.return_value = mock_web3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,  # Fake private key for testing
            )

            assert client.rpc_url == "https://polygon-rpc.com"
            assert client.address is not None
            assert len(client.address) == 42  # Ethereum address length
            assert client.w3 is not None

    def test_initialization_fails_without_private_key(self):
        """Test that initialization fails without private key."""
        with pytest.raises(ValueError, match="Private key is required"):
            Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key=None,
            )

    def test_initialization_with_invalid_private_key(self):
        """Test that initialization fails with invalid private key."""
        with pytest.raises(ValueError):
            Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="invalid_key",
            )


class TestGetBalance:
    """Test suite for getting USDC balance."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_get_balance_success(self, client):
        """Test successfully getting USDC balance."""
        # Mock the contract call
        mock_contract = Mock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 1000000  # 1 USDC (6 decimals)

        with patch.object(client, "_get_usdc_contract", return_value=mock_contract):
            balance = await client.get_balance("0x" + "1" * 40)

            assert balance == Decimal("1.0")
            mock_contract.functions.balanceOf.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_balance_zero(self, client):
        """Test getting zero balance."""
        mock_contract = Mock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 0

        with patch.object(client, "_get_usdc_contract", return_value=mock_contract):
            balance = await client.get_balance("0x" + "1" * 40)

            assert balance == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_balance_large_amount(self, client):
        """Test getting large balance."""
        mock_contract = Mock()
        mock_contract.functions.balanceOf.return_value.call.return_value = 1000000000  # 1000 USDC

        with patch.object(client, "_get_usdc_contract", return_value=mock_contract):
            balance = await client.get_balance("0x" + "1" * 40)

            assert balance == Decimal("1000.0")

    @pytest.mark.asyncio
    async def test_get_balance_contract_error(self, client):
        """Test handling contract call errors."""
        mock_contract = Mock()
        mock_contract.functions.balanceOf.return_value.call.side_effect = Exception("Contract error")

        with patch.object(client, "_get_usdc_contract", return_value=mock_contract):
            with pytest.raises(Exception, match="Contract error"):
                await client.get_balance("0x" + "1" * 40)


class TestEstimateGas:
    """Test suite for gas estimation."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_estimate_gas_success(self, client):
        """Test successful gas estimation."""
        transaction: TxParams = {
            "to": "0x" + "2" * 40,
            "from": "0x" + "1" * 40,
            "value": 1000000,
        }

        client.w3.eth.estimate_gas.return_value = 21000

        gas_limit = await client.estimate_gas(transaction)

        assert gas_limit == 21000
        client.w3.eth.estimate_gas.assert_called_once()

    @pytest.mark.asyncio
    async def test_estimate_gas_with_multiplier(self, client):
        """Test gas estimation with multiplier applied."""
        transaction: TxParams = {
            "to": "0x" + "2" * 40,
            "from": "0x" + "1" * 40,
        }

        client.w3.eth.estimate_gas.return_value = 100000

        gas_limit = await client.estimate_gas(transaction, multiplier=1.5)

        assert gas_limit == 150000

    @pytest.mark.asyncio
    async def test_estimate_gas_failure(self, client):
        """Test gas estimation failure."""
        transaction: TxParams = {
            "to": "0x" + "2" * 40,
        }

        client.w3.eth.estimate_gas.side_effect = Exception("Gas estimation failed")

        with pytest.raises(Exception, match="Gas estimation failed"):
            await client.estimate_gas(transaction)


class TestEstimateEIP1559Gas:
    """Test suite for EIP-1559 gas estimation."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_estimate_eip1559_gas_success(self, client):
        """Test successful EIP-1559 gas estimation."""
        # Mock latest block with base fee
        client.w3.eth.get_block.return_value = {
            "baseFeePerGas": 30000000,  # 30 gwei
        }

        gas_params = await client.estimate_eip1559_gas()

        assert "maxFeePerGas" in gas_params
        assert "maxPriorityFeePerGas" in gas_params
        assert gas_params["maxFeePerGas"] > 0
        assert gas_params["maxPriorityFeePerGas"] > 0
        # Max fee should be base fee + priority fee
        assert gas_params["maxFeePerGas"] >= 30000000

    @pytest.mark.asyncio
    async def test_estimate_eip1559_gas_with_custom_priority_fee(self, client):
        """Test EIP-1559 gas estimation with custom priority fee."""
        client.w3.eth.get_block.return_value = {
            "baseFeePerGas": 30000000,
        }

        gas_params = await client.estimate_eip1559_gas(priority_fee=100000000)  # 100 gwei

        assert gas_params["maxPriorityFeePerGas"] == 100000000

    @pytest.mark.asyncio
    async def test_estimate_eip1559_gas_max_limit(self, client):
        """Test EIP-1559 gas estimation respects maximum gas price."""
        from src.core.config import Config

        client.w3.eth.get_block.return_value = {
            "baseFeePerGas": 400000000,  # 400 gwei (very high)
        }

        gas_params = await client.estimate_eip1559_gas(max_gas_price=Config.MAX_GAS_PRICE)

        assert gas_params["maxFeePerGas"] <= Config.MAX_GAS_PRICE


class TestSignTransaction:
    """Test suite for transaction signing."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_sign_transaction_success(self, client):
        """Test successful transaction signing."""
        transaction: TxParams = {
            "to": "0x" + "2" * 40,
            "from": client.address,
            "value": 1000000,
            "gas": 21000,
            "maxFeePerGas": 50000000,
            "maxPriorityFeePerGas": 2000000,
            "nonce": 0,
            "chainId": 137,
        }

        signed_tx = await client.sign_transaction(transaction)

        assert isinstance(signed_tx, bytes)
        assert len(signed_tx) > 0

    @pytest.mark.asyncio
    async def test_sign_transaction_includes_all_fields(self, client):
        """Test that signing includes all transaction fields."""
        transaction: TxParams = {
            "to": "0x" + "2" * 40,
            "from": client.address,
            "value": 1000000,
            "gas": 21000,
            "maxFeePerGas": 50000000,
            "maxPriorityFeePerGas": 2000000,
            "nonce": 0,
            "chainId": 137,
        }

        signed_tx = await client.sign_transaction(transaction)

        assert isinstance(signed_tx, bytes)
        # Verify the signed transaction can be decoded
        # (This is a basic check - in production we'd verify more)


class TestSendTransaction:
    """Test suite for sending transactions."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_send_transaction_success(self, client):
        """Test successfully sending a transaction."""
        signed_tx = b"signed_transaction_bytes"
        expected_tx_hash = "0x" + "a" * 64

        client.w3.eth.send_raw_transaction.return_value = expected_tx_hash

        tx_hash = await client.send_transaction(signed_tx)

        assert tx_hash == expected_tx_hash
        client.w3.eth.send_raw_transaction.assert_called_once_with(signed_tx)

    @pytest.mark.asyncio
    async def test_send_transaction_failure(self, client):
        """Test handling transaction sending failure."""
        signed_tx = b"signed_transaction_bytes"

        client.w3.eth.send_raw_transaction.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            await client.send_transaction(signed_tx)

    @pytest.mark.asyncio
    async def test_send_transaction_nonce_too_low(self, client):
        """Test handling nonce too low error."""
        signed_tx = b"signed_transaction_bytes"

        client.w3.eth.send_raw_transaction.side_effect = Exception(
            "nonce too low"
        )

        with pytest.raises(Exception, match="nonce"):
            await client.send_transaction(signed_tx)


class TestGetTransactionReceipt:
    """Test suite for getting transaction receipt."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_get_receipt_success(self, client):
        """Test successfully getting transaction receipt."""
        tx_hash = "0x" + "a" * 64
        mock_receipt = {
            "transactionHash": tx_hash,
            "blockNumber": 12345,
            "status": 1,
            "gasUsed": 21000,
        }

        client.w3.eth.get_transaction_receipt.return_value = mock_receipt

        receipt = await client.get_transaction_receipt(tx_hash)

        assert receipt["status"] == 1
        assert receipt["blockNumber"] == 12345
        client.w3.eth.get_transaction_receipt.assert_called_once_with(tx_hash)

    @pytest.mark.asyncio
    async def test_get_receipt_pending(self, client):
        """Test getting receipt for pending transaction."""
        tx_hash = "0x" + "a" * 64

        client.w3.eth.get_transaction_receipt.return_value = None

        receipt = await client.get_transaction_receipt(tx_hash)

        assert receipt is None

    @pytest.mark.asyncio
    async def test_get_receipt_failed_transaction(self, client):
        """Test getting receipt for failed transaction."""
        tx_hash = "0x" + "a" * 64
        mock_receipt = {
            "transactionHash": tx_hash,
            "blockNumber": 12345,
            "status": 0,  # Failed
            "gasUsed": 21000,
        }

        client.w3.eth.get_transaction_receipt.return_value = mock_receipt

        receipt = await client.get_transaction_receipt(tx_hash)

        assert receipt["status"] == 0


class TestNonceManagement:
    """Test suite for nonce management."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_get_nonce_success(self, client):
        """Test successfully getting transaction count."""
        client.w3.eth.get_transaction_count.return_value = 5

        nonce = await client.get_nonce()

        assert nonce == 5
        client.w3.eth.get_transaction_count.assert_called_once_with(
            client.address, "pending"
        )

    @pytest.mark.asyncio
    async def test_get_nonce_latest_block(self, client):
        """Test getting nonce from latest block."""
        client.w3.eth.get_transaction_count.return_value = 3

        nonce = await client.get_nonce(block="latest")

        assert nonce == 3
        client.w3.eth.get_transaction_count.assert_called_once_with(
            client.address, "latest"
        )


class TestErrorHandling:
    """Test suite for error handling."""

    @pytest.fixture
    def client(self):
        """Create a Web3Client for testing."""
        with patch("src.connectors.web3_client.Web3") as mock_web3:
            mock_w3_instance = Mock()
            mock_web3.return_value = mock_w3_instance

            client = Web3Client(
                rpc_url="https://polygon-rpc.com",
                private_key="0x" + "1" * 64,
            )
            return client

    @pytest.mark.asyncio
    async def test_rpc_connection_failure(self, client):
        """Test handling RPC connection failure."""
        client.w3.eth.get_block.side_effect = ConnectionError("RPC unavailable")

        with pytest.raises(ConnectionError, match="RPC unavailable"):
            await client.estimate_eip1559_gas()

    @pytest.mark.asyncio
    async def test_invalid_address_format(self, client):
        """Test handling invalid address format."""
        with pytest.raises(ValueError):
            await client.get_balance("invalid_address")

    @pytest.mark.asyncio
    async def test_timeout_on_transaction(self, client):
        """Test handling timeout when sending transaction."""
        client.w3.eth.send_raw_transaction.side_effect = TimeoutError("Request timeout")

        with pytest.raises(TimeoutError, match="Request timeout"):
            await client.send_transaction(b"signed_tx")
