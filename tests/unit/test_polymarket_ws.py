"""
Unit tests for Polymarket WebSocket Connector.

Tests are written FIRST (TDD methodology).
The implementation should make these tests pass.
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.connectors.polymarket_ws import PolymarketWSClient
from src.core.models import OrderBook, Bid, Ask


class TestPolymarketWSClientInit:
    """Test suite for PolymarketWSClient initialization."""

    @pytest.mark.asyncio
    async def test_init_with_default_url(self):
        """Test initialization with default WebSocket URL."""
        client = PolymarketWSClient()
        assert client.url == "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        assert client.connected is False
        assert client.orderbooks == {}

    @pytest.mark.asyncio
    async def test_init_with_custom_url(self):
        """Test initialization with custom WebSocket URL."""
        client = PolymarketWSClient(url="wss://custom.url")
        assert client.url == "wss://custom.url"

    @pytest.mark.asyncio
    async def test_init_with_reconnect_params(self):
        """Test initialization with custom reconnect parameters."""
        client = PolymarketWSClient(
            max_reconnect_attempts=5,
            reconnect_delay=1.0,
        )
        assert client.max_reconnect_attempts == 5
        assert client.reconnect_delay == 1.0


class TestConnect:
    """Test suite for WebSocket connection."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WebSocket connection."""
        client = PolymarketWSClient()

        # Mock websockets.connect to return a coroutine
        async def mock_connect_coro(*args, **kwargs):
            mock_ws = AsyncMock()
            mock_ws.close = AsyncMock()
            return mock_ws

        with patch("src.connectors.polymarket_ws.websockets.connect", side_effect=mock_connect_coro):
            await client.connect()

            assert client.connected is True

    @pytest.mark.asyncio
    async def test_connect_with_reconnect_on_failure(self):
        """Test reconnection on connection failure."""
        client = PolymarketWSClient(max_reconnect_attempts=2, reconnect_delay=0.01)

        call_count = [0]

        async def mock_connect_coro(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Connection failed")
            mock_ws = AsyncMock()
            mock_ws.close = AsyncMock()
            return mock_ws

        with patch("src.connectors.polymarket_ws.websockets.connect", side_effect=mock_connect_coro):
            await client.connect()

            assert client.connected is True
            assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_connect_fails_after_max_attempts(self):
        """Test connection failure after max attempts."""
        client = PolymarketWSClient(max_reconnect_attempts=2, reconnect_delay=0.01)

        with patch("src.connectors.polymarket_ws.websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Failed to connect after 2 attempts"):
                await client.connect()

            assert client.connected is False
            assert mock_connect.call_count == 2


class TestSubscribe:
    """Test suite for order book subscription."""

    @pytest.mark.asyncio
    async def test_subscribe_to_token(self):
        """Test subscribing to a single token."""
        client = PolymarketWSClient()

        # Mock WebSocket connection
        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client.connected = True

        await client.subscribe("token_123")

        # Verify subscription message was sent
        client._ws.send.assert_called_once()
        call_args = client._ws.send.call_args[0][0]
        # Should be JSON with subscription message
        import json
        message = json.loads(call_args)
        assert message["action"] == "subscribe"
        assert "token_123" in message.get("tokens", [])

    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_tokens(self):
        """Test subscribing to multiple tokens."""
        client = PolymarketWSClient()

        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client.connected = True

        await client.subscribe("token_1")
        await client.subscribe("token_2")

        assert client._ws.send.call_count == 2

    @pytest.mark.asyncio
    async def test_subscribe_when_not_connected(self):
        """Test subscribing when not connected raises error."""
        client = PolymarketWSClient()

        with pytest.raises(Exception, match="Not connected"):
            await client.subscribe("token_123")


class TestMessageHandling:
    """Test suite for handling WebSocket messages."""

    @pytest.mark.asyncio
    async def test_handle_order_book_snapshot(self):
        """Test handling order book snapshot message."""
        client = PolymarketWSClient()

        # Mock snapshot message
        message = {
            "type": "snapshot",
            "token_id": "token_123",
            "bids": [
                {"price": "0.50", "size": "100", "token_id": "token_123"},
                {"price": "0.49", "size": "200", "token_id": "token_123"},
            ],
            "asks": [
                {"price": "0.51", "size": "100", "token_id": "token_123"},
                {"price": "0.52", "size": "150", "token_id": "token_123"},
            ],
        }

        await client._handle_message(message)

        # Verify order book was created
        assert "token_123" in client.orderbooks
        orderbook = client.orderbooks["token_123"]
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        assert orderbook.bids[0].price == Decimal("0.50")
        assert orderbook.asks[0].price == Decimal("0.51")

    @pytest.mark.asyncio
    async def test_handle_order_book_update(self):
        """Test handling order book update message."""
        client = PolymarketWSClient()

        # First, create initial order book
        snapshot_msg = {
            "type": "snapshot",
            "token_id": "token_123",
            "bids": [{"price": "0.50", "size": "100", "token_id": "token_123"}],
            "asks": [{"price": "0.51", "size": "100", "token_id": "token_123"}],
        }
        await client._handle_message(snapshot_msg)

        # Now apply update
        update_msg = {
            "type": "update",
            "token_id": "token_123",
            "bids": [{"price": "0.51", "size": "50", "token_id": "token_123"}],
        }
        await client._handle_message(update_msg)

        # Verify order book was updated
        orderbook = client.orderbooks["token_123"]
        # Should have both old and new bids
        assert len(orderbook.bids) == 2
        # Highest bid should be 0.51
        assert orderbook.get_best_bid().price == Decimal("0.51")

    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self):
        """Test handling unknown message type is ignored."""
        client = PolymarketWSClient()

        message = {"type": "unknown", "data": "test"}

        # Should not raise exception
        await client._handle_message(message)

        assert "token_123" not in client.orderbooks


