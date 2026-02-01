"""
Event Replayer module for replaying recorded events.

This module provides:
- Event loading from JSONL files
- Time-accurate event replay
- Multiple replay modes (real-time, fast-forward)
- Event filtering and selection

Example:
    replayer = EventReplayer()
    async for event in replayer.replay_date(date(2026, 2, 1)):
        print(event)
"""
import json
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator, Callable
from enum import Enum
import aiofiles

from src.core.recorder import EventType, EVENTS_BASE_DIR


class ReplayMode(str, Enum):
    """Replay speed modes."""
    REAL_TIME = "real_time"  # Replay at original speed
    FAST_FORWARD = "fast_forward"  # Replay as fast as possible
    CUSTOM = "custom"  # Custom speed multiplier


class EventReplayer:
    """
    Replays recorded trading events.

    Supports time-accurate replay with adjustable speed.
    """

    def __init__(
        self,
        base_dir: Path = EVENTS_BASE_DIR,
        mode: ReplayMode = ReplayMode.FAST_FORWARD,
        speed_multiplier: float = 1.0,
    ):
        """
        Initialize event replayer.

        Args:
            base_dir: Base directory for event files
            mode: Replay mode
            speed_multiplier: Speed multiplier (only for CUSTOM mode)
        """
        self.base_dir = base_dir
        self.mode = mode
        self.speed_multiplier = speed_multiplier

    def get_event_file(self, event_date: date) -> Path:
        """
        Get path to event file for a given date.

        Args:
            event_date: Date to replay

        Returns:
            Path to event file
        """
        return self.base_dir / f"{event_date.isoformat()}.jsonl"

    async def load_events(self, event_file: Path) -> List[Dict[str, Any]]:
        """
        Load all events from a file.

        Args:
            event_file: Path to event file

        Returns:
            List of events
        """
        if not event_file.exists():
            return []

        events = []
        async with aiofiles.open(event_file, "r") as f:
            async for line in f:
                if line.strip():
                    events.append(json.loads(line))

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])
        return events

    async def replay_date(
        self,
        event_date: date,
        event_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Replay events from a specific date.

        Args:
            event_date: Date to replay
            event_filter: Optional filter function for events
            progress_callback: Optional callback for progress updates

        Yields:
            Events in chronological order
        """
        event_file = self.get_event_file(event_date)
        events = await self.load_events(event_file)

        if not events:
            return

        total_events = len(events)
        last_timestamp: Optional[datetime] = None

        for i, event in enumerate(events):
            # Apply filter if provided
            if event_filter and not event_filter(event):
                continue

            # Parse timestamp
            event_ts = datetime.fromisoformat(event["timestamp"])

            # Sleep to maintain timing (for real-time mode)
            if last_timestamp and self.mode == ReplayMode.REAL_TIME:
                delay = (event_ts - last_timestamp).total_seconds()
                if delay > 0:
                    await asyncio.sleep(delay)

            # Custom speed mode
            elif last_timestamp and self.mode == ReplayMode.CUSTOM:
                delay = (event_ts - last_timestamp).total_seconds() / self.speed_multiplier
                if delay > 0:
                    await asyncio.sleep(delay)

            last_timestamp = event_ts

            # Call progress callback if provided
            if progress_callback:
                await progress_callback(i + 1, total_events)

            yield event

    async def replay_date_range(
        self,
        start_date: date,
        end_date: date,
        event_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Replay events from a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            event_filter: Optional filter function for events

        Yields:
            Events in chronological order
        """
        current_date = start_date
        all_events: List[Dict[str, Any]] = []

        # Load all events from date range
        while current_date <= end_date:
            event_file = self.get_event_file(current_date)
            if event_file.exists():
                events = await self.load_events(event_file)
                if event_filter:
                    events = [e for e in events if event_filter(e)]
                all_events.extend(events)

            current_date += timedelta(days=1)

        # Sort all events by timestamp
        all_events.sort(key=lambda e: e["timestamp"])

        # Yield events
        for event in all_events:
            yield event

    async def replay_token(
        self,
        event_date: date,
        token_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Replay events for a specific token.

        Args:
            event_date: Date to replay
            token_id: Token identifier to filter by

        Yields:
            Events for the specified token
        """
        def token_filter(event: Dict[str, Any]) -> bool:
            if event["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value:
                return event["data"]["token_id"] == token_id
            elif event["event_type"] == EventType.SIGNAL.value:
                return (
                    event["data"]["yes_token"] == token_id or
                    event["data"]["no_token"] == token_id
                )
            return True

        async for event in self.replay_date(event_date, token_filter):
            yield event

    async def count_events(
        self,
        event_date: date,
        event_type: Optional[EventType] = None,
    ) -> int:
        """
        Count events for a date.

        Args:
            event_date: Date to count events for
            event_type: Optional event type filter

        Returns:
            Number of events
        """
        event_file = self.get_event_file(event_date)
        if not event_file.exists():
            return 0

        count = 0
        async with aiofiles.open(event_file, "r") as f:
            async for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event_type is None or event["event_type"] == event_type.value:
                        count += 1

        return count

    async def get_statistics(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get statistics for a date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_events": 0,
            "orderbook_snapshots": 0,
            "signals": 0,
            "order_requests": 0,
            "order_results": 0,
            "tokens": set(),
            "dates": [],
        }

        current_date = start_date
        while current_date <= end_date:
            event_file = self.get_event_file(current_date)
            if event_file.exists():
                stats["dates"].append(current_date.isoformat())

                async with aiofiles.open(event_file, "r") as f:
                    async for line in f:
                        if line.strip():
                            event = json.loads(line)
                            stats["total_events"] += 1

                            event_type = event["event_type"]
                            if event_type == EventType.ORDERBOOK_SNAPSHOT.value:
                                stats["orderbook_snapshots"] += 1
                                stats["tokens"].add(event["data"]["token_id"])
                            elif event_type == EventType.SIGNAL.value:
                                stats["signals"] += 1
                            elif event_type == EventType.ORDER_REQUEST.value:
                                stats["order_requests"] += 1
                            elif event_type == EventType.ORDER_RESULT.value:
                                stats["order_results"] += 1

            current_date += timedelta(days=1)

        # Convert set to list for JSON serialization
        stats["tokens"] = list(stats["tokens"])
        return stats

    async def find_opportunities(
        self,
        event_date: date,
        min_profit: float = 0.01,
    ) -> List[Dict[str, Any]]:
        """
        Find trading opportunities from recorded events.

        Args:
            event_date: Date to analyze
            min_profit: Minimum profit threshold

        Returns:
            List of opportunities
        """
        opportunities = []

        async for event in self.replay_date(event_date):
            if event["event_type"] == EventType.SIGNAL.value:
                expected_profit = float(event["data"]["expected_profit"])
                if expected_profit >= min_profit:
                    opportunities.append(event)

        return opportunities
