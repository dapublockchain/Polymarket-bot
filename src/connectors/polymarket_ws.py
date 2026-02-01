"""
Polymarket CLOB WebSocket Connector.

Connects to Polymarket's WebSocket API for real-time order book updates.

Resilience features:
- Message deduplication
- Sequence number validation
- Connection statistics
- Heartbeat timeout detection
"""
import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Optional, Dict, Set
from json import JSONDecodeError
from collections import OrderedDict
from datetime import datetime, timedelta

import websockets

from src.core.models import OrderBook, Bid, Ask
from src.core.telemetry import generate_trace_id, log_event, EventType as TeleEventType

logger = logging.getLogger(__name__)


# LRU cache for message deduplication
class MessageCache:
    """LRU cache for message deduplication."""

    def __init__(self, max_size: int = 10000):
        """
        Initialize message cache.

        Args:
            max_size: Maximum number of messages to cache
        """
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def add(self, message_id: str) -> bool:
        """
        Add message to cache.

        Args:
            message_id: Message identifier

        Returns:
            True if message was new (added to cache)
            False if message was already in cache (duplicate)
        """
        if message_id in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(message_id)
            self.hits += 1
            return False  # Duplicate
        else:
            self.cache[message_id] = time.time()
            self.misses += 1

            # Evict oldest if at capacity
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

            return True  # New message

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0.0
        }


