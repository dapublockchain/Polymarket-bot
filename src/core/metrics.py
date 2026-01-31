"""
Metrics module for latency tracking and aggregation.

This module provides:
- Latency metric recording
- Time window aggregation
- Percentile calculation
- Metrics persistence to JSONL

Example:
    collector = MetricsCollector()
    collector.record_latency(
        trace_id="abc123",
        ws_to_book_update_ms=10.5,
        book_to_signal_ms=5.2,
        signal_to_risk_ms=3.1,
        risk_to_send_ms=15.8
    )
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import asyncio
import aiofiles

# Metrics log file path
METRICS_LOG_FILE = Path("logs/metrics.jsonl")


@dataclass
class LatencyMetric:
    """
    Latency metric for a single trace.

    Attributes:
        trace_id: Unique trace identifier
        ws_to_book_update_ms: WebSocket to order book update latency
        book_to_signal_ms: Order book to signal generation latency
        signal_to_risk_ms: Signal to risk check latency
        risk_to_send_ms: Risk check to order send latency
        end_to_end_ms: Total end-to-end latency
        timestamp: When the metric was recorded
    """
    trace_id: str
    ws_to_book_update_ms: float
    book_to_signal_ms: float
    signal_to_risk_ms: float
    risk_to_send_ms: float
    end_to_end_ms: float
    timestamp: datetime = None

    def __post_init__(self):
        """Set default timestamp if not provided"""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "trace_id": self.trace_id,
            "ws_to_book_update_ms": self.ws_to_book_update_ms,
            "book_to_signal_ms": self.book_to_signal_ms,
            "signal_to_risk_ms": self.signal_to_risk_ms,
            "risk_to_send_ms": self.risk_to_send_ms,
            "end_to_end_ms": self.end_to_end_ms,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MetricsSnapshot:
    """
    Aggregated metrics snapshot for a time window.

    Attributes:
        count: Number of metrics in the window
        avg_end_to_end_ms: Average end-to-end latency
        min_end_to_end_ms: Minimum end-to-end latency
        max_end_to_end_ms: Maximum end-to-end latency
        p50_end_to_end_ms: 50th percentile latency
        p95_end_to_end_ms: 95th percentile latency
        p99_end_to_end_ms: 99th percentile latency
        window_start: Window start time
        window_end: Window end time
    """
    count: int
    avg_end_to_end_ms: float
    min_end_to_end_ms: float
    max_end_to_end_ms: float
    p50_end_to_end_ms: Optional[float] = None
    p95_end_to_end_ms: Optional[float] = None
    p99_end_to_end_ms: Optional[float] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class TimeWindow:
    """Time window for metrics aggregation"""

    def __init__(self, seconds: int):
        """
        Initialize time window.

        Args:
            seconds: Window size in seconds
        """
        self.seconds = seconds

    def contains(self, timestamp: datetime) -> bool:
        """
        Check if a timestamp is within the time window.

        Args:
            timestamp: Timestamp to check

        Returns:
            True if timestamp is within the window
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=self.seconds)
        return window_start <= timestamp <= now


