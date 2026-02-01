"""
Unit tests for Event Replayer module.
"""
import pytest
import json
import asyncio
from datetime import date, datetime
from pathlib import Path
from decimal import Decimal

from src.backtesting.event_replayer import EventReplayer, ReplayMode
from src.core.recorder import EventType, EVENTS_BASE_DIR


@pytest.fixture
def temp_event_dir(tmp_path):
    """Create temporary event directory."""
    event_dir = tmp_path / "events"
    event_dir.mkdir()
    return event_dir


@pytest.fixture
def sample_events():
    """Create sample events for testing."""
    return [
        {
            "event_type": EventType.ORDERBOOK_SNAPSHOT.value,
            "timestamp": "2026-02-01T10:00:00",
            "data": {
                "token_id": "token_1",
                "bids": [{"price": "0.50", "size": "100"}],
                "asks": [{"price": "0.51", "size": "100"}],
            }
        },
        {
            "event_type": EventType.SIGNAL.value,
            "timestamp": "2026-02-01T10:01:00",
            "data": {
                "yes_token": "token_1",
                "no_token": "token_2",
                "yes_price": "0.50",
                "no_price": "0.50",
                "expected_profit": "0.05",
            }
        },
        {
            "event_type": EventType.ORDERBOOK_SNAPSHOT.value,
            "timestamp": "2026-02-01T10:02:00",
            "data": {
                "token_id": "token_2",
                "bids": [{"price": "0.49", "size": "100"}],
                "asks": [{"price": "0.50", "size": "100"}],
            }
        },
    ]


class TestEventReplayerInit:
    """Test suite for EventReplayer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        replayer = EventReplayer()

        assert replayer.base_dir == EVENTS_BASE_DIR
        assert replayer.mode == ReplayMode.FAST_FORWARD
        assert replayer.speed_multiplier == 1.0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        replayer = EventReplayer(
            base_dir=Path("/custom/path"),
            mode=ReplayMode.REAL_TIME,
            speed_multiplier=2.0,
        )

        assert replayer.base_dir == Path("/custom/path")
        assert replayer.mode == ReplayMode.REAL_TIME
        assert replayer.speed_multiplier == 2.0


class TestGetEventFile:
    """Test suite for get_event_file method."""

    def test_get_event_file(self):
        """Test getting event file path."""
        replayer = EventReplayer()
        event_date = date(2026, 2, 1)

        path = replayer.get_event_file(event_date)

        assert path == EVENTS_BASE_DIR / "2026-02-01.jsonl"


class TestLoadEvents:
    """Test suite for load_events method."""

    @pytest.mark.asyncio
    async def test_load_events_from_file(self, temp_event_dir, sample_events):
        """Test loading events from file."""
        # Create event file
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        # Load events
        replayer = EventReplayer(base_dir=temp_event_dir)
        events = await replayer.load_events(event_file)

        assert len(events) == 3
        assert events[0]["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value
        assert events[1]["event_type"] == EventType.SIGNAL.value

    @pytest.mark.asyncio
    async def test_load_events_sorts_by_timestamp(self, temp_event_dir):
        """Test that loaded events are sorted by timestamp."""
        # Create events with out-of-order timestamps
        events = [
            {
                "event_type": "test",
                "timestamp": "2026-02-01T10:02:00",
                "data": {},
            },
            {
                "event_type": "test",
                "timestamp": "2026-02-01T10:00:00",
                "data": {},
            },
            {
                "event_type": "test",
                "timestamp": "2026-02-01T10:01:00",
                "data": {},
            },
        ]

        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)
        loaded = await replayer.load_events(event_file)

        assert loaded[0]["timestamp"] == "2026-02-01T10:00:00"
        assert loaded[1]["timestamp"] == "2026-02-01T10:01:00"
        assert loaded[2]["timestamp"] == "2026-02-01T10:02:00"

    @pytest.mark.asyncio
    async def test_load_events_nonexistent_file(self, temp_event_dir):
        """Test loading from nonexistent file."""
        replayer = EventReplayer(base_dir=temp_event_dir)
        event_file = temp_event_dir / "nonexistent.jsonl"

        events = await replayer.load_events(event_file)

        assert events == []


class TestReplayDate:
    """Test suite for replay_date method."""

    @pytest.mark.asyncio
    async def test_replay_date_yields_events(self, temp_event_dir, sample_events):
        """Test replaying events from a date."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)
        events = []

        async for event in replayer.replay_date(date(2026, 2, 1)):
            events.append(event)

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_replay_date_with_filter(self, temp_event_dir, sample_events):
        """Test replaying with event filter."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)

        # Filter for only ORDERBOOK_SNAPSHOT events
        def orderbook_filter(event):
            return event["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value

        events = []
        async for event in replayer.replay_date(date(2026, 2, 1), event_filter=orderbook_filter):
            events.append(event)

        assert len(events) == 2
        assert all(e["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value for e in events)

    @pytest.mark.asyncio
    async def test_replay_date_with_progress_callback(self, temp_event_dir, sample_events):
        """Test replaying with progress callback."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)

        progress_updates = []

        async def progress_callback(current, total):
            progress_updates.append((current, total))

        events = []
        async for event in replayer.replay_date(date(2026, 2, 1), progress_callback=progress_callback):
            events.append(event)

        assert len(progress_updates) == 3
        assert progress_updates[-1] == (3, 3)  # Final update


class TestReplayToken:
    """Test suite for replay_token method."""

    @pytest.mark.asyncio
    async def test_replay_token_filters_events(self, temp_event_dir, sample_events):
        """Test replaying events for specific token."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)

        events = []
        async for event in replayer.replay_token(date(2026, 2, 1), "token_1"):
            events.append(event)

        # Should get the orderbook snapshot for token_1 and the signal
        # (signal includes token_1 as yes_token)
        assert len(events) >= 1


class TestCountEvents:
    """Test suite for count_events method."""

    @pytest.mark.asyncio
    async def test_count_all_events(self, temp_event_dir, sample_events):
        """Test counting all events."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)
        count = await replayer.count_events(date(2026, 2, 1))

        assert count == 3

    @pytest.mark.asyncio
    async def test_count_events_by_type(self, temp_event_dir, sample_events):
        """Test counting events by type."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)

        count = await replayer.count_events(date(2026, 2, 1), EventType.ORDERBOOK_SNAPSHOT)

        assert count == 2


class TestGetStatistics:
    """Test suite for get_statistics method."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, temp_event_dir, sample_events):
        """Test getting statistics for date range."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)
        stats = await replayer.get_statistics(date(2026, 2, 1), date(2026, 2, 1))

        assert stats["total_events"] == 3
        assert stats["orderbook_snapshots"] == 2
        assert stats["signals"] == 1
        assert stats["order_requests"] == 0
        assert stats["order_results"] == 0
        assert "token_1" in stats["tokens"]


class TestFindOpportunities:
    """Test suite for find_opportunities method."""

    @pytest.mark.asyncio
    async def test_find_opportunities(self, temp_event_dir, sample_events):
        """Test finding trading opportunities."""
        event_file = temp_event_dir / "2026-02-01.jsonl"
        with open(event_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        replayer = EventReplayer(base_dir=temp_event_dir)
        opportunities = await replayer.find_opportunities(date(2026, 2, 1), min_profit=0.01)

        # Signal has 0.05 (5%) profit, which is >= 0.01 (1%)
        assert len(opportunities) == 1
        assert opportunities[0]["event_type"] == EventType.SIGNAL.value
