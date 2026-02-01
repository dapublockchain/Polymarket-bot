"""
Unit tests for Nonce Manager module.

Tests the Ethereum nonce management implementation.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.execution.nonce_manager import NonceManager, NonceStatus
from src.connectors.web3_client import Web3Client


class TestNonceStatus:
    """Test suite for NonceStatus dataclass."""

    def test_nonce_status_creation(self):
        """Test creating a NonceStatus."""
        status = NonceStatus(nonce=5)

        assert status.nonce == 5
        assert status.in_use is False
        assert status.confirmed is False
        assert status.created_at is not None
        assert isinstance(status.created_at, datetime)

    def test_nonce_status_with_flags(self):
        """Test creating NonceStatus with flags."""
        status = NonceStatus(
            nonce=5,
            in_use=True,
            confirmed=True,
        )

        assert status.nonce == 5
        assert status.in_use is True
        assert status.confirmed is True


class TestNonceManagerInit:
    """Test suite for NonceManager initialization."""

    def test_init_with_required_params(self):
        """Test initialization with required parameters."""
        web3_client = Mock(spec=Web3Client)
        address = "0x1234567890123456789012345678901234567890"

        manager = NonceManager(web3_client=web3_client, address=address)

        assert manager.web3_client == web3_client
        assert manager.address == address
        assert manager._next_nonce is None
        assert manager._pending_nonces == {}
        assert manager._confirmed_nonces == set()


class TestNonceManagerInitialize:
    """Test suite for NonceManager initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization."""
        web3_client = Mock(spec=Web3Client)
        web3_client.get_nonce = AsyncMock(return_value=5)

        address = "0x1234567890123456789012345678901234567890"
        manager = NonceManager(web3_client=web3_client, address=address)

        nonce = await manager.initialize()

        assert nonce == 5
        assert manager._next_nonce == 5
        web3_client.get_nonce.assert_called_once_with(address)

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test initialization failure."""
        web3_client = Mock(spec=Web3Client)
        web3_client.get_nonce = AsyncMock(side_effect=Exception("RPC error"))

        address = "0x1234567890123456789012345678901234567890"
        manager = NonceManager(web3_client=web3_client, address=address)

        with pytest.raises(Exception, match="RPC error"):
            await manager.initialize()


class TestNonceManagerGetNonce:
    """Test suite for get_nonce method."""

    @pytest.fixture
    def initialized_manager(self):
        """Create an initialized nonce manager."""
        web3_client = Mock(spec=Web3Client)
        web3_client.get_nonce = AsyncMock(return_value=10)

        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 10  # Simulate initialization
        return manager

    @pytest.mark.asyncio
    async def test_get_nonce_increments(self, initialized_manager):
        """Test that get_nonce increments the nonce."""
        nonce1 = await initialized_manager.get_nonce()
        nonce2 = await initialized_manager.get_nonce()

        assert nonce1 == 10
        assert nonce2 == 11
        assert initialized_manager._next_nonce == 12

    @pytest.mark.asyncio
    async def test_get_nonce_tracks_pending(self, initialized_manager):
        """Test that get_nonce tracks pending nonces."""
        nonce = await initialized_manager.get_nonce()

        assert nonce in initialized_manager._pending_nonces
        assert initialized_manager._pending_nonces[nonce].in_use is True
        assert initialized_manager._pending_nonces[nonce].nonce == nonce

    @pytest.mark.asyncio
    async def test_get_nonce_not_initialized(self):
        """Test get_nonce when not initialized raises error."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )

        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.get_nonce()


class TestNonceManagerAllocateNonce:
    """Test suite for allocate_nonce method."""

    @pytest.fixture
    def initialized_manager(self):
        """Create an initialized nonce manager."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 20
        return manager

    @pytest.mark.asyncio
    async def test_allocate_nonce_alias(self, initialized_manager):
        """Test that allocate_nonce is an alias for get_nonce."""
        nonce = await initialized_manager.allocate_nonce()

        assert nonce == 20
        assert initialized_manager._next_nonce == 21
        assert nonce in initialized_manager._pending_nonces