class PolymarketWSClient:
    """
    WebSocket client for Polymarket CLOB.

    Maintains local order books for subscribed tokens and handles
    automatic reconnection with exponential backoff.

    Resilience features:
    - Message deduplication via MessageCache
    - Sequence number tracking and validation
    - Connection statistics (connect_count, message_count, duplicate_count)
    - Heartbeat timeout detection
    """

    def __init__(
        self,
        url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        use_exponential_backoff: bool = True,
        heartbeat_timeout: int = 30,
    ):
        """
        Initialize the WebSocket client.

        Args:
            url: WebSocket URL
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Initial delay between reconnections (seconds)
            use_exponential_backoff: Whether to use exponential backoff
            heartbeat_timeout: Seconds without message before considering stale
        """
        self.url = url
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.use_exponential_backoff = use_exponential_backoff
        self.heartbeat_timeout = heartbeat_timeout
        self.connected: bool = False
        self.orderbooks: Dict[str, OrderBook] = {}
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._subscriptions: set = set()

        # Resilience features
        self._message_cache = MessageCache(max_size=10000)
        self._sequence_numbers: Dict[str, int] = {}  # token_id -> last_seq
        self._last_message_time: Optional[datetime] = None

        # Connection statistics
        self._connect_count = 0
        self._disconnect_count = 0
        self._message_count = 0
        self._duplicate_count = 0
        self._sequence_gap_count = 0

    async def connect(self) -> None:
        """
        Connect to the WebSocket server with reconnection logic.

        Raises:
            Exception: If connection fails after max attempts
        """
        attempt = 0
        delay = self.reconnect_delay

        while attempt < self.max_reconnect_attempts:
            try:
                logger.info(f"正在连接到 {self.url} (尝试 {attempt + 1}/{self.max_reconnect_attempts})")
                self._ws = await websockets.connect(self.url)
                self.connected = True
                self._connect_count += 1
                logger.info(f"连接成功 (总连接次数: {self._connect_count})")

                # Resubscribe to previous subscriptions
                for token_id in self._subscriptions:
                    await self._send_subscription(token_id)

                return
            except Exception as e:
                attempt += 1
                logger.warning(f"连接失败: {e}")

                if attempt >= self.max_reconnect_attempts:
                    raise Exception(f"Failed to connect after {self.max_reconnect_attempts} attempts")

                # Wait before retrying
                await asyncio.sleep(delay)

                # Exponential backoff
                if self.use_exponential_backoff:
                    delay = min(delay * 2, 30)

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self.connected = False

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("已断开连接")

    async def subscribe(self, token_id: str) -> None:
        """
        Subscribe to order book updates for a token.

        Args:
            token_id: Token identifier to subscribe to

        Raises:
            Exception: If not connected
        """
        if not self.connected:
            raise Exception("Not connected")

        await self._send_subscription(token_id)
        self._subscriptions.add(token_id)
        logger.info(f"已订阅 {token_id}")

    async def _send_subscription(self, token_id: str) -> None:
        """Send subscription message to the server."""
        message = {
            "action": "subscribe",
            "tokens": [token_id],
        }
        await self._ws.send(json.dumps(message))

    async def listen(self) -> None:
        """
        Listen for incoming messages and update order books.

        This method runs in a loop until disconnected.
        It will automatically reconnect on connection loss.
        """
        while self.connected:
            try:
                if not self._ws:
                    await asyncio.sleep(0.1)
                    continue

                message_raw = await self._ws.recv()

                # Skip empty messages (heartbeat/ping)
                if not message_raw or not message_raw.strip():
                    continue

                try:
                    message = json.loads(message_raw)
                except JSONDecodeError:
                    # Skip non-JSON messages (heartbeat/control frames)
                    logger.debug(f"跳过非 JSON 消息: {message_raw[:50]}")
                    continue

                await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("连接已关闭，尝试重新连接...")
                self.connected = False
                await self.connect()

            except Exception as e:
                logger.error(f"监听循环错误: {e}")
                await asyncio.sleep(0.1)

    async def _handle_message(self, message: dict) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            message: Parsed JSON message
        """
        # Update last message time (for heartbeat detection)
        self._last_message_time = datetime.now()

        # Increment message count
        self._message_count += 1

        # Generate message ID for deduplication
        token_id = message.get("token_id")
        msg_type = message.get("type")
        seq_num = message.get("sequence_number", 0)

        # Skip if no token_id
        if not token_id:
            logger.debug("Skipping message without token_id")
            return

        # Generate message ID
        message_id = f"{token_id}_{msg_type}_{seq_num}"

        # Check for duplicates
        if not self._message_cache.add(message_id):
            self._duplicate_count += 1
            logger.debug(f"Duplicate message skipped: {message_id}")
            return

        # Validate sequence number
        if seq_num > 0:  # Only validate if seq_num is provided
            last_seq = self._sequence_numbers.get(token_id, 0)
            if seq_num <= last_seq:
                # Out of order or duplicate
                logger.warning(
                    f"Sequence gap detected: {token_id} "
                    f"(seq={seq_num}, last={last_seq})"
                )
                self._sequence_gap_count += 1
                return  # Discard out-of-order message

            # Check for gaps
            if seq_num > last_seq + 1:
                gap = seq_num - last_seq - 1
                logger.warning(
                    f"Sequence gap detected: {token_id} "
                    f"missing {gap} messages (seq={seq_num}, last={last_seq})"
                )
                self._sequence_gap_count += gap

            # Update sequence number
            self._sequence_numbers[token_id] = seq_num

        # Handle message types
        if msg_type == "snapshot":
            await self._handle_snapshot(message)
        elif msg_type == "update":
            await self._handle_update(message)
        else:
            logger.debug(f"Ignoring unknown message type: {msg_type}")

    async def _handle_snapshot(self, message: dict) -> None:
        """
        Handle order book snapshot message.

        Creates a new order book from the snapshot data.

        Args:
            message: Snapshot message
        """
        # Record event received timestamp for latency tracking
        event_received_ms = int(asyncio.get_event_loop().time() * 1000)

        token_id = message.get("token_id")
        if not token_id:
            return

        # Generate trace_id for this snapshot
        trace_id = generate_trace_id()

        # Log telemetry event
        await log_event(
            TeleEventType.EVENT_RECEIVED,
            {
                "token_id": token_id,
                "message_type": "snapshot",
                "bids_count": len(message.get("bids", [])),
                "asks_count": len(message.get("asks", []))
            },
            trace_id=trace_id
        )

        bids_raw = message.get("bids", [])
        asks_raw = message.get("asks", [])

        bids = [
            Bid(
                price=Decimal(str(b["price"])),
                size=Decimal(str(b["size"])),
                token_id=token_id,
            )
            for b in bids_raw
        ]

        asks = [
            Ask(
                price=Decimal(str(a["price"])),
                size=Decimal(str(a["size"])),
                token_id=token_id,
            )
            for a in asks_raw
        ]

        # Sort orders
        bids.sort(key=lambda x: x.price, reverse=True)  # Highest first
        asks.sort(key=lambda x: x.price)  # Lowest first

        self.orderbooks[token_id] = OrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks,
            last_update=int(asyncio.get_event_loop().time() * 1000),
            event_received_ms=event_received_ms,
        )

        logger.info(f"已更新订单本: {token_id} (快照 - {len(bids)} 买单, {len(asks)} 卖单)")

    async def _handle_update(self, message: dict) -> None:
        """
        Handle order book update message.

        Updates the existing order book with new orders.

        Args:
            message: Update message
        """
        # Record event received timestamp for latency tracking
        event_received_ms = int(asyncio.get_event_loop().time() * 1000)

        token_id = message.get("token_id")
        if not token_id or token_id not in self.orderbooks:
            return

        orderbook = self.orderbooks[token_id]

        # Generate trace_id for this update
        trace_id = generate_trace_id()

        # Log telemetry event
        await log_event(
            TeleEventType.EVENT_RECEIVED,
            {
                "token_id": token_id,
                "message_type": "update",
                "bids_count": len(message.get("bids", [])),
                "asks_count": len(message.get("asks", []))
            },
            trace_id=trace_id
        )

        # Update bids
        bids_raw = message.get("bids", [])
        for b in bids_raw:
            bid = Bid(
                price=Decimal(str(b["price"])),
                size=Decimal(str(b["size"])),
                token_id=token_id,
            )
            # Remove existing bid at same price
            orderbook.bids = [existing for existing in orderbook.bids if existing.price != bid.price]
            # Add new bid if size > 0
            if bid.size > 0:
                orderbook.bids.append(bid)

        # Update asks
        asks_raw = message.get("asks", [])
        for a in asks_raw:
            ask = Ask(
                price=Decimal(str(a["price"])),
                size=Decimal(str(a["size"])),
                token_id=token_id,
            )
            # Remove existing ask at same price
            orderbook.asks = [existing for existing in orderbook.asks if existing.price != ask.price]
            # Add new ask if size > 0
            if ask.size > 0:
                orderbook.asks.append(ask)

        # Re-sort
        orderbook.bids.sort(key=lambda x: x.price, reverse=True)
        orderbook.asks.sort(key=lambda x: x.price)

        orderbook.last_update = int(asyncio.get_event_loop().time() * 1000)
        orderbook.event_received_ms = event_received_ms

        logger.info(f"已更新订单本: {token_id} (更新 - {len(bids_raw)} 买单变动, {len(asks_raw)} 卖单变动)")

    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Get the current order book for a token.

        Args:
            token_id: Token identifier

        Returns:
            OrderBook if available, None otherwise
        """
        return self.orderbooks.get(token_id)

    def get_stats(self) -> dict:
        """
        Get connection statistics.

        Returns:
            Dictionary with connection stats
        """
        # Calculate uptime if connected
        uptime_seconds = None
        if self._last_message_time and self.connected:
            uptime_seconds = (datetime.now() - self._last_message_time).total_seconds()

        # Check for heartbeat timeout
        heartbeat_ok = True
        if self._last_message_time:
            time_since_last = (datetime.now() - self._last_message_time).total_seconds()
            heartbeat_ok = time_since_last < self.heartbeat_timeout

        return {
            "connected": self.connected,
            "connect_count": self._connect_count,
            "disconnect_count": self._disconnect_count,
            "message_count": self._message_count,
            "duplicate_count": self._duplicate_count,
            "sequence_gap_count": self._sequence_gap_count,
            "subscriptions": len(self._subscriptions),
            "orderbooks": len(self.orderbooks),
            "cache_stats": self._message_cache.get_stats(),
            "heartbeat_ok": heartbeat_ok,
            "time_since_last_message_seconds": (
                (datetime.now() - self._last_message_time).total_seconds()
                if self._last_message_time
                else None
            ),
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
