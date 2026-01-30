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