class MetricsCollector:
    """
    Collector for latency metrics.

    Provides methods to record metrics and calculate aggregations.
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: List[LatencyMetric] = []

    def record_latency(
        self,
        trace_id: str,
        ws_to_book_update_ms: float,
        book_to_signal_ms: float = 0.0,
        signal_to_risk_ms: float = 0.0,
        risk_to_send_ms: float = 0.0
    ) -> None:
        """
        Record a latency metric.

        Args:
            trace_id: Unique trace identifier
            ws_to_book_update_ms: WebSocket to order book update latency
            book_to_signal_ms: Order book to signal generation latency
            signal_to_risk_ms: Signal to risk check latency
            risk_to_send_ms: Risk check to order send latency
        """
        # Calculate end-to-end latency
        end_to_end_ms = (
            ws_to_book_update_ms +
            book_to_signal_ms +
            signal_to_risk_ms +
            risk_to_send_ms
        )

        metric = LatencyMetric(
            trace_id=trace_id,
            ws_to_book_update_ms=ws_to_book_update_ms,
            book_to_signal_ms=book_to_signal_ms,
            signal_to_risk_ms=signal_to_risk_ms,
            risk_to_send_ms=risk_to_send_ms,
            end_to_end_ms=end_to_end_ms
        )

        self.metrics.append(metric)

    def get_metrics_in_window(self, window: TimeWindow) -> List[LatencyMetric]:
        """
        Get metrics within a time window.

        Args:
            window: Time window to filter by

        Returns:
            List of metrics within the window
        """
        return [
            m for m in self.metrics
            if window.contains(m.timestamp)
        ]

    def calculate_snapshot(self, window: TimeWindow) -> MetricsSnapshot:
        """
        Calculate aggregated metrics snapshot for a time window.

        Args:
            window: Time window to aggregate over

        Returns:
            MetricsSnapshot with aggregated statistics
        """
        window_metrics = self.get_metrics_in_window(window)

        if not window_metrics:
            return MetricsSnapshot(
                count=0,
                avg_end_to_end_ms=0.0,
                min_end_to_end_ms=0.0,
                max_end_to_end_ms=0.0
            )

        latencies = [m.end_to_end_ms for m in window_metrics]

        # Calculate basic statistics
        count = len(latencies)
        avg_latency = sum(latencies) / count
        min_latency = min(latencies)
        max_latency = max(latencies)

        # Calculate percentiles
        percentiles = calculate_percentiles(latencies)

        return MetricsSnapshot(
            count=count,
            avg_end_to_end_ms=avg_latency,
            min_end_to_end_ms=min_latency,
            max_end_to_end_ms=max_latency,
            p50_end_to_end_ms=percentiles.get("p50") if percentiles else None,
            p95_end_to_end_ms=percentiles.get("p95") if percentiles else None,
            p99_end_to_end_ms=percentiles.get("p99") if percentiles else None,
            window_start=datetime.now() - timedelta(seconds=window.seconds),
            window_end=datetime.now()
        )


def calculate_percentiles(values: List[float]) -> Optional[Dict[str, float]]:
    """
    Calculate percentiles for a list of values.

    Args:
        values: List of numeric values

    Returns:
        Dictionary with p50, p95, p99, or None if values is empty
    """
    if not values:
        return None

    sorted_values = sorted(values)
    n = len(sorted_values)

    # Calculate percentiles using linear interpolation
    def get_percentile(p: float) -> float:
        """Get percentile using linear interpolation"""
        index = (n - 1) * p / 100
        lower = int(index)
        upper = min(lower + 1, n - 1)

        if lower == upper:
            return sorted_values[lower]

        # Linear interpolation
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    return {
        "p50": get_percentile(50),
        "p95": get_percentile(95),
        "p99": get_percentile(99)
    }


# Global metrics collector instance
_global_collector = MetricsCollector()


async def _write_metrics_log(data: str) -> None:
    """
    Write metrics data to log file.

    Args:
        data: JSON string to write
    """
    # Ensure log directory exists
    METRICS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write to file (append mode)
    async with aiofiles.open(METRICS_LOG_FILE, mode='a') as f:
        await f.write(data + '\n')


async def record_latency(
    trace_id: str,
    ws_to_book_update_ms: float,
    book_to_signal_ms: float = 0.0,
    signal_to_risk_ms: float = 0.0,
    risk_to_send_ms: float = 0.0
) -> None:
    """
    Record a latency metric (global function).

    Args:
        trace_id: Unique trace identifier
        ws_to_book_update_ms: WebSocket to order book update latency
        book_to_signal_ms: Order book to signal generation latency
        signal_to_risk_ms: Signal to risk check latency
        risk_to_send_ms: Risk check to order send latency
    """
    # Record to global collector
    _global_collector.record_latency(
        trace_id=trace_id,
        ws_to_book_update_ms=ws_to_book_update_ms,
        book_to_signal_ms=book_to_signal_ms,
        signal_to_risk_ms=signal_to_risk_ms,
        risk_to_send_ms=risk_to_send_ms
    )

    # Get the last metric
    metric = _global_collector.metrics[-1]

    # Write to log file
    await _write_metrics_log(json.dumps(metric.to_dict()))
