"""
Event recorder module for persistent logging.

This module provides:
- Event recording to JSONL files
- Date-based sharding
- Automatic buffer flushing
- Multiple event types support

Example:
    recorder = EventRecorder()
    await recorder.record_orderbook_snapshot(
        token_id="abc123",
        bids=[...],
        asks=[...]
    )
    await recorder.flush()
"""
import json
import asyncio
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum
import aiofiles

# Event storage path
EVENTS_BASE_DIR = Path("data/events")


class EventType(str, Enum):
    """Event types for recording"""
    ORDERBOOK_SNAPSHOT = "orderbook_snapshot"
    SIGNAL = "signal"
    ORDER_REQUEST = "order_request"
    ORDER_RESULT = "order_result"


class EventRecorder:
    """
    Recorder for trading events.

    Buffers events in memory and flushes to disk periodically.
    """

    def __init__(self, buffer_size: int = 100):
        """
        Initialize event recorder.

        Args:
            buffer_size: Maximum buffer size before auto-flush
        """
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_size = buffer_size
        self._lock = asyncio.Lock()

    async def record_orderbook_snapshot(
        self,
        token_id: str,
        bids: List[Dict[str, Any]],
        asks: List[Dict[str, Any]],
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record an order book snapshot event.

        Args:
            token_id: Token identifier
            bids: List of bid orders
            asks: List of ask orders
            timestamp: Event timestamp (defaults to now)
        """
        event = {
            "event_type": EventType.ORDERBOOK_SNAPSHOT.value,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "data": {
                "token_id": token_id,
                "bids": bids,
                "asks": asks
            }
        }

        await self._add_to_buffer(event)

    async def record_signal(
        self,
        trace_id: str,
        strategy: str,
        yes_token: str,
        no_token: str,
        yes_price: Decimal,
        no_price: Decimal,
        expected_profit: Decimal,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record a strategy signal event.

        Args:
            trace_id: Trace identifier
            strategy: Strategy name
            yes_token: YES token ID
            no_token: NO token ID
            yes_price: YES token price
            no_price: NO token price
            expected_profit: Expected profit
            timestamp: Event timestamp (defaults to now)
        """
        event = {
            "event_type": EventType.SIGNAL.value,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "data": {
                "trace_id": trace_id,
                "strategy": strategy,
                "yes_token": yes_token,
                "no_token": no_token,
                "yes_price": str(yes_price),
                "no_price": str(no_price),
                "expected_profit": str(expected_profit)
            }
        }

        await self._add_to_buffer(event)

    async def record_order_request(
        self,
        trace_id: str,
        order_type: str,
        token_id: str,
        size: Decimal,
        price: Decimal,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record an order request event.

        Args:
            trace_id: Trace identifier
            order_type: Order type (buy/sell)
            token_id: Token to trade
            size: Order size
            price: Order price
            timestamp: Event timestamp (defaults to now)
        """
        event = {
            "event_type": EventType.ORDER_REQUEST.value,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "data": {
                "trace_id": trace_id,
                "order_type": order_type,
                "token_id": token_id,
                "size": str(size),
                "price": str(price)
            }
        }

        await self._add_to_buffer(event)

    async def record_order_result(
        self,
        trace_id: str,
        success: bool,
        tx_hash: str,
        gas_used: int,
        actual_price: Decimal,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record an order result event.

        Args:
            trace_id: Trace identifier
            success: Whether order succeeded
            tx_hash: Transaction hash
            gas_used: Gas used
            actual_price: Actual execution price
            timestamp: Event timestamp (defaults to now)
        """
        event = {
            "event_type": EventType.ORDER_RESULT.value,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "data": {
                "trace_id": trace_id,
                "success": success,
                "tx_hash": tx_hash,
                "gas_used": gas_used,
                "actual_price": str(actual_price)
            }
        }

        await self._add_to_buffer(event)

    async def _add_to_buffer(self, event: Dict[str, Any]) -> None:
        """
        Add event to buffer and auto-flush if needed.

        Args:
            event: Event to add
        """
        should_flush = False
        async with self._lock:
            self.buffer.append(event)
            # Check if we need to flush (but don't flush while holding lock)
            if len(self.buffer) >= self.buffer_size:
                should_flush = True

        # Flush outside the lock to avoid deadlock
        if should_flush:
            await self._flush_unlocked()

    async def _flush_unlocked(self) -> None:
        """
        Internal flush without lock acquisition.
        Caller must handle locking.
        """
        async with self._lock:
            if not self.buffer:
                return

            # Get file path for today
            file_path = get_events_path()

            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write all events to file
            async with aiofiles.open(file_path, mode='a') as f:
                for event in self.buffer:
                    await f.write(json.dumps(event) + '\n')

            # Clear buffer
            self.buffer.clear()

    async def flush(self) -> None:
        """
        Flush buffer to disk.

        Writes all buffered events to the appropriate date file.
        """
        await self._flush_unlocked()


# Global recorder instance
_global_recorder = EventRecorder()


def get_events_path(target_date: Optional[date] = None) -> Path:
    """
    Get the events file path for a specific date.

    Args:
        target_date: Target date (defaults to today)

    Returns:
        Path to events file
    """
    if target_date is None:
        target_date = date.today()

    date_str = target_date.strftime("%Y%m%d")
    return EVENTS_BASE_DIR / date_str / "events.jsonl"


async def record_event(
    event_type: EventType,
    data: Dict[str, Any]
) -> None:
    """
    Convenience function to record an event.

    Args:
        event_type: Type of event
        data: Event data
    """
    if event_type == EventType.ORDERBOOK_SNAPSHOT:
        await _global_recorder.record_orderbook_snapshot(**data)
    elif event_type == EventType.SIGNAL:
        await _global_recorder.record_signal(**data)
    elif event_type == EventType.ORDER_REQUEST:
        await _global_recorder.record_order_request(**data)
    elif event_type == EventType.ORDER_RESULT:
        await _global_recorder.record_order_result(**data)