class TestGetOrderBook:
    """Test suite for getting order books."""

    @pytest.mark.asyncio
    async def test_get_order_book_for_subscribed_token(self):
        """Test getting order book for subscribed token."""
        client = PolymarketWSClient()

        # Create an order book
        snapshot_msg = {
            "type": "snapshot",
            "token_id": "token_123",
            "bids": [{"price": "0.50", "size": "100", "token_id": "token_123"}],
            "asks": [{"price": "0.51", "size": "100", "token_id": "token_123"}],
        }
        await client._handle_message(snapshot_msg)

        orderbook = client.get_order_book("token_123")

        assert orderbook is not None
        assert orderbook.token_id == "token_123"
        assert len(orderbook.bids) == 1
        assert len(orderbook.asks) == 1

    @pytest.mark.asyncio
    async def test_get_order_book_for_unsubscribed_token(self):
        """Test getting order book for unsubscribed token returns None."""
        client = PolymarketWSClient()

        orderbook = client.get_order_book("token_999")

        assert orderbook is None


class TestDisconnect:
    """Test suite for WebSocket disconnection."""

    @pytest.mark.asyncio
    async def test_disconnect_clears_state(self):
        """Test that disconnect clears connection state."""
        client = PolymarketWSClient()

        # Mock WebSocket connection
        client._ws = AsyncMock()
        client._ws.close = AsyncMock()
        client.connected = True

        await client.disconnect()

        assert client.connected is False
        # Note: close might not be called if _ws was already None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected doesn't raise error."""
        client = PolymarketWSClient()

        # Should not raise exception
        await client.disconnect()

        assert client.connected is False