class TestNonceManagerMarkConfirmed:
    """Test suite for mark_confirmed method."""

    @pytest.fixture
    def manager_with_pending(self):
        """Create manager with pending nonces."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 30

        # Add some pending nonces
        manager._pending_nonces[30] = NonceStatus(nonce=30, in_use=True)
        manager._pending_nonces[31] = NonceStatus(nonce=31, in_use=True)

        return manager

    @pytest.mark.asyncio
    async def test_mark_confirmed_removes_from_pending(self, manager_with_pending):
        """Test that mark_confirmed removes nonce from pending."""
        await manager_with_pending.mark_confirmed(30)

        assert 30 not in manager_with_pending._pending_nonces
        assert 30 in manager_with_pending._confirmed_nonces

    @pytest.mark.asyncio
    async def test_mark_confirmed_idempotent(self, manager_with_pending):
        """Test that mark_confirmed is idempotent."""
        await manager_with_pending.mark_confirmed(30)
        await manager_with_pending.mark_confirmed(30)  # Should not error

        assert 30 not in manager_with_pending._pending_nonces
        assert 30 in manager_with_pending._confirmed_nonces


class TestNonceManagerMarkFailed:
    """Test suite for mark_failed method."""

    @pytest.fixture
    def manager_with_pending(self):
        """Create manager with pending nonces."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 35

        # Add pending nonces
        manager._pending_nonces[35] = NonceStatus(nonce=35, in_use=True)
        manager._pending_nonces[36] = NonceStatus(nonce=36, in_use=True)

        return manager

    @pytest.mark.asyncio
    async def test_mark_failed_removes_from_pending(self, manager_with_pending):
        """Test that mark_failed removes nonce from pending."""
        await manager_with_pending.mark_failed(35)

        assert 35 not in manager_with_pending._pending_nonces

    @pytest.mark.asyncio
    async def test_mark_failed_makes_nonce_reusable(self, manager_with_pending):
        """Test that failed nonce can be reused."""
        manager_with_pending._next_nonce = 37  # Current next nonce

        await manager_with_pending.mark_failed(35)

        # Next nonce should be the failed one (for reuse)
        assert manager_with_pending._next_nonce == 35

    @pytest.mark.asyncio
    async def test_mark_failed_preserves_lower_nonce(self, manager_with_pending):
        """Test that mark_failed preserves lower nonce for reuse."""
        manager_with_pending._next_nonce = 40  # Current next nonce is higher

        await manager_with_pending.mark_failed(35)

        # Should reuse the lower nonce
        assert manager_with_pending._next_nonce == 35


class TestNonceManagerIsPending:
    """Test suite for is_pending method."""

    def test_is_pending_true(self):
        """Test is_pending returns True for pending nonce."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._pending_nonces[10] = NonceStatus(nonce=10, in_use=True)

        assert manager.is_pending(10) is True

    def test_is_pending_false(self):
        """Test is_pending returns False for non-pending nonce."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )

        assert manager.is_pending(10) is False


class TestNonceManagerGetPendingCount:
    """Test suite for get_pending_count method."""

    def test_get_pending_count_empty(self):
        """Test get_pending_count with no pending nonces."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )

        assert manager.get_pending_count() == 0

    def test_get_pending_count_with_pending(self):
        """Test get_pending_count with pending nonces."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._pending_nonces[10] = NonceStatus(nonce=10, in_use=True)
        manager._pending_nonces[11] = NonceStatus(nonce=11, in_use=True)
        manager._pending_nonces[12] = NonceStatus(nonce=12, in_use=True)

        assert manager.get_pending_count() == 3


class TestNonceManagerGetStats:
    """Test suite for get_stats method."""

    def test_get_stats(self):
        """Test get_stats returns correct statistics."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 50
        manager._pending_nonces[48] = NonceStatus(nonce=48, in_use=True)
        manager._pending_nonces[49] = NonceStatus(nonce=49, in_use=True)
        manager._confirmed_nonces = {45, 46, 47}

        stats = manager.get_stats()

        assert stats["next_nonce"] == 50
        assert stats["pending_count"] == 2
        assert stats["confirmed_count"] == 3
        assert set(stats["pending_nonces"]) == {48, 49}


class TestNonceManagerConcurrency:
    """Test suite for concurrent nonce allocation."""

    @pytest.mark.asyncio
    async def test_concurrent_allocation(self):
        """Test concurrent nonce allocation is thread-safe."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 100

        # Allocate nonces concurrently
        tasks = [manager.get_nonce() for _ in range(10)]
        nonces = await asyncio.gather(*tasks)

        # All nonces should be unique
        assert len(set(nonces)) == 10
        assert min(nonces) == 100
        assert max(nonces) == 109
        assert manager._next_nonce == 110


class TestNonceManagerEdgeCases:
    """Test suite for edge cases."""

    @pytest.mark.asyncio
    async def test_mark_confirmed_non_pending(self):
        """Test marking confirmed nonce that was never pending."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )

        # Should not error
        await manager.mark_confirmed(999)

    @pytest.mark.asyncio
    async def test_mark_failed_non_pending(self):
        """Test marking failed nonce that was never pending."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )
        manager._next_nonce = 50

        # Should make the nonce available for reuse
        await manager.mark_failed(40)
        assert manager._next_nonce == 40

    def test_get_stats_empty_manager(self):
        """Test get_stats on empty manager."""
        web3_client = Mock(spec=Web3Client)
        manager = NonceManager(
            web3_client=web3_client,
            address="0x1234567890123456789012345678901234567890"
        )

        stats = manager.get_stats()

        assert stats["next_nonce"] is None
        assert stats["pending_count"] == 0
        assert stats["confirmed_count"] == 0
        assert stats["pending_nonces"] == []
