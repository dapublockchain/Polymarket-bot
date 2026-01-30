"""
Polymarket CLOB WebSocket Connector.

Connects to Polymarket's WebSocket API for real-time order book updates.
"""
import asyncio
import json
import logging
from decimal import Decimal
from typing import Optional, Dict

import websockets

from src.core.models import OrderBook, Bid, Ask

logger = logging.getLogger(__name__)


class PolymarketWSClient:
    """
    WebSocket client for Polymarket CLOB.

    Maintains local order books for subscribed tokens and handles
    automatic reconnection with exponential backoff.
    """

    def __init__(
        self,
        url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        use_exponential_backoff: bool = True,
    ):
        """
        Initialize the WebSocket client.

        Args:
            url: WebSocket URL
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Initial delay between reconnections (seconds)
            use_exponential_backoff: Whether to use exponential backoff
        """
        self.url = url
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.use_exponential_backoff = use_exponential_backoff
        self.connected: bool = False
        self.orderbooks: Dict[str, OrderBook] = {}
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._subscriptions: set = set()

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
                logger.info(f"Connecting to {self.url} (attempt {attempt + 1})")
                self._ws = await websockets.connect(self.url)
                self.connected = True
                logger.info("Connected successfully")

                # Resubscribe to previous subscriptions
                for token_id in self._subscriptions:
                    await self._send_subscription(token_id)

                return
            except Exception as e:
                attempt += 1
                logger.warning(f"Connection failed: {e}")

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

        logger.info("Disconnected")

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
        logger.info(f"Subscribed to {token_id}")

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
                message = json.loads(message_raw)

                await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed, attempting to reconnect...")
                self.connected = False
                await self.connect()

            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                await asyncio.sleep(0.1)

    async def _handle_message(self, message: dict) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            message: Parsed JSON message
        """
        msg_type = message.get("type")

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
        token_id = message.get("token_id")
        if not token_id:
            return

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
        )

        logger.debug(f"Updated order book for {token_id}")

    async def _handle_update(self, message: dict) -> None:
        """
        Handle order book update message.

        Updates the existing order book with new orders.

        Args:
            message: Update message
        """
        token_id = message.get("token_id")
        if not token_id or token_id not in self.orderbooks:
            return

        orderbook = self.orderbooks[token_id]

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

        logger.debug(f"Updated order book for {token_id}")

    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Get the current order book for a token.

        Args:
            token_id: Token identifier

        Returns:
            OrderBook if available, None otherwise
        """
        return self.orderbooks.get(token_id)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