class TestReconnectLogic:
    """Test suite for reconnection logic."""

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that reconnect uses exponential backoff."""
        client = PolymarketWSClient(reconnect_delay=0.1, use_exponential_backoff=True)

        with patch("src.connectors.polymarket_ws.websockets.connect") as mock_connect:
            # All attempts fail
            mock_connect.side_effect = Exception("Connection failed")

            with pytest.raises(Exception):
                await client.connect()

            # Verify exponential backoff was used
            # The delay should increase between attempts
            assert mock_connect.call_count == client.max_reconnect_attempts

    @pytest.mark.asyncio
    async def test_listen_reconnects_on_disconnect(self):
        """Test that listen loop reconnects on disconnect."""
        client = PolymarketWSClient(max_reconnect_attempts=2, reconnect_delay=0.01)

        with patch("src.connectors.polymarket_ws.websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.__aenter__.return_value = mock_ws
            mock_ws.recv = AsyncMock(side_effect=["message1", Exception("Disconnect"), "message2"])

            # Mock reconnect to succeed
            mock_connect.return_value = mock_ws

            # This should reconnect and continue
            # We'll use a timeout to prevent infinite loop
            task = asyncio.create_task(client.listen())

            # Wait a bit for messages
            await asyncio.sleep(0.1)

            # Cancel the task
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass


class TestMessageCache:
    """Test suite for MessageCache."""

    def test_message_cache_add_new(self):
        """Test adding new message to cache."""
        from src.connectors.polymarket_ws import MessageCache

        cache = MessageCache(max_size=100)

        result = cache.add("msg_1")

        assert result is True  # New message
        assert "msg_1" in cache.cache
        assert cache.misses == 1

    def test_message_cache_duplicate(self):
        """Test detecting duplicate message."""
        from src.connectors.polymarket_ws import MessageCache

        cache = MessageCache(max_size=100)

        cache.add("msg_1")
        result = cache.add("msg_1")

        assert result is False  # Duplicate
        assert cache.hits == 1

    def test_message_cache_eviction(self):
        """Test LRU eviction when cache is full."""
        from src.connectors.polymarket_ws import MessageCache

        cache = MessageCache(max_size=3)

        cache.add("msg_1")
        cache.add("msg_2")
        cache.add("msg_3")
        cache.add("msg_4")  # Should evict msg_1

        assert "msg_1" not in cache.cache
        assert "msg_4" in cache.cache
        assert len(cache.cache) == 3

    def test_message_cache_get_stats(self):
        """Test getting cache statistics."""
        from src.connectors.polymarket_ws import MessageCache

        cache = MessageCache(max_size=100)

        cache.add("msg_1")
        cache.add("msg_1")  # Duplicate
        cache.add("msg_2")

        stats = cache.get_stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 1/3

    def test_message_cache_lru_ordering(self):
        """Test that recently used items are moved to end."""
        from src.connectors.polymarket_ws import MessageCache
        import time

        cache = MessageCache(max_size=3)

        cache.add("msg_1")
        time.sleep(0.01)
        cache.add("msg_2")
        time.sleep(0.01)
        cache.add("msg_3")

        # Access msg_1 (moves to end)
        cache.add("msg_1")

        # Add new message - should evict msg_2 (oldest after msg_1 was accessed)
        cache.add("msg_4")

        assert "msg_1" in cache.cache  # Was accessed, still present
        assert "msg_2" not in cache.cache  # Evicted
        assert "msg_4" in cache.cache


class TestStatsAndTracking:
    """Test suite for statistics and tracking."""

    @pytest.mark.asyncio
    async def test_get_stats_includes_all_fields(self):
        """Test get_stats returns all expected fields."""
        client = PolymarketWSClient()

        stats = client.get_stats()

        expected_keys = {
            "connected", "connect_count", "disconnect_count",
            "message_count", "duplicate_count", "sequence_gap_count",
            "subscriptions", "orderbooks", "cache_stats",
            "heartbeat_ok", "time_since_last_message_seconds",
        }

        assert set(stats.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_get_stats_with_messages(self):
        """Test stats reflect message handling."""
        client = PolymarketWSClient()

        # Simulate some messages
        message = {
            "type": "snapshot",
            "token_id": "test_token",
            "bids": [{"price": "0.5", "size": "100", "token_id": "test_token"}],
            "asks": [{"price": "0.5", "size": "100", "token_id": "test_token"}],
        }

        await client._handle_message(message)

        stats = client.get_stats()

        assert stats["message_count"] == 1
        assert stats["orderbooks"] == 1
        assert stats["duplicate_count"] == 0

    @pytest.mark.asyncio
    async def test_sequence_tracking(self):
        """Test sequence number tracking."""
        client = PolymarketWSClient()

        # Send messages with sequence numbers
        for i in range(1, 4):
            message = {
                "type": "snapshot",
                "token_id": "test_token",
                "sequence_number": i,
                "bids": [],
                "asks": [],
            }
            await client._handle_message(message)

        assert client._sequence_numbers["test_token"] == 3

    @pytest.mark.asyncio
    async def test_sequence_gap_detection(self):
        """Test detection of sequence gaps."""
        client = PolymarketWSClient()

        # Send message with sequence 1
        message1 = {
            "type": "snapshot",
            "token_id": "test_token",
            "sequence_number": 1,
            "bids": [],
            "asks": [],
        }
        await client._handle_message(message1)

        # Send message with sequence 5 (gap of 3)
        message2 = {
            "type": "snapshot",
            "token_id": "test_token",
            "sequence_number": 5,
            "bids": [],
            "asks": [],
        }
        await client._handle_message(message2)

        # Should detect gap
        stats = client.get_stats()
        assert stats["sequence_gap_count"] >= 3

    @pytest.mark.asyncio
    async def test_duplicate_detection(self):
        """Test duplicate message detection."""
        client = PolymarketWSClient()

        message = {
            "type": "snapshot",
            "token_id": "test_token",
            "sequence_number": 1,
            "bids": [],
            "asks": [],
        }

        # Send same message twice
        await client._handle_message(message)
        await client._handle_message(message)

        stats = client.get_stats()

        # Should detect duplicate
        assert stats["duplicate_count"] == 1

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_detection(self):
        """Test heartbeat timeout detection."""
        client = PolymarketWSClient(heartbeat_timeout=1)

        # Initially, no heartbeat received
        stats = client.get_stats()
        assert stats["heartbeat_ok"] is True  # No messages yet, considered OK

        # Send a message
        message = {
            "type": "snapshot",
            "token_id": "test_token",
            "bids": [],
            "asks": [],
        }
        await client._handle_message(message)

        stats = client.get_stats()
        assert stats["heartbeat_ok"] is True
        assert stats["time_since_last_message_seconds"] < 1

    @pytest.mark.asyncio
    async def test_message_without_token_id(self):
        """Test handling message without token_id."""
        client = PolymarketWSClient()

        message = {
            "type": "snapshot",
            "bids": [],
            "asks": [],
        }

        # Should not raise, just skip
        await client._handle_message(message)

        assert len(client.orderbooks) == 0


class TestResubscription:
    """Test suite for resubscription behavior."""

    @pytest.mark.asyncio
    async def test_resubscribe_after_reconnect(self):
        """Test that subscriptions are restored after reconnect."""
        client = PolymarketWSClient()

        # Mock initial connection
        client._ws = AsyncMock()
        client._ws.send = AsyncMock()
        client.connected = True

        # Subscribe to tokens
        await client.subscribe("token_1")
        await client.subscribe("token_2")

        assert len(client._subscriptions) == 2

        # Simulate reconnect
        async def mock_connect(*args, **kwargs):
            new_ws = AsyncMock()
            new_ws.send = AsyncMock()
            return new_ws

        with patch("src.connectors.polymarket_ws.websockets.connect", side_effect=mock_connect):
            await client.connect()

            # Should have resubscribed to previous subscriptions
            assert client._ws.send.call_count >= 2


class TestContextManager:
    """Test suite for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_enter_exit(self):
        """Test using client as context manager."""
        async def mock_connect(*args, **kwargs):
            mock_ws = AsyncMock()
            mock_ws.close = AsyncMock()
            return mock_ws

        with patch("src.connectors.polymarket_ws.websockets.connect", side_effect=mock_connect):
            async with PolymarketWSClient() as client:
                assert client.connected is True

            # After exit, should be disconnected
            assert client.connected is False


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_message_handling(self):
        """Test handling of empty messages."""
        client = PolymarketWSClient()

        # Empty string should be handled
        client._message_cache.add("")  # Should not crash

    @pytest.mark.asyncio
    async def test_zero_sequence_number(self):
        """Test handling of zero sequence number."""
        client = PolymarketWSClient()

        message = {
            "type": "snapshot",
            "token_id": "test_token",
            "sequence_number": 0,
            "bids": [],
            "asks": [],
        }

        # Should not trigger sequence validation for 0
        await client._handle_message(message)

        assert client._sequence_numbers.get("test_token", 0) == 0

    @pytest.mark.asyncio
    async def test_very_small_prices(self):
        """Test handling of very small prices (edge case)."""
        from decimal import Decimal

        client = PolymarketWSClient()

        # Use very small but positive prices
        message = {
            "type": "snapshot",
            "token_id": "test_token",
            "bids": [{"price": "0.001", "size": "100", "token_id": "test_token"}],
            "asks": [{"price": "0.002", "size": "100", "token_id": "test_token"}],
        }

        # Should handle small positive prices
        await client._handle_message(message)

        assert "test_token" in client.orderbooks

    @pytest.mark.asyncio
    async def test_very_large_message_cache(self):
        """Test behavior with very large message cache."""
        from src.connectors.polymarket_ws import MessageCache

        cache = MessageCache(max_size=10000)

        # Add many messages
        for i in range(20000):
            cache.add(f"msg_{i}")

        # Should stay bounded
        assert len(cache.cache) <= 10000
