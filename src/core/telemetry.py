"""
Telemetry module for distributed tracing and structured logging.

This module provides:
- trace_id generation and propagation
- Structured event logging
- Context management for async operations

Example:
    trace_id = generate_trace_id()
    async with TraceContext(trace_id):
        await log_event(EventType.EVENT_RECEIVED, {"data": "value"})
"""
import uuid
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict
from dataclasses import dataclass
import aiofiles

# Telemetry log file path
TELEMETRY_LOG_FILE = Path("logs/telemetry.jsonl")


class EventType(str, Enum):
    """Telemetry event types"""
    EVENT_RECEIVED = "event_received"
    OPPORTUNITY_DETECTED = "opportunity_detected"
    RISK_PASSED = "risk_passed"
    ORDER_SUBMITTED = "order_submitted"
    FILL = "fill"
    PNL_UPDATE = "pnl_update"


@dataclass
class TelemetryEvent:
    """
    Structured telemetry event.

    Attributes:
        event_type: Type of event
        timestamp: When the event occurred (defaults to current time)
        trace_id: Unique identifier for the trace
        data: Event-specific data
    """
    event_type: EventType
    trace_id: str
    data: Dict[str, Any]
    timestamp: datetime = None

    def __post_init__(self):
        """Set default timestamp if not provided"""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "data": self.data
        }


# Context variable for trace_id storage
_trace_context: Optional[str] = None


def generate_trace_id() -> str:
    """
    Generate a unique trace ID.

    Returns:
        UUID v4 string
    """
    return str(uuid.uuid4())


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID from context.

    Returns:
        Current trace_id or None if not in context
    """
    global _trace_context
    return _trace_context


class TraceContext:
    """
    Context manager for trace_id propagation.

    Usage:
        async with TraceContext(trace_id):
            # All code here has access to trace_id
            await log_event(...)
    """

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.previous_trace_id: Optional[str] = None

    async def __aenter__(self):
        global _trace_context
        self.previous_trace_id = _trace_context
        _trace_context = self.trace_id
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        global _trace_context
        _trace_context = self.previous_trace_id
        return None


async def _write_event_log(event: TelemetryEvent) -> None:
    """
    Write event to telemetry log file.

    Args:
        event: Event to write
    """
    # Ensure log directory exists
    TELEMETRY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write to file (append mode)
    async with aiofiles.open(TELEMETRY_LOG_FILE, mode='a') as f:
        await f.write(json.dumps(event.to_dict()) + '\n')


async def log_event(
    event_type: EventType,
    data: Dict[str, Any],
    trace_id: Optional[str] = None
) -> str:
    """
    Log a telemetry event.

    Args:
        event_type: Type of event
        data: Event-specific data
        trace_id: Optional trace_id (uses current context if not provided)

    Returns:
        The trace_id used for this event
    """
    # Use provided trace_id, current context, or generate new
    if trace_id is None:
        trace_id = get_current_trace_id()

    if trace_id is None:
        # No trace_id in context, generate new one
        trace_id = generate_trace_id()

    # Create event
    event = TelemetryEvent(
        event_type=event_type,
        trace_id=trace_id,
        data=data
    )

    # Write to log
    await _write_event_log(event)

    return trace_id
